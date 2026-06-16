"""Tests for MappingService.compute_stats: the per-scan rollup used by views."""
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

    def test_sonar_finding_falls_back_to_rule_mapper_when_cwe_missing(self):
        # No CWE tag, but the SonarQube rule_id is in the curated table.
        # MappingService should fall through to the SonarRuleMapper and
        # produce a real category with the fallback confidence.
        finding = {
            "tool": "sonarqube",
            "rule_id": "java:S2076",
            "cwe_id": "",
            "severity": "HIGH",
        }
        result = self.service.map_finding(finding)
        self.assertEqual(result["owasp_category"], "A1:2017-Injection")
        self.assertEqual(result["confidence_score"], 0.7)

    def test_cwe_match_takes_precedence_over_sonar_rule(self):
        # A Sonar finding with both a valid CWE and a rule_id in the
        # fallback table must use the CWE path (confidence 1.0). The
        # fallback only kicks in when CWE returns UNMAPPED.
        finding = {
            "tool": "sonarqube",
            "rule_id": "java:S2076",  # would map to A1 at 0.7
            "cwe_id": "CWE-79",       # maps to A7 at 1.0
            "severity": "HIGH",
        }
        result = self.service.map_finding(finding)
        self.assertEqual(
            result["owasp_category"], "A7:2017-Cross-Site Scripting (XSS)"
        )
        self.assertEqual(result["confidence_score"], 1.0)

    def test_semgrep_finding_does_not_trigger_sonar_fallback(self):
        # The Sonar rule fallback is gated on tool == 'sonarqube'.
        # A Semgrep rule_id with the literal text 'S2076' must NOT
        # accidentally pick up the Sonar mapping.
        finding = {
            "tool": "semgrep",
            "rule_id": "S2076",  # would hit the table if not gated
            "cwe_id": "",
            "severity": "HIGH",
        }
        result = self.service.map_finding(finding)
        self.assertEqual(result["owasp_category"], "UNMAPPED")
        self.assertEqual(result["confidence_score"], 0.0)
