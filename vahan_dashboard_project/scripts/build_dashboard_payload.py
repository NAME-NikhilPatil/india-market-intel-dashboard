#!/usr/bin/env python3
"""Build the v18 dashboard payloads from the canonical consolidated dataset.

Reads the standard dataset pointer (CURRENT_STANDARD_DATASET.json) -> consolidated
CSV, computes every aggregate the v18 dashboard expects, and writes two JSON
files that the rewire step (rewire_v18_dashboard.py) splices into the HTML:

  outputs/
    dashboard_payload.json        # the inline <script id="payload"> block
    dashboard_state_payload.json  # the formerly-external state_payload.js block

Maker name canonicalisation
---------------------------
The dashboard uses canonical names like "Hero Group", "Suzuki / Maruti", "Ola
Electric". The mapping was extracted from the archived v18 payload (535 raw
VAHAN names -> 471 canonical buckets) and lives at:

    scripts/_resources/maker_canonical_map.json

Makers in the new data that aren't in the mapping are normalised by a fallback
(title-case + common-suffix strip) and tagged "fallback" in the build log so we
can review which canonical entries to add explicitly.

Data routing
------------
- National maker totals (the source that has Ola = 47,604 YTD) come from
  `national_maker_month` rows of the consolidated CSV.
- State x maker x category totals come from `state_maker_category`.
- State x maker x fuel comes from `state_maker_fuel` (rescaled per maker-month
  so the fuel split sums to the canonical national or category total - this
  way the fuel-route scraping gaps for Ola/etc don't undercut totals).
- State x category x fuel comes from `state_category_fuel`.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "vahan_2021_2026_calendar"
CONSOLIDATED = DATA_DIR / "standard_consolidated" / "vahan_standard_consolidated_long.csv"
POINTER = DATA_DIR / "CURRENT_STANDARD_DATASET.json"
MAKER_MAP_PATH = ROOT / "scripts" / "_resources" / "maker_canonical_map.json"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# Domain constants ----------------------------------------------------------
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
FUEL_ORDER = ["EV", "Petrol", "Diesel", "Hybrid", "Others"]
BUCKETS = ["2W", "3W", "4W", "CV"]
PARTIAL_YEAR = 2026

CAT_CODE_TO_BUCKET = {
    "2WIC": "2W", "2WN": "2W", "2WT": "2W",
    "3WIC": "3W", "3WN": "3W", "3WT": "3W",
    "4WIC": "4W", "LMV": "4W", "LPV": "4W", "MMV": "4W", "MPV": "4W",
    "LGV": "CV", "MGV": "CV", "HGV": "CV", "HMV": "CV", "HPV": "CV",
    "OTH": "CV",
}

CAT_VERBOSE_TO_BUCKET = {
    "TWO WHEELER(NT)": "2W", "TWO WHEELER(T)": "2W",
    "TWO WHEELER (INVALID CARRIAGE)": "2W",
    "M-CYCLE/SCOOTER": "2W",
    "MOTOR CYCLE/SCOOTER-USED FOR HIRE": "2W",
    "MOTORISED CYCLE (CC > 25CC)": "2W",
    "THREE WHEELER(NT)": "3W", "THREE WHEELER(T)": "3W",
    "THREE WHEELER (INVALID CARRIAGE)": "3W",
    "THREE WHEELER (PASSENGER)": "3W", "THREE WHEELER (GOODS)": "3W",
    "THREE WHEELER (PERSONAL)": "3W",
    "E-RICKSHAW WITH CART (G)": "3W",
    "LIGHT MOTOR VEHICLE": "4W", "LIGHT PASSENGER VEHICLE": "4W",
    "FOUR WHEELER (INVALID CARRIAGE)": "4W",
    "MEDIUM MOTOR VEHICLE": "4W", "MEDIUM PASSENGER VEHICLE": "4W",
    "MOTOR CAR": "4W", "MOTOR CAB": "4W", "MAXI CAB": "4W",
    "ADAPTED VEHICLE": "4W", "CAMPER VAN / TRAILER": "4W",
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

SUFFIX_PATTERNS = [
    r"\s+\(P\)\s+LTD\.?$", r"\s+PVT\.?\s*LTD\.?$", r"\s+PRIVATE LIMITED$",
    r"\s+LIMITED$", r"\s+LTD\.?$", r"\s+CO\.?$", r"\s+CORPORATION$",
    r"\s+INDIA$", r"\s+\(INDIA\)$",
]

def fallback_canonical(raw: str) -> str:
    s = raw.strip()
    for p in SUFFIX_PATTERNS:
        s = re.sub(p, "", s, flags=re.IGNORECASE)
    return " ".join(w.capitalize() if not w.isupper() or len(w) > 4 else w for w in s.split())


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_canonical():
    """Load consolidated CSV split by dataset."""
    by_dataset = defaultdict(list)
    with CONSOLIDATED.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_dataset[r["dataset"]].append(r)
    print(f"  consolidated row count: {sum(len(v) for v in by_dataset.values()):,}")
    for k, v in by_dataset.items():
        print(f"    {k}: {len(v):,}")
    return by_dataset


def reg(r, key="registrations"):
    try:
        return int(r[key])
    except Exception:
        try:
            return int(float(r[key] or 0))
        except Exception:
            return 0


def load_maker_map():
    with MAKER_MAP_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Maker canonicaliser with fallback bookkeeping
# ---------------------------------------------------------------------------
class MakerCanon:
    def __init__(self, base_map):
        self.base = dict(base_map)
        self.fallback_added = {}

    def __call__(self, raw):
        if not raw:
            return None
        if raw in self.base:
            return self.base[raw]
        if raw in self.fallback_added:
            return self.fallback_added[raw]
        c = fallback_canonical(raw)
        self.fallback_added[raw] = c
        return c

    def report(self):
        if not self.fallback_added:
            print("  no fallback canonicalisation needed")
            return
        print(f"  fallback canonicalisation applied to {len(self.fallback_added)} unknown raw makers:")
        for raw, c in list(self.fallback_added.items())[:10]:
            print(f"    {raw!r} -> {c!r}")
        if len(self.fallback_added) > 10:
            print(f"    ... and {len(self.fallback_added) - 10} more")


# ---------------------------------------------------------------------------
# Long-form aggregates (one pass per dataset, cached in memory)
# ---------------------------------------------------------------------------
class Aggregates:
    """Read the four consolidated datasets and build the indexes the
    downstream payload builders need.

    Indexes are stored as plain dicts of dicts and exposed as attributes.
    """

    def __init__(self, by_dataset, canon: MakerCanon):
        self.canon = canon
        self._build_national_maker_month(by_dataset["national_maker_month"])
        self._build_state_maker_category(by_dataset["state_maker_category"])
        self._build_state_maker_fuel(by_dataset["state_maker_fuel"])
        self._build_state_category_fuel(by_dataset["state_category_fuel"])
        self._derive_months_and_states()

    def _build_national_maker_month(self, rows):
        # canon -> month -> int   (authoritative national maker totals)
        self.nat_canon_month = defaultdict(lambda: defaultdict(int))
        self.raw_to_canon_seen = {}
        for r in rows:
            raw = r["maker"]
            canon = self.canon(raw)
            self.raw_to_canon_seen[raw] = canon
            self.nat_canon_month[canon][r["month"]] += reg(r)

    def _build_state_maker_category(self, rows):
        # canon -> month -> bucket -> int (national, summed across states)
        # state -> canon -> month -> bucket -> int
        # state -> month -> int (state monthly total via category route)
        self.nat_canon_month_bucket = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        self.state_canon_month_bucket = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
        self.state_month_total = defaultdict(lambda: defaultdict(int))
        # also: state -> bucket -> month -> int (state monthly by bucket)
        self.state_bucket_month = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        for r in rows:
            raw = r["maker"]
            canon = self.canon(raw)
            self.raw_to_canon_seen[raw] = canon
            code = r["vehicle_category"]
            bucket = CAT_CODE_TO_BUCKET.get(code)
            if not bucket:
                continue
            mth = r["month"]
            st = r["state"]
            n = reg(r)
            if not n:
                continue
            self.nat_canon_month_bucket[canon][mth][bucket] += n
            self.state_canon_month_bucket[st][canon][mth][bucket] += n
            self.state_month_total[st][mth] += n
            self.state_bucket_month[st][bucket][mth] += n

    def _build_state_maker_fuel(self, rows):
        # canon -> month -> fuel -> int (national, summed)
        # state -> canon -> month -> fuel -> int
        # state -> month -> fuel -> int
        self.nat_canon_month_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        self.state_canon_month_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
        self.state_month_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        # raw long rows kept so we can emit payload["rows"]
        self._raw_fuel_rows = rows
        for r in rows:
            raw = r["maker"]
            canon = self.canon(raw)
            self.raw_to_canon_seen[raw] = canon
            fg = r["fuel_group"]
            if fg not in FUEL_ORDER:
                continue
            mth = r["month"]
            st = r["state"]
            n = reg(r)
            if not n:
                continue
            self.nat_canon_month_fuel[canon][mth][fg] += n
            self.state_canon_month_fuel[st][canon][mth][fg] += n
            self.state_month_fuel[st][mth][fg] += n

    def _build_state_category_fuel(self, rows):
        # month -> bucket -> fuel -> int (national, summed across states)
        # state -> bucket -> month -> fuel -> int
        self.nat_month_bucket_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        self.state_bucket_month_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
        for r in rows:
            cv = r["vehicle_category"]
            bucket = CAT_VERBOSE_TO_BUCKET.get(cv)
            if not bucket:
                continue
            fg = r["fuel_group"]
            if fg not in FUEL_ORDER:
                continue
            mth = r["month"]
            st = r["state"]
            n = reg(r)
            if not n:
                continue
            self.nat_month_bucket_fuel[mth][bucket][fg] += n
            self.state_bucket_month_fuel[st][bucket][mth][fg] += n

    def _derive_months_and_states(self):
        months = set()
        for d in (self.nat_canon_month, self.state_month_total["__none__"]):
            for v in d.values():
                if isinstance(v, dict):
                    months.update(v.keys())
                else:
                    months.add(v)
        # Use category-route state_month_total as the canonical month list
        for st_d in self.state_month_total.values():
            months.update(st_d.keys())
        self.months = sorted(months)
        # states
        self.state_names = sorted(set(
            list(self.state_month_total.keys())
            + list(self.state_canon_month_fuel.keys())
            + list(self.state_canon_month_bucket.keys())
            + list(self.state_bucket_month_fuel.keys())
        ))
        # state code map - take from any row that has both
        self.state_code_of = {}
        for st in self.state_names:
            self.state_code_of[st] = ""  # to be filled below from raw rows
        # Inspect the consolidated rows for state -> state_code (one row is enough)
        # We do this by scanning state_maker_fuel which is largest
        seen = set()
        for r in self._raw_fuel_rows:
            st = r.get("state"); code = r.get("state_code")
            if st and code and st not in seen:
                self.state_code_of[st] = code
                seen.add(st)

    # ------------------------------------------------------------------
    # Helpers used by both payload builders
    # ------------------------------------------------------------------
    def national_maker_year(self, canon, year):
        """Annual national total for a canonical maker. Sourced from
        national_maker_month (authoritative). Falls back to summing
        state_maker_category if a maker is absent from the national table."""
        total = 0
        for mth, v in self.nat_canon_month[canon].items():
            if mth.startswith(str(year) + "-"):
                total += v
        if total > 0:
            return total
        # fallback
        for mth, by_b in self.nat_canon_month_bucket[canon].items():
            if mth.startswith(str(year) + "-"):
                total += sum(by_b.values())
        return total

    def national_maker_year_bucket(self, canon, year, bucket):
        total = 0
        for mth, by_b in self.nat_canon_month_bucket[canon].items():
            if mth.startswith(str(year) + "-"):
                total += by_b.get(bucket, 0)
        return total

    def national_maker_year_fuel(self, canon, year, fuel):
        """Maker's fuel-route total for the year. NOT rescaled."""
        total = 0
        for mth, by_f in self.nat_canon_month_fuel[canon].items():
            if mth.startswith(str(year) + "-"):
                total += by_f.get(fuel, 0)
        return total

    def national_maker_month_total(self, canon, month):
        """The trusted monthly total (national_maker_month source)."""
        return self.nat_canon_month[canon].get(month, 0)

    def rescaled_maker_month_fuel(self, canon, month):
        """Return {fuel: int} for the maker-month, rescaled so the sum equals
        the canonical national total for that maker-month."""
        fuel_raw = self.nat_canon_month_fuel[canon].get(month, {})
        target = self.national_maker_month_total(canon, month)
        if not fuel_raw:
            return {}
        fsum = sum(fuel_raw.values())
        if fsum <= 0 or target <= 0:
            return {f: int(v) for f, v in fuel_raw.items()}
        scale = target / fsum
        return {f: int(round(v * scale)) for f, v in fuel_raw.items()}


# ---------------------------------------------------------------------------
# Build the inline (national) payload
# ---------------------------------------------------------------------------
def build_inline_payload(agg: Aggregates) -> dict:
    payload = {}
    months = agg.months
    full_years = [y for y in YEARS if y != PARTIAL_YEAR]
    latest_full = max(full_years)
    prior_full = sorted(full_years)[-2]

    # partial_month = max month in 2026
    months_2026 = [m for m in months if m.startswith(f"{PARTIAL_YEAR}-")]
    partial_month = max(months_2026) if months_2026 else None

    payload["meta"] = {
        "years": YEARS,
        "full_years": full_years,
        "partial_year": PARTIAL_YEAR,
        "latest_full_year": latest_full,
        "prior_full_year": prior_full,
        "fuel_order": FUEL_ORDER,
        "buckets": BUCKETS,
        "scrape_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "source_url": "https://vahan.parivahan.gov.in/vahan4dashboard/",
        "version": "v19",
        "data_layer": "canonical_consolidated",
        "partial_month": partial_month,
        "notes": "Built from vahan_standard_consolidated_long.csv. National maker totals from national_maker_month; state x maker x category/fuel from corresponding state-level datasets.",
    }

    # ---- Monthly fuel mix (national totals by fuel) ----
    monthly_fuel_mix = []
    monthly_ev_pen = []
    for mth in months:
        bk_fuel = agg.nat_month_bucket_fuel.get(mth, {})
        fuel_totals = {f: 0 for f in FUEL_ORDER}
        for bucket, fs in bk_fuel.items():
            for f, v in fs.items():
                fuel_totals[f] += v
        total = sum(fuel_totals.values())
        monthly_fuel_mix.append({"month": mth, **fuel_totals, "total": total})
        monthly_ev_pen.append({
            "month": mth, "ev": fuel_totals["EV"], "total": total,
            "pen": fuel_totals["EV"] / total if total else 0.0,
        })
    payload["monthly_fuel_mix"] = monthly_fuel_mix
    payload["monthly_ev_penetration"] = monthly_ev_pen

    # ---- Monthly fuel mix by category ----
    mfm_by_cat = {b: [] for b in BUCKETS}
    mep_by_cat = {b: [] for b in BUCKETS}
    for mth in months:
        bk_fuel = agg.nat_month_bucket_fuel.get(mth, {})
        for bucket in BUCKETS:
            fs = bk_fuel.get(bucket, {})
            fuel_totals = {f: fs.get(f, 0) for f in FUEL_ORDER}
            total = sum(fuel_totals.values())
            mfm_by_cat[bucket].append({"month": mth, **fuel_totals, "total": total, "derived": True})
            mep_by_cat[bucket].append({
                "month": mth, "ev": fuel_totals["EV"], "total": total,
                "pen": fuel_totals["EV"] / total if total else 0.0, "derived": True,
            })
    payload["monthly_fuel_mix_by_cat"] = mfm_by_cat
    payload["monthly_ev_pen_by_cat"] = mep_by_cat

    # ---- Annual totals ----
    annual_totals = {}
    annual_totals_by_fuel = {}
    for y in YEARS:
        fuel_totals = {f: 0 for f in FUEL_ORDER}
        ytotal = 0
        for mth in months:
            if not mth.startswith(f"{y}-"):
                continue
            for bucket, fs in agg.nat_month_bucket_fuel.get(mth, {}).items():
                for f, v in fs.items():
                    fuel_totals[f] += v
                    ytotal += v
        annual_totals[str(y)] = ytotal
        annual_totals_by_fuel[str(y)] = fuel_totals
    payload["annual_totals"] = annual_totals
    payload["annual_totals_by_fuel"] = annual_totals_by_fuel

    # ---- Annual EV penetration per category ----
    aep = []
    for y in YEARS:
        for bucket in BUCKETS:
            ev = 0
            tot = 0
            for mth in months:
                if not mth.startswith(f"{y}-"):
                    continue
                fs = agg.nat_month_bucket_fuel.get(mth, {}).get(bucket, {})
                ev += fs.get("EV", 0)
                tot += sum(fs.values())
            aep.append({"year": y, "category": bucket, "ev": ev, "total": tot,
                        "pen": ev / tot if tot else 0.0})
    payload["annual_ev_penetration"] = aep

    # ---- YTD 2026 (current vs prior-year same months) ----
    payload["ytd_2026"] = _build_ytd_2026(agg, months, partial_month)

    # ---- by_year_maker[cat][year][canon] = int  ----
    # `all` uses the authoritative national_maker_month total when available;
    # per-bucket entries are rescaled to sum to that total so the bucket split
    # remains consistent with the canonical year total.
    bym = {b: {str(y): {} for y in YEARS} for b in BUCKETS}
    bym["all"] = {str(y): {} for y in YEARS}
    byme = {b: {str(y): {} for y in YEARS} for b in BUCKETS}
    byme["all"] = {str(y): {} for y in YEARS}
    all_canons = set(agg.nat_canon_month.keys()) | set(agg.nat_canon_month_bucket.keys()) | set(agg.nat_canon_month_fuel.keys())
    for canon in all_canons:
        for y in YEARS:
            ystr = str(y)
            # bucket totals via category route (un-rescaled raw values)
            raw_bucket = {b: agg.national_maker_year_bucket(canon, y, b) for b in BUCKETS}
            cat_sum = sum(raw_bucket.values())
            # authoritative `all` total
            nat_total = agg.national_maker_year(canon, y)
            chosen_all = max(cat_sum, nat_total)
            if chosen_all:
                bym["all"][ystr][canon] = chosen_all
            # rescale buckets to sum to chosen_all
            if cat_sum > 0 and chosen_all > 0:
                scale = chosen_all / cat_sum
                # Use largest-remainder rounding so the rescaled buckets sum
                # exactly to chosen_all
                scaled = {b: raw_bucket[b] * scale for b in BUCKETS}
                int_parts = {b: int(scaled[b]) for b in BUCKETS}
                remainders = sorted(BUCKETS, key=lambda b: -(scaled[b] - int_parts[b]))
                shortfall = chosen_all - sum(int_parts.values())
                for b in remainders[:max(0, shortfall)]:
                    int_parts[b] += 1
                for b in BUCKETS:
                    if int_parts[b]:
                        bym[b][ystr][canon] = int_parts[b]
            else:
                # bucket data absent; leave per-bucket empty
                for b in BUCKETS:
                    if raw_bucket[b]:
                        bym[b][ystr][canon] = raw_bucket[b]

            # EV per bucket: take fuel-route EV, rescale to canonical, then split by bucket share
            ev_year_raw = agg.national_maker_year_fuel(canon, y, "EV")
            year_total_fuel = sum(agg.national_maker_year_fuel(canon, y, f) for f in FUEL_ORDER)
            if year_total_fuel > 0 and chosen_all > 0:
                ev_year = int(round(ev_year_raw * chosen_all / year_total_fuel))
            else:
                ev_year = ev_year_raw
            if ev_year:
                byme["all"][ystr][canon] = ev_year
                if chosen_all > 0:
                    for bucket in BUCKETS:
                        b_v = bym[bucket][ystr].get(canon, 0)
                        share = b_v / chosen_all
                        ev_b = int(round(ev_year * share))
                        if ev_b:
                            byme[bucket][ystr][canon] = ev_b
    payload["by_year_maker"] = bym
    payload["by_year_maker_ev"] = byme

    # ---- monthly_maker_by_cat[cat][canon][month] = int ----
    mmc = {b: defaultdict(dict) for b in BUCKETS}
    mmc["all"] = defaultdict(dict)
    for canon in all_canons:
        for mth in months:
            by_b = agg.nat_canon_month_bucket[canon].get(mth, {})
            for bucket in BUCKETS:
                v = by_b.get(bucket, 0)
                if v:
                    mmc[bucket][canon][mth] = v
            # all = sum of buckets OR national_maker_month (use whichever is greater
            # so the all view reflects the canonical national-maker-month source)
            all_v = sum(by_b.values()) if by_b else 0
            nat_v = agg.nat_canon_month[canon].get(mth, 0)
            chosen = max(all_v, nat_v)
            if chosen:
                mmc["all"][canon][mth] = chosen
    payload["monthly_maker_by_cat"] = {k: dict(v) for k, v in mmc.items()}

    # ---- monthly_maker_fuel[canon][month] = {fuel: int} (rescaled) ----
    mmf = defaultdict(dict)
    for canon in all_canons:
        for mth in months:
            split = agg.rescaled_maker_month_fuel(canon, mth)
            if split:
                # Only store fuel groups with non-zero value
                split = {f: v for f, v in split.items() if v}
                if split:
                    mmf[canon][mth] = split
    payload["monthly_maker_fuel"] = dict(mmf)

    # ---- monthly_maker_fuel_by_cat[cat][canon][month] = {fuel: int} ----
    # Approximation: for each maker-month, split the rescaled fuel total by bucket
    # share from nat_canon_month_bucket.
    mmfbc = {b: defaultdict(dict) for b in BUCKETS}
    for canon in all_canons:
        for mth in months:
            split = agg.rescaled_maker_month_fuel(canon, mth)
            if not split:
                continue
            by_b = agg.nat_canon_month_bucket[canon].get(mth, {})
            bk_sum = sum(by_b.values()) or 0
            if bk_sum <= 0:
                continue
            for bucket, bv in by_b.items():
                share = bv / bk_sum
                bk_split = {f: int(round(v * share)) for f, v in split.items()}
                bk_split = {f: v for f, v in bk_split.items() if v}
                if bk_split:
                    mmfbc[bucket][canon][mth] = bk_split
    payload["monthly_maker_fuel_by_cat"] = {k: dict(v) for k, v in mmfbc.items()}

    # ---- maker_universe[canon] ----
    mu = {}
    for canon in all_canons:
        entry = {
            "totals": {}, "by_cat": {}, "by_fuel": {},
            "rank_all": {}, "rank_2W": {}, "rank_3W": {}, "rank_4W": {}, "rank_CV": {},
        }
        for y in YEARS:
            ystr = str(y)
            entry["totals"][ystr] = bym["all"][ystr].get(canon, 0)
            entry["by_cat"][ystr] = {b: bym[b][ystr].get(canon, 0) for b in BUCKETS if bym[b][ystr].get(canon)}
            # fuel split for the year (rescaled by summing rescaled monthly splits)
            fl = defaultdict(int)
            for mth in months:
                if not mth.startswith(f"{y}-"):
                    continue
                for f, v in agg.rescaled_maker_month_fuel(canon, mth).items():
                    fl[f] += v
            entry["by_fuel"][ystr] = dict(fl)
        # ranks per year
        for y in YEARS:
            ystr = str(y)
            ordered = sorted(bym["all"][ystr].items(), key=lambda kv: -kv[1])
            for i, (c, _) in enumerate(ordered):
                if c == canon:
                    entry["rank_all"][ystr] = i + 1
                    break
            for bucket in BUCKETS:
                ordered_b = sorted(bym[bucket][ystr].items(), key=lambda kv: -kv[1])
                for i, (c, _) in enumerate(ordered_b):
                    if c == canon:
                        entry[f"rank_{bucket}"][ystr] = i + 1
                        break
        mu[canon] = entry
    # Subset to makers with non-zero totals in latest_full_year for compactness?
    # v18 had ~122; keep all.
    payload["maker_universe"] = mu

    # ---- maker_rank_bump[cat] = {makers: [top10], ranks: {year: {maker: rank}}}
    bump = {}
    TOP_BUMP = 10
    for cat_key in list(BUCKETS) + ["all"]:
        # Use latest_full to pick top-10 makers consistently across years
        latest_d = bym[cat_key][str(latest_full)]
        top10 = [c for c, _ in sorted(latest_d.items(), key=lambda kv: -kv[1])[:TOP_BUMP]]
        ranks = {}
        for y in YEARS:
            ystr = str(y)
            d = bym[cat_key][ystr]
            ordered = sorted(d.items(), key=lambda kv: -kv[1])
            ranks[ystr] = {c: i + 1 for i, (c, _) in enumerate(ordered)}
        bump[cat_key] = {"makers": top10, "ranks": ranks}

        ev_latest_d = byme[cat_key][str(latest_full)]
        ev_top10 = [c for c, _ in sorted(ev_latest_d.items(), key=lambda kv: -kv[1])[:TOP_BUMP]]
        ev_ranks = {}
        for y in YEARS:
            ystr = str(y)
            d_ev = byme[cat_key][ystr]
            ordered_ev = sorted(d_ev.items(), key=lambda kv: -kv[1])
            ev_ranks[ystr] = {c: i + 1 for i, (c, _) in enumerate(ordered_ev)}
        bump[f"ev_{cat_key}"] = {"makers": ev_top10, "ranks": ev_ranks}
    payload["maker_rank_bump"] = bump

    # ---- concentration[cat][year] = {top3, top5, top7, top10} ----
    conc = {}
    for cat_key in list(BUCKETS) + ["all"]:
        conc[cat_key] = {}
        for y in YEARS:
            ystr = str(y)
            d = bym[cat_key][ystr]
            total = sum(d.values()) or 1
            shares = sorted([v / total for v in d.values()], reverse=True)
            conc[cat_key][ystr] = {
                "top3": sum(shares[:3]),
                "top5": sum(shares[:5]),
                "top7": sum(shares[:7]),
                "top10": sum(shares[:10]),
            }
    payload["concentration"] = conc

    # ---- small_multiples[cat] = {makers: [top24], series: {maker: [year-values]}, years: [int-years]} ----
    sm = {}
    for cat_key in list(BUCKETS) + ["all"]:
        top24 = [c for c, _ in sorted(bym[cat_key][str(latest_full)].items(), key=lambda kv: -kv[1])[:24]]
        series = {c: [bym[cat_key][str(y)].get(c, 0) for y in YEARS] for c in top24}
        sm[cat_key] = {"makers": top24, "series": series, "years": list(YEARS)}

        ev_top24 = [c for c, _ in sorted(byme[cat_key][str(latest_full)].items(), key=lambda kv: -kv[1])[:24]]
        ev_series = {c: [byme[cat_key][str(y)].get(c, 0) for y in YEARS] for c in ev_top24}
        sm[f"ev_{cat_key}"] = {"makers": ev_top24, "series": ev_series, "years": list(YEARS)}
    payload["small_multiples"] = sm

    # ---- seasonality ----
    payload["seasonality"] = _build_seasonality(agg, months, partial_month)

    # ---- fuel_yoy ----
    payload["fuel_yoy"] = _build_fuel_yoy(annual_totals_by_fuel, full_years)

    # ---- ev_milestones (annual) ----
    payload["ev_milestones"] = _build_ev_milestones_annual(bym, byme, all_canons, full_years, latest_full)

    # ---- ev_milestones_monthly ----
    payload["ev_milestones_monthly"] = _build_ev_milestones_monthly(
        agg, months, all_canons, latest_full
    )

    # ---- maker_rank_monthly ----
    payload["maker_rank_monthly"] = _build_maker_rank_monthly(agg, months, all_canons, bym, latest_full)

    # ---- maker_fuel_sparklines ----
    payload["maker_fuel_sparklines"] = _build_sparklines(agg, months, all_canons, bym, latest_full)

    # ---- movers ----
    payload["movers"] = _build_movers(bym, byme, latest_full, prior_full, YEARS[0])

    # ---- cohorts ----
    payload["cohorts"] = _build_cohorts(bym, latest_full, YEARS[0])

    # ---- rows (annual long-form) ----
    payload["rows"] = _build_rows(agg)

    # ---- cyclicality (v19: industry-level inflection view) ----
    payload["cyclicality"] = _build_cyclicality(agg, months)

    # ---- maker profiles + years-to-N (v19.4: player profiles view) ----
    payload["maker_profiles"] = _build_maker_profiles(agg, months, bym, byme, payload)
    payload["years_to_n"] = _build_years_to_n(agg, months)

    return payload


# ---------------------------------------------------------------------------
# Maker profiles (per-maker destination page)
# ---------------------------------------------------------------------------
def _build_maker_profiles(agg, months, bym, byme, payload):
    """Per top-50 maker, pre-compute everything the Makers view needs to
    render a profile page: first-appearance month, peak month + value,
    rank evolution, threshold-crossing months, state over/under-index map,
    category + fuel mix, biography text.
    """
    latest_full = max(int(y) for y in bym["all"] if int(y) != PARTIAL_YEAR)
    # Top 50 by latest_full all-cats volume
    top50 = [c for c, _ in sorted(bym["all"][str(latest_full)].items(),
                                   key=lambda kv: -kv[1])[:50]]

    # Helper: national monthly total per maker (use canonical totals, fall back
    # to bucket-sum if needed)
    def nat_monthly(canon, mth):
        v = agg.nat_canon_month[canon].get(mth, 0)
        if v == 0:
            v = sum(agg.nat_canon_month_bucket[canon].get(mth, {}).values())
        return v

    # Precompute monthly all-segment totals (for share calculations)
    nat_total_per_month = {mth: 0 for mth in months}
    for mth in months:
        for canon in bym["all"]["2025"].keys():
            nat_total_per_month[mth] += nat_monthly(canon, mth)
    # Annual totals
    nat_annual_total = {y: 0 for y in YEARS}
    for canon in bym["all"][str(latest_full)].keys():
        for y in YEARS:
            for mth in months:
                if mth.startswith(f"{y}-"):
                    nat_annual_total[y] += nat_monthly(canon, mth)

    profiles = {}
    THRESHOLDS = [1000, 10000, 100000, 1000000]

    for canon in top50:
        prof = {}
        # Monthly series for this maker
        series = [nat_monthly(canon, mth) for mth in months]

        # First non-zero month
        first_idx = next((i for i, v in enumerate(series) if v > 0), None)
        prof["first_month"] = months[first_idx] if first_idx is not None else None

        # Peak month + value (monthly)
        if any(v > 0 for v in series):
            peak_idx = max(range(len(series)), key=lambda i: series[i])
            prof["peak_month"] = months[peak_idx]
            prof["peak_value"] = series[peak_idx]
        else:
            prof["peak_month"] = None
            prof["peak_value"] = 0

        # Threshold-crossing months (monthly volume crossings)
        crossings_monthly = {}
        for t in THRESHOLDS:
            for i, v in enumerate(series):
                if v >= t:
                    crossings_monthly[str(t)] = months[i]
                    break
        # Cumulative threshold crossings
        crossings_cum = {}
        cum = 0
        for i, v in enumerate(series):
            cum += v
            for t in THRESHOLDS:
                if str(t) not in crossings_cum and cum >= t:
                    crossings_cum[str(t)] = months[i]
        prof["thresholds_monthly"] = crossings_monthly
        prof["thresholds_cumulative"] = crossings_cum

        # Annual values + rank evolution
        annual_vol = {}
        rank_all = {}
        share_all = {}
        for y in YEARS:
            ystr = str(y)
            annual_vol[ystr] = bym["all"][ystr].get(canon, 0)
            # rank
            ordered = sorted(bym["all"][ystr].items(), key=lambda kv: -kv[1])
            for i, (c, _) in enumerate(ordered):
                if c == canon:
                    rank_all[ystr] = i + 1
                    break
            tot = nat_annual_total.get(y, 0)
            share_all[ystr] = (annual_vol[ystr] / tot) if tot else 0
        prof["annual_volume"] = annual_vol
        prof["rank_all"] = rank_all
        prof["share_all"] = share_all

        # Current standing
        prof["current_volume_ytd"] = annual_vol.get(str(PARTIAL_YEAR), 0)
        prof["current_rank_all"] = rank_all.get(str(PARTIAL_YEAR))
        prof["current_share_all"] = share_all.get(str(PARTIAL_YEAR))

        # Peak share + when
        share_items = sorted(share_all.items(), key=lambda kv: -kv[1])
        if share_items and share_items[0][1] > 0:
            prof["peak_share"] = share_items[0][1]
            prof["peak_share_year"] = share_items[0][0]
        else:
            prof["peak_share"] = 0
            prof["peak_share_year"] = None

        # Category mix (latest full year)
        cat_mix_total = 0
        cat_mix = {}
        for b in BUCKETS:
            v = bym[b][str(latest_full)].get(canon, 0)
            cat_mix[b] = v
            cat_mix_total += v
        if cat_mix_total > 0:
            cat_mix = {b: v / cat_mix_total for b, v in cat_mix.items() if v > 0}
        prof["category_mix"] = cat_mix
        prof["dominant_category"] = max(cat_mix.items(), key=lambda kv: kv[1])[0] if cat_mix else None

        # Fuel mix (latest full year, from rescaled fuel split)
        fuel_mix_raw = {}
        fuel_mix_total = 0
        for mth in months:
            if not mth.startswith(f"{latest_full}-"):
                continue
            for f, v in agg.rescaled_maker_month_fuel(canon, mth).items():
                fuel_mix_raw[f] = fuel_mix_raw.get(f, 0) + v
                fuel_mix_total += v
        if fuel_mix_total > 0:
            fuel_mix = {f: v / fuel_mix_total for f, v in fuel_mix_raw.items() if v > 0}
        else:
            fuel_mix = {}
        prof["fuel_mix"] = fuel_mix

        # State over/under-index ratios
        # Each state's share of THIS maker's volume, divided by that state's
        # share of the national total. >1 means over-indexed in that state.
        maker_state_vol = {}
        for st, by_canon in agg.state_canon_month_bucket.items():
            mvol = 0
            for mth, by_b in by_canon.get(canon, {}).items():
                if mth.startswith(f"{latest_full}-"):
                    mvol += sum(by_b.values())
            if mvol > 0:
                maker_state_vol[st] = mvol
        total_maker_vol = sum(maker_state_vol.values()) or 1
        # National state shares (latest_full)
        nat_state_vol = {}
        for st, sm in agg.state_month_total.items():
            sv = sum(v for mth, v in sm.items() if mth.startswith(f"{latest_full}-"))
            if sv > 0:
                nat_state_vol[st] = sv
        total_nat = sum(nat_state_vol.values()) or 1
        state_index = {}
        for st, mvol in maker_state_vol.items():
            maker_share = mvol / total_maker_vol
            nat_share = nat_state_vol.get(st, 0) / total_nat
            if nat_share > 0:
                state_index[st] = {
                    "maker_share": maker_share,
                    "nat_share": nat_share,
                    "index": maker_share / nat_share,
                    "maker_vol": mvol,
                }
        prof["state_index"] = state_index

        # Top threats / threatened (share swing vs the maker over latest_full vs prior)
        prior = latest_full - 1
        my_share_now = share_all.get(str(latest_full), 0)
        my_share_prior = share_all.get(str(prior), 0)
        my_delta = my_share_now - my_share_prior
        # Find makers who moved opposite to this one with the biggest shift
        opposite = []
        for other_canon in top50:
            if other_canon == canon:
                continue
            o_now = bym["all"][str(latest_full)].get(other_canon, 0) / (nat_annual_total.get(latest_full, 1) or 1)
            o_prev = bym["all"][str(prior)].get(other_canon, 0) / (nat_annual_total.get(prior, 1) or 1)
            opposite.append((other_canon, o_now - o_prev))
        if my_delta < 0:
            # We lost share — top threats are makers who gained the most
            opposite.sort(key=lambda x: -x[1])
            prof["top_threats"] = [{"maker": c, "delta_bps": d * 10000} for c, d in opposite[:3] if d > 0]
        else:
            # We gained share — top threatened are makers who lost the most
            opposite.sort(key=lambda x: x[1])
            prof["top_threatened"] = [{"maker": c, "delta_bps": d * 10000} for c, d in opposite[:3] if d < 0]

        # Biography auto-text
        prof["biography"] = _maker_biography(canon, prof, bym)

        # Monthly series itself (for sparklines/timeline)
        prof["monthly_series"] = series

        profiles[canon] = prof

    return profiles


def _maker_biography(canon, prof, bym):
    """Auto-generate a 2-paragraph maker biography from the computed profile."""
    parts = []

    # Paragraph 1: ranking + scale
    rank_now = prof.get("current_rank_all")
    share_now = prof.get("current_share_all", 0)
    peak_share = prof.get("peak_share", 0)
    peak_year = prof.get("peak_share_year")
    cur_year = str(PARTIAL_YEAR)
    bps_off_peak = (peak_share - share_now) * 10000 if peak_share and share_now is not None else None
    dom = prof.get("dominant_category") or "?"
    first_mth = prof.get("first_month")

    sent1 = f"{canon} is currently ranked #{rank_now} all-India" if rank_now else f"{canon}"
    sent1 += f" with a {share_now*100:.1f}% share of {cur_year} YTD registrations" if share_now else ""
    sent1 += "." if sent1 and not sent1.endswith(".") else ""
    parts.append(sent1)

    if peak_share and peak_year:
        if abs(bps_off_peak or 0) < 50:
            parts.append(f"Share is at its all-time high.")
        else:
            direction = "down" if (bps_off_peak or 0) > 0 else "up"
            parts.append(f"Peak share was {peak_share*100:.1f}% in {peak_year}, currently {direction} {abs(bps_off_peak):.0f} bps.")

    if first_mth:
        parts.append(f"First appeared in VAHAN in {_fmt_month_long(first_mth)}.")

    # Threshold crossings
    cm = prof.get("thresholds_monthly", {})
    if "100000" in cm:
        parts.append(f"Crossed 100,000 monthly registrations in {_fmt_month_long(cm['100000'])}.")
    elif "10000" in cm:
        parts.append(f"Crossed 10,000 monthly in {_fmt_month_long(cm['10000'])}.")

    # Paragraph 2: composition + threats
    cat_mix = prof.get("category_mix", {})
    if cat_mix:
        dom_share = cat_mix.get(dom, 0)
        if dom_share > 0.95:
            cat_line = f"Operations are nearly pure {dom} ({dom_share*100:.1f}%)."
        else:
            other_cats = [(c, s) for c, s in cat_mix.items() if c != dom and s > 0.02]
            other_cats.sort(key=lambda x: -x[1])
            if other_cats:
                others = " · ".join(f"{c} {s*100:.0f}%" for c, s in other_cats[:2])
                cat_line = f"Category mix: {dom} {dom_share*100:.0f}% (plus {others})."
            else:
                cat_line = f"Dominant category: {dom} ({dom_share*100:.0f}%)."
        parts.append(cat_line)

    fuel_mix = prof.get("fuel_mix", {})
    ev_share = fuel_mix.get("EV", 0)
    if ev_share > 0.95:
        parts.append(f"100% EV pure-play.")
    elif ev_share > 0.10:
        parts.append(f"EV share of own volume: {ev_share*100:.0f}%.")

    threats = prof.get("top_threats", [])
    threatened = prof.get("top_threatened", [])
    if threats:
        top = threats[0]
        parts.append(f"Biggest share gainer against them in {cur_year}: {top['maker']} (+{top['delta_bps']:.0f} bps).")
    elif threatened:
        top = threatened[0]
        parts.append(f"Lost the most share to this maker in {cur_year}: {top['maker']} ({top['delta_bps']:.0f} bps).")

    return " ".join(p for p in parts if p)


def _fmt_month_long(mth):
    """e.g. '2024-03' -> 'March 2024'"""
    if not mth:
        return "—"
    y, m = mth.split("-")
    names = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    return f"{names[int(m) - 1]} {y}"


def _build_years_to_n(agg, months):
    """Years-to-N leaderboard: for each canonical maker, the first month its
    CUMULATIVE registrations crossed each of {1K, 10K, 100K, 1M}.
    """
    THRESHOLDS = [1000, 10000, 100000, 1000000]
    out = {str(t): [] for t in THRESHOLDS}
    # Iterate every canonical maker that has any data
    all_canons = set(agg.nat_canon_month.keys()) | set(agg.nat_canon_month_bucket.keys())
    for canon in all_canons:
        cum = 0
        first_idx = None
        for i, mth in enumerate(months):
            v = agg.nat_canon_month[canon].get(mth, 0)
            if v == 0:
                v = sum(agg.nat_canon_month_bucket[canon].get(mth, {}).values())
            if v > 0 and first_idx is None:
                first_idx = i
            cum += v
            for t in THRESHOLDS:
                bucket = out[str(t)]
                # only record first crossing per maker
                if not any(r["maker"] == canon for r in bucket) and cum >= t:
                    months_elapsed = (i - first_idx) if first_idx is not None else None
                    bucket.append({
                        "maker": canon,
                        "first_month": months[first_idx] if first_idx is not None else None,
                        "crossed_month": mth,
                        "months_elapsed": months_elapsed,
                    })
    # Sort each bucket by months_elapsed asc (fastest first)
    for t in THRESHOLDS:
        out[str(t)].sort(key=lambda r: r["months_elapsed"] if r["months_elapsed"] is not None else 9999)
        out[str(t)] = out[str(t)][:25]  # top 25 fastest
    return out


# ---------------------------------------------------------------------------
# Cyclicality: per-segment TTM volume, YoY%, inflection points, phase tagging
# ---------------------------------------------------------------------------
def _build_cyclicality(agg, months):
    """Produce per-segment time series + phase classification for the
    Cyclicality view.

    For each segment (2W / 3W / 4W / CV) we compute:
      - monthly registrations + trailing-12-month sum (TTM)
      - YoY% (and EV-only YoY%)
      - YoY acceleration (second derivative; leading indicator)
      - inflection points (zero crossings)
      - current phase + duration in that phase
      - typical historical phase durations
      - drawdowns (peak-to-trough episodes on TTM)
      - calendar-year overlay arrays (each year as Jan..Dec values)
      - pre-anchor base (2022 monthly average) for "TTM is N.NNx base" context
    """
    # Exclude the partial month from phase/inflection math so a half-month
    # read doesn't get classified as a turn point. The partial month is
    # whichever month is the max in 2026 (kept in sync with meta.partial_month).
    months_2026 = [m for m in months if m.startswith("2026-")]
    partial_month = max(months_2026) if months_2026 else None

    by_segment = {}
    for bucket in BUCKETS:
        monthly_total = [0] * len(months)
        monthly_ev = [0] * len(months)
        for i, mth in enumerate(months):
            fs = agg.nat_month_bucket_fuel.get(mth, {}).get(bucket, {})
            monthly_total[i] = sum(fs.values())
            monthly_ev[i] = fs.get("EV", 0)

        by_segment[bucket] = _segment_cyclicality(months, monthly_total, monthly_ev, partial_month)

    return {
        "segments": BUCKETS,
        "months": months,
        "partial_month": partial_month,
        "by_segment": by_segment,
        "lead_lag": _cross_segment_lead_lag(by_segment),
    }


def _segment_cyclicality(months, monthly, ev_monthly, partial_month):
    """Compute TTM, YoY, acceleration, drawdowns, year overlay, phase tagging.

    `partial_month` is excluded from phase classification + inflection
    detection so a half-month value doesn't masquerade as a turn point. The
    series themselves still expose the partial-month value so the chart can
    render it (dimmed).
    """
    n = len(monthly)
    ttm = [None] * n
    ev_ttm = [None] * n
    yoy = [None] * n
    ev_yoy = [None] * n
    accel = [None] * n     # second derivative of YoY (m/m change in YoY)

    # Trailing 12-month sums (i >= 11)
    for i in range(n):
        if i >= 11:
            ttm[i] = sum(monthly[i - 11:i + 1])
            ev_ttm[i] = sum(ev_monthly[i - 11:i + 1])

    # YoY: monthly[i] / monthly[i-12] - 1 (i >= 12)
    for i in range(n):
        if i >= 12:
            prev = monthly[i - 12]
            yoy[i] = (monthly[i] - prev) / prev if prev else None
            prev_ev = ev_monthly[i - 12]
            ev_yoy[i] = (ev_monthly[i] - prev_ev) / prev_ev if prev_ev else None

    # Acceleration: YoY[i] - YoY[i-1]; smoothed 3-mo trailing average
    raw_accel = [None] * n
    for i in range(n):
        if i >= 13 and yoy[i] is not None and yoy[i - 1] is not None:
            raw_accel[i] = yoy[i] - yoy[i - 1]
    for i in range(n):
        sub = [raw_accel[j] for j in range(max(0, i - 2), i + 1) if raw_accel[j] is not None]
        accel[i] = (sum(sub) / len(sub)) if sub else None

    # Inflections (skip partial month)
    inflections = _find_inflections(months, yoy, exclude=partial_month)
    ev_inflections = _find_inflections(months, ev_yoy, exclude=partial_month)

    # Phase classification (skip partial month from the 3-mo window)
    phase = _classify_phase(months, yoy, exclude=partial_month)
    ev_phase = _classify_phase(months, ev_yoy, exclude=partial_month)

    # Phase durations: history of each phase episode for total YoY
    typical_durations, phase_episodes = _phase_episode_stats(months, yoy, exclude=partial_month)
    # Current phase duration (how many months we've been in the same phase)
    cur_duration = 0
    if phase_episodes:
        last = phase_episodes[-1]
        if last["phase"] == phase["current"]:
            cur_duration = last["length"]
    phase["duration_months"] = cur_duration
    phase["typical_duration"] = typical_durations.get(phase["current"])

    # Drawdowns on TTM series (peak-to-trough)
    drawdowns = _drawdowns(months, ttm, partial_month=partial_month)
    ev_drawdowns = _drawdowns(months, ev_ttm, partial_month=partial_month)

    # Calendar-year overlay: by_year_month[year][month_index 0..11] = yoy_value
    by_year_yoy = {}
    by_year_monthly = {}
    for i, mth in enumerate(months):
        yr, mo = mth.split("-")
        mo_i = int(mo) - 1
        by_year_yoy.setdefault(yr, [None] * 12)[mo_i] = yoy[i]
        by_year_monthly.setdefault(yr, [None] * 12)[mo_i] = monthly[i]

    # ------------------------------------------------------------------
    # v19.3 additions: smoother growth signals + momentum stats
    # ------------------------------------------------------------------
    # TTM-on-TTM YoY: TTM[i] / TTM[i-12] - 1. Much smoother than monthly YoY
    # because the numerator and denominator are each 12-month sums.
    ttm_yoy = [None] * n
    ev_ttm_yoy = [None] * n
    for i in range(n):
        if i >= 23 and ttm[i] is not None and ttm[i - 12] is not None and ttm[i - 12] > 0:
            ttm_yoy[i] = ttm[i] / ttm[i - 12] - 1
        if i >= 23 and ev_ttm[i] is not None and ev_ttm[i - 12] is not None and ev_ttm[i - 12] > 0:
            ev_ttm_yoy[i] = ev_ttm[i] / ev_ttm[i - 12] - 1

    # Latest 3/6/12/24-month annualised CAGRs of TTM (skip partial month).
    def latest_cagr(period_months):
        last_idx = None
        for i in range(n - 1, -1, -1):
            if months[i] == partial_month:
                continue
            if ttm[i] is not None:
                last_idx = i
                break
        if last_idx is None or last_idx < period_months:
            return None
        prior = ttm[last_idx - period_months]
        if not prior:
            return None
        ratio = ttm[last_idx] / prior
        # Annualised
        return ratio ** (12 / period_months) - 1
    cagrs = {
        "m3": latest_cagr(3),
        "m6": latest_cagr(6),
        "m12": latest_cagr(12),
        "m24": latest_cagr(24),
    }

    # Same CAGRs on EV TTM
    def latest_cagr_ev(period_months):
        last_idx = None
        for i in range(n - 1, -1, -1):
            if months[i] == partial_month:
                continue
            if ev_ttm[i] is not None:
                last_idx = i
                break
        if last_idx is None or last_idx < period_months:
            return None
        prior = ev_ttm[last_idx - period_months]
        if not prior:
            return None
        ratio = ev_ttm[last_idx] / prior
        return ratio ** (12 / period_months) - 1
    ev_cagrs = {
        "m3": latest_cagr_ev(3),
        "m6": latest_cagr_ev(6),
        "m12": latest_cagr_ev(12),
        "m24": latest_cagr_ev(24),
    }

    # Momentum streak: how many consecutive months has YoY been in current
    # direction (positive / negative) and how many in current trend
    # (accelerating / decelerating). Skip partial month.
    def streaks(series, accel_series):
        valid = [(i, v) for i, v in enumerate(series)
                 if v is not None and months[i] != partial_month]
        if len(valid) < 2:
            return {"sign_streak": 0, "sign_direction": "n/a",
                    "accel_streak": 0, "accel_direction": "n/a"}
        # sign streak: walk back from latest while sign matches
        latest_sign = 1 if valid[-1][1] > 0 else -1
        sign_count = 0
        for i in range(len(valid) - 1, -1, -1):
            s = 1 if valid[i][1] > 0 else -1
            if s == latest_sign:
                sign_count += 1
            else:
                break
        # accel direction: change in series between consecutive valid points
        diffs = [valid[i][1] - valid[i - 1][1] for i in range(1, len(valid))]
        latest_diff = diffs[-1] if diffs else 0
        latest_accel = 1 if latest_diff > 0 else (-1 if latest_diff < 0 else 0)
        accel_count = 0
        for i in range(len(diffs) - 1, -1, -1):
            d = 1 if diffs[i] > 0 else (-1 if diffs[i] < 0 else 0)
            if d == latest_accel:
                accel_count += 1
            else:
                break
        return {
            "sign_streak": sign_count,
            "sign_direction": "positive" if latest_sign > 0 else "negative",
            "accel_streak": accel_count,
            "accel_direction":
                "accelerating" if latest_accel > 0 else
                "decelerating" if latest_accel < 0 else "flat",
        }
    momentum = streaks(yoy, accel)
    ev_momentum = streaks(ev_yoy, None)

    # Pre-anchor base: average MONTHLY volume during 2022 (post-recovery,
    # representative of normal demand). TTM-vs-base ratio gives a quick
    # secular-growth read.
    base_year = "2022"
    base_vals = [monthly[i] for i, m in enumerate(months) if m.startswith(base_year + "-") and monthly[i]]
    base_monthly_avg = (sum(base_vals) / len(base_vals)) if base_vals else None
    base_annual = (base_monthly_avg * 12) if base_monthly_avg is not None else None
    latest_ttm = next((v for v in reversed(ttm) if v is not None), None)
    ttm_vs_base = (latest_ttm / base_annual) if (base_annual and latest_ttm) else None

    return {
        "monthly": monthly,
        "ttm": ttm,
        "yoy": yoy,
        "ttm_yoy": ttm_yoy,
        "accel": accel,
        "ev_monthly": ev_monthly,
        "ev_ttm": ev_ttm,
        "ev_yoy": ev_yoy,
        "ev_ttm_yoy": ev_ttm_yoy,
        "inflections": inflections,
        "ev_inflections": ev_inflections,
        "phase": phase,
        "ev_phase": ev_phase,
        "phase_episodes": phase_episodes,
        "typical_durations": typical_durations,
        "drawdowns": drawdowns,
        "ev_drawdowns": ev_drawdowns,
        "by_year_yoy": by_year_yoy,
        "by_year_monthly": by_year_monthly,
        "base_year": base_year,
        "base_annual": base_annual,
        "latest_ttm": latest_ttm,
        "ttm_vs_base": ttm_vs_base,
        "cagrs": cagrs,
        "ev_cagrs": ev_cagrs,
        "momentum": momentum,
        "ev_momentum": ev_momentum,
    }


def _phase_episode_stats(months, yoy, exclude=None):
    """Walk the YoY history, classify each window into a phase, then
    collapse consecutive same-phase months into episodes. Returns
    ({phase: typical_length_months}, [episode_list])."""
    # Reclassify each month using rolling 3-mo window (so we get a phase per month)
    # Then collapse runs.
    phases = []  # list of (month, phase) tuples
    valid_idx = [i for i, v in enumerate(yoy) if v is not None and months[i] != exclude]
    if len(valid_idx) < 3:
        return {}, []
    for k in range(2, len(valid_idx)):
        # 3-window ending at valid_idx[k]
        win = [yoy[valid_idx[k - 2]], yoy[valid_idx[k - 1]], yoy[valid_idx[k]]]
        mean = sum(win) / 3
        xs = [0, 1, 2]
        x_mean = 1
        y_mean = mean
        num = sum((xs[j] - x_mean) * (win[j] - y_mean) for j in range(3))
        den = sum((xs[j] - x_mean) ** 2 for j in range(3)) or 1
        slope = num / den
        if mean > 0 and slope > 0: p = "EXPANSION"
        elif mean > 0 and slope <= 0: p = "PEAK"
        elif mean <= 0 and slope < 0: p = "CONTRACTION"
        else: p = "TROUGH"
        phases.append((months[valid_idx[k]], p))
    # Collapse runs
    episodes = []
    if phases:
        cur_phase = phases[0][1]
        cur_start = phases[0][0]
        cur_len = 1
        for i in range(1, len(phases)):
            if phases[i][1] == cur_phase:
                cur_len += 1
            else:
                episodes.append({"phase": cur_phase, "start": cur_start,
                                  "end": phases[i - 1][0], "length": cur_len})
                cur_phase = phases[i][1]
                cur_start = phases[i][0]
                cur_len = 1
        episodes.append({"phase": cur_phase, "start": cur_start,
                          "end": phases[-1][0], "length": cur_len})
    # Typical (median) duration per phase across COMPLETED episodes (skip last)
    by_phase = defaultdict(list)
    for ep in episodes[:-1]:
        by_phase[ep["phase"]].append(ep["length"])
    typical = {}
    for p, lens in by_phase.items():
        lens.sort()
        typical[p] = lens[len(lens) // 2]  # median
    return typical, episodes


def _drawdowns(months, ttm, partial_month=None):
    """Find peak-to-trough episodes on the TTM series. A drawdown starts
    after a local TTM maximum and ends at the next local minimum where TTM
    starts rising again. Returns a list sorted by depth_pct desc.
    """
    valid = [(i, v) for i, v in enumerate(ttm) if v is not None and months[i] != partial_month]
    if len(valid) < 3:
        return []
    out = []
    i = 0
    while i < len(valid) - 1:
        # find local peak from i: walk forward while non-decreasing
        peak_k = i
        while peak_k + 1 < len(valid) and valid[peak_k + 1][1] >= valid[peak_k][1]:
            peak_k += 1
        if peak_k == len(valid) - 1:
            break
        peak_idx, peak_val = valid[peak_k]
        # find trough: walk forward while non-increasing
        trough_k = peak_k
        while trough_k + 1 < len(valid) and valid[trough_k + 1][1] <= valid[trough_k][1]:
            trough_k += 1
        trough_idx, trough_val = valid[trough_k]
        if trough_val < peak_val and trough_k > peak_k:
            depth_pct = (trough_val - peak_val) / peak_val
            out.append({
                "peak_month": months[peak_idx],
                "peak_ttm": peak_val,
                "trough_month": months[trough_idx],
                "trough_ttm": trough_val,
                "depth_pct": depth_pct,
                "duration_months": trough_k - peak_k,
            })
        i = trough_k + 1
    out.sort(key=lambda d: d["depth_pct"])  # most negative first
    return out


def _cross_segment_lead_lag(by_segment):
    """For each pair of segments, find the lag (in months) that maximises
    correlation between their YoY series. A positive lag of segment A vs B
    means A's YoY leads B's by that many months.

    Returns: {
      "matrix": [[lag_for_(A,B) ...], ...]   # 4x4
      "labels": ["2W", "3W", "4W", "CV"],
      "rankings": {"leads": [...], "lags": [...]}
    }
    """
    labels = list(by_segment.keys())
    n = len(labels)
    matrix = [[0] * n for _ in range(n)]
    sums = {lab: 0 for lab in labels}  # net "leadingness"

    def corr(a, b):
        pairs = [(av, bv) for av, bv in zip(a, b) if av is not None and bv is not None]
        if len(pairs) < 6:
            return 0.0
        mean_a = sum(p[0] for p in pairs) / len(pairs)
        mean_b = sum(p[1] for p in pairs) / len(pairs)
        num = sum((p[0] - mean_a) * (p[1] - mean_b) for p in pairs)
        den_a = sum((p[0] - mean_a) ** 2 for p in pairs) ** 0.5
        den_b = sum((p[1] - mean_b) ** 2 for p in pairs) ** 0.5
        if den_a == 0 or den_b == 0:
            return 0.0
        return num / (den_a * den_b)

    for i, A in enumerate(labels):
        for j, B in enumerate(labels):
            if i == j:
                matrix[i][j] = 0
                continue
            yoy_a = by_segment[A]["yoy"]
            yoy_b = by_segment[B]["yoy"]
            # Try lags from -6 .. +6 (A shifted by k vs B)
            best_corr = -2
            best_lag = 0
            for k in range(-6, 7):
                if k >= 0:
                    shifted_a = yoy_a[:len(yoy_a) - k] if k > 0 else yoy_a[:]
                    aligned_b = yoy_b[k:] if k > 0 else yoy_b[:]
                else:
                    shifted_a = yoy_a[-k:]
                    aligned_b = yoy_b[:len(yoy_b) + k]
                c = corr(shifted_a, aligned_b)
                if c > best_corr:
                    best_corr = c
                    best_lag = k
            matrix[i][j] = {"lag": best_lag, "corr": best_corr}
            sums[A] += -best_lag  # A leading means smaller lag from A
            sums[B] += best_lag

    sorted_labels = sorted(sums.items(), key=lambda kv: -kv[1])
    return {
        "labels": labels,
        "matrix": matrix,
        "rankings_by_leadingness": [lab for lab, _ in sorted_labels],
    }


def _find_inflections(months, yoy, exclude=None):
    """Months where YoY crosses zero. `exclude` skips the partial-month entry
    so it doesn't fire as a fake inflection.
    """
    out = []
    prev_sign = None
    for i in range(len(yoy)):
        if exclude is not None and months[i] == exclude:
            continue
        v = yoy[i]
        if v is None:
            continue
        sign = 1 if v > 0 else (-1 if v < 0 else 0)
        if prev_sign is not None and sign != 0 and sign != prev_sign:
            kind = "peak" if prev_sign > 0 else "trough"
            out.append({
                "month": months[i],
                "kind": kind,
                "yoy_before": yoy[i - 1],
                "yoy_after": v,
            })
        prev_sign = sign if sign != 0 else prev_sign
    return out


def _classify_phase(months, yoy, exclude=None):
    """Classify current cycle phase from last few months of YoY.

    Rule: take last 3 valid YoY values; mean tells us the level, slope tells
    us the direction.
      mean > 0 & slope > 0 -> EXPANSION (above trend, accelerating)
      mean > 0 & slope <= 0 -> PEAK     (above trend, decelerating)
      mean <= 0 & slope < 0 -> CONTRACTION (below trend, worsening)
      mean <= 0 & slope >= 0 -> TROUGH  (below trend, recovering)

    `since` = earliest month where the same phase has been continuous.
    `exclude` skips the partial-month entry from the 3-mo window.
    """
    # Collect last 3 valid points (skipping the partial month if given)
    valid = [(i, v) for i, v in enumerate(yoy)
             if v is not None and (exclude is None or months[i] != exclude)]
    if len(valid) < 3:
        return {"current": "INSUFFICIENT DATA", "since": None,
                "yoy_now": None, "trend": None}
    recent = valid[-3:]
    vals = [v for _, v in recent]
    mean = sum(vals) / 3
    # Slope: linear fit y = a*x + b on x=[0,1,2]
    xs = [0, 1, 2]
    x_mean = sum(xs) / 3
    y_mean = mean
    num = sum((xs[i] - x_mean) * (vals[i] - y_mean) for i in range(3))
    den = sum((xs[i] - x_mean) ** 2 for i in range(3)) or 1
    slope = num / den

    if mean > 0 and slope > 0:
        phase = "EXPANSION"
    elif mean > 0 and slope <= 0:
        phase = "PEAK"
    elif mean <= 0 and slope < 0:
        phase = "CONTRACTION"
    else:
        phase = "TROUGH"

    # Trend label
    if slope > 0.005:
        trend = "accelerating"
    elif slope < -0.005:
        trend = "decelerating"
    else:
        trend = "stable"

    # Walk back to find when this phase started
    since = None
    for i in range(len(valid) - 1, -1, -1):
        sub = valid[max(0, i - 2):i + 1]
        sub_vals = [v for _, v in sub]
        if len(sub_vals) < 3:
            break
        sub_mean = sum(sub_vals) / 3
        sub_xs = [0, 1, 2]
        sub_x_mean = sum(sub_xs) / 3
        sub_y_mean = sub_mean
        sub_num = sum((sub_xs[j] - sub_x_mean) * (sub_vals[j] - sub_y_mean) for j in range(3))
        sub_den = sum((sub_xs[j] - sub_x_mean) ** 2 for j in range(3)) or 1
        sub_slope = sub_num / sub_den
        sub_phase = (
            "EXPANSION" if sub_mean > 0 and sub_slope > 0 else
            "PEAK" if sub_mean > 0 and sub_slope <= 0 else
            "CONTRACTION" if sub_mean <= 0 and sub_slope < 0 else
            "TROUGH"
        )
        if sub_phase != phase:
            break
        since = months[valid[i][0]]

    return {
        "current": phase,
        "since": since,
        "yoy_now": vals[-1],
        "yoy_3mo_mean": mean,
        "slope": slope,
        "trend": trend,
    }


def _build_ytd_2026(agg, months, partial_month):
    if not partial_month:
        return {}
    # YTD months 2026
    ytd_months = [m for m in months if m.startswith(f"{PARTIAL_YEAR}-") and m <= partial_month]
    prior_months = [m.replace(f"{PARTIAL_YEAR}", f"{PARTIAL_YEAR - 1}") for m in ytd_months]

    def aggregate(ms):
        total = 0
        by_fuel = {f: 0 for f in FUEL_ORDER}
        by_cat = {b: {f: 0 for f in FUEL_ORDER} for b in BUCKETS}
        for mth in ms:
            for bucket, fs in agg.nat_month_bucket_fuel.get(mth, {}).items():
                for f, v in fs.items():
                    if f not in by_fuel:
                        continue
                    by_fuel[f] += v
                    total += v
                    by_cat[bucket][f] += v
        for bucket in BUCKETS:
            by_cat[bucket]["total"] = sum(by_cat[bucket][f] for f in FUEL_ORDER)
        return {"total": total, "by_fuel": by_fuel, "by_category": by_cat}

    return {
        "ytd_months": ytd_months,
        "full_months_for_comparison": ytd_months,
        "partial_trailing_month": partial_month,
        "current": aggregate(ytd_months),
        "prior": aggregate(prior_months),
    }


def _build_seasonality(agg, months, partial_month):
    totals = {}
    totals_by_cat = {b: {} for b in BUCKETS}
    by_fuel = {}
    by_fuel_by_cat = {b: {} for b in BUCKETS}
    for mth in months:
        bk_fuel = agg.nat_month_bucket_fuel.get(mth, {})
        fuel_totals = {f: 0 for f in FUEL_ORDER}
        m_total = 0
        for bucket in BUCKETS:
            fs = bk_fuel.get(bucket, {})
            b_total = sum(fs.values())
            totals_by_cat[bucket][mth] = b_total
            by_fuel_by_cat[bucket][mth] = {f: fs.get(f, 0) for f in FUEL_ORDER}
            for f, v in fs.items():
                if f in fuel_totals:
                    fuel_totals[f] += v
                    m_total += v
        totals[mth] = m_total
        by_fuel[mth] = fuel_totals
    return {
        "totals": totals,
        "totals_by_cat": totals_by_cat,
        "by_fuel": by_fuel,
        "by_fuel_by_cat": by_fuel_by_cat,
        "partial_month": partial_month,
    }


def _build_fuel_yoy(annual_totals_by_fuel, full_years):
    rows = []
    years_sorted = sorted(full_years)
    for f in FUEL_ORDER:
        by_year = {str(y): annual_totals_by_fuel[str(y)].get(f, 0) for y in years_sorted}
        yoy = {}
        for i, y in enumerate(years_sorted):
            if i == 0:
                yoy[str(y)] = None
            else:
                prev = by_year[str(years_sorted[i - 1])]
                cur = by_year[str(y)]
                yoy[str(y)] = (cur - prev) / prev if prev else None
        rows.append({"fuel": f, "by_year": by_year, "yoy": yoy})
    return {"rows": rows, "years": years_sorted}


def _build_ev_milestones_annual(bym, byme, all_canons, full_years, latest_full):
    thresholds = [1000, 10000, 100000, 500000]
    rows = []
    # Top 25 EV makers in latest_full_year (all cats)
    top = sorted(byme["all"][str(latest_full)].items(), key=lambda kv: -kv[1])[:25]
    for canon, _ in top:
        per_year = {}
        cum = 0
        first_hit = {str(t): None for t in thresholds}
        for y in sorted(YEARS):
            ev = byme["all"][str(y)].get(canon, 0)
            cum += ev
            per_year[str(y)] = ev
            for t in thresholds:
                if first_hit[str(t)] is None and cum >= t:
                    first_hit[str(t)] = y
        rows.append({"maker": canon, "by_year": per_year,
                     "first_hit_year": first_hit, "latest_cum_ev": cum})
    return {"thresholds": thresholds, "years": YEARS, "rows": rows}


def _build_ev_milestones_monthly(agg, months, all_canons, latest_full):
    thresholds = [1000, 10000, 100000, 500000]
    # Top 25 EV makers all-time (by total rescaled EV across all months)
    ev_totals = []
    for canon in all_canons:
        s = 0
        for mth in months:
            s += agg.rescaled_maker_month_fuel(canon, mth).get("EV", 0)
        if s > 0:
            ev_totals.append((canon, s))
    ev_totals.sort(key=lambda x: -x[1])
    top_all = [c for c, _ in ev_totals[:25]]

    def row_for(canon, scope_filter=None):
        cum = 0
        per_month = []
        first_hit = {str(t): None for t in thresholds}
        for mth in months:
            split = agg.rescaled_maker_month_fuel(canon, mth)
            ev = split.get("EV", 0)
            if scope_filter is not None:
                # restrict EV to specific bucket share
                bucket = scope_filter
                by_b = agg.nat_canon_month_bucket[canon].get(mth, {})
                bk_sum = sum(by_b.values()) or 0
                if bk_sum > 0:
                    ev = int(round(ev * by_b.get(bucket, 0) / bk_sum))
                else:
                    ev = 0
            cum += ev
            for t in thresholds:
                if first_hit[str(t)] is None and cum >= t:
                    first_hit[str(t)] = mth
            per_month.append({"month": mth, "ev": ev, "cum_ev": cum})
        return {"maker": canon, "per_month": per_month, "first_hit_month": first_hit,
                "latest_cum_ev": cum}

    rows = [row_for(c) for c in top_all]
    by_cat = {b: [] for b in BUCKETS}
    for bucket in BUCKETS:
        # Top 10 EV makers in this bucket by rescaled EV-in-bucket
        ev_by_bk = []
        for canon in all_canons:
            s = 0
            for mth in months:
                split = agg.rescaled_maker_month_fuel(canon, mth)
                ev = split.get("EV", 0)
                by_b = agg.nat_canon_month_bucket[canon].get(mth, {})
                bk_sum = sum(by_b.values()) or 0
                if bk_sum > 0:
                    s += int(round(ev * by_b.get(bucket, 0) / bk_sum))
            if s > 0:
                ev_by_bk.append((canon, s))
        ev_by_bk.sort(key=lambda x: -x[1])
        for canon, _ in ev_by_bk[:10]:
            by_cat[bucket].append(row_for(canon, scope_filter=bucket))

    return {"thresholds": thresholds, "months": months, "rows": rows, "by_cat": by_cat}


def _build_maker_rank_monthly(agg, months, all_canons, bym, latest_full):
    # Top 25 by latest_full all-cats; same makers used for each cat
    top_all = [c for c, _ in sorted(bym["all"][str(latest_full)].items(), key=lambda kv: -kv[1])[:25]]
    cats = list(BUCKETS) + ["all"]
    out = {}
    for cat_key in cats:
        # series[canon] = [rank_at_month_i ...]
        series = {c: [None] * len(months) for c in top_all}
        for i, mth in enumerate(months):
            if cat_key == "all":
                vols = []
                for c in all_canons:
                    v = agg.national_maker_month_total(c, mth)
                    if v == 0:
                        # fall back to summing buckets
                        v = sum(agg.nat_canon_month_bucket[c].get(mth, {}).values())
                    if v:
                        vols.append((c, v))
            else:
                vols = []
                for c in all_canons:
                    v = agg.nat_canon_month_bucket[c].get(mth, {}).get(cat_key, 0)
                    if v:
                        vols.append((c, v))
            vols.sort(key=lambda x: -x[1])
            ranks = {c: r + 1 for r, (c, _) in enumerate(vols)}
            for c in top_all:
                series[c][i] = ranks.get(c)
        out[cat_key] = {"makers": top_all, "months": months, "series": series}
    return out


def _build_sparklines(agg, months, all_canons, bym, latest_full):
    # Top 200 by latest_full all-cats. Each series element matches v18 shape:
    # { month, EV, Petrol, Diesel, Hybrid, Others, total, ev } where the
    # uppercase-fuel keys are the dashboard's spark-grid input, and `total`/
    # `ev` are convenience scalars.
    top = [c for c, _ in sorted(bym["all"][str(latest_full)].items(), key=lambda kv: -kv[1])[:200]]
    series = {}
    for canon in top:
        arr = []
        for mth in months:
            split = agg.rescaled_maker_month_fuel(canon, mth)
            rec = {"month": mth}
            for f in FUEL_ORDER:
                rec[f] = split.get(f, 0)
            rec["total"] = sum(rec[f] for f in FUEL_ORDER) or agg.national_maker_month_total(canon, mth)
            rec["ev"] = rec["EV"]
            arr.append(rec)
        series[canon] = arr
    return {"months": months, "series": series}


def _build_movers(bym, byme, latest_full, prior_full, first_year):
    # yoy_gainers/losers, ev_share_gainers, new_entrants (in latest but not first),
    # fell_out (in first but not latest). Field names match v18 schema exactly.
    latest = bym["all"][str(latest_full)]
    prior = bym["all"][str(prior_full)]
    first = bym["all"][str(first_year)]

    # Only rank meaningful makers (>= 1000 in latest) to keep the feed signal-rich.
    deltas = []
    for canon, v in latest.items():
        if v < 1000:
            continue
        pv = prior.get(canon, 0)
        if pv == 0:
            continue
        deltas.append((canon, v, pv, (v - pv) / pv))
    deltas.sort(key=lambda x: -x[3])
    gainers = [{"maker": c, "to": v, "from": pv, "pct": pct} for c, v, pv, pct in deltas[:8]]
    losers = [{"maker": c, "to": v, "from": pv, "pct": pct} for c, v, pv, pct in deltas[-8:][::-1]]

    # ev_share_gainers: change in EV/total share for makers with >= 1000 total in latest
    ev_share_deltas = []
    for canon, v in latest.items():
        if v < 1000:
            continue
        ev_l = byme["all"].get(str(latest_full), {}).get(canon, 0)
        ev_p = byme["all"].get(str(prior_full), {}).get(canon, 0)
        share_l = ev_l / v if v else 0
        share_p = ev_p / prior.get(canon, 1) if prior.get(canon) else 0
        if share_l == 0 and share_p == 0:
            continue
        ev_share_deltas.append((canon, share_l, share_p, share_l - share_p))
    ev_share_deltas.sort(key=lambda x: -x[3])
    ev_share_gainers = [
        {"maker": c, "cur_share": sl, "prev_share": sp, "delta_pp": d}
        for c, sl, sp, d in ev_share_deltas[:8]
    ]

    # v18 schema: new_entrants and fell_out are *lists of maker name strings*.
    new_entrants = [c for c, v in sorted(latest.items(), key=lambda kv: -kv[1])
                    if v >= 1000 and c not in first][:20]
    fell_out = [c for c, v in sorted(first.items(), key=lambda kv: -kv[1])
                if v >= 1000 and c not in latest][:20]

    return {
        "yoy_gainers": gainers,
        "yoy_losers": losers,
        "ev_share_gainers": ev_share_gainers,
        "new_entrants": new_entrants,
        "fell_out": fell_out,
        "latest_year": latest_full,
        "prior_year": prior_full,
        "first_year": first_year,
    }


def _build_cohorts(bym, latest_full, first_year):
    # Bucket makers by first-appearance year and roll up their cumulative volumes.
    first_seen = {}
    for y in YEARS:
        for canon, v in bym["all"][str(y)].items():
            if v <= 0:
                continue
            first_seen.setdefault(canon, y)
    cohorts = defaultdict(list)
    for canon, y in first_seen.items():
        cohorts[y].append(canon)
    # v18 schema: buckets is empty list, totals/movers/counts are dicts.
    # The dashboard's cohort lens panel was retired in v8 so this struct is
    # essentially inert — we just preserve the shape it expected.
    return {"buckets": [], "totals": {}, "movers": {}, "counts": {}}


def _build_rows(agg):
    """Emit the annual long-form table the dashboard reads at payload.rows.

    Each row = (year, cat, maker_raw, norm, fuel_group, fuel_type, n_annual).
    Source: state_maker_fuel rows summed across states.
    """
    # state_maker_fuel rows: each row already has year, maker (raw), fuel_group,
    # fuel_type, registrations. But it doesn't have a category - we derive
    # category from the maker's annual dominant category (state_maker_category).
    # For simplicity, attribute each maker-fuel row to the maker's dominant
    # category in that year.
    annual = defaultdict(lambda: defaultdict(int))  # (year, raw, fg, ft) -> int
    for r in agg._raw_fuel_rows:
        key = (int(r["calendar_year"]), r["maker"], r["fuel_group"], r["fuel_type"])
        annual[key]["n"] += reg(r)

    # dominant cat per (year, raw_maker) - from category route
    dom_cat = {}
    raw_cat_year = defaultdict(lambda: defaultdict(int))  # (year, raw) -> bucket -> int
    for st, by_canon in agg.state_canon_month_bucket.items():
        pass  # we no longer have raw_maker grouping in state_canon_month_bucket
    # Instead iterate raw rows from state_maker_category route via reading
    # the consolidated state_maker_category rows. We don't have direct access
    # here; we'll derive dominant cat from nat_canon_month_bucket using the
    # canonical mapping (less precise but fine for the rows table).

    out = []
    for (year, raw, fg, ft), v in annual.items():
        n = v["n"]
        if not n:
            continue
        canon = agg.canon(raw)
        # dominant cat of this canon in this year
        by_b_year = defaultdict(int)
        for mth, by_b in agg.nat_canon_month_bucket[canon].items():
            if mth.startswith(f"{year}-"):
                for b, vv in by_b.items():
                    by_b_year[b] += vv
        if by_b_year:
            top_b = max(by_b_year.items(), key=lambda kv: kv[1])[0]
        else:
            top_b = "2W"  # safe default
        out.append({
            "year": year, "cat": top_b, "maker": raw, "norm": canon,
            "fg": fg, "ft": ft, "n": n,
        })
    return out


# ---------------------------------------------------------------------------
# State payload builder
# ---------------------------------------------------------------------------
def build_state_payload(agg: Aggregates, inline_payload: dict) -> dict:
    months = agg.months
    states = agg.state_names
    full_years = inline_payload["meta"]["full_years"]
    latest_full = inline_payload["meta"]["latest_full_year"]
    partial_month = inline_payload["meta"]["partial_month"]

    sp = {"meta": {
        "states": [{"state_code": agg.state_code_of.get(st, ""), "state": st} for st in states],
        "years": [str(y) for y in YEARS],
        "full_years": [str(y) for y in full_years],
        "months": months,
        "partial_month": partial_month,
        "buckets": BUCKETS,
        "fuel_order": FUEL_ORDER,
        "data_status": "rebuilt_from_consolidated",
    }}

    # by_state[state] = ...
    by_state = {}
    for st in states:
        block = _build_state_block(agg, st, months)
        by_state[st] = block
    sp["by_state"] = by_state

    # state_leaderboard
    sp["state_leaderboard"] = _build_state_leaderboard(by_state, YEARS, BUCKETS)

    # top_states_for_maker[canon] = [{state, total}, ...]
    sp["top_states_for_maker"] = _build_top_states_for_maker(agg, states)

    # choropleth
    sp["choropleth"] = _build_choropleth(by_state, YEARS, BUCKETS)

    # maker_state_matrix
    sp["maker_state_matrix"] = _build_maker_state_matrix(agg, inline_payload, states)

    # maker_state_yoy + ev_pen
    sp["maker_state_yoy"], sp["maker_state_ev_pen"] = _build_maker_state_metrics(sp["maker_state_matrix"], by_state)

    # state_yoy_total[state][year] = float
    syt = {}
    for st in states:
        annual = by_state[st]["annual_total"]
        sy = {}
        for i, y in enumerate(YEARS):
            if i == 0:
                continue
            prev = annual.get(str(YEARS[i - 1])) or 0
            cur = annual.get(str(y)) or 0
            sy[str(y)] = (cur - prev) / prev if prev else 0.0
        syt[st] = sy
    sp["state_yoy_total"] = syt

    # state_ev_milestones
    sp["state_ev_milestones"] = _build_state_ev_milestones(by_state, months)

    # state_year_table
    sp["state_year_table"] = _build_state_year_table(by_state, YEARS, syt)

    # state_full_leaderboard (for latest_full_year)
    sp["state_full_leaderboard"] = _build_state_full_leaderboard(agg, by_state, states, latest_full)

    # national_aggregate
    sp["national_aggregate"] = _build_national_aggregate(agg, inline_payload, months)

    return sp


def _build_state_block(agg, st, months):
    block = {
        "monthly_total": {},
        "by_cat": {b: {} for b in BUCKETS},
        "by_fuel": {f: {} for f in FUEL_ORDER},
        "by_cat_fuel": {b: {f: {} for f in FUEL_ORDER} for b in BUCKETS},
        "top_makers_overall": [],
        "top_makers_per_year": {},
        "top_makers_per_cat": {b: [] for b in BUCKETS},
        "top_makers_per_fuel": {f: [] for f in FUEL_ORDER},
        "annual_total": {},
        "annual_by_cat": {},
        "annual_ev": {},
        "annual_ev_pen": {},
        "annual_ev_pen_by_cat": {b: {} for b in BUCKETS},
        "monthly_by_maker": {},
    }
    st_canon = agg.state_canon_month_bucket.get(st, {})
    st_canon_f = agg.state_canon_month_fuel.get(st, {})
    st_bk_month = agg.state_bucket_month.get(st, {})
    st_bk_month_fuel = agg.state_bucket_month_fuel.get(st, {})

    # monthly_total + by_cat + by_fuel + by_cat_fuel
    for mth in months:
        block["monthly_total"][mth] = agg.state_month_total[st].get(mth, 0)
        for bucket in BUCKETS:
            block["by_cat"][bucket][mth] = st_bk_month.get(bucket, {}).get(mth, 0)
            for f in FUEL_ORDER:
                block["by_cat_fuel"][bucket][f][mth] = st_bk_month_fuel.get(bucket, {}).get(mth, {}).get(f, 0)
        # by_fuel: prefer category-route attribution where possible
        for f in FUEL_ORDER:
            total = sum(st_bk_month_fuel.get(b, {}).get(mth, {}).get(f, 0) for b in BUCKETS)
            block["by_fuel"][f][mth] = total

    # annual aggregates
    for y in YEARS:
        ystr = str(y)
        block["annual_total"][ystr] = sum(
            v for mth, v in block["monthly_total"].items() if mth.startswith(f"{y}-")
        )
        block["annual_by_cat"][ystr] = {
            b: sum(v for mth, v in block["by_cat"][b].items() if mth.startswith(f"{y}-"))
            for b in BUCKETS
        }
        ev = sum(v for mth, v in block["by_fuel"]["EV"].items() if mth.startswith(f"{y}-"))
        tot = block["annual_total"][ystr]
        block["annual_ev"][ystr] = ev
        block["annual_ev_pen"][ystr] = ev / tot if tot else 0.0
        for bucket in BUCKETS:
            cat_ev = sum(
                v for mth, v in block["by_cat_fuel"][bucket]["EV"].items()
                if mth.startswith(f"{y}-")
            )
            cat_tot = block["annual_by_cat"][ystr].get(bucket, 0)
            block["annual_ev_pen_by_cat"][bucket][ystr] = cat_ev / cat_tot if cat_tot else 0.0

    # monthly_by_maker: store top 50 makers in this state
    canon_totals = []
    for canon, by_mth in st_canon.items():
        tot = sum(sum(by_b.values()) for by_b in by_mth.values())
        if tot > 0:
            canon_totals.append((canon, tot))
    canon_totals.sort(key=lambda x: -x[1])
    top50 = [c for c, _ in canon_totals[:50]]
    for canon in top50:
        block["monthly_by_maker"][canon] = {
            mth: sum(st_canon.get(canon, {}).get(mth, {}).values())
            for mth in months
        }
        # prune zeros to keep payload small
        block["monthly_by_maker"][canon] = {k: v for k, v in block["monthly_by_maker"][canon].items() if v}

    # top_makers_overall - top 25 with totals
    block["top_makers_overall"] = [
        {"maker": c, "total": t} for c, t in canon_totals[:25]
    ]
    # top_makers_per_year
    for y in YEARS:
        ystr = str(y)
        yt = []
        for canon, by_mth in st_canon.items():
            yt_total = sum(sum(by_b.values()) for mth, by_b in by_mth.items() if mth.startswith(f"{y}-"))
            if yt_total > 0:
                yt.append((canon, yt_total))
        yt.sort(key=lambda x: -x[1])
        block["top_makers_per_year"][ystr] = [{"maker": c, "n": t} for c, t in yt[:10]]
    # top_makers_per_cat - top 10 per bucket all-time
    for bucket in BUCKETS:
        tot_by_canon = []
        for canon, by_mth in st_canon.items():
            t = sum(by_b.get(bucket, 0) for by_b in by_mth.values())
            if t > 0:
                tot_by_canon.append((canon, t))
        tot_by_canon.sort(key=lambda x: -x[1])
        block["top_makers_per_cat"][bucket] = [{"maker": c, "n": t} for c, t in tot_by_canon[:10]]
    # top_makers_per_fuel - by fuel route
    for f in FUEL_ORDER:
        tot_by_canon = []
        for canon, by_mth in st_canon_f.items():
            t = sum(by_f.get(f, 0) for by_f in by_mth.values())
            if t > 0:
                tot_by_canon.append((canon, t))
        tot_by_canon.sort(key=lambda x: -x[1])
        block["top_makers_per_fuel"][f] = [{"maker": c, "n": t} for c, t in tot_by_canon[:10]]
    return block


def _build_state_leaderboard(by_state, years, buckets):
    sl = {}
    for y in years:
        ystr = str(y)
        totals = [(st, b["annual_total"].get(ystr, 0)) for st, b in by_state.items()]
        totals.sort(key=lambda x: -x[1])
        sl[f"total_{y}"] = [[st, v] for st, v in totals]
        ev_pens = [(st, b["annual_ev_pen"].get(ystr, 0)) for st, b in by_state.items()]
        ev_pens.sort(key=lambda x: -x[1])
        sl[f"ev_pen_{y}"] = [[st, v] for st, v in ev_pens]
    latest_full = max(years if isinstance(years, list) else list(years))
    # cat_share_<bucket>_<latest_full>
    for bucket in buckets:
        shares = []
        for st, b in by_state.items():
            tot = b["annual_total"].get(str(latest_full), 0) or 1
            share = b["annual_by_cat"].get(str(latest_full), {}).get(bucket, 0) / tot
            shares.append((st, share))
        shares.sort(key=lambda x: -x[1])
        sl[f"cat_share_{bucket}_{latest_full}"] = [[st, v] for st, v in shares]
    return sl


def _build_top_states_for_maker(agg, states):
    out = {}
    # for each canonical maker that appears in state_canon_month_bucket
    canons = set()
    for st in states:
        canons.update(agg.state_canon_month_bucket.get(st, {}).keys())
    for canon in canons:
        rows = []
        for st in states:
            by_mth = agg.state_canon_month_bucket.get(st, {}).get(canon, {})
            tot = sum(sum(by_b.values()) for by_b in by_mth.values())
            if tot > 0:
                rows.append({"state": st, "total": tot})
        rows.sort(key=lambda r: -r["total"])
        if rows:
            out[canon] = rows
    return out


def _build_choropleth(by_state, years, buckets):
    chor = {}
    for y in years:
        ystr = str(y)
        chor[f"total_{y}"] = {st: b["annual_total"].get(ystr, 0) for st, b in by_state.items()}
        chor[f"ev_reg_{y}"] = {st: b["annual_ev"].get(ystr, 0) for st, b in by_state.items()}
        chor[f"ev_pen_{y}"] = {st: b["annual_ev_pen"].get(ystr, 0) for st, b in by_state.items()}
        for bucket in buckets:
            chor[f"{bucket}_share_{y}"] = {
                st: (b["annual_by_cat"].get(ystr, {}).get(bucket, 0) /
                     (b["annual_total"].get(ystr, 0) or 1))
                for st, b in by_state.items()
            }
    return chor


def _build_maker_state_matrix(agg, inline_payload, states):
    # Top 30 makers all-time across all states
    canon_totals = defaultdict(int)
    for st in states:
        for canon, by_mth in agg.state_canon_month_bucket.get(st, {}).items():
            t = sum(sum(by_b.values()) for by_b in by_mth.values())
            canon_totals[canon] += t
    top30 = [c for c, _ in sorted(canon_totals.items(), key=lambda kv: -kv[1])[:30]]
    data = {}
    for canon in top30:
        rec = {}
        for st in states:
            by_mth = agg.state_canon_month_bucket.get(st, {}).get(canon, {})
            total = sum(sum(by_b.values()) for by_b in by_mth.values())
            by_year = {}
            for y in YEARS:
                yt = sum(sum(by_b.values()) for mth, by_b in by_mth.items() if mth.startswith(f"{y}-"))
                by_year[str(y)] = yt
            rec[st] = {"total": total, "by_year": by_year}
        data[canon] = rec
    return {"makers": top30, "data": data}


def _build_maker_state_metrics(matrix, by_state):
    yoy = {}
    ev_pen = {}
    for canon, st_data in matrix["data"].items():
        yoy[canon] = {}
        ev_pen[canon] = {}
        for st, rec in st_data.items():
            latest = rec["by_year"].get(str(PARTIAL_YEAR), 0)
            prior = rec["by_year"].get(str(PARTIAL_YEAR - 1), 0)
            yoy[canon][st] = (latest - prior) / prior if prior else 0.0
            # ev pen for the maker in that state: use state annual_ev_pen as proxy
            ev_pen[canon][st] = by_state[st]["annual_ev_pen"].get(str(PARTIAL_YEAR - 1), 0)
    return yoy, ev_pen


def _build_state_ev_milestones(by_state, months):
    thresholds = [1000, 10000, 100000, 500000]
    out = {"thresholds": thresholds, "months": months, "by_state": {}}
    for st, b in by_state.items():
        per_month = []
        cum = 0
        first_hit = {str(t): None for t in thresholds}
        for mth in months:
            ev = b["by_fuel"]["EV"].get(mth, 0)
            cum += ev
            for t in thresholds:
                if first_hit[str(t)] is None and cum >= t:
                    first_hit[str(t)] = mth
            per_month.append({"month": mth, "ev": ev, "cum_ev": cum})
        out["by_state"][st] = {"per_month": per_month, "first_hit_month": first_hit,
                               "latest_cum_ev": cum}
    return out


def _build_state_year_table(by_state, years, syt):
    out = {"years": [str(y) for y in years], "data": {}}
    for st, b in by_state.items():
        out["data"][st] = {
            "total": dict(b["annual_total"]),
            "ev_pen": dict(b["annual_ev_pen"]),
            "ev_reg": dict(b["annual_ev"]),
            "yoy_total": dict(syt.get(st, {})),
        }
    return out


def _build_state_full_leaderboard(agg, by_state, states, latest_full):
    ystr = str(latest_full)
    rows = []
    for st in states:
        b = by_state[st]
        total = b["annual_total"].get(ystr, 0)
        if not total:
            continue
        ev_reg = b["annual_ev"].get(ystr, 0)
        ev_pen = b["annual_ev_pen"].get(ystr, 0)
        shares = b["annual_by_cat"].get(ystr, {})
        twoW_share = (shares.get("2W", 0) / total) if total else 0
        threeW_share = (shares.get("3W", 0) / total) if total else 0
        fourW_share = (shares.get("4W", 0) / total) if total else 0
        cv_share = (shares.get("CV", 0) / total) if total else 0
        # top maker, top ev maker
        top_makers = b.get("top_makers_per_year", {}).get(ystr, [])
        top_maker = top_makers[0]["maker"] if top_makers else None
        top_maker_n = top_makers[0]["n"] if top_makers else 0
        # top ev maker: scan monthly_by_maker for the year and rank by EV (via rescaled fuel split per maker)
        # easier: use top_makers_per_fuel[EV]
        top_ev_makers = b.get("top_makers_per_fuel", {}).get("EV", [])
        top_ev_maker = top_ev_makers[0]["maker"] if top_ev_makers else None
        top_ev_maker_n = top_ev_makers[0]["n"] if top_ev_makers else 0
        prior_tot = b["annual_total"].get(str(latest_full - 1), 0)
        yoy = (total - prior_tot) / prior_tot if prior_tot else 0.0
        rows.append({
            "state": st, "total": total, "ev_reg": ev_reg, "ev_pen": ev_pen,
            "twoW_share": twoW_share, "threeW_share": threeW_share,
            "fourW_share": fourW_share, "cv_share": cv_share,
            "top_maker": top_maker, "top_maker_n": top_maker_n,
            "top_ev_maker": top_ev_maker, "top_ev_maker_n": top_ev_maker_n,
            "yoy": yoy,
        })
    rows.sort(key=lambda r: -r["total"])
    return rows


def _build_national_aggregate(agg, inline_payload, months):
    na = {
        "monthly_total": {},
        "by_cat": {b: {} for b in BUCKETS},
        "by_fuel": {f: {} for f in FUEL_ORDER},
        "monthly_by_maker": {},
        "annual_total": {},
        "annual_ev": {},
        "annual_ev_pen": {},
    }
    for mth in months:
        bk_fuel = agg.nat_month_bucket_fuel.get(mth, {})
        m_total = 0
        for bucket in BUCKETS:
            fs = bk_fuel.get(bucket, {})
            na["by_cat"][bucket][mth] = sum(fs.values())
            for f in FUEL_ORDER:
                na["by_fuel"][f][mth] = na["by_fuel"][f].get(mth, 0) + fs.get(f, 0)
                m_total += fs.get(f, 0)
        na["monthly_total"][mth] = m_total
    # monthly_by_maker: every canonical maker that appears anywhere
    all_canons = set(agg.nat_canon_month.keys()) | set(agg.nat_canon_month_bucket.keys())
    for canon in all_canons:
        # Use national_maker_month total when available, else fall back to sum of buckets
        by_mth = {}
        for mth in months:
            v = agg.national_maker_month_total(canon, mth)
            if v == 0:
                v = sum(agg.nat_canon_month_bucket[canon].get(mth, {}).values())
            if v:
                by_mth[mth] = v
        if by_mth:
            na["monthly_by_maker"][canon] = by_mth

    # annual aggregates
    for y in YEARS:
        ytotal = sum(v for mth, v in na["monthly_total"].items() if mth.startswith(f"{y}-"))
        yev = sum(v for mth, v in na["by_fuel"]["EV"].items() if mth.startswith(f"{y}-"))
        na["annual_total"][str(y)] = ytotal
        na["annual_ev"][str(y)] = yev
        na["annual_ev_pen"][str(y)] = yev / ytotal if ytotal else 0.0

    return na


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("Loading consolidated data...")
    by_dataset = load_canonical()
    print()
    print("Loading maker canonicalisation map...")
    base_map = load_maker_map()
    print(f"  {len(base_map)} raw -> canonical pairs loaded")
    canon = MakerCanon(base_map)

    print()
    print("Building aggregates...")
    agg = Aggregates(by_dataset, canon)
    canon.report()
    print(f"  months: {agg.months[0]} .. {agg.months[-1]} ({len(agg.months)} total)")
    print(f"  states: {len(agg.state_names)}")

    print()
    print("Building inline payload...")
    payload = build_inline_payload(agg)
    print(f"  inline payload keys: {len(payload)}")
    print(f"  meta.partial_month: {payload['meta']['partial_month']}")

    # Trim long-tail makers from the heavy maker-keyed structures so the
    # payload stays around v18's footprint (~3.5 MB). Keep any maker whose
    # max annual total >= 100 across YEARS (786 makers in this build).
    MIN_PEAK = 100
    keep = set(c for c, e in payload["maker_universe"].items()
               if max(e.get("totals", {}).values() or [0]) >= MIN_PEAK)
    dropped = len(payload["maker_universe"]) - len(keep)
    print(f"  trimming long-tail makers below max-year-total {MIN_PEAK}: keeping {len(keep)}, dropping {dropped}")
    payload["maker_universe"] = {c: v for c, v in payload["maker_universe"].items() if c in keep}
    payload["monthly_maker_fuel"] = {c: v for c, v in payload["monthly_maker_fuel"].items() if c in keep}
    for cat_key, d in payload["monthly_maker_by_cat"].items():
        payload["monthly_maker_by_cat"][cat_key] = {c: v for c, v in d.items() if c in keep}
    for cat_key, d in payload["monthly_maker_fuel_by_cat"].items():
        payload["monthly_maker_fuel_by_cat"][cat_key] = {c: v for c, v in d.items() if c in keep}
    for cat_key in list(payload["by_year_maker"].keys()):
        for ystr, d in payload["by_year_maker"][cat_key].items():
            payload["by_year_maker"][cat_key][ystr] = {c: v for c, v in d.items() if c in keep}
    for cat_key in list(payload["by_year_maker_ev"].keys()):
        for ystr, d in payload["by_year_maker_ev"][cat_key].items():
            payload["by_year_maker_ev"][cat_key][ystr] = {c: v for c, v in d.items() if c in keep}
    # maker_rank_bump: trim makers list + ranks dicts
    for cat_key, block in payload["maker_rank_bump"].items():
        block["makers"] = [m for m in block["makers"] if m in keep]
        for ystr, d in block["ranks"].items():
            block["ranks"][ystr] = {c: r for c, r in d.items() if c in keep}
    # small_multiples: trim makers list + series dict
    for cat_key, block in payload["small_multiples"].items():
        block["makers"] = [m for m in block["makers"] if m in keep]
        block["series"] = {c: s for c, s in block["series"].items() if c in keep}
    # rows: keep only those whose canonical is in keep
    payload["rows"] = [r for r in payload["rows"] if r["norm"] in keep]

    print()
    print("Building state payload...")
    sp = build_state_payload(agg, payload)
    print(f"  state payload keys: {len(sp)}")

    # Quick Ola/Ather sanity print
    OLA = "Ola Electric"
    ATH = "Ather Energy"
    print()
    print("=== Sanity check ===")
    for canon_name in [OLA, ATH]:
        mmf = payload["monthly_maker_fuel"].get(canon_name, {})
        bym_all = payload["by_year_maker"]["all"]["2026"].get(canon_name)
        mu_totals = payload["maker_universe"].get(canon_name, {}).get("totals", {}).get("2026")
        nbm = sp["national_aggregate"]["monthly_by_maker"].get(canon_name, {})
        print(f"  {canon_name}:")
        print(f"    monthly_maker_fuel 2026 = ", {k: v for k, v in sorted(mmf.items()) if k.startswith('2026')})
        print(f"    by_year_maker.all[2026] = {bym_all}, maker_universe.totals[2026] = {mu_totals}")
        print(f"    state_payload national 2026 = ", {k: v for k, v in sorted(nbm.items()) if k.startswith('2026')})

    print()
    print("Writing JSON outputs...")
    inline_path = OUT_DIR / "dashboard_payload.json"
    state_path = OUT_DIR / "dashboard_state_payload.json"
    inline_tmp = inline_path.with_suffix(inline_path.suffix + ".tmp")
    state_tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    with inline_tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with state_tmp.open("w", encoding="utf-8") as f:
        json.dump(sp, f, ensure_ascii=False, separators=(",", ":"))
    inline_tmp.replace(inline_path)
    state_tmp.replace(state_path)
    print(f"  wrote {inline_path} ({inline_path.stat().st_size:,} bytes)")
    print(f"  wrote {state_path} ({state_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
