#!/usr/bin/env python3
"""Fetch the NY Fed's repo operation results for 2019-09-17 to 2021-07-28 and save them as tracked fixtures.

    PYTHONPATH=src python3 scripts/fetch_temp_repo.py

Needs network access to markets.newyorkfed.org (the endpoint the parent's `nyfed_srf` snapshots come from). Each
search response is saved unmodified, with a sha256 manifest, by `repo_liquidity.fed_repo.write_snapshot`. The panel
reads only the saved files. Standard library only.
"""

import sys
import time
import urllib.request
from datetime import date, datetime, timezone

from repo_liquidity import fed_repo

WINDOWS = ((date(2019, 9, 17), date(2019, 12, 31)), (date(2020, 1, 1), date(2020, 12, 31)),
           (date(2021, 1, 1), date(2021, 7, 28)))


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "repo-market-liquidity (research)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except OSError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not fetch {url}")


def main():
    for first, last in WINDOWS:
        payload = fetch(fed_repo.URL.format(first=first.isoformat(), last=last.isoformat()))
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path = fed_repo.write_snapshot(payload, first, last, retrieved)
        print(path.name, len(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
