#!/usr/bin/env python3
"""Scrape exact VAHAN Maker x Fuel data month-by-month.

The VAHAN dashboard exposes a month dropdown inside the rendered Maker x Fuel
table. The generic harvester captures only the year total, so this script
drives that inner dropdown and writes monthly maker/fuel long-form CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from build_monthly_maker_fuel import fuel_group
from vahan_harvest import REPORTS, SEGMENTS, URL, Harvester, Job, number_from_text


MONTH_LABEL_TO_NUMBER = {
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


def month_options(harvester: Harvester, year: str) -> list[tuple[str, str, int]]:
    select_id = "groupingTable:selectMonth_input"
    harvester.wait.until(lambda d: d.find_elements(By.ID, select_id))
    raw_options = harvester.driver.execute_script(
        """
        return Array.from(document.getElementById(arguments[0]).options)
          .map(option => [option.value, option.textContent.trim()]);
        """,
        select_id,
    )
    options: list[tuple[str, str, int]] = []
    for value, label in raw_options:
        label = str(label).strip().upper()
        if value == year or label == year:
            continue
        month_number = MONTH_LABEL_TO_NUMBER.get(label)
        if month_number:
            options.append((str(value), label, month_number))
    return options


def parse_int(value: object) -> int:
    return number_from_text(str(value or "0"))


def scrape_current_table(harvester: Harvester, year: str, segment: str, month_value: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    page = 1
    while True:
        for row in harvester.parse_page(year):
            key = json.dumps(row, sort_keys=True)
            if key not in seen:
                seen.add(key)
                rows.append(row)
        print(f"maker_fuel_monthly/{segment}/{year}/{month_value}: page {page}, rows {len(rows)}", flush=True)
        if harvester.job.max_pages and page >= harvester.job.max_pages:
            break
        if not harvester.next_page():
            break
        page += 1
    return rows


def scrape_segment_year(job: Job, year: str) -> dict:
    harvester = Harvester(replace(job, years=[year], report="maker_fuel"))
    try:
        harvester.load_year(year)
        options = month_options(harvester, year)
        records: list[dict] = []
        for month_value, month_label, month_number in options:
            before = harvester.driver.find_element(By.ID, "groupingTable").text
            harvester.set_select("groupingTable:selectMonth_input", month_value)
            try:
                harvester.wait.until(lambda d: d.find_element(By.ID, "groupingTable").text != before)
            except TimeoutException:
                pass
            time.sleep(job.delay)
            for record in scrape_current_table(harvester, year, job.segment, month_value):
                record.update(
                    {
                        "calendar_year": year,
                        "month": f"{year}-{month_number:02d}",
                        "month_number": month_number,
                        "month_label": month_label,
                        "month_value": month_value,
                    }
                )
                records.append(record)
        return {
            "source_url": URL,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
            "report": "maker_fuel_monthly",
            "segment": SEGMENTS[job.segment]["label"],
            "segment_filter": {
                "name": SEGMENTS[job.segment]["filter_name"],
                "values": SEGMENTS[job.segment]["filter_values"],
                "category_values": SEGMENTS[job.segment]["category_values"],
            },
            "y_axis": REPORTS["maker_fuel"]["y_axis"],
            "x_axis": REPORTS["maker_fuel"]["x_axis"],
            "years": [year],
            "year_type": job.year_type,
            "records": records,
        }
    finally:
        harvester.close()


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csvs(payloads: list[dict], detail_output: Path, group_output: Path) -> tuple[int, int]:
    detail_rows: list[dict[str, object]] = []
    group_totals: dict[tuple[str, str, int, str, str, str], int] = {}
    group_meta: dict[tuple[str, str, int, str, str, str], dict[str, object]] = {}

    for payload in payloads:
        vehicle_category = payload["segment"]
        source_url = payload["source_url"]
        scraped_at = payload["scraped_at"]
        for record in payload["records"]:
            maker = str(record.get("maker", "")).strip()
            maker_total = parse_int(record.get("total"))
            for fuel_type, registrations_raw in record.get("values", {}).items():
                registrations = parse_int(registrations_raw)
                if registrations == 0:
                    continue
                group = fuel_group(fuel_type)
                detail_rows.append(
                    {
                        "calendar_year": record["calendar_year"],
                        "month": record["month"],
                        "month_number": record["month_number"],
                        "vehicle_category": vehicle_category,
                        "maker": maker,
                        "fuel_group": group,
                        "fuel_type": fuel_type,
                        "registrations": registrations,
                        "monthly_maker_total": maker_total,
                        "is_fuel_split_estimated": "false",
                        "source_file": f"{vehicle_category.lower()}_maker_fuel_monthly.json",
                        "source_url": source_url,
                        "scraped_at": scraped_at,
                    }
                )
                key = (
                    record["calendar_year"],
                    record["month"],
                    int(record["month_number"]),
                    vehicle_category,
                    maker,
                    group,
                )
                group_totals[key] = group_totals.get(key, 0) + registrations
                group_meta[key] = {
                    "monthly_maker_total": maker_total,
                    "source_file": f"{vehicle_category.lower()}_maker_fuel_monthly.json",
                    "source_url": source_url,
                    "scraped_at": scraped_at,
                }

    detail_rows.sort(
        key=lambda row: (
            row["month"],
            row["vehicle_category"],
            row["maker"],
            row["fuel_group"],
            row["fuel_type"],
        )
    )

    group_rows = []
    for key, registrations in group_totals.items():
        year, month, month_number, vehicle_category, maker, group = key
        meta = group_meta[key]
        group_rows.append(
            {
                "calendar_year": year,
                "month": month,
                "month_number": month_number,
                "vehicle_category": vehicle_category,
                "maker": maker,
                "fuel_group": group,
                "registrations": registrations,
                "monthly_maker_total": meta["monthly_maker_total"],
                "is_fuel_split_estimated": "false",
                "source_file": meta["source_file"],
                "source_url": meta["source_url"],
                "scraped_at": meta["scraped_at"],
            }
        )
    group_rows.sort(key=lambda row: (row["month"], row["vehicle_category"], row["maker"], row["fuel_group"]))

    detail_output.parent.mkdir(parents=True, exist_ok=True)
    with detail_output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "calendar_year",
            "month",
            "month_number",
            "vehicle_category",
            "maker",
            "fuel_group",
            "fuel_type",
            "registrations",
            "monthly_maker_total",
            "is_fuel_split_estimated",
            "source_file",
            "source_url",
            "scraped_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)

    with group_output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "calendar_year",
            "month",
            "month_number",
            "vehicle_category",
            "maker",
            "fuel_group",
            "registrations",
            "monthly_maker_total",
            "is_fuel_split_estimated",
            "source_file",
            "source_url",
            "scraped_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(group_rows)

    return len(detail_rows), len(group_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape exact monthly VAHAN Maker x Fuel tables.")
    parser.add_argument("--segments", nargs="+", choices=sorted(SEGMENTS), default=["2w", "4w"])
    parser.add_argument("--years", nargs="+", default=["2021", "2022", "2023", "2024", "2025", "2026"])
    parser.add_argument("--year-type", choices=["C", "F"], default="C")
    parser.add_argument("--output-dir", type=Path, default=Path("data/vahan_2021_2026_calendar"))
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--headful", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_payloads: list[dict] = []
    for segment in args.segments:
        segment_payload = {
            "source_url": URL,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
            "report": "maker_fuel_monthly",
            "segment": SEGMENTS[segment]["label"],
            "segment_filter": {
                "name": SEGMENTS[segment]["filter_name"],
                "values": SEGMENTS[segment]["filter_values"],
                "category_values": SEGMENTS[segment]["category_values"],
            },
            "y_axis": REPORTS["maker_fuel"]["y_axis"],
            "x_axis": REPORTS["maker_fuel"]["x_axis"],
            "years": args.years,
            "year_type": args.year_type,
            "records": [],
        }
        for year in args.years:
            job = Job("maker_fuel", segment, [year], args.year_type, args.output_dir, args.max_pages, args.delay, args.headful)
            year_payload = scrape_segment_year(job, year)
            segment_payload["records"].extend(year_payload["records"])
            segment_payload["scraped_at"] = datetime.now().isoformat(timespec="seconds")
            write_json(segment_payload, args.output_dir / f"{segment}_maker_fuel_monthly.json")
        all_payloads.append(segment_payload)

    detail_rows, group_rows = write_csvs(
        all_payloads,
        args.output_dir / "monthly_maker_fuel_vehicle_category_long.csv",
        args.output_dir / "monthly_maker_fuel_group_vehicle_category_long.csv",
    )
    print(f"Wrote {detail_rows} exact monthly maker-fuel rows")
    print(f"Wrote {group_rows} exact monthly maker-fuel-group rows")


if __name__ == "__main__":
    main()
