"""Tests for CWEMapper, the heart of the security reasoning layer.

These lock in two things:
  1. CWE input normalization handles the noisy formats real tools emit.
  2. All ten OWASP 2017 categories remain reachable from the bundled JSON.
"""
import json
import os
from django.test import SimpleTestCase
from scans.mappings.mapper import CWEMapper


class CWEMapperNormalizationTests(SimpleTestCase):
    def setUp(self):
        self.mapper = CWEMapper()

    def test_dashed_uppercase(self):
        cat, conf = self.mapper.map_cwe_to_owasp("CWE-79")
        self.assertEqual(cat, "A7:2017-Cross-Site Scripting (XSS)")
        self.assertEqual(conf, 1.0)

    def test_dashed_lowercase(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("cwe-79")[0],
                         "A7:2017-Cross-Site Scripting (XSS)")

    def test_just_a_number(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("79")[0],
                         "A7:2017-Cross-Site Scripting (XSS)")

    def test_dashless_form(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("CWE79")[0],
                         "A7:2017-Cross-Site Scripting (XSS)")

    def test_with_description_after_colon(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("CWE-79: XSS")[0],
                         "A7:2017-Cross-Site Scripting (XSS)")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("  cwe-89  ")[0],
                         "A1:2017-Injection")

    def test_empty_input_returns_unmapped(self):
        cat, conf = self.mapper.map_cwe_to_owasp("")
        self.assertEqual(cat, "UNMAPPED")
        self.assertEqual(conf, 0.0)

    def test_unknown_cwe_returns_unmapped(self):
        cat, conf = self.mapper.map_cwe_to_owasp("CWE-99999")
        self.assertEqual(cat, "UNMAPPED")
        self.assertEqual(conf, 0.0)

    def test_garbage_input_returns_unmapped(self):
        self.assertEqual(self.mapper.map_cwe_to_owasp("CWE-NotANumber")[0], "UNMAPPED")


class OWASP2017CoverageTests(SimpleTestCase):
    """The platform's stated priority: every OWASP 2017 category must
    be reachable from the bundled CWE table."""

    EXPECTED_CATEGORIES = {
        "A1:2017-Injection",
        "A2:2017-Broken Authentication",
        "A3:2017-Sensitive Data Exposure",
        "A4:2017-XML External Entities (XXE)",
        "A5:2017-Broken Access Control",
        "A6:2017-Security Misconfiguration",
        "A7:2017-Cross-Site Scripting (XSS)",
        "A8:2017-Insecure Deserialization",
        "A9:2017-Using Components with Known Vulnerabilities",
        "A10:2017-Insufficient Logging & Monitoring",
    }

    def test_all_ten_categories_present(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "mappings", "cwe_to_owasp_2017.json"
        )
        with open(path) as f:
            mapping = json.load(f)
        present = set(mapping.values())
        missing = self.EXPECTED_CATEGORIES - present
        self.assertFalse(missing, f"Missing OWASP 2017 categories: {missing}")
