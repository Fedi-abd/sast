"""Tests for the credits feature.

Covers:
  - The post_save signal auto-creates a UserProfile.
  - `UserProfile.charge` decrements and raises correctly.
  - `cost_for_tool` returns the documented per-tool cost.
  - Scan-trigger paths (templated + API) charge credits and reject
    when insufficient.
  - `cost_for_tool` is bypassed at the view layer when a "Run Both"
    request resolves to a single new scan because the other tool is
    already running; only the actual reservation is billed.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from scans.models import Project, Scan
from users.models import InsufficientCreditsError, UserProfile


class UserProfileModelTests(TestCase):
    def test_signal_creates_profile_on_new_user(self):
        User = get_user_model()
        user = User.objects.create_user(username="brand-new", password="p")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.credits, UserProfile.DEFAULT_CREDITS)

    def test_charge_decrements_credits(self):
        User = get_user_model()
        user = User.objects.create_user(username="u", password="p")
        with transaction.atomic():
            remaining = UserProfile.charge(user, cost=5)
        self.assertEqual(remaining, UserProfile.DEFAULT_CREDITS - 5)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, UserProfile.DEFAULT_CREDITS - 5)

    def test_charge_with_zero_cost_is_noop(self):
        User = get_user_model()
        user = User.objects.create_user(username="u", password="p")
        with transaction.atomic():
            remaining = UserProfile.charge(user, cost=0)
        self.assertEqual(remaining, UserProfile.DEFAULT_CREDITS)

    def test_charge_raises_when_insufficient(self):
        User = get_user_model()
        user = User.objects.create_user(username="u", password="p")
        user.profile.credits = 1
        user.profile.save()
        with self.assertRaises(InsufficientCreditsError) as cm:
            with transaction.atomic():
                UserProfile.charge(user, cost=5)
        self.assertEqual(cm.exception.cost, 5)
        self.assertEqual(cm.exception.remaining, 1)
        # The balance must not have been touched on a failed charge.
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, 1)

    def test_cost_for_tool(self):
        self.assertEqual(UserProfile.cost_for_tool("semgrep"), 1)
        self.assertEqual(UserProfile.cost_for_tool("sonarqube"), 1)
        self.assertEqual(UserProfile.cost_for_tool("both"), 2)

    def test_refund_adds_credits(self):
        User = get_user_model()
        user = User.objects.create_user(username="r", password="p")
        user.profile.credits = 10
        user.profile.save()
        self.assertEqual(UserProfile.refund(user, amount=1), 11)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, 11)

    def test_refund_skips_staff(self):
        User = get_user_model()
        staff = User.objects.create_user(username="s", password="p", is_staff=True)
        staff.profile.credits = 10
        staff.profile.save()
        self.assertEqual(UserProfile.refund(staff, amount=1), 10)
        staff.profile.refresh_from_db()
        self.assertEqual(staff.profile.credits, 10)

    def test_refund_nonpositive_is_noop(self):
        User = get_user_model()
        user = User.objects.create_user(username="z", password="p")
        before = user.profile.credits
        self.assertEqual(UserProfile.refund(user, amount=0), before)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, before)

    def test_charge_unlimited_when_credits_negative(self):
        # -1 is the admin-set "unlimited" sentinel: never charged, never raises.
        User = get_user_model()
        user = User.objects.create_user(username="inf", password="p")
        user.profile.credits = -1
        user.profile.save()
        with transaction.atomic():
            remaining = UserProfile.charge(user, cost=5)
        self.assertEqual(remaining, -1)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, -1)

    def test_refund_skips_unlimited(self):
        User = get_user_model()
        user = User.objects.create_user(username="inf2", password="p")
        user.profile.credits = -1
        user.profile.save()
        self.assertEqual(UserProfile.refund(user, amount=1), -1)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.credits, -1)


class ApiScanTriggerCreditsTests(TestCase):
    """Credits behavior on POST /api/scans/trigger/."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            name="P", owner=self.user, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse("scan-trigger")

    @patch("django_q.tasks.async_task")
    def test_single_scan_decrements_one_credit(self, mock_async):
        self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS - 1)

    @patch("django_q.tasks.async_task")
    def test_both_decrements_two_credits_when_both_start(self, mock_async):
        self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "both"},
            content_type="application/json",
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS - 2)

    @patch("django_q.tasks.async_task")
    def test_both_charges_one_when_other_tool_already_running(self, mock_async):
        # "both" requested, semgrep already running → only sonarqube is
        # newly reserved → 1 credit, not 2.
        Scan.objects.create(
            project=self.project, tool="semgrep", status="RUNNING",
        )
        self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "both"},
            content_type="application/json",
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS - 1)

    @patch("django_q.tasks.async_task")
    def test_unlimited_user_is_never_charged(self, mock_async):
        self.user.profile.credits = -1
        self.user.profile.save()
        self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "both"},
            content_type="application/json",
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, -1)

    @patch("django_q.tasks.async_task")
    def test_insufficient_credits_returns_402(self, mock_async):
        self.user.profile.credits = 0
        self.user.profile.save()
        response = self.client.post(
            self.url,
            {"project_id": str(self.project.pk), "tool": "semgrep"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 402)
        body = response.json()
        self.assertEqual(body["cost"], 1)
        self.assertEqual(body["remaining"], 0)
        self.assertIn("Insufficient credits", body["detail"])
        # Critically: no scan row was created when credits failed.
        self.assertEqual(Scan.objects.filter(project=self.project).count(), 0)
        mock_async.assert_not_called()


class TemplatedTriggerScanCreditsTests(TestCase):
    """Credits behavior on the templated POST /debug/.../scan/."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            name="P", owner=self.user, source_type="local", repo_path="/tmp/x",
        )
        self.url = reverse(
            "scans:trigger_scan", kwargs={"project_id": self.project.pk},
        )

    @patch("django_q.tasks.async_task")
    def test_templated_trigger_decrements_credits(self, mock_async):
        self.client.post(self.url, {"tool": "semgrep"})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS - 1)

    @patch("django_q.tasks.async_task")
    def test_templated_insufficient_credits_redirects_without_creating_scan(self, mock_async):
        self.user.profile.credits = 0
        self.user.profile.save()
        response = self.client.post(self.url, {"tool": "semgrep"})
        self.assertEqual(response.status_code, 302)  # back to project detail
        self.assertEqual(Scan.objects.filter(project=self.project).count(), 0)
        mock_async.assert_not_called()


class RefundOnFailedScanTests(TestCase):
    """A scan that fails returns the credit it was charged at trigger."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.project = Project.objects.create(
            name="P", owner=self.user, source_type="local", repo_path="/tmp/x",
        )

    @patch("scans.services.scan_service.PathResolver.resolve", side_effect=ValueError("boom"))
    def test_failed_scan_refunds_the_credit(self, _mock):
        from scans.services.scan_service import ScanService
        with transaction.atomic():
            UserProfile.charge(self.user, cost=1)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS - 1)

        scan = Scan.objects.create(project=self.project, tool="semgrep", status="RUNNING")
        result = ScanService().execute(scan)

        self.assertFalse(result["success"])
        scan.refresh_from_db()
        self.assertEqual(scan.status, "FAILED")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, UserProfile.DEFAULT_CREDITS)

    @patch("scans.services.scan_service.PathResolver.resolve", side_effect=ValueError("boom"))
    def test_failed_staff_scan_leaves_credits_untouched(self, _mock):
        from scans.services.scan_service import ScanService
        self.user.is_staff = True
        self.user.save()
        before = self.user.profile.credits
        scan = Scan.objects.create(project=self.project, tool="semgrep", status="RUNNING")
        ScanService().execute(scan)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.credits, before)


class MeIncludesCreditsTests(TestCase):
    def test_me_endpoint_includes_credits(self):
        User = get_user_model()
        user = User.objects.create_user(username="u", password="p")
        user.profile.credits = 42
        user.profile.save()
        self.client.force_login(user)
        body = self.client.get(reverse("me")).json()
        self.assertEqual(body["credits"], 42)
