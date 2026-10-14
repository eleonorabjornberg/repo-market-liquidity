#!/usr/bin/env python3
"""The numbers behind `docs/research/h8-groups-due-diligence.md` (#26): lags, revisions and restatement releases.

    PYTHONPATH=src python3 scripts/diagnostics/h8_groups_diligence.py --raw-root RAW

Reads the archive pages the extract was cut from (the parent's `fetch_frb_h8_archive` saves them under RAW), at the
releases the tracked extract lists, and prints, as JSON:
- the first-print lag in calendar days (week ending Wednesday to release), by count;
- per field, how many weeks a later release restates, and by how much (the first print against the same week in the
  last release that carries it);
- the releases in which an overlapping week moves by more than `--threshold` (a share of its level) against the previous
  release (a share of its level);
- the releases that move one earlier week's large and small total assets by at least `--reclass` billion each, in opposite
  directions: a reclassification between the two groups, which the notes archive does not date.
Standard library plus the parent's parser.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from repo_liquidity import h8

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_h8_groups  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.005)
    parser.add_argument("--reclass", type=float, default=50.0)
    args = parser.parse_args(argv)
    _index, found = extract_h8_groups.snapshots(args.raw_root)
    pages = {day: h8.parse_group_lines(artifact.path.read_bytes(), day) for day, artifact in sorted(found.items())
             if day <= h8.LAST_RELEASE}
    prints = h8.load_extract(extract_h8_groups.OUTPUT / h8.EXTRACT_NAME)
    lags = Counter((item.release_date - item.week_ending).days for item in prints)
    revisions = {}
    for field in h8.FIELDS:
        carried = {}
        for day, release in pages.items():
            for week, value in release.lines[field].weeks.items():
                carried.setdefault(week, []).append((day, value))
        deltas = []
        for item in prints:
            seen = carried[item.week_ending]
            deltas.append(seen[-1][1] - seen[0][1])
        moved = [d for d in deltas if abs(d) > 1e-9]
        revisions[field] = {
            "weeks": len(deltas), "carried_in_releases": sorted({len(carried[item.week_ending]) for item in prints}),
            "restated": len(moved), "max_abs_billion": round(max(abs(d) for d in deltas), 1),
            "mean_abs_billion_when_restated": round(sum(abs(d) for d in moved) / len(moved), 2) if moved else 0.0,
        }
    restatements = []
    days = sorted(pages)
    for before, after in zip(days, days[1:]):
        for field in h8.FIELDS:
            old, new = pages[before].lines[field].weeks, pages[after].lines[field].weeks
            for week in sorted(set(old) & set(new)):
                if old[week] and abs(new[week] - old[week]) / abs(old[week]) > args.threshold:
                    restatements.append({"release": after.isoformat(), "field": field, "week": week.isoformat(),
                                         "before": old[week], "after": new[week]})
    reclassified = []
    for before, after in zip(days, days[1:]):
        lines = {name: (pages[before].lines[name].weeks, pages[after].lines[name].weeks)
                 for name in ("h8_large_domestic_total_assets", "h8_small_domestic_total_assets")}
        weeks = sorted(set(lines["h8_large_domestic_total_assets"][0]) & set(lines["h8_large_domestic_total_assets"][1]))
        moves = [(lines["h8_large_domestic_total_assets"][1][w] - lines["h8_large_domestic_total_assets"][0][w],
                  lines["h8_small_domestic_total_assets"][1][w] - lines["h8_small_domestic_total_assets"][0][w], w)
                 for w in weeks]
        large, small, week = max(moves, key=lambda move: abs(move[0]))
        if abs(large) >= args.reclass and abs(small) >= args.reclass and large * small < 0:
            reclassified.append({"release": after.isoformat(), "week": week.isoformat(),
                                 "large_total_assets_change": round(large, 1), "small_total_assets_change": round(small, 1)})
    print(json.dumps({"first_print_lag_days": dict(sorted(lags.items())), "revisions": revisions,
                      "restatements_over_threshold": restatements, "threshold": args.threshold,
                      "group_reclassifications": reclassified, "reclass_threshold_billion": args.reclass}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
