"""OWASP mapping orchestration.

`MappingService` is the single entry point views and tests use to turn
parsed findings into OWASP-categorized ones. It chains two mappers:

  1. **CWE mapper** (authoritative). Most findings (all Semgrep
     output, the majority of SonarQube issues) arrive with a CWE tag.
     `CWEMapper` looks it up against the OWASP 2017 table and returns
     a category with confidence 1.0.

  2. **Sonar rule fallback** (heuristic, curated). When step 1 yields
     UNMAPPED *and* the finding came from SonarQube, try mapping the
     bare Sonar rule number (`S2076`, etc.) directly to an OWASP
     category. This catches Security Hotspots and CWE-less issues
     from older Sonar projects. Confidence drops to 0.7 to mark the
     mapping as heuristic rather than authoritative.

The fallback is gated on `tool == 'sonarqube'` because Semgrep's
`rule_id` format is unrelated (`python.lang.security.audit...`), so a
lookup against the Sonar table on a Semgrep finding would always
miss, just adding a useless dict access on the hot path.
"""
from typing import Any, Dict, List

from scans.mappings.mapper import CWEMapper
from scans.mappings.sonar_rule_mapper import SonarRuleMapper


class MappingService:
    """Map findings to OWASP categories and compute rollup statistics."""

    def __init__(self):
        self.mapper = CWEMapper()
        self.sonar_rule_mapper = SonarRuleMapper()

    def map_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Attach `owasp_category` and `confidence_score` to a finding.

        Mutates `finding` in place and returns it. The two-step lookup
        is described in the module docstring above.

        Args:
            finding: Finding dict from a parser. Required keys: none
                strictly, but `cwe_id` drives step 1 and `tool` +
                `rule_id` drive step 2. Missing fields are treated as
                empty strings.

        Returns:
            The same dict with `owasp_category` and `confidence_score`
            set. Unmapped findings get ("UNMAPPED", 0.0).
        """
        cwe_id = finding.get('cwe_id', '')
        owasp_category, confidence = self.mapper.map_cwe_to_owasp(cwe_id)

        # Step 2: Sonar rule fallback. Only for SonarQube findings that
        # the CWE step left UNMAPPED.
        if owasp_category == "UNMAPPED" and finding.get('tool') == 'sonarqube':
            rule_id = finding.get('rule_id', '')
            owasp_category, confidence = self.sonar_rule_mapper.map_rule(rule_id)

        finding['owasp_category'] = owasp_category
        finding['confidence_score'] = confidence

        return finding

    def map_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply `map_finding` to a list of findings."""
        return [self.map_finding(f) for f in findings]

    def compute_stats(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate counts used by the scan-detail rollup cards.

        Args:
            findings: Mapped findings (output of `map_findings`).

        Returns:
            Dict with:
              - total: total finding count.
              - mapped: count of findings with a real OWASP category.
              - unmapped: count of findings still UNMAPPED.
              - mapping_rate: mapped / total * 100 (or 0 if total == 0).
              - by_owasp: {category: count}.
              - by_severity: {severity: count}.
        """
        total = len(findings)
        mapped = sum(1 for f in findings if f.get('owasp_category') != 'UNMAPPED')
        unmapped = total - mapped

        by_owasp: Dict[str, int] = {}
        for f in findings:
            category = f.get('owasp_category', 'UNMAPPED')
            by_owasp[category] = by_owasp.get(category, 0) + 1

        by_severity: Dict[str, int] = {}
        for f in findings:
            severity = f.get('severity', 'UNKNOWN')
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            'total': total,
            'mapped': mapped,
            'unmapped': unmapped,
            'mapping_rate': (mapped / total * 100) if total > 0 else 0.0,
            'by_owasp': by_owasp,
            'by_severity': by_severity,
        }
