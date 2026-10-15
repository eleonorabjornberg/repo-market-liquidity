"""First prints of the Fed's U.S. Treasury securities held outright, from archived H.4.1 releases.

Each weekly H.4.1 release, archived at federalreserve.gov/releases/h41/YYYYMMDD/, is read once, as published. Its
table 1 row "U.S. Treasury securities" gives the week average, the change from the previous week as printed in that
same release, and the Wednesday level, in millions of dollars. A release is its own first print, so no later
revision can reach a value read here.

The extract (`tests/fixtures/snapshots/h41/h41_treasury_first_print.csv`) is written by `scripts/fetch_h41.py`
from the live archive and tracked with a sha256 manifest; the panel is built from the extract alone, with no
network. Standard library only.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

from repo_liquidity import contenthash

ARCHIVE = "https://www.federalreserve.gov/releases/h41/{stamp}/"

#: The release time, New York, as the release pages and the Board's release calendar state it.
RELEASE_TIME = time(16, 30)
NEW_YORK = ZoneInfo("America/New_York")

#: The column the panel carries: the change from the previous week in the week average, as printed.
SERIES = "soma_treasury_weekly_change"
#: The same for the MBS row (`docs/stages/stage-1a-correction.md`, item 1).
MBS_SERIES = "soma_mbs_weekly_change"

#: The same for the "Federal agency debt securities" row (#30; answer 15 of `docs/decisions/data-meaning.md`).
AGENCY_SERIES = "soma_agency_debt_weekly_change"
#: Agency debt plus MBS, week by week from the same release: Nicholas Beroud's "agency securities" (answer 15), the
#: definition the Fed's caps and its reinvestment into bills use.
AGENCY_SECURITIES_SERIES = "soma_agency_securities_weekly_change"

#: Table 1 rows the parser reads.
TREASURY_ROW = "U.S. Treasury securities"
MBS_ROW = "Mortgage-backed securities"
AGENCY_ROW = "Federal agency debt securities"
ROWS = {TREASURY_ROW: SERIES, MBS_ROW: MBS_SERIES, AGENCY_ROW: AGENCY_SERIES}

_NUMBERS = (
    # An optional footnote mark, printed "(4)" in older releases and a bare "4" in newer ones, then the four values.
    r"\s+(?:\(?\d{1,2}\)?\s+)?"
    r"(?P<average>[\d,]+)\s+"
    r"(?P<week>[+-]\s*[\d,]+|0)\s+"
    r"(?P<year>[+-]\s*[\d,]+|0)\s+"
    r"(?P<wednesday>[\d,]+)"
)
_ROW_PATTERNS = {label: re.compile(re.escape(label) + _NUMBERS) for label in ROWS}
_DATE = re.compile(r"\b([A-Z][a-z]{2,3})\.? (\d{1,2}), (\d{4})\b")
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "June": 6, "Jul": 7, "July": 7,
    "Aug": 8, "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


@dataclass(frozen=True)
class Release:
    week_ended: date
    release_date: date
    week_average: int
    change_from_prior_week: int
    wednesday_level: int


def _text(page: str) -> str:
    text = re.sub(r"<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(text))


def _signed(token: str) -> int:
    token = token.replace(" ", "").replace(",", "")
    return int(token)


def parse_release(page: str, *, release_date: date, row: str = TREASURY_ROW) -> Release:
    """One table 1 row (`TREASURY_ROW` or `MBS_ROW`) from one archived H.4.1 page.

    Raises:
        ValueError: if `row` is not one the parser reads, if the row or the week's date is not found, or if the week
            does not end on the Wednesday before the release.
    """
    if row not in _ROW_PATTERNS:
        raise ValueError(f"the parser reads {sorted(_ROW_PATTERNS)}, not {row!r}")
    text = _text(page)
    start = text.find("Averages of daily figures")
    if start < 0:
        start = text.find("Reserve Bank credit, related items")
    if start < 0:
        raise ValueError("no table 1 header in the page")
    match = _ROW_PATTERNS[row].search(text, start)
    if match is None:
        raise ValueError(f"no {row!r} row in table 1")
    week_ended = None
    for month, day, year in _DATE.findall(text[start:match.start()]):
        if month in _MONTHS:
            week_ended = date(int(year), _MONTHS[month], int(day))
            break
    if week_ended is None:
        raise ValueError("no week-ended date in table 1's header")
    if week_ended.weekday() != 2:
        raise ValueError(f"week ended {week_ended} is not a Wednesday")
    if not 0 < (release_date - week_ended).days <= 7:
        raise ValueError(f"release {release_date} is not in the week after {week_ended}")
    return Release(
        week_ended=week_ended,
        release_date=release_date,
        week_average=_signed(match["average"]),
        change_from_prior_week=_signed(match["week"]),
        wednesday_level=_signed(match["wednesday"]),
    )


def agency_securities(agency: Iterable[Release], mbs: Iterable[Release]) -> List[Release]:
    """Agency securities (answer 15): the agency-debt row plus the MBS row, each week, from the same release.

    Raises:
        ValueError: if the two extracts do not cover the same weeks of the same releases, in the same order.
    """
    agency, mbs = list(agency), list(mbs)
    if len(agency) != len(mbs):
        raise ValueError(f"{len(agency)} agency-debt weeks against {len(mbs)} MBS weeks")
    out = []
    for debt, backed in zip(agency, mbs):
        if (debt.week_ended, debt.release_date) != (backed.week_ended, backed.release_date):
            raise ValueError(f"agency debt is of the release of {debt.release_date} (week ended {debt.week_ended}), "
                             f"MBS of {backed.release_date} (week ended {backed.week_ended})")
        out.append(Release(
            week_ended=debt.week_ended,
            release_date=debt.release_date,
            week_average=debt.week_average + backed.week_average,
            change_from_prior_week=debt.change_from_prior_week + backed.change_from_prior_week,
            wednesday_level=debt.wednesday_level + backed.wednesday_level,
        ))
    return out


def available_at(release_date: date) -> datetime:
    """The instant a release is public: 16:30 New York time on its release date."""
    return datetime.combine(release_date, RELEASE_TIME, tzinfo=NEW_YORK)


# ---------------------------------------------------------------------------------------------------------------
# The tracked extract

#: `fetch_sha256` is the SHA-256 of the page as fetched: it identifies the fetch, not the release (finding #40; the
#: archive injects per-request tokens). `content_sha256` identifies the extracted values (`repo_liquidity.contenthash`).
EXTRACT_COLUMNS = (
    "week_ended", "release_date", "url", "fetch_sha256",
    "week_average_musd", "change_from_prior_week_musd", "wednesday_level_musd",
    "content_sha256",
)
#: The columns the content hash covers: the release's extracted values. Not the URL or the fetch hash, which say where
#: and when a page was read, not what it said.
CONTENT_COLUMNS = ("week_ended", "release_date", "week_average_musd", "change_from_prior_week_musd",
                   "wednesday_level_musd")
CONTENT_PLACES = {"week_average_musd": 0, "change_from_prior_week_musd": 0, "wednesday_level_musd": 0}


def row_content_sha256(row) -> str:
    """The content hash of one extract row (a mapping by column name): recomputed from its extracted values alone."""
    return contenthash.content_sha256(CONTENT_COLUMNS, [[row[column] for column in CONTENT_COLUMNS]], CONTENT_PLACES)


def write_extract(rows: Iterable[tuple], path: Path) -> str:
    """Write the extract and its manifest; return the extract's sha256.

    A row is `(week_ended, release_date, url, fetch_sha256, week_average, change, wednesday_level)`; the content hash is
    appended here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(EXTRACT_COLUMNS)
        for row in rows:
            named = dict(zip(EXTRACT_COLUMNS, row))
            writer.writerow(tuple(row) + (row_content_sha256(named),))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"path": path.name, "sha256": digest, "source": ARCHIVE.format(stamp="YYYYMMDD")}
    path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return digest


def load_extract(path: Path) -> List[Release]:
    """The tracked extract, checked against its manifest.

    Raises:
        ValueError: if the extract's bytes do not match its manifest, its columns are not `EXTRACT_COLUMNS`, a row's
            `content_sha256` is not the hash of its own values, or its weeks are not consecutive Wednesdays.
    """
    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    releases = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXTRACT_COLUMNS:
            raise ValueError(f"{path.name}: columns {reader.fieldnames} are not {list(EXTRACT_COLUMNS)}")
        for row in reader:
            if row["content_sha256"] != row_content_sha256(row):
                raise ValueError(f"{path.name}: the content_sha256 of the week ended {row['week_ended']} is not the hash "
                                 f"of its values")
            releases.append(Release(
                week_ended=date.fromisoformat(row["week_ended"]),
                release_date=date.fromisoformat(row["release_date"]),
                week_average=int(row["week_average_musd"]),
                change_from_prior_week=int(row["change_from_prior_week_musd"]),
                wednesday_level=int(row["wednesday_level_musd"]),
            ))
    for before, after in zip(releases, releases[1:]):
        if after.week_ended - before.week_ended != timedelta(days=7):
            raise ValueError(f"the extract skips from {before.week_ended} to {after.week_ended}")
    return releases


def worst_case_lag_days(releases: Iterable[Release]) -> int:
    """The longest gap, in calendar days, from a week's Wednesday to its release."""
    return max((release.release_date - release.week_ended).days for release in releases)


def observations(releases: Iterable[Release], *, source_sha: str, series: str = SERIES):
    """An extract as the parent's point-in-time rows: one per week, dated the Wednesday, public at release."""
    from repo_model.data import PointInTimeObservation

    return [
        PointInTimeObservation(
            series_id=series,
            ref_date=release.week_ended,
            available_at=available_at(release.release_date),
            value=release.change_from_prior_week / 1000.0,
            vintage_id=f"h41-{release.release_date.isoformat()}",
            source_sha=source_sha,
        )
        for release in releases
    ]


def find_release(week_ended: date, fetch) -> Optional[tuple]:
    """The first archived release in the eight days after `week_ended`, as (release_date, url, page)."""
    for offset in (1, 2, 3, 4, 5, 6, 7, 8):
        release_date = week_ended + timedelta(days=offset)
        url = ARCHIVE.format(stamp=release_date.strftime("%Y%m%d"))
        page = fetch(url)
        if page is not None and "U.S. Treasury securities" in page:
            return release_date, url, page
    return None


def check_declared_lag(entry, releases: Iterable[Release]) -> None:
    """Refuse a declaration under which some release would be read before it was published.

    Raises:
        LookAheadError: naming the first week released after its declared availability.
    """
    from repo_model.splits import LookAheadError

    lag = entry["release_lag"]
    if lag.get("basis") != "record_date" or lag.get("unit") != "calendar_days":
        raise ValueError(f"an H.4.1 source must be declared record_date/calendar_days, not {lag}")
    moment = time.fromisoformat(lag["available_time"])
    for release in releases:
        declared = datetime.combine(release.week_ended + timedelta(days=int(lag["days"])), moment)
        published = datetime.combine(release.release_date, RELEASE_TIME)
        if published > declared:
            raise LookAheadError(
                f"the week ended {release.week_ended} was released {published}, "
                f"after its declared availability {declared}")
