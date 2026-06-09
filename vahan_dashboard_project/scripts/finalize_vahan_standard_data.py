#!/usr/bin/env python3
"""Finalize VAHAN scrape outputs into the one standard consolidated dataset."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "vahan_2021_2026_calendar"
LOG_DIR = PROJECT_ROOT / "logs"
STANDARD_CSV_REL = "standard_consolidated/vahan_standard_consolidated_long.csv"
POINTER = DATA_DIR / "CURRENT_STANDARD_DATASET.json"

STANDARD_SOURCES = {
    "national_maker_month": "all_state_maker_month_long.csv",
    "state_maker_fuel": "state_maker_fuel_month_long.csv",
    "state_maker_category": "state_maker_category_month_long.csv",
    "state_category_fuel": "state_category_fuel_month_long.csv",
}

DO_NOT_USE_FOR_DASHBOARD = [
    "2w_*.csv/json",
    "4w_*.csv/json",
    "monthly_*.csv",
    "fuel_maker_vehicle_category_long.csv",
    "all_state_maker_fuel_month_long.csv",
    "all_state_maker_category_month_long.csv",
    "state_*_month_raw/*.json",
]


def run_step(name: str, command: list[str], log_name: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    print(f"{name}...", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc.returncode:
        raise RuntimeError(f"{name} failed with exit {proc.returncode}. See {log_path}")
    print(f"{name} complete. Log: {log_path}", flush=True)


def csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def consolidated_dataset_counts(path: Path) -> dict[str, int]:
    counts = {dataset: 0 for dataset in STANDARD_SOURCES}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            counts[row["dataset"]] = counts.get(row["dataset"], 0) + 1
    return counts


def write_pointer() -> None:
    standard_csv = DATA_DIR / STANDARD_CSV_REL
    source_files = {
        dataset: {
            "file": source_name,
            "row_count": csv_row_count(DATA_DIR / source_name),
        }
        for dataset, source_name in STANDARD_SOURCES.items()
    }
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "canonical_consolidated_csv": STANDARD_CSV_REL,
        "canonical_consolidated_csv_absolute": str(standard_csv),
        "consolidated_row_count": csv_row_count(standard_csv),
        "dataset_row_counts": consolidated_dataset_counts(standard_csv),
        "standard_source_files": source_files,
        "pipeline_rule": (
            "After any scrape or repair, run scripts/finalize_vahan_standard_data.py. "
            "Dashboards and analysis should read canonical_consolidated_csv, not raw JSON or legacy CSVs."
        ),
        "raw_data_role": "Raw JSON partitions are audit/rebuild inputs only.",
        "do_not_use_for_dashboard": DO_NOT_USE_FOR_DASHBOARD,
        "qa_files": [
            "CANONICAL_DATA.md",
            "STANDARD_DATASET_MANIFEST.csv",
            "vahan_data_quality_report.md",
            "data_source_validation_report.md",
        ],
    }
    POINTER.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {POINTER}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument(
        "--strict-app",
        action="store_true",
        help="Fail validation if root HTML/JS still references legacy data CSVs.",
    )
    args = parser.parse_args()

    if not args.skip_build:
        run_step(
            "Building consolidated CSV",
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_vahan_standard_consolidated.py")],
            "finalize_build_vahan_standard_consolidated.log",
        )
    if not args.skip_audit:
        run_step(
            "Running data quality audit",
            [sys.executable, str(PROJECT_ROOT / "scripts" / "audit_vahan_data_quality.py")],
            "finalize_audit_vahan_data_quality.log",
        )

    write_pointer()

    if not args.skip_validate:
        command = [sys.executable, str(PROJECT_ROOT / "scripts" / "validate_standard_data_sources.py")]
        if args.strict_app:
            command.append("--strict-app")
        run_step("Validating standard data source", command, "finalize_validate_standard_data_sources.log")

    print(f"Standard data source: {DATA_DIR / STANDARD_CSV_REL}", flush=True)


if __name__ == "__main__":
    main()
