from django.utils import timezone
from typing import Dict, List, Any, Optional
from scans.models import Project, Scan, Finding
from scans.tools.semgrep_adapter import SemgrepAdapter
from scans.tools.semgrep_parser import SemgrepParser
from scans.tools.sonar_adapter import SonarAdapter
from scans.tools.sonar_parser import SonarParser
from scans.services.mapping_service import MappingService
from scans.services.path_resolver import PathResolver

import logging
logger = logging.getLogger("scans")


class ScanService:
    """Main service for orchestrating security scans"""

    def __init__(self):
        self.mapping_service = MappingService()
        self.path_resolver = PathResolver()

    def run_scan(self, project: Project, tool: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Validate `tool`, create a RUNNING Scan row, and execute it.

        Convenience entry point for callers that don't already hold a
        Scan row (e.g. the `scan_project` management command). Web
        requests use `_create_running_scan` + `execute` separately so the
        creation can sit inside a short locking transaction while the
        actual run happens outside it.
        """
        if config is None:
            config = {}
        scan = self._create_running_scan(project, tool)
        return self.execute(scan, config)

    def _create_running_scan(self, project: Project, tool: str) -> Scan:
        """Validate the tool and create the RUNNING Scan row."""
        # Revision 1 (Sprint 1): validate `tool` against the supported set
        # before persisting a Scan row, so we never store an invalid scan.
        valid_tools = {value for value, _label in Scan.TOOL_CHOICES}
        if tool not in valid_tools:
            raise ValueError(
                f"Unsupported tool '{tool}'. Must be one of: {sorted(valid_tools)}"
            )
        # `started_at` has auto_now_add=True; let the model populate it.
        return Scan.objects.create(project=project, tool=tool, status='RUNNING')

    def execute(self, scan: Scan, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Run the adapter/parser/mapping pipeline on an existing scan row.

        Must be called OUTSIDE any caller-held transaction — a DB error
        during `bulk_create` would otherwise poison the transaction and
        prevent the FAILED-status save below from going through.
        """
        if config is None:
            config = {}

        project = scan.project
        tool = scan.tool

        # logging: scan start
        logger.info(f"scan_start id={scan.id} project={project.name} tool={tool}")

        start_time = timezone.now()
        resolved = None

        try:
            # Sprint 2: resolve project source -> local directory the
            # adapter can read. Local paths are returned as-is; uploads
            # are extracted to a temp dir; git URLs are shallow-cloned.
            # The cleanup() in `finally` removes any temp dir we made.
            resolved = self.path_resolver.resolve(project)

            adapter_result = self._run_adapter(tool, resolved.path, config)

            if not adapter_result.success:
                scan.status = 'FAILED'
                scan.error_message = adapter_result.error_message
                scan.finished_at = timezone.now()
                scan.duration_seconds = int((timezone.now() - start_time).total_seconds())
                scan.save()

                # logging: adapter failure
                logger.error(f"scan_error id={scan.id} error='{adapter_result.error_message}'")

                return {
                    'success': False,
                    'scan_id': str(scan.id),
                    'error': adapter_result.error_message
                }

            # Parse findings
            parsed_findings = self._parse_results(tool, adapter_result.raw_output)

            # Map to OWASP
            mapped_findings = self.mapping_service.map_findings(parsed_findings)

            # Store findings
            finding_objects = self._create_finding_objects(scan, mapped_findings)
            Finding.objects.bulk_create(finding_objects)

            # Mark success
            scan.status = 'SUCCESS'
            scan.finished_at = timezone.now()
            scan.duration_seconds = int((timezone.now() - start_time).total_seconds())
            scan.save()

            # logging: scan end success
            logger.info(
                f"scan_end id={scan.id} status=SUCCESS duration={scan.duration_seconds}s"
            )

            # Stats
            stats = self.mapping_service.compute_stats(mapped_findings)

            return {
                'success': True,
                'scan_id': str(scan.id),
                'tool': tool,
                'duration_seconds': scan.duration_seconds,
                'total_findings': stats['total'],
                'mapped': stats['mapped'],
                'unmapped': stats['unmapped'],
                'mapping_rate': stats['mapping_rate'],
                'by_severity': stats['by_severity'],
                'by_owasp': stats['by_owasp'],
            }

        except (ValueError, RuntimeError) as e:
            # Expected, human-readable validation failures: zip-slip
            # rejected, git host not allowed, missing source, git clone
            # failed. Show the message as-is — no "Unexpected error:"
            # prefix, since we raised this on purpose.
            scan.status = 'FAILED'
            scan.error_message = str(e)
            scan.finished_at = timezone.now()
            scan.duration_seconds = int((timezone.now() - start_time).total_seconds())
            scan.save()

            logger.info(f"scan_error id={scan.id} error='{str(e)}'")
            logger.info(
                f"scan_end id={scan.id} status=FAILED duration={scan.duration_seconds}s"
            )
            return {
                'success': False,
                'scan_id': str(scan.id),
                'error': str(e),
            }
        except Exception as e:
            scan.status = 'FAILED'
            scan.error_message = f'Unexpected error: {str(e)}'
            scan.finished_at = timezone.now()
            scan.duration_seconds = int((timezone.now() - start_time).total_seconds())
            scan.save()

            # logging: unexpected exception
            logger.error(f"scan_error id={scan.id} error='{str(e)}'")

            # logging: scan end failure
            logger.info(
                f"scan_end id={scan.id} status=FAILED duration={scan.duration_seconds}s"
            )

            return {
                'success': False,
                'scan_id': str(scan.id),
                'error': str(e)
            }
        finally:
            if resolved is not None:
                resolved.cleanup()

    def _run_adapter(self, tool: str, repo_path: str, config: Dict):
        if tool == 'semgrep':
            adapter = SemgrepAdapter()
            return adapter.run(repo_path, config)
        elif tool == 'sonarqube':
            from django.conf import settings as dj_settings
            # Per-scan overrides (admin-edited SonarSettings) come in
            # via `config`; static infrastructure settings stay in
            # Django settings.
            adapter = SonarAdapter(
                sonar_host=config.get('sonar_host', 'http://localhost:9000'),
                sonar_token=config.get('sonar_token'),
                sonar_scanner_path=getattr(dj_settings, 'SONAR_SCANNER_PATH', None),
                poll_interval=getattr(dj_settings, 'SAST_SONAR_POLL_INTERVAL', 2.0),
                poll_timeout=getattr(dj_settings, 'SAST_SONAR_POLL_TIMEOUT', 300.0),
                issue_types=config.get(
                    'issue_types',
                    getattr(dj_settings, 'SAST_SONAR_ISSUE_TYPES', 'VULNERABILITY'),
                ),
            )
            return adapter.run(repo_path, config)
        else:
            raise ValueError(f'Unknown tool: {tool}')

    def _parse_results(self, tool: str, raw_output: str) -> List[Dict[str, Any]]:
        if tool == 'semgrep':
            parser = SemgrepParser()
            return parser.parse(raw_output)
        elif tool == 'sonarqube':
            parser = SonarParser()
            return parser.parse(raw_output)
        else:
            raise ValueError(f'Unknown tool: {tool}')

    def _create_finding_objects(self, scan: Scan, findings: List[Dict[str, Any]]) -> List[Finding]:
        finding_objects = []

        for f in findings:
            raw = f['raw']
            # Revision 2 (Sprint 1): Finding.raw must hold only the per-finding
            # node emitted by the parser. Reject any caller that smuggles the
            # whole tool dump (e.g., a dict with a top-level 'results'/'issues'
            # list) into a single Finding row.
            if not isinstance(raw, dict):
                raise ValueError(
                    f"Finding.raw must be a dict (per-finding node), got {type(raw).__name__}"
                )
            if 'results' in raw or 'issues' in raw:
                raise ValueError(
                    "Finding.raw appears to contain the full scan output; "
                    "store only the per-finding node from the parser."
                )

            finding = Finding(
                scan=scan,
                tool=f['tool'],
                rule_id=f['rule_id'],
                severity=f['severity'],
                file_path=f['file_path'],
                line_number=f['line_number'],
                message=f['message'],
                cwe_id=f.get('cwe_id', ''),
                owasp_category=f.get('owasp_category', 'UNMAPPED'),
                confidence_score=f.get('confidence_score', 0.0),
                raw=raw,
            )
            finding_objects.append(finding)

        return finding_objects
