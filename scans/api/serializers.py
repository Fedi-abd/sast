"""DRF serializers for the read-only API."""
from django.db.models import Count
from rest_framework import serializers

from scans.models import Finding, Project, Scan


class ProjectSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True,
    )

    class Meta:
        model = Project
        fields = [
            "id", "name", "language",
            "source_type", "source_type_display",
            "created_at",
        ]


class ScanSerializer(serializers.ModelSerializer):
    finding_count = serializers.IntegerField(read_only=True)
    tool_display = serializers.CharField(source="get_tool_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    project_id = serializers.UUIDField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Scan
        fields = [
            "id",
            "project_id", "project_name",
            "tool", "tool_display",
            "status", "status_display",
            "started_at", "finished_at", "duration_seconds",
            "finding_count", "error_message",
        ]


class FindingSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(
        source="get_severity_display", read_only=True,
    )

    class Meta:
        model = Finding
        fields = [
            "id", "tool", "rule_id",
            "severity", "severity_display",
            "file_path", "line_number", "message",
            "cwe_id", "owasp_category",
            "confidence_score",
        ]


def annotate_finding_count(queryset):
    return queryset.annotate(finding_count=Count("findings"))
