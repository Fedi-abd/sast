"""Auth URLs for the platform.

Mounted at /accounts/ from config/urls.py. Provides:
  /accounts/login/    -> our Bootstrap-styled login
  /accounts/logout/   -> Django's built-in logout (POST)
  /accounts/signup/   -> create-and-auto-login signup
plus the rest of `django.contrib.auth.urls` (password change/reset)
which we get for free without listing them.
"""
from django.contrib.auth.views import LoginView
from django.urls import include, path

from .forms import BootstrapAuthenticationForm
from .views import SignUpView, password_requirements, password_reset_request

urlpatterns = [
    # Override the built-in LoginView so it picks up our styled form.
    path(
        "login/",
        LoginView.as_view(authentication_form=BootstrapAuthenticationForm),
        name="login",
    ),
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "password/requirements/",
        password_requirements,
        name="password-requirements",
    ),
    path("password/forgot/", password_reset_request, name="password-forgot"),
    # Password change/reset views, plus the LogoutView used by the navbar
    # button. Listed AFTER login/ so our custom one wins.
    path("", include("django.contrib.auth.urls")),
]
