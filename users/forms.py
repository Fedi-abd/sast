"""Auth forms for the users app.

Both forms reuse Django's built-in `UserCreationForm` and
`AuthenticationForm` so we get the same validation rules (password
length, similarity to username, common-password check, etc.) without
re-implementing them. The only customization is dressing each field
with Bootstrap's `form-control` class so the templates render cleanly.
"""
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


def _bootstrapify(form):
    """Add `form-control` to every visible field's widget."""
    for field in form.fields.values():
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (existing + " form-control").strip()


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self)


class BootstrapAuthenticationForm(AuthenticationForm):
    """Vanilla Django login form with Bootstrap classes attached."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrapify(self)
