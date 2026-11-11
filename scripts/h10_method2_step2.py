#!/usr/bin/env python3
"""H10's second declaration, step 2 (#209): the nine-driver development attribution, in pieces (`repo_liquidity.h10_apply_2`).

    # The full run: a long run for Eleonora's Mac (about 2.5 hours on one core, 30 to 40 minutes on eight). From a clean tree.
    PYTHONPATH=<parent at the pin>/src:src python3 scripts/h10_method2_step2.py run --workers 8
    PYTHONPATH=<parent at the pin>/src:src python3 scripts/h10_method2_step2.py assemble
    PYTHONPATH=<parent at the pin>/src:src python3 scripts/emit_h10_method2_table.py

    # A smoke run, to show that the code path works (never a result; written outside the tracked pieces):
    PYTHONPATH=... python3 scripts/h10_method2_step2.py run --smoke --limit 3 --draws 50 --null-draws 5

    PYTHONPATH=... python3 scripts/h10_method2_step2.py status

`run` writes one file per episode and one for the null under `results/h10/method2/`, skipping any piece that exists with the same
settings, so an interrupted run is finished by running it again. `assemble` scores only the pieces that exist: it names what is
missing and writes `results/h10/development_2.json` only when every piece is there, from one clean commit. Development evidence,
never a verdict: nothing is registered, and no day after the parent's development end is read.
"""

import argparse
import json
import os
import sys

from repo_liquidity import attribution, h10_apply, h10_apply_2 as h2


def _onsets():
    return [e["onset"] for e in json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))["episodes"]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the pieces that do not exist")
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--draws", type=int, default=attribution.DRAWS)
    run.add_argument("--null-draws", type=int, default=attribution.NULL_DRAWS)
    run.add_argument("--limit", type=int, help="only the first N episodes (a smoke run)")
    run.add_argument("--smoke", action="store_true", help="label the run a smoke run and write to results/h10/method2_smoke/")
    sub.add_parser("status", help="list the pieces that exist and the ones that are missing")
    assemble = sub.add_parser("assemble", help="write the record from the pieces, if they are all there")
    assemble.add_argument("--smoke", action="store_true", help="read the smoke pieces and print the record to stdout; write nothing")
    args = parser.parse_args(argv)

    if args.command == "status":
        absent = h2.missing_pieces(h2.PIECES_DIR, _onsets())
        print(f"{len(_onsets()) + 1 - len(absent)} of {len(_onsets()) + 1} pieces exist under {h2.PIECES_DIR}")
        for name in absent:
            print("missing:", name)
        return 0
    if args.command == "run":
        out = h2.SMOKE_DIR if args.smoke else h2.PIECES_DIR
        report = h2.run_pieces(out, draws=args.draws, null_draws=args.null_draws, workers=args.workers, limit=args.limit,
                               smoke=args.smoke)
        label = "SMOKE RUN (not a result)" if args.smoke else "run"
        print(f"{label}: wrote {len(report['written'])} piece(s), skipped {len(report['skipped_existing'])} existing, under {out}")
        print(f"panel version {h2.PANEL_VERSION_2} sha256 {report['panel_sha256']}; commit {report['provenance']['repo_commit']}, "
              f"tree modified: {report['provenance']['tree_modified']}; Python {report['provenance']['python']}")
        return 0
    if args.smoke:
        print(json.dumps(h2.build_record(h2.SMOKE_DIR, allow_smoke=True), indent=2, sort_keys=True))
        return 0
    try:
        record = h2.build_record(h2.PIECES_DIR)
    except ValueError as error:
        print(f"no record assembled: {error}", file=sys.stderr)
        return 2
    h2.RECORD.parent.mkdir(parents=True, exist_ok=True)
    h2.RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    s = record["summary"]
    print(f"wrote {h2.RECORD}: {s['episodes']} episodes, under bar {s['under_bar']}, beats null {s['beats_null']}, both {s['counted']}: "
          f"{s['outcome']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
