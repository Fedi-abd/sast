from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Finding, Project, Scan, SonarSettings


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name", "source_type", "language", "owner", "created_at",
    ]
    list_filter = ["source_type", "language", "owner", "created_at"]
    search_fields = ["name", "repo_path", "git_url", "source_filename"]
    readonly_fields = ["id", "created_at", "sonar_project_key"]


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = [
        "project", "tool", "status",
        "started_at", "duration_seconds", "finished_at",
    ]
    list_filter = ["status", "tool", "started_at", "project__owner"]
    search_fields = ["project__name", "error_message"]
    readonly_fields = [
        "id", "started_at", "finished_at", "duration_seconds",
    ]
    date_hierarchy = "started_at"


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = [
        "rule_id", "severity", "owasp_category",
        "file_path", "line_number", "tool", "scan",
    ]
    list_filter = [
        "severity", "owasp_category", "tool",
        "scan__project", "scan__started_at",
    ]
    search_fields = [
        "rule_id", "message", "file_path", "cwe_id",
    ]
    readonly_fields = ["id", "scan"]


@admin.register(SonarSettings)
class SonarSettingsAdmin(admin.ModelAdmin):
    """Singleton admin — there is only one Sonar settings row.

    Disables the "Add" button once a row exists, and redirects the
    changelist to the change form for the singleton so admins land
    directly on the editor instead of a one-row list.
    """

    list_display = ["__str__", "host", "token_set", "issue_types_or_default"]
    fieldsets = (
        (None, {
            "fields": ("host", "token", "issue_types"),
            "description": (
                "Platform-wide SonarQube configuration. Leave any field "
                "blank to fall back to the matching <code>SONAR_*</code> "
                "environment variable from <code>.env</code>."
            ),
        }),
    )

    def has_add_permission(self, request):
        return not SonarSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't let admins delete the singleton — they should edit it.
        return False

    def changelist_view(self, request, extra_context=None):
        # Land directly on the singleton's edit page for a smoother UX.
        obj = SonarSettings.get_solo()
        return redirect(
            reverse("admin:scans_sonarsettings_change", args=[obj.pk])
        )

    @admin.display(boolean=True, description="Token set?")
    def token_set(self, obj):
        return bool(obj.token)

    @admin.display(description="Issue types")
    def issue_types_or_default(self, obj):
        if obj.issue_types:
            return obj.issue_types
        return format_html("<em>(env default)</em>")
