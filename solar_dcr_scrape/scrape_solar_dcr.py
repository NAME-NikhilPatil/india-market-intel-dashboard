#!/usr/bin/env python3
"""Scrape public Solar DCR dashboard totals and solar cell summary data."""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://solardcrportal.nise.res.in"
INDEX_URL = f"{BASE_URL}/Summary/index"
MONTH_ORDER = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": INDEX_URL,
            "Origin": BASE_URL,
        }
    )
    return session


def fetch_index(session: requests.Session) -> str:
    response = session.get(INDEX_URL, timeout=60)
    response.raise_for_status()
    return response.text


def post_summary(session: requests.Session, endpoint: str, payload: dict[str, str]) -> str:
    response = session.post(
        f"{BASE_URL}{endpoint}",
        data={**payload, "RecaptchaToken": ""},
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def post_form(session: requests.Session, endpoint: str, payload: list[tuple[str, str]]) -> str:
    response = session.post(
        f"{BASE_URL}{endpoint}",
        data=payload,
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=120,
    )
    response.raise_for_status()
    return response.text


def parse_number(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text))


def scrape_dashboard_totals(index_html: str, scraped_at: str) -> pd.DataFrame:
    soup = BeautifulSoup(index_html, "html.parser")
    labels = {
        "Solar Cell Manufacturer": "solar_cell_manufacturers",
        "Solar Module Manufacturer": "solar_module_manufacturers",
        "Solar Cell & Solar Module Stock": "solar_cell_module_stock",
        "DCR Generated": "dcr_generated",
    }

    rows = []
    for label, metric in labels.items():
        label_node = soup.find(string=lambda value: value and value.strip() == label)
        if not label_node:
            continue
        container = label_node.find_parent("div")
        value_node = container.find("h3") if container else None
        if not value_node:
            continue
        rows.append(
            {
                "metric": metric,
                "label": label,
                "value": parse_number(value_node.get_text(" ", strip=True)),
                "scraped_at": scraped_at,
                "source_url": INDEX_URL,
            }
        )

    if len(rows) != len(labels):
        missing = sorted(set(labels.values()) - {row["metric"] for row in rows})
        raise RuntimeError(f"Could not parse dashboard totals: missing {missing}")

    return pd.DataFrame(rows)


def extract_arraystore_data(html: str) -> list[dict]:
    marker = '"data":['
    start = html.find(marker)
    if start == -1:
        raise RuntimeError("Could not find DevExtreme ArrayStore data in response")

    array_start = html.find("[", start)
    depth = 0
    in_string = False
    escaped = False

    for pos in range(array_start, len(html)):
        char = html[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                data_text = html[array_start : pos + 1]
                data_text = re.sub(r"new Date\([^)]*\)", "null", data_text)
                return json.loads(data_text)

    raise RuntimeError("ArrayStore data was unterminated")


def scrape_cell_company_year(
    session: requests.Session, year: int, scraped_at: str
) -> pd.DataFrame:
    html = post_summary(session, "/Summary/CellChart", {f"Year1[]": str(year)})
    rows = []
    for item in extract_arraystore_data(html):
        rows.append(
            {
                "year": year,
                "rank": item.get("xValue"),
                "agency_id": item.get("AgencyId"),
                "company_name": item.get("tagValue"),
                "cell_manufactured_mw": item.get("yValue"),
                "series": item.get("SeriesText"),
                "is_almm": item.get("isAlmm"),
                "scraped_at": scraped_at,
            }
        )
    return pd.DataFrame(rows)


def scrape_module_company_year(
    session: requests.Session, year: int, scraped_at: str
) -> pd.DataFrame:
    html = post_summary(session, "/Summary/PnlChart", {f"Year1[]": str(year)})
    rows = []
    for item in extract_arraystore_data(html):
        rows.append(
            {
                "year": year,
                "rank": item.get("xValue"),
                "agency_id": item.get("AgencyId"),
                "company_name": item.get("tagValue"),
                "module_manufactured_mw": item.get("yValue"),
                "series": item.get("SeriesText"),
                "is_almm": item.get("isAlmm"),
                "scraped_at": scraped_at,
            }
        )
    return pd.DataFrame(rows)


def monthly_rows(
    html: str,
    year: int,
    agency_id: str | None,
    company_name: str | None,
    metric: str,
    scraped_at: str,
) -> list[dict]:
    rows = []
    for item in extract_arraystore_data(html):
        month_name = item.get("xValue")
        rows.append(
            {
                "year": year,
                "month": MONTH_ORDER.get(month_name),
                "month_name": month_name,
                "agency_id": agency_id,
                "company_name": company_name,
                "metric": metric,
                "value_mw": item.get("yValue"),
                "scraped_at": scraped_at,
            }
        )
    return rows


def scrape_cell_monthly(
    session: requests.Session,
    year: int,
    agency_id: str | None,
    company_name: str | None,
    scraped_at: str,
) -> list[dict]:
    payload = {"Year1[]": str(year), "MfgId": agency_id or ""}
    manufactured_html = post_summary(session, "/Summary/WaferToCell", payload)
    time.sleep(0.2)
    sold_html = post_summary(session, "/Summary/DCRInvChart", payload)
    return [
        *monthly_rows(
            manufactured_html,
            year,
            agency_id,
            company_name,
            "cell_manufactured_mw",
            scraped_at,
        ),
        *monthly_rows(
            sold_html,
            year,
            agency_id,
            company_name,
            "cell_sold_mw",
            scraped_at,
        ),
    ]


def scrape_module_monthly(
    session: requests.Session,
    year: int,
    agency_id: str | None,
    company_name: str | None,
    scraped_at: str,
) -> list[dict]:
    payload = {"Year1[]": str(year), "MfgId": agency_id or ""}
    manufactured_html = post_summary(session, "/Summary/PnlMfgChart", payload)
    time.sleep(0.2)
    sold_html = post_summary(session, "/Summary/PnlInvChart", payload)
    return [
        *monthly_rows(
            manufactured_html,
            year,
            agency_id,
            company_name,
            "module_manufactured_mw",
            scraped_at,
        ),
        *monthly_rows(
            sold_html,
            year,
            agency_id,
            company_name,
            "module_sold_mw",
            scraped_at,
        ),
    ]


def scrape_stock_summary(session: requests.Session, scraped_at: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    html = post_form(
        session,
        "/Summary/AgencyListTbl",
        [
            ("CompType[]", "Manufacturer"),
            ("CompType[]", "Reseller"),
            ("RecaptchaToken", ""),
        ],
    )
    raw_rows = extract_arraystore_data(html)
    keep_columns = {
        "State": "state",
        "TotalUser": "total_users",
        "CellDCR": "cell_with_manufacturer_mw",
        "CellDCRQty": "cell_with_reseller_mw",
        "ModuleDCR": "module_with_manufacturer_mw",
        "ModuleDCRQty": "module_with_reseller_mw",
        "CellDCR1": "cell_unclaimed_with_manufacturer_mw",
        "CellDCR1Qty": "cell_unclaimed_with_reseller_mw",
        "ModuleDCR1": "module_unclaimed_with_manufacturer_mw",
        "ModuleDCR1Qty": "module_unclaimed_with_reseller_mw",
    }

    state_rows = []
    for item in raw_rows:
        row = {new: item.get(old) for old, new in keep_columns.items()}
        row["scraped_at"] = scraped_at
        state_rows.append(row)
    state_df = pd.DataFrame(state_rows)

    total_metrics = [
        "cell_with_manufacturer_mw",
        "cell_with_reseller_mw",
        "module_with_manufacturer_mw",
        "module_with_reseller_mw",
        "cell_unclaimed_with_manufacturer_mw",
        "cell_unclaimed_with_reseller_mw",
        "module_unclaimed_with_manufacturer_mw",
        "module_unclaimed_with_reseller_mw",
    ]
    totals_df = pd.DataFrame(
        [
            {
                "metric": metric,
                "value_mw": state_df[metric].sum(),
                "scraped_at": scraped_at,
                "source_endpoint": "/Summary/AgencyListTbl",
            }
            for metric in total_metrics
        ]
    )
    return state_df, totals_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--output-dir", default="data/solar_dcr")
    parser.add_argument(
        "--company-monthly",
        action="store_true",
        help="Also scrape monthly cell manufactured/sold data for each company.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scraped_at = datetime.now().isoformat(timespec="seconds")

    session = make_session()
    index_html = fetch_index(session)

    totals = scrape_dashboard_totals(index_html, scraped_at)
    totals.to_csv(output_dir / "dashboard_totals.csv", index=False)

    print("Scraping stock summary...")
    stock_state, stock_totals = scrape_stock_summary(session, scraped_at)
    stock_state.to_csv(output_dir / "stock_summary_by_state.csv", index=False)
    stock_totals.to_csv(output_dir / "stock_summary_totals.csv", index=False)

    company_year_frames = []
    monthly_rows_all = []
    module_company_year_frames = []
    module_monthly_rows_all = []

    for year in range(args.start_year, args.end_year + 1):
        print(f"Scraping solar cell summary for {year}...")
        company_year = scrape_cell_company_year(session, year, scraped_at)
        company_year_frames.append(company_year)

        monthly_rows_all.extend(
            scrape_cell_monthly(session, year, None, "All Manufacturers", scraped_at)
        )
        time.sleep(0.4)

        if args.company_monthly:
            for row in company_year.to_dict("records"):
                agency_id = row["agency_id"]
                company_name = row["company_name"]
                if not agency_id:
                    continue
                monthly_rows_all.extend(
                    scrape_cell_monthly(
                        session, year, agency_id, company_name, scraped_at
                    )
                )
                time.sleep(0.4)

        print(f"Scraping solar module summary for {year}...")
        module_company_year = scrape_module_company_year(session, year, scraped_at)
        module_company_year_frames.append(module_company_year)

        module_monthly_rows_all.extend(
            scrape_module_monthly(
                session, year, None, "All Manufacturers", scraped_at
            )
        )
        time.sleep(0.4)

        if args.company_monthly:
            for row in module_company_year.to_dict("records"):
                agency_id = row["agency_id"]
                company_name = row["company_name"]
                if not agency_id:
                    continue
                module_monthly_rows_all.extend(
                    scrape_module_monthly(
                        session, year, agency_id, company_name, scraped_at
                    )
                )
                time.sleep(0.4)

    cell_company_year = pd.concat(company_year_frames, ignore_index=True)
    cell_company_year.to_csv(
        output_dir / "cell_company_yearly_manufactured_mw.csv", index=False
    )

    cell_monthly = pd.DataFrame(monthly_rows_all)
    cell_monthly.to_csv(output_dir / "cell_monthly_manufactured_sold_mw.csv", index=False)

    module_company_year = pd.concat(module_company_year_frames, ignore_index=True)
    module_company_year.to_csv(
        output_dir / "module_company_yearly_manufactured_mw.csv", index=False
    )

    module_monthly = pd.DataFrame(module_monthly_rows_all)
    module_monthly.to_csv(
        output_dir / "module_monthly_manufactured_sold_mw.csv", index=False
    )

    print(f"Wrote {len(totals)} rows to {output_dir / 'dashboard_totals.csv'}")
    print(
        "Wrote "
        f"{len(stock_state)} rows to {output_dir / 'stock_summary_by_state.csv'}"
    )
    print(
        "Wrote "
        f"{len(stock_totals)} rows to {output_dir / 'stock_summary_totals.csv'}"
    )
    print(
        "Wrote "
        f"{len(cell_company_year)} rows to "
        f"{output_dir / 'cell_company_yearly_manufactured_mw.csv'}"
    )
    print(
        "Wrote "
        f"{len(cell_monthly)} rows to "
        f"{output_dir / 'cell_monthly_manufactured_sold_mw.csv'}"
    )
    print(
        "Wrote "
        f"{len(module_company_year)} rows to "
        f"{output_dir / 'module_company_yearly_manufactured_mw.csv'}"
    )
    print(
        "Wrote "
        f"{len(module_monthly)} rows to "
        f"{output_dir / 'module_monthly_manufactured_sold_mw.csv'}"
    )


if __name__ == "__main__":
    main()
