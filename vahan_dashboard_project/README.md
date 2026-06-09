# VAHAN Dashboard Project

This project now has one active standard data source for downstream analysis:

- `data/vahan_2021_2026_calendar/standard_consolidated/vahan_standard_consolidated_long.csv`

Machine-readable pointer:

- `data/vahan_2021_2026_calendar/CURRENT_STANDARD_DATASET.json`

Use the pointer file from dashboards, notebooks, or spreadsheet workflows so
there is no ambiguity about which CSV is current.

## Active Data Chain

The active integrity chain is:

1. Raw state/month VAHAN JSON partitions in `state_*_month_raw/`.
2. Four standard source CSVs:
   - `all_state_maker_month_long.csv`
   - `state_maker_fuel_month_long.csv`
   - `state_maker_category_month_long.csv`
   - `state_category_fuel_month_long.csv`
3. One consolidated downstream CSV:
   - `standard_consolidated/vahan_standard_consolidated_long.csv`

The raw JSON files are audit/rebuild inputs only. Downstream work should use
the consolidated CSV.

## Monthly Refresh

Refresh current and previous month:

```bash
../.venv-vahan/bin/python3 scripts/refresh_vahan_recent_months.py
```

That runner refreshes the standard source CSVs and then finalizes the
consolidated CSV automatically.

Finalize without scraping:

```bash
python3 scripts/finalize_vahan_standard_data.py
```

Validate the standard source:

```bash
python3 scripts/validate_standard_data_sources.py --strict-app
```

## Archive

Legacy exploratory files and old static dashboards were moved to:

- `archive/legacy_pre_standardization_20260530/`

The archive has `ARCHIVE_MANIFEST.csv` with original paths, byte sizes, and
SHA-256 checksums. Active scrape/finalize work should not read from the archive.
