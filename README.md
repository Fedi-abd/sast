# SAST Analysis Platform

A web platform that orchestrates open-source SAST tools (Semgrep,
SonarQube), normalizes their output, and maps findings to **OWASP Top 10
(2017)** for consistent review.

The platform itself does not implement detection rules — it sits above
the scanners as a reasoning layer, giving you a unified view of findings
across tools.

**Tech stack:** Django 6, PostgreSQL 16, Bootstrap 5, Semgrep, SonarQube.

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)

---

## Features

- Three project source types: local path, ZIP upload, Git URL
- Semgrep and SonarQube as scan profiles
- Scan history and lifecycle tracking per project
- OWASP Top 10 (2017) mapping
- Interactive severity and OWASP filtering on findings
- Light and dark mode
- Built-in user registration (no CLI setup required)
- Secure upload with drag-and-drop

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

Visit `http://localhost:8000/`, sign up, then:

1. Create a project — pick a source type (local path, ZIP, or Git URL).
2. Click **Run Semgrep** or **Run SonarQube** on the project page.
3. Review findings with severity and OWASP filters.

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
