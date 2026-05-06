"""Tests for PathResolver — Sprint 2 source-ingest pipeline.

Covers the local / upload / git branches plus the security-relevant
edge cases: zip-slip, oversized archive, git URL whitelist, missing
git binary, missing local path.
"""
import os
import tempfile
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from scans.models import Project
from scans.services.path_resolver import PathResolver


def _make_zip(contents):
    """Build an in-memory zip with the given {name: bytes} dict."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in contents.items():
            zf.writestr(name, data)
    return buf.getvalue()


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="resolver-user", password="x")

    def setUp(self):
        self.resolver = PathResolver()


class LocalResolveTests(_Base):
    def test_existing_path_resolves_with_noop_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.objects.create(
                owner=self.user, name="local",
                source_type="local", repo_path=tmp,
            )
            resolved = self.resolver.resolve(project)
            self.assertEqual(resolved.path, tmp)
            # cleanup() should not blow up and should not delete the dir.
            resolved.cleanup()
            self.assertTrue(os.path.exists(tmp))

    def test_missing_path_raises(self):
        project = Project.objects.create(
            owner=self.user, name="missing",
            source_type="local", repo_path="/definitely/not/a/path/zzz",
        )
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)

    def test_empty_path_raises(self):
        project = Project.objects.create(
            owner=self.user, name="empty",
            source_type="local", repo_path="",
        )
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)


class UploadResolveTests(_Base):
    def _project_with_zip(self, contents, name="archive.zip"):
        zip_bytes = _make_zip(contents)
        project = Project.objects.create(
            owner=self.user, name="upload",
            source_type="upload",
            source_archive=SimpleUploadedFile(name, zip_bytes),
        )
        return project

    def test_extracts_into_temp_dir(self):
        project = self._project_with_zip({
            "src/main.py": b"print('hi')\n",
            "README.md": b"# test\n",
        })
        resolved = self.resolver.resolve(project)
        try:
            self.assertTrue(os.path.isdir(resolved.path))
            self.assertTrue(os.path.exists(os.path.join(resolved.path, "src", "main.py")))
        finally:
            resolved.cleanup()
            self.assertFalse(os.path.exists(resolved.path))

    def test_zip_slip_rejected(self):
        project = self._project_with_zip({
            "../../../tmp/escaped.txt": b"pwned",
        })
        with self.assertRaises(ValueError) as cm:
            self.resolver.resolve(project)
        self.assertIn("unsafe path", str(cm.exception).lower())

    def test_absolute_path_rejected(self):
        project = self._project_with_zip({
            "/etc/passwd": b"root:x:0:0::/root:/bin/sh\n",
        })
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)

    @override_settings(SAST_MAX_EXTRACTED_SIZE_MB=1)
    def test_oversized_archive_rejected(self):
        # 2 MB of zeros (compresses tiny but extracts to 2 MB)
        project = self._project_with_zip({
            "big.bin": b"\x00" * (2 * 1024 * 1024),
        })
        with self.assertRaises(ValueError) as cm:
            self.resolver.resolve(project)
        self.assertIn("zip bomb", str(cm.exception).lower())

    def test_extraction_failure_cleans_up_temp_dir(self):
        # Use an obviously-malformed "zip" (just text bytes).
        bad_bytes = b"this is not a zip"
        project = Project.objects.create(
            owner=self.user, name="bad",
            source_type="upload",
            source_archive=SimpleUploadedFile("bad.zip", bad_bytes),
        )
        with self.assertRaises(zipfile.BadZipFile):
            self.resolver.resolve(project)
        # No assertion on the temp dir path — _safe_rmtree ran on the
        # short-lived dir we never received a handle to.

    def test_missing_archive_raises(self):
        project = Project.objects.create(
            owner=self.user, name="no-archive",
            source_type="upload",
        )
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)


class GitResolveTests(_Base):
    def _git_project(self, url, branch=""):
        return Project.objects.create(
            owner=self.user, name="git",
            source_type="git", git_url=url, git_branch=branch,
        )

    def test_https_github_url_accepted(self):
        # Mock subprocess.run so the test doesn't actually clone.
        project = self._git_project("https://github.com/octocat/Hello-World.git")

        with mock.patch("scans.services.path_resolver.subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stderr="")
            resolved = self.resolver.resolve(project)

        try:
            self.assertTrue(os.path.isdir(resolved.path))
            # Confirm git was invoked with the right shape
            args = mrun.call_args.args[0]
            self.assertEqual(args[0], "git")
            self.assertEqual(args[1], "clone")
            self.assertIn("--depth", args)
            self.assertEqual(args[-2], "https://github.com/octocat/Hello-World.git")
        finally:
            resolved.cleanup()

    def test_https_gitlab_url_accepted(self):
        project = self._git_project("https://gitlab.com/some/repo")
        with mock.patch("scans.services.path_resolver.subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stderr="")
            resolved = self.resolver.resolve(project)
        resolved.cleanup()

    def test_branch_passed_to_git(self):
        project = self._git_project(
            "https://github.com/x/y", branch="develop",
        )
        with mock.patch("scans.services.path_resolver.subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stderr="")
            resolved = self.resolver.resolve(project)
        try:
            args = mrun.call_args.args[0]
            self.assertIn("--branch", args)
            self.assertIn("develop", args)
        finally:
            resolved.cleanup()

    def test_ssh_url_rejected(self):
        project = self._git_project("git@github.com:x/y.git")
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)

    def test_arbitrary_host_rejected(self):
        project = self._git_project("https://evil.example.com/x/y.git")
        with self.assertRaises(ValueError) as cm:
            self.resolver.resolve(project)
        self.assertIn("not allowed", str(cm.exception).lower())

    def test_empty_url_rejected(self):
        project = self._git_project("")
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)

    def test_clone_failure_cleans_up_and_raises(self):
        project = self._git_project("https://github.com/x/y")
        with mock.patch("scans.services.path_resolver.subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=128, stderr="not found")
            with self.assertRaises(RuntimeError) as cm:
                self.resolver.resolve(project)
            self.assertIn("git clone failed", str(cm.exception))

    def test_missing_git_binary_raises_clear_error(self):
        project = self._git_project("https://github.com/x/y")
        with mock.patch(
            "scans.services.path_resolver.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            with self.assertRaises(RuntimeError) as cm:
                self.resolver.resolve(project)
            self.assertIn("git executable not found", str(cm.exception))


class UnknownSourceTypeTests(_Base):
    def test_unknown_source_type_raises(self):
        project = Project(owner=self.user, name="bad", source_type="weird")
        with self.assertRaises(ValueError):
            self.resolver.resolve(project)
