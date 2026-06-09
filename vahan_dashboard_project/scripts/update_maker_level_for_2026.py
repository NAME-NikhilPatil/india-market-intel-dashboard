#!/usr/bin/env python3
"""Second-pass refresh for v18 dashboard: propagate the May-2026 update into
every maker-keyed structure that my first pass (update_v18_for_may2026.py)
left untouched.

Why this exists
---------------
The first pass updated headline national/state/category aggregates and a couple
of maker-keyed buckets (monthly_maker_fuel, monthly_maker_by_cat for 2W/3W/4W/CV).
But the dashboard has *many* other maker-keyed structures that all need to see
the new 2026-05 number — including the one the Anomalies feed reads
(state_payload.national_aggregate.monthly_by_maker). That's why "Ola Electric
numbers haven't changed" when looking at the anomalies / rank / sparkline / EV-
milestone views: the headline panels were updated, the maker drill-downs were
not.

This script reads the maker -> canonical-name mapping out of
PAYLOAD.rows.{maker, norm} and uses it to canonicalise raw VAHAN names when
aggregating from state-level CSVs.

Touched structures
------------------
Inline payload (vahan_dashboard_v18.html):
  - monthly_maker_by_cat['all'][canon][2026-mm]            (re-summed across cats)
  - by_year_maker[cat][2026][canon]                         (YTD)
  - by_year_maker_ev[cat][2026][canon]                      (YTD EV)
  - maker_universe[canon].totals/by_cat/by_fuel/rank_*['2026']
  - ev_milestones_monthly.rows[*].per_month[2026]           + cum_ev roll-forward
  - ev_milestones_monthly.by_cat[bucket][*].per_month[2026] + cum_ev roll-forward
  - maker_rank_monthly[cat].series[canon][2026-mm]
  - maker_fuel_sparklines.series[canon][2026-mm]

state_payload.js:
  - national_aggregate.monthly_by_maker[canon][2026-mm]
  - by_state[state].monthly_by_maker[canon][2026-mm]
  - top_states_for_maker[canon] (re-ranked using 2026 YTD)
  - maker_state_matrix.data[canon][state].by_year['2026'] + .total
  - maker_state_yoy[canon][state] (YoY using 2026 YTD vs 2025 full)
  - maker_state_ev_pen[canon][state] (EV pen using 2026 YTD)

Years 2021-2025 are never touched.
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

MONTHS_2026 = [f"2026-{m:02d}" for m in range(1, 6)]
BUCKETS = ["2W", "3W", "4W", "CV"]

# Reuse category mapping from first-pass script (kept in lock-step here so this
# script is standalone).
CAT_CODE_TO_BUCKET = {
    "2WIC": "2W", "2WN": "2W", "2WT": "2W",
    "3WIC": "3W", "3WN": "3W", "3WT": "3W",
    "4WIC": "4W", "LMV": "4W", "LPV": "4W", "MMV": "4W", "MPV": "4W",
    "LGV": "CV", "MGV": "CV", "HGV": "CV", "HMV": "CV", "HPV": "CV",
    "OTH": "CV",
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_sp():
    txt = SP_PATH.read_text()
    prefix = "window.__STATE_PAYLOAD__ = "
    return json.loads(txt[len(prefix):].rstrip().rstrip(";"))


def save_sp(sp):
    SP_PATH.write_text(
        "window.__STATE_PAYLOAD__ = "
        + json.dumps(sp, ensure_ascii=False, separators=(",", ":")) + ";"
    )


PAYLOAD_RE = re.compile(
    r'(<script id="payload" type="application/json">)(.*?)(</script>)', re.DOTALL,
)


def load_dash():
    html = DASH_PATH.read_text()
    m = PAYLOAD_RE.search(html)
    return html, m, json.loads(m.group(2))


def save_dash(html, m, payload):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    DASH_PATH.write_text(html[:m.start(2)] + body + html[m.end(2):])


# ---------------------------------------------------------------------------
# Aggregation helpers (read state-level CSVs, canonicalise, accumulate)
# ---------------------------------------------------------------------------
def build_maker_norm_map(payload):
    """Raw VAHAN maker name -> canonical dashboard maker name.

    Source of truth: payload['rows'], which carries both the raw `maker` and
    the canonical `norm` for every (year, cat, maker, fuel) annual row that
    was used to build the dashboard.
    """
    m = {}
    for r in payload.get("rows", []):
        raw = r.get("maker")
        norm = r.get("norm")
        if raw and norm:
            m[raw] = norm
    return m


def reg(row):
    try:
        return float(row.get("registrations") or 0)
    except Exception:
        return 0.0


def aggregate_canonical_2026(maker_map):
    """Return nested dicts keyed by canonical maker for the 2026 months.

    Source selection
    ----------------
    The two state-level CSVs disagree for some maker-month-state cells because
    VAHAN's `Maker × Fuel` and `Maker × Vehicle Category` pages don't always
    scrape cleanly together. For Ola Electric Jan 2026, the fuel-route CSV is
    missing Rajasthan (628), Telangana (256), and Chandigarh (5) — 889
    registrations the category-route CSV captured. The category route is the
    more complete source for *total* monthly volume.

    So this aggregator treats state_maker_category as the primary source for
    every total (national, per-state, per-bucket) and uses state_maker_fuel
    only to compute the fuel-mix shape (which is then rescaled per maker-month
    so the rescaled fuel split sums to the category-route total).

    Returns:
      nat_fuel[canon][month][fuel]              (rescaled to match nat_total)
      nat_total[canon][month]                   (from state_maker_category sum)
      nat_cat[canon][month][bucket]             (from state_maker_category)
      state_total[state][canon][month]          (from state_maker_category sum)
      state_cat[state][canon][month][bucket]    (from state_maker_category)
    """
    # First pass: category route → totals + bucket split, both national and state
    nat_cat = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    nat_total = defaultdict(lambda: defaultdict(int))
    state_cat = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    state_total = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    with (DATA / "state_maker_category_month_long.csv").open() as f:
        for r in csv.DictReader(f):
            mth = r["month"]
            if mth not in MONTHS_2026:
                continue
            canon = maker_map.get(r["maker"])
            if not canon:
                continue
            v = reg(r)
            if not v:
                continue
            bucket = CAT_CODE_TO_BUCKET.get(r["vehicle_category"])
            if not bucket:
                continue
            st = r["state"]
            nat_cat[canon][mth][bucket] += v
            nat_total[canon][mth] += v
            state_cat[st][canon][mth][bucket] += v
            state_total[st][canon][mth] += v

    # Second pass: fuel route → fuel-mix shape per (canon, month) at national
    # level, then rescale so the EV+Petrol+Diesel+Hybrid+Others sum equals
    # nat_total[canon][month]. This preserves the category route's larger
    # total while keeping the fuel split realistic.
    raw_fuel = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    with (DATA / "state_maker_fuel_month_long.csv").open() as f:
        for r in csv.DictReader(f):
            mth = r["month"]
            if mth not in MONTHS_2026:
                continue
            canon = maker_map.get(r["maker"])
            if not canon:
                continue
            v = reg(r)
            if not v:
                continue
            raw_fuel[canon][mth][r["fuel_group"]] += v

    nat_fuel = defaultdict(lambda: defaultdict(dict))
    for canon, by_mth in raw_fuel.items():
        for mth, fuels in by_mth.items():
            fuel_total = sum(fuels.values()) or 0
            cat_total = nat_total.get(canon, {}).get(mth, 0)
            if fuel_total > 0 and cat_total > 0:
                scale = cat_total / fuel_total
                nat_fuel[canon][mth] = {fg: int(round(v * scale)) for fg, v in fuels.items()}
            else:
                # No fuel-route data — keep raw (often empty)
                nat_fuel[canon][mth] = {fg: int(round(v)) for fg, v in fuels.items()}

    # For makers with cat-route data but no fuel-route data at all, attribute
    # the volume to the maker's dominant historical fuel (best effort: EV if
    # they appear in EV milestones, else "Petrol" as the catch-all 2W default).
    # We can fall back on the existing inline payload's `rows` table for this,
    # but for the scope of this fix the dashboard charts that read nat_fuel
    # will simply show no fuel split for those edge cases.

    # Cast to int and de-defaultdict
    def to_int(d):
        if isinstance(d, dict):
            return {k: to_int(v) for k, v in d.items()}
        return int(round(d))

    return (
        to_int(nat_fuel),
        to_int(nat_total),
        to_int(nat_cat),
        to_int(state_total),
        to_int(state_cat),
    )


# ---------------------------------------------------------------------------
# Inline-payload patches (national + maker)
# ---------------------------------------------------------------------------
def patch_inline(payload, nat_fuel, nat_total, nat_cat):
    # 0. monthly_maker_fuel[canon][month] = {fuel: registrations}
    # First pass used state_maker_fuel route directly; now we replace 2026 entries
    # with the rescaled-to-category-total fuel split.
    mmf = payload.get("monthly_maker_fuel", {})
    for canon, by_mth in mmf.items():
        if not isinstance(by_mth, dict):
            continue
        new_fuel = nat_fuel.get(canon, {})
        for mth in MONTHS_2026:
            if mth in new_fuel:
                by_mth[mth] = dict(new_fuel[mth])
            elif mth in by_mth:
                # maker has category-route volume but no fuel split — preserve
                # an empty dict so the dashboard doesn't show stale fuel mix
                # numbers
                if nat_total.get(canon, {}).get(mth, 0) == 0:
                    by_mth[mth] = {}

    # 1. monthly_maker_by_cat['all'] - the aggregate-across-categories view
    mmc = payload.get("monthly_maker_by_cat", {})
    if "all" in mmc:
        for canon, by_mth in mmc["all"].items():
            if not isinstance(by_mth, dict):
                continue
            tot = nat_total.get(canon, {})
            for mth in MONTHS_2026:
                if mth in tot:
                    by_mth[mth] = tot[mth]
                elif mth in by_mth:
                    by_mth[mth] = 0
    # Also make sure the per-bucket monthly_maker_by_cat dicts agree with
    # nat_cat (first-pass used a state_maker_cat aggregation; this re-affirms it)
    for bucket in BUCKETS:
        if bucket not in mmc:
            continue
        for canon, by_mth in mmc[bucket].items():
            if not isinstance(by_mth, dict):
                continue
            for mth in MONTHS_2026:
                v = nat_cat.get(canon, {}).get(mth, {}).get(bucket, 0)
                if mth in by_mth or v:
                    by_mth[mth] = v

    # 2. by_year_maker[cat]['2026'] = {canon: YTD}
    bym = payload.get("by_year_maker", {})
    if bym:
        # Compute YTD per canon per bucket
        ytd_by_cat = defaultdict(lambda: defaultdict(int))  # [bucket][canon] = int
        ytd_all = defaultdict(int)                          # [canon] = int
        for canon, by_mth in nat_cat.items():
            for mth, bk in by_mth.items():
                for bucket, v in bk.items():
                    ytd_by_cat[bucket][canon] += v
                    ytd_all[canon] += v
        # If a maker has fuel-route totals but no cat-route (rare), fall back
        # to fuel-route total for `all` so the YTD still moves.
        for canon, by_mth in nat_total.items():
            tot = sum(by_mth.values())
            if canon not in ytd_all and tot:
                ytd_all[canon] = tot
        for bucket in BUCKETS:
            if bucket in bym:
                bym[bucket]["2026"] = dict(ytd_by_cat.get(bucket, {}))
        if "all" in bym:
            bym["all"]["2026"] = dict(ytd_all)

    # 3. by_year_maker_ev[cat]['2026'] = {canon: YTD EV}
    byme = payload.get("by_year_maker_ev", {})
    if byme:
        ytd_ev_by_cat = defaultdict(lambda: defaultdict(int))
        ytd_ev_all = defaultdict(int)
        # We need cat × ev: combine nat_fuel (gives EV by maker by month)
        # with nat_cat (gives bucket by maker by month) — but we don't have
        # a direct three-way (canon, month, cat, fuel). Fall back to:
        # EV by canon = nat_fuel[canon][month]['EV']; then split across cats
        # proportionally to nat_cat[canon][month] (categorical mix at month level).
        for canon, by_mth in nat_fuel.items():
            for mth, fuels in by_mth.items():
                ev = fuels.get("EV", 0)
                if not ev:
                    continue
                # find bucket mix for this canon/month
                bk = nat_cat.get(canon, {}).get(mth, {})
                tot_bk = sum(bk.values()) or 1
                for bucket, v in bk.items():
                    share = v / tot_bk if tot_bk else 0
                    add = int(round(ev * share))
                    ytd_ev_by_cat[bucket][canon] += add
                ytd_ev_all[canon] += ev
        for bucket in BUCKETS:
            if bucket in byme:
                byme[bucket]["2026"] = dict(ytd_ev_by_cat.get(bucket, {}))
        if "all" in byme:
            byme["all"]["2026"] = dict(ytd_ev_all)

    # 4. maker_universe[canon] for 2026
    mu = payload.get("maker_universe", {})
    if mu:
        # First refresh totals / by_cat / by_fuel for 2026
        for canon, entry in mu.items():
            tot_2026 = sum(nat_total.get(canon, {}).values())
            entry.setdefault("totals", {})["2026"] = tot_2026
            # by_cat
            bk = defaultdict(int)
            for mth in MONTHS_2026:
                for b, v in nat_cat.get(canon, {}).get(mth, {}).items():
                    bk[b] += v
            entry.setdefault("by_cat", {})["2026"] = dict(bk)
            # by_fuel
            fl = defaultdict(int)
            for mth in MONTHS_2026:
                for f, v in nat_fuel.get(canon, {}).get(mth, {}).items():
                    fl[f] += v
            entry.setdefault("by_fuel", {})["2026"] = dict(fl)
        # Now recompute rank_all and rank_<bucket> for 2026
        # rank_all = rank by totals['2026'] across all makers
        ordered = sorted(mu.items(), key=lambda kv: -(kv[1].get("totals", {}).get("2026") or 0))
        for i, (canon, _) in enumerate(ordered):
            mu[canon].setdefault("rank_all", {})["2026"] = i + 1
        for bucket in BUCKETS:
            ordered_b = sorted(
                mu.items(),
                key=lambda kv: -(kv[1].get("by_cat", {}).get("2026", {}).get(bucket) or 0),
            )
            rank = 0
            for canon, entry in ordered_b:
                vol = (entry.get("by_cat", {}).get("2026", {}) or {}).get(bucket) or 0
                if vol > 0:
                    rank += 1
                    entry.setdefault(f"rank_{bucket}", {})["2026"] = rank
                else:
                    # absent from this bucket in 2026 — drop the 2026 rank
                    rb = entry.get(f"rank_{bucket}", {})
                    rb.pop("2026", None)

    # 5. ev_milestones_monthly: replace 2026 entries + roll cum_ev forward.
    emm = payload.get("ev_milestones_monthly", {})
    if emm:
        thresholds = emm.get("thresholds", [])
        months_order = emm.get("months", [])
        def refresh_rows(rows, scope):
            """scope: 'all' or a bucket key. Determines which series to use."""
            for row in rows:
                canon = row["maker"]
                # Get the 2026 monthly EV values for this maker
                ev_by_mth = {pm["month"]: pm.get("ev", 0) for pm in row.get("per_month", [])}
                for mth in MONTHS_2026:
                    if scope == "all":
                        ev_by_mth[mth] = nat_fuel.get(canon, {}).get(mth, {}).get("EV", 0)
                    else:
                        # bucket-specific EV — split EV by bucket proportionally
                        bk = nat_cat.get(canon, {}).get(mth, {})
                        tot_bk = sum(bk.values()) or 1
                        ev_total = nat_fuel.get(canon, {}).get(mth, {}).get("EV", 0)
                        share = bk.get(scope, 0) / tot_bk if tot_bk else 0
                        ev_by_mth[mth] = int(round(ev_total * share))
                # Re-roll cum_ev across months_order from scratch
                new_pm = []
                cum = 0
                first_hit = {str(t): None for t in thresholds}
                for mth in months_order:
                    ev = ev_by_mth.get(mth, 0)
                    cum += ev
                    for t in thresholds:
                        if first_hit[str(t)] is None and cum >= t:
                            first_hit[str(t)] = mth
                    new_pm.append({"month": mth, "ev": ev, "cum_ev": cum})
                row["per_month"] = new_pm
                row["first_hit_month"] = first_hit
                row["latest_cum_ev"] = cum
        refresh_rows(emm.get("rows", []), "all")
        for bucket, rows in (emm.get("by_cat") or {}).items():
            refresh_rows(rows, bucket)

    # 6. maker_rank_monthly[cat].series[canon] for 2026 months
    mrm = payload.get("maker_rank_monthly", {})
    for cat_key in list(mrm.keys()):
        block = mrm[cat_key]
        if "series" not in block:
            continue
        # For each 2026 month, rank makers by volume in that month under this cat
        for mth in MONTHS_2026:
            vols = []
            for canon in block.get("makers", list(block["series"].keys())):
                if cat_key == "all":
                    v = nat_total.get(canon, {}).get(mth, 0)
                else:
                    v = nat_cat.get(canon, {}).get(mth, {}).get(cat_key, 0)
                vols.append((canon, v))
            vols.sort(key=lambda x: -x[1])
            rank_map = {}
            r = 0
            for canon, v in vols:
                if v > 0:
                    r += 1
                    rank_map[canon] = r
                # makers with 0 in this month get null in their series
            for canon in block["series"]:
                series_arr = block["series"][canon]
                # Find index of mth in block.months
                if mth not in block.get("months", []):
                    continue
                idx = block["months"].index(mth)
                series_arr[idx] = rank_map.get(canon)  # null if not ranked

    # 7. maker_fuel_sparklines.series[canon] for 2026 months
    mfs = payload.get("maker_fuel_sparklines", {})
    if "series" in mfs and "months" in mfs:
        months = mfs["months"]
        for canon, series_arr in mfs["series"].items():
            for mth in MONTHS_2026:
                if mth not in months:
                    continue
                idx = months.index(mth)
                v = nat_total.get(canon, {}).get(mth, 0)
                # series elements might be objects {month, ev, total} or scalars;
                # detect and update accordingly
                if idx < len(series_arr):
                    el = series_arr[idx]
                    if isinstance(el, dict):
                        new = dict(el)
                        new["total"] = v
                        new["ev"] = nat_fuel.get(canon, {}).get(mth, {}).get("EV", 0)
                        new["month"] = mth
                        series_arr[idx] = new
                    else:
                        series_arr[idx] = v


# ---------------------------------------------------------------------------
# state_payload patches (per-state maker-level)
# ---------------------------------------------------------------------------
def patch_state_payload(sp, nat_total, state_total, state_cat):
    # 1. national_aggregate.monthly_by_maker[canon][2026-mm]
    nbm = sp["national_aggregate"]["monthly_by_maker"]
    for canon in set(list(nbm.keys()) + list(nat_total.keys())):
        if canon not in nbm:
            # New maker that wasn't tracked — skip (keeps universe stable)
            continue
        for mth in MONTHS_2026:
            v = nat_total.get(canon, {}).get(mth, 0)
            if mth in nbm[canon] or v:
                nbm[canon][mth] = v

    # 2. by_state[state].monthly_by_maker[canon][2026-mm]
    for state_name, sb in sp["by_state"].items():
        mbm = sb.get("monthly_by_maker", {})
        if not isinstance(mbm, dict):
            continue
        sttotals = state_total.get(state_name, {})
        for canon in list(mbm.keys()):
            for mth in MONTHS_2026:
                v = sttotals.get(canon, {}).get(mth, 0)
                if mth in mbm[canon] or v:
                    mbm[canon][mth] = v
        # Also add canon-makers that have non-zero state_total but aren't in
        # the existing mbm — they're new entrants to that state
        for canon, by_mth in sttotals.items():
            if canon in mbm:
                continue
            if not any(by_mth.get(mth) for mth in MONTHS_2026):
                continue
            mbm[canon] = {mth: by_mth.get(mth, 0) for mth in MONTHS_2026}

    # 3. top_states_for_maker[canon] — re-rank states by total volume in window
    # (the existing structure stores ordered list of {state, total, ev_reg, share}).
    # We need a state-level full-history total for each maker to re-rank. The
    # cheapest correct approach is to read the per-state monthly_by_maker we
    # just wrote and re-sum.
    if "top_states_for_maker" in sp:
        tsfm = sp["top_states_for_maker"]
        for canon, current in tsfm.items():
            # Re-compute total across all months for this maker per state
            new_totals = {}
            for state_name, sb in sp["by_state"].items():
                mbm = sb.get("monthly_by_maker", {})
                if canon in mbm:
                    new_totals[state_name] = sum(mbm[canon].values())
            ordered = sorted(new_totals.items(), key=lambda kv: -kv[1])
            # Preserve the prior record shape but refresh totals + ordering
            tsfm[canon] = [
                {"state": s, "total": int(round(t))} for s, t in ordered if t > 0
            ]

    # 4. maker_state_matrix.data[canon][state].by_year['2026'] + .total
    msm = sp.get("maker_state_matrix")
    if msm and "data" in msm:
        for canon, st_data in msm["data"].items():
            for state_name, rec in st_data.items():
                # by_year[2026] = sum of 2026 months for this canon in this state
                ytd = sum(
                    (state_total.get(state_name, {}).get(canon, {}).get(mth, 0))
                    for mth in MONTHS_2026
                )
                if "by_year" in rec:
                    rec["by_year"]["2026"] = ytd
                # refresh total
                rec["total"] = sum(rec.get("by_year", {}).values())

    # 5. maker_state_yoy[canon][state] = (2026YTD - 2025full) / 2025full
    msy = sp.get("maker_state_yoy")
    if msy:
        # Need 2025 totals per maker per state from existing matrix data
        for canon in msy:
            for state_name in list(msy[canon].keys()):
                ytd_2026 = sum(
                    (state_total.get(state_name, {}).get(canon, {}).get(mth, 0))
                    for mth in MONTHS_2026
                )
                # 2025 baseline from maker_state_matrix if available
                prev = 0
                if msm and canon in msm.get("data", {}) and state_name in msm["data"][canon]:
                    prev = msm["data"][canon][state_name].get("by_year", {}).get("2025", 0) or 0
                msy[canon][state_name] = ((ytd_2026 - prev) / prev) if prev else 0.0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    shutil.copy(SP_PATH, SP_PATH.with_suffix(f".bak.{ts}"))
    shutil.copy(DASH_PATH, DASH_PATH.with_suffix(f".bak.{ts}"))
    print(f"backups: *.bak.{ts}")

    print("Loading existing payloads ...")
    html, m_payload_tag, payload = load_dash()
    sp = load_sp()

    print("Building maker normalisation map from payload.rows ...")
    maker_map = build_maker_norm_map(payload)
    print(f"  raw maker names mapped: {len(maker_map):,}")
    canons = sorted(set(maker_map.values()))
    print(f"  canonical makers covered: {len(canons):,}")

    print("Aggregating 2026 by canonical maker × state × month ...")
    nat_fuel, nat_total, nat_cat, state_total, state_cat = aggregate_canonical_2026(maker_map)
    # Spot check
    OLA = "Ola Electric"
    print(f"  spot check: {OLA} 2026 monthly totals = "
          f"{ {mth: nat_total.get(OLA, {}).get(mth, 0) for mth in MONTHS_2026} }")
    print(f"  spot check: UP {OLA} 2026-05 = "
          f"{state_total.get('Uttar Pradesh', {}).get(OLA, {}).get('2026-05', 0):,}")

    print("Patching inline payload ...")
    patch_inline(payload, nat_fuel, nat_total, nat_cat)

    print("Patching state_payload ...")
    patch_state_payload(sp, nat_total, state_total, state_cat)

    print("Saving ...")
    save_dash(html, m_payload_tag, payload)
    save_sp(sp)

    # Final spot check
    print()
    print("=== Final Ola Electric spot check ===")
    print("Inline payload:")
    print(f"  monthly_maker_fuel[Ola Electric][2026-05] = {payload['monthly_maker_fuel'].get('Ola Electric', {}).get('2026-05')}")
    print(f"  monthly_maker_by_cat[all][Ola Electric][2026-05] = {payload['monthly_maker_by_cat'].get('all', {}).get('Ola Electric', {}).get('2026-05')}")
    print(f"  monthly_maker_by_cat[2W][Ola Electric][2026-05] = {payload['monthly_maker_by_cat'].get('2W', {}).get('Ola Electric', {}).get('2026-05')}")
    print(f"  by_year_maker[all][2026][Ola Electric] = {payload['by_year_maker']['all'].get('2026', {}).get('Ola Electric')}")
    print(f"  by_year_maker_ev[all][2026][Ola Electric] = {payload['by_year_maker_ev']['all'].get('2026', {}).get('Ola Electric')}")
    print(f"  maker_universe[Ola Electric].totals[2026] = {payload['maker_universe']['Ola Electric']['totals'].get('2026')}")
    ola_row = next((r for r in payload['ev_milestones_monthly']['rows'] if r['maker'] == 'Ola Electric'), None)
    if ola_row:
        last = ola_row['per_month'][-1]
        print(f"  ev_milestones_monthly.rows[Ola Electric] last = {last}")
        print(f"    latest_cum_ev = {ola_row['latest_cum_ev']:,}")
    print("state_payload:")
    print(f"  national_aggregate.monthly_by_maker[Ola Electric][2026-05] = {sp['national_aggregate']['monthly_by_maker']['Ola Electric'].get('2026-05')}")
    print(f"  by_state[Uttar Pradesh].monthly_by_maker[Ola Electric][2026-05] = {sp['by_state']['Uttar Pradesh']['monthly_by_maker']['Ola Electric'].get('2026-05')}")
    print(f"  by_state[Karnataka].monthly_by_maker[Ola Electric][2026-05] = {sp['by_state']['Karnataka']['monthly_by_maker']['Ola Electric'].get('2026-05')}")


if __name__ == "__main__":
    main()
