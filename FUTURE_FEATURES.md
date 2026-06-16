# Future Features

Planned and proposed work, grouped by area. Items here are explicitly
**not** in the current shipping scope. They're either next-up or
ideas worth keeping a list of.

(Sprint 4 in-progress items are tracked separately, see the
sprint plan, not this file.)

---

## Reporting

- **Cross-project dashboard**: KPI cards (total projects, total scans,
  scans-this-week, most-frequent OWASP category), recent-activity table,
  OWASP distribution chart aggregated across the user's projects.
  Templated UI, charts via Chart.js or similar.

## Help / onboarding

- **Help bot: retrieval over a knowledge base, optional LLM on top**
  (refined 2026-06-15). A small in-app helper for common questions
  ("how do credits work?", "why is a finding UNMAPPED?", "which source
  types are supported?"). Tiers:
  1. **Retrieval (smart canned, the floor).** Embed the docs/FAQ once
     into a small knowledge base; at query time embed the question and
     return the closest pre-written answer by similarity. Handles
     paraphrasing without hand-coding edge cases, no generation, no
     hallucination, works offline. A tiny embedding model (MiniLM
     class, ~22M) does this on CPU. This is the demo-safe default and a
     real step up from exact-match canned.
  2. **Optional generation (true RAG).** Feed the retrieved chunks to a
     model to phrase a fluent answer, behind one OpenAI-compatible config.
     Hosting (clarified 2026-06-16): the real host is the user's **3060
     desktop at home** running a more capable model. The tower stays home,
     so for the uni demo it is reached remotely via LM Studio's link (a
     zero-hassle public OpenAI-compatible URL the client just points at,
     no LAN, no hauling a tower). The i9 laptop (Iris Xe + 14 cores) can
     run a tiny 80M to 2B model locally as a fallback (user benchmarked
     ~50 to 150 tok/s Q8 with a TeaPot-class model or Gemma 3n E2B); a
     free API (Groq) is the other tier. Degrades to tier 1 when none are
     reachable.
  3. **Reuse for enrichment.** The same knowledge base + retrieval can
     map UNMAPPED findings (rule to OWASP). For that path prefer
     retrieval or classification over generation: a wrong generated
     category is a real correctness bug, whereas retrieval returns a
     real curated mapping. Generation stays the cherry for the chatty
     bot, not the security classification.
  No model download needed for tier 1.

## Finding triage

- **Per-finding status (acknowledged / suppressed / open)**: the Sprint 4
  designer wired `Acknowledge` and `Suppress rule` buttons into the
  scan-results disclosure rows, and a "Critical · unresolved" KPI on the
  dashboard. Both imply a `Finding.status` field the backend doesn't have
  yet: today every finding is implicitly "open". Adding it means a
  migration + a PATCH endpoint + the dashboard KPI logic; small but
  meaningful work. Deferred from v1 to keep the demo focused.

## Scan execution

- **Scan-result caching / change detection**: before running, compute
  a hash of the source (commit SHA for git, archive hash for upload,
  content hash for local). If a successful scan with the same hash
  already exists for this project + tool, redirect to that scan
  instead of re-running. Saves time on repeated clicks; falls through
  to a real scan whenever the source actually changed.

## SonarQube polish

- **Per-user Sonar token override**: currently the platform-level
  token in `.env` / SonarSettings authenticates all users. A per-user
  `User.sonar_token` profile field would let users with their own
  Sonar instance override.
- **Pull Reliability + Maintainability findings into the main UI**:
  already supported in storage via `SAST_SONAR_ISSUE_TYPES`, but no UI
  exists to view them as separate categories. Sprint 4 PDF report
  exposes them via a toggle, but the main scan-detail page doesn't.

## Semgrep polish

- **Semgrep rule selector**: let users choose which Semgrep ruleset
  to run when triggering a scan (`p/security`, `p/owasp-top-10`,
  `p/python`, `auto`, custom). Currently hardcoded to `auto` via the
  adapter's `ruleset` config key.

## Credits

- **Blank credits = unmetered**: in the admin limits tab, leaving a
  user's Credits field empty would mark that account infinite (the
  way staff already are), instead of clamping to 0. Needs a nullable
  `credits` column + the charge/display logic treating null as ∞.
- **Configurable cost per scan per tool**: admin-editable cost
  fields (Semgrep, SonarQube, Run Both) instead of the hardcoded
  1/1/2. Costs live in PlatformSettings, served via `/api/config/`
  so the SPA's scan cards and warnings read the real numbers.

## Auth & accounts

- **Templated password-reset flow**: Django's stock views are wired
  but no email backend is configured.
- **Login with username OR email**: small auth-backend addition;
  match email only when exactly one account carries it (emails are
  not unique today).
- **"Forgot password" → admin notification**: no-SMTP reset loop:
  a login-page link where the user submits their username, the
  platform records a reset request, and staff see it in the admin
  console (could finally give the topbar bell a real job). Admin
  resets + sends the temp password through the existing flow.
- **Failed-login lockout + admin alert**: detect repeated failed
  logins (foul play), throttle or lock the account, surface the
  event to staff. django-axes territory; needs the notification
  surface above first.
- **Styled HTML email**: the reset email is plain text because
  mailto: can't carry HTML by spec. A themed (CLI-design) email
  needs a real SMTP backend sending from Django; pairs with the
  password-reset flow item.

## Admin console

- **Git host allowlist setting**: github.com/gitlab.com is
  hardcoded in the validator; make it a PlatformSettings field
  editable from the deployment tab.

## Misc cleanup

- **Move legacy tests** from `scans/migrations/tests/` to
  `scans/tests/`. Functionally fine where they are, but the location
  risks colliding with future migration files.
- **Drop the unused `python-sonarqube-api` dependency**: pinned in
  `requirements.txt` but the SonarAdapter rolls its own `requests`.
- **`ALLOWED_HOSTS = ['*']`**: fine for dev, tighten before any
  non-local deployment.
- **Drop the empty `core/` Django app**: sits in `INSTALLED_APPS`
  doing nothing. Q12 resolved as "keep for now"; revisit if it stays
  empty through Sprint 4.
