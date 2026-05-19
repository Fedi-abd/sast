# Future Features

Planned and proposed work, grouped by area. Items here are explicitly
**not** in the current shipping scope — they're either next-up or
ideas worth keeping a list of.

---

## Product UI

- **Custom in-platform admin page** — replace the Django admin
  (`/admin/`) with a product-grade settings interface inside the
  platform itself. Django admin is great for development; not the
  right shape for an end-user-facing product. The new admin page
  would hold SonarQube settings, future rule selector, possibly
  user management. Includes turning off `DEBUG=True` for production.
- **Semgrep rule selector** — let users choose which Semgrep ruleset
  to run when triggering a scan (`p/security`, `p/owasp-top-10`,
  `p/python`, `auto`, custom). Currently hardcoded to `auto` via the
  adapter's `ruleset` config key.

## Reporting & dashboard

- **Cross-project dashboard** — KPI cards (total projects, total scans,
  scans-this-week, most-frequent OWASP category), recent-activity table,
  OWASP distribution chart aggregated across the user's projects.
- **PDF report** for individual scans — one-page summary with metadata,
  severity counts, OWASP chart, full findings table. WeasyPrint is the
  intended renderer.
- **Scan-diff view** — given two scans of the same project (or two
  related projects), show what changed: findings resolved, findings new,
  findings unchanged. Demonstrates security improvement over time.

## Scan execution

- **Async scans** — move `ScanService.execute` off the request thread
  via django-q2 or Celery. Scan trigger returns immediately; UI polls
  for completion. Today scans block the HTTP request for the full
  duration.
- **Scan-result caching / change detection** — before running, compute
  a hash of the source (commit SHA for git, archive hash for upload,
  content hash for local). If a successful scan with the same hash
  already exists for this project + tool, redirect to that scan
  instead of re-running. Saves time on repeated clicks; falls through
  to a real scan whenever the source actually changed.
- **Admin-controlled scan rate limit** — token / quota system so a
  single user can't pin server resources by triggering scans on every
  project at once. Builds on the per-(project, tool) lock that's
  already in place.

## SonarQube polish

- **Per-user Sonar token override** — currently the platform-level
  token in `.env` authenticates all users. A per-user
  `User.sonar_token` profile field would let users with their own
  Sonar instance override.
- **Pull Reliability + Maintainability findings** — already supported
  via `SAST_SONAR_ISSUE_TYPES=VULNERABILITY,BUG,CODE_SMELL` in `.env`,
  but no UI exists to view them as separate categories.
- **Sonar `rule_id` → OWASP 2017 mapping table.** Today most Sonar
  findings end up `UNMAPPED` because Sonar's rules don't carry CWE
  tags by default. A hand-curated mapping (`docker:S7029` →
  `A6:2017-Security Misconfiguration`, `python:S2076` →
  `A1:2017-Injection`, etc.) would dramatically reduce the unmapped
  count. Real curation work — start with the most-frequent ~50-100
  rules. Format would mirror `cwe_to_owasp_2017.json`.

## Chatbot

- A read-only assistant fed by a local LLM (LM Studio) that can answer
  questions about scan results, explain CWE / OWASP categories, and
  summarize findings. Possible Maintainability / Reliability data
  consumption to give it broader context.

## Auth & accounts

- **Templated password-reset flow** — Django's stock views are wired
  but no email backend is configured.
- **Admin toggle for source-type availability** — UI / settings
  switch to enable or disable the "Local path" source type per
  deployment (only useful where users have shell access).

## Misc cleanup

- **Move legacy tests** from `scans/migrations/tests/` to
  `scans/tests/`. Functionally fine where they are, but the location
  risks colliding with future migration files.
- **Drop the unused `python-sonarqube-api` dependency** — pinned in
  `requirements.txt` but the SonarAdapter rolls its own `requests`.
- **`ALLOWED_HOSTS = ['*']`** — fine for dev, tighten before any
  non-local deployment.
