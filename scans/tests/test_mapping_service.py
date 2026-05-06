"""Tests for MappingService.compute_stats — the per-scan rollup used by views."""
from django.test import SimpleTestCase
from scans.services.mapping_service import MappingService


class MappingServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = MappingService()

    def test_empty_input_does_not_divide_by_zero(self):
        stats = self.service.compute_stats([])
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["mapped"], 0)
        self.assertEqual(stats["unmapped"], 0)
        self.assertEqual(stats["mapping_rate"], 0.0)
        self.assertEqual(stats["by_owasp"], {})
        self.assertEqual(stats["by_severity"], {})

    def test_mapping_rate_is_percentage(self):
        findings = [
            {"cwe_id": "CWE-79", "severity": "HIGH"},
            {"cwe_id": "CWE-89", "severity": "HIGH"},
            {"cwe_id": "", "severity": "LOW"},  # unmapped
            {"cwe_id": "CWE-99999", "severity": "LOW"},  # unmapped
        ]
        mapped = self.service.map_findings(findings)
        stats = self.service.compute_stats(mapped)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["mapped"], 2)
        self.assertEqual(stats["unmapped"], 2)
        self.assertEqual(stats["mapping_rate"], 50.0)

    def test_by_severity_and_by_owasp_counts(self):
        findings = self.service.map_findings([
            {"cwe_id": "CWE-79", "severity": "HIGH"},
            {"cwe_id": "CWE-79", "severity": "MEDIUM"},
            {"cwe_id": "CWE-89", "severity": "HIGH"},
            {"cwe_id": "", "severity": "LOW"},
        ])
        stats = self.service.compute_stats(findings)
        self.assertEqual(stats["by_severity"]["HIGH"], 2)
        self.assertEqual(stats["by_severity"]["MEDIUM"], 1)
        self.assertEqual(stats["by_severity"]["LOW"], 1)
        self.assertEqual(stats["by_owasp"]["A7:2017-Cross-Site Scripting (XSS)"], 2)
        self.assertEqual(stats["by_owasp"]["A1:2017-Injection"], 1)
        self.assertEqual(stats["by_owasp"]["UNMAPPED"], 1)

    def test_map_finding_attaches_owasp_and_confidence(self):
        finding = {"cwe_id": "CWE-79", "severity": "HIGH"}
        result = self.service.map_finding(finding)
        self.assertEqual(result["owasp_category"], "A7:2017-Cross-Site Scripting (XSS)")
        self.assertEqual(result["confidence_score"], 1.0)

    def test_unmapped_finding_gets_zero_confidence(self):
        result = self.service.map_finding({"cwe_id": "CWE-99999", "severity": "LOW"})
        self.assertEqual(result["owasp_category"], "UNMAPPED")
        self.assertEqual(result["confidence_score"], 0.0)
