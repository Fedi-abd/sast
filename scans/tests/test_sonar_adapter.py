"""Tests for the Sprint-3 SonarAdapter rewrite.

The adapter now drives sonar-scanner directly + polls SonarQube's task
queue + fetches issues. We mock both `subprocess.run` (the scanner) and
`requests.get` (the API calls) so the test suite never needs a real
SonarQube instance running.
"""
from unittest import mock

from django.test import SimpleTestCase

from scans.tools.sonar_adapter import SonarAdapter


def _ok_scanner():
    """A successful sonar-scanner subprocess result."""
    return mock.Mock(returncode=0, stdout="", stderr="")


def _ok_status_response(status="SUCCESS"):
    response = mock.Mock(status_code=200)
    response.json.return_value = {"current": {"status": status}, "queue": []}
    return response


def _ok_issues_response(payload='{"issues": []}'):
    import json as _json
    response = mock.Mock(status_code=200, text=payload)
    response.json.return_value = _json.loads(payload)
    return response


class SonarAdapterTests(SimpleTestCase):
    def setUp(self):
        # Tiny poll values so the test suite stays fast.
        self.adapter = SonarAdapter(
            sonar_host="http://localhost:9000",
            sonar_token="t",
            sonar_scanner_path="/usr/bin/sonar-scanner",
            poll_interval=0.001,
            poll_timeout=1.0,
        )
        # Synthetic paths in these tests don't exist on the real
        # filesystem; patch the cwd-exists pre-check globally so each
        # test can focus on the behavior it actually cares about.
        # Tests that explicitly want the "missing source dir" path
        # still patch isdir themselves.
        self._isdir_patch = mock.patch(
            "scans.tools.sonar_adapter.os.path.isdir", return_value=True
        )
        self._isdir_patch.start()
        self.addCleanup(self._isdir_patch.stop)

    def test_missing_token_fails_clearly(self):
        adapter = SonarAdapter(sonar_token=None)
        result = adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("SONAR_TOKEN", result.error_message)

    def test_missing_project_key_fails_clearly(self):
        result = self.adapter.run("/repo", {})
        self.assertFalse(result.success)
        self.assertIn("project_key", result.error_message)

    def test_happy_path_runs_scanner_then_polls_then_fetches(self):
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ) as run_mock, mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            side_effect=[_ok_status_response(), _ok_issues_response()],
        ) as get_mock:
            result = self.adapter.run("/repo", {"project_key": "k"})

        self.assertTrue(result.success, result.error_message)
        # Pagination wraps the per-page response in a synthesized
        # envelope; assert the shape, not the exact bytes.
        import json as _json
        merged = _json.loads(result.raw_output)
        self.assertEqual(merged["issues"], [])

        # Scanner ran with the right project key + token.
        scanner_args = run_mock.call_args.args[0]
        self.assertIn("-Dsonar.projectKey=k", scanner_args)
        self.assertIn("-Dsonar.token=t", scanner_args)

        # Three HTTP calls: status poll, issues fetch, hotspots fetch.
        # (Hotspots endpoint isn't mocked, so the call raises StopIteration
        # internally and the adapter swallows it — counted but harmless.)
        self.assertEqual(get_mock.call_count, 3)
        self.assertIn("/api/ce/component", get_mock.call_args_list[0].args[0])
        self.assertIn("/api/issues/search", get_mock.call_args_list[1].args[0])
        self.assertIn("/api/hotspots/search", get_mock.call_args_list[2].args[0])

    def test_scanner_nonzero_exit_surfaces_stderr(self):
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="auth failed"),
        ):
            result = self.adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("auth failed", result.error_message)
        self.assertIn("exited 1", result.error_message)

    def test_scanner_missing_binary_fails_clearly(self):
        # Stub os.path.isdir so the cwd pre-check passes — we want this
        # test to exercise the FileNotFoundError-from-subprocess path.
        with mock.patch(
            "scans.tools.sonar_adapter.os.path.isdir", return_value=True
        ), mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            side_effect=FileNotFoundError("[Errno 2] No such file: 'sonar-scanner'"),
        ):
            result = self.adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("Could not start sonar-scanner", result.error_message)
        self.assertIn("sonar-scanner", result.error_message)

    def test_missing_source_dir_fails_clearly(self):
        # If PathResolver returns a path that doesn't exist (or got
        # cleaned up too early), the message should say so explicitly
        # rather than blame the executable.
        with mock.patch(
            "scans.tools.sonar_adapter.os.path.isdir", return_value=False
        ):
            result = self.adapter.run("/nope", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("Source directory disappeared", result.error_message)

    def test_polls_until_status_becomes_success(self):
        responses = [
            _ok_status_response("PENDING"),
            _ok_status_response("IN_PROGRESS"),
            _ok_status_response("SUCCESS"),
            _ok_issues_response(),
        ]
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            side_effect=responses,
        ) as get_mock:
            result = self.adapter.run("/repo", {"project_key": "k"})
        self.assertTrue(result.success, result.error_message)
        # 3 polls + 1 issues fetch + 1 hotspots fetch (the hotspots
        # call has no mock so raises StopIteration, which the adapter
        # silently absorbs).
        self.assertEqual(get_mock.call_count, 5)

    def test_failed_status_surfaces_error(self):
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            return_value=mock.Mock(
                status_code=200,
                json=lambda: {
                    "current": {"status": "FAILED", "errorMessage": "out of disk"},
                    "queue": [],
                },
            ),
        ):
            result = self.adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("FAILED", result.error_message)
        self.assertIn("out of disk", result.error_message)

    def test_poll_timeout_fails_clearly(self):
        # SonarQube keeps reporting IN_PROGRESS forever; we should give up.
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            return_value=_ok_status_response("IN_PROGRESS"),
        ):
            adapter = SonarAdapter(
                sonar_token="t",
                sonar_scanner_path="/usr/bin/sonar-scanner",
                poll_interval=0.001,
                poll_timeout=0.05,  # 50ms — guaranteed to time out
            )
            result = adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("Timed out", result.error_message)

    def test_paginates_until_all_issues_fetched(self):
        # First /api/issues/search call returns 500 issues + total=750.
        # Adapter should call again with p=2 to fetch the remaining 250.
        page1 = mock.Mock(status_code=200, text="")
        page1.json.return_value = {
            "issues": [{"key": f"a{i}"} for i in range(500)],
            "total": 750,
        }
        page2 = mock.Mock(status_code=200, text="")
        page2.json.return_value = {
            "issues": [{"key": f"b{i}"} for i in range(250)],
            "total": 750,
        }
        responses = [_ok_status_response(), page1, page2]
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            side_effect=responses,
        ) as get_mock:
            result = self.adapter.run("/repo", {"project_key": "k"})

        self.assertTrue(result.success, result.error_message)
        # Pages 1 and 2 against /api/issues/search, then page 1 against
        # the (unmocked) /api/hotspots/search which fails silently.
        # Verify both issue pages were requested.
        issues_pages = [
            c.kwargs.get("params", {}).get("p")
            for c in get_mock.call_args_list[1:]
            if "/api/issues/search" in c.args[0]
        ]
        self.assertEqual(issues_pages, [1, 2])
        # And the synthesized payload contains all 750 issues.
        import json as _json
        merged = _json.loads(result.raw_output)
        self.assertEqual(len(merged["issues"]), 750)

    def test_hotspots_merged_into_issues(self):
        # Issues endpoint returns nothing; hotspots endpoint returns
        # two findings. Verify they get reshaped + merged.
        empty_issues = mock.Mock(status_code=200, text="")
        empty_issues.json.return_value = {"issues": [], "total": 0}
        hotspots_response = mock.Mock(status_code=200, text="")
        hotspots_response.json.return_value = {
            "hotspots": [
                {
                    "key": "h1",
                    "ruleKey": "java:S2076",
                    "component": "p:src/Main.java",
                    "line": 42,
                    "message": "Possible command injection",
                    "vulnerabilityProbability": "HIGH",
                },
                {
                    "key": "h2",
                    "ruleKey": "java:S5042",
                    "component": "p:src/Other.java",
                    "line": 7,
                    "message": "Zip slip risk",
                    "vulnerabilityProbability": "MEDIUM",
                },
            ],
            "paging": {"total": 2},
        }
        empty_hotspots = mock.Mock(status_code=200, text="")
        empty_hotspots.json.return_value = {"hotspots": [], "paging": {"total": 2}}

        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            side_effect=[
                _ok_status_response(),     # CE component poll
                empty_issues,              # /api/issues/search p=1
                hotspots_response,         # /api/hotspots/search p=1
                empty_hotspots,            # /api/hotspots/search p=2 (paging stop)
            ],
        ):
            result = self.adapter.run("/repo", {"project_key": "k"})

        self.assertTrue(result.success, result.error_message)
        import json as _json
        merged = _json.loads(result.raw_output)
        self.assertEqual(len(merged["issues"]), 2)
        # Both should be reshaped to look like /api/issues/search results.
        h1 = merged["issues"][0]
        self.assertEqual(h1["rule"], "java:S2076")
        self.assertEqual(h1["type"], "SECURITY_HOTSPOT")
        self.assertEqual(h1["severity"], "CRITICAL")  # HIGH probability → CRITICAL
        self.assertEqual(merged["issues"][1]["severity"], "MAJOR")  # MEDIUM → MAJOR

    def test_unreachable_sonar_during_poll_fails_clearly(self):
        import requests as _requests
        with mock.patch(
            "scans.tools.sonar_adapter.subprocess.run",
            return_value=_ok_scanner(),
        ), mock.patch(
            "scans.tools.sonar_adapter.requests.get",
            side_effect=_requests.exceptions.ConnectionError("refused"),
        ):
            result = self.adapter.run("/repo", {"project_key": "k"})
        self.assertFalse(result.success)
        self.assertIn("SonarQube unreachable", result.error_message)
