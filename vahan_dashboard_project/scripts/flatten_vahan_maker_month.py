#!/usr/bin/env python3
"""Flatten VAHAN maker x month harvest JSON files into one long CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from flatten_vahan_monthly_fuel import MONTH_ORDER
from flatten_vahan_maker_fuel import parse_int


FIELDNAMES = [
    "calendar_year",
    "month",
    "month_number",
    "vehicle_category",
    "maker",
    "registrations",
    "annual_maker_total",
    "source_file",
    "source_url",
    "scraped_at",
]


def flatten(input_dir: Path, output: Path, include_zero_months: bool) -> int:
    rows: list[dict[str, object]] = []

    for path in sorted(input_dir.glob("*_maker_month.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        vehicle_category = payload.get("segment", path.name.split("_", 1)[0].upper())
        source_url = payload.get("source_url", "")
        scraped_at = payload.get("scraped_at", "")

        for record in payload.get("records", []):
            year = str(record.get("financial_year", ""))
            maker = str(record.get("maker", "")).strip()
            annual_total = parse_int(record.get("total"))

            for month_name, month_number in MONTH_ORDER.items():
                registrations = parse_int(record.get("values", {}).get(month_name, 0))
                if registrations == 0 and not include_zero_months:
                    continue
                rows.append(
                    {
                        "calendar_year": year,
                        "month": f"{year}-{month_number:02d}",
                        "month_number": month_number,
                        "vehicle_category": vehicle_category,
                        "maker": maker,
                        "registrations": registrations,
                        "annual_maker_total": annual_total,
                        "source_file": path.name,
                        "source_url": source_url,
                        "scraped_at": scraped_at,
                    }
                )

    rows.sort(key=lambda row: (row["month"], row["vehicle_category"], row["maker"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/vahan_2021_2026_calendar"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/vahan_2021_2026_calendar/monthly_maker_vehicle_category_long.csv"),
    )
    parser.add_argument(
        "--include-zero-months",
        action="store_true",
        help="Keep explicit zero rows for each maker-month. Default keeps only non-zero registrations.",
    )
    args = parser.parse_args()
    count = flatten(args.input_dir, args.output, args.include_zero_months)
    print(f"Wrote {count} monthly maker rows to {args.output}")


if __name__ == "__main__":
    main()
