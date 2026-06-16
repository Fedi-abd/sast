"""Tests for GET /api/health/: the dashboard's engine-status source.

The Sonar ping is mocked (no network in tests) and the module-level
cache is reset per test so verdicts don't leak between cases.
"""
import time
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from scans.api import views as api_views


@override_settings(
    SEMGREP_PATH="C:/fake/semgrep",
    SONAR_HOST="http://env-sonar:9000",
    SONAR_TOKEN=None,
)
class HealthTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="health", password="p")
        self.client.force_login(self.user)
        api_views._HEALTH_CACHE.update({"at": 0.0, "sonarqube": None})

    def test_reports_both_engines(self):
        fake = mock.Mock(status_code=200)
        with mock.patch("scans.api.views.requests.get", return_value=fake), \
             mock.patch(
                 "scans.api.views.shutil.which", return_value="C:/fake/semgrep",
             ):
            body = self.client.get(reverse("health")).json()
        self.assertTrue(body["semgrep"])
        self.assertTrue(body["sonarqube"])

    def test_fresh_param_busts_the_cache_after_grace(self):
        # Cached "down" verdict, older than the 5s floor but well inside
        # the regular 60s window. Only fresh=1 re-pings.
        api_views._HEALTH_CACHE.update(
            {"at": time.monotonic() - 10, "sonarqube": False},
        )
        fake = mock.Mock(status_code=200)
        with mock.patch("scans.api.views.requests.get", return_value=fake), \
             mock.patch("scans.api.views.shutil.which", return_value="x"):
            cached = self.client.get(reverse("health")).json()
            self.assertFalse(cached["sonarqube"])
            freshed = self.client.get(reverse("health") + "?fresh=1").json()
        self.assertTrue(freshed["sonarqube"])

    def test_stale_semgrep_path_reports_false(self):
        # A configured-but-nonexistent SEMGREP_PATH must not light the
        # pill green; which() validates the path, not just its presence.
        fake = mock.Mock(status_code=200)
        with mock.patch("scans.api.views.requests.get", return_value=fake), \
             mock.patch("scans.api.views.shutil.which", return_value=None):
            body = self.client.get(reverse("health")).json()
        self.assertFalse(body["semgrep"])

    def test_sonar_down_is_a_verdict_not_an_error(self):
        with mock.patch(
            "scans.api.views.requests.get",
            side_effect=requests.ConnectionError("refused"),
        ):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["sonarqube"])

    def test_sonar_ping_is_cached_across_requests(self):
        fake = mock.Mock(status_code=200)
        with mock.patch(
            "scans.api.views.requests.get", return_value=fake,
        ) as mocked:
            self.client.get(reverse("health"))
            self.client.get(reverse("health"))
        self.assertEqual(mocked.call_count, 1)

    def test_anonymous_rejected(self):
        self.client.logout()
        response = self.client.get(reverse("health"))
        self.assertIn(response.status_code, (401, 403))
