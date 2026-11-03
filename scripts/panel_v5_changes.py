#!/usr/bin/env python3
"""Write `results/panel/v5_changes.json`: the rows where panel version 5 differs from version 4 (#200).

    PYTHONPATH=src python3 -B scripts/panel_v5_changes.py --v4 <version 4 CSV> --v5 <version 5 CSV> [--output ...]

Version 4 is built at the parent's pin of 08ff67e (`PYTHONPATH=src:<parent at 08ff67e>/src python3 -B
scripts/build_panel.py --version 4 --output <csv>` was how it was made, at the commit that published it), version 5 at the
current pin. The record lists every cell that differs, by date and column, with both values, and the cause. Nothing is scored.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAUSE = ("the parent's afternoon test-trade rule (repo-market-model#938), merged between the pins of 08ff67e and 2032de4; "
         "the decision instant's move to 18:00 (#1312) changes no cell of this panel")


def changes(v4_path: Path, v5_path: Path) -> dict:
    with v4_path.open(encoding="utf-8") as a, v5_path.open(encoding="utf-8") as b:
        old, new = list(csv.DictReader(a)), list(csv.DictReader(b))
    if len(old) != len(new) or list(old[0]) != list(new[0]):
        raise ValueError("the two panels do not have the same rows and columns")
    columns, rows = Counter(), []
    for x, y in zip(old, new):
        if x["date"] != y["date"]:
            raise ValueError(f"dates differ: {x['date']} and {y['date']}")
        for column in x:
            if x[column] != y[column]:
                columns[column] += 1
                rows.append({"column": column, "date": x["date"], "v4": x[column], "v5": y[column]})
    if set(columns) != {"srf_take_up"}:
        raise ValueError(f"columns other than srf_take_up differ: {dict(columns)}")
    by_year = Counter(row["date"][:4] for row in rows)
    return {"cause": CAUSE, "column": "srf_take_up", "count": len(rows), "by_year": dict(sorted(by_year.items())),
            "changes": [{"date": r["date"], "v4": r["v4"], "v5": r["v5"]} for r in rows]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v4", type=Path, required=True)
    parser.add_argument("--v5", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "panel" / "v5_changes.json")
    args = parser.parse_args(argv)
    record = changes(args.v4, args.v5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{record['count']} cells differ, all in srf_take_up; by year {record['by_year']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
