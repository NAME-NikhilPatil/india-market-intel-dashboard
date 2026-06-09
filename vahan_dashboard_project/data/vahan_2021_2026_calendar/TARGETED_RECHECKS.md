# Targeted VAHAN Rechecks

## 2026-05-30 - Rajasthan March 2026

Purpose: verify whether the `RJ 2026-03` mismatch between `state_maker_category_month_long.csv` and `state_category_fuel_month_long.csv` was a VAHAN source issue or a local scrape issue.

Temporary output folder: `/tmp/vahan_audit_recheck`

Fresh live pulls:

| Dataset | VAHAN title | records | total |
| --- | --- | --- | --- |
| State x Maker x Vehicle Category | `Maker Wise Vehicle Category Data of Rajasthan (MAR,2026)` | 260 | 159945 |
| State x Vehicle Category x Fuel | `Vehicle Category Wise Fuel Data of Rajasthan (MAR,2026)` | 15 | 159945 |

Stored main dataset before repair:

| Dataset | stored total |
| --- | --- |
| `state_maker_category_month_long.csv` for `RJ 2026-03` | 148115 |
| `state_category_fuel_month_long.csv` for `RJ 2026-03` | 159945 |

Conclusion: `RJ 2026-03` is not a VAHAN source mismatch. The stored state-maker-category partition is stale/partial and should be replaced by a targeted rescrape.

## 2026-05-30 - Targeted Standard-Data Repairs

Repairs run after the audit:

| Dataset | State/months repaired | Outcome |
| --- | --- | --- |
| State x Maker x Vehicle Category | `UK 2025-10/11` | Replaced partial captures with full multi-page pulls. |
| State x Maker x Vehicle Category | `WB 2024-02` | Replaced partial capture; remaining variance vs category-fuel is 1 registration. |
| State x Maker x Vehicle Category | `MP 2024-01/02` | Replaced partial captures; remaining variance vs category-fuel is 2 and 1 registrations. |
| State x Maker x Vehicle Category | `RJ 2026-03` | Replaced partial capture; now matches category-fuel exactly. |
| State x Maker x Vehicle Category | `HP 2022-10` | Replaced partial capture after a clean retry; remaining variance vs category-fuel is 1 registration. |
| State x Vehicle Category x Fuel | `TG 2023-04` through `TG 2023-12` | Replaced bad-title Vehicle Class x Fuel captures with proper Vehicle Category x Fuel captures. |
| State x Maker x Vehicle Category | `TG 2023-04` through `TG 2023-12` | Refreshed corresponding maker-category partitions; now reconciles with repaired category-fuel. |

Post-repair audit:

- `state_maker_category_month_raw`: 2,340 files, 0 bad titles.
- `state_category_fuel_month_raw`: 2,340 files, 0 bad titles.
- State-maker-category vs state-category-fuel totals now have only four residual state-month differences, all <= 2 registrations.
- `state_maker_fuel_month_raw` still has 157 bad-title partitions and remains quarantined.
