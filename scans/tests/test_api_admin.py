"""Tests for the staff-only /api/admin/* endpoints and /api/config/.

Coverage:
  - Gating: every admin endpoint 403s for non-staff and rejects
    anonymous users.
  - SonarQube config: env-fallback merge, token masking (last4 only),
    PUT keeps the stored token when omitted, test-connection verdicts.
  - Limits: roster GET, bulk PATCH (all-or-nothing on bad rows).
  - Usage: cross-user rows, limit param.
  - Users: is_active toggle, self-deactivation refused, password
    reset returns a working temp password.
  - Platform settings: hide_local_source round-trip, show_debug_ui
    rejected on PATCH (env-managed).
  - Enforcement on the API project-create path: max_projects quota,
    per-user upload cap, hide_local_source flag.
  - /api/config/: per-user effective values for non-staff clients.
"""
import io
import tempfile
import zipfile
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from scans.models import PlatformSettings, Project, Scan, SonarSettings
from users.models import PasswordResetRequest


def _tiny_zip(name="src.zip"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", "print('hi')\n")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="application/zip")


class AdminApiBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="boss", password="p", is_staff=True,
        )
        self.pleb = User.objects.create_user(username="pleb", password="p")
        self.client.force_login(self.staff)


class AdminGatingTests(AdminApiBase):
    URLS = [
        "admin-sonarqube", "admin-limits", "admin-usage",
        "admin-users", "admin-settings",
    ]

    def test_non_staff_rejected_everywhere(self):
        self.client.force_login(self.pleb)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 403, msg=name)

    def test_anonymous_rejected(self):
        self.client.logout()
        response = self.client.get(reverse("admin-sonarqube"))
        self.assertIn(response.status_code, (401, 403))


@override_settings(
    SONAR_HOST="http://env-sonar:9000",
    SONAR_TOKEN=None,
    SAST_SONAR_ISSUE_TYPES="VULNERABILITY",
)
class AdminSonarConfigTests(AdminApiBase):
    def test_get_falls_back_to_env(self):
        body = self.client.get(reverse("admin-sonarqube")).json()
        self.assertEqual(body["host"], "http://env-sonar:9000")
        self.assertFalse(body["has_token"])
        self.assertEqual(body["token_last4"], "")
        self.assertEqual(body["issue_types"], ["VULNERABILITY"])

    def test_put_updates_and_masks_token(self):
        response = self.client.put(
            reverse("admin-sonarqube"),
            {"host": "http://sonar.example:9000", "token": "squ_secret9999",
             "issue_types": ["VULNERABILITY", "BUG"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["host"], "http://sonar.example:9000")
        self.assertTrue(body["has_token"])
        self.assertEqual(body["token_last4"], "9999")
        self.assertNotIn("squ_secret9999", str(body))
        self.assertEqual(body["issue_types"], ["VULNERABILITY", "BUG"])
        self.assertEqual(body["updated_by"], "boss")

    def test_put_without_token_keeps_stored_one(self):
        row = SonarSettings.get_solo()
        row.token = "squ_keepme1234"
        row.save()
        body = self.client.put(
            reverse("admin-sonarqube"),
            {"host": "http://other.example:9000"},
            content_type="application/json",
        ).json()
        self.assertTrue(body["has_token"])
        self.assertEqual(body["token_last4"], "1234")
        self.assertEqual(SonarSettings.get_solo().token, "squ_keepme1234")

    def test_put_rejects_unknown_issue_type(self):
        response = self.client.put(
            reverse("admin-sonarqube"),
            {"issue_types": ["SECURITY_HOTSPOT"]},
            content_type="application/json",
        )
        # Hotspots always come via their own API; not a valid filter.
        self.assertEqual(response.status_code, 400)

    def test_get_defaults_hotspots_shown(self):
        body = self.client.get(reverse("admin-sonarqube")).json()
        self.assertTrue(body["include_hotspots"])

    def test_put_can_hide_hotspots(self):
        body = self.client.put(
            reverse("admin-sonarqube"),
            {"include_hotspots": False},
            content_type="application/json",
        ).json()
        self.assertFalse(body["include_hotspots"])
        self.assertFalse(SonarSettings.get_solo().include_hotspots)

    def test_connection_ok_validates_the_token(self):
        row = SonarSettings.get_solo()
        row.token = "squ_real1234"
        row.save()
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {"valid": True}
        with mock.patch(
            "scans.api.admin_views.requests.get", return_value=fake,
        ) as mocked:
            body = self.client.post(
                reverse("admin-sonarqube-test"), {}, content_type="application/json",
            ).json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["server"])
        self.assertTrue(body["token"])
        self.assertIn("token valid", body["detail"])
        # The validate endpoint (not status, which answers without auth).
        self.assertIn("/api/authentication/validate", mocked.call_args[0][0])

    def test_connection_with_invalid_token_is_not_ok(self):
        row = SonarSettings.get_solo()
        row.token = "squ_mashed"
        row.save()
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {"valid": False}
        with mock.patch("scans.api.admin_views.requests.get", return_value=fake):
            body = self.client.post(
                reverse("admin-sonarqube-test"), {}, content_type="application/json",
            ).json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["server"])
        self.assertFalse(body["token"])
        self.assertIn("INVALID", body["detail"])

    def test_connection_tests_typed_values_before_save(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {"valid": True}
        with mock.patch(
            "scans.api.admin_views.requests.get", return_value=fake,
        ) as mocked:
            body = self.client.post(
                reverse("admin-sonarqube-test"),
                {"host": "http://typed.example:9000", "token": "squ_typed"},
                content_type="application/json",
            ).json()
        self.assertTrue(body["ok"])
        called_url = mocked.call_args[0][0]
        self.assertTrue(called_url.startswith("http://typed.example:9000"))

    def test_connection_without_any_token_is_not_ok(self):
        fake = mock.Mock(status_code=200)
        with mock.patch("scans.api.admin_views.requests.get", return_value=fake):
            body = self.client.post(
                reverse("admin-sonarqube-test"), {}, content_type="application/json",
            ).json()
        self.assertFalse(body["ok"])
        self.assertIn("no token", body["detail"])

    def test_connection_failure_is_a_verdict_not_an_error(self):
        with mock.patch(
            "scans.api.admin_views.requests.get",
            side_effect=requests.ConnectionError("refused"),
        ):
            response = self.client.post(
                reverse("admin-sonarqube-test"), {}, content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertFalse(body["server"])
        self.assertIsNone(body["token"])


class AdminLimitsTests(AdminApiBase):
    def test_get_lists_all_users_with_profile_values(self):
        self.pleb.profile.credits = 7
        self.pleb.profile.save()
        body = self.client.get(reverse("admin-limits")).json()
        by_name = {row["username"]: row for row in body}
        self.assertIn("boss", by_name)
        self.assertEqual(by_name["pleb"]["credits"], 7)
        self.assertEqual(by_name["pleb"]["max_projects"], 25)
        self.assertEqual(by_name["pleb"]["max_upload_mb"], 250)

    def test_bulk_patch_updates_rows(self):
        response = self.client.patch(
            reverse("admin-limits"),
            {"users": [{"user_id": self.pleb.id, "credits": 3, "max_projects": 1}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.pleb.profile.refresh_from_db()
        self.assertEqual(self.pleb.profile.credits, 3)
        self.assertEqual(self.pleb.profile.max_projects, 1)
        # Untouched field unchanged.
        self.assertEqual(self.pleb.profile.max_upload_mb, 250)

    def test_negative_below_minus_one_rejected(self):
        # -1 is the "unlimited" sentinel; anything more negative is invalid.
        response = self.client.patch(
            reverse("admin-limits"),
            {"users": [{"user_id": self.pleb.id, "credits": -5}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_minus_one_sets_unlimited(self):
        response = self.client.patch(
            reverse("admin-limits"),
            {"users": [{"user_id": self.pleb.id, "credits": -1, "max_projects": -1}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.pleb.profile.refresh_from_db()
        self.assertEqual(self.pleb.profile.credits, -1)
        self.assertEqual(self.pleb.profile.max_projects, -1)

    def test_unknown_user_rolls_back_whole_batch(self):
        response = self.client.patch(
            reverse("admin-limits"),
            {"users": [
                {"user_id": self.pleb.id, "credits": 3},
                {"user_id": 99999, "credits": 1},
            ]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.pleb.profile.refresh_from_db()
        self.assertEqual(self.pleb.profile.credits, 100)


class AdminUsageTests(AdminApiBase):
    def setUp(self):
        super().setUp()
        boss_project = Project.objects.create(
            name="BossApp", owner=self.staff, source_type="local", repo_path="/tmp/a",
        )
        pleb_project = Project.objects.create(
            name="PlebApp", owner=self.pleb, source_type="local", repo_path="/tmp/b",
        )
        Scan.objects.create(project=boss_project, tool="semgrep", status="SUCCESS")
        Scan.objects.create(project=pleb_project, tool="semgrep", status="FAILED")

    def test_usage_spans_all_users(self):
        body = self.client.get(reverse("admin-usage")).json()
        usernames = {row["username"] for row in body}
        self.assertEqual(usernames, {"boss", "pleb"})

    def test_limit_param(self):
        body = self.client.get(reverse("admin-usage") + "?limit=1").json()
        self.assertEqual(len(body), 1)
        response = self.client.get(reverse("admin-usage") + "?limit=abc")
        self.assertEqual(response.status_code, 400)


class AdminUsersTests(AdminApiBase):
    def test_roster_shape(self):
        body = self.client.get(reverse("admin-users")).json()
        row = next(r for r in body if r["username"] == "pleb")
        self.assertEqual(
            set(row), {"id", "username", "email", "is_staff", "is_active"},
        )

    def test_deactivate_and_reactivate_other_user(self):
        url = reverse("admin-user-detail", args=[self.pleb.id])
        body = self.client.patch(
            url, {"is_active": False}, content_type="application/json",
        ).json()
        self.assertFalse(body["is_active"])
        self.pleb.refresh_from_db()
        self.assertFalse(self.pleb.is_active)
        self.client.patch(url, {"is_active": True}, content_type="application/json")
        self.pleb.refresh_from_db()
        self.assertTrue(self.pleb.is_active)

    def test_cannot_deactivate_self(self):
        response = self.client.patch(
            reverse("admin-user-detail", args=[self.staff.id]),
            {"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_non_boolean_is_active_rejected(self):
        response = self.client.patch(
            reverse("admin-user-detail", args=[self.pleb.id]),
            {"is_active": "nope"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_password_returns_working_temp(self):
        body = self.client.post(
            reverse("admin-user-reset-password", args=[self.pleb.id])
        ).json()
        temp = body["temp_password"]
        self.assertEqual(len(temp), 16)
        self.client.logout()
        self.assertTrue(self.client.login(username="pleb", password=temp))


@override_settings(SAST_DEBUG_UI=True)
class AdminPlatformSettingsTests(AdminApiBase):
    def test_get_defaults(self):
        body = self.client.get(reverse("admin-settings")).json()
        # Local paths are hidden by default; admins opt in for dev.
        self.assertTrue(body["hide_local_source"])
        self.assertTrue(body["show_debug_ui"])

    def test_patch_hide_local_source(self):
        # Default is True, so the meaningful round-trip is turning it OFF.
        body = self.client.patch(
            reverse("admin-settings"),
            {"hide_local_source": False},
            content_type="application/json",
        ).json()
        self.assertFalse(body["hide_local_source"])
        self.assertFalse(PlatformSettings.get_solo().hide_local_source)

    def test_patch_show_debug_ui_rejected(self):
        response = self.client.patch(
            reverse("admin-settings"),
            {"show_debug_ui": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class LimitEnforcementTests(TestCase):
    """The quotas the console edits must actually bite on project create."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="quota", password="p")
        self.client.force_login(self.user)
        self.url = reverse("project-list")
        # These tests create local projects; the flag is now on by
        # default, so allow local explicitly.
        row = PlatformSettings.get_solo()
        row.hide_local_source = False
        row.save()

    def test_max_projects_enforced(self):
        self.user.profile.max_projects = 1
        self.user.profile.save()
        first = self.client.post(self.url, {
            "name": "one", "source_type": "local",
            "repo_path": tempfile.mkdtemp(),
        }, content_type="application/json")
        self.assertEqual(first.status_code, 201, first.content)
        second = self.client.post(self.url, {
            "name": "two", "source_type": "local",
            "repo_path": tempfile.mkdtemp(),
        }, content_type="application/json")
        self.assertEqual(second.status_code, 400)
        self.assertIn("limit", str(second.json()).lower())

    def test_upload_cap_enforced(self):
        self.user.profile.max_upload_mb = 0
        self.user.profile.save()
        response = self.client.post(self.url, {
            "name": "zipped", "source_type": "upload",
            "source_archive": _tiny_zip(),
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_archive", response.json())

    def test_hide_local_source_blocks_new_local_projects(self):
        row = PlatformSettings.get_solo()
        row.hide_local_source = True
        row.save()
        response = self.client.post(self.url, {
            "name": "nope", "source_type": "local", "repo_path": "/tmp/x",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_type", response.json())
        # Other source types stay available.
        ok = self.client.post(self.url, {
            "name": "still-fine", "source_type": "git",
            "git_url": "https://github.com/org/repo",
        }, content_type="application/json")
        self.assertEqual(ok.status_code, 201)


class ConfigEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="reader", password="p")
        self.client.force_login(self.user)

    def test_config_shape_and_effective_cap(self):
        body = self.client.get(reverse("config")).json()
        self.assertEqual(
            set(body), {"hide_local_source", "max_upload_mb", "max_projects"},
        )
        self.assertTrue(body["hide_local_source"])

    def test_user_cap_wins_when_lower_than_global(self):
        self.user.profile.max_upload_mb = 10
        self.user.profile.save()
        body = self.client.get(reverse("config")).json()
        self.assertEqual(body["max_upload_mb"], 10)

    def test_unlimited_cap_falls_back_to_global(self):
        from django.conf import settings as dj
        self.user.profile.max_upload_mb = -1
        self.user.profile.max_projects = -1
        self.user.profile.save()
        body = self.client.get(reverse("config")).json()
        self.assertEqual(body["max_upload_mb"], dj.SAST_MAX_UPLOAD_SIZE_MB)
        self.assertEqual(body["max_projects"], -1)

    def test_anonymous_rejected(self):
        self.client.logout()
        response = self.client.get(reverse("config"))
        self.assertIn(response.status_code, (401, 403))


class AdminResetRequestsTests(AdminApiBase):
    def setUp(self):
        super().setUp()
        self.pending = PasswordResetRequest.objects.create(identifier="alice")
        PasswordResetRequest.objects.create(identifier="bob", handled=True)

    def test_lists_pending_first(self):
        body = self.client.get(reverse("admin-reset-requests")).json()
        self.assertEqual(len(body), 2)
        self.assertFalse(body[0]["handled"])

    def test_mark_handled(self):
        url = reverse("admin-reset-request-detail", kwargs={"request_id": self.pending.id})
        body = self.client.patch(
            url, {"handled": True}, content_type="application/json",
        ).json()
        self.assertTrue(body["handled"])
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.handled)

    def test_non_staff_forbidden(self):
        self.client.force_login(self.pleb)
        self.assertEqual(
            self.client.get(reverse("admin-reset-requests")).status_code, 403,
        )
