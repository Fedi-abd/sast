"""Auto-create a UserProfile when a new User is saved.

Registered in `users.apps.UsersConfig.ready`.

`get_or_create` rather than plain `create` so the handler is
idempotent: re-running migrations, loading fixtures, or any other
flow that double-fires `post_save` won't blow up on a UNIQUE
constraint violation.
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
