"""Project-detail view: scan-trigger button states.

Pins the fix for the prof-meeting bug: Run Both must disable when
either tool is running, not just when both are. The async/API rewrite
must honor the same contract.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from scans.models import Project, Scan


class RunBothButtonDisableTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            name="P", owner=self.user, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse("scans:project_detail", kwargs={"pk": self.project.pk})

    def _run_both_disabled(self, response):
        # The Run Both <button> carries `name="tool" value="both"`. The
        # disabled attribute precedes the value attribute in the rendered
        # template, so look for the literal `disabled` on that line.
        html = response.content.decode()
        marker = 'value="both"'
        idx = html.find(marker)
        self.assertNotEqual(idx, -1, "Run Both button not found in template")
        # Look back 200 chars for the disabled attr on the same tag.
        return "disabled" in html[max(0, idx - 200):idx + 200]

    def test_no_scans_running_run_both_enabled(self):
        response = self.client.get(self.url)
        self.assertFalse(self._run_both_disabled(response))

    def test_semgrep_running_disables_run_both(self):
        Scan.objects.create(project=self.project, tool="semgrep", status="RUNNING")
        response = self.client.get(self.url)
        self.assertTrue(self._run_both_disabled(response))

    def test_sonar_running_disables_run_both(self):
        Scan.objects.create(project=self.project, tool="sonarqube", status="RUNNING")
        response = self.client.get(self.url)
        self.assertTrue(self._run_both_disabled(response))

    def test_both_running_disables_run_both(self):
        Scan.objects.create(project=self.project, tool="semgrep", status="RUNNING")
        Scan.objects.create(project=self.project, tool="sonarqube", status="RUNNING")
        response = self.client.get(self.url)
        self.assertTrue(self._run_both_disabled(response))

    def test_finished_scans_dont_disable_run_both(self):
        Scan.objects.create(project=self.project, tool="semgrep", status="SUCCESS")
        Scan.objects.create(project=self.project, tool="sonarqube", status="FAILED")
        response = self.client.get(self.url)
        self.assertFalse(self._run_both_disabled(response))
