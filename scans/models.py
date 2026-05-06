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

    # Local — required when source_type == SOURCE_LOCAL.
    repo_path = models.CharField(max_length=500, blank=True)

    # Upload — required when source_type == SOURCE_UPLOAD.
    source_archive = models.FileField(
        upload_to=_archive_upload_path, blank=True, null=True,
    )
    # Original filename, kept for display in the UI even though storage
    # would normally re-use it via upload_to.
    source_filename = models.CharField(max_length=255, blank=True)

    # Git — git_url is required when source_type == SOURCE_GIT;
    # git_branch is optional (empty = repo's default branch).
    git_url = models.URLField(max_length=500, blank=True)
    git_branch = models.CharField(max_length=100, blank=True)

    class Meta:
        indexes = [models.Index(fields=['created_at'])]

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
    
    class Meta:
        indexes = [models.Index(fields=['severity']), models.Index(fields=['owasp_category'])]
    
    def __str__(self):
        return f"{self.rule_id} - {self.severity}"
