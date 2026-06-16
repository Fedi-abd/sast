"""User-adjacent models.

Currently just `UserProfile`, which extends the default `auth.User`
with platform-specific fields (credits today; admin-configurable
limits later in Sprint 4).

We're using the profile-extension pattern rather than swapping in a
custom user model. The trade-off:

  - Custom user model is the "Django-recommended" path on day one of
    a new project, but it can't be retrofitted onto an existing
    database without a destructive migration. This project shipped
    Sprint 1 on the default User model, so we live with that.
  - The profile pattern adds one OneToOneField hop on most queries,
    which is negligible at our scale and gets factored into the
    handful of places that read credits.

A `post_save` signal on User (in `users.signals`, registered via
`users.apps.UsersConfig.ready`) creates a `UserProfile` row the first
time a User is saved. Credits default to 100, generous enough for
testing, the admin dashboard will let staff bump or zero this per
user.
"""
from django.conf import settings
from django.db import models, transaction


class InsufficientCreditsError(Exception):
    """Raised by `UserProfile.charge` when the user can't afford the cost.

    Carries the cost and the user's remaining balance on the exception
    instance so the view can surface a useful message without a second
    query.
    """

    def __init__(self, cost: int, remaining: int):
        self.cost = cost
        self.remaining = remaining
        super().__init__(
            f"Insufficient credits: cost {cost}, remaining {remaining}."
        )


class UserProfile(models.Model):
    """Platform-specific extension of `auth.User`."""

    DEFAULT_CREDITS = 100
    DEFAULT_MAX_PROJECTS = 25
    DEFAULT_MAX_UPLOAD_MB = 250

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    credits = models.IntegerField(
        default=DEFAULT_CREDITS,
        help_text=(
            "Scan budget: decremented by `cost_for_tool` on each scan "
            "the user triggers. Reaches zero -> the trigger view returns "
            "402 (Payment Required). Edit here to top up or restrict."
        ),
    )
    max_projects = models.IntegerField(
        default=DEFAULT_MAX_PROJECTS,
        help_text=(
            "Most projects this user may own at once. New creations are "
            "rejected at the cap. 0 blocks project creation entirely."
        ),
    )
    max_upload_mb = models.IntegerField(
        default=DEFAULT_MAX_UPLOAD_MB,
        help_text=(
            "Per-user ZIP upload cap in MB. The global "
            "SAST_MAX_UPLOAD_SIZE_MB still applies on top of this. "
            "0 blocks the upload source type entirely."
        ),
    )

    class Meta:
        verbose_name = "user profile"
        verbose_name_plural = "user profiles"

    def __str__(self):
        return f"{self.user.username} (credits: {self.credits})"

    @staticmethod
    def cost_for_tool(tool: str) -> int:
        """Return the credit cost of triggering a scan with `tool`.

        Trivial today: 1 credit per single-tool scan, 2 for "both".
        The prof hasn't ratified a more elaborate cost function yet
        (see open-questions.md), so this lives as a static method that
        can be swapped in one place when policy changes.
        """
        return 2 if tool == "both" else 1

    @classmethod
    def charge(cls, user, cost: int) -> int:
        """Atomically decrement `user`'s credits by `cost`, returning
        the new balance.

        Must run inside a `transaction.atomic()` block; the
        `select_for_update()` row lock relies on an open transaction.
        The caller's transaction also gives us rollback-on-failure for
        free: if scan-row creation fails after this returns, the
        credit decrement reverts with the rest of the transaction.

        Raises `InsufficientCreditsError` (carrying both cost and the
        user's actual remaining balance) when the user can't afford it.
        A cost of 0 short-circuits past the UPDATE, relevant when
        "Run Both" was requested but both tools are already in flight,
        leaving nothing to charge for.
        """
        profile = cls.objects.select_for_update().get(user=user)
        # Staff aren't metered; they scan for ops/debugging, and a
        # depleted admin who can't reproduce a user's issue helps
        # nobody (user decision 2026-06-10). Negative credits = the
        # admin-set unlimited sentinel.
        if user.is_staff or profile.credits < 0:
            return profile.credits
        if profile.credits < cost:
            raise InsufficientCreditsError(cost, profile.credits)
        if cost > 0:
            profile.credits -= cost
            profile.save(update_fields=["credits"])
        return profile.credits

    @classmethod
    def refund(cls, user, amount: int = 1) -> int:
        """Return credits to a user after one of their scans failed.

        Runs in its own transaction (the scan worker holds none) and
        skips staff, who are never charged in the first place.
        """
        with transaction.atomic():
            profile = cls.objects.select_for_update().get(user=user)
            # Never charged (staff or unlimited) means nothing to refund.
            if user.is_staff or profile.credits < 0 or amount <= 0:
                return profile.credits
            profile.credits += amount
            profile.save(update_fields=["credits"])
            return profile.credits


class PasswordResetRequest(models.Model):
    """A self-service reset request waiting for an admin to action it.

    No FK to User on purpose: storing only the typed identifier avoids
    confirming whether an account exists.
    """

    identifier = models.CharField(max_length=254)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["handled", "-created_at"]

    def __str__(self):
        state = "handled" if self.handled else "pending"
        return f"reset request: {self.identifier} ({state})"
