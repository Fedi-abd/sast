"""Forms for the scans app."""
from urllib.parse import urlparse

from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Project
from .services.path_resolver import _ALLOWED_GIT_HOSTS


class ProjectForm(forms.ModelForm):
    """Project create/edit form.

    Validation is conditional on `source_type`:
      - local  -> repo_path required
      - upload -> source_archive required (only on create; edits keep the
                  existing archive immutable per Sprint 2 design)
      - git    -> git_url required; git_branch optional
    """

    class Meta:
        model = Project
        fields = [
            "name",
            "language",
            "source_type",
            "repo_path",
            "source_archive",
            "git_url",
            "git_branch",
        ]
        widgets = {
            "source_type": forms.RadioSelect(),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "language": forms.TextInput(attrs={"class": "form-control"}),
            "repo_path": forms.TextInput(attrs={"class": "form-control"}),
            "source_archive": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "git_url": forms.URLInput(attrs={"class": "form-control"}),
            "git_branch": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "repo_path": "Repository path (on the server)",
            "source_archive": "ZIP archive",
            "git_url": "Git URL (https://github.com/... or https://gitlab.com/...)",
            "git_branch": "Branch (optional — defaults to the repo's default branch)",
        }

    def clean(self):
        cleaned = super().clean()
        source_type = cleaned.get("source_type")

        if source_type == Project.SOURCE_LOCAL:
            if not cleaned.get("repo_path"):
                self.add_error(
                    "repo_path",
                    "A repository path is required for the local source type.",
                )
        elif source_type == Project.SOURCE_UPLOAD:
            # On create the archive must be provided; on edit, an
            # existing archive is fine and immutable (Sprint 2 design).
            # `_state.adding` is the canonical "is this row in the DB
            # yet?" check — `instance.pk` is unreliable for UUID PKs
            # because the default fires at construction time, so a
            # brand-new instance already has a pk.
            is_edit = not self.instance._state.adding
            has_existing = bool(is_edit and self.instance.source_archive)
            has_uploaded = bool(cleaned.get("source_archive"))
            if not (has_existing or has_uploaded):
                self.add_error(
                    "source_archive",
                    "A ZIP archive is required for the upload source type.",
                )
        elif source_type == Project.SOURCE_GIT:
            url = cleaned.get("git_url") or ""
            if not url:
                self.add_error(
                    "git_url",
                    "A Git URL is required for the git source type.",
                )
            else:
                # Same allowlist PathResolver enforces — reject early so
                # the user doesn't end up with a stuck project they can't
                # scan.
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower()
                if parsed.scheme not in ("http", "https"):
                    self.add_error(
                        "git_url",
                        "Git URL must use http(s).",
                    )
                elif host not in _ALLOWED_GIT_HOSTS:
                    allowed = ", ".join(sorted(_ALLOWED_GIT_HOSTS))
                    self.add_error(
                        "git_url",
                        f"Host {host!r} is not on the allowlist. Allowed: {allowed}.",
                    )

        # On edit, source_type is locked (the template renders it as a
        # hidden input). Defense-in-depth: if anyone POSTs a different
        # source_type, snap it back to the saved value. Use _state.adding
        # rather than instance.pk — UUID PKs default at construction so
        # `instance.pk` is truthy for fresh, never-saved instances too.
        if not self.instance._state.adding and source_type != self.instance.source_type:
            cleaned["source_type"] = self.instance.source_type

        return cleaned

    def save(self, commit=True):
        # Two things happen here that can't live in clean():
        # 1) Update source_filename for genuinely new uploads only. On
        #    edit-without-reupload, cleaned_data["source_archive"] is
        #    the existing FieldFile whose .name is the storage path —
        #    writing that into source_filename would mangle the display.
        # 2) Clear data from non-active source-type fields. Doing this
        #    in clean() doesn't stick because _post_clean re-runs
        #    construct_instance which copies cleaned_data back onto the
        #    instance. Setting on the instance just before super().save()
        #    is the place that holds.
        archive = self.cleaned_data.get("source_archive")
        if archive and "/" not in (archive.name or ""):
            # New upload: name is bare ("x.zip"). Existing FieldFile
            # has the storage path ("uploads/<uuid>/x.zip"), with a slash.
            self.instance.source_filename = archive.name

        source_type = self.instance.source_type
        if source_type == Project.SOURCE_LOCAL:
            self.instance.source_archive = None
            self.instance.git_url = ""
            self.instance.git_branch = ""
        elif source_type == Project.SOURCE_UPLOAD:
            self.instance.repo_path = ""
            self.instance.git_url = ""
            self.instance.git_branch = ""
        elif source_type == Project.SOURCE_GIT:
            self.instance.repo_path = ""
            self.instance.source_archive = None

        return super().save(commit=commit)
