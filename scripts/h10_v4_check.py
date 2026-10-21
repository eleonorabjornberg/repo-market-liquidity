#!/usr/bin/env python3
"""H10 re-registration (#152): are H10's published development tables unchanged on panel version 4?

    PYTHONPATH=src python3 scripts/h10_v4_check.py [--workers N]

Re-runs the step 2 application, its ON RRP interaction sensitivity, its regime sensitivity and the placebo-floor comparison
on panel version 4 (what `h10_apply.load_development()` reads now), at the published records' pin, seeds and episodes, and
compares each with the tracked record in `results/h10/`. Only `panel` (the records name version 1) and `parent_commit` (they name the pin they were made at, 8fd2cf8) may differ.
Writes nothing: the published records are not touched. Development evidence only; nothing is scored or registered.
"""

import argparse
import json
import sys

from repo_liquidity import h10_apply, panel

RECORDS = (
    ("development", h10_apply.RECORD, {}),
    ("interaction", h10_apply.SENSITIVITY_RECORD, {"interaction": True}),
    ("regimes", h10_apply.REGIMES_RECORD, {"regimes": True}),
)


def differences(published, rebuilt, path=""):
    """The paths at which two JSON-able values differ."""
    if isinstance(published, dict) and isinstance(rebuilt, dict):
        out = []
        for key in sorted(set(published) | set(rebuilt)):
            if key not in published or key not in rebuilt:
                out.append(f"{path}/{key}")
            else:
                out.extend(differences(published[key], rebuilt[key], f"{path}/{key}"))
        return out
    if isinstance(published, list) and isinstance(rebuilt, list) and len(published) == len(rebuilt):
        return [d for i, (a, b) in enumerate(zip(published, rebuilt)) for d in differences(a, b, f"{path}[{i}]")]
    return [] if published == rebuilt else [path or "/"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    rows, manifest = h10_apply.load_development()
    print(f"panel version {manifest['version']}, sha256 {manifest['sha256']}, {len(rows)} rows to {rows[-1].date}")
    failed = False
    for name, path, kwargs in RECORDS:
        published = json.loads(path.read_text(encoding="utf-8"))
        rebuilt = json.loads(json.dumps(h10_apply.build_record(rows, manifest, workers=args.workers, **kwargs)))
        diffs = [d for d in differences(published, rebuilt) if not d.startswith(("/panel", "/parent_commit"))]
        print(f"{name}: {path.name}: {'identical outside /panel and /parent_commit' if not diffs else 'DIFFERS at ' + ', '.join(diffs[:20])}")
        failed = failed or bool(diffs)
        if name == "development":
            development = published
    floor = json.loads(h10_apply.PLACEBO_FLOOR_RECORD.read_text(encoding="utf-8"))
    rebuilt = json.loads(json.dumps(h10_apply.placebo_floor_record(rows, development, panel.load_manifest(h10_apply.PANEL_VERSION))))
    diffs = [d for d in differences(floor, rebuilt) if not d.startswith(("/panel", "/parent_commit"))]
    print(f"placebo floor: {h10_apply.PLACEBO_FLOOR_RECORD.name}: {'identical outside /panel and /parent_commit' if not diffs else 'DIFFERS at ' + ', '.join(diffs[:20])}")
    return 1 if failed or diffs else 0


if __name__ == "__main__":
    sys.exit(main())
