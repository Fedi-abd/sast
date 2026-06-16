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
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import PasswordResetRequest


def _rule_ok(rules, needle):
    """Pass/fail of the rule whose help text contains `needle`."""
    for r in rules:
        if needle in r["label"]:
            return r["ok"]
    raise AssertionError(f"no rule label contains {needle!r}: {rules!r}")


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
            "email": "alice@example.com",
            "password1": "verysafePassw0rd!",
            "password2": "verysafePassw0rd!",
        })

        # 302 -> /app/ (Vue SPA placeholder) on signup success.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/app/", response.url)
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertEqual(
            User.objects.get(username="alice").email, "alice@example.com",
        )

        # /app/ placeholders to /debug/projects/, which renders the
        # templated project list. follow=True chases the chain to a 200.
        followed = self.client.get(response.url, follow=True)
        self.assertEqual(followed.status_code, 200)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse("signup"), {
            "username": "bob",
            "email": "bob@example.com",
            "password1": "verysafePassw0rd!",
            "password2": "different",
        })
        # Form re-renders with errors, status 200 (no redirect).
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_signup_requires_email(self):
        response = self.client.post(reverse("signup"), {
            "username": "noemail",
            "password1": "verysafePassw0rd!",
            "password2": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="noemail").exists())

    def test_inactive_login_explains_instead_of_wrong_password(self):
        # Needs AllowAllUsersModelBackend: the default backend rejects
        # inactive users inside authenticate(), which renders as
        # "wrong credentials", exactly the confusion being fixed.
        User = get_user_model()
        user = User.objects.create_user(
            username="benched", password="verysafePassw0rd!",
        )
        user.is_active = False
        user.save()

        response = self.client.post(reverse("login"), {
            "username": "benched",
            "password": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "disabled")
        self.assertNotContains(response, "correct username and password")

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


class EmailLoginTests(TestCase):
    """Username-or-email sign-in via users.backends.EmailOrUsernameBackend."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="erin", email="erin@example.com", password="verysafePassw0rd!",
        )

    def test_login_with_email(self):
        response = self.client.post(reverse("login"), {
            "username": "Erin@Example.com",   # case-insensitive match
            "password": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/app/", response.url)

    def test_login_with_email_wrong_password(self):
        response = self.client.post(reverse("login"), {
            "username": "erin@example.com",
            "password": "wrong",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "correct username and password")

    def test_username_login_still_works(self):
        response = self.client.post(reverse("login"), {
            "username": "erin",
            "password": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 302)

    def test_ambiguous_email_falls_back_to_username_only(self):
        # Two accounts sharing an address (legacy data); the backend
        # must refuse to guess between them.
        get_user_model().objects.create_user(
            username="erin2", email="ERIN@example.com", password="otherPassw0rd!",
        )
        response = self.client.post(reverse("login"), {
            "username": "erin@example.com",
            "password": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "correct username and password")

    def test_inactive_user_email_login_gets_disabled_message(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse("login"), {
            "username": "erin@example.com",
            "password": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "disabled")


class UniqueEmailSignupTests(TestCase):
    """Signup refuses an email already on another account."""

    def test_duplicate_email_rejected_case_insensitive(self):
        get_user_model().objects.create_user(
            username="frank", email="frank@example.com", password="verysafePassw0rd!",
        )
        response = self.client.post(reverse("signup"), {
            "username": "frank2",
            "email": "FRANK@example.com",
            "password1": "verysafePassw0rd!",
            "password2": "verysafePassw0rd!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already uses this email")
        self.assertFalse(
            get_user_model().objects.filter(username="frank2").exists()
        )


class PasswordResetRequestViewTests(TestCase):
    def setUp(self):
        self.url = reverse("password-forgot")

    def test_get_renders_the_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="identifier"')

    def test_post_records_a_request(self):
        self.assertFalse(PasswordResetRequest.objects.exists())
        response = self.client.post(self.url, {"identifier": "alice@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PasswordResetRequest.objects.count(), 1)
        req = PasswordResetRequest.objects.first()
        self.assertEqual(req.identifier, "alice@example.com")
        self.assertFalse(req.handled)

    def test_does_not_reveal_whether_the_account_exists(self):
        # A known and an unknown identifier both record a request and
        # return the same 200, so it can't be used to probe for users.
        get_user_model().objects.create_user(username="real", password="verysafePassw0rd!")
        known = self.client.post(self.url, {"identifier": "real"})
        unknown = self.client.post(self.url, {"identifier": "ghost"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(PasswordResetRequest.objects.count(), 2)

    def test_other_methods_rejected(self):
        self.assertEqual(self.client.delete(self.url).status_code, 405)


class PasswordRequirementsTests(TestCase):
    """Live per-rule validation behind the signup/change-password checklist."""

    def setUp(self):
        self.url = reverse("password-requirements")

    def _post(self, **data):
        return self.client.post(self.url, data).json()

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_one_entry_per_validator(self):
        rules = self._post(password="x")["rules"]
        self.assertEqual(len(rules), len(settings.AUTH_PASSWORD_VALIDATORS))

    def test_strong_password_passes_all(self):
        data = self._post(password="verysafePassw0rd!")
        self.assertTrue(data["all_ok"])
        self.assertTrue(all(r["ok"] for r in data["rules"]))

    def test_short_and_numeric_password_fails(self):
        data = self._post(password="1234567")
        self.assertFalse(data["all_ok"])
        self.assertFalse(_rule_ok(data["rules"], "at least 8"))
        self.assertFalse(_rule_ok(data["rules"], "entirely numeric"))

    def test_common_password_flagged(self):
        data = self._post(password="password")
        self.assertFalse(_rule_ok(data["rules"], "commonly used"))

    def test_similarity_uses_typed_username(self):
        data = self._post(password="northwindbank", username="northwindbank")
        self.assertFalse(_rule_ok(data["rules"], "similar"))

    def test_empty_password_is_not_all_ok(self):
        self.assertFalse(self._post(password="")["all_ok"])
