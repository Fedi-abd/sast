"""Tests for SonarParser — covers the cases the bundled Sprint-1 tests miss."""
import json
from django.test import SimpleTestCase
from scans.tools.sonar_parser import SonarParser


class SonarParserTests(SimpleTestCase):
    def setUp(self):
        self.parser = SonarParser()

    def _issue(self, **overrides):
        base = {
            "rule": "java:S1234",
            "message": "Example issue",
            "component": "myproj:src/Main.java",
            "line": 12,
            "severity": "MAJOR",
            "tags": [],
        }
        base.update(overrides)
        return base

    def _wrap(self, *issues):
        return json.dumps({"issues": list(issues)})

    def test_extracts_basic_fields(self):
        out = self.parser.parse(self._wrap(self._issue()))
        self.assertEqual(len(out), 1)
        f = out[0]
        self.assertEqual(f["tool"], "sonarqube")
        self.assertEqual(f["rule_id"], "java:S1234")
        self.assertEqual(f["file_path"], "src/Main.java")
        self.assertEqual(f["line_number"], 12)
        self.assertEqual(f["severity"], "MEDIUM")  # MAJOR -> MEDIUM
        self.assertEqual(f["message"], "Example issue")

    def test_severity_mapping(self):
        cases = [
            ("BLOCKER", "HIGH"),
            ("CRITICAL", "HIGH"),
            ("MAJOR", "MEDIUM"),
            ("MINOR", "LOW"),
            ("INFO", "LOW"),
            ("WHATEVER", "LOW"),  # unknown falls through
        ]
        for sonar_sev, expected in cases:
            with self.subTest(sonar_sev=sonar_sev):
                out = self.parser.parse(self._wrap(self._issue(severity=sonar_sev)))
                self.assertEqual(out[0]["severity"], expected)

    def test_component_with_no_colon_keeps_raw_value(self):
        out = self.parser.parse(self._wrap(self._issue(component="Main.java")))
        self.assertEqual(out[0]["file_path"], "Main.java")

    def test_cwe_tag_with_dash(self):
        out = self.parser.parse(self._wrap(self._issue(tags=["cwe-79"])))
        self.assertEqual(out[0]["cwe_id"], "CWE-79")

    def test_cwe_tag_without_dash(self):
        # The Sprint-1 audit fix made the parser accept both forms.
        out = self.parser.parse(self._wrap(self._issue(tags=["cwe79"])))
        self.assertEqual(out[0]["cwe_id"], "CWE-79")

    def test_bare_cwe_tag_yields_nothing(self):
        out = self.parser.parse(self._wrap(self._issue(tags=["cwe", "owasp-a1"])))
        self.assertEqual(out[0]["cwe_id"], "")

    def test_multiple_cwe_tags_returns_first_numeric_one(self):
        out = self.parser.parse(self._wrap(self._issue(tags=["cwe", "cwe-79", "cwe-89"])))
        self.assertEqual(out[0]["cwe_id"], "CWE-79")

    def test_empty_issues_list(self):
        self.assertEqual(self.parser.parse(json.dumps({"issues": []})), [])

    def test_missing_issues_key(self):
        self.assertEqual(self.parser.parse(json.dumps({})), [])

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.parser.parse("not json at all")
