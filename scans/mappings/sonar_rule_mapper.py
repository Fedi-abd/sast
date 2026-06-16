"""Sonar `rule_id` -> OWASP 2017 fallback mapper.

The primary mapping path is CWE -> OWASP (see `cwe_to_owasp_2017.json`).
SonarQube tags many issues with CWE numbers, but a meaningful fraction
of security findings (especially Security Hotspots and rules from
older Sonar projects) arrive without a CWE tag, leaving the CWE
mapper to return UNMAPPED.

This module covers that gap by mapping Sonar's own rule numbers
(`Sxxxx`) directly to OWASP categories. Maintained as a curated
JSON table next to the CWE map, hot-reloadable by editing the file.

Language prefix handling: SonarQube emits rule IDs like
`python:S2076`, `java:S2076`, `javascript:S2076`. Sonar uses the same
`Sxxxx` number across languages for the same vulnerability concept,
so the mapper strips the language prefix and looks up the bare
number.

Confidence score: a successful Sonar-rule lookup returns confidence
0.7, clearly below the CWE mapping's 1.0 (CWE -> OWASP is the
industry-standard authoritative mapping; this table is hand-curated
heuristic).
"""
import json
import os
from typing import Optional


class SonarRuleMapper:
    """Map a SonarQube `rule_id` to an OWASP 2017 category."""

    # 0.7 = heuristic curation; CWE lookup is 1.0.
    CONFIDENCE = 0.7

    def __init__(self, mapping_file: Optional[str] = None):
        """Load the JSON map from disk.

        Args:
            mapping_file: Optional override for the JSON path. Defaults
                to `sonar_rule_to_owasp.json` next to this file.
        """
        if mapping_file is None:
            mapping_file = os.path.join(
                os.path.dirname(__file__),
                'sonar_rule_to_owasp.json'
            )

        with open(mapping_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # The JSON carries a `_comment` key for human readers; strip it
        # so it doesn't show up as a real rule mapping. Mutating once at
        # load time keeps the hot path (`map_rule`) simple.
        self.mapping = {k: v for k, v in raw.items() if not k.startswith('_')}

    def map_rule(self, rule_id: str) -> tuple[str, float]:
        """Return (owasp_category, confidence_score) for a Sonar rule.

        Args:
            rule_id: The SonarQube rule identifier as emitted by the
                API. Accepted forms include `python:S2076`, `java:S2076`,
                `S2076`, or any other `<lang>:Sxxxx` shape. Case-sensitive
                on the S-number (Sonar uses upper-case S).

        Returns:
            Tuple of (owasp_category, confidence). Returns
            ("UNMAPPED", 0.0) when the rule isn't in the table, same
            contract as CWEMapper, so MappingService can fall through
            uniformly.
        """
        if not rule_id:
            return "UNMAPPED", 0.0

        key = self._normalize(rule_id)
        if key in self.mapping:
            return self.mapping[key], self.CONFIDENCE

        return "UNMAPPED", 0.0

    @staticmethod
    def _normalize(rule_id: str) -> str:
        """Strip the language prefix from a Sonar rule_id.

        `python:S2076` -> `S2076`. `S2076` -> `S2076`. Anything without
        a colon is returned as-is so unexpected formats still get a
        clean lookup attempt rather than a normalization error.
        """
        rule_id = rule_id.strip()
        if ':' in rule_id:
            return rule_id.split(':', 1)[1].strip()
        return rule_id
