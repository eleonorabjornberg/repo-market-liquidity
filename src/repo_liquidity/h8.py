"""First prints of the H.8 bank-group lines: cash assets and total assets of large domestic, small domestic and
foreign-related banks (#26, `docs/decisions/data-meaning.md` answers 6 and 17).

Each weekly H.8 release is archived at federalreserve.gov/releases/h8/YYYYMMDD/. Its not-seasonally-adjusted tables 7
(large domestically chartered banks), 9 (small) and 11 (foreign-related institutions) carry the lines `Cash assets` and
`Total assets` for the week ending Wednesday, in billions of dollars. A week is printed in four consecutive releases
and restated afterwards; only the **first print** is read, as for the parent's all-banks total assets
(`repo_model.ingest.parse_frb_h8_total_assets`, repo-market-model #115). That parser reads one table. The page
helpers, the release dataclass, the first-print rule and the release-date index are imported from it at the pin, not
copied; this module adds the table and line selection for the groups.

Never falls back to the latest vintage: a page that does not parse is a refusal, and so is a week missing between the
first and the last. Standard library only (the parent's `repo_model.data` is imported for `observations`).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

from repo_model import ingest, lockbox
from repo_model.ingest import FrbH8Release

from repo_liquidity import development

SOURCE_ID = "frb_h8_groups"
NEW_YORK = ZoneInfo("America/New_York")
#: The declared release time (the parent's `frb_h8` declaration, `ingest.FRB_H8_RELEASE_TIME`).
RELEASE_TIME = ingest.FRB_H8_RELEASE_TIME

#: The groups, by the title of the table that carries them (the not-seasonally-adjusted table has the same title as its
#: seasonally adjusted twin; the unit line tells them apart).
GROUPS: Mapping[str, str] = {
    "large_domestic": "Assets and Liabilities of Large Domestically Chartered Commercial Banks in the United States",
    "small_domestic": "Assets and Liabilities of Small Domestically Chartered Commercial Banks in the United States",
    "foreign_related": "Assets and Liabilities of Foreign-Related Institutions in the United States",
}
#: The lines, by the label the table prints (footnote marks stripped).
LINES: Mapping[str, str] = {"cash_assets": "Cash assets", "total_assets": "Total assets"}
UNIT = ingest._FRB_H8_UNIT

#: The registry fields, in the order the extract carries them.
FIELDS: Tuple[str, ...] = tuple(f"h8_{group}_{line}" for group in GROUPS for line in LINES)
_WHERE = {f"h8_{group}_{line}": (group, line) for group in GROUPS for line in LINES}

# The last release read is the day before the model repo's first locked tier (`repo-market-model
# docs/decisions/lockbox.md`), read from its lockbox by `development.development_end`; there is no copy of it here.
#: The first week of the extract: the newest week of the earliest release in range (5 January 2018).
FIRST_WEEK = date(2017, 12, 27)

EXTRACT_COLUMNS = ("week_ending", "release_date") + FIELDS + ("release_sha256",)
EXTRACT_NAME = "h8_group_first_print.csv"
RELEASES_NAME = "h8_group_first_print.releases.json"


@dataclass(frozen=True)
class GroupRelease:
    """One archived page: the dates it states, and each group line as the parent's `FrbH8Release`."""

    release_date: date
    stated_time: Optional[time]
    stated_date: Optional[date]
    lines: Mapping[str, FrbH8Release]

    @property
    def public_on(self) -> date:
        """The later of the archive date and the date the page states, as the parent dates a release."""
        return self.lines[FIELDS[0]].public_on


def parse_group_lines(payload: bytes, release_date: date) -> GroupRelease:
    """The six group lines from one archived H.8 page.

    Each line is read from the one table whose preamble carries the group's title and the not-seasonally-adjusted unit
    line, by its label. The week columns are the header cells that read as a month and a day, dated by the release (the
    parent's `_frb_h8_week`), and the values are the line's last cells, one per week.

    Raises:
        ValueError: unless every group has exactly one `Cash assets` and one `Total assets` line in the tables carrying
            its title, a number for every week column, and distinct ascending Wednesdays that are the same in every
            table.
    """
    page = payload.decode("utf-8", errors="strict")
    page = re.sub(r"<script\b.*?</script>", "", page, flags=re.S | re.I)
    header = ingest._frb_h8_text(page[:200000])
    stated = ingest._FRB_H8_STATED_TIME_RE.search(header)
    stated_time = None if stated is None else time(int(stated.group(1)) % 12 + 12, int(stated.group(2)))
    stated_day = ingest._FRB_H8_STATED_DATE_RE.search(header)
    stated_date = None if stated_day is None else datetime.strptime(stated_day.group(1), "%B %d, %Y").date()
    found: Dict[str, list] = {group: [] for group in GROUPS}
    previous = 0
    for table in re.finditer(r"<table\b.*?</table>", page, flags=re.S | re.I):
        preamble = ingest._frb_h8_text(page[previous:table.start()])[-600:]
        previous = table.end()
        if UNIT not in preamble:
            continue
        for group, title in GROUPS.items():
            if title in preamble:
                found[group].append(table.group(0))
    lines: Dict[str, FrbH8Release] = {}
    columns = None
    for group, tables in found.items():
        if not tables:
            raise ValueError(f"H.8 {release_date}: no table titled {GROUPS[group]!r} with the unit {UNIT!r}")
        # Before the 2020s layout a table runs over two pages, each with its own header: the group's lines are
        # spread over the tables carrying its title, and each line is read from the one that has it.
        parsed = []
        for table in tables:
            rows = [[ingest._frb_h8_text(cell) for cell in re.findall(r"<t[hd]\b.*?</t[hd]>", row, flags=re.S | re.I)]
                    for row in re.findall(r"<tr\b.*?</tr>", table, flags=re.S | re.I)]
            labels = [cells for cells in rows if cells and all(ingest._FRB_H8_WEEK_RE.match(cell) for cell in cells)]
            if len(labels) != 1:
                raise ValueError(f"H.8 {release_date}: a {group} table has {len(labels)} week-ending header rows, "
                                 f"not one")
            weeks = [ingest._frb_h8_week(label, release_date) for label in labels[0]]
            if weeks != sorted(set(weeks)) or any(week.weekday() != 2 for week in weeks):
                raise ValueError(f"H.8 {release_date}: week columns {[w.isoformat() for w in weeks]} of a {group} "
                                 f"table are not distinct ascending Wednesdays")
            if columns is None:
                columns = weeks
            elif weeks != columns:
                raise ValueError(f"H.8 {release_date}: a {group} table's weeks differ from the other tables'")
            parsed.append((rows, weeks))
        for line, label in LINES.items():
            matches = [(cells, weeks) for rows, weeks in parsed for cells in rows
                       if len(cells) > 1 and re.sub(r"(\s+\d+)+$", "", cells[1]) == label]
            if len(matches) != 1:
                raise ValueError(f"H.8 {release_date}: found {len(matches)} {label!r} lines in the {group} tables, "
                                 f"not exactly one")
            cells, weeks = matches[0]
            if len(cells) < 2 + len(weeks):
                raise ValueError(f"H.8 {release_date}: the {group} {label!r} line has {len(cells) - 2} values for "
                                 f"{len(weeks)} week columns")
            values = cells[len(cells) - len(weeks):]
            lines[f"h8_{group}_{line}"] = FrbH8Release(
                release_date=release_date, stated_time=stated_time, stated_date=stated_date,
                weeks={week: ingest._frb_h8_number(raw, release_date, week) for week, raw in zip(weeks, values)})
    return GroupRelease(release_date=release_date, stated_time=stated_time, stated_date=stated_date, lines=lines)


def check_stated_release_time(day: date, stated_time: Optional[time]) -> None:
    """Refuse a page that states a release time other than the declared one (the parent's rule, same direction).

    Raises:
        ValueError: if the page states a time other than `RELEASE_TIME`.
    """
    if stated_time is not None and stated_time != RELEASE_TIME:
        raise ValueError(f"the H.8 release of {day} states {stated_time}, not the declared {RELEASE_TIME}")


@dataclass(frozen=True)
class FirstPrint:
    """One week's six group values as first printed, the release that printed them and that page's digest."""

    week_ending: date
    release_date: date
    values: Mapping[str, float]
    release_sha256: str


def first_prints(releases: Iterable[Tuple[GroupRelease, str]]) -> List[FirstPrint]:
    """The first print of every week, from `(GroupRelease, sha256)` pairs, by the parent's rule for one line.

    A week's first print is its values in the earliest release that carries it; all six lines of a week come from
    that one release. Each line goes through `ingest.frb_h8_first_prints`.

    Raises:
        ValueError: if two pages are given for one release date, or the six lines disagree on the release that first
            printed a week.
    """
    pairs = list(releases)
    by_field = {field: ingest.frb_h8_first_prints([(release.lines[field], sha) for release, sha in pairs])
                for field in FIELDS}
    reference = by_field[FIELDS[0]]
    for field in FIELDS[1:]:
        if [(p.week_ending, p.release_date) for p in by_field[field]] != [(p.week_ending, p.release_date) for p in reference]:
            raise ValueError(f"H.8: {field} was first printed in different releases from {FIELDS[0]}")
    return [FirstPrint(week_ending=ref.week_ending, release_date=ref.release_date,
                       values={field: by_field[field][i].value for field in FIELDS},
                       release_sha256=ref.release_sha256)
            for i, ref in enumerate(reference)]


def write_extract(prints: Iterable[FirstPrint]) -> bytes:
    """The tracked CSV: one row per week, values to one decimal as the page prints them."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXTRACT_COLUMNS)
    for item in prints:
        writer.writerow((item.week_ending.isoformat(), item.release_date.isoformat())
                        + tuple(format(item.values[field], ".1f") for field in FIELDS) + (item.release_sha256,))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[FirstPrint]:
    """The tracked extract, checked against its manifest.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `EXTRACT_COLUMNS`, or the weeks are not
            consecutive Wednesdays.
    """
    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXTRACT_COLUMNS:
            raise ValueError(f"{path.name}: columns {reader.fieldnames} are not {list(EXTRACT_COLUMNS)}")
        prints = [FirstPrint(week_ending=date.fromisoformat(row["week_ending"]),
                             release_date=date.fromisoformat(row["release_date"]),
                             values={field: float(row[field]) for field in FIELDS},
                             release_sha256=row["release_sha256"]) for row in reader]
    for before, after in zip(prints, prints[1:]):
        if after.week_ending - before.week_ending != timedelta(days=7):
            raise ValueError(f"the extract skips from {before.week_ending} to {after.week_ending}")
    return prints


def available_at(release_date: date) -> datetime:
    """The instant a release is public: 16:15 New York time on its release date."""
    return datetime.combine(release_date, RELEASE_TIME, tzinfo=NEW_YORK)


def worst_case_lag_days(prints: Iterable[FirstPrint]) -> int:
    """The longest gap, in calendar days, from a week's Wednesday to its first print's release."""
    return max((item.release_date - item.week_ending).days for item in prints)


def check_declared_lag(entry: Mapping, prints: Iterable[FirstPrint]) -> None:
    """Refuse a declaration under which some first print would be read before its release, or any later than needed.

    The declared lag is the measured maximum and not above it (the registry's own note says so): every value is public
    no earlier than declared, and no later than the slowest release makes necessary.

    Raises:
        ValueError: if the declaration is not record_date / calendar_days.
        LookAheadError: naming the first week released after its declared availability.
        StaleReadError: if the declared lag is longer than the longest release lag in the extract.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    prints = list(prints)
    lag = entry["release_lag"]
    if lag.get("basis") != "record_date" or lag.get("unit") != "calendar_days":
        raise ValueError(f"an H.8 source must be declared record_date/calendar_days, not {lag}")
    moment = time.fromisoformat(lag["available_time"])
    for item in prints:
        declared = datetime.combine(item.week_ending + timedelta(days=int(lag["days"])), moment)
        published = datetime.combine(item.release_date, RELEASE_TIME)
        if published > declared:
            raise LookAheadError(f"the week ending {item.week_ending} was released {published}, after its declared "
                                 f"availability {declared}")
    if int(lag["days"]) > worst_case_lag_days(prints):
        raise StaleReadError(f"the declared lag of {lag['days']} days is longer than the {worst_case_lag_days(prints)} "
                             f"days the slowest release in the extract took: values would be read later than needed")


def check_first_prints(prints: Iterable[FirstPrint], releases: Mapping) -> None:
    """Refuse an extract that reads a week from any release but the earliest that carries it.

    `releases` is the extract's `.releases.json`: for each release the page carries `weeks`. A week read from a later
    release is a revised value, not the first print (`ingest.frb_h8_first_prints`' rule, #115).

    Raises:
        ValueError: naming the first week read from a later release than the earliest one that carries it, or read from
            a release the record does not list.
    """
    earliest: Dict[str, str] = {}
    for record in sorted(releases["releases"], key=lambda record: record["public_on"]):
        for week in record["weeks"]:
            earliest.setdefault(week, record["public_on"])
    for item in prints:
        week = item.week_ending.isoformat()
        if earliest.get(week) != item.release_date.isoformat():
            raise ValueError(f"the week ending {week} is read from the release of {item.release_date}, but the earliest "
                             f"release that carries it is {earliest.get(week)}")

def observations(prints: Iterable[FirstPrint], field: str, *, source_sha: str):
    """One field of an extract as the parent's point-in-time rows: dated the Wednesday, public at the release."""
    from repo_model.data import PointInTimeObservation

    if field not in _WHERE:
        raise ValueError(f"{field!r} is not an H.8 group field; they are {list(FIELDS)}")
    return [PointInTimeObservation(series_id=field, ref_date=item.week_ending,
                                   available_at=available_at(item.release_date), value=item.values[field],
                                   vintage_id=f"h8-{item.release_date.isoformat()}", source_sha=source_sha)
            for item in prints]


# ---------------------------------------------------------------------------------------------------------------
# Breaks: the H.8 "Notes on Data" archive (`docs/decisions/data-meaning.md`, answer 17(c))

NOTES_URL = "https://www.federalreserve.gov/releases/h8/h8notes.htm"
BREAKS_PATH = Path(__file__).resolve().parents[2] / "docs" / "research" / "h8-group-breaks.json"
NOTES_PAGE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "h8_notes" / "h8notes.htm.gz"

#: The kind of a note, by the phrase that opens it. A note that matches none is refused, not guessed: it is read.
_KINDS = (
    ("thrift_conversion", re.compile(r"conversions? of (?:a )?thrifts?", re.I)),
    ("nonbank_acquisition", re.compile(r"\bacquired\b|acquisition of assets and liabilities of nonbank", re.I)),
    ("nonbank_divestiture", re.compile(r"\bdivested\b", re.I)),
    ("accounting_standard", re.compile(r"adoption of FASB", re.I)),
    ("reporting_reclassification", re.compile(r"clarification of reporting instructions", re.I)),
)
_NOTE_DATE = re.compile(r'<a name="notes_(\d{8})">')
_AMOUNT = re.compile(r"\$(\d+(?:\.\d+)?) billion")


def _scope(text: str) -> str:
    """Whose balance sheet the note says moved, in its own words: the H.8 notes do not split large from small."""
    lowered = text.lower()
    if "foreign-related" in lowered:
        return "foreign_related"
    if "domestically chartered" in lowered or "domestic commercial banks" in lowered:
        return "domestic"
    return "commercial_banks"


def parse_notes(payload: bytes, first: date = FIRST_WEEK, last: Optional[date] = None) -> List[dict]:
    """The dated events of the H.8 notes archive page, oldest first, from `first` to `last` (both as-of dates).
    `last` defaults to the development tier's end, the day before the model repo's first locked tier.

    Each `datanote` block is one note: its heading is the as-of date, its paragraphs the text. The block's headings are
    checked against the page's own index of notes, so a block the split missed is an error, not a gap.

    Raises:
        LookAheadError: if `last` is given and is a day the model repo's lockbox holds.
        ValueError: if a note's date is not a Wednesday, the blocks do not match the index, or a note's opening matches
            none of `_KINDS` (a new kind of break is for a reader to classify).
    """
    if last is None:
        last = development.development_end() or date.max
    else:
        lockbox.require_unlocked([last], where="h8.parse_notes")
    page = payload.decode("utf-8", errors="strict")
    index = re.findall(r'<a href="#notes_(\d{8})">', page)
    blocks = page.split('<div class="datanote">')[1:]
    dates = []
    events = []
    for block in blocks:
        match = _NOTE_DATE.search(block)
        if match is None:
            raise ValueError("an H.8 notes block has no dated heading")
        stamp = match.group(1)
        as_of = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))
        dates.append(stamp)
        if not first <= as_of <= last:
            continue
        if as_of.weekday() != 2:
            raise ValueError(f"the H.8 note of {as_of} is not as of a Wednesday")
        body = block[match.end():].split("</center>", 1)[1]
        text = ingest._frb_h8_text(body.split("</div>")[0])
        kinds = [name for name, pattern in _KINDS if pattern.search(text[:500])]
        if not kinds:
            raise ValueError(f"the H.8 note of {as_of} matches no known kind: {text[:120]!r}")
        amounts = _AMOUNT.findall(text)
        events.append({"as_of": as_of.isoformat(), "kinds": kinds, "scope": _scope(text),
                       "first_amount_billion": float(amounts[0]) if amounts else None, "text": text})
    if dates != index:
        raise ValueError(f"the H.8 notes page indexes {len(index)} notes and has {len(dates)} blocks, or in another order")
    return sorted(events, key=lambda event: event["as_of"])



# ---------------------------------------------------------------------------------------------------------------
# Moves between the large and small groups: structural breaks in the group input (#47; answer 17(c), her Q18 ruling)

MOVES_PATH = Path(__file__).resolve().parents[2] / "docs" / "research" / "h8-group-moves.json"
#: A move is labelled by a note that states its cause, or it is `unexplained`; nothing is labelled from memory.
CAUSE_STATUSES = ("cited", "unexplained")
#: The columns of the published `h8_groups` snapshot: the extract's, and the ids of the breaks that start at the week.
SNAPSHOT_COLUMNS: Tuple[str, ...] = EXTRACT_COLUMNS + ("break_ids",)


def check_moves(record: Mapping, notes_page: str) -> None:
    """Refuse a moves record that labels a move other than by a cited note or `unexplained`.

    A `cited` cause names the note's as-of date and quotes it; the quote must be in the saved notes page, verbatim.

    Raises:
        ValueError: naming the first move or failure whose cause is neither, or whose quote is not in the page.
    """
    text = ingest._frb_h8_text(notes_page)
    for item in list(record["moves"]) + list(record["failures_2023"]):
        cause = item["cause"]
        if cause.get("status") not in CAUSE_STATUSES:
            raise ValueError(f"{item['id']}: a cause is {' or '.join(CAUSE_STATUSES)}, not {cause.get('status')!r}")
        if cause["status"] == "cited" and (not cause.get("note_as_of") or not cause.get("quote")
                                           or cause["quote"] not in text):
            raise ValueError(f"{item['id']}: a cited cause names the note's date and quotes the saved notes page")


def load_moves(path: Path = MOVES_PATH, notes_path: Path = NOTES_PAGE) -> dict:
    """The tracked moves record, checked against the saved notes page.

    Raises:
        ValueError: as `check_moves`.
    """
    record = json.loads(path.read_text(encoding="utf-8"))
    check_moves(record, gzip.decompress(notes_path.read_bytes()).decode("utf-8"))
    return record


def break_flags(record: Mapping) -> Dict[date, str]:
    """The break weeks of a moves record: each week to the id of the move that starts at it.

    Raises:
        ValueError: if two moves start at one week.
    """
    flags: Dict[date, str] = {}
    for move in record["moves"]:
        week = date.fromisoformat(move["break_week"])
        if week in flags:
            raise ValueError(f"{flags[week]} and {move['id']} both start at the week ending {week}")
        flags[week] = move["id"]
    return flags


def difference(prints: Iterable[FirstPrint], field: str, start: date, end: date, record: Mapping) -> float:
    """`field` at week `end` less `field` at week `start`, refused when the weeks lie on two sides of a break.

    A level restated between the large and small groups moves them in opposite directions by the same amount: across a
    break week the difference is a change of basis, not a flow, and there is no adjustment here.

    Raises:
        ValueError: if either week is not in the extract, `end` is not after `start`, or a break week `w` has
            `start < w <= end`.
    """
    if field not in _WHERE:
        raise ValueError(f"{field!r} is not an H.8 group field; they are {list(FIELDS)}")
    by_week = {item.week_ending: item.values[field] for item in prints}
    for week in (start, end):
        if week not in by_week:
            raise ValueError(f"the week ending {week} is not in the extract")
    if end <= start:
        raise ValueError(f"the difference runs from {start} to a later week, not {end}")
    for week, move in sorted(break_flags(record).items()):
        if start < week <= end:
            raise ValueError(f"the difference from {start} to {end} spans the break at the week ending {week} ({move}): "
                             f"a change of basis between the large and small groups, not a flow")
    return by_week[end] - by_week[start]
