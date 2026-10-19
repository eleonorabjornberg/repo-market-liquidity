"""Due diligence for #43: what the FFIEC CDR bulk files say about "balances due from Federal Reserve Banks" (RC-A item 4).

Reads the "Call Reports -- Single Period" bulk zips (`FFIEC CDR Call Bulk All Schedules MMDDYYYY.zip`) saved in a
directory and, for each quarter, reports: how many filers carry the item (Schedule RC-A, mnemonics RCFD0090 consolidated
and RCON0090 domestic offices), their sum, the sum for the 25 largest filers by total assets (RCFD2170, else RCON2170),
how many of those 25 carry it, and how late the latest submission update is for the filers that carry it ("Last
Date/Time Submission Updated On" in `Call Bulk POR`; the latest, not the first). If `--reserves` names a
FRED/ALFRED WRESBAL csv (week-average reserve balances in millions of dollars), the sum is also shown beside the weekly
value for the week ending nearest the quarter-end. Nothing is scored, nothing is built from the output.

    python3 -I scripts/diagnostics/ffiec_rca_diligence.py DIRECTORY_WITH_ZIPS [--reserves WRESBAL.csv]

The top 25 here is by consolidated total assets of the Call Report filer, a stand-in for the Board's "top 25 domestically
chartered commercial banks by domestic assets" (data-meaning answer 17(c)); it is not the Board's panel.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path


def _table(archive: zipfile.ZipFile, fragment: str):
    header, rows = None, []
    for name in sorted(n for n in archive.namelist() if fragment in n):
        reader = csv.reader(io.StringIO(archive.read(name).decode("latin-1")), delimiter="\t", quotechar='"')
        head = next(reader)
        next(reader)  # the second line holds the item descriptions
        header = header or head
        rows += list(reader)
    return header, rows


def _value(row, index, item):
    """The consolidated (RCFD) figure, else the domestic-offices (RCON) one, in USD thousands; None if neither is filed."""
    for prefix in ("RCFD", "RCON"):
        position = index.get(prefix + item)
        if position is not None and position < len(row) and row[position].strip():
            return float(row[position])
    return None


def _reserves(path: Path):
    series = {}
    for row in csv.reader(path.open()):
        try:
            series[date.fromisoformat(row[0])] = float(row[1])
        except (ValueError, IndexError):
            continue
    return series


def quarter_report(path: Path, reserves=None) -> None:
    m = re.search(r"(\d{2})(\d{2})(\d{4})\.zip$", path.name)
    quarter_end = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    with zipfile.ZipFile(path) as archive:
        as_of = re.search(r"as of (\S+)", archive.read("Readme.txt").decode("latin-1")).group(1)
        _, por = _table(archive, "Bulk POR")
        rca_head, rca = _table(archive, "Schedule RCA ")
        rc_head, rc = _table(archive, "Schedule RC ")
    updated = {int(r[0]): datetime.fromisoformat(r[11]) for r in por}
    rc_index = {h: i for i, h in enumerate(rc_head)}
    assets = {int(r[0]): _value(r, rc_index, "2170") or 0.0 for r in rc}
    rca_index = {h: i for i, h in enumerate(rca_head)}
    frb = {}
    for row in rca:
        value = _value(row, rca_index, "0090")
        if value is not None:
            frb[int(row[0])] = value
    top = sorted(assets, key=assets.get, reverse=True)[:25]
    lags = sorted((updated[k].date() - quarter_end).days for k in frb if k in updated)
    total = sum(frb.values()) / 1e6
    print(f"\n== quarter ended {quarter_end}; file as of {as_of}")
    print(f"filers {len(por)}; RC-A rows {len(rca)}; carrying item 0090: {len(frb)}; sum {total:,.1f} bn; "
          f"25 largest by total assets: {sum(1 for k in top if k in frb)} carry it, sum {sum(frb.get(k, 0) for k in top) / 1e6:,.1f} bn")
    print(f"days from quarter-end to latest submission update, filers carrying 0090: median {statistics.median(lags)}, "
          f"max {lags[-1]}; more than 45 days: {sum(1 for d in lags if d > 45)} of {len(lags)}")
    if reserves:
        near = min(reserves, key=lambda d: abs((d - quarter_end).days))
        print(f"WRESBAL week ending {near}: {reserves[near] / 1e3:,.1f} bn; item 0090 sum is {100 * total / (reserves[near] / 1e3):.0f}% of it")


if __name__ == "__main__":
    args = sys.argv[1:]
    reserves = _reserves(Path(args[args.index("--reserves") + 1])) if "--reserves" in args else None
    for zip_path in sorted(Path(args[0]).glob("*.zip"), key=lambda p: p.name[-8:-4] + p.name[-12:-8]):
        quarter_report(zip_path, reserves)
