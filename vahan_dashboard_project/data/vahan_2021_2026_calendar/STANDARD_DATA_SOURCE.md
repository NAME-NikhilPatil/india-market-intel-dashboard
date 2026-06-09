# VAHAN Standard Data Source

The downstream source of truth is:

- `standard_consolidated/vahan_standard_consolidated_long.csv`

The machine-readable pointer is:

- `CURRENT_STANDARD_DATASET.json`

Any dashboard, notebook, spreadsheet import, or analysis should read the pointer
file and then load `canonical_consolidated_csv`.

## Pipeline

Raw VAHAN JSON partitions are kept only so we can audit and rebuild:

1. Scrapers write raw state/month JSON partitions.
2. Scrapers compile the standard long CSVs.
3. `scripts/finalize_vahan_standard_data.py` rebuilds the one consolidated CSV.
4. `scripts/validate_standard_data_sources.py` checks that the consolidated CSV is complete and that root app files are not quietly pointing at older CSV exports.

For monthly refreshes, run:

```bash
../.venv-vahan/bin/python3 scripts/refresh_vahan_recent_months.py
```

That runner now finalizes automatically unless `--skip-finalize` is passed.

## Use

Use:

- `standard_consolidated/vahan_standard_consolidated_long.csv`
- `CURRENT_STANDARD_DATASET.json`

Do not use these as dashboard sources:

- `2w_*` and `4w_*`
- `monthly_*`
- `fuel_maker_vehicle_category_long.csv`
- `all_state_maker_fuel_month_long.csv`
- `all_state_maker_category_month_long.csv`
- `state_*_month_raw/*.json`

Those files remain in the project as legacy/debug/audit inputs only.

## Active vs Archive

Active files are the raw partitions, the four standard source CSVs, the
consolidated CSV, and QA/pointer files.

Legacy exploratory outputs and old static dashboards are archived under:

- `archive/legacy_pre_standardization_20260530/`

The archive has `ARCHIVE_MANIFEST.csv` with original paths, byte sizes, and
SHA-256 checksums. Nothing in the active scrape/finalize path should read from
that archive.
