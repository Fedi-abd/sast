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
    # Deliberate uncaught error. Lets us confirm the styled 500 page
    # renders under DEBUG=False. Wired in config/urls.py.
    1 / 0


def handler_404(request, exception):
    """Project-wide 404 handler.

    Renders the styled `templates/errors/404.html` instead of Django's
    debug 404 page. Wired in via `handler404` in `config/urls.py`.
    Active when `DEBUG=False`; under DEBUG=True Django shows its own
    diagnostic page regardless.
    """
    return render(request, "errors/404.html", status=404)


@login_required
@require_POST
def trigger_scan(request, project_id):
    """Enqueue one or both scans for `project_id` and return immediately.

    `tool` from the form is one of "semgrep", "sonarqube", or "both".
    For each requested tool we:

      1. Open a short DB transaction with `select_for_update()` on the
         Project row. This serializes concurrent "click Run Scan twice"
         attempts so the duplicate check below is race-free.
      2. Skip any tool that already has a RUNNING scan for this project
         (the per-(project, tool) lock).
      3. Charge the user one credit per scan we're about to create
         (one credit per single tool, two for "both" if both are
         free). Insufficient credits → bounce back to the project
         detail page with an error message via Django's messages
         framework.
      4. Reserve a RUNNING `Scan` row for the survivors.
      5. Push `scans.tasks.run_scan` onto the django-q2 queue with the
         new scan IDs.

    The view then redirects to the project detail page, which has
    a small polling script that hits `/api/scans/<id>/` every 3s and
    reloads the page once nothing's still RUNNING. The actual scan
    work happens in the qcluster worker process; runserver returns
    in milliseconds.
    """
    from django.contrib import messages
    from django_q.tasks import async_task

    from users.models import InsufficientCreditsError, UserProfile

    valid_tools = {value for value, _ in Scan.TOOL_CHOICES} | {"both"}
    tool = request.POST.get("tool", "semgrep")
    if tool not in valid_tools:
        return redirect("scans:project_detail", pk=project_id)

    project = get_object_or_404(Project, id=project_id, owner=request.user)
    service = ScanService()

    requested_tools = ("semgrep", "sonarqube") if tool == "both" else (tool,)

    try:
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=project.pk)
            running = set(
                project.scans.filter(status="RUNNING").values_list("tool", flat=True)
            )
            to_create = [t for t in requested_tools if t not in running]
            # One credit per scan actually created. If both tools were
            # requested but one's already running, we only charge for
            # the one we're starting now.
            UserProfile.charge(request.user, cost=len(to_create))
            scans = [
                service._create_running_scan(project, t)
                for t in to_create
            ]
    except InsufficientCreditsError as err:
        messages.error(
            request,
            f"Not enough credits to start this scan "
            f"(needs {err.cost}, have {err.remaining}). "
            f"Ask an admin to top up.",
        )
        return redirect("scans:project_detail", pk=project.pk)

    for scan in scans:
        async_task(
            "scans.tasks.run_scan",
            str(scan.id),
            _build_scan_config(scan.tool, project),
        )

    return redirect("scans:project_detail", pk=project.pk)


def _build_scan_config(tool, project):
    """Per-tool config dict for `ScanService.execute`.

    Semgrep has no per-scan config; its adapter just needs a path,
    which the resolver provides. SonarQube needs host + token + the
    per-project sonar_project_key. The resolution order for the
    host/token pair is:

      1. `SonarSettings` singleton row (editable in `/admin/`).
      2. `settings.SONAR_*` from `.env` / environment variables.
      3. Hardcoded fallback (host only; there is no fallback token).

    Each Project has a unique `sonar_project_key` (auto-set on first
    save) that namespaces its findings inside SonarQube, so one shared
    Sonar instance can host every user's scans without collisions.
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