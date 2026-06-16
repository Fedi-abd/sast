"""Resolve a Project's source to a local directory the scanner can read.

Each source type returns a `ResolvedPath` with:
  - `path`: absolute local directory the adapter can scan
  - `cleanup()`: idempotent callable that removes any temp dirs created

`local` sources return a no-op cleanup. `upload` and `git` create temp
dirs and return real cleanup callables. The caller is expected to use
the cleanup in a `try/finally` so temp dirs go away on both success and
failure.
"""
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from django.conf import settings


@dataclass
class ResolvedPath:
    path: str
    cleanup: Callable[[], None]


# Allowlist of hosts we accept for the `git` source type. Keeping this
# tight (HTTPS only, two known hosts) blocks shell-style URLs that could
# trick git into running arbitrary commands.
_ALLOWED_GIT_HOSTS = {"github.com", "gitlab.com"}


def _noop():
    pass


def _safe_rmtree(path):
    """Best-effort tempdir cleanup. Errors are intentionally swallowed;
    if the OS can't delete a temp file we don't want to crash a scan."""
    if path and os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


class PathResolver:
    """Translate a Project into a local directory the scanner can read."""

    def resolve(self, project) -> ResolvedPath:
        """Dispatch by `project.source_type`."""
        st = project.source_type
        if st == "local":
            return self._resolve_local(project)
        if st == "upload":
            return self._resolve_upload(project)
        if st == "git":
            return self._resolve_git(project)
        raise ValueError(f"Unknown source_type: {st!r}")

    # -- local ---------------------------------------------------------

    def _resolve_local(self, project) -> ResolvedPath:
        path = project.repo_path or ""
        if not path:
            raise ValueError("Local project has no repo_path set")
        if not os.path.exists(path):
            raise ValueError(f"Repository path does not exist: {path}")
        return ResolvedPath(path=path, cleanup=_noop)

    # -- upload --------------------------------------------------------

    def _resolve_upload(self, project) -> ResolvedPath:
        if not project.source_archive:
            raise ValueError("Upload project has no archive attached")

        archive_path = project.source_archive.path
        max_extracted_bytes = (
            getattr(settings, "SAST_MAX_EXTRACTED_SIZE_MB", 750) * 1024 * 1024
        )

        extract_dir = tempfile.mkdtemp(prefix="sast-upload-")
        try:
            with zipfile.ZipFile(archive_path) as zf:
                self._validate_zip(zf, extract_dir, max_extracted_bytes)
                zf.extractall(extract_dir)
        except Exception:
            _safe_rmtree(extract_dir)
            raise

        return ResolvedPath(
            path=extract_dir,
            cleanup=lambda: _safe_rmtree(extract_dir),
        )

    @staticmethod
    def _validate_zip(zf, extract_dir, max_extracted_bytes):
        """Defenses run before any file is written:
          - zip-slip: every entry must extract inside `extract_dir`.
          - zip-bomb: total uncompressed size must be under the cap.
        """
        extract_root = os.path.realpath(extract_dir)
        total = 0
        for info in zf.infolist():
            # zip-slip: resolve the destination path and confirm it
            # stays inside extract_root. Catches absolute paths,
            # `../` traversal, and Windows drive letters.
            target = os.path.realpath(os.path.join(extract_dir, info.filename))
            if not (target == extract_root or target.startswith(extract_root + os.sep)):
                raise ValueError(
                    f"Archive contains an unsafe path: {info.filename!r}"
                )
            total += info.file_size
            if total > max_extracted_bytes:
                mb = max_extracted_bytes // (1024 * 1024)
                raise ValueError(
                    f"Archive exceeds the {mb} MB extracted-size cap "
                    "(possible zip bomb)."
                )

    # -- git -----------------------------------------------------------

    def _resolve_git(self, project) -> ResolvedPath:
        url = project.git_url or ""
        if not url:
            raise ValueError("Git project has no URL")

        self._validate_git_url(url)

        timeout = getattr(settings, "SAST_GIT_CLONE_TIMEOUT", 60)
        clone_dir = tempfile.mkdtemp(prefix="sast-git-")
        cmd = ["git", "clone", "--depth", "1"]
        if project.git_branch:
            cmd.extend(["--branch", project.git_branch])
        cmd.extend([url, clone_dir])

        # Nonexistent/private repos make git prompt for credentials,
        # which hangs headless until the timeout. Kill the prompt so
        # those clones fail fast with a real stderr instead.
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "echo"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            _safe_rmtree(clone_dir)
            raise RuntimeError(
                f"git clone timed out after {timeout}s ({url})"
            )
        except FileNotFoundError:
            _safe_rmtree(clone_dir)
            raise RuntimeError(
                "git executable not found. Install git in the runtime environment."
            )
        except Exception:
            _safe_rmtree(clone_dir)
            raise

        if result.returncode != 0:
            _safe_rmtree(clone_dir)
            raise RuntimeError(
                f"git clone failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        return ResolvedPath(
            path=clone_dir,
            cleanup=lambda: _safe_rmtree(clone_dir),
        )

    @staticmethod
    def _validate_git_url(url):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Git URL must use http(s); got scheme {parsed.scheme!r}"
            )
        host = (parsed.hostname or "").lower()
        if host not in _ALLOWED_GIT_HOSTS:
            raise ValueError(
                f"Git host not allowed: {host!r}. "
                f"Allowed: {', '.join(sorted(_ALLOWED_GIT_HOSTS))}"
            )
