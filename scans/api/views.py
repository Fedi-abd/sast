"""SAST API viewsets, scoped to request.user, full CRUD on projects.

Two viewsets and one action:

  - `ProjectViewSet`: full CRUD. Read responses use `ProjectSerializer`
    (display values + IDs); write payloads use `ProjectWriteSerializer`
    (source-type-conditional validation, immutable source_type on
    update). Multipart parsing is enabled so the upload source type
    can post a ZIP archive in the same request that creates the
    project.

  - `ScanViewSet`: read-only on the rows themselves (status polling,
    finding listing). Scans are *created* via the `trigger` action,
    not via direct POST to /api/scans/. The lifecycle wraps the same
    lock + django-q2 enqueue path the templated `trigger_scan` view
    uses.

  - `ScanViewSet.trigger`: POST /api/scans/trigger/, enqueue one or
    both scans for a project the requester owns. Returns the new
    Scan IDs immediately; the UI polls them via GET /api/scans/<id>/.
"""
import shutil
import time
from datetime import timedelta

import requests
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings as django_settings

from scans.models import Finding, PlatformSettings, Project, Scan, SonarSettings
from scans.services import report_service
from scans.services.scan_service import ScanService
from scans.views import SEVERITY_ORDERING, _build_scan_config
from users.models import UserProfile

from .serializers import (
    CrossProjectFindingSerializer,
    FindingSerializer,
    MeSerializer,
    ProjectSerializer,
    ProjectWriteSerializer,
    ScanSerializer,
    ScanTriggerSerializer,
    annotate_finding_count,
)


class MeView(APIView):
    """GET /api/me/: current user identity + role.

    The SPA hits this on mount to (a) confirm auth state cheaper than
    `/api/projects/`, and (b) decide whether to render admin nav. The
    response is small and uncached; clients should refetch when the
    user's role might have changed.

    Returns 401 when anonymous (IsAuthenticated permission). `credits`
    reads from the user's profile (auto-created by the Track 6 signal).
    """

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ConfigView(APIView):
    """GET /api/config/: deployment knobs any authenticated client needs.

    The SPA's New-project form reads this to (a) hide the local-path
    radio when the deployment disables it and (b) show the user's
    *effective* upload cap instead of a hardcoded number. Staff-only
    knobs live under /api/admin/; this endpoint is the read-only,
    everyone-visible subset.
    """

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        user_cap = (
            profile.max_upload_mb if profile is not None
            else UserProfile.DEFAULT_MAX_UPLOAD_MB
        )
        max_projects = (
            profile.max_projects if profile is not None
            else UserProfile.DEFAULT_MAX_PROJECTS
        )
        # Negative per-user cap means unlimited; the global ceiling
        # still applies. max_projects passes through (-1) for the client.
        effective_upload = (
            django_settings.SAST_MAX_UPLOAD_SIZE_MB if user_cap < 0
            else min(user_cap, django_settings.SAST_MAX_UPLOAD_SIZE_MB)
        )
        return Response({
            "hide_local_source": PlatformSettings.get_solo().hide_local_source,
            "max_upload_mb": effective_upload,
            "max_projects": max_projects,
        })


# Sonar reachability is the slow part of the health check; one ping per
# minute (process-wide) keeps the dashboard's status line honest without
# hammering the server on every reload.
_HEALTH_CACHE = {"at": 0.0, "sonarqube": None}


class HealthView(APIView):
    """GET /api/health/: engine status for the dashboard's ONLINE pill.

    Response: ``{"semgrep": bool, "sonarqube": bool}``. Semgrep checks
    the CLI is discoverable; SonarQube pings the configured server's
    status endpoint (3s timeout, cached 60s process-wide). Clients
    should fetch this non-blocking; it must never delay first paint.
    """

    def get(self, request):
        # which() validates a configured absolute path too; a stale
        # SEMGREP_PATH in .env must not light the pill green.
        semgrep_ok = bool(shutil.which(django_settings.SEMGREP_PATH or "semgrep"))

        now = time.monotonic()
        # fresh=1 (sent by the dashboard's page load + Refresh button)
        # busts the cache, with a 5s floor so a click-happy admin can't
        # hammer Sonar; everything else rides the 60s window.
        max_age = 5 if request.query_params.get("fresh") == "1" else 60
        if now - _HEALTH_CACHE["at"] > max_age or _HEALTH_CACHE["sonarqube"] is None:
            row = SonarSettings.get_solo()
            host = (row.host or django_settings.SONAR_HOST).rstrip("/")
            try:
                response = requests.get(f"{host}/api/system/status", timeout=3)
                _HEALTH_CACHE["sonarqube"] = response.status_code == 200
            except requests.RequestException:
                _HEALTH_CACHE["sonarqube"] = False
            _HEALTH_CACHE["at"] = now

        return Response({
            "semgrep": semgrep_ok,
            "sonarqube": _HEALTH_CACHE["sonarqube"],
        })


_VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}
_VALID_ORDERINGS = {
    "-detected_at": "-scan__started_at",
    "detected_at": "scan__started_at",
    "severity": "severity",
    "-severity": "-severity",
    "project": "scan__project__name",
    "-project": "-scan__project__name",
}


class CrossProjectFindingsView(APIView):
    """GET /api/findings/: every finding across the requester's projects.

    Powers the designer's Vulnerabilities triage queue (`#/vulns`).
    Distinct from `/api/scans/<id>/findings/` (which is filtered to
    one scan); this view spans the whole workspace.

    Query params:
      - severity=HIGH         single value
      - severity=HIGH,MEDIUM  comma-separated for multi-select
      - owasp=A1:2017-Injection,UNMAPPED   category filter (UNMAPPED
        matches rows with no category)
      - project_id=<uuid>     scope to one project (optional)
      - ordering=-detected_at, severity, -severity, project, -project
        Default is `-detected_at` (most recent first).
      - limit=<n> / offset=<n>  paginate. When either is present the
        response becomes an envelope::

            {"results": [...], "total": int,
             "severity_counts": {...}, "owasp_counts": [...]}

        `total` counts rows after filters (drives "load more"); the
        `*_counts` aggregate the user's ENTIRE findings set (they
        drive filter chips). Without limit/offset the plain list is
        returned (legacy shape). Unlike severity/ordering (where an
        unknown value is a harmless no-op), a bad limit/offset is
        unambiguously a client bug; it 400s.

    Only findings from SUCCESS scans are included; FAILED scans
    never persist findings, and including their rows would be empty
    noise.
    """

    def get(self, request):
        qs = Finding.objects.filter(
            scan__project__owner=request.user,
            scan__status="SUCCESS",
        ).select_related("scan", "scan__project")

        base = qs  # unfiltered snapshot; the *_counts chips aggregate the whole set

        severities_raw = request.query_params.get("severity", "")
        severities = [
            s for s in severities_raw.upper().split(",") if s in _VALID_SEVERITIES
        ]
        if severities:
            qs = qs.filter(severity__in=severities)

        owasp = [o for o in request.query_params.get("owasp", "").split(",") if o]
        if owasp:
            named = [o for o in owasp if o != "UNMAPPED"]
            cond = Q(owasp_category__in=named) if named else Q()
            if "UNMAPPED" in owasp:
                cond = cond | Q(owasp_category="") | Q(owasp_category="UNMAPPED")
            qs = qs.filter(cond)

        project_id = request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(scan__project_id=project_id)

        ordering = request.query_params.get("ordering", "-detected_at")
        qs = qs.order_by(_VALID_ORDERINGS.get(ordering, "-scan__started_at"))

        limit_raw = request.query_params.get("limit")
        offset_raw = request.query_params.get("offset")
        if limit_raw is None and offset_raw is None:
            return Response(CrossProjectFindingSerializer(qs, many=True).data)

        try:
            limit = int(limit_raw) if limit_raw is not None else 25
            offset = int(offset_raw) if offset_raw is not None else 0
            if limit < 1 or offset < 0:
                raise ValueError
        except ValueError:
            return Response(
                {"detail": "limit must be >= 1 and offset >= 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for row in base.values("severity").annotate(count=Count("id")):
            severity_counts[row["severity"]] = row["count"]
        owasp_counts = [
            {"category": row["owasp_category"] or "UNMAPPED", "count": row["count"]}
            for row in base.values("owasp_category")
            .annotate(count=Count("id")).order_by("-count")
        ]

        return Response({
            "results": CrossProjectFindingSerializer(
                qs[offset:offset + limit], many=True,
            ).data,
            "total": qs.count(),
            "severity_counts": severity_counts,
            "owasp_counts": owasp_counts,
        })


class SolveFindingView(APIView):
    """POST /api/findings/<uuid>/solve/, body ``{"solved": true|false}``
    (defaults true). Owner-scoped: a finding the requester doesn't own
    returns 404.
    """

    def post(self, request, finding_id):
        finding = get_object_or_404(
            Finding, pk=finding_id, scan__project__owner=request.user,
        )
        raw = request.data.get("solved", True)
        finding.solved = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1")
        finding.save(update_fields=["solved"])
        return Response({"id": str(finding.id), "solved": finding.solved})


class _PDFContentRenderer(BaseRenderer):
    """Exists only to satisfy DRF content negotiation when the client
    asks for application/pdf. The view streams the PDF straight into an
    HttpResponse, so render() only ever runs for DRF's own error
    payloads (a 404 dict, say); those fall back to JSON so the body
    stays readable.
    """

    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, (bytes, bytearray, memoryview)):
            return data
        return JSONRenderer().render(data)


class ScanReportPDFView(APIView):
    """One scan's report as a downloadable PDF.

    Cross-user access returns 404, not 403 (a scan only "exists" to its
    owner), same scope convention as `ScanViewSet`.

    Query params:
      - severity=HIGH[,MEDIUM]   Scope the report to those severities
        (e.g. a HIGH-only executive summary). Omitted means every
        finding. Unknown values are ignored.

    Returns an `application/pdf` response with
    `Content-Disposition: attachment` so browsers download rather
    than render inline.
    """

    renderer_classes = [_PDFContentRenderer, JSONRenderer]
    VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}

    def get(self, request, scan_id):
        scan = get_object_or_404(
            Scan, pk=scan_id, project__owner=request.user,
        )
        raw = request.query_params.get("severity", "")
        severities = {s for s in raw.upper().split(",") if s in self.VALID_SEVERITIES} or None

        pdf_bytes = report_service.generate_scan_report_pdf(scan, severities=severities)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = f"sast-scan-{scan.id}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class DashboardView(APIView):
    """GET /api/dashboard/: KPIs for the SPA's landing page.

    Response shape::

        {
          "totals": {
            "projects": int,
            "scans": int,
            "scans_this_week": int,
            "open_findings": int       # sum of finding counts across all
                                       # SUCCESS scans owned by the user.
                                       # Double-counts findings across
                                       # rescans of the same project;
                                       # treat as a directional metric,
                                       # not an exact count of unique
                                       # vulnerabilities.
          },
          "owasp_distribution": [
            {"category": "...", "count": int}, ...
          ],
          "recent_activity": [
            {"scan_id": uuid, "project_id": uuid, "project_name": str,
             "tool": str, "tool_display": str, "status": str,
             "started_at": iso8601, "finding_count": int}, ...
          ]
        }

    All counts are user-scoped; the same project/scan/finding row
    appears in nobody else's dashboard.
    """

    def get(self, request):
        user = request.user
        user_scans = Scan.objects.filter(project__owner=user)

        week_ago = timezone.now() - timedelta(days=7)
        scans_this_week = user_scans.filter(started_at__gte=week_ago).count()

        # FAILED scans have no findings; counting them would tell the
        # user nothing useful about their security posture.
        user_findings = Finding.objects.filter(
            scan__project__owner=user, scan__status="SUCCESS",
        )
        open_findings = user_findings.count()

        # UNMAPPED stays in the distribution so coverage gaps are
        # visible; hiding them would falsely suggest the mapping is
        # complete.
        owasp_rows = (
            user_findings
            .values("owasp_category")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        owasp_distribution = [
            {
                "category": row["owasp_category"] or "UNMAPPED",
                "count": row["count"],
            }
            for row in owasp_rows
        ]

        recent_qs = annotate_finding_count(
            user_scans.select_related("project").order_by("-started_at")
        )[:5]
        recent_activity = [
            {
                "scan_id": str(scan.id),
                "project_id": str(scan.project_id),
                "project_name": scan.project.name,
                "tool": scan.tool,
                "tool_display": scan.get_tool_display(),
                "status": scan.status,
                "started_at": scan.started_at.isoformat(),
                "finding_count": scan.finding_count,
            }
            for scan in recent_qs
        ]

        return Response({
            "totals": {
                "projects": Project.objects.filter(owner=user).count(),
                "scans": user_scans.count(),
                "scans_this_week": scans_this_week,
                "open_findings": open_findings,
            },
            "owasp_distribution": owasp_distribution,
            "recent_activity": recent_activity,
        })


class ProjectViewSet(viewsets.ModelViewSet):
    """Full CRUD on Projects, scoped to the requesting user."""

    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ProjectWriteSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ScanViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/retrieve + the `findings` and `trigger` actions."""

    serializer_class = ScanSerializer

    def get_queryset(self):
        # /api/scans/<id>/ is the polling target for the eventual async
        # UI; keep the per-row payload light (status + finding_count,
        # no findings list).
        return annotate_finding_count(
            Scan.objects.filter(project__owner=self.request.user)
            .select_related("project")
            .order_by("-started_at")
        )

    @action(detail=True, methods=["get"])
    def findings(self, request, pk=None):
        """GET /api/scans/<id>/findings/: the findings table data.

        Plain GET returns the full list (legacy shape; also what the
        JSON export wants). When `limit` or `offset` is present the
        response becomes an envelope so big scans render incrementally::

            {"results": [...], "total": int,
             "severity_counts": {"HIGH": n, ...},     # whole scan
             "owasp_counts": [{"category": ..., "count": n}, ...]}

        `total` counts rows AFTER the severity/owasp filters (it drives
        "load more"); the two `*_counts` aggregate the WHOLE scan (they
        drive the filter chips). Filters: `severity=HIGH,MEDIUM` and
        `owasp=A1:2017-Injection,UNMAPPED` (UNMAPPED matches rows with
        no category).
        """
        scan = self.get_object()

        # Drop hotspots from everything below if the admin hid them.
        base = scan.findings.all()
        if not SonarSettings.get_solo().include_hotspots:
            base = base.exclude(raw__type="SECURITY_HOTSPOT")

        # The type selection (the burger) is the working set; the
        # severity/owasp filters and the solved-hide apply within it.
        # `typed` stays clean (no annotate/order, which would break the
        # GROUP BY in the tallies). The frontend only sends `type` for
        # Sonar scans, where every finding carries one.
        types = [t for t in request.query_params.get("type", "").split(",") if t]
        typed = base.filter(raw__type__in=types) if types else base

        qs = base.annotate(_sev=SEVERITY_ORDERING).order_by("_sev", "id")
        if types:
            qs = qs.filter(raw__type__in=types)

        severities = [
            s for s in request.query_params.get("severity", "").upper().split(",")
            if s in _VALID_SEVERITIES
        ]
        if severities:
            qs = qs.filter(severity__in=severities)
        owasp = [o for o in request.query_params.get("owasp", "").split(",") if o]
        if owasp:
            named = [o for o in owasp if o != "UNMAPPED"]
            cond = Q(owasp_category__in=named) if named else Q()
            if "UNMAPPED" in owasp:
                cond = cond | Q(owasp_category="") | Q(owasp_category="UNMAPPED")
            qs = qs.filter(cond)

        # Solved findings stay counted but drop out of the live list.
        qs = qs.exclude(solved=True)

        limit_raw = request.query_params.get("limit")
        offset_raw = request.query_params.get("offset")
        if limit_raw is None and offset_raw is None:
            return Response(FindingSerializer(qs, many=True).data)

        try:
            limit = int(limit_raw) if limit_raw is not None else 25
            offset = int(offset_raw) if offset_raw is not None else 0
            if limit < 1 or offset < 0:
                raise ValueError
        except ValueError:
            return Response(
                {"detail": "limit must be >= 1 and offset >= 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rollups follow the type selection AND skip solved findings, so
        # the chips/tiles match the open rows in the list. visible_total
        # below keeps the full working-set size for the "N/M solved" math.
        typed_unsolved = typed.exclude(solved=True)
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for row in typed_unsolved.values("severity").annotate(count=Count("id")):
            severity_counts[row["severity"]] = row["count"]
        owasp_counts = [
            {"category": row["owasp_category"] or "UNMAPPED", "count": row["count"]}
            for row in typed_unsolved.values("owasp_category")
            .annotate(count=Count("id")).order_by("-count")
        ]
        # Whole-scan tally so the burger always shows every type's size
        # (minus any the admin suppressed, since base already dropped them).
        type_counts = [
            {"type": row["raw__type"], "count": row["count"]}
            for row in base.values("raw__type")
            .annotate(count=Count("id")).order_by("-count")
            if row["raw__type"]
        ]

        return Response({
            "results": FindingSerializer(qs[offset:offset + limit], many=True).data,
            "total": qs.count(),
            "visible_total": typed.count(),
            "solved_count": typed.filter(solved=True).count(),
            "severity_counts": severity_counts,
            "owasp_counts": owasp_counts,
            "type_counts": type_counts,
        })

    @action(detail=False, methods=["post"])
    def trigger(self, request):
        """POST /api/scans/trigger/: enqueue a scan and return its row.

        Body: {project_id: UUID, tool: "semgrep" | "sonarqube" | "both"}.

        Success: 202 Accepted with the list of scan IDs reserved.
        Scans that were already RUNNING for the requested tools get
        skipped, not duplicated; the response calls those out so the
        client can surface them.

        Insufficient credits: 402 Payment Required with body
        ``{"detail": "...", "cost": int, "remaining": int}``: the
        client can show the user what was needed vs what they had.

        Implementation mirrors the templated `trigger_scan` view in
        `scans/views.py`: same per-(project, tool) lock, same
        credit charge, same `async_task` enqueue.
        """
        from django_q.tasks import async_task

        from users.models import InsufficientCreditsError, UserProfile

        payload = ScanTriggerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        project = get_object_or_404(
            Project, id=payload.validated_data["project_id"], owner=request.user,
        )
        tool = payload.validated_data["tool"]
        requested_tools = ("semgrep", "sonarqube") if tool == "both" else (tool,)
        service = ScanService()

        try:
            with transaction.atomic():
                Project.objects.select_for_update().get(pk=project.pk)
                running = set(
                    project.scans.filter(status="RUNNING").values_list("tool", flat=True)
                )
                to_create = [t for t in requested_tools if t not in running]
                skipped = [t for t in requested_tools if t in running]
                UserProfile.charge(request.user, cost=len(to_create))
                scans = [
                    service._create_running_scan(project, t)
                    for t in to_create
                ]
        except InsufficientCreditsError as err:
            return Response(
                {
                    "detail": str(err),
                    "cost": err.cost,
                    "remaining": err.remaining,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        for scan in scans:
            async_task(
                "scans.tasks.run_scan",
                str(scan.id),
                _build_scan_config(scan.tool, project),
            )

        return Response(
            {
                "scans": ScanSerializer(
                    annotate_finding_count(
                        Scan.objects.filter(id__in=[s.id for s in scans])
                    ),
                    many=True,
                ).data,
                "skipped_tools": skipped,
            },
            status=status.HTTP_202_ACCEPTED,
        )
