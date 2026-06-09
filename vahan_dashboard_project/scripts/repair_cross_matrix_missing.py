#!/usr/bin/env python3
"""Repair maker-month rows missing from one all-state monthly matrix.

Compares:
  - all_state_maker_fuel_month_long.csv
  - all_state_maker_category_month_long.csv

If a maker-month has positive registrations in one matrix and zero rows in
the other, this script re-scrapes only that year-month selector and merges
only the missing makers back into the relevant raw JSON.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent))
from selenium.common.exceptions import TimeoutException  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore

from vahan_harvest import URL, Harvester, Job  # type: ignore
import scrape_vahan_all_state_maker_fuel_monthly as fuel_scraper  # type: ignore
import scrape_vahan_all_state_maker_category_monthly as category_scraper  # type: ignore


DATA_DIR = Path("data/vahan_2021_2026_calendar")


def read_totals(path: Path) -> dict[tuple[str, str, str], int]:
    totals: dict[tuple[str, str, str], int] = defaultdict(int)
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            totals[(row["calendar_year"], row["month"], row["maker"])] += int(row["registrations"])
    return totals


def find_missing(data_dir: Path, threshold: int) -> tuple[list[tuple[int, tuple[str, str, str]]], list[tuple[int, tuple[str, str, str]]]]:
    fuel = read_totals(data_dir / "all_state_maker_fuel_month_long.csv")
    category = read_totals(data_dir / "all_state_maker_category_month_long.csv")
    missing_category = sorted(
        [(value, key) for key, value in fuel.items() if value > threshold and category.get(key, 0) == 0],
        reverse=True,
    )
    missing_fuel = sorted(
        [(value, key) for key, value in category.items() if value > threshold and fuel.get(key, 0) == 0],
        reverse=True,
    )
    return missing_category, missing_fuel


def setup_harvester(year: str, x_axis: str, output_dir: Path, delay: float,
                    headful: bool, max_pages: Optional[int]) -> Harvester:
    job = Job("maker_fuel", "2w", [year], "C", output_dir, max_pages, delay, headful)
    harvester = Harvester(job)
    harvester.driver.set_page_load_timeout(60)
    try:
        harvester.driver.get(URL)
    except TimeoutException:
        harvester.driver.execute_script("window.stop();")
    harvester.wait.until(EC.presence_of_element_located((By.ID, "yaxisVar_input")))
    harvester.wait_idle()
    harvester.set_select("yaxisVar_input", "Maker")
    harvester.set_select("xaxisVar_input", x_axis)
    harvester.set_select("selectedYearType_input", "C")
    harvester.set_select("selectedYear_input", year)
    harvester.click_refresh("j_idt68")
    return harvester


def scrape_missing(axis_name: str,
                   x_axis: str,
                   select_month: Callable[[Harvester, str, int], None],
                   scrape_current_table: Callable[[Harvester, str, int], list[dict]],
                   targets: list[tuple[int, tuple[str, str, str]]],
                   output_dir: Path,
                   delay: float,
                   headful: bool,
                   max_pages: Optional[int],
                   attempts: int) -> list[dict]:
    by_year_month: dict[tuple[str, int], set[str]] = defaultdict(set)
    for _, (year, month, maker) in targets:
        by_year_month[(year, int(month[-2:]))].add(maker)

    records: list[dict] = []
    for (year, month_number), makers in sorted(by_year_month.items()):
        print(f"\n{axis_name}: {year}-{month_number:02d} · {len(makers)} makers", flush=True)
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            harvester: Optional[Harvester] = None
            try:
                if attempt > 1:
                    print(f"  retry {attempt}/{attempts}", flush=True)
                harvester = setup_harvester(year, x_axis, output_dir, delay, headful, max_pages)
                select_month(harvester, year, month_number)
                rows = scrape_current_table(harvester, year, month_number)
                rows = [r for r in rows if (r.get("maker") or "").strip() in makers]
                records.extend(rows)
                print(f"  merged candidates: {len(rows)}", flush=True)
                break
            except Exception as e:
                last_error = e
                print(f"  failed: {type(e).__name__}: {e}", flush=True)
                time.sleep(3 * attempt)
            finally:
                if harvester:
                    harvester.close()
        else:
            raise RuntimeError(f"{axis_name} {year}-{month_number:02d} failed") from last_error
    return records


def merge_payload(payload_path: Path, records: list[dict]) -> None:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    key = lambda row: ((row.get("maker") or "").strip(), row.get("month") or "")
    replace = {key(row) for row in records}
    payload["records"] = [row for row in payload.get("records", []) if key(row) not in replace] + records
    payload["records"].sort(key=lambda row: (row.get("month") or "", (row.get("maker") or "").strip()))
    payload["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--threshold", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    missing_category, missing_fuel = find_missing(args.data_dir, args.threshold)
    print(f"Missing category maker-months: {len(missing_category)}")
    for value, key in missing_category[:80]:
        print(f"  category <- {value:>8} {key}")
    if len(missing_category) > 80:
        print(f"  ... {len(missing_category) - 80} more")
    print(f"\nMissing fuel maker-months: {len(missing_fuel)}")
    for value, key in missing_fuel[:80]:
        print(f"  fuel     <- {value:>8} {key}")
    if len(missing_fuel) > 80:
        print(f"  ... {len(missing_fuel) - 80} more")

    if args.dry_run or (not missing_category and not missing_fuel):
        return

    if missing_category:
        records = scrape_missing(
            "category",
            "Vehicle Category",
            category_scraper.select_month,
            category_scraper.scrape_current_table,
            missing_category,
            args.data_dir,
            args.delay,
            args.headful,
            args.max_pages,
            args.attempts,
        )
        print(f"\nMerging {len(records)} category rows", flush=True)
        merge_payload(args.data_dir / "all_state_maker_category_month.json", records)
        payload = json.loads((args.data_dir / "all_state_maker_category_month.json").read_text(encoding="utf-8"))
        rows = category_scraper.write_long_csv(payload, args.data_dir / "all_state_maker_category_month_long.csv")
        print(f"Wrote {rows} category long rows", flush=True)

    if missing_fuel:
        records = scrape_missing(
            "fuel",
            "Fuel",
            fuel_scraper.select_month,
            fuel_scraper.scrape_current_table,
            missing_fuel,
            args.data_dir,
            args.delay,
            args.headful,
            args.max_pages,
            args.attempts,
        )
        print(f"\nMerging {len(records)} fuel rows", flush=True)
        merge_payload(args.data_dir / "all_state_maker_fuel_month.json", records)
        payload = json.loads((args.data_dir / "all_state_maker_fuel_month.json").read_text(encoding="utf-8"))
        rows = fuel_scraper.write_long_csv(payload, args.data_dir / "all_state_maker_fuel_month_long.csv")
        print(f"Wrote {rows} fuel long rows", flush=True)
        print("Re-running classifier", flush=True)
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "classify_all_state_maker_fuel_month.py")],
            check=True,
        )

    remaining_category, remaining_fuel = find_missing(args.data_dir, args.threshold)
    print("\nVerification")
    print(f"  Missing category maker-months: {len(remaining_category)}")
    print(f"  Missing fuel maker-months: {len(remaining_fuel)}")


if __name__ == "__main__":
    main()
