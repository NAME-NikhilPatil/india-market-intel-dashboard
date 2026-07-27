# VAHAN Data Quality Report

Generated: 2026-07-28T01:58:40

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
| state_maker_fuel_month_raw | Maker Wise Fuel Data | 2412 | 0 |  |  |
| state_maker_category_month_raw | Maker Wise Vehicle Category Data | 2412 | 0 |  |  |
| state_category_fuel_month_raw | Vehicle Category Wise Fuel Data | 2412 | 0 |  |  |

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

State-month cells with any difference: 104; max absolute state-month difference: 309606 registrations.
| month | state | maker_category_total | maker_fuel_total | diff |
| --- | --- | --- | --- | --- |
| 2026-06 | UP | 346444 | 36838 | 309606 |
| 2026-06 | WB | 128872 | 16277 | 112595 |
| 2026-06 | MH | 252019 | 140706 | 111313 |
| 2026-06 | MP | 127424 | 21609 | 105815 |
| 2026-07 | UP | 245927 | 146661 | 99266 |
| 2026-07 | GJ | 174327 | 77593 | 96734 |
| 2026-06 | KA | 188029 | 94504 | 93525 |
| 2026-07 | MP | 98799 | 12662 | 86137 |
| 2026-06 | PB | 66644 | 7049 | 59595 |
| 2026-06 | TG | 81396 | 23413 | 57983 |
| 2026-07 | KA | 147133 | 94640 | 52493 |
| 2026-07 | BR | 93934 | 49472 | 44462 |
| 2026-07 | MH | 215084 | 173007 | 42077 |
| 2026-06 | JH | 58478 | 18585 | 39893 |
| 2026-07 | TG | 39614 | 71392 | -31778 |
| 2026-07 | WB | 81747 | 51863 | 29884 |
| 2026-06 | RJ | 133770 | 105033 | 28737 |
| 2026-07 | RJ | 112247 | 87814 | 24433 |
| 2026-06 | CG | 26905 | 48435 | -21530 |
| 2026-06 | KL | 93981 | 72741 | 21240 |
| 2026-06 | HR | 87859 | 66928 | 20931 |
| 2026-06 | AP | 97939 | 77320 | 20619 |
| 2026-07 | DL | 41956 | 60366 | -18410 |
| 2026-07 | JH | 43702 | 30307 | 13395 |
| 2026-06 | GJ | 176804 | 165820 | 10984 |

State-maker-month cells with any difference: 3596; max absolute state-maker-month difference: 122183 registrations.
| month | state | maker | category_sum | fuel_sum | diff |
| --- | --- | --- | --- | --- | --- |
| 2026-06 | UP | HERO MOTOCORP LTD | 122183 | 0 | 122183 |
| 2026-06 | UP | TVS MOTOR COMPANY LTD | 50527 | 0 | 50527 |
| 2026-07 | GJ | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 49293 | 0 | 49293 |
| 2026-07 | UP | TVS MOTOR COMPANY LTD | 36293 | 0 | 36293 |
| 2026-06 | UP | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 34849 | 0 | 34849 |
| 2026-06 | KA | TVS MOTOR COMPANY LTD | 30959 | 0 | 30959 |
| 2026-06 | MH | TVS MOTOR COMPANY LTD | 30852 | 0 | 30852 |
| 2026-06 | MP | HERO MOTOCORP LTD | 30751 | 0 | 30751 |
| 2026-06 | WB | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 27083 | 0 | 27083 |
| 2026-07 | KA | TVS MOTOR COMPANY LTD | 26155 | 0 | 26155 |
| 2026-07 | BR | HERO MOTOCORP LTD | 24669 | 0 | 24669 |
| 2026-06 | MP | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 22196 | 0 | 22196 |
| 2026-07 | WB | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 21885 | 0 | 21885 |
| 2026-06 | MH | SUZUKI MOTORCYCLE INDIA PVT LTD | 21036 | 0 | 21036 |
| 2026-06 | UP | MARUTI SUZUKI INDIA LTD | 20773 | 0 | 20773 |
| 2026-06 | WB | TVS MOTOR COMPANY LTD | 20636 | 0 | 20636 |
| 2026-07 | MP | HERO MOTOCORP LTD | 20019 | 0 | 20019 |
| 2026-06 | TG | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 19206 | 0 | 19206 |
| 2026-07 | TG | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 0 | 19184 | -19184 |
| 2026-07 | MP | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 18256 | 0 | 18256 |
| 2026-06 | MH | MARUTI SUZUKI INDIA LTD | 17946 | 0 | 17946 |
| 2026-07 | WB | TVS MOTOR COMPANY LTD | 0 | 16759 | -16759 |
| 2026-06 | WB | HERO MOTOCORP LTD | 16444 | 0 | 16444 |
| 2026-06 | MP | TVS MOTOR COMPANY LTD | 16240 | 0 | 16240 |
| 2026-07 | BR | HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD | 16124 | 0 | 16124 |

## State Total: Category x Fuel vs Maker x Category

Different state-month cells after excluding category-fuel bad-title files: 28. Left = state maker-category total; right = state category-fuel total.
| month | state | maker_category_total | category_fuel_total | diff |
| --- | --- | --- | --- | --- |
| 2026-07 | TG | 39614 | 71394 | -31780 |
| 2026-06 | CG | 26905 | 55406 | -28501 |
| 2026-07 | WB | 81747 | 102351 | -20604 |
| 2026-07 | DL | 41956 | 60366 | -18410 |
| 2026-06 | TG | 81396 | 92981 | -11585 |
| 2026-07 | TN | 183180 | 194062 | -10882 |
| 2026-06 | MH | 252019 | 262269 | -10250 |
| 2026-06 | DL | 61064 | 69849 | -8785 |
| 2026-06 | UK | 16849 | 23925 | -7076 |
| 2026-07 | AS | 31501 | 37263 | -5762 |
| 2026-07 | OR | 59859 | 64147 | -4288 |
| 2026-06 | PB | 66644 | 70643 | -3999 |
| 2026-07 | UK | 19618 | 23419 | -3801 |
| 2026-06 | AS | 48376 | 51517 | -3141 |
| 2026-07 | GA | 6832 | 4939 | 1893 |
| 2026-06 | PY | 6520 | 8015 | -1495 |
| 2026-06 | GA | 5628 | 6832 | -1204 |
| 2026-07 | JH | 43702 | 44296 | -594 |
| 2026-06 | BR | 132341 | 132914 | -573 |
| 2026-06 | RJ | 133770 | 134002 | -232 |
| 2026-06 | HR | 87859 | 88007 | -148 |
| 2026-06 | AP | 97939 | 98056 | -117 |
| 2026-06 | JK | 22177 | 22203 | -26 |
| 2026-06 | CH | 5150 | 5159 | -9 |
| 2024-01 | MP | 134260 | 134258 | 2 |

## Source vs Our End

- May 2026 is internally consistent across the refreshed standard tables: 2267511 registrations in all three total views.
- Jan-Apr 2026 differences between national maker-month and state-summed data line up with scrape freshness: national maker-month was refreshed on May 30, while state-level Jan-Apr rows are mostly May 15. Treat that as our refresh/staleness issue, not a VAHAN source problem.
- Raw-title validation is clean for all three state-level standard datasets.
- Remaining state-total mismatches need targeted rescrape before blaming VAHAN. Several look like partial state-maker-category captures because the independent category-fuel total is much higher.

## Ather/Ola Check Against Canonical Maker-Month

| maker | JAN | FEB | MAR | APR | MAY | YTD |
| --- | --- | --- | --- | --- | --- | --- |
| ATHER ENERGY LTD | 23083 | 21259 | 36326 | 28441 | 24854 | 133963 |
| OLA ELECTRIC TECHNOLOGIES PVT LTD | 7806 | 4167 | 10254 | 12323 | 13054 | 47604 |
