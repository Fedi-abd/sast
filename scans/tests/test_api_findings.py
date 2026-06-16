"""Tests for the cross-project findings endpoint.

GET /api/findings/ backs the SPA's Vulnerabilities triage page.
Coverage:
  - User scoping (Alice cannot see Bob's findings).
  - Only SUCCESS scans contribute findings.
  - Severity filter accepts single + comma-separated values.
  - `project_id` filter scopes to one project.
  - Ordering by recency, severity, project name.
  - `limit` caps the row count; non-positive or garbage limits → 400.
  - Response includes project + scan context.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from scans.models import Finding, Project, Scan


def _make(scan, severity="HIGH", message="m", owasp="A1:2017-Injection"):
    return Finding.objects.create(
        scan=scan,
        tool="semgrep",
        rule_id="r",
        severity=severity,
        file_path="x.py",
        line_number=1,
        message=message,
        owasp_category=owasp,
        raw={},
    )


def _sonar(scan, ftype, severity="HIGH"):
    return Finding.objects.create(
        scan=scan,
        tool="sonarqube",
        rule_id="r",
        severity=severity,
        file_path="x",
        line_number=1,
        message="m",
        owasp_category="",
        raw={"type": ftype},
    )


class CrossProjectFindingsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.bob = User.objects.create_user(username="bob", password="p")
        self.client.force_login(self.alice)
        self.url = reverse("findings")

        self.alice_p1 = Project.objects.create(
            name="DVPWA", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        self.alice_p2 = Project.objects.create(
            name="WebGoat", owner=self.alice, source_type="local", repo_path="/tmp/y",
        )
        self.bob_p = Project.objects.create(
            name="Bob's app", owner=self.bob, source_type="local", repo_path="/tmp/z",
        )

        self.alice_scan_1 = Scan.objects.create(
            project=self.alice_p1, tool="semgrep", status="SUCCESS",
        )
        self.alice_scan_2 = Scan.objects.create(
            project=self.alice_p2, tool="sonarqube", status="SUCCESS",
        )
        self.bob_scan = Scan.objects.create(
            project=self.bob_p, tool="semgrep", status="SUCCESS",
        )

        # Alice: 2 HIGH in DVPWA, 1 MEDIUM and 1 LOW in WebGoat. Bob: 1 HIGH.
        _make(self.alice_scan_1, severity="HIGH")
        _make(self.alice_scan_1, severity="HIGH")
        _make(self.alice_scan_2, severity="MEDIUM")
        _make(self.alice_scan_2, severity="LOW")
        _make(self.bob_scan, severity="HIGH")

    def test_anonymous_request_rejected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_user_scoped_returns_only_alices_findings(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Alice has 4, Bob has 1, total in DB = 5. Alice's response: 4.
        self.assertEqual(len(body), 4)
        project_names = {row["project_name"] for row in body}
        self.assertEqual(project_names, {"DVPWA", "WebGoat"})

    def test_failed_scans_excluded(self):
        failed = Scan.objects.create(
            project=self.alice_p1, tool="semgrep", status="FAILED",
        )
        _make(failed, severity="HIGH")  # would never happen in practice
        body = self.client.get(self.url).json()
        # Still 4; the failed-scan finding doesn't appear.
        self.assertEqual(len(body), 4)

    def test_severity_filter_single(self):
        body = self.client.get(self.url + "?severity=HIGH").json()
        self.assertEqual(len(body), 2)
        self.assertTrue(all(row["severity"] == "HIGH" for row in body))

    def test_severity_filter_comma_separated(self):
        body = self.client.get(self.url + "?severity=HIGH,LOW").json()
        self.assertEqual(len(body), 3)
        severities = {row["severity"] for row in body}
        self.assertEqual(severities, {"HIGH", "LOW"})

    def test_severity_filter_ignores_unknown_values(self):
        # `garbage` is dropped; HIGH remains as the only valid value.
        body = self.client.get(self.url + "?severity=garbage,HIGH").json()
        self.assertEqual(len(body), 2)
        self.assertTrue(all(row["severity"] == "HIGH" for row in body))

    def test_project_id_filter(self):
        body = self.client.get(
            self.url + f"?project_id={self.alice_p1.id}"
        ).json()
        self.assertEqual(len(body), 2)
        self.assertTrue(all(row["project_name"] == "DVPWA" for row in body))

    def test_response_includes_project_and_scan_context(self):
        body = self.client.get(self.url).json()
        row = body[0]
        self.assertIn("project_id", row)
        self.assertIn("project_name", row)
        self.assertIn("scan_id", row)
        self.assertIn("detected_at", row)

    def test_ordering_by_project_name(self):
        body = self.client.get(self.url + "?ordering=project").json()
        names_in_order = [row["project_name"] for row in body]
        # DVPWA's "D" < WebGoat's "W", so all DVPWA rows first.
        self.assertEqual(names_in_order, sorted(names_in_order))


class ScanFindingsPaginationTests(TestCase):
    """Same envelope mechanics on the per-scan findings action."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="paged", password="p")
        self.client.force_login(self.user)
        project = Project.objects.create(
            name="Big", owner=self.user, source_type="local", repo_path="/tmp/p",
        )
        self.scan = Scan.objects.create(
            project=project, tool="semgrep", status="SUCCESS",
        )
        _make(self.scan, severity="HIGH")
        _make(self.scan, severity="HIGH")
        _make(self.scan, severity="MEDIUM", owasp="")
        self.url = reverse("scan-findings", kwargs={"pk": self.scan.pk})

    def test_plain_get_returns_full_legacy_array(self):
        body = self.client.get(self.url).json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 3)

    def test_limit_returns_envelope_with_whole_scan_counts(self):
        body = self.client.get(self.url + "?severity=HIGH&limit=1").json()
        self.assertEqual(len(body["results"]), 1)
        # total counts AFTER the filter; severity_counts cover the scan.
        self.assertEqual(body["total"], 2)
        self.assertEqual(
            body["severity_counts"], {"HIGH": 2, "MEDIUM": 1, "LOW": 0},
        )

    def test_owasp_unmapped_filter(self):
        body = self.client.get(self.url + "?owasp=UNMAPPED&limit=10").json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["results"][0]["severity"], "MEDIUM")

    def test_bad_pagination_rejected(self):
        for query in ("?limit=abc", "?limit=0", "?offset=-1"):
            response = self.client.get(self.url + query)
            self.assertEqual(response.status_code, 400, msg=query)

    def test_limit_returns_envelope(self):
        body = self.client.get(self.url + "?limit=2").json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["total"], 3)
        self.assertEqual(
            body["severity_counts"], {"HIGH": 2, "MEDIUM": 1, "LOW": 0},
        )
        self.assertTrue(any(
            row["category"] == "A1:2017-Injection" for row in body["owasp_counts"]
        ))

    def test_limit_larger_than_result_set_is_harmless(self):
        body = self.client.get(self.url + "?limit=999").json()
        self.assertEqual(len(body["results"]), 3)

    def test_offset_pages_without_overlap(self):
        page1 = self.client.get(self.url + "?limit=2&offset=0").json()
        page2 = self.client.get(self.url + "?limit=2&offset=2").json()
        ids1 = {row["id"] for row in page1["results"]}
        ids2 = {row["id"] for row in page2["results"]}
        self.assertEqual(len(ids1 & ids2), 0)
        self.assertEqual(len(ids1 | ids2), 3)

    def test_owasp_filter_applies_to_plain_array_too(self):
        _make(self.scan, severity="LOW", owasp="A2:2017-Broken Authentication")
        body = self.client.get(
            self.url + "?owasp=A2:2017-Broken Authentication"
        ).json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["severity"], "LOW")


class ScanFindingsTypeFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="typer", password="p")
        self.client.force_login(self.user)
        project = Project.objects.create(
            name="S", owner=self.user, source_type="local", repo_path="/tmp/s",
        )
        self.scan = Scan.objects.create(
            project=project, tool="sonarqube", status="SUCCESS",
        )
        _sonar(self.scan, "VULNERABILITY")
        _sonar(self.scan, "VULNERABILITY")
        _sonar(self.scan, "SECURITY_HOTSPOT")
        _sonar(self.scan, "BUG")
        _sonar(self.scan, "CODE_SMELL")
        self.url = reverse("scan-findings", kwargs={"pk": self.scan.pk})

    def test_type_counts_tally_the_whole_scan(self):
        body = self.client.get(self.url + "?limit=10").json()
        counts = {row["type"]: row["count"] for row in body["type_counts"]}
        self.assertEqual(
            counts,
            {"VULNERABILITY": 2, "SECURITY_HOTSPOT": 1, "BUG": 1, "CODE_SMELL": 1},
        )

    def test_type_filter_single(self):
        body = self.client.get(self.url + "?type=VULNERABILITY&limit=10").json()
        self.assertEqual(body["total"], 2)

    def test_type_filter_comma_separated(self):
        body = self.client.get(
            self.url + "?type=VULNERABILITY,SECURITY_HOTSPOT&limit=10"
        ).json()
        self.assertEqual(body["total"], 3)

    def test_type_filter_applies_to_plain_array(self):
        body = self.client.get(self.url + "?type=BUG").json()
        self.assertEqual(len(body), 1)

    def test_semgrep_scan_has_empty_type_counts(self):
        project = Project.objects.create(
            name="SG", owner=self.user, source_type="local", repo_path="/tmp/sg",
        )
        sg = Scan.objects.create(project=project, tool="semgrep", status="SUCCESS")
        _make(sg, severity="HIGH")
        url = reverse("scan-findings", kwargs={"pk": sg.pk})
        body = self.client.get(url + "?limit=10").json()
        self.assertEqual(body["type_counts"], [])

    def test_type_scopes_the_rollups(self):
        allc = self.client.get(self.url + "?limit=10").json()
        self.assertEqual(allc["visible_total"], 5)
        self.assertEqual(allc["severity_counts"]["HIGH"], 5)
        vuln = self.client.get(self.url + "?type=VULNERABILITY&limit=10").json()
        self.assertEqual(vuln["visible_total"], 2)
        self.assertEqual(vuln["severity_counts"]["HIGH"], 2)

    def test_admin_can_hide_hotspots_everywhere(self):
        from scans.models import SonarSettings
        row = SonarSettings.get_solo()
        row.include_hotspots = False
        row.save()
        body = self.client.get(self.url + "?limit=10").json()
        types = {t["type"] for t in body["type_counts"]}
        self.assertNotIn("SECURITY_HOTSPOT", types)   # gone from the burger
        self.assertEqual(body["visible_total"], 4)    # 5 minus the 1 hotspot


class SolveFindingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="solver", password="p")
        self.other = User.objects.create_user(username="other", password="p")
        self.client.force_login(self.user)
        project = Project.objects.create(
            name="S", owner=self.user, source_type="local", repo_path="/tmp/s",
        )
        self.scan = Scan.objects.create(
            project=project, tool="semgrep", status="SUCCESS",
        )
        self.f1 = _make(self.scan, severity="HIGH")
        self.f2 = _make(self.scan, severity="MEDIUM")
        self.list_url = reverse("scan-findings", kwargs={"pk": self.scan.pk})

    def _solve_url(self, finding):
        return reverse("finding-solve", kwargs={"finding_id": finding.id})

    def test_marks_solved(self):
        r = self.client.post(self._solve_url(self.f1), {"solved": True}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["solved"])
        self.f1.refresh_from_db()
        self.assertTrue(self.f1.solved)

    def test_defaults_to_solved_true(self):
        self.client.post(self._solve_url(self.f1), {}, content_type="application/json")
        self.f1.refresh_from_db()
        self.assertTrue(self.f1.solved)

    def test_unsolve(self):
        self.f1.solved = True
        self.f1.save()
        self.client.post(self._solve_url(self.f1), {"solved": False}, content_type="application/json")
        self.f1.refresh_from_db()
        self.assertFalse(self.f1.solved)

    def test_solved_excluded_from_list_but_counted(self):
        self.f1.solved = True
        self.f1.save()
        body = self.client.get(self.list_url + "?limit=10").json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["visible_total"], 2)
        self.assertEqual(body["solved_count"], 1)
        ids = {row["id"] for row in body["results"]}
        self.assertNotIn(str(self.f1.id), ids)

    def test_solved_excluded_from_rollups(self):
        # f1 is the only HIGH; solving it drops HIGH from the tiles but
        # leaves it in visible_total so "N/M solved" stays honest.
        self.f1.solved = True
        self.f1.save()
        body = self.client.get(self.list_url + "?limit=10").json()
        self.assertEqual(body["severity_counts"]["HIGH"], 0)
        self.assertEqual(body["severity_counts"]["MEDIUM"], 1)
        self.assertEqual(body["visible_total"], 2)
        self.assertEqual(body["solved_count"], 1)

    def test_other_user_cannot_solve(self):
        self.client.force_login(self.other)
        r = self.client.post(self._solve_url(self.f1))
        self.assertEqual(r.status_code, 404)
