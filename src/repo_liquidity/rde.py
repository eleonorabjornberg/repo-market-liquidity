"""The New York Fed's reserve demand elasticity (RDE), an external check on H7m goalposts 1 and 3 (#132).

Groundwork for H7m under Eleonora's ruling of 19 October 2026 on Lens B of repo-market-model#958 ("We need both"): the
RDE is **reported and never deciding**. R and S stay the deciding benchmarks of `docs/decisions/measurement-protocol.md`
section 5; the protocol does not change, and nothing here is wired into a goalpost or a score.

- **The source.** The "Chart Data" workbook behind https://www.newyorkfed.org/research/reserve-demand-elasticity
  (`download-data`, one xlsx). Its sheet "chart data" holds one row per estimate date (about weekly, from 2010-01-20)
  with the 50th percentile of the elasticity (the main estimate) and the 2.5th, 97.5th, 16th and 84th percentiles; its
  cover sheet says "Updated on <day> for release on <day>". The workbook is saved as fetched, named by its SHA-256.
- **One vintage.** The page serves only the latest workbook. Earlier releases are not published, so a row's value is the
  one in the latest stored release, labelled `vintage = latest_release:<release date>`; if the Fed has revised an
  estimate since its first release, the first print is not recoverable here. A later fetch is stored beside this one and
  never replaces it (`scripts/extract_rde.py capture`).
- **Availability** (the ruling of 19 October 2026, with the launch press release of 17 October 2024 as its source: "The RDE
  will be updated around 10:00 A.M. Eastern Time on the third Thursday of each month, or on the first business day
  following a Federal Open Market Committee blackout period if the third Thursday of the month falls within the blackout
  period"). A release is public from 12:00 New York time, the conservative reading of "around 10:00", on the third
  Thursday, or when that day is inside an FOMC blackout (the second Saturday before a meeting through the day after it)
  on the first business day after the blackout, and never before the launch on 2024-10-17. The meetings are read from the
  Board's calendar page saved in this repository (`live.CALENDAR_PAGE`); the parent holds no meeting calendar at the pin
  (finding filed with the pull request). An estimate for date d is public at the first release whose data-as-of date is on
  or after d. Two as-of dates are recorded: Friday 11 October 2024 for the launch release (its press release: "include data
  as of Friday, October 11, 2024") and Monday 5 October 2026 for the release of 15 October 2026 (the stored workbook's cover
  sheet, "Updated on October 5 for release on October 15"). A release with no recorded as-of date is assumed to carry data
  as of `UNRECORDED_AS_OF_LAG_DAYS` before its third Thursday, the larger of the two recorded gaps (6 and 10 days). That is
  later than the truth for most estimates, which is staleness on the safe side, not leakage (a marked question for
  Eleonora on the pull request).
- **The table starts at the launch.** The table (the extract and the declaration) holds the estimates from the one the
  launch release headlined (the latest dated on or before its as-of date, 2024-10-09) onward. The estimates dated earlier
  are the back history the launch carried: they are published apart as a labelled series (`HISTORY_LABEL`, outside the
  declaration and read by nothing), because they are not a point-in-time series (all would be "public" on one day), and a
  declared lag covering them, years long, would leave the panel nothing to read.
- **Nothing past the development tier.** A row whose assigned release falls on a day the parent's lockbox holds is
  withheld and listed in the coverage record; the loader refuses an extract that holds one (`LookAheadError`).

Standard library only (the parent's `repo_model` is imported for the exception classes and the point-in-time row).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from repo_liquidity import contenthash, development, live

SOURCE_ID = "nyfed_rde"
URL = "https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/elasticity/download-data"
PAGE_URL = "https://www.newyorkfed.org/research/reserve-demand-elasticity"
NEW_YORK = ZoneInfo("America/New_York")

#: The third Thursday of October 2024, the day the Fed launched the product (press release of 17 October 2024).
LAUNCH_DATE = date(2024, 10, 17)
#: The release press release says "around 10:00 A.M."; availability is declared at 12:00, the conservative reading (the
#: ruling of 19 October 2026). It is still before the 16:00 decision.
RELEASE_TIME = time(12, 0)
LAUNCH = datetime.combine(LAUNCH_DATE, RELEASE_TIME, tzinfo=NEW_YORK)
#: The releases whose data-as-of date is recorded, by their third Thursday: the launch ("The first RDE estimates, released
#: today, include data as of Friday, October 11, 2024") and the stored workbook's ("Updated on October 5 for release on
#: October 15", 2026).
AS_OF_RECORDED = {date(2024, 10, 17): date(2024, 10, 11), date(2026, 10, 15): date(2026, 10, 5)}
#: A release with no recorded as-of date is read as carrying data as of this many days before its third Thursday: the larger
#: of the two recorded gaps (6 days at the launch, 10 in October 2026). A declared conservative lag, not a source.
UNRECORDED_AS_OF_LAG_DAYS = 10

VINTAGE_PREFIX = "latest_release"
SHEET = "chart data"
COVER = "Cover Sheet"
#: The header of the sheet, in order: the date, then the five percentiles of the elasticity.
HEADER = ("Date", "Elasticity - 50th percentile (main)", "Elasticity - 2.5th percentile",
          "Elasticity - 97.5th percentile", "Elasticity - 16th percentile", "Elasticity - 84th percentile")
#: The declared fields, one per percentile column. The 95% interval is the 2.5th to the 97.5th percentile.
FIELDS: Tuple[str, ...] = ("rde_elasticity", "rde_lower_95", "rde_upper_95", "rde_lower_68", "rde_upper_68")
PLACES = 6
EXTRACT_COLUMNS: Tuple[str, ...] = (
    "estimate_date", "vintage", "available_from", "elasticity_p50", "elasticity_p2_5", "elasticity_p97_5",
    "elasticity_p16", "elasticity_p84", "sign", "interval_excludes_zero_95", "fetch_sha256", "content_sha256")
VALUE_COLUMNS = EXTRACT_COLUMNS[3:8]
CONTENT_COLUMNS = ("estimate_date",) + VALUE_COLUMNS
#: The estimates before the launch release's headline, apart from the table (the ruling of 19 October 2026).
HISTORY_LABEL = "history, not public before 2024-10-17"
HISTORY_COLUMNS: Tuple[str, ...] = ("estimate_date", "series", "elasticity_p50", "elasticity_p2_5", "elasticity_p97_5",
                                    "elasticity_p16", "elasticity_p84", "fetch_sha256", "content_sha256")
HISTORY_NAME = "rde_history.csv"
VALUE_COLUMNS_HISTORY = HISTORY_COLUMNS[2:7]
EXTRACT_NAME = "rde_estimates.csv"
CAPTURES_NAME = "rde_captures.json"
COVERAGE_NAME = "rde_estimates.coverage.json"
HASH_NOTE = ("fetch_sha256 identifies the stored workbook; content_sha256 identifies the row's date and five "
             "values, as six-place decimals")
_MONTHS = {name: number for number, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
     "December"), start=1)}
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_EXCEL_DAY_ZERO = date(1899, 12, 30)


def third_thursday(year: int, month: int) -> date:
    """The third Thursday of the month."""
    first = date(year, month, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 14)


@lru_cache(maxsize=None)
def fomc_meetings() -> Tuple[Tuple[date, date], ...]:
    """The scheduled FOMC meetings (first day, last day) in the Board's calendar page saved in this repository.

    A row whose dates are not two days of a meeting (a notation vote, such as 22 August 2025) is not a meeting.

    Raises:
        ValueError: if the saved page does not match its manifest, or holds no meeting.
    """
    page = live.CALENDAR_PAGE
    manifest = json.loads(page.with_name(page.name + ".manifest.json").read_text(encoding="utf-8"))
    raw = page.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise ValueError(f"{page.name} does not match its manifest")
    parts = re.split(r'<a id="\d+">(\d{4}) FOMC Meetings</a>', gzip.decompress(raw).decode("utf-8"))
    meetings = []
    for year, body in zip(parts[1::2], parts[2::2]):
        for month, days in re.findall(r'fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
                                      body, re.S):
            match = re.fullmatch(r"(\d+)-(\d+)\*?", days.strip())
            if match is None:
                continue
            names = [name.strip() for name in month.split("/")]
            first_month, last_month = _month_number(names[0]), _month_number(names[-1])
            meetings.append((date(int(year), first_month, int(match.group(1))), date(int(year), last_month, int(match.group(2)))))
    if not meetings:
        raise ValueError(f"{page.name} holds no FOMC meeting")
    return tuple(sorted(meetings))


def _month_number(name: str) -> int:
    for number, full in enumerate(_MONTHS, start=1):
        if full.startswith(name[:3]):
            return number
    raise ValueError(f"{name!r} is not a month")


def blackout(first_day: date, last_day: date) -> Tuple[date, date]:
    """The FOMC blackout of a meeting: from the second Saturday before its first day through the day after its last."""
    saturday = first_day - timedelta(days=(first_day.weekday() - 5) % 7 or 7)
    return saturday - timedelta(days=7), last_day + timedelta(days=1)


def nominal_release_day(year: int, month: int) -> date:
    """The third Thursday, the release day before the blackout fallback."""
    return third_thursday(year, month)


def release_day(year: int, month: int) -> date:
    """The day the month's release is public: its third Thursday, or, when that day is inside an FOMC blackout, the first
    business day after the blackout (the launch press release of 17 October 2024).

    Raises:
        ValueError: if the saved FOMC calendar does not cover the year, so a blackout could be missed.
    """
    from repo_model.data import next_business_day

    covered = {first.year for first, _ in fomc_meetings()}
    if year not in covered:
        raise ValueError(f"the saved FOMC calendar covers {min(covered)} to {max(covered)}, not enough to place the "
                         f"release of {year}-{month:02d}")
    nominal = nominal_release_day(year, month)
    for first, last in fomc_meetings():
        start, end = blackout(first, last)
        if start <= nominal <= end:
            return next_business_day(end, 1)
    return nominal


def as_of_date(year: int, month: int) -> date:
    """The day the month's release carries data as of: the recorded one, or `UNRECORDED_AS_OF_LAG_DAYS` before its third
    Thursday."""
    nominal = nominal_release_day(year, month)
    return AS_OF_RECORDED.get(nominal, nominal - timedelta(days=UNRECORDED_AS_OF_LAG_DAYS))


def release_for(estimate_date: date) -> datetime:
    """The release at which the estimate dated `estimate_date` is read as public (see the module note).

    The first release whose data is as of the estimate's date or later, at 12:00 New York time on its release day, and
    never before the launch.
    """
    year, month = max((estimate_date.year, estimate_date.month), (LAUNCH_DATE.year, LAUNCH_DATE.month))
    while as_of_date(year, month) < estimate_date:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return datetime.combine(release_day(year, month), RELEASE_TIME, tzinfo=NEW_YORK)


def launch_headline(estimate_dates: Iterable[date]) -> date:
    """The estimate the launch release headlined: the latest dated on or before the launch release's as-of date.

    Raises:
        ValueError: if no estimate is dated that early.
    """
    cutoff = AS_OF_RECORDED[LAUNCH_DATE]
    earlier = [day for day in estimate_dates if day <= cutoff]
    if not earlier:
        raise ValueError(f"no estimate is dated on or before {cutoff}, the launch release's data date")
    return max(earlier)


def split_back_history(rows: Sequence["Row"]) -> Tuple[List["Row"], List["Row"]]:
    """The rows from the launch headline onward (the table), and the back history before it."""
    headline = launch_headline(row.estimate_date for row in rows)
    return [row for row in rows if row.estimate_date >= headline], [row for row in rows if row.estimate_date < headline]


def _sign(value: Decimal) -> str:
    return "negative" if value < 0 else "positive" if value > 0 else "zero"


@dataclass(frozen=True)
class Row:
    """One estimate date's elasticity, as the latest stored release carries it."""

    estimate_date: date
    vintage: str
    elasticity_p50: Decimal
    elasticity_p2_5: Decimal
    elasticity_p97_5: Decimal
    elasticity_p16: Decimal
    elasticity_p84: Decimal
    fetch_sha256: str

    @property
    def available_from(self) -> datetime:
        return release_for(self.estimate_date)

    @property
    def sign(self) -> str:
        """The sign of the main estimate."""
        return _sign(self.elasticity_p50)

    @property
    def interval_excludes_zero_95(self) -> bool:
        """Whether the 95% interval lies wholly on one side of zero: the Fed's operational test for scarce reserves."""
        return self.elasticity_p97_5 < 0 or self.elasticity_p2_5 > 0

    @property
    def values(self) -> Tuple[Decimal, ...]:
        return (self.elasticity_p50, self.elasticity_p2_5, self.elasticity_p97_5, self.elasticity_p16,
                self.elasticity_p84)

    @property
    def content_sha256(self) -> str:
        return content_hash(self.estimate_date, self.values)


def available_at(row: Row) -> datetime:
    return row.available_from


def content_hash(estimate_date: date, values: Sequence[Decimal]) -> str:
    return contenthash.content_sha256(CONTENT_COLUMNS, [[estimate_date.isoformat(), *values]],
                                      {column: PLACES for column in VALUE_COLUMNS})


def _decimal(raw: str, where: str) -> Decimal:
    """A six-place decimal from a cell, refusing a value the sheet carries to more places than that."""
    exact = Decimal(repr(float(raw)))
    fixed = exact.quantize(Decimal(1).scaleb(-PLACES))
    if abs(exact - fixed) > Decimal("1e-9"):
        raise ValueError(f"{where}: {raw!r} has more than {PLACES} decimal places")
    return fixed


# ---------------------------------------------------------------------------------------------------------------
# Reading the workbook


def _sheets(archive: zipfile.ZipFile) -> Dict[str, str]:
    """Sheet name -> member path, from the workbook and its relationships."""
    book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    out = {}
    for sheet in book.find("m:sheets", _NS):
        target = targets[sheet.get(f"{{{_NS['r']}}}id")]
        out[sheet.get("name")] = "xl/" + target.lstrip("/").removeprefix("xl/")
    return out


def _cells(archive: zipfile.ZipFile, member: str, strings: Sequence[str]) -> List[Dict[str, str]]:
    """Each row of a sheet as {column letters: text of the cell}; a shared string is resolved."""
    rows = []
    for row in ElementTree.fromstring(archive.read(member)).iter(f"{{{_NS['m']}}}row"):
        cells = {}
        for cell in row.findall("m:c", _NS):
            value = cell.find("m:v", _NS)
            if value is None or value.text is None:
                continue
            letters = re.match(r"[A-Z]+", cell.get("r")).group(0)
            cells[letters] = strings[int(value.text)] if cell.get("t") == "s" else value.text
        rows.append(cells)
    return rows


def parse_workbook(payload: bytes) -> Tuple[List[Tuple[date, Tuple[Decimal, ...]]], dict]:
    """The estimates in a stored workbook, and what its cover sheet says about the release.

    Returns the (estimate date, five values) pairs in the sheet's order, and a dict with `update_date` and
    `release_date`, read from "Updated on <month> <day> for release on <month> <day>" with the year of the last estimate.

    Raises:
        ValueError: if the bytes are not an xlsx, the sheets or header are not the expected ones, a value is missing or
            carries more than six places, a date repeats or is out of order, or the cover sheet's dates do not fit the
            last estimate or the third Thursday of the release month.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise ValueError("the RDE file is not an xlsx") from error
    with archive:
        sheets = _sheets(archive)
        for name in (SHEET, COVER):
            if name not in sheets:
                raise ValueError(f"the RDE workbook has no sheet named {name!r}; it has {sorted(sheets)}")
        strings = ["".join(t.text or "" for t in item.iter(f"{{{_NS['m']}}}t"))
                   for item in ElementTree.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", _NS)]
        table = _cells(archive, sheets[SHEET], strings)
        cover = " ".join(text for row in _cells(archive, sheets[COVER], strings) for text in row.values())
    head = next((i for i, row in enumerate(table) if row.get("A") == HEADER[0]), None)
    if head is None or tuple(table[head].get(letter) for letter in "ABCDEF") != HEADER:
        raise ValueError(f"the RDE sheet's header is not {list(HEADER)}")
    estimates: List[Tuple[date, Tuple[Decimal, ...]]] = []
    for row in table[head + 1:]:
        missing = [letter for letter in "ABCDEF" if letter not in row]
        if missing:
            raise ValueError(f"the RDE sheet has a row with no value in column(s) {missing}: {row}")
        day = _EXCEL_DAY_ZERO + timedelta(days=int(float(row["A"])))
        if estimates and day <= estimates[-1][0]:
            raise ValueError(f"the RDE sheet's dates are not strictly increasing at {day}")
        estimates.append((day, tuple(_decimal(row[letter], f"{day} {letter}") for letter in "BCDEF")))
    if not estimates:
        raise ValueError("the RDE sheet holds no estimates")
    match = re.search(r"Updated on (\w+) (\d+) for release on (\w+) (\d+)", cover)
    if match is None:
        raise ValueError("the RDE cover sheet has no 'Updated on <day> for release on <day>' line")
    year = estimates[-1][0].year
    try:
        updated = date(year, _MONTHS[match.group(1)], int(match.group(2)))
        released = date(year, _MONTHS[match.group(3)], int(match.group(4)))
    except (KeyError, ValueError) as error:
        raise ValueError(f"the RDE cover sheet's dates are not read: {match.group(0)!r}") from error
    if updated != estimates[-1][0]:
        raise ValueError(f"the cover sheet says updated {updated}; the last estimate is dated {estimates[-1][0]}")
    if released != release_day(released.year, released.month):
        raise ValueError(f"the cover sheet's release on {released} is not the release day of its month "
                         f"({release_day(released.year, released.month)}, the third Thursday or the day the blackout ends)")
    return estimates, {"update_date": updated, "release_date": released}


def rows_from_workbook(payload: bytes) -> Tuple[List[Row], dict]:
    """The workbook's rows, each labelled with the release it was read from and the workbook's digest."""
    estimates, cover = parse_workbook(payload)
    digest = hashlib.sha256(payload).hexdigest()
    vintage = f"{VINTAGE_PREFIX}:{cover['release_date'].isoformat()}"
    return [Row(day, vintage, *values, digest) for day, values in estimates], cover


def withhold_locked(rows: Iterable[Row]) -> Tuple[List[Row], List[dict]]:
    """The rows whose assigned release is not on a day the parent's lockbox holds, and a hole for each that is."""
    kept: List[Row] = []
    holes: List[dict] = []
    for row in rows:
        if development.is_locked(row.available_from.date()):
            holes.append({"estimate_date": row.estimate_date.isoformat(), "reason": "released_after_development_end",
                          "detail": f"read as public from {row.available_from.isoformat()}, on a day the parent's "
                                    f"lockbox holds"})
        else:
            kept.append(row)
    return kept, holes


# ---------------------------------------------------------------------------------------------------------------
# The extract


def write_extract(rows: Iterable[Row]) -> bytes:
    """The tracked CSV: one row per estimate date, oldest first."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXTRACT_COLUMNS)
    for row in sorted(rows, key=lambda r: r.estimate_date):
        writer.writerow((row.estimate_date.isoformat(), row.vintage, row.available_from.isoformat(),
                         *(f"{value:.{PLACES}f}" for value in row.values), row.sign,
                         str(row.interval_excludes_zero_95).lower(), row.fetch_sha256, row.content_sha256))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against the rules that built it.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `EXTRACT_COLUMNS`, a date is listed
            twice, a row is not labelled with a `latest_release:` vintage, or a stored derived column (availability,
            sign, interval flag, content hash) is not what the values give.
        LookAheadError: if a row's assigned release is on a day the parent's lockbox holds.
    """
    from repo_model.splits import LookAheadError

    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXTRACT_COLUMNS:
            raise ValueError(f"{path.name}: columns {reader.fieldnames} are not {list(EXTRACT_COLUMNS)}")
        stored = list(reader)
    rows: List[Row] = []
    seen = set()
    for item in stored:
        row = Row(date.fromisoformat(item["estimate_date"]), item["vintage"],
                  *(Decimal(item[column]) for column in VALUE_COLUMNS), item["fetch_sha256"])
        if row.estimate_date in seen:
            raise ValueError(f"{path.name}: {row.estimate_date} is listed twice")
        seen.add(row.estimate_date)
        if not row.vintage.startswith(VINTAGE_PREFIX + ":"):
            raise ValueError(f"{path.name}: {row.estimate_date} is labelled {row.vintage!r}, not {VINTAGE_PREFIX}:<date>")
        for column, expected in (("available_from", row.available_from.isoformat()), ("sign", row.sign),
                                 ("interval_excludes_zero_95", str(row.interval_excludes_zero_95).lower()),
                                 ("content_sha256", row.content_sha256)):
            if item[column] != expected:
                raise ValueError(f"{path.name}: {row.estimate_date} stores {column} {item[column]!r}, the values give "
                                 f"{expected!r}")
        if development.is_locked(row.available_from.date()):
            raise LookAheadError(f"{row.estimate_date} is read from {row.available_from}, on a day the parent's "
                                 f"lockbox holds")
        rows.append(row)
    return rows


def write_history(rows: Iterable[Row]) -> bytes:
    """The tracked CSV of the estimates before the table: labelled, with no availability column, oldest first."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HISTORY_COLUMNS)
    for row in sorted(rows, key=lambda r: r.estimate_date):
        writer.writerow((row.estimate_date.isoformat(), HISTORY_LABEL, *(f"{value:.{PLACES}f}" for value in row.values),
                         row.fetch_sha256, row.content_sha256))
    return buffer.getvalue().encode("utf-8")


def load_history(path: Path) -> List[Row]:
    """The history series, checked against its manifest and the rules that built it. Nothing reads it as of an instant.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `HISTORY_COLUMNS`, a row is not labelled
            `HISTORY_LABEL`, a date is listed twice or out of order, or a stored content hash is not what the values give.
    """
    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != HISTORY_COLUMNS:
            raise ValueError(f"{path.name}: columns {reader.fieldnames} are not {list(HISTORY_COLUMNS)}")
        stored = list(reader)
    rows: List[Row] = []
    for item in stored:
        if item["series"] != HISTORY_LABEL:
            raise ValueError(f"{path.name}: {item['estimate_date']} is labelled {item['series']!r}, not {HISTORY_LABEL!r}")
        row = Row(date.fromisoformat(item["estimate_date"]), HISTORY_LABEL,
                  *(Decimal(item[column]) for column in VALUE_COLUMNS_HISTORY), item["fetch_sha256"])
        if rows and row.estimate_date <= rows[-1].estimate_date:
            raise ValueError(f"{path.name}: {row.estimate_date} is listed twice or out of order")
        if item["content_sha256"] != row.content_sha256:
            raise ValueError(f"{path.name}: {row.estimate_date} stores content_sha256 {item['content_sha256']!r}, the values "
                             f"give {row.content_sha256!r}")
        rows.append(row)
    return rows


def worst_case_lag_days(rows: Iterable[Row]) -> int:
    """The longest gap, in calendar days, from an estimate date to the day it is read as public."""
    return max((row.available_from.date() - row.estimate_date).days for row in rows)


def check_declared_lag(entry: Mapping, rows: Iterable[Row]) -> None:
    """Refuse a declaration under which some estimate would be read before its release, or any later than needed.

    The declared lag is the measured maximum and not above it, as for the SLR and the H.8 groups.

    Raises:
        ValueError: if the declaration is not record_date / calendar_days.
        LookAheadError: naming the first estimate available after its declared availability.
        StaleReadError: if the declared lag is longer than the longest in the extract.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    lag = entry["release_lag"]
    if lag.get("basis") != "record_date" or lag.get("unit") != "calendar_days":
        raise ValueError(f"an RDE source must be declared record_date/calendar_days, not {lag}")
    moment = time.fromisoformat(lag["available_time"])
    for row in rows:
        declared = datetime.combine(row.estimate_date + timedelta(days=int(lag["days"])), moment, tzinfo=NEW_YORK)
        if row.available_from > declared:
            raise LookAheadError(f"the estimate of {row.estimate_date} is available from {row.available_from}, after its "
                                 f"declared availability {declared}")
    worst = worst_case_lag_days(rows)
    if int(lag["days"]) > worst:
        raise StaleReadError(f"the declared lag of {lag['days']} days is longer than the {worst} days the slowest estimate "
                             f"in the extract took: values would be read later than needed")


# ---------------------------------------------------------------------------------------------------------------
# Reading as of an instant


def latest_public(rows: Iterable[Row], at: datetime) -> Optional[Row]:
    """The latest estimate public at `at`, or None.

    Raises:
        ValueError: if `at` has no time zone.
    """
    if at.tzinfo is None:
        raise ValueError("the decision instant must be timezone-aware")
    public = [row for row in rows if row.available_from <= at]
    return max(public, key=lambda row: row.estimate_date, default=None)


def read(rows: Iterable[Row], estimate_date: date, at: datetime) -> Row:
    """The estimate dated `estimate_date`, as read at the decision instant `at`.

    Raises:
        ValueError: if the date is not in the extract, or `at` has no time zone.
        LookAheadError: if the estimate's release is after `at`.
        StaleReadError: if a later estimate is already public at `at`.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    matches = [row for row in rows if row.estimate_date == estimate_date]
    if not matches:
        raise ValueError(f"no RDE estimate dated {estimate_date}")
    row = matches[0]
    latest = latest_public(rows, at)
    if row.available_from > at:
        raise LookAheadError(f"the estimate of {estimate_date} is available from {row.available_from}, after the "
                             f"decision instant {at}")
    if latest is not None and latest.estimate_date > estimate_date:
        raise StaleReadError(f"the estimate of {estimate_date} is read at {at}, when the one dated "
                             f"{latest.estimate_date} is already public")
    return row


def observations(rows: Iterable[Row], field: str, *, source_sha: str):
    """One field of the extract as the parent's point-in-time rows."""
    from repo_model.data import PointInTimeObservation

    pick = {"rde_elasticity": lambda r: r.elasticity_p50, "rde_lower_95": lambda r: r.elasticity_p2_5,
            "rde_upper_95": lambda r: r.elasticity_p97_5, "rde_lower_68": lambda r: r.elasticity_p16,
            "rde_upper_68": lambda r: r.elasticity_p84}.get(field)
    if pick is None:
        raise ValueError(f"{field!r} is not an RDE field; they are {list(FIELDS)}")
    return [PointInTimeObservation(series_id=field, ref_date=row.estimate_date, available_at=row.available_from,
                                   value=float(pick(row)), vintage_id=row.vintage, source_sha=source_sha)
            for row in rows]


def sign_changes(rows: Iterable[Row]) -> List[dict]:
    """The estimate dates at which the sign of the main estimate differs from the previous estimate's."""
    ordered = sorted(rows, key=lambda r: r.estimate_date)
    return [{"estimate_date": now.estimate_date.isoformat(), "from": before.sign, "to": now.sign,
             "read_from": now.available_from.isoformat()}
            for before, now in zip(ordered, ordered[1:]) if before.sign != now.sign]


def significance_changes(rows: Iterable[Row]) -> List[dict]:
    """The estimate dates at which the 95% interval starts or stops excluding zero."""
    ordered = sorted(rows, key=lambda r: r.estimate_date)
    return [{"estimate_date": now.estimate_date.isoformat(), "interval_excludes_zero_95": now.interval_excludes_zero_95,
             "read_from": now.available_from.isoformat()}
            for before, now in zip(ordered, ordered[1:])
            if before.interval_excludes_zero_95 != now.interval_excludes_zero_95]


def coverage(rows: Sequence[Row], holes: Sequence[dict], back_history: Sequence[Row]) -> Dict:
    """The rows read, those withheld and why, the back history left out, and the sign and significance changes."""
    return {"estimates_in_workbook": len(rows) + len(holes) + len(back_history), "rows": len(rows),
            "back_history": {"estimates": len(back_history), "first": back_history[0].estimate_date.isoformat(),
                             "last": back_history[-1].estimate_date.isoformat()} if back_history else None,
            "first_estimate": rows[0].estimate_date.isoformat(), "last_estimate": rows[-1].estimate_date.isoformat(),
            "first_read_from": rows[0].available_from.isoformat(), "last_read_from": rows[-1].available_from.isoformat(),
            "worst_case_lag_days": worst_case_lag_days(rows), "withheld": len(holes),
            "withheld_estimates": list(holes), "sign_changes": sign_changes(rows),
            "significance_changes": significance_changes(rows)}
