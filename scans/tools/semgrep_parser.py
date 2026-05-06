import json
from typing import List, Dict, Any

class SemgrepParser:
    """Parse Semgrep JSON output into normalized findings"""
    
    def parse(self, raw_json: str) -> List[Dict[str, Any]]:
        """
        Parse Semgrep JSON output
        
        Args:
            raw_json: Raw JSON string from Semgrep
            
        Returns:
            List of normalized finding dictionaries
        """
        findings = []
        
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        results = data.get('results', [])
        
        for result in results:
            finding = self._parse_single_result(result)
            if finding:
                findings.append(finding)
        
        return findings
    
    def _parse_single_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single Semgrep result into normalized format.

        Revision 2 (Sprint 1): the `raw` key on the returned dict MUST hold
        only the per-finding node from `data['results']`, never the full
        Semgrep scan output. This keeps Finding.raw small and avoids storing
        duplicate scan-wide blobs across every finding row.
        """
        
        # Extract basic fields
        rule_id = result.get('check_id', 'unknown')
        message = result.get('extra', {}).get('message', '')
        
        # Extract file and line info
        path = result.get('path', '')
        start_line = result.get('start', {}).get('line', 0)
        
        # Map severity
        severity = self._map_severity(result.get('extra', {}).get('severity', 'INFO'))
        
        # Extract CWE from metadata
        cwe_id = self._extract_cwe(result.get('extra', {}).get('metadata', {}))
        
        return {
            'tool': 'semgrep',
            'rule_id': rule_id,
            'severity': severity,
            'file_path': path,
            'line_number': start_line,
            'message': message,
            'cwe_id': cwe_id,
            'raw': result
        }
    
    def _map_severity(self, semgrep_severity: str) -> str:
        """Map Semgrep severity to our standard HIGH/MEDIUM/LOW"""
        severity_map = {
            'ERROR': 'HIGH',
            'WARNING': 'MEDIUM',
            'INFO': 'LOW'
        }
        return severity_map.get(semgrep_severity.upper(), 'LOW')
    
    def _extract_cwe(self, metadata: Dict[str, Any]) -> str:
        """Extract CWE ID from metadata"""
        # Semgrep stores CWE in metadata.cwe as list or string
        cwe = metadata.get('cwe', [])
        
        if isinstance(cwe, list) and cwe:
            return cwe[0]  # Take first CWE
        elif isinstance(cwe, str):
            return cwe
        
        return ''
