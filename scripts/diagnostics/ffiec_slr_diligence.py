"""Due diligence for #27: what the FFIEC CDR bulk files say about when a Call Report quarter became public.

Reads the "Call Reports -- Single Period" bulk zips (`FFIEC CDR Call Bulk All Schedules MMDDYYYY.zip`) saved in a
directory, and for each quarter reports, for the G-SIB depository subsidiaries and for all filers, the "Last
Date/Time Submission Updated On" column of the POR file against the quarter-end, and the Schedule RC-R Part I items
the SLR needs (tier 1 capital 8274 and total leverage exposure H015, read from the consolidated column RCFA, else the domestic-offices column RCOA). Nothing is scored.

    python3 -I scripts/diagnostics/ffiec_slr_diligence.py DIRECTORY_WITH_ZIPS
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

#: The G-SIBs' depository subsidiaries by IDRSSD (the Call Report's institution id), as named in the 12/31/2025 POR file.
GSIB_SUBSIDIARIES = {
    852218: "JPMorgan Chase Bank, N.A.",
    480228: "Bank of America, N.A.",
    476810: "Citibank, N.A.",
    451965: "Wells Fargo Bank, N.A.",
    2182786: "Goldman Sachs Bank USA",
    1456501: "Morgan Stanley Bank, N.A.",
    2489805: "Morgan Stanley Private Bank, N.A.",
    93619: "State Street Bank and Trust Company, N.A.",
    541101: "The Bank of New York Mellon",
}


def _table(archive: zipfile.ZipFile, fragment: str):
    names = [n for n in archive.namelist() if fragment in n]
    header, rows = None, []
    for name in sorted(names):
        reader = csv.reader(io.StringIO(archive.read(name).decode("latin-1")), delimiter="\t", quotechar='"')
        head = next(reader)
        next(reader)  # the second line holds the item descriptions
        header = header or head
        rows += list(reader)
    return header, rows


def _cell(row, index, item):
    """The item's cell, or an empty string when the row is short or the item is not on the form that quarter."""
    position = index.get(item)
    return row[position] if row is not None and position is not None and position < len(row) else ""


def quarter_report(path: Path) -> None:
    m = re.search(r"(\d{2})(\d{2})(\d{4})\.zip$", path.name)
    quarter_end = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    with zipfile.ZipFile(path) as archive:
        readme = archive.read("Readme.txt").decode("latin-1")
        as_of = re.search(r"as of (\S+)", readme).group(1)
        por_head, por = _table(archive, "Bulk POR")
        rcri_head, rcri = _table(archive, "Schedule RCRI ")
    updated = {int(r[0]): datetime.fromisoformat(r[11]) for r in por}
    lags = sorted((u.date() - quarter_end).days for u in updated.values())
    late = sum(1 for d in lags if d > 45)
    print(f"\n== quarter ended {quarter_end}; file as of {as_of}")
    print(f"filers {len(lags)}; days from quarter-end to last submission update: median {statistics.median(lags)}, "
          f"max {lags[-1]}; updated more than 45 days after quarter-end: {late} ({100 * late / len(lags):.1f}%)")
    index = {h: i for i, h in enumerate(rcri_head)}
    by_id = {int(r[0]): r for r in rcri}
    for idrssd, name in GSIB_SUBSIDIARIES.items():
        if idrssd not in updated:
            print(f"  {name} ({idrssd}): not a filer in this file")
            continue
        row = by_id.get(idrssd)
        t1, exposure = (_cell(row, index, "RCFA" + item) or _cell(row, index, "RCOA" + item) for item in ("8274", "H015"))
        print(f"  {name} ({idrssd}): last updated {updated[idrssd]:%Y-%m-%d %H:%M} "
              f"(+{(updated[idrssd].date() - quarter_end).days} days); tier 1 capital {t1 or 'blank'}; "
              f"total leverage exposure {exposure or 'blank'} (USD thousands)")


if __name__ == "__main__":
    for zip_path in sorted(Path(sys.argv[1]).glob("*.zip")):
        quarter_report(zip_path)
