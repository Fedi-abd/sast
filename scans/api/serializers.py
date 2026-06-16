"""DRF serializers for the SAST API.

Two flavors of project serializer:

  - `ProjectSerializer` (read): the shape returned by list/retrieve.
    Includes display values (`source_type_display`) and timestamps.
  - `ProjectWriteSerializer` (create/update): mirrors `ProjectForm`'s
    validation rules (source-type-conditional required fields, git
    host allowlist, source_type immutability on update). The two are
    separate because read responses include data the client never
    sends (display values, IDs) and write payloads need validation
    rules that don't make sense on a read response.

Scan and Finding serializers are read-only; scans are created
indirectly through `/api/scans/trigger/` (which writes via
`ScanService._create_running_scan` + django-q2), and findings are
created by the scan worker. Nothing on the client sends those
directly.
"""
import os
import zipfile
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import serializers

from scans.models import Finding, PlatformSettings, Project, Scan
from scans.services.path_resolver import _ALLOWED_GIT_HOSTS
from users.models import UserProfile


def _profile_limits(user):
    """(max_projects, max_upload_mb), with class defaults when the
    profile row is missing, mirrors MeSerializer's defensive stance
    against user-creation paths that bypass the post_save signal."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return UserProfile.DEFAULT_MAX_PROJECTS, UserProfile.DEFAULT_MAX_UPLOAD_MB
    return profile.max_projects, profile.max_upload_mb


class ProjectSerializer(serializers.ModelSerializer):
    """Read-shape: list + retrieve responses."""

    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True,
    )

    class Meta:
        model = Project
        fields = [
            "id", "name", "language",
            "source_type", "source_type_display",
            "repo_path", "git_url", "git_branch",
            "source_archive", "source_filename",
            "created_at",
        ]


class ProjectWriteSerializer(serializers.ModelSerializer):
    """Write-shape: create + partial update payloads.

    Validation mirrors `scans.forms.ProjectForm` to keep the templated
    and JSON paths in sync:

      - `local`  → `repo_path` required.
      - `upload` → `source_archive` required on create; immutable on
        update (Sprint 2 design, the `_ALLOWED_GIT_HOSTS` analog for
        archives).
      - `git`    → `git_url` required; URL must be http(s) and the
        host must be on `_ALLOWED_GIT_HOSTS`.

    The `source_type` field is also locked after creation: a client
    that POSTs a different `source_type` on PATCH gets a validation
    error rather than silently ignored.
    """

    class Meta:
        model = Project
        fields = [
            "id", "name", "language",
            "source_type",
            "repo_path",
            "source_archive", "source_filename",
            "git_url", "git_branch",
        ]
        read_only_fields = ["id", "source_filename"]

    def validate(self, attrs):
        instance = self.instance
        is_update = instance is not None
        request = self.context.get("request")
        user = getattr(request, "user", None)

        # Admin-configurable quotas (Track 5). Checked first so the
        # user hears "you're at your limit" rather than a field nitpick
        # on a project that couldn't be created anyway.
        if user is not None:
            # A negative limit is the admin-set "unlimited" sentinel: skip
            # the cap entirely.
            max_projects, max_upload_mb = _profile_limits(user)
            if not is_update and max_projects >= 0:
                owned = Project.objects.filter(owner=user).count()
                if owned >= max_projects:
                    raise serializers.ValidationError(
                        f"Project limit reached ({max_projects}). "
                        "Ask an admin to raise it."
                    )
            archive = attrs.get("source_archive")
            if (archive is not None and max_upload_mb >= 0
                    and archive.size > max_upload_mb * 1024 * 1024):
                raise serializers.ValidationError({
                    "source_archive": f"Archive exceeds your {max_upload_mb} MB "
                                      "upload limit.",
                })

        # On update, source_type is locked. Don't even let the client
        # send a different value silently; return a clear error.
        if is_update and "source_type" in attrs and attrs["source_type"] != instance.source_type:
            raise serializers.ValidationError({
                "source_type": "Source type is fixed once a project exists. "
                               "Delete and recreate to use a different source.",
            })

        # The effective source_type for this validation pass: the
        # incoming value on create, or the saved one on update.
        source_type = attrs.get("source_type") or (instance and instance.source_type)
        if not source_type:
            # On create with no source_type at all, let the field
            # validator complain about the missing required value.
            return attrs

        if source_type == Project.SOURCE_LOCAL:
            # Deployment flag: production hides local paths (Q9). Only
            # blocks NEW projects; existing local ones keep scanning.
            if not is_update and PlatformSettings.get_solo().hide_local_source:
                raise serializers.ValidationError({
                    "source_type": "The local path source type is disabled "
                                   "on this deployment.",
                })
            if not attrs.get("repo_path") and not (is_update and instance.repo_path):
                raise serializers.ValidationError({
                    "repo_path": "A repository path is required for the local source type.",
                })
            # Fail at create time, not at first scan. A typo'd path
            # otherwise burns a credit on a guaranteed-FAILED scan.
            if attrs.get("repo_path") and not os.path.isdir(attrs["repo_path"]):
                raise serializers.ValidationError({
                    "repo_path": "Path does not exist (or is not a directory) "
                                 "on the scan host.",
                })

        elif source_type == Project.SOURCE_UPLOAD:
            has_existing = bool(is_update and instance.source_archive)
            has_uploaded = bool(attrs.get("source_archive"))
            if not (has_existing or has_uploaded):
                raise serializers.ValidationError({
                    "source_archive": "A ZIP archive is required for the upload source type.",
                })
            if has_uploaded:
                # Same fail-fast rationale as the path check above.
                if not zipfile.is_zipfile(attrs["source_archive"]):
                    raise serializers.ValidationError({
                        "source_archive": "Not a valid ZIP archive.",
                    })
                # is_zipfile consumed the stream; rewind for storage.
                attrs["source_archive"].seek(0)

        elif source_type == Project.SOURCE_GIT:
            url = attrs.get("git_url") or (is_update and instance.git_url) or ""
            if not url:
                raise serializers.ValidationError({
                    "git_url": "A Git URL is required for the git source type.",
                })
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme not in ("http", "https"):
                raise serializers.ValidationError({
                    "git_url": "Git URL must use http(s).",
                })
            if host not in _ALLOWED_GIT_HOSTS:
                allowed = ", ".join(sorted(_ALLOWED_GIT_HOSTS))
                raise serializers.ValidationError({
                    "git_url": f"Host {host!r} is not on the allowlist. Allowed: {allowed}.",
                })

        return attrs

    def create(self, validated_data):
        archive = validated_data.get("source_archive")
        # New uploads come in as `UploadedFile` whose `.name` is the
        # bare filename. Existing FieldFiles (only relevant on update)
        # have a storage path with slashes. Preserve the original name
        # for display.
        if archive and "/" not in (archive.name or ""):
            validated_data["source_filename"] = archive.name
        project = super().create(validated_data)
        # The owner is set on the view (we don't trust the client);
        # see ProjectViewSet.perform_create.
        self._clear_non_active_source_fields(project)
        project.save()
        return project

    def update(self, instance, validated_data):
        archive = validated_data.get("source_archive")
        if archive and "/" not in (archive.name or ""):
            validated_data["source_filename"] = archive.name
        project = super().update(instance, validated_data)
        self._clear_non_active_source_fields(project)
        project.save()
        return project

    @staticmethod
    def _clear_non_active_source_fields(project):
        """Zero out the fields that don't belong to the active source type."""
        if project.source_type == Project.SOURCE_LOCAL:
            project.source_archive = None
            project.git_url = ""
            project.git_branch = ""
        elif project.source_type == Project.SOURCE_UPLOAD:
            project.repo_path = ""
            project.git_url = ""
            project.git_branch = ""
        elif project.source_type == Project.SOURCE_GIT:
            project.repo_path = ""
            project.source_archive = None


class ScanSerializer(serializers.ModelSerializer):
    """Read-shape for scans. Polling target for live status updates."""

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


class ScanTriggerSerializer(serializers.Serializer):
    """Request body for POST /api/scans/trigger/.

    Fields:
      - project_id: UUID of the target project. Must belong to the
        requesting user; the view enforces ownership.
      - tool: one of "semgrep", "sonarqube", or "both". "both" expands
        to the two tools in the view.
    """

    project_id = serializers.UUIDField()
    tool = serializers.ChoiceField(choices=["semgrep", "sonarqube", "both"])


class MeSerializer(serializers.ModelSerializer):
    """Shape for GET /api/me/: minimal user identity for the SPA.

    `credits` reads from the user's `UserProfile` (auto-created via a
    post_save signal in `users.signals`). If the profile is somehow
    missing (shouldn't happen post-Track-6 backfill, but a defense
    against any future user-creation path that bypasses the signal),
    the field reports 0 rather than erroring.
    """

    credits = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "is_staff", "credits"]
        read_only_fields = fields

    def get_credits(self, user):
        profile = getattr(user, "profile", None)
        return profile.credits if profile is not None else 0


class FindingSerializer(serializers.ModelSerializer):
    """Read-shape for findings (rows in the scan-detail findings table)."""

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
            "confidence_score", "solved",
        ]


class CrossProjectFindingSerializer(FindingSerializer):
    """Findings on the cross-project Vulnerabilities page.

    Extends `FindingSerializer` with project + scan context that
    scan-detail findings don't need (the scan-detail page already
    knows which scan/project you're on). `detected_at` is the scan's
    started_at. Finer granularity (per-finding emit time) isn't
    tracked by Semgrep or SonarQube, so the scan timestamp is the
    best proxy.

    Inherits from `FindingSerializer` so a field added there
    automatically propagates to this serializer, avoiding the silent
    drift the auditor flagged on the first cut.
    """

    project_id = serializers.UUIDField(source="scan.project.id", read_only=True)
    project_name = serializers.CharField(source="scan.project.name", read_only=True)
    scan_id = serializers.UUIDField(source="scan.id", read_only=True)
    detected_at = serializers.DateTimeField(source="scan.started_at", read_only=True)

    class Meta(FindingSerializer.Meta):
        fields = FindingSerializer.Meta.fields + [
            "project_id", "project_name", "scan_id", "detected_at",
        ]


def annotate_finding_count(queryset):
    return queryset.annotate(finding_count=Count("findings"))
