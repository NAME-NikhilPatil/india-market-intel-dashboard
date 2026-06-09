# Solar DCR Scrape

Source: https://solardcrportal.nise.res.in/Summary/index

Generated CSVs:

- `dashboard_totals.csv` - top dashboard counts.
- `cell_company_yearly_manufactured_mw.csv` - solar cell company/year manufactured MW.
- `cell_monthly_manufactured_sold_mw.csv` - solar cell monthly manufactured/sold MW, including all-manufacturer totals and per-company rows.
- `module_company_yearly_manufactured_mw.csv` - solar module company/year manufactured MW.
- `module_monthly_manufactured_sold_mw.csv` - solar module monthly manufactured/sold MW, including all-manufacturer totals and per-company rows.
- `stock_summary_by_state.csv` - state-wise stock and unclaimed MW values.
- `stock_summary_totals.csv` - summed stock and unclaimed MW metrics.

The scraper script is `scrape_solar_dcr.py`.

Note: `/Summary/DCRListTbl` was probed with the same session and AJAX headers used for stock, but clean DCR table extraction did not complete reliably. Repeated scalar parameters returned a server error, and bracket-array parameters timed out during this run.
