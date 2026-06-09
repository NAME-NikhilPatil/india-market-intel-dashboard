# VAHAN Dashboard Session Notes

## Project location

`/Users/rajagrawal/Library/CloudStorage/OneDrive-CHEMNINELLP/Temp9/vahan_dashboard_project`

Open the dashboard with: `vahan_dashboard_v9.html` (latest).

## Versions in this folder

| File | What it is |
|---|---|
| `index.html` | Original v1 — initial build with editorial layout (untouched, kept for reference). |
| `vahan_2yr_dashboard.html` | Duplicate of original v1. |
| `vahan_dashboard_v2.html` | First rebuild. FT-style editorial layout: masthead, KPI strip, narrative sections, methodology footer. Self-contained HTML. |
| `vahan_dashboard_v3.html` | Sidebar + canvas redesign. Stripped editorial copy. Reactive filter system. Year drill panels. Per-maker drawer. Maker compare. Movers tables. Quadrant. Cohort lens. EV stairway. |
| `vahan_dashboard_v4.html` | Year range slider replacing year dropdown. Maker focus panel. 6-button cross-cut toggles (All / 2W / 4W / 2W-EV / 4W-EV / EV-all). Auto-insights bar. Quadrant scatterplot, fuel YoY heatmap, cohort lens, EV adoption stairway. |
| `vahan_dashboard_v5.html` | Fixed 2026 monthly aggregation bug (Diesel/Hybrid showing 0%). Three seasonality heatmaps unified to identical grid template. Heatmaps respond to maker focus. |
| `vahan_dashboard_v6.html` | Deleted Cohort Lens, Movers, Quadrant sections per request. Removed YTD growth comparison KPI. Sidebar Cat filter now drives every chart in maker league + density (per-chart Cat toggles removed). Added Top 5 + Others stacked chart with absolute / share toggle. |
| `vahan_dashboard_v7.html` | Trends and seasonality heatmaps fully respond to Cat filter (using per-category monthly source rows). Maker focus also drives trend chart, fuel stream, EV pen chart. Compare section gained a per-row red→green heatmap table with two toggle pairs: Yearly / Last-12-months and Actual / % share. |
| `vahan_dashboard_v8.html` | Ingests actual monthly data into every affected view. (1) `monthly_fuel_mix_by_cat` and `monthly_ev_pen_by_cat` now use the real 2W/4W split derived from the classified file (no longer mirror the all-category figures). (2) Per-maker monthly views (drawer, maker focus) use the actual all-state Maker × Fuel × Month scrape. The drawer always renders from all-state regardless of the active 2W/4W filter, so individual maker views are never undercounted. (3) Maker-focus seasonality heatmaps (registrations, EV share, fuel share) now compute month-to-month from actual data instead of replicating annual share across months — visible as genuine within-year variation (e.g., Bajaj Group EV share: 3.8% Apr 2024 → 13.2% Sep 2024 → 19.4% Mar 2025). (4) Compare heatmap monthly grain reads actual monthly maker × cat/fuel data. (5) `monthly_maker_by_cat` rebuilt from the all-state and classified files because the per-category maker-month CSV was missing Bajaj for 2021–2025 (see data-quality note below). (6) The 2026 ≈2× inflation that affected v7 is gone — the new scrape route does not exhibit it. (7) New "Monthly granularity" section adds three charts unlocked by the new data: EV adoption timing (month each maker crossed 1k/10k/100k/500k EV thresholds), monthly rank evolution per category, per-maker monthly fuel-mix stacked-area grid (top 24 tracked makers). (8) Methodology block rewritten; all residual "estimated" labels removed. Payload grew from 660 KB → 1.88 MB; final HTML 0.84 MB → 2.08 MB. |

## How v8 is structured

v8 keeps v7's sidebar + canvas layout and adds a "Monthly granularity" section between the EV-stairway and Compare sections. The methodology block and version pill reflect the data-source upgrade. The per-maker drawer gained two new panels: actual monthly registrations and actual monthly fuel mix (both all-state).

## v9 — actual VAHAN categories, no more 2W/4W classifier

| Change | Detail |
|---|---|
| **Source of truth for categories** | `all_state_maker_category_month_long.csv` (refreshed) — actual per-maker × per-month × per-VAHAN-category. 17 VAHAN codes mapped to 4 buckets. |
| **Bucket convention** | `2W` = 2WIC + 2WN + 2WT · `3W` = 3WIC + 3WN + 3WT · `4W` = 4WIC + LMV + LPV + MPV + HPV · `CV` = LGV + MGV + HGV + HMV + MMV + OTH |
| **Sidebar cat toggle** | Now 5 buttons: `All · 2W · 3W · 4W · CV` |
| **Maker × cat is exact** | M&M shows 2W=7, 3W=77K, 4W=712K, CV=276K in 2024 — no more dominant-classifier lumping. Bajaj shows 2W=2.29M + 3W=475K + 4W=405 + CV=63. |
| **Cross-product limitation** | Maker × cat × fuel × month is NOT in source. Charts that combine cat=3W or cat=CV with a specific fuel show an override pill ("cross-product not in source"). 2W and 4W × fuel still works from the annual cross-product table. |
| **New chart** | "Maker category mix" section — horizontal stacked bars showing each top maker's split across 2W/3W/4W/CV. Showcases the actual category split as a first-class view. |
| **Classifier retired** | `monthly_maker_fuel_2w4w_actual_classified.csv`, `monthly_maker_fuel_2w4w_classification_excluded.csv`, and `scripts/classify_all_state_maker_fuel_month.py` removed. |
| **Ather May 2023 gap closed** | Re-scraped cell now in source: 16,411 EVs. |
| **Payload size** | 660 KB (v7) → 1.88 MB (v8) → 2.82 MB (v9). Final HTML 3.04 MB. |

Spot checks (verified with JSDOM):
- **Cat=3W top makers**: Bajaj (59%) · Mahindra (12%) · Piaggio (11%) · TVS (6%) — matches real Indian 3W market.
- **Cat=CV top makers**: Mahindra (31%) · Tata (31%) · Ashok Leyland (17%) · Eicher/VECV (7%) — matches Indian CV market.
- **Cat=3W + Fuel=EV**: trend chart shows override pill "No per-cat monthly fuel data for 3W in source."
- **M&M focused on 4W**: time-series re-scopes to M&M's 4W operations only.

## Universal filter cascade (added this session)

In v8.0 only 3 of 23 charts honored the year-range slider, 10 of 23 honored the cat filter, and 2 of 23 honored the fuel filter. Selecting a filter often felt decorative because most of the canvas continued to show the unfiltered view.

v8.1 routes every chart through a **scope helper layer** (`scopedYears`, `scopedFullYears`, `scopedMonths`, `scopedAnnualByYear`, `scopedAnnualForYear`, `scopedAggregateMakerTotal`, `scopedRankBump`, `scopedMonthlyMix`, `scopedMonthlyEvPen`, `focusOpacity`, `overridePill`). Filter cascade after the refactor:

- **Year range** — applies to every time-series chart (trims months/years) and every annual chart (recomputes rankings within the range). Charts that need ≥2 years (bump, slope, top5+Others, concentration) show a small "override" pill if the range collapses too far.
- **Cat (2W/4W)** — cascades to 17 of 19 main charts. Now visible on: bump, slope, treemap, density heatmap, small multiples, EV milestones monthly, rank monthly, sparkgrid. The remaining two (EV stairway, fuel YoY heatmap) read pre-aggregated payload structures that don't have a cat split.
- **Fuel** — cascades to ~11 charts. EV gets first-class support via `by_year_maker_ev`; specific non-EV fuels (Petrol/Diesel/Hybrid/Others) are derived on the fly from `monthly_maker_fuel(_by_cat)`. Trend chart, seasonality registrations heatmap, and monthly rank chart all re-scope to the selected fuel.
- **Maker focus** — time-series charts re-scope to that maker (existing v8 behaviour). Ranking/treemap/density/EV stairway/sparkgrid now **highlight** the focused maker (dim others to ~18% opacity, bold/outline the focused one) instead of hiding context.

UI affordances added:
- The scope bar is now sticky and pills with non-default values are inked (active state).
- `overridePill` helper inserts a small red-tinted note inside any chart that can't honor part of the current scope.
- The fuel mix streamgraph is **hidden** with an override pill when a specific fuel is selected (single-fuel stream is redundant).

## Scrape gaps found (logged this session)

The all-state Maker × Fuel × Month scrape dropped a handful of (maker, month) cells silently. These cells exist in the v7 annual scrape but are missing from the monthly file. Detected by `scripts/rescrape_missing_cells.py --dry-run`:

| Raw maker | Year | Month | Implied vol |
|---|---|---|---|
| ATHER ENERGY LTD | 2023 | 2023-05 | 16,096 EVs |
| GOREEN E-MOBILITY PVT LTD | 2022 | 2022-04 | ~613 |
| RENAULT INDIA PVT LTD | 2021 | 2021-04 | (small) |
| ROYAL-ENFIELD (UNIT OF EICHER LTD) | 2021 | 2021-04 | (small) |
| RENAULT NISSAN AUTOMOTIVE INDIA PRIVATE LIMITED | 2021 | 2021-04 | (small) |

The Ather May 2023 gap is the most visible: April 2023 = 8,335 → May 2023 = MISSING → June 2023 = 4,861. The implied 16,096 fits the FAME-II pre-buy story (subsidy cut effective June 1, 2023).

**Fix path:** `scripts/rescrape_missing_cells.py` audits the existing scrape against v7 annual totals, drives Selenium with the existing Harvester to re-scrape only the missing (year, month) selectors, merges the new rows into `all_state_maker_fuel_month.json` without disturbing existing data, re-flattens the long CSV, and re-runs the classifier. Usage:

```bash
# Audit (no scrape)
python3 scripts/rescrape_missing_cells.py --dry-run

# Re-scrape every audited gap
python3 scripts/rescrape_missing_cells.py

# Re-scrape specific cells only
python3 scripts/rescrape_missing_cells.py --targets "ATHER ENERGY LTD@2023-05"
```

After re-scrape, the v8 payload would need to be rebuilt (see "How to rebuild" section). The dashboard's affected views: monthly trend (Ather focus shows the May 2023 dip), seasonality heatmap, fuel mix stream (April→June 2023 cells), and the per-maker drawer monthly chart for Ather.

## Missing-data repair pass (2026-05-15)

The missing-data repair has now been executed.

First pass: `scripts/rescrape_missing_cells.py`

- Re-scraped the 5 previously audited all-state `Maker × Fuel × Month` gaps.
- Backfilled:
  - `ATHER ENERGY LTD` @ `2023-05`
  - `GOREEN E-MOBILITY PVT LTD` @ `2022-04`
  - `RENAULT INDIA PVT LTD` @ `2021-04`
  - `ROYAL-ENFIELD (UNIT OF EICHER LTD)` @ `2021-04`
  - `RENAULT NISSAN AUTOMOTIVE INDIA PRIVATE LIMITED` @ `2021-04`
- Re-flattened `all_state_maker_fuel_month_long.csv`.
- Re-ran `classify_all_state_maker_fuel_month.py`.
- Verification: `scripts/rescrape_missing_cells.py --dry-run` now reports `Audited gaps: 0`.

Second pass: `scripts/repair_cross_matrix_missing.py`

- Compared actual all-state monthly `Maker × Fuel` and `Maker × Vehicle Category` matrices at maker-month level.
- Re-scraped missing whole maker-month rows where one actual matrix had positive volume and the other had zero.
- Backfilled 74 category-side maker-month rows. Important recovered rows include:
  - `HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD` @ `2025-11`
  - `HYUNDAI MOTOR INDIA LTD` @ `2025-11`
  - `HONDA CARS INDIA LTD` @ `2025-11`
- Backfilled 240 fuel-side maker-month rows. Important recovered rows include:
  - `ASHOK LEYLAND LTD` @ `2023-05`
  - `ATUL AUTO LTD` @ `2023-05`
  - `G.K. RICKSHAW LTD` @ `2023-02` and `2022-04`
- Re-flattened:
  - `all_state_maker_fuel_month_long.csv` → 79,794 rows
  - `all_state_maker_category_month_long.csv` → 89,956 rows
  - `monthly_maker_fuel_2w4w_actual_classified.csv` → 23,574 rows
- Remaining unresolved cross-matrix zero-side gap:
  - `ESCORTS TRACTORS LTD` @ `2021-08`, category-side volume 1. This row did not appear when the live category page was re-scraped, so it was not fabricated.

Spot checks after repair:

- `ATHER ENERGY LTD` 2023 now has all 12 months in fuel, classified fuel, and category files. 2023 total is 111,806 in the repaired all-state monthly files.
- `HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD` @ `2025-11`: fuel 639,863; category 639,865.
- `HYUNDAI MOTOR INDIA LTD` @ `2025-11`: fuel 52,714; category 52,714.
- `ASHOK LEYLAND LTD` @ `2023-05`: fuel 15,377; category 15,377.

## State x Maker x Fuel monthly scrape (started 2026-05-15)

Feasibility result: exact `State x Maker x Fuel x Month` is possible from VAHAN.

Method:

- Use VAHAN global State dropdown.
- Set Y-Axis = `Maker`.
- Set X-Axis = `Fuel`.
- Set Year Type = `Calendar Year`.
- Use the table-level month selector.

Validation probe:

- State dropdown = `KA`
- Month = `2026-03`
- VAHAN title changed to `Maker Wise Fuel Data of Karnataka (MAR,2026)`.
- State-filtered `Maker x Fuel` total = 202,165.
- Independent all-state `State x Fuel` row for `KARNATAKA` = 202,165.
- EV total matched as 29,565.

New scraper:

- `scripts/scrape_vahan_state_maker_fuel_monthly.py`

Design:

- raw partition per state-month: `state_maker_fuel_month_raw/{STATE_CODE}/{YYYY-MM}.json`
- compiled long CSV: `state_maker_fuel_month_long.csv`
- state manifest: `vahan_states.json`
- resume-safe: skips existing raw partitions unless `--overwrite` is passed
- compiles the long CSV after each state/year block

Initial starter batch completed:

- States: `DL`, `GJ`, `KA`, `MH`, `TG`, `TN`
- Months: 2026 Jan-May
- Raw files: 30
- Long rows: 8,122

YTD totals from starter batch:

| State | 2026 Jan-May total | EV total | EV % |
|---|---:|---:|---:|
| Maharashtra | 1,348,058 | 123,743 | 9.18% |
| Tamil Nadu | 1,017,974 | 95,077 | 9.34% |
| Karnataka | 817,281 | 100,423 | 12.29% |
| Gujarat | 809,171 | 39,239 | 4.85% |
| Delhi | 312,940 | 32,333 | 10.33% |
| Telangana | 293,886 | 30,996 | 10.55% |

Notable Karnataka March 2026 EV maker leaders from the pilot:

- Ather Energy: 7,155 EV registrations
- TVS Motor: 6,388
- Bajaj Auto: 3,159
- Hero MotoCorp: 2,584
- Tata Passenger Electric Mobility: 1,276
- JSW MG Motor: 1,179
- River Mobility: 1,089
- Ola Electric: 692

Useful commands:

```bash
# list state codes
../.venv-vahan/bin/python3 scripts/scrape_vahan_state_maker_fuel_monthly.py --list-states

# scrape a pilot
../.venv-vahan/bin/python3 scripts/scrape_vahan_state_maker_fuel_monthly.py --states KA --years 2026 --months 2026-03

# compile existing raw partitions only
../.venv-vahan/bin/python3 scripts/scrape_vahan_state_maker_fuel_monthly.py --compile-only

# continue all-state/all-year scrape; will skip existing raw files
../.venv-vahan/bin/python3 scripts/scrape_vahan_state_maker_fuel_monthly.py --years 2021 2022 2023 2024 2025 2026
```

## Data-quality finding (logged this session)

`data/vahan_2021_2026_calendar/monthly_maker_vehicle_category_long.csv` (the maker × category × month long table) is missing **Bajaj Auto entirely for 2021–2025**. Bajaj only appears in 2026 there. As a result the file's 2024 total is ~20.7 M vs. the ~23.5 M expected when Bajaj is included.

v8's `monthly_maker_by_cat` was therefore rebuilt from the more complete sources:

- `monthly_maker_by_cat['all']` ← all-state Maker × Fuel × Month, summed across fuels.
- `monthly_maker_by_cat['2W']` and `['4W']` ← classified Maker × Fuel × Month (dominant-category split).

If the per-category maker-month scrape gets re-run later, the easiest fix is to overwrite the broken CSV and rebuild — but until then v8 already paints from the all-state route.

## 2026 audit (verified on v8 payload)

| | 2025 | 2026 YTD (Jan–May) | Annualised 2026 ÷ 2025 |
|---|---|---|---|
| v7 monthly_fuel_mix | 28.58 M | 19.61 M | **1.647** ← inflated |
| v8 monthly_fuel_mix | 29.28 M | 11.75 M | **0.963** ← clean |

The new scrape route (per-maker × month + all-state maker × fuel × month) does not exhibit the v7 2026 inflation. 2W share of 2025 = 77.9%, 4W = 22.1% (vs. v7's broken state where 2W and 4W reported identical figures for 2021–2025).

## How v7 is structured

**Sidebar (left, 252px wide)** — single source of truth for filters:
- Year range slider (dual-handle, 2021–2026)
- Vehicle category (All / 2W / 4W)
- Fuel group (All / EV / Petrol / Diesel / Hybrid / Others)
- Maker search (free text; if it uniquely matches a normalised maker, the Maker Focus panel materialises)
- Reset filters
- Compare makers picker (chips + dropdown, max 5)
- Section nav (jump links)
- Collapsible methodology block

**Canvas (right) — sections from top to bottom**:
1. Auto-insights bar (horizontal scroll cards) + scope summary pill bar
2. **Maker focus panel** — appears only when one maker uniquely matches the search; shows annual registrations, fuel mix evolution, rank history, closest peers by fuel-mix profile, plus auto-generated badges (EV-pure / Fast climber / Declining / etc.)
3. **Overview** — 6 KPI tiles (registrations in scope, EV mix, distinct makers, top maker, top EV maker, latest full year)
4. **Trends** — monthly registrations + 12-mo rolling avg, annual EV penetration line, monthly fuel-mix streamgraph, top makers bar
5. **Selected year drill** — appears only when a single year is selected (yearMin == yearMax); monthly registrations, monthly fuel mix, monthly EV pen, top makers in chosen year
6. **Seasonality** — three uniform year×month heatmaps (registrations, EV penetration, per-fuel share) all stacked at full width with identical grid template (64px label + 12 equal columns)
7. **Fuel dynamics** — fuel × year YoY growth heatmap (5 fuels × 6 years)
8. **Maker league** — Top 5 + Others share chart (toggle abs / share), bump chart (rank evolution), slope graph (2021→2025 share shift), market share treemap, Top-N concentration trend
9. **Density grids** — top 20 maker × year heatmap (Registrations / YoY% / EV-share-within metrics), small multiples wall (24 tiles, shared/own y toggle)
10. **EV adoption stairway** — top 15 EV makers × 6 years grid colored by milestone tiers (1k / 10k / 100k / 500k EVs)
11. **Compare** — appears once you add ≥1 maker; contains the new red→green heatmap table (Yearly/Monthly + Actual/Share toggles), annual trajectory overlay, EV share overlay, side-by-side metrics table
12. **Detail rows** — full filtered raw table, sortable, clickable rows open the maker drawer
13. **Per-maker drawer** — slides in from right when any maker name is clicked anywhere on the page (KPI sub, top makers bar, treemap, heatmap row label, table row, compare table, etc.)

## Design decisions locked in across the conversation

- **Visual style**: FT cream / salmon (`#fff1e5`) palette, serif headlines, sans body, monospace numerics. Tightened spacing for analyst density.
- **Layout**: Sidebar + canvas (no editorial masthead since v3).
- **Hero angle**: Comprehensive multi-angle dashboard, no single story leading.
- **Format**: Reactive sidebar drives everything; per-chart toggles only kept where they add a meaningfully orthogonal axis (chart-specific metric toggles, not Cat).
- **Year filter**: Dual-handle range slider, not single-year dropdown.
- **Maker focus**: When search uniquely matches one maker, a focus panel appears at the top + the trend chart, EV pen chart, fuel stream, and seasonality heatmaps all re-scope to that maker.
- **Cat filter centrality**: Sidebar Cat (2W / 4W) drives bump, slope, treemap, density heatmap, small multiples, top 5+Others, and the seasonality heatmaps.
- **No editorial prose** in v3+. Methodology lives in the sidebar's collapsible block and a tooltip-style note where relevant.
- **No growth math attached to YTD** — the 2026 YTD KPI shows the absolute total, not a YoY comparison (because the comparison is unreliable due to the 2026 source-data behavior change).

## Pipeline added in this session

```
data/vahan_2021_2026_calendar/*.csv  (existing scrape)
        ↓
outputs/build_payload.py             (Python; reads CSVs, applies maker
                                      normalisation, computes all the
                                      pre-aggregations the dashboard needs)
        ↓
outputs/payload.json                 (~580 KB single JSON blob)
        ↓
outputs/build_dashboard.py           (assembles dashboard.css + dashboard.body.html
                                      + dashboard.js + payload.json into one file)
        ↓
vahan_dashboard_v7.html              (single-file ~820 KB, self-contained)
```

The intermediate source files live in the agent scratch directory; only the
final HTML is written into this project folder.

## Current Data Understanding

Yes, we now have both major monthly data layers needed for the future HTML:

1. **Monthly maker data by 2W/4W** is available as actual VAHAN data in `monthly_maker_vehicle_category_long.csv`.
2. **Monthly maker × fuel data** is available as actual VAHAN all-state/all-category data in `all_state_maker_fuel_month_long.csv`.
3. **Monthly maker × vehicle-category data** is available as actual VAHAN all-state/all-category data in `all_state_maker_category_month_long.csv`.
4. **Monthly maker × fuel with 2W/4W labels** is available in `monthly_maker_fuel_2w4w_actual_classified.csv`, but the 2W/4W value is a dominant-maker classification from annual maker-category reference data. It is not a direct VAHAN monthly category split and it does not allocate/split maker volumes.

Use the classified file for practical 2W/4W dashboard views, and use `monthly_maker_fuel_2w4w_classification_excluded.csv` to see what was left out.

## Latest scrape: all-state Maker x Vehicle Category x Month

User asked to scrape the VAHAN screen with:

- Y-Axis: Maker
- X-Axis: Vehicle Category
- Year Type: Calendar Year
- Table-level month selector

Added scraper:

- `scripts/scrape_vahan_all_state_maker_category_monthly.py`

Outputs:

- `data/vahan_2021_2026_calendar/all_state_maker_category_month.json`
- `data/vahan_2021_2026_calendar/all_state_maker_category_month_long.csv`

Final validation after the 2023 gap was re-run:

| Year | Months covered | Long rows | Maker count range per month |
|---|---:|---:|---:|
| 2021 | 12 | 15,494 | 530-996 |
| 2022 | 12 | 15,737 | 860-982 |
| 2023 | 12 | 15,688 | 896-1,010 |
| 2024 | 12 | 16,438 | 981-1,081 |
| 2025 | 12 | 18,448 | 1,115-1,298 |
| 2026 | 5, Jan-May | 8,037 | 990-1,334 |

Total long rows: 89,842. Total registrations represented: 134,845,111.

Vehicle-category codes present: `2WIC`, `2WN`, `2WT`, `3WIC`, `3WN`, `3WT`, `4WIC`, `HGV`, `HMV`, `HPV`, `LGV`, `LMV`, `LPV`, `MGV`, `MMV`, `MPV`, `OTH`.

Spot checks confirm the important makers are present in March 2026:

- `ATHER ENERGY LTD`: `2WN` = 36,278; monthly maker total = 36,278.
- `BAJAJ AUTO LTD`: `2WN` = 225,564; `2WT` = 26; `3WN` = 55; `3WT` = 43,631; monthly maker total = 269,279.
- `MARUTI SUZUKI INDIA LTD`: `LMV` = 153,432; `LPV` = 25,024; `LGV` = 4,084; monthly maker total = 182,640.
- `MAHINDRA & MAHINDRA LIMITED`: `LMV` = 59,674; `LGV` = 24,711; monthly maker total = 88,134.
- `TATA MOTORS LTD`: `HGV` = 16,285; `LGV` = 15,743; monthly maker total = 39,188.

This is actual granular VAHAN category data. It has not been mapped into custom 2W/4W buckets yet. If the dashboard needs a collapsed `vehicle_group`, do it later as a documented deterministic aggregation from these raw category codes, not as an estimate.

## Data caveats found in this session

1. **VAHAN's Month Wise filter was broken for 2021–2025**: The `vehicle_category=2W` and `vehicle_category=4W` source rows in `monthly_fuel_vehicle_category_long.csv` show *identical* numbers per month for those years — they both contain the all-category figure. Per-category monthly data does not exist for 2021–2025.

2. **VAHAN fixed it for 2026**: For 2026 months, the 2W rows and 4W rows are genuinely independent (they sum to all-category). This is a real source-data behavior change.

3. **Total inflation in 2026**: After the existing pipeline's dedupe heuristic, the all-category 2026 monthly totals are ~2× higher than 2025 (e.g., Jan 2026 = 4.68M vs Jan 2025 = 2.34M). This is too high for India's actual auto market and reflects the source change, not real growth. The dashboard surfaces this in the methodology footer.

4. **Per-maker monthly data is now available**: `maker_month` was scraped for 2W and 4W, calendar years 2021–2026. New raw files are `2w_maker_month.{json,csv}` and `4w_maker_month.{json,csv}`. The clean long file is `monthly_maker_vehicle_category_long.csv`.

5. **All-state monthly Maker × Fuel is now available**: The all-state `Maker × Fuel` table-level month selector was scraped for 2021–2026. Raw file: `all_state_maker_fuel_month.json`. Clean long file: `all_state_maker_fuel_month_long.csv`. This is actual monthly maker-fuel data with no estimates.

6. **2W/4W monthly maker-fuel classification is available, but it is classification, not a true category split**: `monthly_maker_fuel_2w4w_actual_classified.csv` starts from the all-state actual monthly maker-fuel file and assigns the whole maker to 2W or 4W when the annual maker-category reference data has a dominant category of at least 95%. Excluded/unmatched makers are in `monthly_maker_fuel_2w4w_classification_excluded.csv`.

7. **Fuel grouping has been revised to the user's requested buckets**: EV, Hybrid, Petrol, Diesel, Others. Hybrid is checked before EV, so `PLUG-IN HYBRID EV`, `STRONG HYBRID EV`, `PETROL/HYBRID`, and similar rows land in Hybrid rather than EV. Pure battery/electric/BOV and fuel-cell rows land in EV.

8. **All-state monthly Maker × Vehicle Category is now available**: The all-state `Maker × Vehicle Category` table-level month selector was scraped for 2021-2025 full years and 2026 Jan-May. Raw file: `all_state_maker_category_month.json`. Clean long file: `all_state_maker_category_month_long.csv`. This is actual monthly maker-category data with no estimates.

## Pending work

(Top priority from previous sessions — ingesting the new CSVs — was completed in this session and is reflected in `vahan_dashboard_v8.html`.)

Open items that could be picked up in a future pass:

1. **Excluded-makers transparency UI**: v8 stashes the excluded list in `payload.classification_excluded` (2,461 makers, 6.7 M registrations) but doesn't surface it visually. A small badge near the Cat filter showing "N makers / X% volume excluded — see methodology" would close the loop on the v8 design decision.
2. **Maker rank monthly cat-toggle**: the new chart shows the current STATE.cat but currently re-renders only on full filter changes. A small in-panel cat toggle (All / 2W / 4W) would let the user compare without switching the global filter.
3. **Year range filter on the new charts**: the three new charts in `sec-monthlyGran` always show the full 2021→2026 timeline. Wiring them to the year-range slider would make them consistent with the rest of the dashboard.
4. **EV-milestone monthly bar timeline as an alternative view**: the current dot-and-track design works for top 18 but a small-multiples version showing the cumulative EV curve per maker could be a complement.
5. **Annual maker-fuel scrape refresh**: `fuel_maker_vehicle_category_long.csv` is the source for `payload.rows` (annual). It hasn't been re-scraped this session — refreshing once 2026 closes would keep the annual aggregates in sync with the monthly ones.

## State x Maker x Fuel scrape status

Started building the exact monthly `State x Maker x Fuel` dataset from VAHAN using the global State dropdown plus `Y-Axis=Maker`, `X-Axis=Fuel`, `Year Type=Calendar Year`, and the table month selector. This is exact source data, not estimated.

Current scraper:
- `scripts/scrape_vahan_state_maker_fuel_monthly.py`
- Raw partition output: `data/vahan_2021_2026_calendar/state_maker_fuel_month_raw/{STATE_CODE}/{YYYY-MM}.json`
- Long CSV output: `data/vahan_2021_2026_calendar/state_maker_fuel_month_long.csv`
- Failure log: `data/vahan_2021_2026_calendar/state_maker_fuel_month_failures.jsonl`

Important scraper behavior:
- Resume-safe at month level. Before opening VAHAN, it checks raw files and skips completed state-years.
- Partially complete state-years resume only missing months.
- CSV compilation is throttled via `--compile-every` instead of recompiling after every state-year.
- A circuit breaker `--max-consecutive-failures` stops the run when VAHAN is unstable instead of burning hours.
- The earlier aggressive timeout settings were too short. AP 2023 failed with 35-40 second waits but completed with patient `--wait-seconds 90 --page-timeout 90`. Keep patient waits for full scrape.

Progress as of May 15, 2026:
- 140 raw state-month files captured.
- `AN` is complete for 2021-2026.
- `AP` has 45 of 65 expected month files; AP 2023 is now fixed and complete. Remaining AP gaps are 2024 Oct-Dec, all 2025, and 2026 Jan-May.
- Initial partial 2026 Jan-May files exist for `DL`, `GJ`, `KA`, `MH`, `TG`, and `TN` from the earlier starter batch.
- `state_maker_fuel_month_long.csv` has been rebuilt from raw files after AP 2023 and contains 16,581 rows.

Parallel scrape update:
- Three detached `screen` workers are running:
  - `vahan_state_scrape`: full ordered run from the beginning; uses resume checks, so completed state-years are skipped.
  - `vahan_state_scrape_2`: later-state worker for `KA KL LA LD MH ML MN MP MZ NL OR PB PY RJ SK TG TN TR UK UP WB`.
  - `vahan_state_scrape_3`: targeted tail/heavy-state worker for `UP WB RJ OR PB`.
- Logs:
  - `logs/state_maker_fuel_full_scrape.log`
  - `logs/state_maker_fuel_full_scrape_worker2.log`
- `logs/state_maker_fuel_full_scrape_worker3.log`
- Worker 3 was added after the first two remained stable; do not add more unless VAHAN continues to tolerate 3 sessions.
- Latest observed status: AP completed through 2026 after one retry; worker 1 moved into AR. Worker 2 moved through KA 2022 and into KA 2023. Raw partition count reached 200.

Final scrape completion:
- The exact `State x Maker x Fuel x Month` scrape completed for all 36 VAHAN states.
- Expected raw state-month partitions: 2,340 = 36 states x (2021-2025 full years + 2026 Jan-May).
- Actual raw state-month partitions: 2,340.
- Missing raw partitions: 0.
- Bad/mismatched raw JSON metadata files: 0.
- Empty raw record files: 0.
- Final long CSV: `data/vahan_2021_2026_calendar/state_maker_fuel_month_long.csv`.
- Final CSV data rows: 381,105 (`381,106` lines including header).
- CSV covers 36 states, 65 months, and all 2,340 state-month pairs.
- CSV positive registration rows match raw positive fuel cells: 381,105.
- The old AP failure-log entries are stale historical failures from before retries/resume fixed AP; AP is complete in the final audit.

## Files in scope

**Final dashboard (workspace folder, the user can open these)**:
- `vahan_dashboard_v9.html` — current
- `vahan_dashboard_v8.html`, `v7`, `v6`, `v5`, `v4`, `v3`, `v2` — earlier versions kept for reference
- `index.html` / `vahan_2yr_dashboard.html` — original v1 (untouched)

**Source data (existing scrape)**:
- `data/vahan_2021_2026_calendar/fuel_maker_vehicle_category_long.csv` — main long table (annual maker × fuel × category)
- `data/vahan_2021_2026_calendar/all_state_maker_fuel_month_long.csv` — actual all-state monthly maker × fuel long table
- `data/vahan_2021_2026_calendar/all_state_maker_category_month_long.csv` — actual all-state monthly maker × vehicle-category long table
- `data/vahan_2021_2026_calendar/monthly_maker_fuel_2w4w_actual_classified.csv` — actual all-state monthly maker × fuel rows classified to 2W/4W by dominant maker category
- `data/vahan_2021_2026_calendar/monthly_maker_fuel_2w4w_classification_excluded.csv` — excluded/unmatched/low-confidence makers from the classifier
- `data/vahan_2021_2026_calendar/monthly_maker_vehicle_category_long.csv` — exact monthly maker × category long table from fresh scrape
- `data/vahan_2021_2026_calendar/monthly_fuel_vehicle_category_long.csv` — monthly fuel × category (with the broken-filter caveat above)
- `data/vahan_2021_2026_calendar/monthly_ev_penetration_all_categories.csv` — pre-computed all-category monthly EV penetration
- `data/vahan_2021_2026_calendar/annual_ev_penetration_by_category.csv` — pre-computed annual EV penetration by category
- `data/vahan_2021_2026_calendar/{2w,4w}_{maker_fuel,fuel_month}.{csv,json}` — raw scrape outputs
- `data/vahan_2021_2026_calendar/all_state_maker_fuel_month.json` — raw all-state monthly maker-fuel scrape
- `data/vahan_2021_2026_calendar/all_state_maker_category_month.json` — raw all-state monthly maker-category scrape
- `data/vahan_2021_2026_calendar/{2w,4w}_maker_month.{csv,json}` — raw maker-month scrape outputs

**Existing scripts**:
- `scripts/vahan_harvest.py` — the Selenium scraper (supports `maker_month` but it was never run)
- `scripts/flatten_vahan_maker_fuel.py` — converts maker/fuel JSON to long CSV
- `scripts/flatten_vahan_monthly_fuel.py` — converts fuel/month JSON to monthly long CSV
- `scripts/build_vahan_penetration.py` — computes annual + monthly EV penetration from long tables
- `scripts/flatten_vahan_maker_month.py` — converts maker-month JSON to exact monthly maker long CSV
- `scripts/scrape_vahan_all_state_maker_fuel_monthly.py` — scrapes actual all-state monthly maker-fuel table
- `scripts/scrape_vahan_all_state_maker_category_monthly.py` — scrapes actual all-state monthly maker-vehicle-category table
- `scripts/classify_all_state_maker_fuel_month.py` — classifies all-state maker-fuel monthly rows to 2W/4W using dominant annual maker-category reference
- `scripts/scrape_vahan_maker_fuel_monthly.py` — experimental category-filtered route; all-state route above is the useful one
- `scripts/requirements-vahan.txt` — Python deps

**Build pipeline (added this session, in agent scratch — kept for the next session if needed)**:
- `outputs/build_payload.py` — pre-aggregator
- `outputs/build_dashboard.py` — single-file HTML assembler
- `outputs/dashboard.css`, `outputs/dashboard.body.html`, `outputs/dashboard.js` — the three pieces that get assembled
- `outputs/payload.json` — the embedded data payload
- `outputs/verify7.js` (and earlier verifyN.js files) — JSDOM smoke tests

## How to rebuild (if the agent rebuilds in a future session)

The `outputs/` directory above lives in agent scratch and is not persisted. If a new session needs to regenerate the dashboard, it would:

1. Re-create `build_payload.py` (or rewrite from scratch)
2. Re-create `dashboard.css`, `dashboard.body.html`, `dashboard.js`
3. Re-create `build_dashboard.py`
4. Run `python build_payload.py && python build_dashboard.py`

Or simpler: use `vahan_dashboard_v7.html` as the canonical artifact and patch it directly.

## New exact state/category scrapes started — 2026-05-15 15:55 IST

User requested two additional monthly VAHAN datasets:
- `State x Maker x Vehicle Category x Month`
- `State x Vehicle Category x Fuel x Month`

Implemented/verified generic scraper:
- `scripts/scrape_vahan_state_cross_monthly.py`
- Supports `--mode maker_category` / `--mode category_fuel` (also `--report`)
- Uses the same state dropdown + Y/X axis pattern as the completed state-maker-fuel scrape.
- Resume model: one raw JSON per state/year/month.
- Calendar window: 2021-2025 Jan-Dec, 2026 Jan-May.
- Compile outputs:
  - `data/vahan_2021_2026_calendar/state_maker_category_month_long.csv`
  - `data/vahan_2021_2026_calendar/state_category_fuel_month_long.csv`

Raw output directories:
- `data/vahan_2021_2026_calendar/state_maker_category_month_raw/{STATE}/{YYYY-MM}.json`
- `data/vahan_2021_2026_calendar/state_category_fuel_month_raw/{STATE}/{YYYY-MM}.json`

Expected raw partitions when complete:
- 2,340 for `state_maker_category_month_raw`
- 2,340 for `state_category_fuel_month_raw`

Six detached screen workers launched, three per dataset. Within each dataset, state batches are disjoint:
- Batch A: `AN AP AR AS BR CG CH DD DL GA GJ HP`
- Batch B: `HR JH JK KA KL LA LD MH ML MN MP MZ`
- Batch C: `NL OR PB PY RJ SK TG TN TR UK UP WB`

Screen workers and logs:
- `vahan_maker_cat_a` -> `logs/state_maker_category_scrape_a.log`
- `vahan_maker_cat_b` -> `logs/state_maker_category_scrape_b.log`
- `vahan_maker_cat_c` -> `logs/state_maker_category_scrape_c.log`
- `vahan_cat_fuel_a` -> `logs/state_category_fuel_scrape_a.log`
- `vahan_cat_fuel_b` -> `logs/state_category_fuel_scrape_b.log`
- `vahan_cat_fuel_c` -> `logs/state_category_fuel_scrape_c.log`

Initial launch check:
- All 6 screens were detached/running.
- First raw files had landed in both new raw folders.
- First visible states:
  - Maker/category workers: `AN`, `HR`, `NL`
  - Category/fuel workers: `AN`, `HR`, `NL`
- No failures were visible in the initial log tail.

Final completion:
- Completed at 2026-05-15 17:32 IST.
- No active `screen` workers remain.
- `State x Maker x Vehicle Category x Month`
  - Raw files: 2,340 / 2,340.
  - Missing raw partitions: 0.
  - Failure count in worker logs: 0.
  - Final CSV: `data/vahan_2021_2026_calendar/state_maker_category_month_long.csv`.
  - Final CSV rows: 398,482 data rows (`398,483` lines including header).
- `State x Vehicle Category x Fuel x Month`
  - Raw files: 2,340 / 2,340.
  - Missing raw partitions: 0.
  - Initial main pass had stale failure-log entries for `PY 2022`, `PY 2025`, `MH 2025`, and `MN 2021`.
  - Focused repair workers filled all 16 missing monthly files:
    - `MH 2025-09` to `2025-12`
    - `MN 2021-05` to `2021-12`
    - `PY 2022-12`
    - `PY 2025-10` to `2025-12`
  - Final CSV: `data/vahan_2021_2026_calendar/state_category_fuel_month_long.csv`.
  - Final CSV rows: 82,294 data rows (`82,295` lines including header).
- The category-fuel failure log still contains historical/stale failure entries from before repair; the raw audit confirms the dataset is complete after repair.

## Monthly refresh plan

Added a targeted refresh runner:
- `scripts/refresh_vahan_recent_months.py`

Purpose:
- Refresh only the current month and previous month, not the full historical scrape.
- It overwrites the raw JSON partitions for those two months and recompiles the long CSVs.
- Default datasets refreshed:
  - `state_maker_fuel`
  - `state_maker_category`
  - `state_category_fuel`

Default command from the project root:

```bash
../.venv-vahan/bin/python3 scripts/refresh_vahan_recent_months.py
```

Explicit month example:

```bash
../.venv-vahan/bin/python3 scripts/refresh_vahan_recent_months.py --months 2026-05 2026-06
```

The runner uses the same three state batches as the full scrape and writes logs like:
- `logs/refresh_state_maker_fuel_YYYY_MM_a.log`
- `logs/refresh_state_maker_category_YYYY_MM_b.log`
- `logs/refresh_state_category_fuel_YYYY_MM_c.log`

Expected monthly workload:
- 2 months x 36 states x 3 state-level datasets = 216 state-month raw partitions refreshed.
- This is much smaller than the full 7,020 state-month scrape across the three datasets.

Recommended automation:
- Run monthly after VAHAN has had time to settle for the prior month, e.g. on the 5th or 7th of each month.
- Keep the current month in the refresh set because it is partial and can change throughout the month.

## Standard data audit - 2026-05-30

The latest QA pass writes:
- `data/vahan_2021_2026_calendar/CANONICAL_DATA.md`
- `data/vahan_2021_2026_calendar/STANDARD_DATASET_MANIFEST.csv`
- `data/vahan_2021_2026_calendar/vahan_data_quality_report.md`

Current standard source decisions after targeted repair:
- Use `all_state_maker_month_long.csv` as the canonical national maker monthly/YTD table for 2026 Jan-May. It matches the VAHAN Maker x Month Wise all-state table for Ather and Ola.
- Use `state_maker_category_month_long.csv` for State x Maker x Vehicle Category. All raw titles are correct; remaining state-total variance versus category-fuel is at most 2 registrations.
- Use `state_category_fuel_month_long.csv` for State x Vehicle Category x Fuel / EV penetration. All raw titles are now correct after repairing Telangana 2023 Apr-Dec.
- Do not use `state_maker_fuel_month_long.csv` as standard yet. Audit found 157 raw partitions where VAHAN returned `Vehicle Class Wise Fuel Data` even though the file was stored as state maker fuel.

Important consistency findings:
- May 2026 is clean across the refreshed standard tables: all-state maker-month, state-maker-category, and state-category-fuel all total `2,267,511`.
- Jan-Apr 2026 mismatches between national maker-month and state-summed rows are due to freshness mismatch: national maker-month was refreshed on 2026-05-30, while state-level Jan-Apr rows are mostly from 2026-05-15.
- Targeted repairs were run for `UK 2025-10/11`, `WB 2024-02`, `MP 2024-01/02`, `RJ 2026-03`, `HP 2022-10`, and `TG 2023-04` through `2023-12`.
- Remaining state-total mismatches after repair are tiny: `MP 2024-01` is +2, and `WB 2024-02`, `MP 2024-02`, `HP 2022-10` are -1. Treat these as immaterial timing/source-table variance unless exact unit-level reconciliation is needed.
- The scrape scripts now reject wrong-title raw partitions during scrape/compile so future refreshes should not silently mix vehicle-class tables into maker-fuel CSVs.
- Targeted live recheck of `RJ 2026-03` on 2026-05-30 produced `159,945` for both State x Maker x Vehicle Category and State x Vehicle Category x Fuel. The stored maker-category file had `148,115`, so that mismatch is confirmed as our stale/partial scrape, not a VAHAN source inconsistency. Details are in `data/vahan_2021_2026_calendar/TARGETED_RECHECKS.md`.

## Full standard repair and consolidated export - 2026-05-30

Goal:
- Eliminate the old/new dataset split.
- Repair remaining wrong-table captures.
- Keep one downstream consolidated CSV for dashboard/data work.

Final standard source files:
- `data/vahan_2021_2026_calendar/all_state_maker_month_long.csv`
- `data/vahan_2021_2026_calendar/state_maker_fuel_month_long.csv`
- `data/vahan_2021_2026_calendar/state_maker_category_month_long.csv`
- `data/vahan_2021_2026_calendar/state_category_fuel_month_long.csv`

Single consolidated export:
- `data/vahan_2021_2026_calendar/standard_consolidated/vahan_standard_consolidated_long.csv`
- Row count: `888,256` data rows.
- This folder intentionally contains only the one consolidated CSV.
- Schema uses a `dataset` column to separate:
  - `national_maker_month`
  - `state_maker_fuel`
  - `state_maker_category`
  - `state_category_fuel`

Repair run sequence:
1. Repair bad-title raw partitions:

```bash
../.venv-vahan/bin/python3 scripts/repair_vahan_bad_title_partitions.py \
  --dataset state_maker_fuel \
  --workers 3 \
  --attempts 4 \
  --wait-seconds 120 \
  --page-timeout 120 \
  --retry-sleep 8
```

Result:
- `state_maker_fuel_month_raw`: 2,340 files, 0 bad titles.
- `state_maker_fuel_month_long.csv`: 398,856 data rows after subsequent targeted refresh.
- Worker logs:
  - `logs/repair_state_maker_fuel_bad_titles_worker_1.log`
  - `logs/repair_state_maker_fuel_bad_titles_worker_2.log`
  - `logs/repair_state_maker_fuel_bad_titles_worker_3.log`
  - `logs/repair_state_maker_fuel_compile.log`

2. Equalize mixed-vintage mismatches across all three state-level datasets:

```bash
../.venv-vahan/bin/python3 scripts/refresh_vahan_targeted_partitions.py \
  --threshold 2 \
  --workers 3 \
  --datasets state_maker_fuel state_maker_category state_category_fuel \
  --attempts 4 \
  --wait-seconds 120 \
  --page-timeout 120 \
  --retry-sleep 8
```

What it does:
- Finds state-months where State x Maker x Fuel and State x Maker x Vehicle Category differ by more than 2 registrations.
- Refreshes the same state/month partitions across all listed datasets.
- Workers use `--skip-compile`; compile happens once at the end per dataset.

Result:
- Refreshed 32 state-months across 12 state-year groups and all 3 state-level datasets.
- Final residual state-month variance:
  - Maker Category vs Maker Fuel: max absolute difference `2`.
  - Maker Category vs Category Fuel: max absolute difference `2`.
- These small 1-2 registration variances are treated as immaterial VAHAN timing/source-table variance.

3. Build the one consolidated CSV:

```bash
python3 scripts/build_vahan_standard_consolidated.py
```

4. Run final QA:

```bash
python3 scripts/audit_vahan_data_quality.py
```

Final QA files:
- `data/vahan_2021_2026_calendar/CANONICAL_DATA.md`
- `data/vahan_2021_2026_calendar/STANDARD_DATASET_MANIFEST.csv`
- `data/vahan_2021_2026_calendar/vahan_data_quality_report.md`

Future scrape rules:
- Always validate the VAHAN table title before writing/compiling raw files.
- For parallel workers, write raw files only with `--skip-compile`, then compile once after all workers finish.
- Use three workers by splitting disjoint state/state-year batches; avoid overlapping the same raw partition.
- After any repair/refresh, run the audit and rebuild `standard_consolidated/vahan_standard_consolidated_long.csv`.
- Downstream dashboard work should read the consolidated CSV unless a specific raw source file is needed for debugging.

## No-confusion standard source workflow - 2026-05-30

This section supersedes older notes that mention using exploratory files as dashboard inputs.

Single downstream source of truth:
- `data/vahan_2021_2026_calendar/standard_consolidated/vahan_standard_consolidated_long.csv`

Machine-readable pointer:
- `data/vahan_2021_2026_calendar/CURRENT_STANDARD_DATASET.json`

Human-readable source guide:
- `data/vahan_2021_2026_calendar/STANDARD_DATA_SOURCE.md`

Validation report:
- `data/vahan_2021_2026_calendar/data_source_validation_report.md`

How future scrapes must finish:
1. Scrape raw JSON partitions.
2. Compile the standard long CSVs.
3. Run `scripts/finalize_vahan_standard_data.py`.
4. That script rebuilds `standard_consolidated/vahan_standard_consolidated_long.csv`, writes `CURRENT_STANDARD_DATASET.json`, reruns QA, and validates row counts.

Monthly refresh rule:
- `scripts/refresh_vahan_recent_months.py` now runs the finalize step automatically at the end, unless `--skip-finalize` is explicitly passed.

Important guardrail:
- Raw folders (`state_*_month_raw`) are audit/rebuild inputs only.
- Legacy exploratory files (`2w_*`, `4w_*`, `monthly_*`, `fuel_maker_vehicle_category_long.csv`, stale all-state maker-fuel/category files) must not be dashboard sources.
- Current root HTML/JS dashboard artifacts can still contain older embedded/reference data. Treat them as legacy until they are rewired to `CURRENT_STANDARD_DATASET.json`.

## Legacy archive cleanup - 2026-05-30

Decision:
- We do not need old exploratory CSV/JSON outputs or old static dashboards in active locations.
- To preserve integrity, they are archived rather than deleted.

Archive location:
- `archive/legacy_pre_standardization_20260530/`

Archive manifest:
- `archive/legacy_pre_standardization_20260530/ARCHIVE_MANIFEST.csv`

Archived file groups:
- Old `2w_*` and `4w_*` segment-filtered CSV/JSON outputs.
- Old `monthly_*`, `fuel_maker_vehicle_category_long.csv`, and annual EV penetration outputs.
- Stale all-state maker-fuel/category files.
- Root static dashboard artifacts (`index.html`, `state_payload.js`, `vahan_dashboard_v*.html`, and Vahaan Workbench HTMLs).
- Old root README/status docs and dashboard backup files.

Active source rule after cleanup:
- Downstream analysis should read `CURRENT_STANDARD_DATASET.json` and then `standard_consolidated/vahan_standard_consolidated_long.csv`.
- Scrape/finalize scripts should use only active raw partitions and standard source CSVs, never archive files.
- Root `README.md` now documents the active data chain and monthly refresh commands.

## Dashboard v19 — canonical-data rewire (2026-05-30)

`vahan_dashboard_v19.html` is the active dashboard at the project root. It is
a single-file build (state payload now inlined; no more external
`state_payload.js`) and reads exclusively from the consolidated dataset.

### Build pipeline

```
data/.../standard_consolidated/vahan_standard_consolidated_long.csv
        ↓
scripts/build_dashboard_payload.py  (reads consolidated CSV, builds two JSONs)
        ↓
outputs/dashboard_payload.json        # inline <script id="payload"> body
outputs/dashboard_state_payload.json  # inline window.__STATE_PAYLOAD__ body
        ↓
scripts/rewire_v19_dashboard.py  (takes archived v18 HTML + the two JSONs)
        ↓
vahan_dashboard_v19.html  (single-file, ~10.9 MB)
```

To rebuild after a fresh scrape:

```bash
python3 scripts/build_dashboard_payload.py
python3 scripts/rewire_v19_dashboard.py
```

### Data routing decisions

- National maker monthly totals come from the consolidated `national_maker_month`
  dataset (the authoritative source — has Ola 7,806/4,167/10,254/12,323/13,054
  for Jan-May 2026, YTD 47,604).
- State x maker x category split comes from `state_maker_category`.
- State x maker x fuel split comes from `state_maker_fuel`, rescaled per
  maker-month so the rescaled fuel split sums to the canonical national total.
  This fixes the previous undercount for makers like Ola where the fuel-route
  scrape had per-state gaps.
- `by_year_maker`, `maker_universe.totals`, and `state_payload.national_aggregate`
  all use the canonical national total; per-bucket entries are rescaled with
  largest-remainder rounding so bucket sums equal the canonical year total.

### Maker name canonicalisation

The raw VAHAN → canonical mapping (e.g. `HERO MOTOCORP LTD` → `Hero Group`)
lives at `scripts/_resources/maker_canonical_map.json`. The build script
applies fallback title-casing for new makers absent from the mapping. The
build trims the long-tail (max-year-total < 100) so the payload stays around
6 MB for the inline block.

### Anomaly view improvements (v19)

The anomaly view was retuned to cut noise:

- **Severity tiers (S / A / B)** — each event now carries a tier from
  combining z-score, %-deviation, and absolute-delta. Thresholds:
  - National: S = |z|>=3 AND |Δ%|>=25 AND |Δ|>=5000;
    A = |z|>=2.5 AND |Δ%|>=15 AND |Δ|>=2000;
    B = |z|>=2 AND |Δ%|>=10 AND |Δ|>=500.
  - State: same z/% thresholds, 5x smaller absolute floors (1000/400/100).
- **Universe tightened** — top 30 national makers (was 40); top 8 states x
  top 12 makers for state-level (was 12 x 15).
- **Confirmation badge** — each event marked `confirmed` (next month
  sustained), `unconfirmed` (next month reversed), or `pending` (latest month;
  no follow-up yet). Default view shows `confirmed` and `pending` only,
  hiding single-month spikes.
- **Default view**: Tier S+A + confirmed. Filter chips expose "All tiers" and
  "All events" toggles for the more permissive view.
- Existing 1M/3M/6M trailing-window toggle retained on top of the above.

Effect: 1M default view now shows ~25 national events (was 30+); state events
correspondingly tighter due to universe cap. Tier B and unconfirmed events
remain detectable behind the chips.

### Deferred for v20

- Seasonal-naive baseline (same-month-prior-year) — alongside trailing-12.
- MAD spread instead of standard deviation (more robust to prior spikes).
- Surfacing the "fallback canonicalisation" list (~2,400 long-tail makers)
  in a small audit panel for review and explicit mapping.
