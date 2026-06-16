"""Auth forms for the users app.

Both forms subclass Django's built-in `UserCreationForm` and
`AuthenticationForm`, inheriting their validation (password length,
similarity-to-username, common-password and numeric-password checks)
unchanged. `__init__` only decorates the widgets with placeholders and
`autocomplete` hints so the standalone auth templates render cleanly and
password managers behave. No CSS classes are attached; the templates
wrap each field in the design system's `.input` element themselves.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Your administrator uses this for password resets.",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        """Refuse an email already on another account (case-insensitive).

        The stock User model doesn't constrain email uniqueness, but the
        platform treats email as a login identifier (EmailOrUsernameBackend),
        so new signups must keep it unambiguous. Pre-existing duplicates
        are unaffected; those accounts simply stay username-only logins.
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account already uses this email address."
            )
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "pick a username", "autocomplete": "username", "autofocus": True}
        )
        self.fields["email"].widget.attrs.update(
            {"placeholder": "you@example.com", "autocomplete": "email"}
        )
        self.fields["password1"].widget.attrs.update(
            {"placeholder": "8+ characters", "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "repeat it", "autocomplete": "new-password"}
        )
        self.fields["password2"].label = "Confirm password"


class BootstrapAuthenticationForm(AuthenticationForm):
    """Django's auth form with placeholder/autocomplete hints for the styled login.

    The `inactive` message replaces the stock one so a deactivated user
    learns to contact their admin instead of doubting their password.
    Reaching that branch requires `AllowAllUsersModelBackend` (set in
    settings); the default backend rejects inactive users during
    `authenticate()`, which surfaces as "wrong credentials".
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": "This account is disabled. Contact your administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        self.fields["username"].widget.attrs.update(
            {"placeholder": "username or email", "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "password", "autocomplete": "current-password"}
        )


class PasswordResetRequestForm(forms.Form):
    """Not checked against the user table, so a submit reveals nothing
    about which accounts exist.
    """

    identifier = forms.CharField(label="Username or email", max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identifier"].widget.attrs.update(
            {"placeholder": "username or email", "autocomplete": "username", "autofocus": True}
        )
