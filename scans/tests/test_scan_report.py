"""Tests for the scan-report PDF endpoint.

The PDF generation service is mocked in view tests because WeasyPrint
links against GTK libraries the Windows test venv doesn't have. The
view-level mocks confirm the API surface; the template-level tests
confirm the rendering, no WeasyPrint involved on either path.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from scans.models import Finding, Project, Scan
from scans.services.report_service import _report_stats, _sonar_types_present


def _make(scan, severity="HIGH", owasp="A1:2017-Injection"):
    f = Finding.objects.create(
        scan=scan,
        tool="semgrep",
        rule_id="r",
        severity=severity,
        file_path="x.py",
        line_number=1,
        message="m",
        owasp_category=owasp,
        cwe_id="CWE-89",
        raw={},
    )
    # The real service attaches this attribute before rendering;
    # template tests use the same factory so we mirror it here.
    f.display_recommendation = "Voir la documentation de la règle."
    return f


class ScanReportPDFViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.bob = User.objects.create_user(username="bob", password="p")
        self.client.force_login(self.alice)

        self.project = Project.objects.create(
            name="P", owner=self.alice, source_type="local", repo_path="/tmp/x",
        )
        self.scan = Scan.objects.create(
            project=self.project, tool="semgrep", status="SUCCESS",
        )
        _make(self.scan, severity="HIGH")

        self.url = reverse("scan-report", kwargs={"scan_id": self.scan.id})

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_returns_pdf_response(self, mock_gen):
        mock_gen.return_value = b"%PDF-fake-bytes%"
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(str(self.scan.id), response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-fake-bytes%")

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_accepts_application_pdf_accept_header(self, mock_gen):
        # The SPA's blob fetch sends Accept: application/pdf. The endpoint
        # used to 406 on it (no matching renderer), which broke export.
        mock_gen.return_value = b"%PDF%"
        response = self.client.get(self.url, HTTP_ACCEPT="application/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.content, b"%PDF%")

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_service_called_with_correct_scan(self, mock_gen):
        mock_gen.return_value = b"%PDF%"
        self.client.get(self.url)
        # The first positional arg is the scan object itself.
        args, kwargs = mock_gen.call_args
        self.assertEqual(args[0].id, self.scan.id)
        self.assertIsNone(kwargs.get("severities"))

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_severity_scope_passes_through(self, mock_gen):
        mock_gen.return_value = b"%PDF%"
        self.client.get(self.url + "?severity=HIGH,MEDIUM")
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["severities"], {"HIGH", "MEDIUM"})

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_unknown_severity_is_ignored(self, mock_gen):
        mock_gen.return_value = b"%PDF%"
        self.client.get(self.url + "?severity=BOGUS")
        _, kwargs = mock_gen.call_args
        self.assertIsNone(kwargs["severities"])

    @patch("scans.services.report_service.generate_scan_report_pdf")
    def test_alice_cannot_download_bobs_report(self, mock_gen):
        bobs_project = Project.objects.create(
            name="Bob's", owner=self.bob, source_type="local", repo_path="/tmp/b",
        )
        bobs_scan = Scan.objects.create(
            project=bobs_project, tool="semgrep", status="SUCCESS",
        )
        url = reverse("scan-report", kwargs={"scan_id": bobs_scan.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        mock_gen.assert_not_called()

    def test_anonymous_request_rejected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))


class ScanReportTemplateTests(TestCase):
    """Template-only tests. Don't touch the WeasyPrint boundary."""

    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="t", password="p")
        self.project = Project.objects.create(
            name="DVPWA", owner=user, language="Python",
            source_type="local", repo_path="/tmp/x",
        )
        self.scan = Scan.objects.create(
            project=self.project, tool="semgrep", status="SUCCESS",
        )

    def _render(self, findings, scope_label=None, sonar_types=None):
        return render_to_string("scans/scan_report.html", {
            "scan": self.scan,
            "findings": findings,
            "total_findings": len(findings),
            "generated_at": timezone.now(),
            "scope_label": scope_label,
            "sonar_types": sonar_types or [],
            "pdf_css_url": "",
            **_report_stats(findings),
        })

    def test_renders_with_zero_findings(self):
        html = self._render([])
        self.assertIn("Aucune vulnérabilité", html)
        self.assertIn(self.project.name, html)

    def test_renders_six_column_headers(self):
        finding = _make(self.scan, severity="HIGH")
        html = self._render([finding])
        for header in (
            "Référence vuln", "Nom de vuln", "Description",
            "Preuve", "Référence", "Recommandation",
        ):
            self.assertIn(header, html)

    def test_severity_pills_match_finding_severities(self):
        findings = [
            _make(self.scan, severity="HIGH"),
            _make(self.scan, severity="MEDIUM"),
            _make(self.scan, severity="LOW"),
        ]
        html = self._render(findings)
        self.assertIn('class="sev-pill high"', html)
        self.assertIn('class="sev-pill medium"', html)
        self.assertIn('class="sev-pill low"', html)

    def test_cover_shows_scope_label_only_when_filtered(self):
        html_all = self._render([_make(self.scan, severity="HIGH")])
        self.assertNotIn("Périmètre du rapport", html_all)
        html_scoped = self._render([_make(self.scan, severity="HIGH")], scope_label="HIGH")
        self.assertIn("Périmètre du rapport : sévérité HIGH", html_scoped)

    def test_renders_owasp_distribution_and_mapping_rate(self):
        findings = [
            _make(self.scan, severity="HIGH", owasp="A1:2017-Injection"),
            _make(self.scan, severity="MEDIUM", owasp="A1:2017-Injection"),
            _make(self.scan, severity="LOW", owasp=""),
        ]
        html = self._render(findings)
        self.assertIn("Répartition OWASP", html)
        self.assertIn("A1:2017-Injection", html)
        self.assertIn("UNMAPPED", html)
        # 2 of 3 findings mapped -> 67%
        self.assertIn("Taux de classification : 67%", html)

    def test_renders_appendix_with_limits(self):
        html = self._render([_make(self.scan, severity="HIGH")])
        self.assertIn("Annexe", html)
        self.assertIn("Limites de l'analyse", html)
        self.assertIn("Analyse statique uniquement", html)

    def test_cover_shows_overall_risk(self):
        html = self._render([
            _make(self.scan, severity="HIGH"),
            _make(self.scan, severity="LOW"),
        ])
        self.assertIn("Risque global", html)

    def test_names_sonar_types_when_present(self):
        html = self._render(
            [_make(self.scan, severity="HIGH")],
            sonar_types=["SECURITY_HOTSPOT", "VULNERABILITY"],
        )
        self.assertIn("Types de remontées SonarQube inclus", html)
        self.assertIn("SECURITY_HOTSPOT, VULNERABILITY", html)

    def test_omits_sonar_types_line_when_absent(self):
        html = self._render([_make(self.scan, severity="HIGH")])
        self.assertNotIn("Types de remontées SonarQube", html)


class SonarTypesPresentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="s", password="p")
        self.project = Project.objects.create(
            name="P", owner=user, source_type="local", repo_path="/tmp/x",
        )

    def _scan(self, tool):
        return Scan.objects.create(project=self.project, tool=tool, status="SUCCESS")

    def _finding(self, scan, raw):
        return Finding.objects.create(
            scan=scan, tool="sonarqube", rule_id="r", severity="HIGH",
            file_path="x", line_number=1, message="m", raw=raw,
        )

    def test_collects_distinct_types_sorted(self):
        scan = self._scan("sonarqube")
        findings = [
            self._finding(scan, {"type": "VULNERABILITY"}),
            self._finding(scan, {"type": "SECURITY_HOTSPOT"}),
            self._finding(scan, {"type": "VULNERABILITY"}),
        ]
        self.assertEqual(
            _sonar_types_present(scan, findings),
            ["SECURITY_HOTSPOT", "VULNERABILITY"],
        )

    def test_empty_for_semgrep(self):
        scan = self._scan("semgrep")
        findings = [self._finding(scan, {"type": "VULNERABILITY"})]
        self.assertEqual(_sonar_types_present(scan, findings), [])

    def test_skips_rows_without_a_type(self):
        scan = self._scan("sonarqube")
        findings = [
            self._finding(scan, {}),
            self._finding(scan, {"type": "VULNERABILITY"}),
        ]
        self.assertEqual(_sonar_types_present(scan, findings), ["VULNERABILITY"])
