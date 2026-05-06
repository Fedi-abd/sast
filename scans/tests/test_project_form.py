"""Tests for ProjectForm — Sprint 2 source-type-aware validation."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from scans.forms import ProjectForm
from scans.models import Project


class ProjectFormValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="form-user", password="x")

    def test_local_requires_repo_path(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_LOCAL,
            "repo_path": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("repo_path", form.errors)

    def test_local_with_repo_path_valid(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_LOCAL,
            "repo_path": "/some/path",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_upload_requires_archive_on_create(self):
        form = ProjectForm(
            data={
                "name": "p1",
                "language": "python",
                "source_type": Project.SOURCE_UPLOAD,
            },
            files={},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("source_archive", form.errors)

    def test_upload_with_archive_valid(self):
        form = ProjectForm(
            data={
                "name": "p1",
                "language": "python",
                "source_type": Project.SOURCE_UPLOAD,
            },
            files={"source_archive": SimpleUploadedFile("x.zip", b"PK\x05\x06")},
        )
        self.assertTrue(form.is_valid(), form.errors)
        # Saving should populate source_filename from the upload's name.
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()
        self.assertEqual(instance.source_filename, "x.zip")

    def test_git_requires_url(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_GIT,
            "git_url": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("git_url", form.errors)

    def test_git_with_url_valid(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_GIT,
            "git_url": "https://github.com/x/y.git",
            "git_branch": "main",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_git_url_host_rejected_at_form_level(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_GIT,
            "git_url": "https://evil.example.com/x/y.git",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("git_url", form.errors)

    def test_git_url_must_be_https(self):
        form = ProjectForm(data={
            "name": "p1",
            "language": "python",
            "source_type": Project.SOURCE_GIT,
            "git_url": "ftp://github.com/x/y",
        })
        self.assertFalse(form.is_valid())

    def test_local_clears_other_source_fields_on_save(self):
        form = ProjectForm(
            data={
                "name": "p1",
                "language": "python",
                "source_type": Project.SOURCE_LOCAL,
                "repo_path": "/some/path",
                # Stray data left over from earlier toggling:
                "git_url": "https://github.com/x/y",
                "git_branch": "main",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()
        self.assertEqual(instance.repo_path, "/some/path")
        self.assertEqual(instance.git_url, "")
        self.assertEqual(instance.git_branch, "")

    def test_git_clears_other_source_fields_on_save(self):
        form = ProjectForm(
            data={
                "name": "p1",
                "language": "python",
                "source_type": Project.SOURCE_GIT,
                "git_url": "https://github.com/x/y",
                # Stray local data:
                "repo_path": "/should/not/be/saved",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()
        self.assertEqual(instance.repo_path, "")
        self.assertEqual(instance.git_url, "https://github.com/x/y")

    def test_source_type_locked_on_edit(self):
        # Existing upload project. A POST that tries to switch to git
        # should be ignored and the source_type pinned to "upload".
        existing = Project.objects.create(
            owner=self.user,
            name="locked",
            source_type=Project.SOURCE_UPLOAD,
            source_archive=SimpleUploadedFile("x.zip", b"PK\x05\x06"),
            source_filename="x.zip",
        )
        form = ProjectForm(
            data={
                "name": "locked",
                "language": "python",
                "source_type": Project.SOURCE_GIT,  # malicious POST
                "git_url": "https://github.com/x/y",
            },
            instance=existing,
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.source_type, Project.SOURCE_UPLOAD)
        # And the git fields didn't sneak in either (cleared because
        # source_type stayed "upload").
        self.assertEqual(instance.git_url, "")

    def test_source_filename_unchanged_on_edit_without_reupload(self):
        existing = Project.objects.create(
            owner=self.user,
            name="archived",
            source_type=Project.SOURCE_UPLOAD,
            source_archive=SimpleUploadedFile("webgoat-v1.zip", b"PK\x05\x06"),
            source_filename="webgoat-v1.zip",
        )
        # Edit submission without uploading a new file. The form
        # rebinds the existing FieldFile; source_filename must stay
        # "webgoat-v1.zip", not get overwritten with the storage path.
        form = ProjectForm(
            data={
                "name": "archived",
                "language": "python",
                "source_type": Project.SOURCE_UPLOAD,
            },
            instance=existing,
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.source_filename, "webgoat-v1.zip")
