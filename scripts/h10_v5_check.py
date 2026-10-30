#!/usr/bin/env python3
"""H10 re-registration (#200): are H10's published development tables unchanged at the post-#1312 pin?

    PYTHONPATH=src python3 scripts/h10_v5_check.py [--workers N]

The same check as `scripts/h10_v4_check.py` (#152), one pin later. Re-runs the step 2 application, its ON RRP interaction
sensitivity, its regime sensitivity and the placebo-floor comparison on panel version 5 (what `h10_apply.load_development()`
reads now: the parent at 2032de4, decision instant 18:00), at the published records' seeds and episodes, and compares each with
the tracked record in `results/h10/`. Only `panel` (the records name version 1 or 4), `parent_commit` (the pin each was made
at) and `settings.decision_time` (the records were made at 16:00; the rebuilt rows at 18:00) may differ. Anything else printed
as DIFFERS is a change in what H10's tables say. Writes nothing: the published records are not touched. Development
evidence only; nothing is scored or registered.
"""

import argparse
import json
import sys

from repo_liquidity import h10_apply, panel
from h10_v4_check import RECORDS, differences  # noqa: E402  (scripts/ is on sys.path when run as a script)

EXEMPT = ("/panel", "/parent_commit", "/settings/decision_time")


def relevant(diffs):
    return [d for d in diffs if not d.startswith(EXEMPT)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    rows, manifest = h10_apply.load_development()
    print(f"panel version {manifest['version']}, sha256 {manifest['sha256']}, {len(rows)} rows to {rows[-1].date}, "
          f"decision instant {h10_apply.DECISION_TIME.isoformat()}")
    failed = False
    for name, path, kwargs in RECORDS:
        published = json.loads(path.read_text(encoding="utf-8"))
        rebuilt = json.loads(json.dumps(h10_apply.build_record(rows, manifest, workers=args.workers, **kwargs)))
        raw = differences(published, rebuilt)
        diffs = relevant(raw)
        print(f"{name}: {path.name}: exempt paths that differ: {sorted(set(d for d in raw if d.startswith(EXEMPT)))}; "
              f"{'identical elsewhere' if not diffs else 'DIFFERS at ' + ', '.join(diffs[:20])}")
        failed = failed or bool(diffs)
        if name == "development":
            development = published
    floor = json.loads(h10_apply.PLACEBO_FLOOR_RECORD.read_text(encoding="utf-8"))
    rebuilt = json.loads(json.dumps(h10_apply.placebo_floor_record(rows, development, panel.load_manifest(h10_apply.PANEL_VERSION))))
    raw = differences(floor, rebuilt)
    diffs = relevant(raw)
    print(f"placebo floor: {h10_apply.PLACEBO_FLOOR_RECORD.name}: exempt paths that differ: {sorted(set(d for d in raw if d.startswith(EXEMPT)))}; "
          f"{'identical elsewhere' if not diffs else 'DIFFERS at ' + ', '.join(diffs[:20])}")
    return 1 if failed or diffs else 0


if __name__ == "__main__":
    sys.exit(main())
