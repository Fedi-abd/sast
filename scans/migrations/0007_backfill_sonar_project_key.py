"""Data migration: backfill `sonar_project_key` for projects created
before the field existed.

Migration 0006 added the column but didn't populate it. The auto-fill
in `Project.save()` only fires on subsequent saves, so projects that
haven't been edited since 0006 land here with `sonar_project_key=""`,
and `_build_scan_config` then refuses to start a Sonar scan because
the project_key is missing.

Idempotent; only touches rows where `sonar_project_key` is empty.
"""
from django.db import migrations


def backfill_sonar_project_keys(apps, schema_editor):
    Project = apps.get_model("scans", "Project")
    for project in Project.objects.filter(sonar_project_key=""):
        project.sonar_project_key = f"{project.owner_id}__{project.id}"
        project.save(update_fields=["sonar_project_key"])


def noop_reverse(apps, schema_editor):
    # Reversing isn't useful; empty values would just re-trigger the
    # same "project_key required" failure mode we just fixed.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("scans", "0006_project_sonar_project_key"),
    ]

    operations = [
        migrations.RunPython(backfill_sonar_project_keys, noop_reverse),
    ]
