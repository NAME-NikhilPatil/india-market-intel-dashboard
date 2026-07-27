"""Build a single JSON blob for embedding into the dashboard HTML.

Reads all 7 CSVs, computes:
- Yearly per-segment totals, market shares, ranks
- HHI (Herfindahl-Hirschman Index) by year per segment
- Top-N by year
- Monthly aggregate manufactured vs sold (gap = inventory build)
- Per-company monthly time series
- Company master (first year, total MW, segments served, growth)
- New-entrant count per year
- State-level rollups, unclaimed ratios
- 2026 full-year projection (linear annualization from partial data)
"""
import csv, json, os, datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))


def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def read_csv(name):
    with open(os.path.join(BASE, name)) as fp:
        return list(csv.DictReader(fp))


# ── Raw reads ─────────────────────────────────────────────
dash = read_csv("dashboard_totals.csv")
stock_tot = read_csv("stock_summary_totals.csv")
stock_state = read_csv("stock_summary_by_state.csv")
cell_y = read_csv("cell_company_yearly_manufactured_mw.csv")
mod_y = read_csv("module_company_yearly_manufactured_mw.csv")
cell_m = read_csv("cell_monthly_manufactured_sold_mw.csv")
mod_m = read_csv("module_monthly_manufactured_sold_mw.csv")

# ── Dashboard headline numbers ────────────────────────────
totals = {r["metric"]: f(r["value"]) for r in dash}
stockTotals = {r["metric"]: f(r["value_mw"]) for r in stock_tot}

# ── Stock by state – clean & merge duplicates ─────────────
def norm_state(s):
    s = s.strip()
    # Merge known case duplicates seen in raw data
    aliases = {
        "Jammu And Kashmir": "Jammu and Kashmir",
        "Andaman And Nicobar Islands": "Andaman and Nicobar Islands",
        "The Dadra And Nagar Haveli And Daman And Diu": "Dadra and Nagar Haveli and Daman and Diu",
        "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
        "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    }
    return aliases.get(s, s)


state_agg = defaultdict(lambda: {
    "state": "", "total_users": 0,
    "cell_mfg": 0.0, "cell_res": 0.0, "mod_mfg": 0.0, "mod_res": 0.0,
    "cell_unc_mfg": 0.0, "cell_unc_res": 0.0, "mod_unc_mfg": 0.0, "mod_unc_res": 0.0,
})
for r in stock_state:
    s = norm_state(r["state"])
    a = state_agg[s]
    a["state"] = s
    a["total_users"] += int(r["total_users"])
    a["cell_mfg"] += f(r["cell_with_manufacturer_mw"])
    a["cell_res"] += f(r["cell_with_reseller_mw"])
    a["mod_mfg"] += f(r["module_with_manufacturer_mw"])
    a["mod_res"] += f(r["module_with_reseller_mw"])
    a["cell_unc_mfg"] += f(r["cell_unclaimed_with_manufacturer_mw"])
    a["cell_unc_res"] += f(r["cell_unclaimed_with_reseller_mw"])
    a["mod_unc_mfg"] += f(r["module_unclaimed_with_manufacturer_mw"])
    a["mod_unc_res"] += f(r["module_unclaimed_with_reseller_mw"])

states = []
for s in state_agg.values():
    total_stock = s["cell_mfg"] + s["cell_res"] + s["mod_mfg"] + s["mod_res"]
    total_unc = s["cell_unc_mfg"] + s["cell_unc_res"] + s["mod_unc_mfg"] + s["mod_unc_res"]
    grand = total_stock + total_unc
    s["total_stock"] = round(total_stock, 2)
    s["total_unclaimed"] = round(total_unc, 2)
    s["grand_total"] = round(grand, 2)
    s["unclaimed_pct"] = round((total_unc / grand * 100) if grand else 0, 2)
    s["per_user_mw"] = round((grand / s["total_users"]) if s["total_users"] else 0, 4)
    for k in ("cell_mfg", "cell_res", "mod_mfg", "mod_res",
              "cell_unc_mfg", "cell_unc_res", "mod_unc_mfg", "mod_unc_res"):
        s[k] = round(s[k], 2)
    states.append(s)
states.sort(key=lambda x: -x["grand_total"])

# ── Yearly per-company (cell & module) ────────────────────
def build_yearly(rows, mw_field, segment):
    out = []
    for r in rows:
        out.append({
            "year": int(r["year"]),
            "rank": int(r["rank"]),
            "agency_id": r["agency_id"],
            "company": r["company_name"].strip(),
            "mw": f(r[mw_field]),
            "is_almm": r["is_almm"].lower() == "true",
            "segment": segment,
        })
    return out


cell_yearly = build_yearly(cell_y, "cell_manufactured_mw", "cell")
mod_yearly = build_yearly(mod_y, "module_manufactured_mw", "module")

# ── Monthly per-company (cell & module) ───────────────────
def build_monthly(rows, segment):
    out = []
    for r in rows:
        out.append({
            "year": int(r["year"]),
            "month": int(r["month"]),
            "month_name": r["month_name"],
            "agency_id": r["agency_id"] or None,
            "company": r["company_name"].strip(),
            "metric": r["metric"],
            "mw": f(r["value_mw"]),
            "segment": segment,
        })
    return out


cell_monthly = build_monthly(cell_m, "cell")
mod_monthly = build_monthly(mod_m, "module")

# ── Derived: yearly totals per segment ────────────────────
def yearly_totals(rows):
    out = defaultdict(float)
    for r in rows:
        out[r["year"]] += r["mw"]
    return {y: round(v, 2) for y, v in sorted(out.items())}


yt_cell = yearly_totals(cell_yearly)
yt_mod = yearly_totals(mod_yearly)

# ── HHI (sum of squared market shares × 10000) per year per segment ──
def hhi_by_year(rows):
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r["mw"])
    out = {}
    for y, vals in by_year.items():
        tot = sum(vals)
        if tot == 0:
            out[y] = 0
            continue
        h = sum((v / tot * 100) ** 2 for v in vals)
        out[y] = round(h, 1)
    return dict(sorted(out.items()))


hhi_cell = hhi_by_year(cell_yearly)
hhi_mod = hhi_by_year(mod_yearly)

# ── Active manufacturer count per year per segment ────────
def active_per_year(rows):
    by_year = defaultdict(set)
    for r in rows:
        by_year[r["year"]].add(r["company"])
    return {y: len(s) for y, s in sorted(by_year.items())}


active_cell = active_per_year(cell_yearly)
active_mod = active_per_year(mod_yearly)

# ── Company master ───────────────────────────────────────
def company_master(rows, segment):
    by_co = defaultdict(lambda: {"name": "", "agency_id": "", "segment": segment,
                                 "years": set(), "total_mw": 0.0,
                                 "first_year": 9999, "last_year": 0,
                                 "by_year": defaultdict(float), "is_almm": False})
    for r in rows:
        c = by_co[r["company"]]
        c["name"] = r["company"]
        c["agency_id"] = r["agency_id"]
        c["years"].add(r["year"])
        c["total_mw"] += r["mw"]
        c["first_year"] = min(c["first_year"], r["year"])
        c["last_year"] = max(c["last_year"], r["year"])
        c["by_year"][r["year"]] += r["mw"]
        c["is_almm"] = c["is_almm"] or r["is_almm"]
    out = []
    for c in by_co.values():
        # CAGR using first→last full years if last is not partial year (2026)
        full_years = sorted([y for y in c["years"] if y < 2026])
        cagr = None
        if len(full_years) >= 2:
            first, last = full_years[0], full_years[-1]
            v0, v1 = c["by_year"][first], c["by_year"][last]
            n = last - first
            if v0 > 0 and v1 > 0 and n > 0:
                cagr = round((((v1 / v0) ** (1 / n)) - 1) * 100, 1)
        out.append({
            "name": c["name"], "agency_id": c["agency_id"],
            "segment": segment, "first_year": c["first_year"],
            "last_year": c["last_year"], "years_active": len(c["years"]),
            "total_mw": round(c["total_mw"], 2),
            "by_year": {y: round(v, 2) for y, v in sorted(c["by_year"].items())},
            "cagr_pct": cagr, "is_almm": c["is_almm"],
        })
    return sorted(out, key=lambda x: -x["total_mw"])


companies_cell = company_master(cell_yearly, "cell")
companies_mod = company_master(mod_yearly, "module")

# ── New entrants per year per segment ─────────────────────
def new_entrants(rows):
    seen = set()
    out = {}
    by_year = defaultdict(set)
    for r in rows:
        by_year[r["year"]].add(r["company"])
    for y in sorted(by_year):
        new = by_year[y] - seen
        out[y] = {"new": len(new), "total": len(by_year[y])}
        seen |= by_year[y]
    return out


new_cell = new_entrants(cell_yearly)
new_mod = new_entrants(mod_yearly)

# ── Monthly aggregate: manufactured vs sold (All Manufacturers row only) ──
def monthly_agg(rows):
    out = []
    for r in rows:
        if r["company"] == "All Manufacturers":
            out.append({"year": r["year"], "month": r["month"],
                        "month_name": r["month_name"], "metric": r["metric"],
                        "mw": round(r["mw"], 3)})
    return out


cell_agg_monthly = monthly_agg(cell_monthly)
mod_agg_monthly = monthly_agg(mod_monthly)

# ── 2026 projection: annualize from monthly Jan-Apr (latest non-zero months) ──
def project_2026(agg_monthly, mfg_metric):
    by_m = {}
    for r in agg_monthly:
        if r["year"] == 2026 and r["metric"] == mfg_metric:
            by_m[r["month"]] = r["mw"]
    # find non-zero months
    nz = [(m, v) for m, v in sorted(by_m.items()) if v > 0]
    if not nz:
        return None
    last_m = nz[-1][0]
    ytd = sum(v for _, v in nz)
    projected = ytd / last_m * 12 if last_m else None
    return {"ytd": round(ytd, 2), "last_month": last_m,
            "projected_full_year": round(projected, 2) if projected else None,
            "by_month": by_m}


proj_cell_mfg = project_2026(cell_agg_monthly, "cell_manufactured_mw")
proj_cell_sold = project_2026(cell_agg_monthly, "cell_sold_mw")
proj_mod_mfg = project_2026(mod_agg_monthly, "module_manufactured_mw")
proj_mod_sold = project_2026(mod_agg_monthly, "module_sold_mw")

# ── Top movers (year-over-year %, last full year vs prior) ──
def top_movers(comps, base_year, prior_year, top_n=10):
    out = []
    for c in comps:
        v1 = c["by_year"].get(base_year, 0)
        v0 = c["by_year"].get(prior_year, 0)
        if v1 == 0:
            continue
        if v0 == 0:
            growth = None  # new entrant
            delta = v1
        else:
            growth = round((v1 - v0) / v0 * 100, 1)
            delta = round(v1 - v0, 2)
        out.append({"name": c["name"], "v0": v0, "v1": v1, "delta": delta,
                    "growth_pct": growth, "is_new": v0 == 0})
    risers = sorted([x for x in out if x["growth_pct"] is not None],
                    key=lambda x: -x["growth_pct"])[:top_n]
    new_entries = sorted([x for x in out if x["is_new"]],
                         key=lambda x: -x["v1"])[:top_n]
    fallers = sorted([x for x in out if x["growth_pct"] is not None],
                     key=lambda x: x["growth_pct"])[:top_n]
    return {"risers": risers, "new_entries": new_entries, "fallers": fallers}


movers_cell = top_movers(companies_cell, 2025, 2024)
movers_mod = top_movers(companies_mod, 2025, 2024)

# ── Share of segment and share of total DCR per company per year ──
def share_of_segment(comps, yt):
    """Returns {company: {year: share_pct}}"""
    out = {}
    for c in comps:
        out[c["name"]] = {}
        for y, mw in c["by_year"].items():
            tot = yt.get(y, 0)
            out[c["name"]][y] = round(mw / tot * 100, 2) if tot else 0
    return out


share_seg_cell = share_of_segment(companies_cell, yt_cell)
share_seg_mod = share_of_segment(companies_mod, yt_mod)

# Total DCR output per year (cell + module combined, summing all-manufacturer rows)
yt_total = {y: round((yt_cell.get(y, 0) + yt_mod.get(y, 0)), 2) for y in sorted(set(list(yt_cell)+list(yt_mod)))}

# Build per-company total (cell+module) per year then compute share-of-DCR
company_total_by_year = defaultdict(lambda: defaultdict(float))
company_segments_seen = defaultdict(set)
for c in companies_cell:
    for y, v in c["by_year"].items():
        company_total_by_year[c["name"]][y] += v
        company_segments_seen[c["name"]].add("cell")
for c in companies_mod:
    for y, v in c["by_year"].items():
        company_total_by_year[c["name"]][y] += v
        company_segments_seen[c["name"]].add("module")

share_dcr = {}
for co, yrs in company_total_by_year.items():
    share_dcr[co] = {y: round(v / yt_total[y] * 100, 2) if yt_total.get(y) else 0 for y, v in yrs.items()}

# Cell-vs-module split per company per year (only dual-segment players)
dual_segment_split = {}
for co, segs in company_segments_seen.items():
    if len(segs) >= 2:
        c_byyr = {y: 0 for y in [2022,2023,2024,2025,2026]}
        m_byyr = {y: 0 for y in [2022,2023,2024,2025,2026]}
        for c in companies_cell:
            if c["name"] == co:
                for y, v in c["by_year"].items(): c_byyr[y] = v
        for c in companies_mod:
            if c["name"] == co:
                for y, v in c["by_year"].items(): m_byyr[y] = v
        dual_segment_split[co] = {"cell": c_byyr, "module": m_byyr,
                                  "total": {y: round(c_byyr[y]+m_byyr[y], 2) for y in c_byyr}}

# ── Per-company 24-month monthly series (2025-Jan through 2026-May), top by 2025 ──
def monthly_series(rows, mfg_metric):
    """Return {company: [{ym, mw}...]} where ym is 'YYYY-MM'."""
    out = defaultdict(dict)
    for r in rows:
        if r["metric"] == mfg_metric and r["company"] != "All Manufacturers":
            ym = f"{r['year']}-{r['month']:02d}"
            out[r["company"]][ym] = r["mw"]
    # Fill missing months with 0 across full range
    months = [f"{y}-{m:02d}" for y in [2022,2023,2024,2025,2026] for m in range(1,13)]
    final = {}
    for co, m in out.items():
        final[co] = [{"ym": k, "mw": round(m.get(k, 0), 3)} for k in months]
    return final


monthly_per_co_cell = monthly_series(cell_monthly, "cell_manufactured_mw")
monthly_per_co_mod = monthly_series(mod_monthly, "module_manufactured_mw")

# Monthly share oscillation: each month, what % of segment total does each top company represent
def monthly_share(monthly_per_co, agg_monthly, mfg_metric):
    """Build {company: [{ym, share_pct}...]} normalized per-month."""
    agg_by_ym = {}
    for r in agg_monthly:
        if r["metric"] == mfg_metric:
            agg_by_ym[f"{r['year']}-{r['month']:02d}"] = r["mw"]
    out = {}
    for co, series in monthly_per_co.items():
        out[co] = []
        for pt in series:
            tot = agg_by_ym.get(pt["ym"], 0)
            out[co].append({"ym": pt["ym"], "share": round((pt["mw"] / tot * 100) if tot else 0, 2)})
    return out


monthly_share_cell = monthly_share(monthly_per_co_cell, cell_agg_monthly, "cell_manufactured_mw")
monthly_share_mod = monthly_share(monthly_per_co_mod, mod_agg_monthly, "module_manufactured_mw")

# ── Final bundle ──────────────────────────────────────────
bundle = {
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "source": "https://solardcrportal.nise.res.in/Summary/index",
    "totals": totals,
    "stockTotals": stockTotals,
    "states": states,
    "cellYearly": cell_yearly,
    "moduleYearly": mod_yearly,
    "cellMonthlyAgg": cell_agg_monthly,
    "moduleMonthlyAgg": mod_agg_monthly,
    "cellMonthly": cell_monthly,
    "moduleMonthly": mod_monthly,
    "derived": {
        "yearlyTotalsCell": yt_cell,
        "yearlyTotalsModule": yt_mod,
        "hhiCell": hhi_cell,
        "hhiModule": hhi_mod,
        "activeCell": active_cell,
        "activeModule": active_mod,
        "companiesCell": companies_cell,
        "companiesModule": companies_mod,
        "newEntrantsCell": new_cell,
        "newEntrantsModule": new_mod,
        "projection2026": {
            "cell_mfg": proj_cell_mfg, "cell_sold": proj_cell_sold,
            "module_mfg": proj_mod_mfg, "module_sold": proj_mod_sold,
        },
        "moversCell": movers_cell,
        "moversModule": movers_mod,
        "shareSegCell": share_seg_cell,
        "shareSegModule": share_seg_mod,
        "shareDCR": share_dcr,
        "dualSegmentSplit": dual_segment_split,
        "monthlyPerCoCell": monthly_per_co_cell,
        "monthlyPerCoModule": monthly_per_co_mod,
        "monthlyShareCell": monthly_share_cell,
        "monthlyShareModule": monthly_share_mod,
        "yearlyTotalDCR": yt_total,
    },
}

out_path = os.path.join(BASE, "dashboard_data.json")
tmp_path = out_path + ".tmp"
with open(tmp_path, "w") as fp:
    json.dump(bundle, fp, separators=(",", ":"))
os.replace(tmp_path, out_path)
print(f"Wrote {out_path} ({os.path.getsize(out_path):,} bytes)")
print("KPIs:", totals)
print("Yearly cell totals:", yt_cell)
print("Yearly module totals:", yt_mod)
print("HHI cell:", hhi_cell)
print("HHI module:", hhi_mod)
print("Active cell:", active_cell)
print("Active mod:", active_mod)
print("Cell companies:", len(companies_cell))
print("Module companies:", len(companies_mod))
print("States after merge:", len(states))
print("2026 cell projection:", proj_cell_mfg)
print("2026 mod projection:", proj_mod_mfg)
