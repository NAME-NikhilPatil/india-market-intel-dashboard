#!/usr/bin/env python3
"""Validate that VAHAN downstream work has one standard data source.

This script does not scrape. It checks that:

1. The single consolidated CSV exists and is the only CSV in standard_consolidated.
2. CURRENT_STANDARD_DATASET.json points at that consolidated CSV.
3. The consolidated row counts match the current standard source CSVs.
4. Dashboard/app files are not silently pointing at older CSV exports.

By default, legacy dashboard references are reported as warnings so the scrape
finalization flow can still complete. Use --strict-app to fail on those too.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE = PROJECT_ROOT / "data" / "vahan_2021_2026_calendar"
STANDARD_DIR = BASE / "standard_consolidated"
STANDARD_CSV_NAME = "vahan_standard_consolidated_long.csv"
STANDARD_CSV = STANDARD_DIR / STANDARD_CSV_NAME
POINTER = BASE / "CURRENT_STANDARD_DATASET.json"
REPORT = BASE / "data_source_validation_report.md"

STANDARD_SOURCES = {
    "national_maker_month": "all_state_maker_month_long.csv",
    "state_maker_fuel": "state_maker_fuel_month_long.csv",
    "state_maker_category": "state_maker_category_month_long.csv",
    "state_category_fuel": "state_category_fuel_month_long.csv",
}

LEGACY_DATA_FILES = [
    "2w_fuel_month.csv",
    "2w_maker_fuel.csv",
    "2w_maker_month.csv",
    "4w_fuel_month.csv",
    "4w_maker_fuel.csv",
    "4w_maker_month.csv",
    "annual_ev_penetration_by_category.csv",
    "fuel_maker_vehicle_category_long.csv",
    "monthly_ev_penetration_all_categories.csv",
    "monthly_fuel_vehicle_category_long.csv",
    "monthly_maker_vehicle_category_long.csv",
    "all_state_maker_fuel_month_long.csv",
    "all_state_maker_category_month_long.csv",
]

RAW_INPUT_DIRS = [
    "state_maker_fuel_month_raw",
    "state_maker_category_month_raw",
    "state_category_fuel_month_raw",
]


def csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def consolidated_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            counts[row["dataset"]] += 1
    return counts


def find_app_references() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(PROJECT_ROOT.glob("*")):
        if path.suffix.lower() not in {".html", ".js"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for filename in LEGACY_DATA_FILES:
            if filename in text:
                findings.append(
                    {
                        "file": str(path.relative_to(PROJECT_ROOT)),
                        "reference": filename,
                        "severity": "legacy_csv_reference",
                    }
                )
        for raw_dir in RAW_INPUT_DIRS:
            if raw_dir in text and "raw_audit" not in text:
                findings.append(
                    {
                        "file": str(path.relative_to(PROJECT_ROOT)),
                        "reference": raw_dir,
                        "severity": "raw_dir_reference",
                    }
                )
    return findings


def write_report(errors: list[str], warnings: list[str], counts: Counter[str], app_findings: list[dict[str, str]]) -> None:
    lines = [
        "# VAHAN Data Source Validation",
        "",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## Canonical Source",
        "",
        f"- Consolidated CSV: `standard_consolidated/{STANDARD_CSV_NAME}`",
        f"- Pointer file: `CURRENT_STANDARD_DATASET.json`",
        "",
        "## Consolidated Row Counts",
        "",
        "| dataset | rows | source file | source rows |",
        "| --- | ---: | --- | ---: |",
    ]
    for dataset, source_name in STANDARD_SOURCES.items():
        source_path = BASE / source_name
        source_rows = csv_row_count(source_path) if source_path.exists() else "MISSING"
        lines.append(f"| {dataset} | {counts.get(dataset, 0)} | `{source_name}` | {source_rows} |")

    lines += ["", "## App/Dashboard Legacy References", ""]
    if app_findings:
        lines += ["| file | reference | severity |", "| --- | --- | --- |"]
        for finding in app_findings:
            lines.append(f"| `{finding['file']}` | `{finding['reference']}` | {finding['severity']} |")
    else:
        lines.append("No legacy CSV/raw references found in root HTML/JS files.")

    lines += ["", "## Result", ""]
    if errors:
        lines.append("Errors:")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- No blocking errors.")
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-app",
        action="store_true",
        help="Fail if root HTML/JS files reference legacy CSVs or raw dirs.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    if not STANDARD_CSV.exists():
        errors.append(f"Missing consolidated CSV: {STANDARD_CSV}")

    csvs = sorted(STANDARD_DIR.glob("*.csv")) if STANDARD_DIR.exists() else []
    if csvs != [STANDARD_CSV]:
        errors.append(
            "standard_consolidated must contain exactly one CSV: "
            f"{STANDARD_CSV_NAME}. Found: {', '.join(path.name for path in csvs) or 'none'}"
        )

    pointer_data = {}
    if not POINTER.exists():
        errors.append(f"Missing pointer file: {POINTER}")
    else:
        try:
            pointer_data = json.loads(POINTER.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Pointer file is not valid JSON: {exc}")
        expected_pointer = f"standard_consolidated/{STANDARD_CSV_NAME}"
        if pointer_data.get("canonical_consolidated_csv") != expected_pointer:
            errors.append(
                "CURRENT_STANDARD_DATASET.json must point to "
                f"{expected_pointer}; found {pointer_data.get('canonical_consolidated_csv')!r}"
            )

    counts: Counter[str] = Counter()
    if STANDARD_CSV.exists():
        counts = consolidated_counts(STANDARD_CSV)
        for dataset, source_name in STANDARD_SOURCES.items():
            source_path = BASE / source_name
            if not source_path.exists():
                errors.append(f"Missing standard source CSV: {source_name}")
                continue
            source_rows = csv_row_count(source_path)
            if counts.get(dataset, 0) != source_rows:
                errors.append(
                    f"Consolidated dataset {dataset} has {counts.get(dataset, 0)} rows; "
                    f"{source_name} has {source_rows} rows."
                )
        extra_datasets = sorted(set(counts) - set(STANDARD_SOURCES))
        if extra_datasets:
            errors.append(f"Unexpected dataset values in consolidated CSV: {', '.join(extra_datasets)}")

    app_findings = find_app_references()
    if app_findings:
        message = (
            f"{len(app_findings)} root HTML/JS legacy data references found. "
            "These files should be treated as legacy until rewired to CURRENT_STANDARD_DATASET.json."
        )
        if args.strict_app:
            errors.append(message)
        else:
            warnings.append(message)

    write_report(errors, warnings, counts, app_findings)

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("FAILED:")
        for error in errors:
            print(f"- {error}")
        print(f"Report: {REPORT}")
        return 1

    print("PASS: standard consolidated data source is valid.")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
