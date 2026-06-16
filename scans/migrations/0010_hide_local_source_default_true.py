"""Flip `hide_local_source` to default-on (user decision 2026-06-12).

Local-path scanning is a dev convenience and a prod foot-gun, so new
deployments now start with it hidden; admins opt back in via the
deployment toggle. The data step flips any existing singleton row too,
so the live DB picks up the new posture without a manual admin visit.
"""
from django.db import migrations, models


def _flip_existing_rows(apps, schema_editor):
    """Set hide_local_source=True on already-created settings rows."""
    PlatformSettings = apps.get_model("scans", "PlatformSettings")
    PlatformSettings.objects.update(hide_local_source=True)


class Migration(migrations.Migration):

    dependencies = [
        ('scans', '0009_platformsettings_sonarsettings_updated_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='platformsettings',
            name='hide_local_source',
            field=models.BooleanField(default=True, help_text='Production safety: refuse the local-path source type for new projects (existing local projects keep working). On by default; untick to allow local paths in dev.'),
        ),
        # Reverse is a no-op: un-migrating shouldn't silently re-enable
        # local paths on a deployment that wants them off.
        migrations.RunPython(_flip_existing_rows, migrations.RunPython.noop),
    ]
