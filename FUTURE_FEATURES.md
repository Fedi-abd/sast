# Future Features

Planned and proposed work, grouped by area. Items here are explicitly
**not** in the current shipping scope — they're either next-up or
ideas worth keeping a list of.

(Sprint 4 in-progress items are tracked separately — see the
sprint plan, not this file.)

---

## Reporting

- **Cross-project dashboard** — KPI cards (total projects, total scans,
  scans-this-week, most-frequent OWASP category), recent-activity table,
  OWASP distribution chart aggregated across the user's projects.
  Templated UI, charts via Chart.js or similar.

## Scan execution

- **Scan-result caching / change detection** — before running, compute
  a hash of the source (commit SHA for git, archive hash for upload,
  content hash for local). If a successful scan with the same hash
  already exists for this project + tool, redirect to that scan
  instead of re-running. Saves time on repeated clicks; falls through
  to a real scan whenever the source actually changed.

## SonarQube polish

- **Per-user Sonar token override** — currently the platform-level
  token in `.env` / SonarSettings authenticates all users. A per-user
  `User.sonar_token` profile field would let users with their own
  Sonar instance override.
- **Pull Reliability + Maintainability findings into the main UI** —
  already supported in storage via `SAST_SONAR_ISSUE_TYPES`, but no UI
  exists to view them as separate categories. Sprint 4 PDF report
  exposes them via a toggle, but the main scan-detail page doesn't.

## Semgrep polish

- **Semgrep rule selector** — let users choose which Semgrep ruleset
  to run when triggering a scan (`p/security`, `p/owasp-top-10`,
  `p/python`, `auto`, custom). Currently hardcoded to `auto` via the
  adapter's `ruleset` config key.

## Auth & accounts

- **Templated password-reset flow** — Django's stock views are wired
  but no email backend is configured.

## Misc cleanup

- **Move legacy tests** from `scans/migrations/tests/` to
  `scans/tests/`. Functionally fine where they are, but the location
  risks colliding with future migration files.
- **Drop the unused `python-sonarqube-api` dependency** — pinned in
  `requirements.txt` but the SonarAdapter rolls its own `requests`.
- **`ALLOWED_HOSTS = ['*']`** — fine for dev, tighten before any
  non-local deployment.
- **Drop the empty `core/` Django app** — sits in `INSTALLED_APPS`
  doing nothing. Q12 resolved as "keep for now"; revisit if it stays
  empty through Sprint 4.
