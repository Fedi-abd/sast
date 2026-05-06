"""Data migration — normalize legacy `source_filename` values.

Before the form fix in this PR, ProjectForm.save() was assigning the
existing FieldFile's `name` (which holds the storage path
"uploads/<uuid>/x.zip") into `source_filename` on every edit. The
column was supposed to hold just the bare filename for display.

This migration cleans up rows where the value still has a slash by
splitting on the last "/" and keeping only the trailing component.
Idempotent — safe to run more than once; rows already in the bare-name
form pass through unchanged.
"""
from django.db import migrations


def normalize_source_filenames(apps, schema_editor):
    Project = apps.get_model("scans", "Project")
    for project in Project.objects.exclude(source_filename=""):
        if "/" in project.source_filename:
            project.source_filename = project.source_filename.rsplit("/", 1)[-1]
            project.save(update_fields=["source_filename"])


def noop_reverse(apps, schema_editor):
    # Once normalized to the bare filename, we can't reconstruct the
    # original storage path. The reverse migration is intentionally a
    # no-op — the original "bug-shaped" data isn't worth restoring.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("scans", "0004_project_git_branch_project_git_url_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_source_filenames, noop_reverse),
    ]
