"""Views for the users app: account signup.

Login / logout / password-reset are handled by Django's built-in views
wired up in `users/urls.py`.
"""
from django.conf import settings
from django.contrib.auth import login
from django.views.generic import CreateView

from .forms import SignUpForm


class SignUpView(CreateView):
    """Create a new User, log them in, and redirect to the Vue SPA.

    By the time the user sees the success page they're already
    authenticated, so dropping them on /accounts/login/ would feel
    redundant. We redirect to LOGIN_REDIRECT_URL (the Vue SPA mount
    at /app/) to match the post-login experience — same destination
    whether the user just signed up or just logged in.
    """

    form_class = SignUpForm
    template_name = "registration/signup.html"

    def get_success_url(self):
        return settings.LOGIN_REDIRECT_URL

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
