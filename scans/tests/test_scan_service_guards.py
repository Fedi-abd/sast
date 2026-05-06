"""Tests for the two Sprint-1 hardening guards in ScanService.

Revision 1: reject unsupported `tool` values before persisting a Scan row.
Revision 2: reject Finding.raw payloads that smuggle in the whole tool dump.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from scans.models import Project, Scan, Finding
from scans.services.scan_service import ScanService


class ToolValidationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="guard-user", password="x")
        self.project = Project.objects.create(
            name="Guard", repo_path="/tmp/x", owner=self.user
        )
        self.service = ScanService()

    def test_unsupported_tool_raises_before_creating_scan(self):
        before = Scan.objects.count()
        with self.assertRaises(ValueError) as cm:
            self.service.run_scan(self.project, tool="bandit")
        self.assertIn("Unsupported tool", str(cm.exception))
        # Critical: no Scan row was created.
        self.assertEqual(Scan.objects.count(), before)

    def test_supported_tools_pass_validation(self):
        # Just make sure semgrep / sonarqube pass the validation gate. We
        # short-circuit the adapter and the resolver so the test doesn't
        # actually shell out or touch the filesystem.
        from scans.services.path_resolver import ResolvedPath

        for tool in ("semgrep", "sonarqube"):
            with self.subTest(tool=tool):
                class _R:
                    success = True
                    raw_output = '{"results": [], "issues": []}'
                    error_message = None

                self.service._run_adapter = lambda t, r, c: _R()
                self.service.path_resolver.resolve = lambda project: ResolvedPath(
                    path="/tmp/x", cleanup=lambda: None,
                )
                result = self.service.run_scan(self.project, tool=tool)
                self.assertTrue(result["success"], result)


class FindingRawGuardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="raw-user", password="x")
        self.project = Project.objects.create(
            name="RawGuard", repo_path="/tmp/x", owner=self.user
        )
        self.service = ScanService()
        self.scan = Scan.objects.create(
            project=self.project, tool="semgrep", status="RUNNING"
        )

    def _finding(self, raw):
        return {
            "tool": "semgrep",
            "rule_id": "r",
            "severity": "LOW",
            "file_path": "a.py",
            "line_number": 1,
            "message": "m",
            "cwe_id": "",
            "raw": raw,
        }

    def test_dict_with_per_finding_node_is_accepted(self):
        f = self._finding({"check_id": "r", "path": "a.py", "start": {"line": 1}})
        objects = self.service._create_finding_objects(self.scan, [f])
        self.assertEqual(len(objects), 1)

    def test_full_semgrep_dump_is_rejected(self):
        # Smuggling the whole scan blob with a top-level 'results' key.
        f = self._finding({"results": [{"check_id": "r"}]})
        with self.assertRaises(ValueError) as cm:
            self.service._create_finding_objects(self.scan, [f])
        self.assertIn("full scan output", str(cm.exception))

    def test_full_sonar_dump_is_rejected(self):
        # Smuggling the whole Sonar response with a top-level 'issues' key.
        f = self._finding({"issues": [{"rule": "r"}]})
        with self.assertRaises(ValueError):
            self.service._create_finding_objects(self.scan, [f])

    def test_non_dict_raw_is_rejected(self):
        f = self._finding(["not", "a", "dict"])
        with self.assertRaises(ValueError) as cm:
            self.service._create_finding_objects(self.scan, [f])
        self.assertIn("must be a dict", str(cm.exception))
