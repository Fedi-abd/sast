# SAST Analysis Platform

A web platform that orchestrates open-source SAST tools (Semgrep,
SonarQube), normalizes their output, and maps findings to **OWASP Top 10
(2017)** for consistent review.

The platform itself does not implement detection rules; it sits above
the scanners as a reasoning layer, giving you a unified view of findings
across tools.

**Tech stack:** Django 6 + Django REST Framework, PostgreSQL 16, a Vue 3
+ Vite single-page app (Django templates stay on as a debug fallback),
django-q2 for async scans, WeasyPrint for PDF reports, Semgrep, SonarQube.

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)

---

## Features

- Vue 3 single-page app as the primary UI, with a Django-templated debug fallback
- REST API (DRF) behind the SPA
- Three project source types: local path, ZIP upload (drag-and-drop), Git URL (host allowlist)
- Semgrep and SonarQube scan profiles, run asynchronously via django-q2
- Scan history and lifecycle tracking per project
- OWASP Top 10 (2017) mapping (CWE lookup plus a curated SonarQube rule fallback)
- SonarQube security hotspots merged in; an admin toggle and a per-scan type menu to show or hide issue types
- Interactive severity and OWASP filtering; mark findings "solved" to track triage progress
- PDF report export, scoped by severity
- Credits and quota system: admin-configurable per-user limits (credits, projects, upload size), with unlimited supported
- In-app admin console: SonarQube config, per-user limits, usage log, user management, deployment flags
- Auth: registration, login by username or email, live password strength + requirements, self-service password-reset requests
- Light and dark mode
- Upload hardening: zip-slip and zip-bomb defenses

---

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 16
- Semgrep on `PATH`
- Git
- Docker *(optional, for SonarQube)*

### Setup

Create a PostgreSQL database, then:

```bash
git clone <your-repo-url> sast
cd sast
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # edit with your DB credentials
python manage.py migrate
python manage.py runserver
```

### Optional: SonarQube

```bash
docker run -d -p 9000:9000 sonarqube:lts-community
```

Then generate a token in the SonarQube UI and set `SONAR_HOST` and
`SONAR_TOKEN` in `.env`.

---

## Usage

The primary UI is the Vue SPA at `/app/`. Build it once from `frontend/`
(`npm install && npm run build`); the Django-templated UI stays available
at `/debug/` as a fallback, and staff get an in-app admin console at
`/app/#/admin`.

Visit `http://localhost:8000/`, sign up, then:

1. Create a project: pick a source type (local path, ZIP, or Git URL).
2. Run **Semgrep** or **SonarQube** on the project page.
3. Review findings with severity, OWASP, and (for SonarQube) issue-type filters; mark items solved; export a PDF.

From the CLI:

```bash
python manage.py scan_project <project-uuid> --tool semgrep
python manage.py scan_project <project-uuid> --tool sonarqube
```

Run the test suite:

```bash
python manage.py test
```

---

## Roadmap

See [`FUTURE_FEATURES.md`](FUTURE_FEATURES.md).
