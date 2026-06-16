"""Backfill UserProfile for users created before the signal existed.

The `post_save` handler in `users.signals` auto-creates a profile for
*new* users, but pre-existing users at migration time don't fire the
signal. Without this backfill, any old user would get an
`UserProfile.DoesNotExist` the first time the platform reads their
profile.

Idempotent: uses `get_or_create`, safe to run on a DB that already
has profiles.
"""
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("users", "UserProfile")

    for user in User.objects.all():
        UserProfile.objects.get_or_create(user=user)


def reverse_noop(apps, schema_editor):
    # Removing the backfilled profiles on rollback would delete
    # whatever credits an admin had set; safer to leave the profile
    # rows in place. UserProfile.objects.all().delete() is what a
    # destructive reverse would do; we deliberately don't.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, reverse_noop),
    ]
