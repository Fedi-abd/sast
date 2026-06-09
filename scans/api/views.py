"""Read-only API endpoints scoped to request.user."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from scans.models import Project, Scan
from scans.views import SEVERITY_ORDERING

from .serializers import (
    FindingSerializer, ProjectSerializer, ScanSerializer,
    annotate_finding_count,
)


class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user).order_by("-created_at")


class ScanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScanSerializer

    def get_queryset(self):
        # /api/scans/<id>/ is the polling target for the eventual async
        # UI — keep the per-row payload light (status + finding_count,
        # no findings list).
        return annotate_finding_count(
            Scan.objects.filter(project__owner=self.request.user)
            .select_related("project")
            .order_by("-started_at")
        )

    @action(detail=True, methods=["get"])
    def findings(self, request, pk=None):
        scan = self.get_object()
        qs = scan.findings.annotate(_sev=SEVERITY_ORDERING).order_by("_sev", "id")
        return Response(FindingSerializer(qs, many=True).data)
