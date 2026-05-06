"""Views for the users app: account signup.

Login / logout / password-reset are handled by Django's built-in views
wired up in `users/urls.py`.
"""
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignUpForm


class SignUpView(CreateView):
    """Create a new User and immediately log them in.

    Redirects to the project list on success — by the time the user
    sees the 'success' page they're already authenticated, so dropping
    them on /accounts/login/ would feel redundant.
    """

    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("scans:project_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
