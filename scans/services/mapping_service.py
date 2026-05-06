from typing import Dict, List, Any
from scans.mappings.mapper import CWEMapper

class MappingService:
    """Service for mapping findings to OWASP categories"""
    
    def __init__(self):
        self.mapper = CWEMapper()
    
    def map_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add OWASP mapping to a finding
        
        Args:
            finding: Finding dict from parser
            
        Returns:
            Finding dict with owasp_category and confidence_score added
        """
        cwe_id = finding.get('cwe_id', '')
        owasp_category, confidence = self.mapper.map_cwe_to_owasp(cwe_id)
        
        finding['owasp_category'] = owasp_category
        finding['confidence_score'] = confidence
        
        return finding
    
    def map_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map multiple findings"""
        return [self.map_finding(f) for f in findings]
    
    def compute_stats(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute mapping statistics for a set of findings
        
        Returns:
            Dict with:
            - total: Total findings
            - mapped: Number of mapped findings
            - unmapped: Number of unmapped findings
            - mapping_rate: Percentage of mapped findings
            - by_owasp: Count by OWASP category
            - by_severity: Count by severity
        """
        total = len(findings)
        mapped = sum(1 for f in findings if f.get('owasp_category') != 'UNMAPPED')
        unmapped = total - mapped
        
        # Count by OWASP category
        by_owasp = {}
        for f in findings:
            category = f.get('owasp_category', 'UNMAPPED')
            by_owasp[category] = by_owasp.get(category, 0) + 1
        
        # Count by severity
        by_severity = {}
        for f in findings:
            severity = f.get('severity', 'UNKNOWN')
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            'total': total,
            'mapped': mapped,
            'unmapped': unmapped,
            'mapping_rate': (mapped / total * 100) if total > 0 else 0.0,
            'by_owasp': by_owasp,
            'by_severity': by_severity
        }
