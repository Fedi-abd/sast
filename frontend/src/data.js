/* ============================================================
   Mock data — shaped to match api-contract.md exactly.
   Replace each export with a real fetch() in implementation.
   ============================================================ */

/* GET /api/me/  (is_staff flips the admin nav + /settings access on) */
export const ME = {
  id: 1,
  username: "peli",
  email: "peli@univ-alger.dz",
  is_staff: true,
  credits: 6,
};

/* GET /api/projects/  — lean list, newest first.
   No scan/severity data here — cards JOIN the latest scan client-side. */
export const PROJECTS = [
  { id: "p-7c14", name: "core-auth-service", language: "Go",     source_type: "git",    source_type_display: "Git repository",   git_url: "https://github.com/org/core-auth-service", git_branch: "main", created_at: "2026-05-21T09:14:00Z" },
  { id: "p-9a02", name: "webgoat-repo",      language: "Java",   source_type: "git",    source_type_display: "Git repository",   git_url: "https://github.com/WebGoat/WebGoat", git_branch: "main", created_at: "2026-05-06T11:20:00Z" },
  { id: "p-3f51", name: "dvpwa-test",        language: "Python", source_type: "local",  source_type_display: "Local path",       repo_path: "/repo/security/dvpwa", created_at: "2026-05-05T16:02:00Z" },
  { id: "p-5b88", name: "vendor-lib-bundle", language: "Python", source_type: "upload", source_type_display: "Uploaded archive", source_archive: "vendor-lib-bundle-v2.1.zip", created_at: "2026-05-05T08:40:00Z" },
  { id: "p-1c20", name: "hello-world",       language: "JavaScript", source_type: "git", source_type_display: "Git repository",  git_url: "https://github.com/org/hello-world", git_branch: "main", created_at: "2026-05-05T10:00:00Z" },
];

/* GET /api/scans/  — status ∈ SUCCESS | RUNNING | FAILED (execution, not severity).
   duration_seconds: int   finding_count: int (total; no severity split here) */
export const SCANS = [
  { id: "s-2041", project_id: "p-5b88", project_name: "vendor-lib-bundle", tool: "semgrep",   tool_display: "Semgrep",   status: "RUNNING", started_at: "2026-06-09T15:09:00Z", finished_at: null,                    duration_seconds: null, finding_count: null, error_message: "" },
  { id: "s-2040", project_id: "p-3f51", project_name: "dvpwa-test",        tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", started_at: "2026-06-09T15:02:00Z", finished_at: "2026-06-09T15:02:45Z", duration_seconds: 45,   finding_count: 10,  error_message: "" },
  { id: "s-2039", project_id: "p-3f51", project_name: "dvpwa-test",        tool: "sonarqube", tool_display: "SonarQube", status: "SUCCESS", started_at: "2026-06-09T14:54:00Z", finished_at: "2026-06-09T14:55:12Z", duration_seconds: 72,   finding_count: 15,  error_message: "" },
  { id: "s-2037", project_id: "p-3f51", project_name: "dvpwa-test",        tool: "semgrep",   tool_display: "Semgrep",   status: "FAILED",  started_at: "2026-06-08T09:15:00Z", finished_at: "2026-06-08T09:15:12Z", duration_seconds: 12,   finding_count: null, error_message: "timeout: ruleset compile exceeded 10s" },
  { id: "s-2034", project_id: "p-7c14", project_name: "core-auth-service", tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", started_at: "2026-06-09T13:14:00Z", finished_at: "2026-06-09T13:14:51Z", duration_seconds: 51,   finding_count: 17,  error_message: "" },
  { id: "s-2030", project_id: "p-9a02", project_name: "webgoat-repo",      tool: "sonarqube", tool_display: "SonarQube", status: "SUCCESS", started_at: "2026-06-06T09:40:00Z", finished_at: "2026-06-06T09:42:04Z", duration_seconds: 124,  finding_count: 22,  error_message: "" },
  { id: "s-2025", project_id: "p-1c20", project_name: "hello-world",       tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", started_at: "2026-06-09T11:00:00Z", finished_at: "2026-06-09T11:00:08Z", duration_seconds: 8,    finding_count: 1,   error_message: "" },
];

/* GET /api/scans/<id>/findings/  — severity-sorted, HIGH first. Keyed by scan_id. */
export const FINDINGS_BY_SCAN = {
  "s-2040": [
    { id: "f-001", tool: "semgrep", rule_id: "python.lang.security.audit.dangerous-sql-string-concat", severity: "HIGH",   severity_display: "High",   file_path: "sqli/dao/user.py",        line_number: 42, message: "Detected SQL statement built with string concatenation of untrusted input. Use parameterised queries instead.", cwe_id: "CWE-89",  owasp_category: "A1:2017-Injection",                       confidence_score: 1.0 },
    { id: "f-002", tool: "semgrep", rule_id: "python.flask.security.audit.hardcoded-secret",            severity: "HIGH",   severity_display: "High",   file_path: "config/settings.py",      line_number: 12, message: "Hardcoded secret assigned to a configuration variable. Move to an environment variable or secret store and rotate the value.", cwe_id: "CWE-798", owasp_category: "A2:2017-Broken Authentication",          confidence_score: 0.9 },
    { id: "f-003", tool: "semgrep", rule_id: "python.django.security.audit.xss.template-autoescape-off", severity: "MEDIUM", severity_display: "Medium", file_path: "sqli/views/profile.py",    line_number: 28, message: "Reflected value rendered with autoescape disabled. Escape on output or enable autoescaping.", cwe_id: "CWE-79",  owasp_category: "A7:2017-Cross-Site Scripting (XSS)",     confidence_score: 0.8 },
    { id: "f-004", tool: "semgrep", rule_id: "python.lang.security.audit.outdated-dependency",           severity: "MEDIUM", severity_display: "Medium", file_path: "requirements.txt",         line_number: 7,  message: "Dependency 'jinja2==2.10' has a known vulnerability (CVE-2020-28493). Upgrade to a patched release.", cwe_id: "CWE-1104", owasp_category: "A9:2017-Using Components with Known Vulnerabilities", confidence_score: 1.0 },
    { id: "f-005", tool: "semgrep", rule_id: "python.flask.security.audit.debug-enabled",                severity: "LOW",    severity_display: "Low",    file_path: "app.py",                  line_number: 96, message: "Flask app run with debug=True. Disable debug mode in production deployments.", cwe_id: "CWE-489", owasp_category: "A6:2017-Security Misconfiguration",       confidence_score: 0.7 },
  ],
};

/* GET /api/findings/  — cross-project. Flattened with project + scan refs. */
export const FINDINGS = Object.entries(FINDINGS_BY_SCAN).flatMap(([scanId, arr]) => {
  const scan = SCANS.find((s) => s.id === scanId);
  return arr.map((f) => ({
    ...f,
    project_id: scan.project_id,
    project_name: scan.project_name,
    scan_id: scanId,
    detected_at: scan.started_at,
  }));
});

/* GET /api/dashboard/ */
export const DASHBOARD = {
  totals: { projects: 5, scans: 23, scans_this_week: 4, open_findings: 187 },
  owasp_distribution: [
    { category: "A1:2017-Injection", count: 45 },
    { category: "A7:2017-Cross-Site Scripting (XSS)", count: 32 },
    { category: "A2:2017-Broken Authentication", count: 21 },
    { category: "A6:2017-Security Misconfiguration", count: 19 },
    { category: "A9:2017-Using Components with Known Vulnerabilities", count: 14 },
    { category: "UNMAPPED", count: 18 },
  ],
  recent_activity: SCANS.slice(0, 5).map((s) => ({
    scan_id: s.id,
    project_name: s.project_name,
    tool: s.tool,
    tool_display: s.tool_display,
    status: s.status,
    started_at: s.started_at,
    finding_count: s.finding_count,
  })),
};

/* ----- client-side selectors ----- */

export function latestScanFor(projectId) {
  return SCANS
    .filter((s) => s.project_id === projectId)
    .sort((a, b) => new Date(b.started_at) - new Date(a.started_at))[0] || null;
}

export function severityTally(scanId) {
  const arr = FINDINGS_BY_SCAN[scanId] || [];
  return {
    HIGH: arr.filter((f) => f.severity === "HIGH").length,
    MEDIUM: arr.filter((f) => f.severity === "MEDIUM").length,
    LOW: arr.filter((f) => f.severity === "LOW").length,
  };
}

/* ============================================================
   ADMIN — staff-only (gated on ME.is_staff). Track 5 endpoints,
   not yet in api-contract.md; these are the shapes the implementer
   should target under /api/admin/*. Mock only.
   ============================================================ */

/* GET/PUT /api/admin/sonarqube/  — single shared config, not per-user.
   The API NEVER returns the full token, only token_last4. */
export const ADMIN_SONARQUBE = {
  host: "https://sonarqube.acme.internal",
  token_last4: "8f2a",
  has_token: true,
  issue_types: ["VULNERABILITY", "SECURITY_HOTSPOT"],
  updated_at: "2026-06-01T09:12:00Z",
  updated_by: "alice",
};
export const SONAR_ISSUE_TYPES = ["VULNERABILITY", "BUG", "CODE_SMELL", "SECURITY_HOTSPOT"];

/* GET/PATCH /api/admin/limits/  — one row per user. Integers, ≥ 0. */
export const ADMIN_LIMITS = [
  { user_id: 1, username: "peli",        credits: 6,   max_projects: 25, max_upload_mb: 500 },
  { user_id: 2, username: "alice",       credits: 100, max_projects: 50, max_upload_mb: 500 },
  { user_id: 3, username: "bouchra",     credits: 40,  max_projects: 10, max_upload_mb: 200 },
  { user_id: 4, username: "yacine",      credits: 25,  max_projects: 10, max_upload_mb: 200 },
  { user_id: 5, username: "karim",       credits: 10,  max_projects: 3,  max_upload_mb: 100 },
  { user_id: 6, username: "nadia",       credits: 40,  max_projects: 10, max_upload_mb: 200 },
  { user_id: 7, username: "ci-bot",      credits: 500, max_projects: 5,  max_upload_mb: 500 },
  { user_id: 8, username: "intern-2024", credits: 0,   max_projects: 0,  max_upload_mb: 0   },
];

/* GET /api/admin/usage/  — recent scans across ALL users (audit lens).
   Read-only, newest first. Same scan shape, plus username. */
export const ADMIN_USAGE = [
  { id: "s-2041", username: "peli",    project_name: "vendor-lib-bundle", tool: "semgrep",   tool_display: "Semgrep",   status: "RUNNING", duration_seconds: null, finding_count: null, started_at: "2026-06-09T15:09:00Z" },
  { id: "s-2040", username: "peli",    project_name: "dvpwa-test",        tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 45,   finding_count: 10,   started_at: "2026-06-09T15:02:00Z" },
  { id: "s-3105", username: "alice",   project_name: "payments-api",      tool: "sonarqube", tool_display: "SonarQube", status: "SUCCESS", duration_seconds: 212,  finding_count: 34,   started_at: "2026-06-09T14:40:00Z" },
  { id: "s-3104", username: "bouchra", project_name: "mobile-gateway",    tool: "semgrep",   tool_display: "Semgrep",   status: "FAILED",  duration_seconds: 9,    finding_count: null, started_at: "2026-06-09T14:05:00Z" },
  { id: "s-3101", username: "yacine",  project_name: "billing-worker",    tool: "sonarqube", tool_display: "SonarQube", status: "SUCCESS", duration_seconds: 158,  finding_count: 7,    started_at: "2026-06-09T13:22:00Z" },
  { id: "s-2034", username: "peli",    project_name: "core-auth-service", tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 51,   finding_count: 17,   started_at: "2026-06-09T13:14:00Z" },
  { id: "s-3098", username: "karim",   project_name: "legacy-php-shop",   tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 88,   finding_count: 61,   started_at: "2026-06-09T11:48:00Z" },
  { id: "s-3097", username: "nadia",   project_name: "data-pipeline",     tool: "both",      tool_display: "Semgrep + SonarQube", status: "SUCCESS", duration_seconds: 304, finding_count: 12, started_at: "2026-06-09T11:10:00Z" },
  { id: "s-2025", username: "peli",    project_name: "hello-world",       tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 8,    finding_count: 1,    started_at: "2026-06-09T11:00:00Z" },
  { id: "s-3090", username: "ci-bot",  project_name: "core-auth-service", tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 49,   finding_count: 16,   started_at: "2026-06-09T06:00:00Z" },
  { id: "s-3088", username: "alice",   project_name: "payments-api",      tool: "semgrep",   tool_display: "Semgrep",   status: "FAILED",  duration_seconds: 14,   finding_count: null, started_at: "2026-06-08T22:31:00Z" },
  { id: "s-3085", username: "karim",   project_name: "legacy-php-shop",   tool: "sonarqube", tool_display: "SonarQube", status: "SUCCESS", duration_seconds: 401,  finding_count: 143,  started_at: "2026-06-08T17:55:00Z" },
  { id: "s-3081", username: "bouchra", project_name: "mobile-gateway",    tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 63,   finding_count: 9,    started_at: "2026-06-08T15:12:00Z" },
  { id: "s-3072", username: "ci-bot",  project_name: "data-pipeline",     tool: "semgrep",   tool_display: "Semgrep",   status: "SUCCESS", duration_seconds: 52,   finding_count: 4,    started_at: "2026-06-08T06:00:00Z" },
];

/* GET /api/admin/users/  — user management roster. */
export const ADMIN_USERS = [
  { id: 1, username: "peli",        email: "peli@univ-alger.dz",  is_staff: true,  is_active: true  },
  { id: 2, username: "alice",       email: "alice@acme.dev",      is_staff: true,  is_active: true  },
  { id: 3, username: "bouchra",     email: "bouchra@acme.dev",    is_staff: false, is_active: true  },
  { id: 4, username: "yacine",      email: "yacine@acme.dev",     is_staff: false, is_active: true  },
  { id: 5, username: "karim",       email: "karim@contractor.io", is_staff: false, is_active: true  },
  { id: 6, username: "nadia",       email: "nadia@acme.dev",      is_staff: false, is_active: true  },
  { id: 7, username: "ci-bot",      email: "ci@acme.dev",         is_staff: false, is_active: true  },
  { id: 8, username: "intern-2024", email: "sam@acme.dev",        is_staff: false, is_active: false },
];

/* GET/PATCH /api/admin/settings/  — deployment flags (booleans). */
export const ADMIN_DEPLOYMENT = {
  hide_local_source: true,
  show_debug_ui: false,
};
