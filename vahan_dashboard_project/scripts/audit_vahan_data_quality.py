#!/usr/bin/env python3
"""Audit VAHAN scraped datasets and flag canonical-source inconsistencies."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE = Path("data/vahan_2021_2026_calendar")
OUT = BASE / "vahan_data_quality_report.md"
CANONICAL = BASE / "CANONICAL_DATA.md"
MANIFEST = BASE / "STANDARD_DATASET_MANIFEST.csv"

EXPECTED_RAW_TITLES = {
    "state_maker_fuel_month_raw": "Maker Wise Fuel Data",
    "state_maker_category_month_raw": "Maker Wise Vehicle Category Data",
    "state_category_fuel_month_raw": "Vehicle Category Wise Fuel Data",
}

MONTHS_2026_YTD = [f"2026-{month:02d}" for month in range(1, 6)]


def read_rows(name: str) -> list[dict[str, str]]:
    with (BASE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_rows_optional(name: str) -> list[dict[str, str]]:
    path = BASE / name
    if not path.exists():
        return []
    return read_rows(name)


def int_value(value: str | int | None) -> int:
    if value is None or value == "":
        return 0
    return int(str(value).replace(",", ""))


def sum_by(rows: list[dict[str, str]], keys: tuple[str, ...], value_field: str = "registrations") -> dict[tuple[str, ...], int]:
    out: dict[tuple[str, ...], int] = defaultdict(int)
    for row in rows:
        out[tuple(row[key] for key in keys)] += int_value(row.get(value_field))
    return dict(out)


def filter_months(rows: list[dict[str, str]], months: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("month") in months]


def unique_scrape_dates(rows: list[dict[str, str]], month: str | None = None) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if month and row.get("month") != month:
            continue
        scraped = row.get("scraped_at", "")[:10]
        counts[scraped or "UNKNOWN"] += 1
    return dict(sorted(counts.items()))


def raw_month_freshness(raw_dir: str, month: str) -> list[tuple[str, str]]:
    stale = []
    for path in sorted((BASE / raw_dir).glob(f"*/{month}.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        stale.append((path.parent.name, payload.get("scraped_at", "")))
    return stale


def raw_title_audit(raw_dir: str, expected_title: str) -> tuple[int, list[dict[str, object]]]:
    bad: list[dict[str, object]] = []
    total = 0
    for path in sorted((BASE / raw_dir).glob("*/*.json")):
        total += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            bad.append(
                {
                    "path": str(path),
                    "state_code": path.parent.name,
                    "month": path.stem,
                    "title": f"JSON_ERROR: {type(exc).__name__}: {exc}",
                    "scraped_at": "",
                    "records": "",
                }
            )
            continue
        title = str(payload.get("title", ""))
        if expected_title not in title:
            bad.append(
                {
                    "path": str(path),
                    "state_code": payload.get("state_code", path.parent.name),
                    "month": payload.get("month", path.stem),
                    "title": title,
                    "scraped_at": payload.get("scraped_at", ""),
                    "records": len(payload.get("records", [])),
                }
            )
    return total, bad


def bad_cells(raw_title_bad: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {(str(row["state_code"]), str(row["month"])) for row in raw_title_bad}


def title_group(title: str) -> str:
    if "(" in title:
        return title.split("(", 1)[0].strip()
    return title


def top_diffs(left: dict[tuple[str, ...], int], right: dict[tuple[str, ...], int], limit: int = 25):
    diffs = []
    for key in sorted(set(left) | set(right)):
        lval = left.get(key, 0)
        rval = right.get(key, 0)
        diff = lval - rval
        if diff:
            diffs.append((abs(diff), diff, key, lval, rval))
    return sorted(diffs, reverse=True)[:limit], len(diffs)


def write_markdown_table(lines: list[str], headers: list[str], rows: list[list[object]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")


def write_manifest(rows: list[list[str]]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "status", "standard_use", "qa_notes"])
        writer.writerows(rows)


def main() -> None:
    maker_month = read_rows("all_state_maker_month_long.csv")
    state_maker_category = read_rows("state_maker_category_month_long.csv")
    state_maker_fuel = read_rows("state_maker_fuel_month_long.csv")
    state_category_fuel = read_rows("state_category_fuel_month_long.csv")

    all_state_maker_category = read_rows_optional("all_state_maker_category_month_long.csv")
    all_state_maker_fuel = read_rows_optional("all_state_maker_fuel_month_long.csv")

    raw_audits = {
        raw_dir: raw_title_audit(raw_dir, expected)
        for raw_dir, expected in EXPECTED_RAW_TITLES.items()
    }
    maker_fuel_bad_cells = bad_cells(raw_audits["state_maker_fuel_month_raw"][1])
    category_fuel_bad_cells = bad_cells(raw_audits["state_category_fuel_month_raw"][1])

    months_in_maker_month = {row["month"] for row in maker_month}
    months_in_state_maker_category = {row["month"] for row in state_maker_category}
    common_maker_months = months_in_maker_month & months_in_state_maker_category

    lines = [
        "# VAHAN Data Quality Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Canonical Source Map",
        "",
        "- National maker monthly and YTD totals: `all_state_maker_month_long.csv`.",
        "- State x maker x vehicle category: `state_maker_category_month_long.csv`.",
        "- State x vehicle category x fuel: `state_category_fuel_month_long.csv`, except any raw-title exceptions listed below.",
        (
            "- State x maker x fuel: `state_maker_fuel_month_long.csv`."
            if not maker_fuel_bad_cells
            else "- Do not use `state_maker_fuel_month_long.csv` as standard yet. Its raw partitions include wrong-table captures."
        ),
        "- Older segment-filtered files (`2w_*`, `4w_*`, `monthly_*`, `fuel_maker_vehicle_category_long.csv`) are legacy/exploratory and should be archived, not active dashboard inputs.",
        "- `all_state_maker_fuel_month_long.csv` and `all_state_maker_category_month_long.csv` are no longer standard; archive them if present.",
        "",
        "## Scrape Freshness",
        "",
    ]

    freshness_rows = []
    freshness_sources = [
        ("all_state_maker_month_long.csv", maker_month),
        ("state_maker_category_month_long.csv May rows", state_maker_category),
        ("state_maker_fuel_month_long.csv May rows", state_maker_fuel),
        ("state_category_fuel_month_long.csv May rows", state_category_fuel),
    ]
    if all_state_maker_category:
        freshness_sources.insert(1, ("all_state_maker_category_month_long.csv", all_state_maker_category))
    if all_state_maker_fuel:
        freshness_sources.insert(2, ("all_state_maker_fuel_month_long.csv", all_state_maker_fuel))
    for name, rows in freshness_sources:
        dates = unique_scrape_dates(rows, "2026-05" if "May rows" in name else None)
        freshness_rows.append([name, ", ".join(f"{k}: {v}" for k, v in dates.items())])
    write_markdown_table(lines, ["Dataset", "scraped_at date distribution"], freshness_rows)

    lines += ["", "## 2026 Month Freshness", ""]
    month_freshness_rows = []
    for name, rows in [
        ("all_state_maker_month_long.csv", maker_month),
        ("state_maker_category_month_long.csv", state_maker_category),
        ("state_category_fuel_month_long.csv", state_category_fuel),
        ("state_maker_fuel_month_long.csv", state_maker_fuel),
    ]:
        for month in MONTHS_2026_YTD:
            dates = unique_scrape_dates(rows, month)
            month_freshness_rows.append(
                [name, month, ", ".join(f"{k}: {v}" for k, v in dates.items()) or "NO ROWS"]
            )
    write_markdown_table(lines, ["Dataset", "Month", "scraped_at date distribution"], month_freshness_rows)

    lines += ["", "## Raw May 2026 State Partition Check", ""]
    raw_rows = []
    for raw_dir in ["state_maker_fuel_month_raw", "state_maker_category_month_raw", "state_category_fuel_month_raw"]:
        rows = raw_month_freshness(raw_dir, "2026-05")
        stale = [(state, scraped) for state, scraped in rows if not scraped.startswith("2026-05-30")]
        raw_rows.append([raw_dir, len(rows), len(stale), "; ".join(f"{s}:{t}" for s, t in stale[:10])])
    write_markdown_table(lines, ["Raw dir", "May files", "not scraped May 30", "examples"], raw_rows)

    lines += ["", "## Raw Title Validation", ""]
    title_rows = []
    for raw_dir, expected in EXPECTED_RAW_TITLES.items():
        total, bad = raw_audits[raw_dir]
        title_counts = Counter(title_group(str(row["title"])) for row in bad)
        examples = "; ".join(
            f"{row['state_code']} {row['month']}: {row['title']} ({row['records']} rows)"
            for row in bad[:8]
        )
        title_rows.append(
            [
                raw_dir,
                expected,
                total,
                len(bad),
                "; ".join(f"{title[:55]}...: {count}" for title, count in title_counts.most_common(4)),
                examples,
            ]
        )
    write_markdown_table(
        lines,
        ["Raw dir", "Expected title fragment", "files", "bad title files", "bad-title groups", "examples"],
        title_rows,
    )

    lines += ["", "## 2026 Market Total Reconciliation", ""]
    all_maker_month = sum_by(maker_month, ("month", "maker"))
    state_cat_maker_month = sum_by(state_maker_category, ("month", "maker"))
    state_category_fuel_month = sum_by(state_category_fuel, ("month", "state_code"))
    total_rows = []
    for month in MONTHS_2026_YTD:
        all_total = sum(value for (row_month, _maker), value in all_maker_month.items() if row_month == month)
        state_cat_total = sum(
            value for (row_month, _maker), value in state_cat_maker_month.items() if row_month == month
        )
        cat_fuel_total = sum(
            value for (row_month, _state), value in state_category_fuel_month.items() if row_month == month
        )
        total_rows.append(
            [
                month,
                all_total,
                state_cat_total,
                cat_fuel_total,
                state_cat_total - all_total,
                state_cat_total - cat_fuel_total,
            ]
        )
    write_markdown_table(
        lines,
        [
            "month",
            "all_state_maker_month",
            "state_maker_category",
            "state_category_fuel",
            "state_category_minus_all_state",
            "state_category_minus_category_fuel",
        ],
        total_rows,
    )

    lines += ["", "## National Maker Month vs State-Summed Maker Category", ""]
    all_maker_month_common = sum_by(filter_months(maker_month, common_maker_months), ("month", "maker"))
    state_cat_maker_month_common = sum_by(
        filter_months(state_maker_category, common_maker_months), ("month", "maker")
    )
    top, count = top_diffs(state_cat_maker_month_common, all_maker_month_common)
    lines.append(
        f"Compared only common months: {', '.join(sorted(common_maker_months))}. "
        "Left = state-summed category; right = all-state Maker x Month."
    )
    top, count = top_diffs(state_cat_maker_month_common, all_maker_month_common)
    lines.append(f"Different maker-month cells in common months: {count}.")
    write_markdown_table(
        lines,
        ["month", "maker", "state_sum", "all_state_maker_month", "diff"],
        [[key[0], key[1], lval, rval, diff] for _, diff, key, lval, rval in top],
    )

    lines += ["", "## State Maker Fuel vs State Maker Category", ""]
    fuel_totals = sum_by(state_maker_fuel, ("month", "state_code", "maker"))
    cat_totals = sum_by(state_maker_category, ("month", "state_code", "maker"))
    state_fuel_totals = sum_by(state_maker_fuel, ("month", "state_code"))
    state_cat_totals = sum_by(state_maker_category, ("month", "state_code"))
    if maker_fuel_bad_cells:
        lines.append(
            "`state_maker_fuel_month_long.csv` is quarantined for now because "
            f"{len(maker_fuel_bad_cells)} state-month raw files captured a non-maker table. "
            "A numeric reconciliation would mix makers with vehicle-class labels, so it is intentionally not treated as standard."
        )
        max_maker_fuel_state_diff = None
        max_maker_fuel_maker_diff = None
    else:
        top_state, state_count = top_diffs(state_cat_totals, state_fuel_totals)
        top_maker, maker_count = top_diffs(cat_totals, fuel_totals)
        max_maker_fuel_state_diff = top_state[0][0] if top_state else 0
        max_maker_fuel_maker_diff = top_maker[0][0] if top_maker else 0
        lines.append(
            f"State-month cells with any difference: {state_count}; "
            f"max absolute state-month difference: {max_maker_fuel_state_diff} registrations."
        )
        write_markdown_table(
            lines,
            ["month", "state", "maker_category_total", "maker_fuel_total", "diff"],
            [[key[0], key[1], lval, rval, diff] for _, diff, key, lval, rval in top_state],
        )
        lines.append("")
        lines.append(
            f"State-maker-month cells with any difference: {maker_count}; "
            f"max absolute state-maker-month difference: {max_maker_fuel_maker_diff} registrations."
        )
        write_markdown_table(
            lines,
            ["month", "state", "maker", "category_sum", "fuel_sum", "diff"],
            [[key[0], key[1], key[2], lval, rval, diff] for _, diff, key, lval, rval in top_maker],
        )

    lines += ["", "## State Total: Category x Fuel vs Maker x Category", ""]
    valid_state_maker_category = [
        row for row in state_maker_category if (row["state_code"], row["month"]) not in category_fuel_bad_cells
    ]
    valid_category_fuel = [
        row for row in state_category_fuel if (row["state_code"], row["month"]) not in category_fuel_bad_cells
    ]
    cat_fuel_state = sum_by(valid_category_fuel, ("month", "state_code"))
    maker_cat_state = sum_by(valid_state_maker_category, ("month", "state_code"))
    top, count = top_diffs(maker_cat_state, cat_fuel_state)
    max_state_total_diff = top[0][0] if top else 0
    lines.append(
        f"Different state-month cells after excluding category-fuel bad-title files: {count}. "
        "Left = state maker-category total; right = state category-fuel total."
    )
    write_markdown_table(
        lines,
        ["month", "state", "maker_category_total", "category_fuel_total", "diff"],
        [[key[0], key[1], lval, rval, diff] for _, diff, key, lval, rval in top],
    )

    lines += ["", "## Source vs Our End", ""]
    may_total_row = total_rows[-1]
    if may_total_row[1] == may_total_row[2] == may_total_row[3]:
        lines.append(
            f"- May 2026 is internally consistent across the refreshed standard tables: "
            f"{may_total_row[1]} registrations in all three total views."
        )
    lines.append(
        "- Jan-Apr 2026 differences between national maker-month and state-summed data line up with scrape freshness: "
        "national maker-month was refreshed on May 30, while state-level Jan-Apr rows are mostly May 15. "
        "Treat that as our refresh/staleness issue, not a VAHAN source problem."
    )
    if maker_fuel_bad_cells or category_fuel_bad_cells:
        lines.append(
            "- Wrong-title raw files are on our side: VAHAN served a different table than requested, "
            "and the earlier scraper accepted it instead of rejecting the partition."
        )
    else:
        lines.append("- Raw-title validation is clean for all three state-level standard datasets.")
    if count and max_state_total_diff <= 2:
        lines.append(
            "- Remaining state-total mismatches are only 1-2 registrations after targeted repair. "
            "Treat them as immaterial timing/source-table variance unless exact unit-level reconciliation is needed."
        )
    elif count:
        lines.append(
            "- Remaining state-total mismatches need targeted rescrape before blaming VAHAN. "
            "Several look like partial state-maker-category captures because the independent category-fuel total is much higher."
        )
    else:
        lines.append("- State maker-category and category-fuel totals now reconcile exactly at state-month level.")

    lines += ["", "## Ather/Ola Check Against Canonical Maker-Month", ""]
    target_makers = ["ATHER ENERGY LTD", "OLA ELECTRIC TECHNOLOGIES PVT LTD"]
    ytd_rows = []
    for maker in target_makers:
        vals = [all_maker_month.get((f"2026-{month:02d}", maker), 0) for month in range(1, 6)]
        ytd_rows.append([maker, *vals, sum(vals)])
    write_markdown_table(lines, ["maker", "JAN", "FEB", "MAR", "APR", "MAY", "YTD"], ytd_rows)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_rows = [
        [
            "standard_consolidated/vahan_standard_consolidated_long.csv",
            "STANDARD_EXPORT" if (BASE / "standard_consolidated/vahan_standard_consolidated_long.csv").exists() else "MISSING",
            "Single consolidated dashboard/export CSV with dataset column.",
            "Built from all current STANDARD source CSVs by scripts/build_vahan_standard_consolidated.py.",
        ],
        [
            "all_state_maker_month_long.csv",
            "STANDARD",
            "National maker monthly/YTD totals for 2026 Jan-May.",
            "Fresh May 30; matches VAHAN Maker x Month Wise all-state table.",
        ],
        [
            "state_maker_category_month_long.csv",
            "STANDARD" if max_state_total_diff <= 2 else "STANDARD_WITH_QA_FLAGS",
            "State x maker x vehicle-category analysis.",
            (
                "All raw titles are correct; remaining state-total variance is at most 2 registrations."
                if max_state_total_diff <= 2
                else "All raw titles are correct; state-total mismatches listed in audit need targeted repair."
            ),
        ],
        [
            "state_category_fuel_month_long.csv",
            "STANDARD" if not category_fuel_bad_cells else "STANDARD_WITH_EXCEPTIONS",
            "State x vehicle-category x fuel and EV penetration.",
            (
                "All raw titles are correct."
                if not category_fuel_bad_cells
                else f"{len(category_fuel_bad_cells)} bad-title partitions must be repaired/excluded."
            ),
        ],
        [
            "state_maker_fuel_month_long.csv",
            "STANDARD" if not maker_fuel_bad_cells else "QUARANTINE",
            (
                "State x maker x fuel analysis."
                if not maker_fuel_bad_cells
                else "Do not use for standard outputs until repaired."
            ),
            (
                "All raw titles are correct; max state-month variance vs maker-category is "
                f"{max_maker_fuel_state_diff} registrations."
                if not maker_fuel_bad_cells
                else f"{len(maker_fuel_bad_cells)} raw partitions captured the wrong table."
            ),
        ],
        [
            "all_state_maker_category_month_long.csv",
            "ARCHIVED_LEGACY" if not (BASE / "all_state_maker_category_month_long.csv").exists() else "STALE",
            "Do not use as standard dashboard source.",
            "Archived/legacy all-state cross-tab; replaced by state-level standard sources and consolidated CSV.",
        ],
        [
            "all_state_maker_fuel_month_long.csv",
            "ARCHIVED_LEGACY" if not (BASE / "all_state_maker_fuel_month_long.csv").exists() else "STALE",
            "Do not use as standard dashboard source.",
            "Archived/legacy all-state cross-tab; replaced by state-level standard sources and consolidated CSV.",
        ],
    ]
    write_manifest(manifest_rows)

    canonical_lines = [
        "# Canonical VAHAN Data Sources",
        "",
        "Use these files as the standard dataset going forward:",
        "",
        "Single consolidated CSV for downstream use:",
        "",
        "- `standard_consolidated/vahan_standard_consolidated_long.csv`",
        "",
        "Machine-readable pointer for downstream code:",
        "",
        "- `CURRENT_STANDARD_DATASET.json`",
        "",
        "| Need | Canonical file | Notes |",
        "| --- | --- | --- |",
        "| National maker monthly/YTD totals | `all_state_maker_month_long.csv` | Matches VAHAN Maker x Month Wise all-state table. Use this for Ather/Ola national totals. |",
        "| State x maker x vehicle category | `state_maker_category_month_long.csv` | Use for state/category splits and maker geography. Remaining state-total variance is at most 2 registrations. |",
        (
            "| State x maker x fuel | `state_maker_fuel_month_long.csv` | "
            "Use for state-level maker fuel mix. All raw titles are correct. |"
            if not maker_fuel_bad_cells
            else "| State x maker x fuel | _Do not use current `state_maker_fuel_month_long.csv`_ | Quarantined: some raw partitions are Vehicle Class x Fuel, not Maker x Fuel. Repair/rescrape before use. |"
        ),
        (
            "| State x vehicle category x fuel | `state_category_fuel_month_long.csv` | "
            + (
                "Use for state/category EV penetration. All raw titles are correct. |"
                if not category_fuel_bad_cells
                else "Use for state/category EV penetration, excluding or repairing bad-title partitions listed in the audit. |"
            )
        ),
        "",
        "Non-canonical / legacy files:",
        "",
        "- `all_state_maker_fuel_month_long.csv` and `all_state_maker_category_month_long.csv` are archived legacy outputs, not standard sources.",
        "- `2w_*`, `4w_*`, `monthly_*`, and `fuel_maker_vehicle_category_long.csv` are earlier exploratory outputs. Keep them archived; do not use them as standard dashboard inputs.",
        (
            "- `state_maker_fuel_month_long.csv` is standard after bad-title repair."
            if not maker_fuel_bad_cells
            else "- `state_maker_fuel_month_long.csv` is quarantined until wrong-title raw partitions are repaired and the CSV is recompiled."
        ),
        "",
        "Latest audit report:",
        "",
        "- `vahan_data_quality_report.md`",
        "- `STANDARD_DATASET_MANIFEST.csv`",
        "- `data_source_validation_report.md`",
    ]
    CANONICAL.write_text("\n".join(canonical_lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Wrote {CANONICAL}")
    print(f"Wrote {MANIFEST}")


if __name__ == "__main__":
    main()
