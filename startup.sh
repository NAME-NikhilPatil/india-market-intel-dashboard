#!/usr/bin/env sh
set -eu

export PORT="${PORT:-${WEBSITES_PORT:-8000}}"
export PYTHONUNBUFFERED=1
APP_ROOT="$(pwd -P)"
if [ ! -f "${APP_ROOT}/app.py" ]; then
  APP_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
fi
export SCRAPER_SEED_DIR="${SCRAPER_SEED_DIR:-${APP_ROOT}}"
export SCRAPER_WORKSPACE_DIR="${SCRAPER_WORKSPACE_DIR:-/home/site/dashboard-workspace}"
export SCRAPER_RUNTIME_DIR="${SCRAPER_RUNTIME_DIR:-/home/site/scraper-runtime}"
export CHROME_BIN="${CHROME_BIN:-/usr/bin/chromium}"
export WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
export ENABLE_SCRAPER_SCHEDULER="${ENABLE_SCRAPER_SCHEDULER:-true}"
export SOLAR_DAILY_UTC="${SOLAR_DAILY_UTC:-02:30}"
export VAHAN_DAILY_UTC="${VAHAN_DAILY_UTC:-03:30}"
export VAHAN_HEADFUL="${VAHAN_HEADFUL:-true}"

GUNICORN_BINDS="--bind 0.0.0.0:${PORT}"
if [ "${PORT}" != "80" ]; then
  # Azure's newer sidecar-based App Service container model can route to its
  # configured target port instead of honoring the legacy WEBSITES_PORT app
  # setting. Listening on both ports makes the same image compatible with
  # both models and prevents a healthy process from appearing as HTTP 503.
  GUNICORN_BINDS="${GUNICORN_BINDS} --bind 0.0.0.0:80"
fi
GUNICORN_ARGS="${GUNICORN_BINDS} --workers ${WEB_CONCURRENCY:-1} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-900} --access-logfile - --error-logfile -"

if command -v xvfb-run >/dev/null 2>&1 && [ -x "${CHROME_BIN}" ]; then
  exec xvfb-run -a gunicorn app:app ${GUNICORN_ARGS}
fi

echo "WARNING: Chromium/Xvfb unavailable; VAHAN scheduling is disabled. Deploy the Docker image to enable it." >&2
export VAHAN_DAILY_UTC=""
export VAHAN_HEADFUL="false"
exec gunicorn app:app ${GUNICORN_ARGS}
