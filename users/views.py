"""Views for the users app: account signup + live password validation.

Login / logout / password-reset are handled by Django's built-in views
wired up in `users/urls.py`.
"""
from django.conf import settings
from django.contrib.auth import get_user_model, login, password_validation
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView

from .forms import PasswordResetRequestForm, SignUpForm
from .models import PasswordResetRequest


class SignUpView(CreateView):
    """Create a new User, log them in, and redirect to the Vue SPA.

    By the time the user sees the success page they're already
    authenticated, so dropping them on /accounts/login/ would feel
    redundant. We redirect to LOGIN_REDIRECT_URL (the Vue SPA mount
    at /app/) to match the post-login experience; same destination
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


@require_POST
def password_requirements(request):
    """Validate server-side so the live checklist can't drift from what
    signup and change-password actually enforce."""
    password = request.POST.get("password", "")
    User = get_user_model()
    # The similarity check needs a user to compare against.
    if request.user.is_authenticated:
        check_user = request.user
    else:
        check_user = User(
            username=request.POST.get("username", ""),
            email=request.POST.get("email", ""),
        )

    rules = []
    for validator in password_validation.get_password_validators(
        settings.AUTH_PASSWORD_VALIDATORS
    ):
        try:
            validator.validate(password, check_user)
            ok = True
        except ValidationError:
            ok = False
        rules.append({"label": validator.get_help_text(), "ok": ok})

    return JsonResponse({
        "rules": rules,
        "all_ok": bool(password) and all(r["ok"] for r in rules),
    })


@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    """The response is identical whether or not the account exists, so a
    submit can't be used to probe for usernames.
    """
    submitted = False
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        PasswordResetRequest.objects.create(
            identifier=form.cleaned_data["identifier"].strip(),
        )
        submitted = True
        form = PasswordResetRequestForm()
    return render(request, "registration/password_forgot.html", {
        "form": form,
        "submitted": submitted,
    })
