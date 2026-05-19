from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Value, When

from .forms import ProjectForm
from .models import Project, Scan
from .services.scan_service import ScanService


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        context["scans"] = (
            project.scans
            .annotate(finding_count=Count("findings"))
            .order_by("-started_at")
        )
        # Per-tool: Semgrep can run while Sonar is in flight, but each
        # tool's own button should be disabled if that tool is busy.
        running_tools = set(
            project.scans.filter(status="RUNNING").values_list("tool", flat=True)
        )
        context["semgrep_running"] = "semgrep" in running_tools
        context["sonarqube_running"] = "sonarqube" in running_tools
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        # Land on the new project's detail page (the user almost
        # always wants to start a scan straight away) rather than
        # bouncing back to the list.
        return reverse_lazy("scans:project_detail", kwargs={"pk": self.object.pk})


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("scans:project_list")

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = "projects/project_delete.html"
    success_url = reverse_lazy("scans:project_list")

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)


SEVERITY_ORDERING = Case(
    When(severity="HIGH", then=Value(1)),
    When(severity="MEDIUM", then=Value(2)),
    When(severity="LOW", then=Value(3)),
    default=Value(4),
    output_field=IntegerField(),
)


class ScanDetailView(LoginRequiredMixin, DetailView):
    model = Scan
    template_name = "scans/scan_detail.html"

    def get_queryset(self):
        # ensure users can only see their own scan results
        return Scan.objects.filter(project__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scan = self.object

        # Always-on rollups (the cards above the table reflect the FULL
        # scan, not the filtered view). One grouped query each.
        all_findings = scan.findings.all()
        severity_counts = {
            row["severity"]: row["count"]
            for row in all_findings.values("severity").annotate(count=Count("id"))
        }
        context["total_findings"] = sum(severity_counts.values())
        context["high_count"] = severity_counts.get("HIGH", 0)
        context["medium_count"] = severity_counts.get("MEDIUM", 0)
        context["low_count"] = severity_counts.get("LOW", 0)

        owasp_distribution = {
            row["owasp_category"] or "UNMAPPED": row["count"]
            for row in all_findings.values("owasp_category").annotate(count=Count("id"))
        }
        context["owasp_distribution"] = owasp_distribution

        # --- Multi-value filter parsing -----------------------------------
        # ?severity=HIGH&severity=MEDIUM&owasp=A1:...&owasp=A2:...
        # Each rollup row is a checkbox-style toggle: clicking it adds or
        # removes the value from the active set.
        valid_severities = {"HIGH", "MEDIUM", "LOW"}
        active_severities = {
            s for s in self.request.GET.getlist("severity") if s in valid_severities
        }
        active_owasps = {
            o for o in self.request.GET.getlist("owasp") if o in owasp_distribution
        }

        findings = all_findings
        if active_severities:
            findings = findings.filter(severity__in=active_severities)
        if active_owasps:
            # The DB stores empty string for unmapped findings; the URL/UI
            # uses the literal "UNMAPPED" so the rollup row has a stable id.
            db_targets = {"" if o == "UNMAPPED" else o for o in active_owasps}
            findings = findings.filter(owasp_category__in=db_targets)
        findings = findings.annotate(_sev=SEVERITY_ORDERING).order_by("_sev", "id")

        # --- Toggle URL helper --------------------------------------------
        def toggle_url(severities, owasps):
            params = []
            for s in sorted(severities):
                params.append(("severity", s))
            for o in sorted(owasps):
                params.append(("owasp", o))
            qs = "?" + urlencode(params) if params else ""
            return qs + "#findings"

        # Severity rollup rows
        severity_rollups = []
        for value, label, color, count in [
            ("HIGH",   "High",   "danger",  context["high_count"]),
            ("MEDIUM", "Medium", "warning", context["medium_count"]),
            ("LOW",    "Low",    "info",    context["low_count"]),
        ]:
            severity_rollups.append({
                "value": value,
                "label": label,
                "color": color,
                "count": count,
                "is_active": value in active_severities,
                "toggle_url": toggle_url(active_severities ^ {value}, active_owasps),
            })

        # OWASP rollup rows
        owasp_rollups = []
        for category, count in owasp_distribution.items():
            owasp_rollups.append({
                "category": category,
                "count": count,
                "is_active": category in active_owasps,
                "toggle_url": toggle_url(active_severities, active_owasps ^ {category}),
            })

        context["findings"] = findings
        context["severity_rollups"] = severity_rollups
        context["owasp_rollups"] = owasp_rollups
        context["has_active_filter"] = bool(active_severities or active_owasps)
        context["clear_url"] = toggle_url(set(), set())
        return context


def crash(request):
    1 / 0  # This will raise a ZeroDivisionError, simulating a crash for testing purposes
    # scans/views.py


@login_required
@require_POST
def trigger_scan(request, project_id):
    """Kick off one or both scanners for `project_id`.

    `tool` from the form is one of "semgrep", "sonarqube", or "both".
    For the single-tool case, lock per-(project, tool), create the
    RUNNING row, then run the adapter outside the transaction.
    For "both", do the same once per tool and run the two scanners
    in parallel via threads — they share no resources (Semgrep is a
    local subprocess; Sonar uses its own server) so concurrency just
    works.
    """
    valid_tools = {value for value, _ in Scan.TOOL_CHOICES}
    tool = request.POST.get("tool", "semgrep")
    if tool not in valid_tools and tool != "both":
        return redirect("scans:project_detail", pk=project_id)

    project = get_object_or_404(Project, id=project_id, owner=request.user)
    service = ScanService()

    if tool == "both":
        return _trigger_both(request, project, service)

    # Step 1: reserve a scan slot under a short lock.
    # Per-(project, tool) lock — different tools can run concurrently
    # on the same project (Semgrep is local, Sonar uses its own server,
    # no resource conflict), but you can't queue the same tool twice
    # on the same project.
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        if project.scans.filter(status="RUNNING", tool=tool).exists():
            return redirect("scans:project_detail", pk=project_id)
        scan = service._create_running_scan(project, tool)

    # Step 2: execute the scan outside the transaction.
    config = _build_scan_config(tool, project)
    result = service.execute(scan, config=config)

    if result.get("success"):
        return redirect("scans:scan_detail", pk=result["scan_id"])
    return redirect("scans:project_detail", pk=project_id)


def _trigger_both(request, project, service):
    """Run Semgrep + SonarQube on the same project in parallel."""
    import threading

    # Lock and create both RUNNING rows in one short transaction.
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        running = set(
            project.scans.filter(status="RUNNING").values_list("tool", flat=True)
        )
        scans = []
        for t in ("semgrep", "sonarqube"):
            if t in running:
                # Don't double-up if that tool's already running.
                continue
            scans.append(service._create_running_scan(project, t))

    if not scans:
        return redirect("scans:project_detail", pk=project.pk)

    # Run each scan in its own thread so they progress in parallel.
    # Django's runserver uses a thread per request anyway, so this
    # adds two more threads — well within the dev server's capacity.
    threads = []
    for scan in scans:
        config = _build_scan_config(scan.tool, project)
        t = threading.Thread(
            target=service.execute, args=(scan,), kwargs={"config": config}
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    return redirect("scans:project_detail", pk=project.pk)


def _build_scan_config(tool, project):
    """Per-tool config dict for ScanService.run_scan.

    SonarQube config resolves in this order:
      1. `SonarSettings` singleton row (editable in /admin/)
      2. `settings.SONAR_*` from .env / environment variables
      3. Hardcoded fallback (host only)

    Each Project has a unique `sonar_project_key` (auto-set on first
    save) that namespaces its findings inside SonarQube, so one shared
    instance can host every user's data without collisions.
    """
    from django.conf import settings
    from .models import SonarSettings

    if tool == "sonarqube":
        admin_cfg = SonarSettings.get_solo()
        return {
            "sonar_host": (
                admin_cfg.host
                or getattr(settings, "SONAR_HOST", "http://localhost:9000")
            ),
            "sonar_token": (
                admin_cfg.token
                or getattr(settings, "SONAR_TOKEN", None)
            ),
            "project_key": project.sonar_project_key,
            "issue_types": (
                admin_cfg.issue_types
                or getattr(settings, "SAST_SONAR_ISSUE_TYPES", "VULNERABILITY")
            ),
        }
    return {}