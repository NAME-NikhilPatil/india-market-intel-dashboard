from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory


SOURCE_ROOT = Path(os.environ.get("SCRAPER_SEED_DIR", Path(__file__).resolve().parent)).resolve()
WORKSPACE_ROOT = Path(os.environ.get("SCRAPER_WORKSPACE_DIR", SOURCE_ROOT)).resolve()
RUNTIME_DIR = Path(os.environ.get("SCRAPER_RUNTIME_DIR", WORKSPACE_ROOT / ".runtime")).resolve()
JOBS_DIR = RUNTIME_DIR / "jobs"
LOG_DIR = JOBS_DIR / "logs"
JOBS_PATH = JOBS_DIR / "jobs.json"

PUBLIC_FILES = {
    "solar_dcr_scrape/solar_dcr_dashboard.html",
    "vahan_dashboard_project/vahan_dashboard_v19.html",
}

COPY_ITEMS = [
    "index.html",
    "solar_dcr_scrape",
    "vahan_dashboard_project",
]

SOLAR_CODE_FILES = [
    "scrape_solar_dcr.py",
    "build_data.py",
    "build_html.py",
    "dashboard_renderers.js",
    "dashboard_template.html",
    "README.md",
    "verify.js",
]

ADMIN_TOKEN = os.environ.get("SCRAPER_ADMIN_TOKEN", "").strip()
PYTHON_BIN = os.environ.get("SCRAPER_PYTHON", sys.executable)
MAX_LOG_BYTES = int(os.environ.get("SCRAPER_MAX_LOG_BYTES", "200000"))

app = Flask(__name__)
_jobs_lock = threading.Lock()
_runner_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_runtime_workspace() -> None:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if WORKSPACE_ROOT == SOURCE_ROOT:
        return

    marker = WORKSPACE_ROOT / ".workspace_seeded"
    reset = bool_env("RESET_RUNTIME_WORKSPACE", False)
    if marker.exists() and not reset:
        sync_runtime_code()
        return

    for item in COPY_ITEMS:
        src = SOURCE_ROOT / item
        dst = WORKSPACE_ROOT / item
        if not src.exists():
            continue
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".DS_Store",
                    "logs",
                    "dist",
                    ".runtime",
                ),
            )
        else:
            shutil.copy2(src, dst)

    marker.write_text(utc_now() + "\n", encoding="utf-8")
    sync_runtime_code()


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def sync_runtime_code() -> None:
    """Refresh deploy-time code in the persistent workspace without wiping
    scraper outputs. Azure App Service keeps /home across container upgrades,
    so this keeps scripts/frontend current after each GitHub Actions deploy.
    """
    if WORKSPACE_ROOT == SOURCE_ROOT:
        return

    copy_file(SOURCE_ROOT / "index.html", WORKSPACE_ROOT / "index.html")

    solar_src = SOURCE_ROOT / "solar_dcr_scrape"
    solar_dst = WORKSPACE_ROOT / "solar_dcr_scrape"
    for name in SOLAR_CODE_FILES:
        copy_file(solar_src / name, solar_dst / name)

    vahan_scripts_src = SOURCE_ROOT / "vahan_dashboard_project" / "scripts"
    vahan_scripts_dst = WORKSPACE_ROOT / "vahan_dashboard_project" / "scripts"
    if vahan_scripts_src.exists():
        if vahan_scripts_dst.exists():
            shutil.rmtree(vahan_scripts_dst)
        shutil.copytree(
            vahan_scripts_src,
            vahan_scripts_dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )


def load_jobs() -> dict[str, Any]:
    if not JOBS_PATH.exists():
        return {"jobs": []}
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"jobs": []}


def save_jobs(payload: dict[str, Any]) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(JOBS_PATH)


def upsert_job(job: dict[str, Any]) -> None:
    with _jobs_lock:
        payload = load_jobs()
        jobs = [j for j in payload.get("jobs", []) if j.get("id") != job["id"]]
        jobs.insert(0, job)
        payload["jobs"] = jobs[:100]
        save_jobs(payload)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        for job in load_jobs().get("jobs", []):
            if job.get("id") == job_id:
                return job
    return None


def auth_required() -> bool:
    if not ADMIN_TOKEN:
        return True
    header_token = request.headers.get("X-Admin-Token", "").strip()
    bearer = request.headers.get("Authorization", "").strip()
    if bearer.lower().startswith("bearer "):
        header_token = bearer[7:].strip()
    return header_token != ADMIN_TOKEN


def require_admin() -> None:
    if not ADMIN_TOKEN:
        abort(Response("SCRAPER_ADMIN_TOKEN is not configured", status=503))
    if auth_required():
        abort(Response("Admin token required", status=401))


def safe_body() -> dict[str, Any]:
    if not request.is_json:
        return {}
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    chrome_bin = env.get("CHROME_BIN")
    if chrome_bin:
        env["CHROME_BIN"] = chrome_bin
    return env


def run_step(command: list[str], cwd: Path, log_handle) -> int:
    log_handle.write("\n$ " + " ".join(command) + f"\n[cwd] {cwd}\n")
    log_handle.flush()
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=command_env(),
    )
    return proc.wait()


def run_job(job: dict[str, Any], steps: list[dict[str, Any]]) -> None:
    if not _runner_lock.acquire(blocking=False):
        job.update(
            status="failed",
            ended_at=utc_now(),
            error="Another scraper job is already running.",
        )
        upsert_job(job)
        return

    try:
        job.update(status="running", started_at=utc_now())
        upsert_job(job)

        log_path = Path(job["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"job_id={job['id']}\nkind={job['kind']}\nstarted_at={job['started_at']}\n")
            for index, step in enumerate(steps, start=1):
                command = step["command"]
                cwd = Path(step["cwd"])
                job["current_step"] = step["name"]
                job["current_step_index"] = index
                job["step_count"] = len(steps)
                upsert_job(job)
                code = run_step(command, cwd, log)
                if code:
                    job.update(
                        status="failed",
                        ended_at=utc_now(),
                        returncode=code,
                        error=f"Step failed: {step['name']}",
                    )
                    upsert_job(job)
                    return

        job.update(
            status="succeeded",
            ended_at=utc_now(),
            returncode=0,
            current_step=None,
        )
        upsert_job(job)
    except Exception as exc:  # pragma: no cover - defensive job boundary
        job.update(status="failed", ended_at=utc_now(), error=str(exc))
        upsert_job(job)
    finally:
        _runner_lock.release()


def start_job(kind: str, steps: list[dict[str, Any]], requested_by: str | None = None) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "queued_at": utc_now(),
        "started_at": None,
        "ended_at": None,
        "requested_by": requested_by,
        "log_path": str(LOG_DIR / f"{job_id}_{kind}.log"),
        "step_count": len(steps),
        "current_step": None,
        "current_step_index": None,
    }
    upsert_job(job)
    thread = threading.Thread(target=run_job, args=(job, steps), daemon=True)
    thread.start()
    return job


def py_script(path: Path) -> list[str]:
    return [PYTHON_BIN, str(path)]


def solar_steps(body: dict[str, Any], scrape: bool) -> list[dict[str, Any]]:
    solar_dir = WORKSPACE_ROOT / "solar_dcr_scrape"
    current_year = datetime.now().year
    start_year = str(body.get("start_year") or os.environ.get("SOLAR_START_YEAR", "2022"))
    end_year = str(body.get("end_year") or os.environ.get("SOLAR_END_YEAR", str(current_year)))
    steps: list[dict[str, Any]] = []
    if scrape:
        scrape_command = py_script(solar_dir / "scrape_solar_dcr.py") + [
            "--start-year",
            start_year,
            "--end-year",
            end_year,
            "--output-dir",
            ".",
        ]
        if bool(body.get("company_monthly")) or bool_env("SOLAR_COMPANY_MONTHLY", False):
            scrape_command.append("--company-monthly")
        steps.append({"name": "Scrape Solar DCR", "command": scrape_command, "cwd": solar_dir})
    steps.extend(
        [
            {"name": "Build Solar dashboard data", "command": py_script(solar_dir / "build_data.py"), "cwd": solar_dir},
            {"name": "Build Solar dashboard HTML", "command": py_script(solar_dir / "build_html.py"), "cwd": solar_dir},
        ]
    )
    return steps


def vahan_recent_steps(body: dict[str, Any], scrape: bool) -> list[dict[str, Any]]:
    project_dir = WORKSPACE_ROOT / "vahan_dashboard_project"
    scripts_dir = project_dir / "scripts"
    steps: list[dict[str, Any]] = []
    if scrape:
        command = py_script(scripts_dir / "refresh_vahan_recent_months.py")
        months = body.get("months")
        if isinstance(months, list) and months:
            command += ["--months", *[str(m) for m in months]]
        datasets = body.get("datasets")
        if isinstance(datasets, list) and datasets:
            command += ["--datasets", *[str(d) for d in datasets]]
        if not bool(body.get("parallel")) and not bool_env("VAHAN_PARALLEL", False):
            command.append("--sequential")
        for env_name, arg_name in [
            ("VAHAN_DELAY", "--delay"),
            ("VAHAN_ATTEMPTS", "--attempts"),
            ("VAHAN_WAIT_SECONDS", "--wait-seconds"),
            ("VAHAN_PAGE_TIMEOUT", "--page-timeout"),
            ("VAHAN_RETRY_SLEEP", "--retry-sleep"),
        ]:
            value = os.environ.get(env_name)
            if value:
                command += [arg_name, value]
        steps.append({"name": "Refresh VAHAN recent months", "command": command, "cwd": project_dir})
    steps.extend(
        [
            {
                "name": "Build VAHAN dashboard payload",
                "command": py_script(scripts_dir / "build_dashboard_payload.py"),
                "cwd": project_dir,
            },
            {
                "name": "Rewire VAHAN v19 dashboard",
                "command": py_script(scripts_dir / "rewire_v19_dashboard.py"),
                "cwd": project_dir,
            },
        ]
    )
    return steps


def dashboard_metadata() -> dict[str, Any]:
    vahan_file = WORKSPACE_ROOT / "vahan_dashboard_project" / "vahan_dashboard_v19.html"
    solar_file = WORKSPACE_ROOT / "solar_dcr_scrape" / "solar_dcr_dashboard.html"
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "runtime_dir": str(RUNTIME_DIR),
        "auth_enabled": bool(ADMIN_TOKEN),
        "scheduler": scheduler_metadata(),
        "dashboards": {
            "vahan": {
                "path": str(vahan_file),
                "exists": vahan_file.exists(),
                "size_bytes": vahan_file.stat().st_size if vahan_file.exists() else None,
                "updated_at": datetime.fromtimestamp(vahan_file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                if vahan_file.exists()
                else None,
            },
            "solar": {
                "path": str(solar_file),
                "exists": solar_file.exists(),
                "size_bytes": solar_file.stat().st_size if solar_file.exists() else None,
                "updated_at": datetime.fromtimestamp(solar_file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                if solar_file.exists()
                else None,
            },
        },
    }


def scheduler_metadata() -> dict[str, Any]:
    return {
        "enabled": bool_env("ENABLE_SCRAPER_SCHEDULER", False),
        "solar_daily_utc": os.environ.get("SOLAR_DAILY_UTC", "").strip() or None,
        "vahan_daily_utc": os.environ.get("VAHAN_DAILY_UTC", "").strip() or None,
        "timezone": "UTC",
        "notes": "Set ENABLE_SCRAPER_SCHEDULER=true plus SOLAR_DAILY_UTC/VAHAN_DAILY_UTC as HH:MM UTC. App Service Always On must be enabled.",
    }


def script_catalog() -> dict[str, list[str]]:
    solar_dir = WORKSPACE_ROOT / "solar_dcr_scrape"
    vahan_scripts = WORKSPACE_ROOT / "vahan_dashboard_project" / "scripts"
    return {
        "solar": sorted(path.name for path in solar_dir.glob("*.py")),
        "vahan": sorted(path.name for path in vahan_scripts.glob("*.py")),
    }


def custom_script_steps(body: dict[str, Any]) -> list[dict[str, Any]]:
    project = str(body.get("project") or "").strip().lower()
    script = str(body.get("script") or "").strip()
    args = body.get("args") or []
    if project not in {"solar", "vahan"}:
        abort(Response("project must be 'solar' or 'vahan'", status=400))
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        abort(Response("args must be a list of strings", status=400))
    catalog = script_catalog()
    if script not in catalog[project]:
        abort(Response("script is not in the allowed catalog", status=400))
    if project == "solar":
        cwd = WORKSPACE_ROOT / "solar_dcr_scrape"
        script_path = cwd / script
    else:
        cwd = WORKSPACE_ROOT / "vahan_dashboard_project"
        script_path = cwd / "scripts" / script
    return [
        {
            "name": f"Run {project}/{script}",
            "command": py_script(script_path) + args,
            "cwd": cwd,
        }
    ]


@app.get("/")
def index() -> Response:
    return send_file(WORKSPACE_ROOT / "index.html")


@app.get("/api/health")
def health() -> Response:
    return jsonify({"ok": True, "time": utc_now(), **dashboard_metadata()})


@app.get("/api/jobs")
def jobs() -> Response:
    require_admin()
    return jsonify(load_jobs())


@app.get("/api/scripts")
def scripts() -> Response:
    require_admin()
    return jsonify(script_catalog())


@app.post("/api/scripts/run")
def run_custom_script() -> Response:
    require_admin()
    body = safe_body()
    project = str(body.get("project") or "script").strip().lower()
    script = str(body.get("script") or "custom").strip().replace(".py", "")
    kind = f"run_{project}_{script}"
    job = start_job(kind, custom_script_steps(body), request.remote_addr)
    return jsonify(job), 202


@app.get("/api/jobs/<job_id>")
def job_detail(job_id: str) -> Response:
    require_admin()
    job = get_job(job_id)
    if not job:
        abort(404)
    return jsonify(job)


@app.get("/api/jobs/<job_id>/log")
def job_log(job_id: str) -> Response:
    require_admin()
    job = get_job(job_id)
    if not job:
        abort(404)
    path = Path(job["log_path"])
    if not path.exists():
        return Response("", mimetype="text/plain")
    data = path.read_bytes()
    if len(data) > MAX_LOG_BYTES:
        data = data[-MAX_LOG_BYTES:]
    return Response(data, mimetype="text/plain")


@app.post("/api/scrape/solar")
def scrape_solar() -> Response:
    require_admin()
    job = start_job("scrape_solar", solar_steps(safe_body(), scrape=True), request.remote_addr)
    return jsonify(job), 202


@app.post("/api/rebuild/solar")
def rebuild_solar() -> Response:
    require_admin()
    job = start_job("rebuild_solar", solar_steps(safe_body(), scrape=False), request.remote_addr)
    return jsonify(job), 202


@app.post("/api/scrape/vahan/recent")
def scrape_vahan_recent() -> Response:
    require_admin()
    job = start_job("scrape_vahan_recent", vahan_recent_steps(safe_body(), scrape=True), request.remote_addr)
    return jsonify(job), 202


@app.post("/api/rebuild/vahan")
def rebuild_vahan() -> Response:
    require_admin()
    job = start_job("rebuild_vahan", vahan_recent_steps(safe_body(), scrape=False), request.remote_addr)
    return jsonify(job), 202


@app.route("/<path:filename>")
def public_files(filename: str) -> Response:
    normalized = filename.replace("\\", "/")
    if normalized not in PUBLIC_FILES:
        abort(404)
    return send_from_directory(WORKSPACE_ROOT, normalized)


def maybe_start_scheduler() -> None:
    if not bool_env("ENABLE_SCRAPER_SCHEDULER", False):
        return

    def loop() -> None:
        last_run: set[str] = set()
        while True:
            now = datetime.now(timezone.utc)
            minute_key = now.strftime("%Y-%m-%dT%H:%M")
            for name, env_name, factory in [
                ("scheduled_solar", "SOLAR_DAILY_UTC", lambda: solar_steps({}, scrape=True)),
                ("scheduled_vahan_recent", "VAHAN_DAILY_UTC", lambda: vahan_recent_steps({}, scrape=True)),
            ]:
                target = os.environ.get(env_name, "").strip()
                if not target:
                    continue
                if now.strftime("%H:%M") == target and f"{name}:{minute_key}" not in last_run:
                    last_run.add(f"{name}:{minute_key}")
                    start_job(name, factory(), "scheduler")
            time.sleep(30)

    threading.Thread(target=loop, daemon=True).start()


ensure_runtime_workspace()
maybe_start_scheduler()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
