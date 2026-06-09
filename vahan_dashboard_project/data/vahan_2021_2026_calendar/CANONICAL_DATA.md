# Canonical VAHAN Data Sources

Use these files as the standard dataset going forward:

Single consolidated CSV for downstream use:

- `standard_consolidated/vahan_standard_consolidated_long.csv`

Machine-readable pointer for downstream code:

- `CURRENT_STANDARD_DATASET.json`

| Need | Canonical file | Notes |
| --- | --- | --- |
| National maker monthly/YTD totals | `all_state_maker_month_long.csv` | Matches VAHAN Maker x Month Wise all-state table. Use this for Ather/Ola national totals. |
| State x maker x vehicle category | `state_maker_category_month_long.csv` | Use for state/category splits and maker geography. Remaining state-total variance is at most 2 registrations. |
| State x maker x fuel | `state_maker_fuel_month_long.csv` | Use for state-level maker fuel mix. All raw titles are correct. |
| State x vehicle category x fuel | `state_category_fuel_month_long.csv` | Use for state/category EV penetration. All raw titles are correct. |

Non-canonical / legacy files:

- `all_state_maker_fuel_month_long.csv` and `all_state_maker_category_month_long.csv` are archived legacy outputs, not standard sources.
- `2w_*`, `4w_*`, `monthly_*`, and `fuel_maker_vehicle_category_long.csv` are earlier exploratory outputs. Keep them archived; do not use them as standard dashboard inputs.
- `state_maker_fuel_month_long.csv` is standard after bad-title repair.

Latest audit report:

- `vahan_data_quality_report.md`
- `STANDARD_DATASET_MANIFEST.csv`
- `data_source_validation_report.md`
