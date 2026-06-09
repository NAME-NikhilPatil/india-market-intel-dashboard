#!/usr/bin/env python3
"""Refresh targeted VAHAN state/month partitions and compile once.

Default mode finds state-months where State x Maker x Fuel totals do not match
State x Maker x Vehicle Category totals beyond a small tolerance. It refreshes
the matching Maker x Category and Category x Fuel partitions so the standard
state-level datasets are the same vintage.
"""

from __future__ import annotations

import argparse
import csv
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
    script: str
    report: str | None
    csv_name: str


DATASETS = {
    "state_maker_fuel": DatasetConfig(
        "state_maker_fuel", "scrape_vahan_state_maker_fuel_monthly.py", None, "state_maker_fuel_month_long.csv"
    ),
    "state_maker_category": DatasetConfig(
        "state_maker_category", "scrape_vahan_state_cross_monthly.py", "maker_category",
        "state_maker_category_month_long.csv",
    ),
    "state_category_fuel": DatasetConfig(
        "state_category_fuel", "scrape_vahan_state_cross_monthly.py", "category_fuel",
        "state_category_fuel_month_long.csv",
    ),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def int_value(value: str | None) -> int:
    return int((value or "0").replace(",", ""))


def sum_by(rows: list[dict[str, str]], keys: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    out: dict[tuple[str, ...], int] = defaultdict(int)
    for row in rows:
        out[tuple(row[key] for key in keys)] += int_value(row["registrations"])
    return out


def mismatch_jobs(data_dir: Path, threshold: int) -> dict[tuple[str, str], list[int]]:
    maker_fuel = read_rows(data_dir / "state_maker_fuel_month_long.csv")
    maker_category = read_rows(data_dir / "state_maker_category_month_long.csv")
    fuel_totals = sum_by(maker_fuel, ("month", "state_code"))
    category_totals = sum_by(maker_category, ("month", "state_code"))
    jobs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for key in sorted(set(fuel_totals) | set(category_totals)):
        diff = category_totals.get(key, 0) - fuel_totals.get(key, 0)
        if abs(diff) <= threshold:
            continue
        month, state = key
        year, month_number = month.split("-")
        jobs[(state, year)].append(int(month_number))
    return {key: sorted(set(value)) for key, value in jobs.items()}


def split_jobs(jobs: list[tuple[str, str, str, list[int]]], workers: int) -> list[list[tuple[str, str, str, list[int]]]]:
    batches: list[list[tuple[str, str, str, list[int]]]] = [[] for _ in range(workers)]
    weights = [0] * workers
    for dataset, state, year, months in sorted(jobs, key=lambda item: (-len(item[3]), item[0], item[1], item[2])):
        index = min(range(workers), key=lambda idx: weights[idx])
        batches[index].append((dataset, state, year, months))
        weights[index] += len(months)
    return batches


def scrape_command(dataset: str, state: str, year: str, months: list[int], args: argparse.Namespace) -> list[str]:
    config = DATASETS[dataset]
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


def compile_command(dataset: str, data_dir: Path) -> list[str]:
    config = DATASETS[dataset]
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / config.script)]
    if config.report:
        command += ["--report", config.report]
    command += ["--output-dir", str(data_dir), "--compile-only"]
    return command


def run_worker(worker_index: int, jobs: list[tuple[str, str, str, list[int]]], args: argparse.Namespace) -> int:
    log_path = LOG_DIR / f"refresh_targeted_partitions_worker_{worker_index}.log"
    failures = 0
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"worker={worker_index} jobs={len(jobs)}\n")
        for dataset, state, year, months in jobs:
            command = scrape_command(dataset, state, year, months, args)
            log.write(f"\n=== {dataset} {state} {year} months={months} ===\n")
            log.write(" ".join(command) + "\n")
            log.flush()
            proc = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, text=True)
            code = proc.wait()
            log.write(f"exit_code={code}\n")
            log.flush()
            if code:
                failures += 1
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--datasets", nargs="+", choices=sorted(DATASETS), default=[
        "state_maker_category",
        "state_category_fuel",
    ])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--threshold", type=int, default=2)
    parser.add_argument("--jobs-json", type=Path,
                        help="Optional JSON object mapping 'STATE YEAR' to month lists.")
    parser.add_argument("--delay", type=float, default=0.30)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument("--page-timeout", type=int, default=120)
    parser.add_argument("--retry-sleep", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.jobs_json:
        raw_jobs = json.loads(args.jobs_json.read_text(encoding="utf-8"))
        grouped = {
            tuple(key.split(" ", 1)): [int(month) for month in months]
            for key, months in raw_jobs.items()
        }
    else:
        grouped = mismatch_jobs(args.data_dir, args.threshold)

    jobs = [
        (dataset, state, year, months)
        for dataset in args.datasets
        for (state, year), months in grouped.items()
    ]
    print(
        f"Targeted refresh: {sum(len(months) for months in grouped.values())} state-months, "
        f"{len(grouped)} state-year groups, datasets={','.join(args.datasets)}",
        flush=True,
    )
    batches = split_jobs(jobs, args.workers)
    for index, batch in enumerate(batches, start=1):
        month_count = sum(len(months) for _, _, _, months in batch)
        print(f"worker {index}: {len(batch)} jobs, {month_count} dataset-month partitions", flush=True)
        for dataset, state, year, months in batch:
            print(f"  {dataset} {state} {year}: {' '.join(str(month) for month in months)}", flush=True)
    if args.dry_run or not jobs:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    worker_procs: list[tuple[subprocess.Popen, Path]] = []
    for index, batch in enumerate(batches, start=1):
        payload = json.dumps(batch)
        code = (
            "import json, sys; "
            "from pathlib import Path; "
            f"sys.path.insert(0, {str(PROJECT_ROOT / 'scripts')!r}); "
            "import refresh_vahan_targeted_partitions as r; "
            f"args = r.argparse.Namespace(data_dir=Path({str(args.data_dir)!r}), delay={args.delay!r}, "
            f"attempts={args.attempts!r}, wait_seconds={args.wait_seconds!r}, "
            f"page_timeout={args.page_timeout!r}, retry_sleep={args.retry_sleep!r}); "
            f"sys.exit(r.run_worker({index!r}, json.loads({payload!r}), args))"
        )
        log_path = LOG_DIR / f"refresh_targeted_partitions_supervisor_{index}.log"
        log = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "-c", code], cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT)
        log.close()
        worker_procs.append((proc, log_path))

    failures = 0
    for proc, log_path in worker_procs:
        code = proc.wait()
        if code:
            failures += code
            print(f"{log_path.name} reported {code} failed jobs", flush=True)
        else:
            print(f"{log_path.name} completed cleanly", flush=True)

    for dataset in args.datasets:
        log_path = LOG_DIR / f"refresh_targeted_{dataset}_compile.log"
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                compile_command(dataset, args.data_dir),
                cwd=PROJECT_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            code = proc.wait()
        if code:
            raise RuntimeError(f"Compile failed for {dataset}; see {log_path}")
        print(f"Compiled {DATASETS[dataset].csv_name}; log={log_path}", flush=True)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
