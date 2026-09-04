# VAHAN Data Quality Report

Generated: 2026-05-30T09:34:33

## Canonical Source Map

- National maker monthly and YTD totals: `all_state_maker_month_long.csv`.
- State x maker x vehicle category: `state_maker_category_month_long.csv`.
- State x vehicle category x fuel: `state_category_fuel_month_long.csv`, except any raw-title exceptions listed below.
- State x maker x fuel: `state_maker_fuel_month_long.csv`.
- Older segment-filtered files (`2w_*`, `4w_*`, `monthly_*`, `fuel_maker_vehicle_category_long.csv`) are legacy/exploratory and should be archived, not active dashboard inputs.
- `all_state_maker_fuel_month_long.csv` and `all_state_maker_category_month_long.csv` are no longer standard; archive them if present.

## Scrape Freshness

| Dataset | scraped_at date distribution |
| --- | --- |
| all_state_maker_month_long.csv | 2026-05-30: 6592 |
| state_maker_category_month_long.csv May rows | 2026-05-30: 6677 |
| state_maker_fuel_month_long.csv May rows | 2026-05-30: 7867 |
| state_category_fuel_month_long.csv May rows | 2026-05-30: 1555 |

## 2026 Month Freshness

| Dataset | Month | scraped_at date distribution |
| --- | --- | --- |
| all_state_maker_month_long.csv | 2026-01 | 2026-05-30: 1334 |
| all_state_maker_month_long.csv | 2026-02 | 2026-05-30: 1365 |
| all_state_maker_month_long.csv | 2026-03 | 2026-05-30: 1320 |
| all_state_maker_month_long.csv | 2026-04 | 2026-05-30: 1321 |
| all_state_maker_month_long.csv | 2026-05 | 2026-05-30: 1252 |
| state_maker_category_month_long.csv | 2026-01 | 2026-05-15: 6716, 2026-05-30: 248 |
| state_maker_category_month_long.csv | 2026-02 | 2026-05-15: 6542, 2026-05-30: 597 |
| state_maker_category_month_long.csv | 2026-03 | 2026-05-15: 6269, 2026-05-30: 780 |
| state_maker_category_month_long.csv | 2026-04 | 2026-05-15: 6596, 2026-05-30: 376 |
| state_maker_category_month_long.csv | 2026-05 | 2026-05-30: 6677 |
| state_category_fuel_month_long.csv | 2026-01 | 2026-05-15: 1623, 2026-05-30: 39 |
| state_category_fuel_month_long.csv | 2026-02 | 2026-05-15: 1537, 2026-05-30: 114 |
| state_category_fuel_month_long.csv | 2026-03 | 2026-05-15: 1500, 2026-05-30: 107 |
| state_category_fuel_month_long.csv | 2026-04 | 2026-05-15: 1532, 2026-05-30: 89 |
| state_category_fuel_month_long.csv | 2026-05 | 2026-05-30: 1555 |
| state_maker_fuel_month_long.csv | 2026-01 | 2026-05-15: 7431, 2026-05-30: 888 |
| state_maker_fuel_month_long.csv | 2026-02 | 2026-05-15: 7490, 2026-05-30: 876 |
| state_maker_fuel_month_long.csv | 2026-03 | 2026-05-15: 7786, 2026-05-30: 465 |
| state_maker_fuel_month_long.csv | 2026-04 | 2026-05-15: 7280, 2026-05-30: 920 |
| state_maker_fuel_month_long.csv | 2026-05 | 2026-05-30: 7867 |

## Raw May 2026 State Partition Check

| Raw dir | May files | not scraped May 30 | examples |
| --- | --- | --- | --- |
| state_maker_fuel_month_raw | 36 | 0 |  |
| state_maker_category_month_raw | 36 | 0 |  |
| state_category_fuel_month_raw | 36 | 0 |  |

## Raw Title Validation

| Raw dir | Expected title fragment | files | bad title files | bad-title groups | examples |
| --- | --- | --- | --- | --- | --- |
| state_maker_fuel_month_raw | Maker Wise Fuel Data | 2340 | 0 |  |  |
| state_maker_category_month_raw | Maker Wise Vehicle Category Data | 2340 | 0 |  |  |
| state_category_fuel_month_raw | Vehicle Category Wise Fuel Data | 2340 | 0 |  |  |

## 2026 Market Total Reconciliation

| month | all_state_maker_month | state_maker_category | state_category_fuel | state_category_minus_all_state | state_category_minus_category_fuel |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | 2845555 | 2845309 | 2845309 | -246 | 0 |
| 2026-02 | 2525868 | 2525437 | 2525437 | -431 | 0 |
| 2026-03 | 2817947 | 2816189 | 2816189 | -1758 | 0 |
| 2026-04 | 2719314 | 2712417 | 2712417 | -6897 | 0 |
| 2026-05 | 2267511 | 2267511 | 2267511 | 0 | 0 |

## National Maker Month vs State-Summed Maker Category

Compared only common months: 2026-01, 2026-02, 2026-03, 2026-04, 2026-05. Left = state-summed category; right = all-state Maker x Month.
Different maker-month cells in common months: 224.
| month | maker | state_sum | all_state_maker_month | diff |
| --- | --- | --- | --- | --- |
| 2026-04 | ROYAL-ENFIELD (UNIT OF EICHER LTD) | 100401 | 101222 | -821 |
| 2026-04 | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 489947 | 490743 | -796 |
| 2026-04 | MAHINDRA & MAHINDRA LIMITED | 76749 | 77471 | -722 |
| 2026-04 | MARUTI SUZUKI INDIA LTD | 166642 | 167195 | -553 |
| 2026-04 | TVS MOTOR COMPANY LTD | 386903 | 387454 | -551 |
| 2026-04 | TOYOTA KIRLOSKAR MOTOR PVT LTD | 28505 | 28975 | -470 |
| 2026-04 | HERO MOTOCORP LTD | 561142 | 561612 | -470 |
| 2026-04 | TATA MOTORS PASSENGER VEHICLES LTD | 49392 | 49707 | -315 |
| 2026-04 | BAJAJ AUTO LTD | 252702 | 253014 | -312 |
| 2026-04 | HYUNDAI MOTOR INDIA LTD | 49132 | 49431 | -299 |
| 2026-04 | KIA INDIA PRIVATE LIMITED | 26206 | 26493 | -287 |
| 2026-03 | MAHINDRA & MAHINDRA LIMITED | 88145 | 88413 | -268 |
| 2026-04 | SUZUKI MOTORCYCLE INDIA PVT LTD | 95043 | 95266 | -223 |
| 2026-03 | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 481244 | 481428 | -184 |
| 2026-03 | TVS MOTOR COMPANY LTD | 394450 | 394633 | -183 |
| 2026-03 | ROYAL-ENFIELD (UNIT OF EICHER LTD) | 99867 | 100036 | -169 |
| 2026-04 | TATA PASSENGER ELECTRIC MOBILITY LTD | 9114 | 9257 | -143 |
| 2026-04 | SKODA AUTO VOLKSWAGEN INDIA PVT LTD | 9250 | 9379 | -129 |
| 2026-03 | TOYOTA KIRLOSKAR MOTOR PVT LTD | 30225 | 30347 | -122 |
| 2026-03 | TATA MOTORS PASSENGER VEHICLES LTD | 59692 | 59814 | -122 |
| 2026-03 | HERO MOTOCORP LTD | 552718 | 552832 | -114 |
| 2026-04 | INDIA YAMAHA MOTOR PVT LTD | 65235 | 65342 | -107 |
| 2026-04 | ATHER ENERGY LTD | 28338 | 28441 | -103 |
| 2026-03 | MARUTI SUZUKI INDIA LTD | 182662 | 182749 | -87 |
| 2026-03 | HYUNDAI MOTOR INDIA LTD | 51709 | 51793 | -84 |

## State Maker Fuel vs State Maker Category

State-month cells with any difference: 57; max absolute state-month difference: 2 registrations.
| month | state | maker_category_total | maker_fuel_total | diff |
| --- | --- | --- | --- | --- |
| 2024-11 | KA | 182512 | 182510 | 2 |
| 2024-06 | KA | 151479 | 151477 | 2 |
| 2024-01 | MP | 134260 | 134258 | 2 |
| 2021-02 | AN | 543 | 541 | 2 |
| 2025-12 | GJ | 169520 | 169522 | -2 |
| 2025-12 | BR | 93656 | 93658 | -2 |
| 2025-05 | GJ | 134078 | 134080 | -2 |
| 2024-07 | KA | 138831 | 138833 | -2 |
| 2024-03 | MN | 1839 | 1841 | -2 |
| 2022-11 | MN | 7447 | 7449 | -2 |
| 2022-11 | HP | 15378 | 15380 | -2 |
| 2022-03 | MN | 4490 | 4492 | -2 |
| 2021-04 | ML | 2440 | 2442 | -2 |
| 2026-04 | AR | 3847 | 3846 | 1 |
| 2025-09 | GJ | 173951 | 173950 | 1 |
| 2025-08 | GJ | 181917 | 181916 | 1 |
| 2025-08 | CG | 47250 | 47249 | 1 |
| 2025-07 | CH | 4337 | 4336 | 1 |
| 2025-07 | BR | 95711 | 95710 | 1 |
| 2025-03 | CG | 59778 | 59777 | 1 |
| 2025-02 | CG | 57965 | 57964 | 1 |
| 2025-01 | CH | 4230 | 4229 | 1 |
| 2025-01 | BR | 92613 | 92612 | 1 |
| 2022-12 | HP | 11934 | 11933 | 1 |
| 2021-12 | ML | 2290 | 2289 | 1 |

State-maker-month cells with any difference: 172; max absolute state-maker-month difference: 4 registrations.
| month | state | maker | category_sum | fuel_sum | diff |
| --- | --- | --- | --- | --- | --- |
| 2026-03 | RJ | HERO MOTOCORP LTD | 55744 | 55748 | -4 |
| 2026-03 | RJ | TAFE LIMITED | 4472 | 4469 | 3 |
| 2026-04 | RJ | KHALSAE-VEHICLES PVT LTD | 27 | 25 | 2 |
| 2026-03 | RJ | MARUTI SUZUKI INDIA LTD | 10994 | 10992 | 2 |
| 2025-11 | BR | TVS MOTOR COMPANY LTD | 35865 | 35863 | 2 |
| 2024-11 | KA | LOCAL TRAILER MANUFACTURER | 1025 | 1023 | 2 |
| 2026-04 | RJ | TATA MOTORS LTD | 2919 | 2921 | -2 |
| 2026-04 | RJ | TAFE LIMITED | 4906 | 4908 | -2 |
| 2026-03 | RJ | MAHINDRA & MAHINDRA LIMITED | 6832 | 6834 | -2 |
| 2026-01 | RJ | BAJAJ AUTO LTD | 8639 | 8641 | -2 |
| 2025-10 | BR | MAHINDRA & MAHINDRA LIMITED | 4445 | 4447 | -2 |
| 2024-09 | KA | HYUNDAI MOTOR INDIA LTD | 2624 | 2626 | -2 |
| 2024-03 | MN | MARUTI SUZUKI INDIA LTD | 223 | 225 | -2 |
| 2024-02 | MP | MAHINDRA & MAHINDRA LIMITED | 3924 | 3926 | -2 |
| 2022-11 | MN | MARUTI SUZUKI INDIA LTD | 921 | 923 | -2 |
| 2026-04 | RJ | TATA MOTORS PASSENGER VEHICLES LTD | 2674 | 2673 | 1 |
| 2026-04 | RJ | SUPERTECH EV LIMITED | 10 | 9 | 1 |
| 2026-04 | RJ | SSB INDISTRIES | 91 | 90 | 1 |
| 2026-04 | RJ | PIAGGIO VEHICLES PVT LTD | 412 | 411 | 1 |
| 2026-04 | RJ | NISSAN MOTOR INDIA PVT LTD | 156 | 155 | 1 |
| 2026-04 | RJ | MINI METRO EV L.L.P | 138 | 137 | 1 |
| 2026-04 | AR | TATA MOTORS LTD | 162 | 161 | 1 |
| 2026-04 | AR | ASHOK LEYLAND LTD | 71 | 70 | 1 |
| 2026-03 | RJ | TVS MOTOR COMPANY LTD | 15124 | 15123 | 1 |
| 2026-03 | RJ | TATA PASSENGER ELECTRIC MOBILITY LTD | 1048 | 1047 | 1 |

## State Total: Category x Fuel vs Maker x Category

Different state-month cells after excluding category-fuel bad-title files: 4. Left = state maker-category total; right = state category-fuel total.
| month | state | maker_category_total | category_fuel_total | diff |
| --- | --- | --- | --- | --- |
| 2024-01 | MP | 134260 | 134258 | 2 |
| 2024-02 | WB | 89282 | 89283 | -1 |
| 2024-02 | MP | 126798 | 126799 | -1 |
| 2022-10 | HP | 10065 | 10066 | -1 |

## Source vs Our End

- May 2026 is internally consistent across the refreshed standard tables: 2267511 registrations in all three total views.
- Jan-Apr 2026 differences between national maker-month and state-summed data line up with scrape freshness: national maker-month was refreshed on May 30, while state-level Jan-Apr rows are mostly May 15. Treat that as our refresh/staleness issue, not a VAHAN source problem.
- Raw-title validation is clean for all three state-level standard datasets.
- Remaining state-total mismatches are only 1-2 registrations after targeted repair. Treat them as immaterial timing/source-table variance unless exact unit-level reconciliation is needed.

## Ather/Ola Check Against Canonical Maker-Month

| maker | JAN | FEB | MAR | APR | MAY | YTD |
| --- | --- | --- | --- | --- | --- | --- |
| ATHER ENERGY LTD | 23083 | 21259 | 36326 | 28441 | 24854 | 133963 |
| OLA ELECTRIC TECHNOLOGIES PVT LTD | 7806 | 4167 | 10254 | 12323 | 13054 | 47604 |
