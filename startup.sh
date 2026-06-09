#!/usr/bin/env sh
set -eu

export PORT="${PORT:-${WEBSITES_PORT:-8000}}"
export PYTHONUNBUFFERED=1
export SCRAPER_SEED_DIR="${SCRAPER_SEED_DIR:-/app}"
export SCRAPER_WORKSPACE_DIR="${SCRAPER_WORKSPACE_DIR:-/home/site/dashboard-workspace}"
export SCRAPER_RUNTIME_DIR="${SCRAPER_RUNTIME_DIR:-/home/site/scraper-runtime}"
export CHROME_BIN="${CHROME_BIN:-/usr/bin/chromium}"

exec gunicorn app:app \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-900}" \
  --access-logfile - \
  --error-logfile -
