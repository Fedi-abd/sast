"""trigger_scan now enqueues via django-q2 instead of running inline.

These tests patch out `async_task` so the queue path is verified
without actually firing the scanner. Sync-mode execution is exercised
indirectly elsewhere — here we just want to confirm:

  - a RUNNING Scan row is reserved,
  - the task is enqueued with the right args,
  - the response redirects to project_detail (not scan_detail),
  - the existing lock still prevents double-queueing.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from scans.models import Project, Scan


class TriggerScanAsyncTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="async-user", password="p")
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            name="P", owner=self.user, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse(
            "scans:trigger_scan", kwargs={"project_id": self.project.pk}
        )

    @patch("django_q.tasks.async_task")
    def test_single_tool_enqueues_and_redirects(self, mock_async):
        response = self.client.post(self.url, {"tool": "semgrep"})
        self.assertRedirects(
            response,
            reverse("scans:project_detail", kwargs={"pk": self.project.pk}),
        )
        scan = Scan.objects.get(project=self.project, tool="semgrep")
        self.assertEqual(scan.status, "RUNNING")
        mock_async.assert_called_once()
        args, _ = mock_async.call_args
        self.assertEqual(args[0], "scans.tasks.run_scan")
        self.assertEqual(args[1], str(scan.id))

    @patch("django_q.tasks.async_task")
    def test_both_enqueues_two_tasks(self, mock_async):
        response = self.client.post(self.url, {"tool": "both"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Scan.objects.filter(project=self.project).count(), 2)
        self.assertEqual(mock_async.call_count, 2)

    @patch("django_q.tasks.async_task")
    def test_lock_blocks_duplicate_queue(self, mock_async):
        Scan.objects.create(
            project=self.project, tool="semgrep", status="RUNNING",
        )
        self.client.post(self.url, {"tool": "semgrep"})
        # Still just the one row — second click is a no-op.
        self.assertEqual(
            Scan.objects.filter(project=self.project, tool="semgrep").count(), 1,
        )
        mock_async.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_both_skips_running_tool(self, mock_async):
        Scan.objects.create(
            project=self.project, tool="semgrep", status="RUNNING",
        )
        self.client.post(self.url, {"tool": "both"})
        # Only sonarqube gets a new row + task; semgrep already running.
        self.assertEqual(
            Scan.objects.filter(project=self.project, tool="semgrep").count(), 1,
        )
        self.assertEqual(
            Scan.objects.filter(project=self.project, tool="sonarqube").count(), 1,
        )
        mock_async.assert_called_once()
        args, _ = mock_async.call_args
        sonar_scan = Scan.objects.get(project=self.project, tool="sonarqube")
        self.assertEqual(args[1], str(sonar_scan.id))
