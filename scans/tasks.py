"""django-q2 task entrypoints.

These are the targets that `async_task("scans.tasks.run_scan", ...)`
in `views.trigger_scan` invokes from a worker process. The qcluster
worker imports this module, pulls the queued task, and calls
`run_scan(scan_id, config)` inside its own thread.

Kept deliberately thin; actual scan orchestration (resolve path,
run adapter, parse, map to OWASP, persist findings) lives in
`ScanService.execute`. The task is just the queue ↔ service bridge.
"""
from .models import Scan
from .services.scan_service import ScanService


def run_scan(scan_id: str, config: dict | None = None):
    """Look up the pre-created RUNNING Scan row and execute it.

    The `Scan` row is created synchronously in the request handler
    (so the lock guarantees uniqueness); only the actual scan work
    is deferred to the worker. By the time this runs, `scan_id`
    already points to a real row in the DB.
    """
    scan = Scan.objects.get(id=scan_id)
    return ScanService().execute(scan, config=config or {})
