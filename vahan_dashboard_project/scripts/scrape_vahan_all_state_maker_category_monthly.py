#!/usr/bin/env python3
"""Scrape exact all-state monthly Maker x Vehicle Category data from VAHAN."""

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

from flatten_vahan_maker_fuel import parse_int
from vahan_harvest import URL, Harvester, Job


MONTHS = [
    ("JAN", 1),
    ("FEB", 2),
    ("MAR", 3),
    ("APR", 4),
    ("MAY", 5),
    ("JUN", 6),
    ("JUL", 7),
    ("AUG", 8),
    ("SEP", 9),
    ("OCT", 10),
    ("NOV", 11),
    ("DEC", 12),
]


def reset_to_first_page(harvester: Harvester) -> None:
    first_links = harvester.driver.find_elements(By.CSS_SELECTOR, "#groupingTable .ui-paginator-first")
    if not first_links:
        return
    first_link = first_links[-1]
    if "ui-state-disabled" in (first_link.get_attribute("class") or ""):
        return
    before_active = harvester.driver.find_element(
        By.CSS_SELECTOR, "#groupingTable .ui-paginator-page.ui-state-active"
    ).text
    harvester.driver.execute_script("arguments[0].click()", first_link)
    try:
        harvester.wait.until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#groupingTable .ui-paginator-page.ui-state-active").text
            != before_active
        )
    except TimeoutException:
        pass
    harvester.wait_idle()


def select_month(harvester: Harvester, year: str, month_number: int) -> None:
    month_value = f"{year}{month_number:02d}"
    before = harvester.driver.find_element(By.ID, "groupingTable").text
    harvester.set_select("groupingTable:selectMonth_input", month_value)
    try:
        harvester.wait.until(lambda d: d.find_element(By.ID, "groupingTable").text != before)
    except TimeoutException:
        pass
    time.sleep(harvester.job.delay)
    reset_to_first_page(harvester)


def scrape_current_table(harvester: Harvester, year: str, month_number: int) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    page = 1
    while True:
        for row in harvester.parse_page(year):
            key = json.dumps(row, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            row["calendar_year"] = year
            row["month"] = f"{year}-{month_number:02d}"
            row["month_number"] = month_number
            rows.append(row)
        print(f"all_state_maker_category_month/{year}-{month_number:02d}: page {page}, rows {len(rows)}", flush=True)
        if harvester.job.max_pages and page >= harvester.job.max_pages:
            break
        if not harvester.next_page():
            break
        page += 1
    return rows


def scrape_year(year: str, output_dir: Path, max_pages: int | None, delay: float, headful: bool) -> dict:
    job = Job("maker_fuel", "2w", [year], "C", output_dir, max_pages, delay, headful)
    harvester = Harvester(job)
    try:
        harvester.driver.set_page_load_timeout(60)
        try:
            harvester.driver.get(URL)
        except TimeoutException:
            harvester.driver.execute_script("window.stop();")
        harvester.wait.until(EC.presence_of_element_located((By.ID, "yaxisVar_input")))
        harvester.wait_idle()
        harvester.set_select("yaxisVar_input", "Maker")
        harvester.set_select("xaxisVar_input", "Vehicle Category")
        harvester.set_select("selectedYearType_input", "C")
        harvester.set_select("selectedYear_input", year)
        harvester.click_refresh("j_idt68")

        available = {
            int(str(value)[-2:]): str(value)
            for value, label in harvester.driver.execute_script(
                """
                return Array.from(document.getElementById('groupingTable:selectMonth_input').options)
                  .map(option => [option.value, option.textContent.trim()]);
                """
            )
            if str(value).startswith(year) and str(value) != year
        }

        records: list[dict] = []
        for _, month_number in MONTHS:
            if month_number not in available:
                continue
            select_month(harvester, year, month_number)
            records.extend(scrape_current_table(harvester, year, month_number))

        return {
            "source_url": URL,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
            "report": "all_state_maker_category_month",
            "y_axis": "Maker",
            "x_axis": "Vehicle Category",
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
    rows: list[dict[str, object]] = []
    for record in payload["records"]:
        maker = str(record.get("maker", "")).strip()
        for vehicle_category, value in record.get("values", {}).items():
            registrations = parse_int(value)
            if registrations == 0:
                continue
            rows.append(
                {
                    "calendar_year": record["calendar_year"],
                    "month": record["month"],
                    "month_number": record["month_number"],
                    "maker": maker,
                    "vehicle_category": vehicle_category,
                    "registrations": registrations,
                    "monthly_maker_total": parse_int(record.get("total")),
                    "source": "all_state_maker_category_month",
                    "scraped_at": payload["scraped_at"],
                }
            )
    rows.sort(key=lambda row: (row["month"], row["maker"], row["vehicle_category"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "calendar_year",
            "month",
            "month_number",
            "maker",
            "vehicle_category",
            "registrations",
            "monthly_maker_total",
            "source",
            "scraped_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", default=["2021", "2022", "2023", "2024", "2025", "2026"])
    parser.add_argument("--output-dir", type=Path, default=Path("data/vahan_2021_2026_calendar"))
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    json_output = args.output_dir / "all_state_maker_category_month.json"
    csv_output = args.output_dir / "all_state_maker_category_month_long.csv"
    if json_output.exists():
        payload = json.loads(json_output.read_text(encoding="utf-8"))
        payload["years"] = sorted(set([*payload.get("years", []), *args.years]))
    else:
        payload = {
            "source_url": URL,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
            "report": "all_state_maker_category_month",
            "y_axis": "Maker",
            "x_axis": "Vehicle Category",
            "year_type": "C",
            "years": args.years,
            "records": [],
        }
    completed_years = {str(record.get("calendar_year")) for record in payload.get("records", [])}

    for year in args.years:
        if year in completed_years:
            print(f"Skipping {year}; already present in {json_output}", flush=True)
            continue
        year_payload = None
        for attempt in range(1, 4):
            try:
                year_payload = scrape_year(year, args.output_dir, args.max_pages, args.delay, args.headful)
                break
            except Exception as exc:
                print(f"{year}: attempt {attempt} failed: {type(exc).__name__}: {exc}", flush=True)
                if attempt == 3:
                    raise
                time.sleep(10 * attempt)
        if year_payload is None:
            raise RuntimeError(f"Could not scrape {year}")
        payload["records"].extend(year_payload["records"])
        payload["scraped_at"] = datetime.now().isoformat(timespec="seconds")
        write_json(payload, json_output)
        row_count = write_long_csv(payload, csv_output)
        print(f"Wrote running all-state category payload: {len(payload['records'])} table rows, {row_count} long rows", flush=True)

    write_json(payload, json_output)
    row_count = write_long_csv(payload, csv_output)
    print(f"Wrote {len(payload['records'])} all-state category table rows to {json_output}")
    print(f"Wrote {row_count} long rows to {csv_output}")


if __name__ == "__main__":
    main()
