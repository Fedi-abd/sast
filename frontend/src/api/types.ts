/**
 * Type aliases that mirror the DRF serializers in `scans/api/serializers.py`.
 * Keep these in sync when serializer fields change — they're the contract
 * between Vue and Django.
 */

export interface Project {
  id: string
  name: string
  language: string
  source_type: 'local' | 'upload' | 'git'
  source_type_display: string
  created_at: string
}

export type ScanStatus = 'RUNNING' | 'SUCCESS' | 'FAILED'
export type ScanTool = 'semgrep' | 'sonarqube'

export interface Scan {
  id: string
  project_id: string
  project_name: string
  tool: ScanTool
  tool_display: string
  status: ScanStatus
  status_display: string
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  finding_count: number
  error_message: string
}

export type Severity = 'HIGH' | 'MEDIUM' | 'LOW'

export interface Finding {
  id: string
  tool: string
  rule_id: string
  severity: Severity
  severity_display: string
  file_path: string
  line_number: number
  message: string
  cwe_id: string
  owasp_category: string
  confidence_score: number | null
}
