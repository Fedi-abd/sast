# SAST Analysis Platform

A web platform that runs open-source security scanners against your code,
normalizes their findings, and maps them to **OWASP Top 10 (2017)** so
you can review vulnerabilities consistently across tools.

---

## Table of contents

- [Description](#description)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)

---

## Description

Modern SAST tools each report findings in their own format, with their
own severity scales and rule IDs. This platform sits above them as an
**orchestration and reasoning layer**: it triggers scans, collects raw
output, and re-presents everything in a single uniform view classified
by the OWASP Top 10 (2017) — a standard most security teams already
think in.

The platform itself does not implement detection rules; it runs
**Semgrep** and **SonarQube** as scan profiles and translates their
output via a curated CWE → OWASP lookup.

**Tech stack**

- **Django 6** — web framework, ORM, admin
- **PostgreSQL 16** — persistence
- **Bootstrap 5** — UI styling, with a built-in dark-mode toggle
- **Semgrep** — static analysis CLI
- **SonarQube** — static analysis server (queried via REST)
- **python-dotenv**, **psycopg2**, **requests** — supporting libraries

---

## Features

- **Sign up and log in** from the browser — no manual `createsuperuser`
  required.
- **Three source types** for projects:
  - Local server path
  - Uploaded ZIP archive (with zip-slip and zip-bomb defenses)
  - Public Git URL (GitHub or GitLab over HTTPS)
- **Two scanner profiles** per project: Semgrep or SonarQube.
- **Scan lifecycle tracking** — each run is recorded with status,
  duration, error message (if any), and full per-finding raw output.
- **OWASP Top 10 (2017) mapping** — every finding's CWE is mapped to a
  category; mapping rate is reported per scan.
- **Findings table** with severity badges, OWASP categories, and
  click-to-toggle filters for severity and OWASP category (multi-select,
  page doesn't reload on filter change).
- **Per-project scan history** so you can compare runs over time.
- **Dark and light themes**, persisted across sessions.
- **Drag-and-drop ZIP upload** on the project create page.

---

## Installation

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 16** running locally
- **Git** (for the Git source type)
- **Semgrep** installed and on `PATH` (`pip install semgrep` is enough)
- **Docker** *(optional)* — only needed if you plan to run a local
  SonarQube instance

### 1. Database

```bash
sudo apt install postgresql postgresql-contrib   # if not already installed
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres createdb sast_db
```

### 2. Project setup

```bash
git clone <your-repo-url> sast
cd sast

python3 -m venv venv
source venv/bin/activate                # Linux / macOS / WSL
# .\venv\Scripts\Activate.ps1           # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env                    # then edit with your secrets
python manage.py migrate
python manage.py runserver
```

### 3. (Optional) SonarQube

If you want the SonarQube profile to work, run a local SonarQube and
generate an admin token:

```bash
docker run -d -p 9000:9000 --name sonarqube sonarqube:lts-community
# Open http://localhost:9000 (default login admin/admin),
# generate a token under My Account → Security,
# then put SONAR_HOST and SONAR_TOKEN into your .env.
```

---

## Usage

Once the dev server is running at `http://localhost:8000/`:

1. **Sign up** at `/accounts/signup/` (or log in if you already have an account).
2. **Create a project** from the project list. Pick a source:
   - **Local path**: absolute path on the server (e.g.
     `/home/you/projects/my-app`)
   - **Uploaded archive**: drag-and-drop or pick a `.zip`
   - **Git repository**: an `https://github.com/...` URL, plus an
     optional branch
3. **Open the project** and click **Run Semgrep** or **Run SonarQube**.
   The page shows a spinner while the scan runs.
4. **Review the results**: severity counts, OWASP distribution, and the
   findings table. Click any severity or OWASP row to filter the table;
   filters compose and toggle off when re-clicked.

You can also trigger scans from the command line:

```bash
python manage.py scan_project <project-uuid> --tool semgrep
python manage.py scan_project <project-uuid> --tool sonarqube
```

And run the test suite:

```bash
python manage.py test
```

---

## Roadmap

See [`FUTURE_FEATURES.md`](FUTURE_FEATURES.md) for planned work
(dashboard, PDF export, scan-history comparison, async scans).
