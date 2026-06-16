from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        # Importing the module attaches the @receiver-decorated
        # handlers to Django's signal dispatcher. Has to live in
        # ready() rather than top-of-models.py because models aren't
        # fully loaded yet during apps.py import.
        from . import signals  # noqa: F401
