#!/usr/bin/env python3
"""Build `announced_pace.csv` from `runoff_caps.csv` and `announced_purchases.csv` (#125; `repo_liquidity.announced_pace`).

    PYTHONPATH=src python3 scripts/build_announced_pace.py            # write the table and its manifest
    PYTHONPATH=src python3 scripts/build_announced_pace.py --check    # compare with the tracked table

The table is derived, never edited by hand: the caps come from `runoff_caps.csv` and the purchases from
`announced_purchases.csv`. Standard library only.
"""

import argparse
import sys

from repo_liquidity import announced_pace, scheduled


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="rebuild and compare with the tracked table")
    args = parser.parse_args(argv)
    data = announced_pace.build_table_bytes()
    if args.check:
        same = data == announced_pace.PACE_TABLE.read_bytes()
        print("announced_pace.csv is what the inputs build" if same else "announced_pace.csv is stale")
        return 0 if same else 1
    announced_pace.PACE_TABLE.write_bytes(data)
    rows = len(data.splitlines()) - 1
    print(f"announced_pace.csv: {scheduled.write_manifest(announced_pace.PACE_TABLE)} ({rows} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
