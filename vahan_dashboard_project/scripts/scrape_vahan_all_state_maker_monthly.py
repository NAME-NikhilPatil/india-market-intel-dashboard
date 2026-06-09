#!/usr/bin/env python3
"""Scrape all-state VAHAN Maker x Month Wise data.

This report is the best source for national maker monthly totals:

  Y-Axis    = Maker
  X-Axis    = Month Wise
  State     = All Vahan4 Running States
  Year Type = Calendar Year

It intentionally does not apply vehicle category, class, maker, fuel, or state
filters. The output is a raw JSON payload plus a long CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from flatten_vahan_maker_fuel import parse_int
from flatten_vahan_monthly_fuel import MONTH_ORDER
from vahan_harvest import URL, Harvester, Job


DATA_DIR = Path("data/vahan_2021_2026_calendar")


def setup_year(year: str, output_dir: Path, max_pages: int | None,
               delay: float, headful: bool, wait_seconds: int,
               page_timeout: int) -> Harvester:
    job = Job("maker_month", "2w", [year], "C", output_dir, max_pages, delay, headful)
    harvester = Harvester(job)
    harvester.wait = WebDriverWait(harvester.driver, wait_seconds)
    harvester.driver.set_page_load_timeout(page_timeout)
    try:
        harvester.driver.get(URL)
    except TimeoutException:
        harvester.driver.execute_script("window.stop();")
    harvester.wait.until(EC.presence_of_element_located((By.ID, "yaxisVar_input")))
    harvester.wait_idle()
    harvester.set_select("yaxisVar_input", "Maker")
    harvester.set_select("xaxisVar_input", "Month Wise")
    harvester.set_select("selectedYearType_input", "C")
    harvester.set_select("selectedYear_input", year)
    harvester.click_refresh("j_idt68")
    harvester.wait.until(lambda d: "Maker" in d.find_element(By.ID, "groupingTable").text)
    return harvester


def scrape_year(year: str, output_dir: Path, max_pages: int | None,
                delay: float, headful: bool, wait_seconds: int,
                page_timeout: int) -> dict:
    harvester = setup_year(year, output_dir, max_pages, delay, headful, wait_seconds, page_timeout)
    try:
        records = []
        seen = set()
        page = 1
        while True:
            for record in harvester.parse_page(year):
                record.pop("segment", None)
                key = json.dumps(record, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                records.append(record)
            print(f"all_state_maker_month/{year}: page {page}, rows {len(records)}", flush=True)
            if max_pages and page >= max_pages:
                break
            if not harvester.next_page():
                break
            page += 1
        title = harvester.driver.find_element(By.ID, "groupingTable").text.splitlines()[0]
        return {
            "source_url": URL,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
            "report": "all_state_maker_month",
            "title": title,
            "y_axis": "Maker",
            "x_axis": "Month Wise",
            "year_type": "C",
            "years": [year],
            "records": records,
        }
    finally:
        harvester.close()


def write_json(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_long_csv(payload: dict, output: Path) -> int:
    rows = []
    for record in payload.get("records", []):
        year = str(record.get("financial_year", ""))
        maker = str(record.get("maker", "")).strip()
        annual_total = parse_int(record.get("total"))
        for month_name, month_number in MONTH_ORDER.items():
            registrations = parse_int(record.get("values", {}).get(month_name, 0))
            if registrations == 0:
                continue
            rows.append(
                {
                    "calendar_year": year,
                    "month": f"{year}-{month_number:02d}",
                    "month_number": month_number,
                    "maker": maker,
                    "registrations": registrations,
                    "annual_maker_total": annual_total,
                    "source": payload["report"],
                    "source_url": payload["source_url"],
                    "scraped_at": payload["scraped_at"],
                }
            )
    rows.sort(key=lambda row: (row["month"], row["maker"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "calendar_year",
            "month",
            "month_number",
            "maker",
            "registrations",
            "annual_maker_total",
            "source",
            "source_url",
            "scraped_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", default=["2026"])
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--delay", type=float, default=0.30)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument("--page-timeout", type=int, default=120)
    args = parser.parse_args()

    output_json = args.output_dir / "all_state_maker_month.json"
    output_csv = args.output_dir / "all_state_maker_month_long.csv"
    payload = {
        "source_url": URL,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "report": "all_state_maker_month",
        "y_axis": "Maker",
        "x_axis": "Month Wise",
        "year_type": "C",
        "years": [],
        "records": [],
    }
    for year in args.years:
        year_payload = scrape_year(
            year, args.output_dir, args.max_pages, args.delay,
            args.headful, args.wait_seconds, args.page_timeout
        )
        payload["years"].append(year)
        payload["scraped_at"] = year_payload["scraped_at"]
        payload["records"].extend(year_payload["records"])
        write_json(payload, output_json)
        rows = write_long_csv(payload, output_csv)
        print(f"Wrote {rows} long rows to {output_csv}", flush=True)
    write_json(payload, output_json)
    rows = write_long_csv(payload, output_csv)
    print(f"Done. Wrote {len(payload['records'])} maker rows to {output_json}; {rows} long rows to {output_csv}")


if __name__ == "__main__":
    main()
