"""Authentication backend for username-or-email sign-in.

Subclasses `AllowAllUsersModelBackend` (not the stock `ModelBackend`)
so inactive accounts still authenticate and the login form can show
its dedicated "account disabled" message instead of the generic
wrong-credentials one; same reasoning as the previous backend choice.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import AllowAllUsersModelBackend


class EmailOrUsernameBackend(AllowAllUsersModelBackend):
    """Accept the account email as the login identifier.

    Username keeps priority: the email lookup only runs when the
    username lookup matched nobody and the identifier contains an
    "@". The match is case-insensitive and honoured only when it is
    unambiguous (emails were historically not unique on this model,
    so two accounts sharing an address keep username-only login
    rather than the backend guessing between them).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(
            request, username=username, password=password, **kwargs
        )
        if user is not None or not username or "@" not in username:
            return user

        UserModel = get_user_model()
        # [:2] caps the query: one row means unambiguous, two means bail.
        matches = list(
            UserModel._default_manager.filter(email__iexact=username)[:2]
        )
        if len(matches) != 1:
            return None
        candidate = matches[0]
        if candidate.check_password(password) and self.user_can_authenticate(candidate):
            return candidate
        return None
