"""DRF read-only endpoint tests.

Trust-boundary coverage: every endpoint must (1) reject unauthenticated
requests and (2) refuse cross-user access. Shape coverage is light,
just enough to catch a serializer field that disappears.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from scans.models import Finding, Project, Scan


class ApiAuthTests(TestCase):
    def test_projects_list_requires_auth(self):
        response = self.client.get(reverse("project-list"))
        self.assertIn(response.status_code, (401, 403))

    def test_scans_list_requires_auth(self):
        response = self.client.get(reverse("scan-list"))
        self.assertIn(response.status_code, (401, 403))

    def test_me_requires_auth(self):
        response = self.client.get(reverse("me"))
        self.assertIn(response.status_code, (401, 403))


class MeEndpointTests(TestCase):
    def test_me_returns_current_user_identity(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="carol", password="p", email="c@example.com",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "carol")
        self.assertEqual(body["email"], "c@example.com")
        self.assertFalse(body["is_staff"])

    def test_me_marks_staff_users(self):
        User = get_user_model()
        admin = User.objects.create_user(username="admin", password="p", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_staff"])

    def test_me_does_not_leak_password_or_other_users(self):
        User = get_user_model()
        alice = User.objects.create_user(username="alice", password="p")
        User.objects.create_user(username="bob", password="p")
        self.client.force_login(alice)
        body = self.client.get(reverse("me")).json()
        # No password fields ever in the response, and only Alice
        # appears. Not a list of all users.
        self.assertNotIn("password", body)
        self.assertEqual(body["username"], "alice")


class ApiScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.bob = User.objects.create_user(username="bob", password="p")

        self.alice_project = Project.objects.create(
            name="Alice", owner=self.alice, source_type="local", repo_path="/tmp/a",
        )
        self.bob_project = Project.objects.create(
            name="Bob", owner=self.bob, source_type="local", repo_path="/tmp/b",
        )
        self.alice_scan = Scan.objects.create(
            project=self.alice_project, tool="semgrep", status="SUCCESS",
        )
        Finding.objects.create(
            scan=self.alice_scan, tool="semgrep", rule_id="r",
            severity="HIGH", file_path="x.py", line_number=1,
            message="m", raw={},
        )

    def test_alice_sees_only_own_projects(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("project-list"))
        self.assertEqual(response.status_code, 200)
        names = {p["name"] for p in response.json()}
        self.assertEqual(names, {"Alice"})

    def test_alice_cannot_retrieve_bob_project(self):
        self.client.force_login(self.alice)
        url = reverse("project-detail", kwargs={"pk": self.bob_project.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_alice_cannot_retrieve_bob_scan(self):
        self.client.force_login(self.alice)
        bob_scan = Scan.objects.create(
            project=self.bob_project, tool="semgrep", status="SUCCESS",
        )
        url = reverse("scan-detail", kwargs={"pk": bob_scan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_scan_detail_shape(self):
        self.client.force_login(self.alice)
        url = reverse("scan-detail", kwargs={"pk": self.alice_scan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for field in (
            "id", "tool", "tool_display", "status", "status_display",
            "started_at", "finished_at", "duration_seconds",
            "finding_count", "project_id", "project_name",
        ):
            self.assertIn(field, body)
        self.assertEqual(body["finding_count"], 1)

    def test_findings_action_returns_only_scan_findings(self):
        self.client.force_login(self.alice)
        url = reverse("scan-findings", kwargs={"pk": self.alice_scan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        findings = response.json()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "HIGH")

    def test_findings_action_blocked_for_other_users_scan(self):
        bob_scan = Scan.objects.create(
            project=self.bob_project, tool="semgrep", status="SUCCESS",
        )
        self.client.force_login(self.alice)
        url = reverse("scan-findings", kwargs={"pk": bob_scan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
