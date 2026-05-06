from django.test import TestCase
from django.utils import timezone
from scans.models import Project, Scan, Finding
from scans.services.path_resolver import ResolvedPath
from scans.services.scan_service import ScanService

class FakeAdapterResult:
    def __init__(self, success, raw_output=None, error_message=None):
        self.success = success
        self.raw_output = raw_output
        self.error_message = error_message

from django.contrib.auth import get_user_model

class ScanServiceTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )

        self.project = Project.objects.create(
            name="TestProject",
            repo_path="/tmp/project",
            language="python",
            owner=self.user
        )

        self.service = ScanService()
        # Sprint 2: ScanService now goes through PathResolver. These
        # tests stub the adapter, so we also stub the resolver to avoid
        # the (correct) "path doesn't exist" error from local resolution.
        self.service.path_resolver.resolve = lambda project: ResolvedPath(
            path="/tmp/project", cleanup=lambda: None,
        )

    def test_successful_scan(self):
        adapter_json = """
        {
            "results": [
                {
                    "check_id": "test.rule",
                    "path": "file.py",
                    "start": {"line": 10},
                    "extra": {
                        "message": "Test message",
                        "metadata": {"cwe": "CWE-79"}
                    }
                }
            ]
        }
        """

        self.service._run_adapter = lambda tool, repo, config: FakeAdapterResult(
            success=True, raw_output=adapter_json
        )

        result = self.service.run_scan(self.project, tool="semgrep")

        self.assertTrue(result["success"])
        self.assertEqual(result["total_findings"], 1)

        scan = Scan.objects.get(id=result["scan_id"])
        self.assertEqual(scan.status, "SUCCESS")
        self.assertGreaterEqual(scan.duration_seconds, 0)

        findings = scan.findings.all()
        self.assertEqual(findings.count(), 1)
        self.assertEqual(findings.first().rule_id, "test.rule")

    def test_adapter_failure(self):
        self.service._run_adapter = lambda tool, repo, config: FakeAdapterResult(
            success=False, error_message="Tool crashed"
        )

        result = self.service.run_scan(self.project, tool="semgrep")

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Tool crashed")

        scan = Scan.objects.get(id=result["scan_id"])
        self.assertEqual(scan.status, "FAILED")

    def test_exception_in_pipeline(self):
        self.service._run_adapter = lambda tool, repo, config: FakeAdapterResult(
            success=True, raw_output="{}"
        )
        self.service._parse_results = lambda tool, raw: 1 / 0

        result = self.service.run_scan(self.project, tool="semgrep")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

        scan = Scan.objects.get(id=result["scan_id"])
        self.assertEqual(scan.status, "FAILED")