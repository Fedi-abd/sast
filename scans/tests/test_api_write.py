"""Tests for the API write endpoints.

Covers:
  - POST /api/projects/  (create, with each source type)
  - PATCH /api/projects/<id>/  (partial update + source_type lock)
  - DELETE /api/projects/<id>/  (own-only)
  - POST /api/scans/trigger/  (single tool, "both", lock behavior)

Trust-boundary checks live alongside happy-path checks because the
fastest way to spot an ownership bug is to ask "can Alice touch Bob's
data?" right next to "can Alice touch her own?".
"""
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from scans.models import PlatformSettings, Project, Scan


class ProjectCreateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.client.force_login(self.alice)
        self.url = reverse("project-list")
        # Local creates validate path existence now, so use a real dir.
        self.tmp = tempfile.mkdtemp()
        # hide_local_source is on by default; these tests exercise the
        # local source type, so allow it explicitly.
        row = PlatformSettings.get_solo()
        row.hide_local_source = False
        row.save()

    def test_create_local_project_succeeds(self):
        response = self.client.post(
            self.url,
            {"name": "Local-x", "source_type": "local", "repo_path": self.tmp},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Project.objects.filter(owner=self.alice).count(), 1)
        project = Project.objects.get(owner=self.alice)
        self.assertEqual(project.name, "Local-x")
        self.assertEqual(project.source_type, "local")
        self.assertEqual(project.repo_path, self.tmp)

    def test_create_local_with_nonexistent_path_rejects(self):
        response = self.client.post(
            self.url,
            {"name": "Ghost", "source_type": "local",
             "repo_path": "/definitely/not/a/real/dir"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("repo_path", response.json())

    def test_create_upload_with_non_zip_rejects(self):
        fake = SimpleUploadedFile(
            "src.zip", b"this is not a zip at all",
            content_type="application/zip",
        )
        response = self.client.post(self.url, {
            "name": "BadZip", "source_type": "upload", "source_archive": fake,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_archive", response.json())

    def test_create_local_without_path_rejects(self):
        response = self.client.post(
            self.url,
            {"name": "Bad", "source_type": "local"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("repo_path", response.json())

    def test_create_git_with_https_github_succeeds(self):
        response = self.client.post(
            self.url,
            {
                "name": "Git-x",
                "source_type": "git",
                "git_url": "https://github.com/o/r",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_create_git_with_off_allowlist_host_rejects(self):
        response = self.client.post(
            self.url,
            {
                "name": "Evil",
                "source_type": "git",
                "git_url": "https://evil.example.com/foo",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("git_url", response.json())

    def test_create_git_with_non_https_scheme_rejects(self):
        response = self.client.post(
            self.url,
            {
                "name": "FTP",
                "source_type": "git",
                "git_url": "ftp://github.com/o/r",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("git_url", response.json())

    def test_owner_is_set_from_request_not_payload(self):
        # Sneak a bogus owner into the payload; it must be ignored.
        # The serializer doesn't expose `owner` as a field, so this
        # is belt-and-braces: the field can't even be sent.
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="p")
        response = self.client.post(
            self.url,
            {
                "name": "Owned",
                "source_type": "local",
                "repo_path": self.tmp,
                "owner": bob.id,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        project = Project.objects.get(name="Owned")
        self.assertEqual(project.owner, self.alice)

    def test_create_clears_non_active_source_fields(self):
        # Client tries to send all source fields at once. Only the
        # ones relevant to the chosen source_type should persist.
        response = self.client.post(
            self.url,
            {
                "name": "Mixed",
                "source_type": "local",
                "repo_path": self.tmp,
                "git_url": "https://github.com/o/r",
                "git_branch": "main",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        project = Project.objects.get(name="Mixed")
        self.assertEqual(project.git_url, "")
        self.assertEqual(project.git_branch, "")


class ProjectUpdateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.client.force_login(self.alice)
        self.project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse("project-detail", kwargs={"pk": self.project.pk})

    def test_partial_update_changes_name(self):
        response = self.client.patch(
            self.url, {"name": "Renamed"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Renamed")

    def test_source_type_change_is_rejected(self):
        # The form-side immutability rule must also enforce on the API.
        response = self.client.patch(
            self.url,
            {"source_type": "git", "git_url": "https://github.com/o/r"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_type", response.json())
        self.project.refresh_from_db()
        self.assertEqual(self.project.source_type, "local")

    def test_alice_cannot_update_bobs_project(self):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="p")
        bobs_project = Project.objects.create(
            name="Bob", owner=bob, source_type="local", repo_path="/tmp/b",
        )
        url = reverse("project-detail", kwargs={"pk": bobs_project.pk})
        response = self.client.patch(
            url, {"name": "Hijacked"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        bobs_project.refresh_from_db()
        self.assertEqual(bobs_project.name, "Bob")


class ProjectDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.client.force_login(self.alice)
        self.project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )

    def test_alice_deletes_own_project(self):
        url = reverse("project-detail", kwargs={"pk": self.project.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_alice_cannot_delete_bobs_project(self):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="p")
        bobs_project = Project.objects.create(
            name="Bob", owner=bob, source_type="local", repo_path="/tmp/b",
        )
        url = reverse("project-detail", kwargs={"pk": bobs_project.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=bobs_project.pk).exists())


class ScanTriggerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.client.force_login(self.alice)
        self.project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse("scan-trigger")

    @patch("django_q.tasks.async_task")
    def test_single_tool_creates_scan_and_enqueues(self, mock_async):
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202, response.content)
        body = response.json()
        self.assertEqual(len(body["scans"]), 1)
        self.assertEqual(body["scans"][0]["tool"], "semgrep")
        self.assertEqual(body["skipped_tools"], [])
        self.assertEqual(
            Scan.objects.filter(project=self.project, tool="semgrep").count(), 1,
        )
        mock_async.assert_called_once()

    @patch("django_q.tasks.async_task")
    def test_both_creates_two_scans(self, mock_async):
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "both"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(len(body["scans"]), 2)
        self.assertEqual(Scan.objects.filter(project=self.project).count(), 2)
        self.assertEqual(mock_async.call_count, 2)

    @patch("django_q.tasks.async_task")
    def test_already_running_tool_is_skipped(self, mock_async):
        Scan.objects.create(
            project=self.project, tool="semgrep", status="RUNNING",
        )
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "both"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        body = response.json()
        # Only sonarqube was reserved; semgrep was already in flight.
        self.assertEqual(len(body["scans"]), 1)
        self.assertEqual(body["scans"][0]["tool"], "sonarqube")
        self.assertEqual(body["skipped_tools"], ["semgrep"])
        mock_async.assert_called_once()

    @patch("django_q.tasks.async_task")
    def test_cannot_trigger_scan_on_other_users_project(self, mock_async):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="p")
        bobs_project = Project.objects.create(
            name="Bob", owner=bob, source_type="local", repo_path="/tmp/b",
        )
        response = self.client.post(
            self.url,
            {"project_id": str(bobs_project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Scan.objects.filter(project=bobs_project).exists())
        mock_async.assert_not_called()

    def test_invalid_tool_value_rejected(self):
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "bandit"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_request_rejected(self):
        self.client.logout()
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.assertIn(response.status_code, (401, 403))

    @patch("django_q.tasks.async_task")
    def test_staff_scans_are_not_metered(self, mock_async):
        # Staff bypass the credit charge entirely, even at 0 balance.
        self.alice.is_staff = True
        self.alice.save()
        self.alice.profile.credits = 0
        self.alice.profile.save()

        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202, response.content)
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.credits, 0)
        mock_async.assert_called_once()
