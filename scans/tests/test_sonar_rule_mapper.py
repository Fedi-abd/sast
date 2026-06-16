"""Tests for the SonarRuleMapper fallback path.

The mapper is the second stage of MappingService's lookup chain.
These tests pin its contract: language-prefix stripping, the
0.7 confidence score for hits, and the UNMAPPED+0.0 contract for
misses, without depending on MappingService itself.
"""
import json
import os
import tempfile

from django.test import SimpleTestCase

from scans.mappings.sonar_rule_mapper import SonarRuleMapper


class SonarRuleMapperTests(SimpleTestCase):
    def setUp(self):
        self.mapper = SonarRuleMapper()

    def test_known_rule_maps_to_owasp_with_fallback_confidence(self):
        category, confidence = self.mapper.map_rule("java:S2076")
        self.assertEqual(category, "A1:2017-Injection")
        self.assertEqual(confidence, 0.7)

    def test_language_prefix_is_stripped(self):
        # python:S2076, java:S2076, javascript:S2076 should all hit
        # the same row in the table.
        for prefix in ("python", "java", "javascript", "typescript", "php"):
            with self.subTest(prefix=prefix):
                category, _ = self.mapper.map_rule(f"{prefix}:S2076")
                self.assertEqual(category, "A1:2017-Injection")

    def test_bare_rule_id_without_prefix_is_accepted(self):
        category, confidence = self.mapper.map_rule("S5135")
        self.assertEqual(category, "A8:2017-Insecure Deserialization")
        self.assertEqual(confidence, 0.7)

    def test_unknown_rule_returns_unmapped_zero_confidence(self):
        category, confidence = self.mapper.map_rule("java:S99999")
        self.assertEqual(category, "UNMAPPED")
        self.assertEqual(confidence, 0.0)

    def test_empty_string_returns_unmapped(self):
        category, confidence = self.mapper.map_rule("")
        self.assertEqual(category, "UNMAPPED")
        self.assertEqual(confidence, 0.0)

    def test_comment_key_is_excluded_from_lookups(self):
        # The JSON carries a `_comment` key for human readers. It must
        # not show up as a valid rule mapping.
        category, _ = self.mapper.map_rule("_comment")
        self.assertEqual(category, "UNMAPPED")

    def test_xss_rules_map_to_a7(self):
        # Cross-check that two distinct XSS rules both land on A7,
        # protects against accidentally diverging mappings.
        for rule in ("javascript:S5131", "java:S5247"):
            with self.subTest(rule=rule):
                category, _ = self.mapper.map_rule(rule)
                self.assertEqual(
                    category, "A7:2017-Cross-Site Scripting (XSS)"
                )

    def test_custom_mapping_file_is_loaded(self):
        # Confidence-boost test: confirm the mapper isn't hard-coding
        # the production table.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump({"S9999": "A1:2017-Injection"}, f)
            tmp_path = f.name

        try:
            custom = SonarRuleMapper(mapping_file=tmp_path)
            category, confidence = custom.map_rule("S9999")
            self.assertEqual(category, "A1:2017-Injection")
            self.assertEqual(confidence, 0.7)
            # Production rule shouldn't be visible to the custom mapper.
            category2, _ = custom.map_rule("S2076")
            self.assertEqual(category2, "UNMAPPED")
        finally:
            os.unlink(tmp_path)
