#!/usr/bin/env python3
"""Re-scrape ONLY the (maker, year, month) cells that are missing from the
existing all_state_maker_fuel_month scrape.

Why this exists
---------------

The original scrape (scrape_vahan_all_state_maker_fuel_monthly.py) drops the
WHOLE year if a single cell errors out, and skips a year if it is already
present in the payload. Some cells went missing silently anyway — most
notably Ather Energy × May 2023, which is present in the v7 annual scrape
(111,491 EVs in 2023) but absent from the monthly scrape.

This script:
  1. Audits the existing all_state_maker_fuel_month.json by comparing the
     monthly sum per (maker, year) against the v7 annual totals embedded in
     vahan_dashboard_v7.html. Anywhere the monthly sum is materially less
     than the v7 annual AND specific months are missing for that maker,
     those months are flagged.
  2. Optionally accepts an explicit --targets list of "MAKER@YYYY-MM" pairs.
  3. Drives Selenium with the existing Harvester to re-scrape only those
     (year, month) selectors and pulls only the listed makers' rows.
  4. Merges the new records into all_state_maker_fuel_month.json,
     replacing any pre-existing record with the same (maker, calendar_year,
     month) key.
  5. Re-flattens all_state_maker_fuel_month_long.csv.
  6. Re-runs classify_all_state_maker_fuel_month.py so the classified file
     also picks up the back-fill.
  7. Prints a verification report.

Prerequisites
-------------

Same as the other scrapers in scripts/:
  - Python 3.9+, the deps in scripts/requirements-vahan.txt
  - Selenium with Chrome (the build_driver helper expects Chrome at the
    macOS path /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
    when present; otherwise falls back to chromedriver on PATH)

Usage
-----

  # Auto-detect and re-scrape every missing cell:
  python3 scripts/rescrape_missing_cells.py

  # Re-scrape a specific list of targets:
  python3 scripts/rescrape_missing_cells.py --targets \
      "ATHER ENERGY LTD@2023-05" \
      "GOREEN E-MOBILITY PVT LTD@2022-04"

  # Headful mode (visible browser) for debugging:
  python3 scripts/rescrape_missing_cells.py --headful

  # Dry-run: print the audit + targets, do not scrape:
  python3 scripts/rescrape_missing_cells.py --dry-run

  # Custom data directory:
  python3 scripts/rescrape_missing_cells.py --data-dir data/vahan_2021_2026_calendar
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Use the existing Harvester / scrape helpers verbatim.
sys.path.insert(0, str(Path(__file__).parent))
from vahan_harvest import URL, Harvester, Job  # type: ignore
from scrape_vahan_all_state_maker_fuel_monthly import (  # type: ignore
    select_month,
    scrape_current_table,
    write_long_csv,
)
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


DEFAULT_DATA_DIR = Path("data/vahan_2021_2026_calendar")
DEFAULT_HTML = Path("vahan_dashboard_v7.html")


# ---------------------------------------------------------------------------
# Audit: detect missing (maker, year, month) cells by comparing
# annual-scrape totals (embedded in v7) against current monthly sums.
# ---------------------------------------------------------------------------

def extract_v7_annual(html_path: Path) -> dict[str, dict[int, int]]:
    """Pull the embedded JSON payload out of v7 and return per-maker annual
    totals keyed by raw maker (uppercase) name.
    Returns: { 'ATHER ENERGY LTD': { 2021: ..., 2022: ..., ... } }"""
    if not html_path.exists():
        raise FileNotFoundError(f"v7 HTML not found at {html_path}")
    raw = html_path.read_text(encoding="utf-8")
    m = re.search(
        r'<script id="payload" type="application/json">(.+?)</script>',
        raw, flags=re.DOTALL,
    )
    if not m:
        raise RuntimeError("payload script not found in v7 HTML")
    payload = json.loads(m.group(1))
    out: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for row in payload["rows"]:
        out[row["maker"]][row["year"]] += row["n"]
    return {k: dict(v) for k, v in out.items()}


def read_monthly_scrape(json_path: Path) -> dict:
    if not json_path.exists():
        return {"records": []}
    return json.loads(json_path.read_text(encoding="utf-8"))


def audit(html_path: Path, json_path: Path,
          tolerance: int = 100) -> list[tuple[str, int, str]]:
    """Return a list of (raw_maker, year, 'YYYY-MM') triples that are
    missing from the monthly scrape but should exist per v7 annual."""
    v7_annual = extract_v7_annual(html_path)
    monthly = read_monthly_scrape(json_path)
    # Build current monthly sums and month-coverage per maker × year
    by_my: dict[tuple[str, int], int] = defaultdict(int)
    months_present: dict[tuple[str, int], set[str]] = defaultdict(set)
    for rec in monthly.get("records", []):
        maker = (rec.get("maker") or "").strip()
        yr = int(rec.get("calendar_year") or 0)
        if not maker or not yr:
            continue
        by_my[(maker, yr)] += int(rec.get("total") or 0)
        months_present[(maker, yr)].add(rec.get("month") or "")

    gaps: list[tuple[str, int, str]] = []
    for maker, by_year in v7_annual.items():
        for yr, annual in by_year.items():
            if yr == 2026:
                continue  # partial year, skip
            if annual <= tolerance:
                continue
            monthly_sum = by_my.get((maker, yr), 0)
            diff = annual - monthly_sum
            if diff <= tolerance:
                continue
            # Find which months are missing for that maker × year
            present = months_present.get((maker, yr), set())
            expected = [f"{yr}-{m:02d}" for m in range(1, 13)]
            missing = [m for m in expected if m not in present]
            for mon in missing:
                gaps.append((maker, yr, mon))
    return gaps


# ---------------------------------------------------------------------------
# Re-scrape one (year, month) selector, keeping only the requested makers.
# ---------------------------------------------------------------------------

def rescrape_month(harvester: Harvester, year: str, month_number: int,
                   wanted_makers: set[str]) -> list[dict]:
    select_month(harvester, year, month_number)
    rows = scrape_current_table(harvester, year, month_number)
    if wanted_makers:
        rows = [r for r in rows if (r.get("maker") or "").strip() in wanted_makers]
    return rows


def rescrape_year_months(year: str, months: list[int],
                         wanted_makers: set[str],
                         output_dir: Path, delay: float, headful: bool,
                         max_pages: Optional[int]) -> list[dict]:
    """Drive Selenium once per year, walk the listed months, return rows."""
    job = Job("maker_fuel", "2w", [year], "C", output_dir, max_pages, delay, headful)
    h = Harvester(job)
    out: list[dict] = []
    try:
        h.driver.set_page_load_timeout(60)
        try:
            h.driver.get(URL)
        except TimeoutException:
            h.driver.execute_script("window.stop();")
        h.wait.until(EC.presence_of_element_located((By.ID, "yaxisVar_input")))
        h.wait_idle()
        h.set_select("yaxisVar_input", "Maker")
        h.set_select("xaxisVar_input", "Fuel")
        h.set_select("selectedYearType_input", "C")
        h.set_select("selectedYear_input", year)
        h.click_refresh("j_idt68")
        for mn in months:
            try:
                rows = rescrape_month(h, year, mn, wanted_makers)
                out.extend(rows)
                print(f"  {year}-{mn:02d}: {len(rows)} matching rows", flush=True)
            except Exception as e:
                print(f"  {year}-{mn:02d}: FAILED {type(e).__name__}: {e}", flush=True)
    finally:
        h.close()
    return out


def rescrape_year_months_with_retries(year: str, months: list[int],
                                      wanted_makers: set[str],
                                      output_dir: Path, delay: float,
                                      headful: bool,
                                      max_pages: Optional[int],
                                      attempts: int = 3) -> list[dict]:
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                print(f"  retrying {year}, attempt {attempt}/{attempts}", flush=True)
            return rescrape_year_months(year, months, wanted_makers,
                                        output_dir, delay, headful, max_pages)
        except Exception as e:
            last_error = e
            print(f"  {year}: attempt {attempt} failed: {type(e).__name__}: {e}",
                  flush=True)
            time.sleep(3 * attempt)
    raise RuntimeError(f"{year}: failed after {attempts} attempts") from last_error


# ---------------------------------------------------------------------------
# Merge new rows into the existing JSON, replacing any prior (maker, ym) row.
# ---------------------------------------------------------------------------

def merge_into_payload(payload_path: Path, new_records: list[dict]) -> int:
    """Replace any existing (maker, month) entries with the new ones; append
    the rest. Returns the count of merged rows."""
    payload = read_monthly_scrape(payload_path)
    existing = payload.get("records", [])
    key = lambda r: ((r.get("maker") or "").strip(), r.get("month") or "")
    keys_to_replace = {key(r) for r in new_records}
    kept = [r for r in existing if key(r) not in keys_to_replace]
    merged = kept + new_records
    # Sort canonically: month then maker
    merged.sort(key=lambda r: (r.get("month") or "", (r.get("maker") or "").strip()))
    payload["records"] = merged
    payload["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(new_records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_target(s: str) -> tuple[str, int, str]:
    """Parse 'MAKER@YYYY-MM' → (maker, year, 'YYYY-MM')."""
    if "@" not in s:
        raise ValueError(f"bad target: {s!r} (expected MAKER@YYYY-MM)")
    maker, ym = s.rsplit("@", 1)
    yr, mn = ym.split("-")
    return maker.strip(), int(yr), f"{int(yr)}-{int(mn):02d}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--v7-html", type=Path, default=DEFAULT_HTML,
                   help="Path to vahan_dashboard_v7.html (used for annual reference)")
    p.add_argument("--targets", nargs="*", default=[],
                   help='Manual targets, e.g. "ATHER ENERGY LTD@2023-05"')
    p.add_argument("--dry-run", action="store_true",
                   help="Audit only, don't actually scrape")
    p.add_argument("--delay", type=float, default=0.25)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--headful", action="store_true")
    p.add_argument("--tolerance", type=int, default=100,
                   help="Annual vs monthly-sum diff below this is ignored (default 100)")
    p.add_argument("--skip-classify", action="store_true",
                   help="Don't re-run the classify_all_state_maker_fuel_month.py step")
    args = p.parse_args()

    json_path = args.data_dir / "all_state_maker_fuel_month.json"
    csv_path = args.data_dir / "all_state_maker_fuel_month_long.csv"

    # 1. Build the audit list (or use the provided targets)
    if args.targets:
        targets = [parse_target(t) for t in args.targets]
        print(f"Manual targets: {len(targets)}")
    else:
        targets = audit(args.v7_html, json_path, tolerance=args.tolerance)
        print(f"Audited gaps: {len(targets)}")

    if not targets:
        print("Nothing to do. Scrape is consistent with v7 annual totals.")
        return

    # Print the audit findings
    print(f"\n{'maker':<40} {'year':>5} {'month':>9}")
    print("-" * 60)
    for maker, yr, mon in targets:
        print(f"{maker[:40]:<40} {yr:>5} {mon:>9}")

    if args.dry_run:
        print("\n--dry-run: not scraping.")
        return

    # 2. Group targets by year for efficient Selenium walks
    by_year: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for maker, yr, mon in targets:
        mn = int(mon.split("-")[1])
        by_year[str(yr)][mn].add(maker)
    print(f"\nScraping {sum(len(months) for months in by_year.values())} "
          f"(year, month) selectors total ...")

    # 3. Re-scrape each year × month
    all_new: list[dict] = []
    for year in sorted(by_year):
        months_map = by_year[year]
        months = sorted(months_map.keys())
        wanted = set().union(*months_map.values())
        print(f"\nYear {year} · months {months} · wanted makers: {sorted(wanted)}")
        new_rows = rescrape_year_months_with_retries(year, months, wanted,
                                                     args.data_dir, args.delay,
                                                     args.headful, args.max_pages)
        all_new.extend(new_rows)

    if not all_new:
        print("\nNo rows scraped. Aborting.")
        return

    # 4. Merge into the payload
    print(f"\nMerging {len(all_new)} new rows into {json_path} ...")
    merge_into_payload(json_path, all_new)

    # 5. Re-flatten the long CSV
    payload = read_monthly_scrape(json_path)
    n_rows = write_long_csv(payload, csv_path)
    print(f"Wrote {n_rows} long rows to {csv_path}")

    # 6. Re-run classifier
    if not args.skip_classify:
        import subprocess
        print("\nRe-running classify_all_state_maker_fuel_month.py ...")
        try:
            subprocess.run(
                [sys.executable, str(Path(__file__).parent / "classify_all_state_maker_fuel_month.py")],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"  classifier returned {e.returncode}")

    # 7. Re-audit to verify the gap closed
    print("\nVerification pass:")
    remaining = audit(args.v7_html, json_path, tolerance=args.tolerance)
    if not remaining:
        print("  ✓ All audited gaps closed.")
    else:
        print(f"  ⚠ {len(remaining)} gaps remain:")
        for maker, yr, mon in remaining:
            print(f"    {maker} {yr}-{mon}")

    print("\nDone. Next step: rebuild the v8 payload by running the build "
          "scripts in your agent scratch directory, or just re-run the "
          "dashboard rebuild path.")


if __name__ == "__main__":
    main()
