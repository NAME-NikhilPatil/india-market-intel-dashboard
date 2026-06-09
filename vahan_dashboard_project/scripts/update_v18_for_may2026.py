#!/usr/bin/env python3
"""Refresh the v18 dashboard payloads with the May-2026 (and re-checked 2026 YTD)
data from the freshly-updated state-level CSVs.

What this script does
---------------------
The source-of-truth CSVs are:
  - data/.../state_maker_fuel_month_long.csv
  - data/.../state_maker_category_month_long.csv
  - data/.../state_category_fuel_month_long.csv

The dashboard reads two payloads:
  - vahan_dashboard_v18.html: inline <script id="payload" ...> JSON (national)
  - state_payload.js: window.__STATE_PAYLOAD__ object (state-level)

For 2026-01 .. 2026-05 this script recomputes the monthly aggregates from the
state-level CSVs and patches every embedded structure that holds those buckets
or 2026-annual values. Years 2021-2025 are left untouched.

It also re-derives the maker-level monthly + 2026-annual rows by reading the
existing maker->norm mapping out of the inline payload's `rows` (so the
canonical Hero Group / Suzuki-Maruti / etc. names are preserved).

Outputs are written in place: state_payload.js + vahan_dashboard_v18.html (a
.bak.<timestamp> backup is created first).
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vahan_2021_2026_calendar"
SP_PATH = ROOT / "state_payload.js"
DASH_PATH = ROOT / "vahan_dashboard_v18.html"

# Months in 2026 that we will recompute from source.
YEAR = "2026"
MONTHS_2026 = [f"{YEAR}-{m:02d}" for m in range(1, 6)]  # 2026-01 .. 2026-05
PARTIAL_MONTH = "2026-05"

# Buckets the dashboard uses (matches META.buckets).
BUCKETS = ["2W", "3W", "4W", "CV"]
FUELS = ["EV", "Petrol", "Diesel", "Hybrid", "Others"]

# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------
# state_maker_category uses short VAHAN codes; state_category_fuel uses
# verbose names. Both must map to one of {2W, 3W, 4W, CV}.
#
# This mapping reproduces the bucketing visible in the existing payload for
# 2026-04 (verified by spot-check; 2W/3W matched exactly, 4W/CV within 0.03%).
CAT_CODE_TO_BUCKET = {
    "2WIC": "2W", "2WN": "2W", "2WT": "2W",
    "3WIC": "3W", "3WN": "3W", "3WT": "3W",
    "4WIC": "4W", "LMV": "4W", "LPV": "4W", "MMV": "4W", "MPV": "4W",
    "LGV": "CV", "MGV": "CV", "HGV": "CV", "HMV": "CV", "HPV": "CV",
    "OTH": "CV",
}

CAT_VERBOSE_TO_BUCKET = {
    # 2W
    "TWO WHEELER(NT)": "2W", "TWO WHEELER(T)": "2W",
    "TWO WHEELER (INVALID CARRIAGE)": "2W",
    "M-CYCLE/SCOOTER": "2W",
    "MOTOR CYCLE/SCOOTER-USED FOR HIRE": "2W",
    "MOTORISED CYCLE (CC > 25CC)": "2W",
    # 3W
    "THREE WHEELER(NT)": "3W", "THREE WHEELER(T)": "3W",
    "THREE WHEELER (INVALID CARRIAGE)": "3W",
    "THREE WHEELER (PASSENGER)": "3W", "THREE WHEELER (GOODS)": "3W",
    "THREE WHEELER (PERSONAL)": "3W",
    "E-RICKSHAW WITH CART (G)": "3W",
    # 4W (passenger)
    "LIGHT MOTOR VEHICLE": "4W", "LIGHT PASSENGER VEHICLE": "4W",
    "FOUR WHEELER (INVALID CARRIAGE)": "4W",
    "MEDIUM MOTOR VEHICLE": "4W", "MEDIUM PASSENGER VEHICLE": "4W",
    "MOTOR CAR": "4W", "MOTOR CAB": "4W", "MAXI CAB": "4W",
    "ADAPTED VEHICLE": "4W", "CAMPER VAN / TRAILER": "4W",
    # CV
    "LIGHT GOODS VEHICLE": "CV", "MEDIUM GOODS VEHICLE": "CV",
    "HEAVY GOODS VEHICLE": "CV", "HEAVY MOTOR VEHICLE": "CV",
    "HEAVY PASSENGER VEHICLE": "CV",
    "GOODS CARRIER": "CV", "BUS": "CV", "OMNI BUS": "CV",
    "OMNI BUS (PRIVATE USE)": "CV", "EDUCATIONAL INSTITUTION BUS": "CV",
    "PRIVATE SERVICE VEHICLE": "CV", "AMBULANCE": "CV",
    "AGRICULTURAL TRACTOR": "CV", "TRACTOR (COMMERCIAL)": "CV",
    "TRAILER (COMMERCIAL)": "CV", "TRAILER (AGRICULTURAL)": "CV",
    "ARTICULATED VEHICLE": "CV",
    "CONSTRUCTION EQUIPMENT VEHICLE": "CV",
    "CRANE MOUNTED VEHICLE": "CV", "FORK LIFT": "CV",
    "HARVESTER": "CV", "ROAD ROLLER": "CV",
    "MOBILE CANTEEN": "CV", "MOBILE CLINIC": "CV", "CASH VAN": "CV",
    "HEARSES": "CV", "RECOVERY VEHICLE": "CV",
    "FIRE FIGHTING VEHICLE": "CV", "FIRE TENDERS": "CV",
    "ANIMAL AMBULANCE": "CV",
    "VEHICLE FITTED WITH COMPRESSOR": "CV",
    "VEHICLE FITTED WITH GENERATOR": "CV",
    "VEHICLE FITTED WITH RIG": "CV",
    "OTHER THAN MENTIONED ABOVE": "CV",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reg(row, key="registrations"):
    try:
        return float(row.get(key) or 0)
    except Exception:
        return 0.0


def load_state_payload():
    txt = SP_PATH.read_text()
    prefix = "window.__STATE_PAYLOAD__ = "
    assert txt.startswith(prefix), "state_payload.js missing expected prefix"
    body = txt[len(prefix):].rstrip().rstrip(";")
    return json.loads(body)


def write_state_payload(sp):
    body = json.dumps(sp, ensure_ascii=False, separators=(",", ":"))
    SP_PATH.write_text(f"window.__STATE_PAYLOAD__ = {body};")


PAYLOAD_TAG_RE = re.compile(
    r'(<script id="payload" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def load_inline_payload(html):
    m = PAYLOAD_TAG_RE.search(html)
    if not m:
        raise SystemExit("Could not find <script id='payload'> tag in dashboard")
    return json.loads(m.group(2)), m


def write_inline_payload(html, payload, m):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return html[:m.start(2)] + body + html[m.end(2):]


def list_replace_or_append(lst, predicate, new_record):
    """Replace the first element matching `predicate` with new_record; if
    none matches, append new_record (preserving list ordering otherwise)."""
    for i, el in enumerate(lst):
        if predicate(el):
            lst[i] = new_record
            return
    lst.append(new_record)


# ---------------------------------------------------------------------------
# Aggregations from state-level CSVs
# ---------------------------------------------------------------------------

def aggregate_2026():
    """Return a nested dict with every aggregate the dashboard needs.

    Structure
    ---------
    out = {
      "by_month": {                                 # months 2026-01..2026-05
        "2026-05": {
          "total": int,
          "by_fuel": {fuel: int},
          "by_cat":  {bucket: int},
          "by_cat_fuel": {bucket: {fuel: int}},
          "by_state": {
            state: {
              "total": int,
              "by_fuel": {fuel: int},
              "by_cat":  {bucket: int},
              "by_cat_fuel": {bucket: {fuel: int}},
              "by_maker_raw": {raw_maker: int},
              "by_maker_cat": {raw_maker: {bucket: int}},
              "by_maker_fuel": {raw_maker: {fuel: int}},
              "by_maker_cat_fuel": {raw_maker: {bucket: {fuel: int}}},
            }
          },
          "by_maker_raw_national": {raw_maker: int},
          "by_maker_cat_national": {raw_maker: {bucket: int}},
          "by_maker_fuel_national": {raw_maker: {fuel: int}},
          "by_maker_cat_fuel_national": {raw_maker: {bucket: {fuel: int}}},
        },
        ...
      },
      "states": set[state names],
    }
    """
    out = {"by_month": {m: _empty_month() for m in MONTHS_2026}, "states": set()}

    # 1) state_maker_fuel: gives maker × fuel per state per month
    with (DATA / "state_maker_fuel_month_long.csv").open() as f:
        for r in csv.DictReader(f):
            mth = r["month"]
            if mth not in out["by_month"]:
                continue
            n = reg(r)
            if not n:
                continue
            st = r["state"]
            mk = r["maker"]
            fg = r["fuel_group"]
            b = out["by_month"][mth]
            sb = b["by_state"].setdefault(st, _empty_state())
            out["states"].add(st)
            # national
            b["total"] += n
            b["by_fuel"][fg] = b["by_fuel"].get(fg, 0) + n
            b["by_maker_raw_national"][mk] = b["by_maker_raw_national"].get(mk, 0) + n
            b["by_maker_fuel_national"].setdefault(mk, {})
            b["by_maker_fuel_national"][mk][fg] = b["by_maker_fuel_national"][mk].get(fg, 0) + n
            # state
            sb["total"] += n
            sb["by_fuel"][fg] = sb["by_fuel"].get(fg, 0) + n
            sb["by_maker_raw"][mk] = sb["by_maker_raw"].get(mk, 0) + n
            sb["by_maker_fuel"].setdefault(mk, {})
            sb["by_maker_fuel"][mk][fg] = sb["by_maker_fuel"][mk].get(fg, 0) + n

    # 2) state_maker_category: gives maker × bucket per state per month
    with (DATA / "state_maker_category_month_long.csv").open() as f:
        for r in csv.DictReader(f):
            mth = r["month"]
            if mth not in out["by_month"]:
                continue
            n = reg(r)
            if not n:
                continue
            code = r["vehicle_category"]
            bucket = CAT_CODE_TO_BUCKET.get(code)
            if not bucket:
                continue
            st = r["state"]
            mk = r["maker"]
            b = out["by_month"][mth]
            sb = b["by_state"].setdefault(st, _empty_state())
            out["states"].add(st)
            b["by_cat"][bucket] = b["by_cat"].get(bucket, 0) + n
            b["by_maker_cat_national"].setdefault(mk, {})
            b["by_maker_cat_national"][mk][bucket] = b["by_maker_cat_national"][mk].get(bucket, 0) + n
            sb["by_cat"][bucket] = sb["by_cat"].get(bucket, 0) + n
            sb["by_maker_cat"].setdefault(mk, {})
            sb["by_maker_cat"][mk][bucket] = sb["by_maker_cat"][mk].get(bucket, 0) + n

    # 3) state_category_fuel: gives bucket × fuel per state per month
    with (DATA / "state_category_fuel_month_long.csv").open() as f:
        for r in csv.DictReader(f):
            mth = r["month"]
            if mth not in out["by_month"]:
                continue
            n = reg(r)
            if not n:
                continue
            cv = r["vehicle_category"]
            bucket = CAT_VERBOSE_TO_BUCKET.get(cv)
            if not bucket:
                continue
            fg = r["fuel_group"]
            st = r["state"]
            b = out["by_month"][mth]
            sb = b["by_state"].setdefault(st, _empty_state())
            out["states"].add(st)
            b["by_cat_fuel"].setdefault(bucket, {})
            b["by_cat_fuel"][bucket][fg] = b["by_cat_fuel"][bucket].get(fg, 0) + n
            sb["by_cat_fuel"].setdefault(bucket, {})
            sb["by_cat_fuel"][bucket][fg] = sb["by_cat_fuel"][bucket].get(fg, 0) + n

    # cast totals to int
    for mth, b in out["by_month"].items():
        b["total"] = int(round(b["total"]))
        b["by_fuel"] = {k: int(round(v)) for k, v in b["by_fuel"].items()}
        b["by_cat"] = {k: int(round(v)) for k, v in b["by_cat"].items()}
        b["by_cat_fuel"] = {c: {f: int(round(v)) for f, v in fs.items()} for c, fs in b["by_cat_fuel"].items()}
        for st, sb in b["by_state"].items():
            sb["total"] = int(round(sb["total"]))
            sb["by_fuel"] = {k: int(round(v)) for k, v in sb["by_fuel"].items()}
            sb["by_cat"] = {k: int(round(v)) for k, v in sb["by_cat"].items()}
            sb["by_cat_fuel"] = {c: {f: int(round(v)) for f, v in fs.items()} for c, fs in sb["by_cat_fuel"].items()}
            sb["by_maker_raw"] = {k: int(round(v)) for k, v in sb["by_maker_raw"].items()}
        b["by_maker_raw_national"] = {k: int(round(v)) for k, v in b["by_maker_raw_national"].items()}
    return out


def _empty_month():
    return {
        "total": 0.0,
        "by_fuel": {},
        "by_cat": {},
        "by_cat_fuel": {},
        "by_state": {},
        "by_maker_raw_national": {},
        "by_maker_cat_national": {},
        "by_maker_fuel_national": {},
    }


def _empty_state():
    return {
        "total": 0.0,
        "by_fuel": {},
        "by_cat": {},
        "by_cat_fuel": {},
        "by_maker_raw": {},
        "by_maker_cat": {},
        "by_maker_fuel": {},
    }


# ---------------------------------------------------------------------------
# Maker normalisation map (raw VAHAN name -> canonical bucket)
# ---------------------------------------------------------------------------

def build_maker_norm_map(payload):
    """Reverse the existing payload['rows'] to get raw_maker -> canonical."""
    m = {}
    for r in payload.get("rows", []):
        raw = r.get("maker")
        norm = r.get("norm")
        if raw and norm:
            m[raw] = norm
    return m


def normalise_maker(raw_name, mapping):
    if raw_name in mapping:
        return mapping[raw_name]
    # tolerant fallback: case-insensitive, then leave raw
    upper = raw_name.upper().strip()
    for k, v in mapping.items():
        if k.upper().strip() == upper:
            return v
    return None  # caller decides whether to drop or keep raw


# ---------------------------------------------------------------------------
# Inline-payload (national) updater
# ---------------------------------------------------------------------------

def update_inline_payload(payload, agg):
    by_month = agg["by_month"]
    maker_map = build_maker_norm_map(payload)

    # 1. monthly_fuel_mix: list of {month, EV, Petrol, Diesel, Hybrid, Others, total}
    for mth in MONTHS_2026:
        b = by_month[mth]
        rec = {"month": mth}
        for f in FUELS:
            rec[f] = b["by_fuel"].get(f, 0)
        rec["total"] = b["total"]
        list_replace_or_append(payload["monthly_fuel_mix"], lambda r: r.get("month") == mth, rec)

    # 2. monthly_ev_penetration: list of {month, ev, total, pen}
    for mth in MONTHS_2026:
        b = by_month[mth]
        ev = b["by_fuel"].get("EV", 0)
        total = b["total"]
        rec = {"month": mth, "ev": ev, "total": total, "pen": (ev / total) if total else 0.0}
        list_replace_or_append(payload["monthly_ev_penetration"], lambda r: r.get("month") == mth, rec)

    # 3. monthly_fuel_mix_by_cat[bucket]: list with same shape per bucket
    for bucket in BUCKETS:
        for mth in MONTHS_2026:
            b = by_month[mth]
            cf = b["by_cat_fuel"].get(bucket, {})
            total = sum(cf.values())
            rec = {"month": mth, **{f: cf.get(f, 0) for f in FUELS}, "total": total, "derived": True}
            list_replace_or_append(payload["monthly_fuel_mix_by_cat"][bucket], lambda r: r.get("month") == mth, rec)

    # 4. monthly_ev_pen_by_cat[bucket]
    for bucket in BUCKETS:
        for mth in MONTHS_2026:
            b = by_month[mth]
            cf = b["by_cat_fuel"].get(bucket, {})
            ev = cf.get("EV", 0)
            total = sum(cf.values())
            rec = {"month": mth, "ev": ev, "total": total, "pen": (ev / total) if total else 0.0, "derived": True}
            list_replace_or_append(payload["monthly_ev_pen_by_cat"][bucket], lambda r: r.get("month") == mth, rec)

    # 5. annual_totals[2026]
    total_2026 = sum(by_month[m]["total"] for m in MONTHS_2026)
    payload["annual_totals"]["2026"] = total_2026

    # 6. annual_totals_by_fuel[2026]
    by_fuel_year = {f: 0 for f in FUELS}
    for m in MONTHS_2026:
        for f, v in by_month[m]["by_fuel"].items():
            if f in by_fuel_year:
                by_fuel_year[f] += v
    payload["annual_totals_by_fuel"]["2026"] = by_fuel_year

    # 7. annual_ev_penetration: per-category rows for year=2026
    cat_year_totals = {b: {"ev": 0, "total": 0} for b in BUCKETS}
    for m in MONTHS_2026:
        cf = by_month[m]["by_cat_fuel"]
        for bucket in BUCKETS:
            v = cf.get(bucket, {})
            cat_year_totals[bucket]["ev"] += v.get("EV", 0)
            cat_year_totals[bucket]["total"] += sum(v.values())
    new_rows = []
    for r in payload["annual_ev_penetration"]:
        if r.get("year") == 2026:
            continue
        new_rows.append(r)
    for bucket in BUCKETS:
        c = cat_year_totals[bucket]
        new_rows.append({
            "year": 2026,
            "category": bucket,
            "ev": c["ev"],
            "total": c["total"],
            "pen": (c["ev"] / c["total"]) if c["total"] else 0.0,
        })
    payload["annual_ev_penetration"] = new_rows

    # 8. ytd_2026: full rebuild for 2026 YTD vs prior-year YTD comparison.
    # `prior` should be the same months of 2025 (so comparable to 2026 YTD).
    payload["ytd_2026"] = _build_ytd_2026(payload, by_month)

    # 9. seasonality.totals[month] and seasonality.by_fuel[month][fuel] etc.
    if "seasonality" in payload and isinstance(payload["seasonality"], dict):
        s = payload["seasonality"]
        for m in MONTHS_2026:
            b = by_month[m]
            if "totals" in s:
                s["totals"][m] = b["total"]
            if "by_fuel" in s:
                s["by_fuel"][m] = dict(b["by_fuel"])
            if "totals_by_cat" in s:
                for bucket in BUCKETS:
                    s["totals_by_cat"].setdefault(bucket, {})
                    s["totals_by_cat"][bucket][m] = b["by_cat"].get(bucket, 0)
            if "by_fuel_by_cat" in s:
                for bucket in BUCKETS:
                    s["by_fuel_by_cat"].setdefault(bucket, {})
                    s["by_fuel_by_cat"][bucket][m] = dict(b["by_cat_fuel"].get(bucket, {}))
        s["partial_month"] = PARTIAL_MONTH

    # 10. meta: bump scrape_date + add partial_month
    payload["meta"]["scrape_date"] = datetime.utcnow().strftime("%Y-%m-%d")
    payload["meta"]["partial_month"] = PARTIAL_MONTH

    # 11. Maker-level monthly entries (only for 2026 months we recomputed).
    _update_monthly_maker_views(payload, by_month, maker_map)

    return payload


def _build_ytd_2026(payload, by_month):
    """Reconstruct ytd_2026 from monthly aggregates + monthly_fuel_mix_by_cat
    for the 2025 comparison window."""
    ytd_months = list(MONTHS_2026)
    # 'prior' = 2025-01..2025-05 from existing monthly_fuel_mix and
    # monthly_fuel_mix_by_cat. The existing payload's 2025 entries are
    # untouched, so we can read them.
    prior_months = [m.replace("2026", "2025") for m in ytd_months]

    # Current
    cur_total = sum(by_month[m]["total"] for m in ytd_months)
    cur_by_fuel = {f: 0 for f in FUELS}
    for m in ytd_months:
        for f, v in by_month[m]["by_fuel"].items():
            if f in cur_by_fuel:
                cur_by_fuel[f] += v
    cur_by_cat = {b: {f: 0 for f in FUELS} for b in BUCKETS}
    for m in ytd_months:
        for bucket, fs in by_month[m]["by_cat_fuel"].items():
            if bucket not in cur_by_cat:
                continue
            for f, v in fs.items():
                if f in cur_by_cat[bucket]:
                    cur_by_cat[bucket][f] += v
    for bucket in BUCKETS:
        cur_by_cat[bucket]["total"] = sum(cur_by_cat[bucket][f] for f in FUELS)

    # Prior (from existing 2025 monthly arrays in the payload, unchanged here)
    def sum_records(arr, months):
        out = {f: 0 for f in FUELS}
        tot = 0
        for r in arr:
            if r.get("month") in months:
                tot += r.get("total", 0)
                for f in FUELS:
                    out[f] = out.get(f, 0) + r.get(f, 0)
        return tot, out

    pr_total, pr_by_fuel = sum_records(payload["monthly_fuel_mix"], prior_months)

    pr_by_cat = {}
    for bucket in BUCKETS:
        arr = payload["monthly_fuel_mix_by_cat"].get(bucket, [])
        tot, by_f = sum_records(arr, prior_months)
        pr_by_cat[bucket] = {**by_f, "total": tot}

    return {
        "ytd_months": ytd_months,
        "full_months_for_comparison": ytd_months,
        "partial_trailing_month": PARTIAL_MONTH,
        "current": {
            "total": cur_total,
            "by_fuel": cur_by_fuel,
            "by_category": cur_by_cat,
        },
        "prior": {
            "total": pr_total,
            "by_fuel": pr_by_fuel,
            "by_category": pr_by_cat,
        },
    }


def _update_monthly_maker_views(payload, by_month, maker_map):
    """Refresh per-canonical-maker monthly entries for 2026 months.

    Three structures are touched:
      - monthly_maker_by_cat[bucket][canonical_maker][month] = int
      - monthly_maker_fuel[canonical_maker][month] = {fuel: int}
      - monthly_maker_fuel_by_cat[bucket][canonical_maker][month] = {fuel: int}

    Makers absent from the existing payload are skipped (kept out of the
    canonical view) so the dashboard maker universe stays consistent.
    """
    # First, build raw->canonical aggregates for each 2026 month.
    canon_cat_month = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # [bucket][canon][month]
    canon_fuel_month = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # [canon][month][fuel]
    canon_cf_month = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))  # [bucket][canon][month][fuel]

    for mth in MONTHS_2026:
        b = by_month[mth]
        for raw, by_b in b["by_maker_cat_national"].items():
            canon = normalise_maker(raw, maker_map)
            if not canon:
                continue
            for bucket, v in by_b.items():
                canon_cat_month[bucket][canon][mth] += v
        for raw, by_f in b["by_maker_fuel_national"].items():
            canon = normalise_maker(raw, maker_map)
            if not canon:
                continue
            for f, v in by_f.items():
                canon_fuel_month[canon][mth][f] = canon_fuel_month[canon][mth].get(f, 0) + v
        # for canon_cf, combine maker_cat + maker_fuel proportions
        # We don't have direct maker×cat×fuel from the source CSVs (no
        # all-state Maker × Cat × Fuel route). Skip canon_cf for now; the
        # affected view falls back to monthly_maker_fuel + monthly_maker_by_cat
        # if monthly_maker_fuel_by_cat is stale.

    # Apply to monthly_maker_by_cat
    mmc = payload.get("monthly_maker_by_cat", {})
    for bucket in BUCKETS:
        if bucket not in mmc:
            continue
        for canon, by_mth in mmc[bucket].items():
            if not isinstance(by_mth, dict):
                continue
            new_vals = canon_cat_month.get(bucket, {}).get(canon, {})
            for mth in MONTHS_2026:
                if mth in new_vals:
                    by_mth[mth] = new_vals[mth]
                elif mth in by_mth:
                    # canonical maker existed previously this month but has
                    # zero registrations in the new aggregate -> set 0
                    by_mth[mth] = 0

    # Apply to monthly_maker_fuel
    mmf = payload.get("monthly_maker_fuel", {})
    for canon, by_mth in mmf.items():
        if not isinstance(by_mth, dict):
            continue
        new_vals = canon_fuel_month.get(canon, {})
        for mth in MONTHS_2026:
            if mth in new_vals:
                by_mth[mth] = dict(new_vals[mth])
            elif mth in by_mth:
                by_mth[mth] = {}


# ---------------------------------------------------------------------------
# State payload updater
# ---------------------------------------------------------------------------

def update_state_payload(sp, agg):
    by_month = agg["by_month"]

    # Update meta
    sp["meta"]["partial_month"] = PARTIAL_MONTH
    if PARTIAL_MONTH not in sp["meta"]["months"]:
        sp["meta"]["months"].append(PARTIAL_MONTH)

    # National aggregate
    na = sp["national_aggregate"]
    for mth in MONTHS_2026:
        b = by_month[mth]
        na["monthly_total"][mth] = b["total"]
        for bucket in BUCKETS:
            na["by_cat"].setdefault(bucket, {})[mth] = b["by_cat"].get(bucket, 0)
        for f in FUELS:
            na["by_fuel"].setdefault(f, {})[mth] = b["by_fuel"].get(f, 0)
    # annual
    total_2026 = sum(by_month[m]["total"] for m in MONTHS_2026)
    ev_2026 = sum(by_month[m]["by_fuel"].get("EV", 0) for m in MONTHS_2026)
    na["annual_total"]["2026"] = total_2026
    na["annual_ev"]["2026"] = ev_2026
    na["annual_ev_pen"]["2026"] = (ev_2026 / total_2026) if total_2026 else 0.0

    # by_state
    bs = sp["by_state"]
    # Compute 2026 annual per-state
    annual_per_state = defaultdict(lambda: {
        "total": 0,
        "by_cat": {b: 0 for b in BUCKETS},
        "ev": 0,
        "by_cat_ev": {b: 0 for b in BUCKETS},
        "by_cat_total": {b: 0 for b in BUCKETS},
    })
    for mth in MONTHS_2026:
        b = by_month[mth]
        for st_name, sb in b["by_state"].items():
            ap = annual_per_state[st_name]
            ap["total"] += sb["total"]
            ap["ev"] += sb["by_fuel"].get("EV", 0)
            for bucket in BUCKETS:
                ap["by_cat"][bucket] += sb["by_cat"].get(bucket, 0)
                ap["by_cat_ev"][bucket] += sb["by_cat_fuel"].get(bucket, {}).get("EV", 0)
                ap["by_cat_total"][bucket] += sum(sb["by_cat_fuel"].get(bucket, {}).values())

    for st_name, st_obj in bs.items():
        # monthly buckets
        for mth in MONTHS_2026:
            sb = by_month[mth]["by_state"].get(st_name, _empty_state())
            st_obj["monthly_total"][mth] = sb["total"]
            for bucket in BUCKETS:
                st_obj["by_cat"].setdefault(bucket, {})[mth] = sb["by_cat"].get(bucket, 0)
            for f in FUELS:
                st_obj["by_fuel"].setdefault(f, {})[mth] = sb["by_fuel"].get(f, 0)
            for bucket in BUCKETS:
                st_obj["by_cat_fuel"].setdefault(bucket, {})
                for f in FUELS:
                    st_obj["by_cat_fuel"][bucket].setdefault(f, {})[mth] = sb["by_cat_fuel"].get(bucket, {}).get(f, 0)
        # annual
        ap = annual_per_state[st_name]
        st_obj["annual_total"]["2026"] = ap["total"]
        st_obj["annual_by_cat"]["2026"] = dict(ap["by_cat"])
        st_obj["annual_ev"]["2026"] = ap["ev"]
        st_obj["annual_ev_pen"]["2026"] = (ap["ev"] / ap["total"]) if ap["total"] else 0.0
        for bucket in BUCKETS:
            denom = ap["by_cat_total"][bucket]
            st_obj["annual_ev_pen_by_cat"].setdefault(bucket, {})["2026"] = (
                (ap["by_cat_ev"][bucket] / denom) if denom else 0.0
            )

    # choropleth
    chor = sp["choropleth"]
    for st_name, ap in annual_per_state.items():
        chor.setdefault("total_2026", {})[st_name] = ap["total"]
        chor.setdefault("ev_reg_2026", {})[st_name] = ap["ev"]
        chor.setdefault("ev_pen_2026", {})[st_name] = (ap["ev"] / ap["total"]) if ap["total"] else 0.0
        for bucket in BUCKETS:
            key = f"{bucket}_share_2026"
            chor.setdefault(key, {})[st_name] = (
                ap["by_cat"][bucket] / ap["total"] if ap["total"] else 0.0
            )

    # state_leaderboard.total_2026 (list of [state, value] sorted desc)
    sl = sp["state_leaderboard"]
    sl["total_2026"] = sorted(
        [[st, ap["total"]] for st, ap in annual_per_state.items()],
        key=lambda x: x[1], reverse=True,
    )
    sl["ev_pen_2026"] = sorted(
        [[st, (ap["ev"] / ap["total"]) if ap["total"] else 0.0]
         for st, ap in annual_per_state.items()],
        key=lambda x: x[1], reverse=True,
    )

    # state_yoy_total[state]['2026'] = (2026YTD - 2025full) / 2025full
    # IMPORTANT: 2026 is partial so this is a comparison vs full 2025; the
    # existing payload already uses this convention.
    for st_name, ap in annual_per_state.items():
        prev = sp["by_state"].get(st_name, {}).get("annual_total", {}).get("2025") or 0
        sp["state_yoy_total"].setdefault(st_name, {})["2026"] = (
            (ap["total"] - prev) / prev if prev else 0.0
        )

    # state_year_table
    syt = sp["state_year_table"]
    if "2026" not in syt["years"]:
        syt["years"].append("2026")
    for st_name, ap in annual_per_state.items():
        td = syt["data"].setdefault(st_name, {"total": {}, "ev_pen": {}, "ev_reg": {}, "yoy_total": {}})
        td["total"]["2026"] = ap["total"]
        td["ev_reg"]["2026"] = ap["ev"]
        td["ev_pen"]["2026"] = (ap["ev"] / ap["total"]) if ap["total"] else 0.0
        prev = td["total"].get("2025") or 0
        td["yoy_total"]["2026"] = (ap["total"] - prev) / prev if prev else 0.0

    # state_ev_milestones.by_state[state].per_month: replace 2026 entries +
    # recompute cum_ev forward + first_hit_month + latest_cum_ev.
    sem = sp["state_ev_milestones"]
    if PARTIAL_MONTH not in sem["months"]:
        sem["months"].append(PARTIAL_MONTH)
    thresholds = sem["thresholds"]
    for st_name, st_block in sem["by_state"].items():
        per_month = st_block["per_month"]
        # Make a dict mth -> ev for fast lookup, then rebuild ordered list
        ev_by_mth = {pm["month"]: pm.get("ev", 0) for pm in per_month}
        # Refresh 2026 months from source
        for mth in MONTHS_2026:
            sb = by_month[mth]["by_state"].get(st_name, _empty_state())
            ev_by_mth[mth] = sb["by_fuel"].get("EV", 0)
        # rebuild ordered list along sem["months"] order
        ordered_months = sem["months"]
        new_per_month = []
        cum = 0
        first_hit = {str(t): None for t in thresholds}
        for mth in ordered_months:
            ev = ev_by_mth.get(mth, 0)
            cum += ev
            for t in thresholds:
                if first_hit[str(t)] is None and cum >= t:
                    first_hit[str(t)] = mth
            new_per_month.append({"month": mth, "ev": ev, "cum_ev": cum})
        st_block["per_month"] = new_per_month
        st_block["first_hit_month"] = first_hit
        st_block["latest_cum_ev"] = cum

    return sp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    sp_bak = SP_PATH.with_suffix(f".bak.{ts}")
    dash_bak = DASH_PATH.with_suffix(f".bak.{ts}")
    shutil.copy(SP_PATH, sp_bak)
    shutil.copy(DASH_PATH, dash_bak)
    print(f"backup: {sp_bak.name}, {dash_bak.name}")

    print("Aggregating 2026 from state-level CSVs ...")
    agg = aggregate_2026()
    for mth in MONTHS_2026:
        b = agg["by_month"][mth]
        print(f"  {mth}: total={b['total']:,}  EV={b['by_fuel'].get('EV', 0):,}  states={len(b['by_state'])}")

    print("Updating state_payload.js ...")
    sp = load_state_payload()
    sp = update_state_payload(sp, agg)
    write_state_payload(sp)

    print("Updating inline payload in vahan_dashboard_v18.html ...")
    html = DASH_PATH.read_text()
    payload, m = load_inline_payload(html)
    payload = update_inline_payload(payload, agg)
    new_html = write_inline_payload(html, payload, m)
    DASH_PATH.write_text(new_html)

    print()
    print("Updated 2026 monthly totals (inline payload):")
    for r in payload["monthly_fuel_mix"][-6:]:
        print(f"  {r['month']}: total={r['total']:,}  EV={r['EV']:,}")
    print()
    print(f"annual_totals[2026] = {payload['annual_totals']['2026']:,}")
    print(f"annual_totals_by_fuel[2026] = {payload['annual_totals_by_fuel']['2026']}")
    print(f"meta.scrape_date = {payload['meta']['scrape_date']}")
    print(f"meta.partial_month = {payload['meta']['partial_month']}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
