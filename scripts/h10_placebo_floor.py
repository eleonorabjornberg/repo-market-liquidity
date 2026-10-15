#!/usr/bin/env python3
"""H10 step 3 amendment (#85): the placebo comparison with and without the 2 bp rise floor.

    PYTHONPATH=src python3 scripts/h10_placebo_floor.py

Rebuilds panel version 1 to its manifest, re-runs only the placebo at the published record's pin, seeds and episodes, and
writes `results/h10/placebo_floor_2bp.json`. `results/h10/development.json` is read and not written. Development
evidence only: nothing is scored or registered.
"""

import json

from repo_liquidity import h10_apply, panel


def main() -> None:
    rows, manifest = h10_apply.load_development()
    development = json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))
    record = h10_apply.placebo_floor_record(rows, development, panel.load_manifest(h10_apply.PANEL_VERSION))
    h10_apply.PLACEBO_FLOOR_RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, reading in record["readings"].items():
        gap = reading["median_placebo_gap"]
        print(f"{name}: median placebo gap {gap['median']:.3f} (interval {gap['interval'][0]:.3f} to {gap['interval'][1]:.3f}, n = {gap['n']})")


if __name__ == "__main__":
    main()
