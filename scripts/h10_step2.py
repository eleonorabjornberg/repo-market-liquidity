#!/usr/bin/env python3
"""H10 step 2 (`docs/stages/h10-step2.md`): apply the declared method to every development onset.

    PYTHONPATH=src python3 scripts/h10_step2.py [--workers N]

Rebuilds panel version 1 to its manifest, reads the parent's onsets at the pinned commit, attributes each episode
(10,000 bootstrap draws, the placebo and the benchmark), builds the selection-aware null (1,000 draws) and writes
`results/h10/development.json`. Development evidence only: no day after the parent's development end is read, and nothing
is scored or registered.
"""

import argparse
import json

from repo_liquidity import h10_apply


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    rows, manifest = h10_apply.load_development()
    record = h10_apply.build_record(rows, manifest, workers=args.workers)
    h10_apply.RECORD.parent.mkdir(parents=True, exist_ok=True)
    h10_apply.RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = record["summary"]
    print(f"wrote {h10_apply.RECORD}: {summary['episodes']} episodes, under bar {summary['under_bar']}, "
          f"beats null {summary['beats_null']}, both {summary['counted']}: {summary['outcome']}")


if __name__ == "__main__":
    main()
