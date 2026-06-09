#!/usr/bin/env python3
"""Flatten VAHAN maker x fuel segment harvest JSON files into one long CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(str(value).replace(",", ""))


def fuel_group(fuel_type: str) -> str:
    fuel = fuel_type.upper()
    if "HYBRID" in fuel:
        return "Hybrid"
    if "ELECTRIC" in fuel or "EV" in fuel or "BOV" in fuel or "FUEL CELL" in fuel:
        return "EV"
    if "PETROL" in fuel or "ETHANOL" in fuel or "METHANOL" in fuel:
        return "Petrol"
    if "DIESEL" in fuel:
        return "Diesel"
    return "Others"


def flatten(input_dir: Path, output: Path) -> int:
    rows: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("*_maker_fuel.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        vehicle_category = payload.get("segment", path.name.split("_", 1)[0].upper())
        source_url = payload.get("source_url", "")
        scraped_at = payload.get("scraped_at", "")
        for record in payload.get("records", []):
            for fuel_type, registrations in record.get("values", {}).items():
                count = parse_int(registrations)
                if count == 0:
                    continue
                rows.append(
                    {
                        "financial_year": record.get("financial_year", ""),
                        "vehicle_category": vehicle_category,
                        "maker": record.get("maker", ""),
                        "fuel_group": fuel_group(fuel_type),
                        "fuel_type": fuel_type,
                        "registrations": count,
                        "maker_total": parse_int(record.get("total")),
                        "source_file": path.name,
                        "source_url": source_url,
                        "scraped_at": scraped_at,
                    }
                )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "financial_year",
            "vehicle_category",
            "maker",
            "fuel_group",
            "fuel_type",
            "registrations",
            "maker_total",
            "source_file",
            "source_url",
            "scraped_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/vahan_2yr_fuel_maker_category"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/vahan_2yr_fuel_maker_category/fuel_maker_vehicle_category_long.csv"),
    )
    args = parser.parse_args()
    count = flatten(args.input_dir, args.output)
    print(f"Wrote {count} non-zero fuel rows to {args.output}")


if __name__ == "__main__":
    main()
