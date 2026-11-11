"""The primary dealers' fails to deliver and to receive US Treasuries, for H10's second declaration, step 2 (#209).

`docs/decisions/h10-method-2.md` section 1 declares `pd_fails_deliver_ust` (the driver) and `pd_fails_receive_ust` (declared,
not a driver). The source is the New York Fed's Primary Dealer Statistics, series `PDFTD-UST` and `PDFTR-UST`, weekly, cumulative
over the week to the Wednesday as-of date and published on the Thursday of the following week. Its declaration is
`declarations/nyfed_pd_fails.json` (six business days, 16:30), copied from the parent's `nyfed_pd_financing`.

**The extract.** `tests/fixtures/snapshots/pd_fails/pd_fails_extract.csv` is the two series' lines of the parent's tracked export
(`PARENT_EXPORT`, at the pin), copied byte for byte, less every week whose publication falls on a day the parent's lockbox
holds (the week of 2026-09-02 is published on 2026-09-10, after the development end). `scripts/extract_pd_fails.py` cuts it and
its manifest; the panel is built from the extract alone, with no network, as the H.4.1 column is. The export keeps no vintages: a
later restatement cannot be seen, and the six-business-day lag is the published schedule, not a measurement.

Standard library only, apart from the parent's point-in-time row and exceptions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence, Tuple
from zoneinfo import ZoneInfo

from repo_liquidity import development

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "tests" / "fixtures" / "snapshots" / "pd_fails"
EXTRACT_NAME = "pd_fails_extract.csv"
EXTRACT = DIR / EXTRACT_NAME
MANIFEST = DIR / (EXTRACT_NAME + ".manifest.json")
#: The parent's tracked Primary Dealer Statistics export (its `nyfed_fr2004` snapshot), relative to the parent's root.
PARENT_EXPORT = "tests/fixtures/snapshots/funding_inputs/nyfed_fr2004/20260914T003100Z_c98524ef8e48.csv"
URL = "https://markets.newyorkfed.org/api/pd/get/all/timeseries.csv"

SOURCE_ID = "nyfed_pd_fails"
#: The export's series name -> the panel column. Only the first is a driver (`h10_drivers_2.FAILS`); the second is declared.
FIELD_COLUMNS = {"PDFTD-UST": "pd_fails_deliver_ust", "PDFTR-UST": "pd_fails_receive_ust"}
DRIVER_FIELD = "PDFTD-UST"
DRIVER_COLUMN = FIELD_COLUMNS[DRIVER_FIELD]
HEADER = ("As Of Date", "Time Series", "Value (millions)")

#: The figures for a Wednesday as-of date are published on the Thursday of the following week, at 16:30 New York time
#: (`declarations/nyfed_pd_fails.json`; `h10_drivers_2.FAILS_PUBLISH_*` are the same constants, and a test says so).
PUBLISH_DAYS_AFTER_WEDNESDAY = 8
PUBLISH_TIME = time(16, 30)
NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Week:
    """One week of one series: the Wednesday as-of date, the series name and the figure in USD millions."""

    as_of: date
    field: str
    value_musd: int


def published_instant(as_of: date) -> datetime:
    """When the New York Fed publishes the week to the Wednesday `as_of`: the Thursday of the following week, 16:30.

    Raises:
        ValueError: `as_of` is not a Wednesday.
    """
    if as_of.weekday() != 2:
        raise ValueError(f"{as_of} is not a Wednesday; the Primary Dealer Statistics are as of Wednesdays")
    return datetime.combine(as_of + timedelta(days=PUBLISH_DAYS_AFTER_WEDNESDAY), PUBLISH_TIME, tzinfo=NEW_YORK)


def _lines(export: bytes) -> Tuple[bytes, List[bytes]]:
    lines = export.splitlines(keepends=True)
    return lines[0], lines[1:]


def cut_extract(export: bytes) -> Tuple[bytes, List[date]]:
    """The extract's bytes cut from the parent's `export`, and the as-of dates of the weeks left out.

    Keeps, byte for byte and in the export's order, the header and every line of `FIELD_COLUMNS`' two series, except a week whose
    publication falls on a day the parent's lockbox holds. A figure the Desk withheld (`*`) is refused, not skipped.

    Raises:
        ValueError: the header is not the export's, a kept figure is not a whole number of millions, or a figure is withheld.
    """
    header, body = _lines(export)
    if tuple(next(csv.reader(io.StringIO(header.decode("utf-8"))))) != HEADER:
        raise ValueError(f"the export's header is not {HEADER}")
    kept = [header]
    withheld = set()
    for line in body:
        as_of_text, field, value = next(csv.reader(io.StringIO(line.decode("utf-8"))))
        if field not in FIELD_COLUMNS:
            continue
        as_of = date.fromisoformat(as_of_text)
        if development.is_locked(published_instant(as_of).date()):
            withheld.add(as_of)
            continue
        if not value.lstrip("-").isdigit():
            raise ValueError(f"{field} for {as_of} is {value!r}, not a whole number of millions")
        kept.append(line)
    return b"".join(kept), sorted(withheld)


def load_extract(path: Path = EXTRACT) -> List[Week]:
    """The extract's weeks, after checking it is the bytes its manifest names and that no week is published on a locked day.

    Raises:
        ValueError: the extract is not its manifest's bytes, or a row is not a Wednesday, a known series or a whole number.
        LookAheadError: a week is published on a day the parent's lockbox holds.
    """
    from repo_model.splits import LookAheadError

    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest["extract_sha256"]:
        raise ValueError(f"{path.name} is not the bytes its manifest names")
    weeks = []
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        field, as_of = row[HEADER[1]], date.fromisoformat(row[HEADER[0]])
        if field not in FIELD_COLUMNS:
            raise ValueError(f"{path.name}: {field!r} is not one of {sorted(FIELD_COLUMNS)}")
        if not row[HEADER[2]].lstrip("-").isdigit():
            raise ValueError(f"{path.name}: {field} for {as_of} is {row[HEADER[2]]!r}")
        published = published_instant(as_of)
        if development.is_locked(published.date()):
            raise LookAheadError(f"{path.name}: the week of {as_of} is published on {published.date()}, a locked day")
        weeks.append(Week(as_of, field, int(row[HEADER[2]])))
    return weeks


def observations(weeks: Iterable[Week], *, source_sha: str, fields: Sequence[str] = (DRIVER_FIELD,)):
    """The weeks of `fields` as the parent's point-in-time rows: dated the Wednesday, in USD billions, public at the Thursday
    of the following week, 16:30. The series id is the field, as the parent maps it to the column (`declaration.FIELDS`)."""
    from repo_model.data import PointInTimeObservation

    return [
        PointInTimeObservation(
            series_id=week.field, ref_date=week.as_of, available_at=published_instant(week.as_of),
            value=week.value_musd / 1000.0, vintage_id=f"nyfed-pd-{week.as_of.isoformat()}", source_sha=source_sha)
        for week in weeks if week.field in fields
    ]


def check_declared_lag(registry: Mapping[str, Mapping], dates: Sequence[date], rows) -> None:
    """Refuse a declaration under which some week would be read before it was published.

    Each row's `available_at` is compared with the parent's `asof.declared_availability` for its field on the panel's
    dates. A week whose Wednesday is not a panel date cannot be read, and is skipped. (A week declared available later than it
    was published is stale, not a leak, and is not refused here: `h10_drivers_2.check_declared_fails_lag` holds that side.)

    Raises:
        LookAheadError: a week is declared available before it was published.
    """
    from repo_model.asof import declared_availability
    from repo_model.splits import LookAheadError

    position = {day: index for index, day in enumerate(dates)}
    for row in rows:
        if row.ref_date not in position:
            continue
        declared = declared_availability(registry, SOURCE_ID, row.series_id, dates, position[row.ref_date])
        public = row.available_at.astimezone(NEW_YORK).replace(tzinfo=None)
        if declared is None or public > declared:
            raise LookAheadError(
                f"{row.series_id} for the week of {row.ref_date} is public at {public:%Y-%m-%d %H:%M}, after its declared "
                f"availability of {declared:%Y-%m-%d %H:%M}" if declared else
                f"{row.series_id} for the week of {row.ref_date} has no declared availability")
