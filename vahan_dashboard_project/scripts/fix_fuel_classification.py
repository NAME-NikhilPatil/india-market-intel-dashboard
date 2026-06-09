#!/usr/bin/env python3
"""Reclassify fuel_group across the long CSVs using the canonical rule.

Canonical rule (Hybrid is checked BEFORE EV so plug-in/strong/petrol-hybrid
land in Hybrid, not EV):

  HYBRID in fuel_type                    -> Hybrid
  fuel_type in {PURE EV, ELECTRIC(BOV),
                FUEL CELL HYDROGEN}      -> EV
  DIESEL in fuel_type                    -> Diesel
  PETROL in fuel_type                    -> Petrol
  else                                   -> Others

Affected files:
  - fuel_maker_vehicle_category_long.csv     (had STRONG/PLUG-IN HYBRID EV mis-tagged as EV)
  - monthly_fuel_vehicle_category_long.csv   (same + FUEL CELL HYDROGEN as Others)

The all_state_maker_fuel_month_long.csv and state_maker_fuel_month_long.csv are
already classified correctly.

Run from project root:
  python3 scripts/fix_fuel_classification.py
"""
from __future__ import annotations

import csv
from pathlib import Path

DATA = Path('data/vahan_2021_2026_calendar')

PURE_EV_TYPES = {'PURE EV', 'ELECTRIC(BOV)', 'FUEL CELL HYDROGEN'}


def fuel_group(fuel_type: str) -> str:
    ft = (fuel_type or '').upper().strip()
    if not ft:
        return 'Others'
    # Hybrid first — covers PLUG-IN HYBRID EV / STRONG HYBRID EV /
    # PETROL/HYBRID / DIESEL/HYBRID / PETROL(E20)/HYBRID / etc.
    if 'HYBRID' in ft:
        return 'Hybrid'
    # EV (only pure battery + fuel cell)
    if ft in PURE_EV_TYPES or 'ELECTRIC' in ft or 'PURE EV' in ft:
        return 'EV'
    if 'DIESEL' in ft:
        return 'Diesel'
    if ft.startswith('PETROL'):
        return 'Petrol'
    return 'Others'


def reclassify_csv(path: Path) -> None:
    print(f"\nProcessing {path.name} ...")
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        rows = list(reader)

    if 'fuel_group' not in cols or 'fuel_type' not in cols:
        print(f"  skipping — no fuel_group/fuel_type columns")
        return

    fixed = 0
    breakdown = {}
    for r in rows:
        old = r.get('fuel_group', '')
        new = fuel_group(r.get('fuel_type', ''))
        if old != new:
            fixed += 1
            key = (r.get('fuel_type', ''), old, new)
            breakdown[key] = breakdown.get(key, 0) + 1
            r['fuel_group'] = new

    if fixed == 0:
        print("  no changes")
        return

    print(f"  reclassified {fixed:,} rows. Changes:")
    for (ft, old, new), n in sorted(breakdown.items(), key=lambda x: -x[1]):
        print(f"    {ft:30s} {old:8s} -> {new:8s} : {n:,} rows")

    # Write back
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path.name}")


def main() -> None:
    for name in [
        'fuel_maker_vehicle_category_long.csv',
        'monthly_fuel_vehicle_category_long.csv',
        # The remaining long files already use the correct classification,
        # but a re-run is idempotent.
        'all_state_maker_fuel_month_long.csv',
        'state_maker_fuel_month_long.csv',
    ]:
        p = DATA / name
        if p.exists():
            reclassify_csv(p)


if __name__ == '__main__':
    main()
