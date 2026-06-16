"""Tests for GET /api/dashboard/.

Covers the response shape, user scoping, and the "this week" cutoff.
Doesn't test the OWASP top-N truncation edge case explicitly because
N=10 is high relative to the 10 OWASP 2017 categories, so in practice
the full distribution always fits.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from scans.models import Finding, Project, Scan


def _make_finding(scan, severity="HIGH", owasp="A1:2017-Injection"):
    return Finding.objects.create(
        scan=scan,
        tool="semgrep",
        rule_id="r",
        severity=severity,
        file_path="x.py",
        line_number=1,
        message="m",
        owasp_category=owasp,
        raw={},
    )


class DashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.bob = User.objects.create_user(username="bob", password="p")
        self.client.force_login(self.alice)
        self.url = reverse("dashboard")

    def test_anonymous_request_rejected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_empty_dashboard_returns_zeros(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["totals"]["projects"], 0)
        self.assertEqual(body["totals"]["scans"], 0)
        self.assertEqual(body["totals"]["scans_this_week"], 0)
        self.assertEqual(body["totals"]["open_findings"], 0)
        self.assertEqual(body["owasp_distribution"], [])
        self.assertEqual(body["recent_activity"], [])

    def test_totals_are_user_scoped(self):
        # Alice has 2 projects + 3 scans + 4 findings.
        # Bob has 5 projects + 7 scans + 9 findings.
        # Alice's dashboard must see only her own counts.
        for i in range(2):
            p = Project.objects.create(
                name=f"a{i}", owner=self.alice, source_type="local", repo_path="/tmp/x",
            )
        for _ in range(3):
            scan = Scan.objects.create(project=p, tool="semgrep", status="SUCCESS")
        for _ in range(4):
            _make_finding(scan)

        for i in range(5):
            bp = Project.objects.create(
                name=f"b{i}", owner=self.bob, source_type="local", repo_path="/tmp/x",
            )
        for _ in range(7):
            bs = Scan.objects.create(project=bp, tool="semgrep", status="SUCCESS")
        for _ in range(9):
            _make_finding(bs)

        body = self.client.get(self.url).json()
        self.assertEqual(body["totals"]["projects"], 2)
        self.assertEqual(body["totals"]["scans"], 3)
        self.assertEqual(body["totals"]["open_findings"], 4)

    def test_scans_this_week_uses_seven_day_cutoff(self):
        project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        # auto_now_add fires `started_at = now`. To simulate "8 days
        # ago", patch the timestamp post-create.
        old_scan = Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        Scan.objects.filter(pk=old_scan.pk).update(
            started_at=timezone.now() - timedelta(days=8),
        )
        Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        Scan.objects.create(project=project, tool="sonarqube", status="SUCCESS")

        body = self.client.get(self.url).json()
        self.assertEqual(body["totals"]["scans"], 3)          # all-time
        self.assertEqual(body["totals"]["scans_this_week"], 2)  # last 7d

    def test_failed_scans_excluded_from_open_findings(self):
        # Findings only exist on a scan if it succeeded; counting
        # failed scans toward `open_findings` would muddy the metric.
        project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        ok_scan = Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        failed_scan = Scan.objects.create(project=project, tool="semgrep", status="FAILED")
        _make_finding(ok_scan)
        _make_finding(failed_scan)  # would never happen in practice
        body = self.client.get(self.url).json()
        self.assertEqual(body["totals"]["open_findings"], 1)

    def test_owasp_distribution_aggregates_and_sorts_desc(self):
        project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        scan = Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        for _ in range(3):
            _make_finding(scan, owasp="A1:2017-Injection")
        for _ in range(5):
            _make_finding(scan, owasp="A7:2017-Cross-Site Scripting (XSS)")
        for _ in range(1):
            _make_finding(scan, owasp="")  # UNMAPPED

        body = self.client.get(self.url).json()
        # XSS should come first (5), then injection (3), then UNMAPPED (1).
        counts = [(r["category"], r["count"]) for r in body["owasp_distribution"]]
        self.assertEqual(counts, [
            ("A7:2017-Cross-Site Scripting (XSS)", 5),
            ("A1:2017-Injection", 3),
            ("UNMAPPED", 1),
        ])

    def test_recent_activity_includes_finding_count_and_status(self):
        project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        scan = Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        _make_finding(scan)
        _make_finding(scan)
        body = self.client.get(self.url).json()
        self.assertEqual(len(body["recent_activity"]), 1)
        entry = body["recent_activity"][0]
        self.assertEqual(entry["project_name"], "P")
        self.assertEqual(entry["tool"], "semgrep")
        self.assertEqual(entry["tool_display"], "Semgrep")
        self.assertEqual(entry["status"], "SUCCESS")
        self.assertEqual(entry["finding_count"], 2)

    def test_recent_activity_limit_is_enforced(self):
        # Create more scans than the limit so the response must truncate.
        project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        for _ in range(8):
            Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        body = self.client.get(self.url).json()
        # Hardcoded `[:5]` slice in DashboardView.get.
        self.assertEqual(len(body["recent_activity"]), 5)
