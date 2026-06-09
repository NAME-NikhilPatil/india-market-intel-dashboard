#!/usr/bin/env python3
"""Build exact annual segment EV penetration and overall monthly EV penetration."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(input_dir: Path) -> None:
    maker_rows = read_csv(input_dir / "fuel_maker_vehicle_category_long.csv")
    monthly_rows = read_csv(input_dir / "monthly_fuel_vehicle_category_long.csv")

    annual = defaultdict(lambda: {"ev": 0, "total": 0})
    for row in maker_rows:
        key = (row["financial_year"], row["vehicle_category"])
        registrations = int(row["registrations"])
        annual[key]["total"] += registrations
        if row["fuel_group"] == "EV":
            annual[key]["ev"] += registrations

    annual_rows = []
    for (year, category), values in sorted(annual.items()):
        total = values["total"]
        ev = values["ev"]
        annual_rows.append(
            {
                "calendar_year": year,
                "vehicle_category": category,
                "ev_registrations": ev,
                "total_registrations": total,
                "ev_penetration": ev / total if total else 0,
            }
        )

    monthly = defaultdict(lambda: {"ev": 0, "total": 0})
    seen = set()
    # The VAHAN Month Wise table ignores segment filters. Use one copy of each
    # raw monthly fuel row, and label it as all-category monthly penetration.
    for row in monthly_rows:
        key_raw = (row["month"], row["fuel_type"], row["registrations"])
        if key_raw in seen:
            continue
        seen.add(key_raw)
        key = (row["calendar_year"], row["month"])
        registrations = int(row["registrations"])
        monthly[key]["total"] += registrations
        if row["fuel_group"] == "EV":
            monthly[key]["ev"] += registrations

    monthly_rows_out = []
    for (year, month), values in sorted(monthly.items()):
        total = values["total"]
        ev = values["ev"]
        monthly_rows_out.append(
            {
                "calendar_year": year,
                "month": month,
                "vehicle_category": "All",
                "ev_registrations": ev,
                "total_registrations": total,
                "ev_penetration": ev / total if total else 0,
            }
        )

    write_csv(
        input_dir / "annual_ev_penetration_by_category.csv",
        annual_rows,
        ["calendar_year", "vehicle_category", "ev_registrations", "total_registrations", "ev_penetration"],
    )
    write_csv(
        input_dir / "monthly_ev_penetration_all_categories.csv",
        monthly_rows_out,
        ["calendar_year", "month", "vehicle_category", "ev_registrations", "total_registrations", "ev_penetration"],
    )
    print(f"Wrote {len(annual_rows)} annual rows and {len(monthly_rows_out)} monthly rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/vahan_2021_2026_calendar"))
    args = parser.parse_args()
    build(args.input_dir)


if __name__ == "__main__":
    main()
