#!/usr/bin/env python3
"""Build the single standard VAHAN consolidated CSV.

The output is intentionally one long CSV with a `dataset` column. Different
VAHAN cross-tabs have different natural dimensions, so unused dimensions are
left blank while common fields stay consistent.
"""

from __future__ import annotations

import csv
from pathlib import Path


BASE = Path("data/vahan_2021_2026_calendar")
OUT_DIR = BASE / "standard_consolidated"
OUT = OUT_DIR / "vahan_standard_consolidated_long.csv"

FIELDNAMES = [
    "dataset",
    "calendar_year",
    "month",
    "month_number",
    "state_code",
    "state",
    "maker",
    "vehicle_category",
    "fuel_group",
    "fuel_type",
    "registrations",
    "monthly_row_total",
    "annual_maker_total",
    "source",
    "scraped_at",
    "source_file",
]


def read_rows(name: str) -> list[dict[str, str]]:
    with (BASE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def base_row(dataset: str, row: dict[str, str], source_file: str) -> dict[str, str]:
    return {
        "dataset": dataset,
        "calendar_year": row.get("calendar_year", ""),
        "month": row.get("month", ""),
        "month_number": row.get("month_number", ""),
        "state_code": row.get("state_code", ""),
        "state": row.get("state", ""),
        "maker": row.get("maker", ""),
        "vehicle_category": row.get("vehicle_category", ""),
        "fuel_group": row.get("fuel_group", ""),
        "fuel_type": row.get("fuel_type", ""),
        "registrations": row.get("registrations", ""),
        "monthly_row_total": "",
        "annual_maker_total": "",
        "source": row.get("source", ""),
        "scraped_at": row.get("scraped_at", ""),
        "source_file": source_file,
    }


def transformed_rows() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    source = "all_state_maker_month_long.csv"
    for row in read_rows(source):
        item = base_row("national_maker_month", row, source)
        item["annual_maker_total"] = row.get("annual_maker_total", "")
        out.append(item)

    source = "state_maker_fuel_month_long.csv"
    for row in read_rows(source):
        item = base_row("state_maker_fuel", row, source)
        item["monthly_row_total"] = row.get("monthly_state_maker_total", "")
        out.append(item)

    source = "state_maker_category_month_long.csv"
    for row in read_rows(source):
        item = base_row("state_maker_category", row, source)
        item["monthly_row_total"] = row.get("monthly_state_row_total", "")
        out.append(item)

    source = "state_category_fuel_month_long.csv"
    for row in read_rows(source):
        item = base_row("state_category_fuel", row, source)
        item["monthly_row_total"] = row.get("monthly_state_row_total", "")
        out.append(item)

    out.sort(
        key=lambda row: (
            row["dataset"],
            row["state_code"],
            row["month"],
            row["maker"],
            row["vehicle_category"],
            row["fuel_group"],
            row["fuel_type"],
        )
    )
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = transformed_rows()
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
