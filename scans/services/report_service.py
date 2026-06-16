"""Server-side PDF report generation.

`generate_scan_report_pdf` renders `templates/scans/scan_report.html`
with scan + findings context, then hands the HTML to WeasyPrint to
produce a downloadable PDF. The 6-column findings table layout and
the static header / footer match the Sprint 4 PDF spec (see
`docs/sprint-4-dashboard-and-export.md` Track 7).

Theming: every color the report renders resolves through CSS custom
properties defined at the top of `static/css/pdf-report.css`. When
the designer's tokens land in `frontend/`, paste the matching values
into that file's `:root` block and the report reskins with no template
or view changes.

Import is deferred to call-time. WeasyPrint links against GTK system
libs (libgobject, pango, cairo) that the user's WSL has but the
Windows venv used for tests doesn't. Deferring keeps tests importing
this module without crashing; views that actually call the function
fail loud when WeasyPrint can't load (a misconfigured deploy is a
better failure mode than a silent missing-feature one).
"""
import logging
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from scans.models import Scan

logger = logging.getLogger("scans")


def _report_stats(findings):
    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    owasp_counts = {}
    for f in findings:
        if f.severity in severity_counts:
            severity_counts[f.severity] += 1
        cat = f.owasp_category or "UNMAPPED"
        owasp_counts[cat] = owasp_counts.get(cat, 0) + 1

    owasp_max = max(owasp_counts.values(), default=0)
    owasp_distribution = [
        {"category": cat, "count": n,
         "pct": round(n / owasp_max * 100) if owasp_max else 0}
        for cat, n in sorted(owasp_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    mapped = sum(n for cat, n in owasp_counts.items() if cat != "UNMAPPED")
    total = len(findings)
    return {
        "severity_counts": severity_counts,
        "owasp_distribution": owasp_distribution,
        "mapped_count": mapped,
        "unmapped_count": owasp_counts.get("UNMAPPED", 0),
        "mapping_rate": round(mapped / total * 100) if total else 0,
    }


def _sonar_types_present(scan, findings):
    # Sonar tags each finding with a type; the normalized model doesn't,
    # so read it back off raw. Semgrep has no equivalent.
    if scan.tool != "sonarqube":
        return []
    return sorted({
        f.raw["type"] for f in findings
        if isinstance(f.raw, dict) and f.raw.get("type")
    })


def generate_scan_report_pdf(scan: Scan, severities=None) -> bytes:
    """`severities` scopes the report to a subset (e.g. {"HIGH"} for an
    executive summary); falsy means every finding. Raises if WeasyPrint
    can't load its native GTK deps (deliberately uncaught, see the
    module docstring) rather than silently degrading.
    """
    from weasyprint import CSS, HTML

    qs = scan.findings.all()
    if severities:
        qs = qs.filter(severity__in=severities)
    findings = list(qs)

    for f in findings:
        raw = f.raw if isinstance(f.raw, dict) else {}
        f.display_recommendation = (
            raw.get("recommendation")
            or raw.get("message")
            or f.message
            or "Voir la documentation de la règle."
        )

    scope_label = None
    if severities:
        scope_label = ", ".join(s for s in ("HIGH", "MEDIUM", "LOW") if s in severities)

    sonar_types = _sonar_types_present(scan, findings)

    pdf_css_path = Path(settings.BASE_DIR) / "static" / "css" / "pdf-report.css"

    html_string = render_to_string(
        "scans/scan_report.html",
        {
            "scan": scan,
            "findings": findings,
            "total_findings": len(findings),
            "generated_at": timezone.now(),
            "scope_label": scope_label,
            "sonar_types": sonar_types,
            "pdf_css_url": "",
            **_report_stats(findings),
        },
    )

    logger.info(
        f"pdf_report_render scan={scan.id} findings={len(findings)} "
        f"scope={scope_label or 'all'}"
    )

    return HTML(string=html_string).write_pdf(
        stylesheets=[CSS(filename=str(pdf_css_path))],
    )
