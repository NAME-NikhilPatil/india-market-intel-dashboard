#!/usr/bin/env python3
"""Repair VAHAN raw partitions whose table title does not match the dataset.

The runner discovers bad raw JSON partitions, splits them into worker batches,
rescrapes those state/year/month groups with title validation enabled, and then
recompiles the affected long CSV once at the end.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "vahan_2021_2026_calendar"
LOG_DIR = PROJECT_ROOT / "logs"


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    raw_dir: str
    csv_name: str
    expected_title: str
    script: str
    report: str | None = None


DATASETS = {
    "state_maker_fuel": DatasetConfig(
        name="state_maker_fuel",
        raw_dir="state_maker_fuel_month_raw",
        csv_name="state_maker_fuel_month_long.csv",
        expected_title="Maker Wise Fuel Data",
        script="scrape_vahan_state_maker_fuel_monthly.py",
    ),
    "state_maker_category": DatasetConfig(
        name="state_maker_category",
        raw_dir="state_maker_category_month_raw",
        csv_name="state_maker_category_month_long.csv",
        expected_title="Maker Wise Vehicle Category Data",
        script="scrape_vahan_state_cross_monthly.py",
        report="maker_category",
    ),
    "state_category_fuel": DatasetConfig(
        name="state_category_fuel",
        raw_dir="state_category_fuel_month_raw",
        csv_name="state_category_fuel_month_long.csv",
        expected_title="Vehicle Category Wise Fuel Data",
        script="scrape_vahan_state_cross_monthly.py",
        report="category_fuel",
    ),
}


def discover_bad_jobs(config: DatasetConfig, data_dir: Path) -> dict[tuple[str, str], list[int]]:
    jobs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for path in sorted((data_dir / config.raw_dir).glob("*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        title = str(payload.get("title", ""))
        if config.expected_title in title:
            continue
        state = str(payload.get("state_code") or path.parent.name)
        month = str(payload.get("month") or path.stem)
        year, month_number = month.split("-")
        jobs[(state, year)].append(int(month_number))
    return {key: sorted(set(value)) for key, value in jobs.items()}


def split_jobs(jobs: dict[tuple[str, str], list[int]], workers: int) -> list[list[tuple[str, str, list[int]]]]:
    batches: list[list[tuple[str, str, list[int]]]] = [[] for _ in range(workers)]
    weights = [0] * workers
    sorted_jobs = sorted(
        [(state, year, months) for (state, year), months in jobs.items()],
        key=lambda item: (-len(item[2]), item[0], item[1]),
    )
    for state, year, months in sorted_jobs:
        index = min(range(workers), key=lambda idx: weights[idx])
        batches[index].append((state, year, months))
        weights[index] += len(months)
    return batches


def scrape_command(config: DatasetConfig, state: str, year: str, months: list[int],
                   args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / config.script)]
    if config.report:
        command += ["--report", config.report]
    command += [
        "--states",
        state,
        "--years",
        year,
        "--months",
        *[str(month) for month in months],
        "--output-dir",
        str(args.data_dir),
        "--delay",
        str(args.delay),
        "--attempts",
        str(args.attempts),
        "--wait-seconds",
        str(args.wait_seconds),
        "--page-timeout",
        str(args.page_timeout),
        "--retry-sleep",
        str(args.retry_sleep),
        "--compile-every",
        "0",
        "--max-consecutive-failures",
        "0",
        "--overwrite",
        "--skip-compile",
    ]
    return command


def compile_command(config: DatasetConfig, data_dir: Path) -> list[str]:
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / config.script)]
    if config.report:
        command += ["--report", config.report]
    command += ["--output-dir", str(data_dir), "--compile-only"]
    return command


def run_worker(worker_index: int, config: DatasetConfig, jobs: list[tuple[str, str, list[int]]],
               args: argparse.Namespace) -> int:
    log_path = LOG_DIR / f"repair_{config.name}_bad_titles_worker_{worker_index}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"worker={worker_index} dataset={config.name} jobs={len(jobs)}\n")
        log.flush()
        for state, year, months in jobs:
            command = scrape_command(config, state, year, months, args)
            log.write(f"\n=== {state} {year} months={months} ===\n")
            log.write(" ".join(command) + "\n")
            log.flush()
            proc = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            code = proc.wait()
            log.write(f"exit_code={code}\n")
            log.flush()
            if code:
                failures += 1
    return failures


def count_bad(config: DatasetConfig, data_dir: Path) -> int:
    return sum(len(months) for months in discover_bad_jobs(config, data_dir).values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="state_maker_fuel")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.30)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument("--page-timeout", type=int, default=120)
    parser.add_argument("--retry-sleep", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = DATASETS[args.dataset]
    jobs = discover_bad_jobs(config, args.data_dir)
    total_bad = sum(len(months) for months in jobs.values())
    print(f"{config.name}: {total_bad} bad partitions across {len(jobs)} state-year groups", flush=True)
    if not jobs:
        print("Nothing to repair.", flush=True)
        return

    batches = split_jobs(jobs, args.workers)
    for index, batch in enumerate(batches, start=1):
        month_count = sum(len(months) for _, _, months in batch)
        print(f"worker {index}: {len(batch)} state-year groups, {month_count} partitions", flush=True)
        for state, year, months in batch:
            print(f"  {state} {year}: {' '.join(str(month) for month in months)}", flush=True)
    if args.dry_run:
        return

    failures = 0
    worker_procs: list[tuple[subprocess.Popen, Path]] = []
    for index, batch in enumerate(batches, start=1):
        payload = json.dumps(batch)
        log_path = LOG_DIR / f"repair_{config.name}_bad_titles_worker_{index}.log"
        code = (
            "import json, sys; "
            "from pathlib import Path; "
            f"sys.path.insert(0, {str(PROJECT_ROOT / 'scripts')!r}); "
            "import repair_vahan_bad_title_partitions as r; "
            f"args = r.argparse.Namespace(data_dir=Path({str(args.data_dir)!r}), delay={args.delay!r}, "
            f"attempts={args.attempts!r}, wait_seconds={args.wait_seconds!r}, "
            f"page_timeout={args.page_timeout!r}, retry_sleep={args.retry_sleep!r}); "
            f"sys.exit(r.run_worker({index!r}, r.DATASETS[{config.name!r}], json.loads({payload!r}), args))"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "-c", code], cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT)
        log.close()
        worker_procs.append((proc, log_path))

    for proc, log_path in worker_procs:
        code = proc.wait()
        if code:
            failures += code
            print(f"{log_path.name} reported {code} failed state-year groups", flush=True)
        else:
            print(f"{log_path.name} completed cleanly", flush=True)

    compile_log_path = LOG_DIR / f"repair_{config.name}_compile.log"
    with compile_log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            compile_command(config, args.data_dir),
            cwd=PROJECT_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        compile_code = proc.wait()
    if compile_code:
        raise RuntimeError(f"Compile failed; see {compile_log_path}")

    remaining = count_bad(config, args.data_dir)
    print(f"Repair done. remaining_bad_partitions={remaining}. state_year_failures={failures}", flush=True)
    print(f"Compile log: {compile_log_path}", flush=True)
    if remaining or failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
