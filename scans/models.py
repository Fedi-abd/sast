from django.db import models
from django.contrib.auth.models import User
import uuid


def _archive_upload_path(instance, filename):
    """`MEDIA_ROOT/uploads/<project-uuid>/<original-filename>`.

    The UUID directory namespaces uploads so two users uploading
    `code.zip` never collide; the original filename is preserved so the
    UI can show the user a familiar name.
    """
    return f"uploads/{instance.id}/{filename}"


class Project(models.Model):
    SOURCE_LOCAL = "local"
    SOURCE_UPLOAD = "upload"
    SOURCE_GIT = "git"
    SOURCE_CHOICES = [
        (SOURCE_LOCAL, "Local path"),
        (SOURCE_UPLOAD, "Uploaded archive"),
        (SOURCE_GIT, "Git repository"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    language = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')

    source_type = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_LOCAL,
    )

    # Local: required when source_type == SOURCE_LOCAL.
    repo_path = models.CharField(max_length=500, blank=True)

    # Upload: required when source_type == SOURCE_UPLOAD.
    source_archive = models.FileField(
        upload_to=_archive_upload_path, blank=True, null=True,
    )
    # Original filename, kept for display in the UI even though storage
    # would normally re-use it via upload_to.
    source_filename = models.CharField(max_length=255, blank=True)

    # Git: git_url is required when source_type == SOURCE_GIT;
    # git_branch is optional (empty = repo's default branch).
    git_url = models.URLField(max_length=500, blank=True)
    git_branch = models.CharField(max_length=100, blank=True)

    # SonarQube: auto-generated on save() if blank. Format
    # `<owner_uuid>__<project_uuid>`, which is unique-per-user-per-project
    # and lets a single SonarQube instance host every user's scans
    # without collisions. The admin token in settings authenticates all
    # uploads, so users never see this value.
    sonar_project_key = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [models.Index(fields=['created_at'])]

    def save(self, *args, **kwargs):
        # On first save, derive the Sonar key from owner + project IDs.
        # Saved permanently so it stays stable across rescans.
        if not self.sonar_project_key and self.owner_id and self.id:
            self.sonar_project_key = f"{self.owner_id}__{self.id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Scan(models.Model):
    STATUS_CHOICES = [('RUNNING', 'Running'), ('SUCCESS', 'Success'), ('FAILED', 'Failed')]
    TOOL_CHOICES = [("semgrep", "Semgrep"),("sonarqube", "SonarQube")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='scans')
    tool = models.CharField(max_length=20, choices=TOOL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        indexes = [models.Index(fields=['project', 'started_at'])]
    
    def __str__(self):
        return f"{self.project.name} - {self.tool} - {self.status}"

class SonarSettings(models.Model):
    """Platform-wide SonarQube config, editable via Django admin.

    Singleton: only one row should ever exist. The admin registration
    blocks adding a second one, and `get_solo()` lazily creates the
    first row on demand. When fields are blank, scan code falls back
    to the corresponding `settings.SONAR_*` value (env-var driven).
    """

    SINGLETON_PK = 1

    id = models.PositiveIntegerField(primary_key=True, default=SINGLETON_PK, editable=False)
    host = models.URLField(
        max_length=200, blank=True,
        help_text="SonarQube server URL, e.g. http://localhost:9000. "
                  "Leave blank to use SONAR_HOST from .env.",
    )
    token = models.CharField(
        max_length=200, blank=True,
        help_text="Admin token from SonarQube (My Account → Security). "
                  "Leave blank to use SONAR_TOKEN from .env.",
    )
    issue_types = models.CharField(
        max_length=200, blank=True,
        help_text='Comma-separated. Default: "VULNERABILITY". Use '
                  '"VULNERABILITY,BUG,CODE_SMELL" to import everything. '
                  "Leave blank to use SAST_SONAR_ISSUE_TYPES from .env.",
    )
    include_hotspots = models.BooleanField(
        default=True,
        help_text="Show SonarQube Security Hotspots in scan results. Off "
                  "drops them from the findings view and the type menu "
                  "(they're still scanned, just not surfaced).",
    )
    # Audit stamp for the in-app admin console: who last saved this
    # config and when. Blank updated_by = edited outside the API
    # (Django admin or shell).
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Sonar settings"
        verbose_name_plural = "Sonar settings"

    def __str__(self):
        host = self.host or "(env default)"
        token_status = "set" if self.token else "(env)"
        return f"SonarQube: {host} • token: {token_status}"

    @classmethod
    def get_solo(cls):
        """Return the singleton row, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj


class PlatformSettings(models.Model):
    """Deployment toggles editable from the in-app admin console.

    Singleton, same pattern as `SonarSettings`. Only flags that can
    safely change at runtime live here. `SAST_DEBUG_UI` stays
    env-driven because it gates URL mounting at import time, so a DB
    toggle couldn't take effect without a restart anyway.
    """

    SINGLETON_PK = 1

    id = models.PositiveIntegerField(primary_key=True, default=SINGLETON_PK, editable=False)
    hide_local_source = models.BooleanField(
        default=True,
        help_text=(
            "Production safety: refuse the local-path source type for "
            "new projects (existing local projects keep working). "
            "On by default; untick to allow local paths in dev."
        ),
    )

    class Meta:
        verbose_name = "Platform settings"
        verbose_name_plural = "Platform settings"

    def __str__(self):
        return f"Platform settings (hide_local_source={self.hide_local_source})"

    @classmethod
    def get_solo(cls):
        """Return the singleton row, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj


class Finding(models.Model):
    SEVERITY_CHOICES = [('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name='findings')
    tool = models.CharField(max_length=50)
    rule_id = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    file_path = models.CharField(max_length=500)
    line_number = models.IntegerField()
    message = models.TextField()
    # cwe_id wide enough for tools that emit "CWE-89: long description here"
    # (Semgrep does this); owasp_category wide enough for the longest 2017
    # category, "A9:2017-Using Components with Known Vulnerabilities" (51).
    cwe_id = models.CharField(max_length=200, blank=True)
    owasp_category = models.CharField(max_length=80, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    raw = models.JSONField()
    # Triage flag: the dev marks a finding solved to drop it from the
    # live list while keeping it counted. Per-scan (a rescan is fresh rows).
    solved = models.BooleanField(default=False)
    
    class Meta:
        indexes = [models.Index(fields=['severity']), models.Index(fields=['owasp_category'])]
    
    def __str__(self):
        return f"{self.rule_id} - {self.severity}"
