"""SonarQube adapter — runs the full scan from inside the platform.

Flow on each invocation:
  1. Validate config (token, host, project key, scanner path).
  2. Run `sonar-scanner` against the local source dir; this uploads the
     analysis to the SonarQube server under the given project key.
  3. Poll `GET /api/ce/component?component=<key>` until the server's
     compute task transitions to SUCCESS / FAILED / CANCELED.
  4. Fetch the issues via `GET /api/issues/search?componentKeys=<key>`.
  5. Hand the issues JSON back to the caller — the parser converts it
     into the platform's normalized finding shape.

Same `ToolRunResult` interface as `SemgrepAdapter`, so `ScanService`
doesn't need to know which scanner it's dealing with.
"""
import logging
import os
import shutil
import subprocess
import time

import requests

from .base import ToolAdapter, ToolRunResult

logger = logging.getLogger("scans")


class SonarAdapter(ToolAdapter):
    def __init__(
        self,
        sonar_host="http://localhost:9000",
        sonar_token=None,
        sonar_scanner_path=None,
        scanner_timeout=600,
        poll_interval=2.0,
        poll_timeout=300.0,
        issue_types="VULNERABILITY",
    ):
        self.sonar_host = sonar_host.rstrip("/")
        self.sonar_token = sonar_token
        self.scanner_timeout = scanner_timeout
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        # Empty/None → no filter applied = import everything.
        self.issue_types = (issue_types or "").strip() or None

        # Resolution order matches SemgrepAdapter:
        # explicit arg → env var → PATH lookup → bare name.
        self.sonar_scanner_path = (
            sonar_scanner_path
            or os.getenv("SONAR_SCANNER_PATH")
            or shutil.which("sonar-scanner")
            or "sonar-scanner"
        )

    def run(self, repo_path, config=None):
        config = config or {}
        project_key = config.get("project_key")
        token = config.get("sonar_token") or self.sonar_token

        if not project_key:
            return self._fail("Sonar project_key required")
        if not token:
            return self._fail(
                "Sonar not configured — set SONAR_TOKEN in .env"
            )

        run_err = self._run_scanner(repo_path, project_key, token)
        if run_err is not None:
            return run_err

        wait_err = self._wait_for_processing(project_key, token)
        if wait_err is not None:
            return wait_err

        return self._fetch_issues(project_key, token)

    # ----- pipeline steps ---------------------------------------------

    def _run_scanner(self, repo_path, project_key, token):
        """Invoke sonar-scanner. Returns None on success, ToolRunResult on error."""
        cmd = [
            self.sonar_scanner_path,
            f"-Dsonar.projectKey={project_key}",
            # `projectBaseDir` is what the scanner uses as its anchor for
            # everything else; without it the scanner treats its CWD as
            # the base, which is the runserver's directory — completely
            # the wrong place. With it set, `sonar.sources=.` (relative)
            # then finds the actual source files.
            f"-Dsonar.projectBaseDir={repo_path}",
            "-Dsonar.sources=.",
            f"-Dsonar.host.url={self.sonar_host}",
            f"-Dsonar.token={token}",
            # Keep the scanner's temp dir inside the source dir so any
            # cleanup we do on the source dir takes it with us.
            f"-Dsonar.working.directory={os.path.join(repo_path, '.scannerwork')}",
            # Java analysis normally requires compiled .class files;
            # without this property Sonar refuses to scan a project that
            # has any .java sources. Pointing binaries at the source
            # dir is the standard "we don't compile" workaround — it
            # disables the bytecode-dependent rules but lets the Java
            # source-level rules run anyway.
            "-Dsonar.java.binaries=.",
        ]
        # Pre-check: subprocess.run raises FileNotFoundError for both
        # "executable missing" AND "cwd doesn't exist" — same exception,
        # very different fixes. Catch the cwd case explicitly so the
        # error message points at the right thing.
        if not os.path.isdir(repo_path):
            return self._fail(
                f"Source directory disappeared before scanner could run: {repo_path}"
            )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.scanner_timeout,
                cwd=repo_path,
            )
        except subprocess.TimeoutExpired:
            return self._fail(
                f"sonar-scanner timed out after {self.scanner_timeout}s"
            )
        except FileNotFoundError as exc:
            # Print the actual filename Python tried to exec so we can
            # tell whether it's sonar-scanner itself, the node interpreter
            # behind the npm scanner, or something else.
            return self._fail(
                f"Could not start sonar-scanner ({exc.__class__.__name__}: "
                f"{exc}). Path tried: {self.sonar_scanner_path!r}. "
                f"Source dir: {repo_path!r}."
            )

        if result.returncode != 0:
            combined = (
                (result.stdout or "")
                + ("\n--- stderr ---\n" + result.stderr if result.stderr else "")
            )
            # Always log the full output to the runserver console so we
            # have a complete record regardless of what slice we show
            # in the UI.
            logger.error(
                f"sonar_scanner_failed key={project_key} "
                f"returncode={result.returncode} full_output={combined!r}"
            )

            # Find the actual diagnostic — Sonar prints `[ERROR]` lines
            # for the real cause, and a Java stack trace far below it.
            # Show 3 lines before + the [ERROR] line + 10 after, so the
            # cause is visible without 50 lines of stack frames.
            lines = combined.splitlines()
            error_idx = next(
                (i for i, l in enumerate(lines) if "[ERROR]" in l), None
            )
            if error_idx is not None:
                snippet = lines[max(0, error_idx - 3): error_idx + 11]
            else:
                # Fallback — last 50 lines is much better than 20 for
                # capturing exception text above stack frames.
                snippet = lines[-50:]
            return self._fail(
                f"sonar-scanner exited {result.returncode}:\n"
                + "\n".join(snippet)[:3000]
            )

        # Surface the scanner summary in the runserver log so a "0
        # findings in 7s" failure mode is debuggable from the console
        # without rerunning. Just the last few lines — the full stdout
        # is huge.
        tail = "\n".join((result.stdout or "").strip().splitlines()[-15:])
        logger.info(f"sonar_scanner_summary key={project_key} tail={tail!r}")
        return None

    def _wait_for_processing(self, project_key, token):
        """Poll the compute-engine task queue until the server finishes
        processing this project's analysis. Returns None on success."""
        deadline = time.monotonic() + self.poll_timeout
        url = f"{self.sonar_host}/api/ce/component"
        while time.monotonic() < deadline:
            try:
                response = requests.get(
                    url,
                    params={"component": project_key},
                    auth=(token, ""),
                    timeout=10,
                )
            except requests.exceptions.RequestException as exc:
                return self._fail(f"SonarQube unreachable: {exc}")

            if response.status_code != 200:
                return self._fail(
                    f"SonarQube /api/ce/component returned "
                    f"{response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            current = data.get("current") or {}
            status = current.get("status")
            queue = data.get("queue", [])
            if status == "SUCCESS" and not queue:
                return None
            if status in {"FAILED", "CANCELED"}:
                return self._fail(
                    f"SonarQube analysis ended with status {status}: "
                    f"{current.get('errorMessage') or '(no error message)'}"
                )
            time.sleep(self.poll_interval)

        return self._fail(
            f"Timed out waiting for SonarQube analysis after "
            f"{self.poll_timeout}s"
        )

    def _fetch_issues(self, project_key, token):
        """Pull every finding Sonar has for this project — both regular
        issues (`/api/issues/search`) and security hotspots
        (`/api/hotspots/search`). Hotspots got promoted to a separate
        API in modern SonarQube; for a security-focused platform we
        want both. Each API paginates 500-at-a-time; Sonar caps any
        single query at 10,000 results."""
        import json as _json

        # --- Issues (VULNERABILITY by default; user can broaden via
        # SAST_SONAR_ISSUE_TYPES) -----------------------------------
        all_issues = []
        page_size = 500
        max_pages = 20  # 20 * 500 = 10,000 — Sonar's hard ceiling.
        for page in range(1, max_pages + 1):
            params = {
                "componentKeys": project_key,
                "p": page,
                "ps": page_size,
                "resolved": "false",
            }
            if self.issue_types:
                params["types"] = self.issue_types
            try:
                response = requests.get(
                    f"{self.sonar_host}/api/issues/search",
                    params=params,
                    auth=(token, ""),
                    timeout=30,
                )
            except requests.exceptions.RequestException as exc:
                return self._fail(f"SonarQube unreachable: {exc}")

            if response.status_code != 200:
                return self._fail(
                    f"SonarQube /api/issues/search returned "
                    f"{response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            issues = data.get("issues", [])
            all_issues.extend(issues)

            total = data.get("total", 0)
            if len(all_issues) >= total or len(issues) < page_size:
                break
        else:
            # Loop completed without break — we hit max_pages.
            logger.warning(
                f"sonar_issues_truncated key={project_key} "
                f"fetched={len(all_issues)} total={data.get('total')}"
            )

        # --- Security hotspots (separate API in modern Sonar) -----
        # Best-effort: any failure (older Sonar without the endpoint,
        # network blip, mocked requests running out of responses in
        # tests, anything) just stops hotspot collection without
        # killing the scan. The issues we already have are kept.
        try:
            for page in range(1, max_pages + 1):
                response = requests.get(
                    f"{self.sonar_host}/api/hotspots/search",
                    params={
                        "projectKey": project_key,
                        "p": page,
                        "ps": page_size,
                        "status": "TO_REVIEW",
                    },
                    auth=(token, ""),
                    timeout=30,
                )
                if response.status_code != 200:
                    logger.info(
                        f"sonar_hotspots_unavailable key={project_key} "
                        f"status={response.status_code}"
                    )
                    break

                data = response.json()
                hotspots = data.get("hotspots", [])
                for hotspot in hotspots:
                    all_issues.append(self._hotspot_to_issue(hotspot))

                paging = data.get("paging", {})
                total = paging.get("total", 0)
                if len(hotspots) < page_size or len(hotspots) == 0 or page * page_size >= total:
                    break
        except Exception as exc:
            logger.info(
                f"sonar_hotspots_skipped key={project_key} reason={exc!r}"
            )

        # The downstream parser expects Sonar's response shape, so
        # reassemble one synthetic envelope around the merged findings.
        combined = _json.dumps({"issues": all_issues, "total": len(all_issues)})
        return ToolRunResult(success=True, raw_output=combined, exit_code=0)

    @staticmethod
    def _hotspot_to_issue(hotspot):
        """Reshape a `/api/hotspots/search` entry into the same dict
        shape `/api/issues/search` returns, so SonarParser handles
        both uniformly. The interesting fields:

        - vulnerabilityProbability → severity (HIGH / MEDIUM / LOW)
        - securityCategory → human-readable tag for the category
        """
        prob = (hotspot.get("vulnerabilityProbability") or "").upper()
        severity = {"HIGH": "CRITICAL", "MEDIUM": "MAJOR", "LOW": "MINOR"}.get(
            prob, "MAJOR"
        )
        return {
            "key": hotspot.get("key", ""),
            "rule": hotspot.get("ruleKey", ""),
            "component": hotspot.get("component", ""),
            "line": hotspot.get("line", 0),
            "message": hotspot.get("message", ""),
            "severity": severity,
            "type": "SECURITY_HOTSPOT",
            "tags": [],
        }

    # ----- helpers ----------------------------------------------------

    @staticmethod
    def _fail(message):
        return ToolRunResult(
            success=False,
            raw_output="",
            error_message=message,
            exit_code=-1,
        )
