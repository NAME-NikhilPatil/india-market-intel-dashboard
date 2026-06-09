#!/usr/bin/env python3
"""Move legacy VAHAN outputs out of the active project surface.

The archive is non-destructive: files are moved into archive/ with SHA-256
checksums and original paths recorded in a manifest. Active scrape/finalize
operations should not read anything from this archive.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "vahan_2021_2026_calendar"
ARCHIVE_ROOT = PROJECT_ROOT / "archive" / "legacy_pre_standardization_20260530"

LEGACY_DATA_FILES = [
    "2w_fuel_month.csv",
    "2w_fuel_month.json",
    "2w_maker_fuel.csv",
    "2w_maker_fuel.json",
    "2w_maker_month.csv",
    "2w_maker_month.json",
    "4w_fuel_month.csv",
    "4w_fuel_month.json",
    "4w_maker_fuel.csv",
    "4w_maker_fuel.json",
    "4w_maker_month.csv",
    "4w_maker_month.json",
    "annual_ev_penetration_by_category.csv",
    "fuel_maker_vehicle_category_long.csv",
    "monthly_ev_penetration_all_categories.csv",
    "monthly_fuel_vehicle_category_long.csv",
    "monthly_maker_vehicle_category_long.csv",
    "all_state_maker_category_month.json",
    "all_state_maker_category_month_long.csv",
    "all_state_maker_fuel_month.json",
    "all_state_maker_fuel_month_long.csv",
]

LEGACY_ROOT_FILES = [
    "ACTUAL_DATA_STATUS.md",
    "README.txt",
    "index.html",
    "state_payload.js",
    "Vahaan Workbench _populated_.html",
    "Vahaan Workbench _standalone_.html",
    "vahan_dashboard_v18.html.bak",
]

LEGACY_ROOT_PATTERNS = [
    "state_payload.bak.*",
    "vahan_dashboard_v18.bak.*",
    "vahan_dashboard_v*.html",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for name in LEGACY_DATA_FILES:
        path = DATA_DIR / name
        if path.exists():
            files.append((path, "legacy/exploratory data output"))
    for name in LEGACY_ROOT_FILES:
        path = PROJECT_ROOT / name
        if path.exists():
            files.append((path, "legacy static dashboard/app artifact"))
    for pattern in LEGACY_ROOT_PATTERNS:
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            if path.exists():
                files.append((path, "legacy static dashboard/app artifact"))

    seen = set()
    unique: list[tuple[Path, str]] = []
    for path, reason in files:
        if path in seen:
            continue
        seen.add(path)
        unique.append((path, reason))
    return unique


def archive_destination(path: Path) -> Path:
    rel = path.relative_to(PROJECT_ROOT)
    return ARCHIVE_ROOT / rel


def write_manifest(rows: list[dict[str, str]]) -> None:
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = ARCHIVE_ROOT / "ARCHIVE_MANIFEST.csv"
    exists = manifest.exists()
    with manifest.open("a", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "archived_at",
            "original_path",
            "archive_path",
            "bytes",
            "sha256",
            "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    archived_at = datetime.now().astimezone().isoformat(timespec="seconds")
    files = candidate_files()
    if not files:
        print("No legacy files found in the active locations.")
        return

    for path, reason in files:
        dest = archive_destination(path)
        file_hash = sha256(path)
        row = {
            "archived_at": archived_at,
            "original_path": str(path.relative_to(PROJECT_ROOT)),
            "archive_path": str(dest.relative_to(PROJECT_ROOT)),
            "bytes": str(path.stat().st_size),
            "sha256": file_hash,
            "reason": reason,
        }
        rows.append(row)
        if args.dry_run:
            print(f"Would archive {row['original_path']} -> {row['archive_path']}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise FileExistsError(f"Archive destination already exists: {dest}")
        shutil.move(str(path), str(dest))
        print(f"Archived {row['original_path']} -> {row['archive_path']}")

    if not args.dry_run:
        write_manifest(rows)
        print(f"Wrote manifest: {ARCHIVE_ROOT / 'ARCHIVE_MANIFEST.csv'}")


if __name__ == "__main__":
    main()
