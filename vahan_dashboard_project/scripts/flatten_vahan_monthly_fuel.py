#!/usr/bin/env python3
"""Flatten VAHAN fuel x month segment harvest JSON files into monthly rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from flatten_vahan_maker_fuel import fuel_group, parse_int


MONTH_ORDER = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def flatten(input_dir: Path, output: Path) -> int:
    grouped: dict[tuple[str, str, str, str, str], int] = {}
    raw_total: dict[tuple[str, str, str, str], int] = {}

    for path in sorted(input_dir.glob("*_fuel_month.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        vehicle_category = payload.get("segment", path.name.split("_", 1)[0].upper())
        for record in payload.get("records", []):
            year = str(record.get("financial_year", ""))
            raw_fuel = str(record.get("fuel", ""))
            group = fuel_group(raw_fuel)
            for month, value in record.get("values", {}).items():
                count = parse_int(value)
                month_num = MONTH_ORDER.get(month.upper())
                if not month_num:
                    continue
                month_key = f"{year}-{month_num:02d}"
                grouped[(year, month_key, vehicle_category, group, raw_fuel)] = (
                    grouped.get((year, month_key, vehicle_category, group, raw_fuel), 0) + count
                )
                raw_total[(year, month_key, vehicle_category, group)] = (
                    raw_total.get((year, month_key, vehicle_category, group), 0) + count
                )

    rows = [
        {
            "calendar_year": year,
            "month": month_key,
            "vehicle_category": vehicle_category,
            "fuel_group": group,
            "fuel_type": raw_fuel,
            "registrations": registrations,
        }
        for (year, month_key, vehicle_category, group, raw_fuel), registrations in grouped.items()
        if registrations
    ]
    rows.sort(key=lambda row: (row["month"], row["vehicle_category"], row["fuel_group"], row["fuel_type"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["calendar_year", "month", "vehicle_category", "fuel_group", "fuel_type", "registrations"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/vahan_2021_2026_calendar"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/vahan_2021_2026_calendar/monthly_fuel_vehicle_category_long.csv"),
    )
    args = parser.parse_args()
    count = flatten(args.input_dir, args.output)
    print(f"Wrote {count} monthly fuel rows to {args.output}")


if __name__ == "__main__":
    main()
