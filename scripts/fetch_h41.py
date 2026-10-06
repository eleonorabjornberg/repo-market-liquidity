#!/usr/bin/env python3
"""Fetch archived H.4.1 releases and write the tracked first-print extract.

    PYTHONPATH=src python3 scripts/fetch_h41.py --first 2017-12-27 --last 2026-09-02

Needs network access to federalreserve.gov. Each week's release is found in the eight days after its Wednesday,
parsed by `repo_liquidity.h41.parse_release`, and recorded with its URL and the page's sha256. A week whose
release cannot be found or parsed is listed and the script exits non-zero: a gap is reported, never filled.
Standard library only.
"""

import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from repo_liquidity import h41

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tests/fixtures/snapshots/h41/h41_treasury_first_print.csv"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "repo-market-liquidity (research)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not fetch {url}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=date.fromisoformat, required=True)
    parser.add_argument("--last", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    if args.first.weekday() != 2 or args.last.weekday() != 2:
        parser.error("--first and --last must be Wednesdays")
    rows, gaps = [], []
    week = args.first
    while week <= args.last:
        found = h41.find_release(week, fetch)
        if found is None:
            gaps.append(f"{week}: no release found")
        else:
            release_date, url, page = found
            try:
                release = h41.parse_release(page, release_date=release_date)
                if release.week_ended != week:
                    raise ValueError(f"page reports week ended {release.week_ended}")
                rows.append((week.isoformat(), release_date.isoformat(), url,
                             hashlib.sha256(page.encode("utf-8")).hexdigest(), release.week_average,
                             release.change_from_prior_week, release.wednesday_level))
            except ValueError as error:
                gaps.append(f"{week}: {error}")
        print(week, "ok" if not gaps or not gaps[-1].startswith(str(week)) else gaps[-1], flush=True)
        week += timedelta(days=7)
    if gaps:
        print("GAPS:", *gaps, sep="\n", file=sys.stderr)
        return 1
    digest = h41.write_extract(rows, EXTRACT)
    print(f"wrote {EXTRACT.relative_to(ROOT)} sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
