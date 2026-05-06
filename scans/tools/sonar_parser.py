import json
from typing import List, Dict, Any

class SonarParser:
    """Parse SonarQube API JSON into normalized findings"""
    
    def parse(self, raw_json: str) -> List[Dict[str, Any]]:
        """
        Parse SonarQube issues JSON
        
        Args:
            raw_json: Raw JSON from SonarQube API
            
        Returns:
            List of normalized finding dictionaries
        """
        findings = []
        
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        issues = data.get('issues', [])
        
        for issue in issues:
            finding = self._parse_single_issue(issue)
            if finding:
                findings.append(finding)
        
        return findings
    
    def _parse_single_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single SonarQube issue into normalized format.

        Revision 2 (Sprint 1): the `raw` key on the returned dict MUST hold
        only the per-issue node from `data['issues']`, never the full
        SonarQube response payload. This keeps Finding.raw small and avoids
        storing duplicate scan-wide blobs across every finding row.
        """
        
        # Extract basic fields
        rule_id = issue.get('rule', 'unknown')
        message = issue.get('message', '')
        
        # Extract file and line info
        component = issue.get('component', '')
        # Component format: "project_key:path/to/file.java"
        file_path = self._extract_file_path(component)
        line_number = issue.get('line', 0)
        
        # Map severity
        severity = self._map_severity(issue.get('severity', 'INFO'))
        
        # Extract CWE from tags
        cwe_id = self._extract_cwe(issue.get('tags', []))
        
        return {
            'tool': 'sonarqube',
            'rule_id': rule_id,
            'severity': severity,
            'file_path': file_path,
            'line_number': line_number,
            'message': message,
            'cwe_id': cwe_id,
            'raw': issue
        }
    
    def _extract_file_path(self, component: str) -> str:
        """Extract file path from SonarQube component string"""
        # Component format: "project_key:path/to/file"
        if ':' in component:
            return component.split(':', 1)[1]
        return component
    
    def _map_severity(self, sonar_severity: str) -> str:
        """Map SonarQube severity to our standard HIGH/MEDIUM/LOW"""
        severity_map = {
            'BLOCKER': 'HIGH',
            'CRITICAL': 'HIGH',
            'MAJOR': 'MEDIUM',
            'MINOR': 'LOW',
            'INFO': 'LOW'
        }
        return severity_map.get(sonar_severity.upper(), 'LOW')
    
    def _extract_cwe(self, tags: List[str]) -> str:
        """Extract CWE ID from tags.

        Accepts both dashed (`cwe-79`) and dashless (`cwe79`) forms; the
        downstream CWEMapper normalizes either into `CWE-79`. The bare tag
        `cwe` (no number) is intentionally skipped.
        """
        for tag in tags:
            lower = tag.lower()
            if not lower.startswith('cwe'):
                continue
            rest = lower[3:].lstrip('-')
            if rest.isdigit():
                return f'CWE-{rest}'
        return ''
