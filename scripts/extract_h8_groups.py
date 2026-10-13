#!/usr/bin/env python3
"""Cut the tracked H.8 group first-print extract out of the archive snapshots (#26).

The archive pages are the parent's: `repo_model.ingest.fetch_frb_h8_archive` saves the release-date index and every
archived release page in range, unmodified and checksummed, under a raw root outside the tree (the pages are about
0.7 MB each and several hundred of them, so they are not tracked, as in the parent). From each page this reads the six
group lines (`repo_liquidity.h8.parse_group_lines`) and keeps each week's **first print**.

    # fetch (needs network access to federalreserve.gov; one request per release, paced by the parent):
    python3 -c "from pathlib import Path; from repo_model import ingest; \\
        ingest.fetch_frb_h8_archive(Path('RAW'), '2018-01-01', '2026-09-30')"
    PYTHONPATH=src python3 scripts/extract_h8_groups.py --raw-root RAW
    PYTHONPATH=src python3 scripts/extract_h8_groups.py --raw-root RAW --check

Written under `tests/fixtures/snapshots/h8_groups/`:
- `h8_group_first_print.csv`: one row per week, `week_ending`, `release_date`, six values, `release_sha256`;
- its snapshot manifest `<extract>.manifest.json`;
- `h8_group_first_print.releases.json`: per release, its date, URL, SHA-256, size, retrieval time and the time and date the
  page states (`null` where it states none), the weeks the page carries and the weeks first printed in it.

Refuses, before writing: a release the index lists in range that has no snapshot, or two snapshots of one release with
different bytes; a page that does not parse to the six lines; a page that states a release time other than the declared
16:15; a week missing between the first and the last; and a week first printed later than `frb_h8_groups.release_lag`
declares. A release after 2026-09-03 (`h8.LAST_RELEASE`, the day the blind tier starts after) is not read. Never falls
back to a later vintage. `--check` re-cuts and compares with the committed files, writing nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from repo_model import ingest
from repo_model.ingest import SnapshotArtifact, load_snapshot_manifest

from repo_liquidity import h8

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/snapshots/h8_groups"


def _release_date(url: str) -> date:
    if not url.startswith(ingest.FRB_H8_ARCHIVE_URL) or not url.endswith("/"):
        raise ValueError(f"{url} is not an H.8 archive release page")
    stamp = url[len(ingest.FRB_H8_ARCHIVE_URL):-1]
    return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))


def snapshots(raw_root: Path):
    """The index (latest retrieval) and one artifact per release date (earliest retrieval)."""
    index, releases = None, {}
    for manifest in sorted((raw_root / ingest.FRB_H8_SOURCE_ID).glob("*.manifest.json")):
        artifact = load_snapshot_manifest(manifest)
        if artifact.url == ingest.FRB_H8_RELEASE_DATES_URL:
            if index is None or artifact.retrieved_at > index.retrieved_at:
                index = artifact
            continue
        day = _release_date(artifact.url)
        earlier = releases.get(day)
        if earlier is not None and earlier.sha256 != artifact.sha256:
            raise ValueError(f"two snapshots of the H.8 release of {day} differ: {earlier.sha256} and {artifact.sha256}")
        if earlier is None or artifact.retrieved_at < earlier.retrieved_at:
            releases[day] = artifact
    if index is None:
        raise ValueError(f"no H.8 release-date index under {raw_root / ingest.FRB_H8_SOURCE_ID}")
    return index, releases


def cut(raw_root: Path, start: date, end: date, declared_days: int):
    index, found = snapshots(raw_root)
    listed = [day for day in ingest.parse_frb_h8_release_dates(index.path.read_bytes()) if start <= day <= end]
    # A listed Friday the archive files under the Thursday before it (a Friday holiday) is that Thursday's snapshot.
    served = {}
    for day in listed:
        thursday = day - timedelta(days=1)
        if day in found:
            served[day] = day
        elif thursday in found and thursday not in listed:
            served[day] = thursday
    missing = [day for day in listed if day not in served]
    if missing:
        raise ValueError(f"{len(missing)} H.8 release(s) listed in range have no snapshot, first {missing[0]}")
    parsed, records = [], []
    for listed_day in listed:
        day = served[listed_day]
        artifact = found[day]
        release = h8.parse_group_lines(artifact.path.read_bytes(), day)
        if day != listed_day and release.stated_date != day:
            raise ValueError(f"the H.8 index lists {listed_day}; the page under {day} states {release.stated_date}")
        h8.check_stated_release_time(day, release.stated_time)
        parsed.append((release, artifact.sha256))
        records.append({
            "release_date": day.isoformat(),
            "listed_date": listed_day.isoformat(),
            "stated_release_date": None if release.stated_date is None else release.stated_date.isoformat(),
            "public_on": release.public_on.isoformat(),
            "url": artifact.url,
            "sha256": artifact.sha256,
            "byte_count": artifact.byte_count,
            "retrieved_at": artifact.retrieved_at,
            "stated_release_time": None if release.stated_time is None
            else release.stated_time.isoformat(timespec="minutes"),
            "weeks": [week.isoformat() for week in sorted(release.lines[h8.FIELDS[0]].weeks)],
        })
    prints = h8.first_prints(parsed)
    # The earliest release in range also carries three older weeks, whose first prints were in releases before the
    # range; only its newest week is a first print here.
    earliest = max(next(iter(parsed[0][0].lines.values())).weeks)
    prints = [item for item in prints if item.week_ending >= earliest and item.release_date <= h8.LAST_RELEASE]
    for before, after in zip(prints, prints[1:]):
        if (after.week_ending - before.week_ending).days != 7:
            raise ValueError(f"H.8 first prints skip from {before.week_ending} to {after.week_ending}")
    for item in prints:
        lag = (item.release_date - item.week_ending).days
        if lag > declared_days:
            raise ValueError(f"the week ending {item.week_ending} was first printed on {item.release_date}, {lag} days "
                             f"on, later than the {declared_days} days frb_h8_groups.release_lag declares")
    records = [record for record in records if record["public_on"] <= h8.LAST_RELEASE.isoformat()]
    printed = {}
    for item in prints:
        printed.setdefault(item.release_date.isoformat(), []).append(item.week_ending.isoformat())
    for record in records:
        record["first_printed_weeks"] = printed.get(record["public_on"], [])
    extract = h8.write_extract(prints)
    manifest = SnapshotArtifact(
        source_id=h8.SOURCE_ID,
        path=Path(h8.SOURCE_ID) / h8.EXTRACT_NAME,
        retrieved_at=max(record["retrieved_at"] for record in records),
        sha256=hashlib.sha256(extract).hexdigest(),
        url=ingest.FRB_H8_ARCHIVE_URL,
        byte_count=len(extract),
    ).as_dict()
    releases = {
        "index": {"url": index.url, "sha256": index.sha256, "retrieved_at": index.retrieved_at},
        "start": start.isoformat(),
        "end": h8.LAST_RELEASE.isoformat(),
        "releases": records,
    }
    summary = {
        "releases": len(records),
        "weeks": len(prints),
        "first_week": prints[0].week_ending.isoformat(),
        "last_week": prints[-1].week_ending.isoformat(),
        "first_print_lag_days": sorted({(item.release_date - item.week_ending).days for item in prints}),
        "stated_release_times": sorted({str(record["stated_release_time"]) for record in records}),
    }
    return {
        h8.EXTRACT_NAME: extract,
        h8.EXTRACT_NAME + ".manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        h8.RELEASES_NAME: (json.dumps(releases, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    declared = h8.overlay()[h8.SOURCE_ID]["release_lag"]["days"]
    files, summary = cut(args.raw_root, args.start, args.end, int(declared))
    if args.check:
        stale = [name for name, payload in files.items()
                 if not (args.output / name).is_file() or (args.output / name).read_bytes() != payload]
        print(json.dumps({**summary, "stale": stale}, indent=2))
        return 1 if stale else 0
    args.output.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (args.output / name).write_bytes(payload)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
