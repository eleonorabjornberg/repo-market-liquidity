#!/usr/bin/env python3
"""H10 step 3 (#86, finding #79): the ON RRP sensitivity with two regime-specific terms.

    PYTHONPATH=src python3 scripts/h10_regimes.py [--workers N]

The step 2 application (`scripts/h10_step2.py`) re-run at the same pin, panel, seeds and episodes, with ON RRP entering as
`window change x 1(depleted)` and `window change x 1(abundant)` (the window's regime fixed by its baseline mean ON RRP),
each with its own coefficient. Writes the new record `results/h10/sensitivity_onrrp_regimes.json`; it never writes
`results/h10/development.json` or `results/h10/sensitivity_onrrp_interaction.json`. Development evidence only, reported
only: it changes no outcome and scores nothing.
"""

import argparse
import json

from repo_liquidity import h10_apply


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    rows, manifest = h10_apply.load_development()
    record = h10_apply.build_record(rows, manifest, workers=args.workers, regimes=True)
    h10_apply.REGIMES_RECORD.parent.mkdir(parents=True, exist_ok=True)
    h10_apply.REGIMES_RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = record["summary"]
    print(f"wrote {h10_apply.REGIMES_RECORD}: {summary['episodes']} episodes, under bar {summary['under_bar']}, "
          f"beats null {summary['beats_null']}, both {summary['counted']}")


if __name__ == "__main__":
    main()
