# Production deployment (WSL Ubuntu)

Target layout: **nginx :80** → gunicorn :8001 (Django) + static files,
with the **qcluster** worker running scans and **PostgreSQL** local.
All commands run inside WSL unless marked otherwise.

```
browser ──► nginx :80 ──► /app/      → frontend/dist  (Vue SPA)
                     ├──► /static/   → staticfiles    (auth CSS, admin)
                     └──► everything else → gunicorn :8001 → Django
                                              └── django-q2 qcluster → semgrep / sonar-scanner
```

## 0. One-time prerequisites

- WSL systemd: `/etc/wsl.conf` must contain `[boot]` `systemd=true`
  (then `wsl --shutdown` from Windows and reopen).
- `sudo apt install nginx`
- SonarQube keeps running via `~/sonarqube-docker` as in dev.

## 1. Build the pieces

```bash
# Frontend (run on the side that owns node_modules — currently Windows):
#   cd frontend && npm run build           → frontend/dist/

# Backend deps (WSL):
cd /mnt/c/Users/Peli911GT/Desktop/sast
source linux-venv/bin/activate
pip install -r requirements.txt            # includes gunicorn

# Static files for nginx:
python manage.py collectstatic --noinput   # → staticfiles/
python manage.py migrate
```

## 2. Production .env

Edit `.env` (same file dev uses — change these):

```
DEBUG=False
SAST_DEBUG_UI=False
ALLOWED_HOSTS=localhost,127.0.0.1,<lan-ip>
CSRF_TRUSTED_ORIGINS=http://localhost,http://<lan-ip>
# SAST_TLS stays False unless nginx terminates HTTPS
```

Sanity check: `python manage.py check --deploy` (warnings about HSTS /
secure cookies are expected while SAST_TLS=False on a LAN demo).

## 3. Services

```bash
sudo cp deploy/gunicorn-sast.service deploy/qcluster-sast.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn-sast qcluster-sast

sudo cp deploy/nginx-sast.conf /etc/nginx/sites-available/sast
sudo ln -s /etc/nginx/sites-available/sast /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Logs: `journalctl -u gunicorn-sast -f` / `journalctl -u qcluster-sast -f`.

## 4. Smoke checklist

1. `http://localhost/` → redirects to login (styled page, CSS loads).
2. Log in → lands on `/app/#/dashboard`, `scan_engine: ONLINE`.
3. `/debug/projects/` → **404** (SAST_DEBUG_UI=False).
4. Run a scan → RUNNING → finishes (proves qcluster).
5. Export PDF on a finished scan.
6. Upload a ZIP close to 250 MB → accepted (proves client_max_body_size).
7. Non-staff account → no Admin nav, `/api/admin/users/` → 403.

## Notes

- Dev mode is unchanged: runserver :8000 + Vite :5173 still work; the
  services above are independent of them. Don't run runserver and
  gunicorn at the same time against different code states.
- After pulling new code: rebuild `frontend/dist`, re-run
  `collectstatic`, then `sudo systemctl restart gunicorn-sast qcluster-sast`.
