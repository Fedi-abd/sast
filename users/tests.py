"""Smoke tests for the users app's auth flow.

These cover the behaviors that broke during Sprint 1 testing:
  - non-admin users couldn't reach the templated UI because there
    was no templated login page;
  - there was no way to create an account without
    `manage.py createsuperuser`.

URL note: the templated project list now lives at /debug/projects/
behind `if settings.DEBUG:` in config/urls.py. After login the user
lands on /app/ (Vue SPA), which placeholders to /debug/projects/
until Vue is built. The assertions below follow the placeholder
chain: 302 → /app/ → 302 → /debug/projects/.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthFlowTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")

    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create an account")

    def test_signup_creates_user_and_logs_in(self):
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="alice").exists())

        response = self.client.post(reverse("signup"), {
            "username": "alice",
            "password1": "verysafePassw0rd!",
            "password2": "verysafePassw0rd!",
        })

        # 302 -> /app/ (Vue SPA placeholder) on signup success.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/app/", response.url)
        self.assertTrue(User.objects.filter(username="alice").exists())

        # /app/ placeholders to /debug/projects/, which renders the
        # templated project list. follow=True chases the chain to a 200.
        followed = self.client.get(response.url, follow=True)
        self.assertEqual(followed.status_code, 200)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse("signup"), {
            "username": "bob",
            "password1": "verysafePassw0rd!",
            "password2": "different",
        })
        # Form re-renders with errors, status 200 (no redirect).
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_logged_out_user_redirected_from_projects_to_login(self):
        # The templated project list now lives at /debug/projects/
        # (debug-gated). When logged out, LoginRequiredMixin bounces
        # the request to /accounts/login/.
        response = self.client.get("/debug/projects/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_login_with_valid_credentials(self):
        User = get_user_model()
        User.objects.create_user(username="carol", password="verysafePassw0rd!")

        response = self.client.post(reverse("login"), {
            "username": "carol",
            "password": "verysafePassw0rd!",
        })
        # Successful login redirects to LOGIN_REDIRECT_URL = /app/,
        # the Vue SPA mount point.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/app/", response.url)

    def test_logout_via_post_redirects_to_login(self):
        User = get_user_model()
        User.objects.create_user(username="dave", password="verysafePassw0rd!")
        self.client.login(username="dave", password="verysafePassw0rd!")

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
