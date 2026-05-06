import json
import os
from typing import Dict, Optional

class CWEMapper:
    """Maps CWE IDs to OWASP Top 10 2017 categories"""
    
    def __init__(self, mapping_file=None):
        if mapping_file is None:
            mapping_file = os.path.join(
                os.path.dirname(__file__),
                'cwe_to_owasp_2017.json'
            )
        
        with open(mapping_file, 'r') as f:
            self.mapping = json.load(f)
    
    def map_cwe_to_owasp(self, cwe_id: str) -> tuple[str, float]:
        """
        Map CWE ID to OWASP category with confidence score
        
        Args:
            cwe_id: CWE identifier (e.g., "CWE-79" or "CWE-79: XSS" or "79")
            
        Returns:
            Tuple of (owasp_category, confidence_score)
        """
        if not cwe_id:
            return "UNMAPPED", 0.0
        
        # Normalize CWE format
        normalized_cwe = self._normalize_cwe(cwe_id)
        
        # Direct mapping
        if normalized_cwe in self.mapping:
            return self.mapping[normalized_cwe], 1.0
        
        # No mapping found
        return "UNMAPPED", 0.0
    
    def _normalize_cwe(self, cwe_id: str) -> str:
        """Normalize CWE ID to CWE-XXX format"""
        cwe_id = cwe_id.strip().upper()
        
        # Remove description after colon
        if ':' in cwe_id:
            cwe_id = cwe_id.split(':')[0].strip()
        
        # Already in correct format
        if cwe_id.startswith('CWE-'):
            return cwe_id
        
        # Just number - add prefix
        if cwe_id.isdigit():
            return f'CWE-{cwe_id}'
        
        # Has CWE but no dash
        if cwe_id.startswith('CWE'):
            number = cwe_id[3:].strip()
            if number.isdigit():
                return f'CWE-{number}'
        
        return cwe_id
