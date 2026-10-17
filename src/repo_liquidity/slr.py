"""SLR headroom of the nine G-SIB depository subsidiaries, from the latest-filed Call Reports (#63, G5 for H7m).

`docs/decisions/data-meaning.md` row 16 defines the measure and Eleonora's ruling of 13 October 2026 (reading 2 of
`docs/research/slr-headroom-due-diligence.md`) sets the vintage: the FFIEC CDR bulk files carry only the **latest-filed**
figures, so each (bank, quarter) value is a labelled, amended figure (`vintage = latest_filed`), available only from its
"Last Date/Time Submission Updated On" time (the `Call Bulk POR` file) and never earlier. It is not a first print.

- **The figures.** Tier 1 capital (Schedule RC-R Part I item 8274) and total leverage exposure (item H015), in USD
  thousands, from the consolidated column (`RCFA`), else the domestic-offices column (`RCOA`); the reported
  supplementary leverage ratio (item H036) is kept beside the ratio computed from the two and checked against it.
- **The measure.** `slr_pct = 100 * tier 1 capital / total leverage exposure`; `headroom_pp = slr_pct - requirement_pct`.
  The requirement is read from `REQUIREMENT_TABLE` (`docs/decisions/slr-requirement.md`, a draft for Eleonora): 6% for
  quarter-ends from 2018-01-01 to 2026-03-31 (the enhanced ratio at G-SIB subsidiaries) and, from 2026-04-01, a value the
  rule leaves to each bank, so those quarters carry the ratio and **no headroom**; before 2018 the table has no entry. All
  nine banks are in the main measure (`measure`): State Street is read at the bank of the G-SIB, IDRSSD 35301 (Eleonora,
  15 October 2026, replacing her decision on #69, Q2, which was made on the figures of the wrong institution).
- **No aggregate.** Row 16 names no way to combine the nine banks; the extract is one row per bank and quarter.
- **Availability.** A row is public from the start of the day after its latest-update date, in New York. The update
  time carries no time zone and the posting lag is not recorded, so the whole day is skipped, which is later than the
  truth and so the safe side. `FIELDS` are declared in `declarations/ffiec_call_slr.json` at the measured worst-case
  lag, as for the H.8 groups; `read` is the exact, row-by-row reader.
- **Nothing past the development tier.** A figure last updated on a day the parent's lockbox holds is withheld and
  listed in the coverage record; the loader refuses an extract that contains one (`LookAheadError`).

Standard library only (the parent's `repo_model` is imported for the lockbox, the exception classes and the point-in-time
row).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from repo_liquidity import development

SOURCE_ID = "ffiec_call_slr"
NEW_YORK = ZoneInfo("America/New_York")
VINTAGE = "latest_filed"

#: The G-SIBs' depository subsidiaries by IDRSSD (the Call Report's institution id), as named in the 12/31/2025 POR file
#: and in PR #44's note.
BANKS: Mapping[int, str] = {
    852218: "JPMorgan Chase Bank, N.A.",
    480228: "Bank of America, N.A.",
    476810: "Citibank, N.A.",
    451965: "Wells Fargo Bank, N.A.",
    2182786: "Goldman Sachs Bank USA",
    1456501: "Morgan Stanley Bank, N.A.",
    2489805: "Morgan Stanley Private Bank, N.A.",
    # Not 93619, State Street Bank and Trust Company, N.A.: a non-depository trust subsidiary of about $65 million that
    # PR #67 read by mistake (its tier 1 capital is close to its exposure, so its ratio was near 100%).
    35301: "State Street Bank and Trust Company",
    541101: "The Bank of New York Mellon",
}

#: Schedule RC-R Part I items, as PR #44's note maps them. Row 16(a): "take them from the current instructions"; that
#: check is not made here (`docs/research/slr-headroom-coverage.md`, "Not checked").
TIER1_ITEM, EXPOSURE_ITEM, REPORTED_RATIO_ITEM = "8274", "H015", "H036"
COLUMN_FORMS = ("RCFA", "RCOA")



@dataclass(frozen=True)
class RequirementPeriod:
    """One period of the requirement table (`docs/decisions/slr-requirement.md`, a draft for Eleonora).

    `start` is the first quarter-end date the period covers; `end` is the first date it does not (None: open-ended).
    `requirement_pct` is None where the rule leaves the value to each bank, so the headroom is left blank.
    """

    start: date
    end: Optional[date]
    requirement_pct: Optional[float]
    citation: str


#: The requirement in force on a quarter-end (#71, Q1; row 16(b)). Quarter-ends before 2018-01-01 have no entry, and the
#: headroom of a quarter with no entry is blank. Each row is quoted in `docs/decisions/slr-requirement.md`, which is
#: DRAFT until Eleonora merges it; `RequirementTableTests` checks that the two agree.
REQUIREMENT_TABLE: Tuple[RequirementPeriod, ...] = (
    RequirementPeriod(date(2018, 1, 1), date(2026, 4, 1), 6.0, "12 CFR 6.4(c)(1)(iv)(B), as added at 79 FR 24539 (May 1, 2014)"),
    RequirementPeriod(date(2026, 4, 1), None, None, "12 CFR 3.10(a)(1)(v) and 3.11(c)(2)(v), as amended at 90 FR 55287 and 55288 (Dec. 1, 2025)"),
)


def _checked(table: Sequence[RequirementPeriod]) -> Sequence[RequirementPeriod]:
    previous: Optional[RequirementPeriod] = None
    for period in table:
        if period.end is not None and period.end <= period.start:
            raise ValueError(f"requirement period {period.start} to {period.end} ends before it starts")
        if previous is not None and (previous.end is None or previous.end > period.start):
            raise ValueError(f"requirement periods overlap or are out of order at {period.start}")
        previous = period
    return table


def requirement_for(quarter_end: date, table: Optional[Sequence[RequirementPeriod]] = None) -> Optional[float]:
    """The requirement, in percent, that the table puts in force on `quarter_end`, or None (no period, or no value).

    Raises:
        ValueError: if the table's periods overlap, are out of order, or end before they start.
    """
    for period in _checked(REQUIREMENT_TABLE if table is None else table):
        if quarter_end >= period.start and (period.end is None or quarter_end < period.end):
            return period.requirement_pct
    return None


def headroom_for(slr_pct: float, quarter_end: date, table: Optional[Sequence[RequirementPeriod]] = None) -> Optional[float]:
    """The ratio minus the requirement in force on `quarter_end`, or None where the table has no requirement."""
    required = requirement_for(quarter_end, table)
    return None if required is None else round(slr_pct - required, 4)


#: Eleonora's decision on #69, Q2 (14 October 2026) kept State Street outside the main measure as a labelled sensitivity.
#: Those figures were the trust subsidiary's (IDRSSD 93619), not the bank's. With the bank read (IDRSSD 35301) she put
#: State Street in the main measure (15 October 2026), so no bank is a sensitivity. The label stays defined, so a stored
#: row that carries it is refused by `load_extract`.
MAIN, SENSITIVITY = "main", "sensitivity_state_street"
SENSITIVITY_BANKS: Tuple[int, ...] = ()
#: Row 16(e): the temporary exclusion of reserves and Treasuries ran from April 2020 to March 2021 (automatic for holding
#: companies, elected by subsidiaries). The quarter-ends inside it, whose election status is flagged unknown.
EXCLUSION_QUARTERS = (date(2020, 6, 30), date(2020, 9, 30), date(2020, 12, 31), date(2021, 3, 31))
#: Floating-point and rounding slack between the computed ratio and the reported one, which is printed to 4 decimals.
RATIO_TOLERANCE_PP = 0.0006

FIELDS: Tuple[str, ...] = ("slr_tier1_capital", "slr_total_leverage_exposure", "slr_ratio", "slr_headroom")
EXTRACT_COLUMNS: Tuple[str, ...] = (
    "quarter_end", "idrssd", "institution", "vintage", "latest_update", "available_from", "column_form",
    "tier1_capital_kusd", "total_leverage_exposure_kusd", "reported_slr_pct", "slr_pct", "requirement_pct",
    "headroom_pp", "exclusion_status", "measure", "source_zip_sha256")
EXTRACT_NAME = "slr_latest_filed.csv"
SOURCES_NAME = "slr_latest_filed.sources.json"
COVERAGE_NAME = "slr_latest_filed.coverage.json"

#: Why a (bank, quarter) is missing from the extract, or kept with a column blank or flagged.
REFUSALS = ("not_a_filer", "item_blank", "updated_after_development_end", "tier1_exceeds_exposure")
KEPT_WITH_NOTE = ("requirement_not_set", "exclusion_status_unknown", "ratio_differs_from_reported")


@dataclass(frozen=True)
class Row:
    """One bank's latest-filed figures for one quarter."""

    quarter_end: date
    idrssd: int
    institution: str
    latest_update: datetime
    column_form: str
    tier1_capital_kusd: int
    total_leverage_exposure_kusd: int
    reported_slr_pct: Optional[float]
    source_zip_sha256: str

    @property
    def slr_pct(self) -> float:
        return round(100.0 * self.tier1_capital_kusd / self.total_leverage_exposure_kusd, 4)

    @property
    def requirement_pct(self) -> Optional[float]:
        """The requirement the table puts in force on the quarter-end, or None (see `REQUIREMENT_TABLE`)."""
        return requirement_for(self.quarter_end)

    @property
    def headroom_pp(self) -> Optional[float]:
        return headroom_for(self.slr_pct, self.quarter_end)

    @property
    def measure(self) -> str:
        """`main`, or the labelled State Street sensitivity (#71, Q2)."""
        return SENSITIVITY if self.idrssd in SENSITIVITY_BANKS else MAIN

    @property
    def exclusion_status(self) -> str:
        return "unknown" if self.quarter_end in EXCLUSION_QUARTERS else ""

    @property
    def available_from(self) -> datetime:
        """The start of the day after the latest update, New York time (see the module note)."""
        return datetime.combine(self.latest_update.date() + timedelta(days=1), time.min, tzinfo=NEW_YORK)


def available_at(row: Row) -> datetime:
    return row.available_from


# ---------------------------------------------------------------------------------------------------------------
# Reading the bulk files


def _table(archive: zipfile.ZipFile, fragment: str) -> Tuple[List[str], List[List[str]]]:
    """The tab-delimited schedule(s) whose file name contains `fragment`: header names and rows (the second line of
    each file holds item descriptions and is skipped)."""
    names = sorted(name for name in archive.namelist() if fragment in name)
    if not names:
        raise ValueError(f"the bulk file has no schedule named {fragment!r}")
    header: List[str] = []
    rows: List[List[str]] = []
    for name in names:
        reader = csv.reader(io.StringIO(archive.read(name).decode("latin-1")), delimiter="\t", quotechar='"')
        head = next(reader)
        next(reader)
        header = header or head
        rows += list(reader)
    return header, rows


def _cell(row: Optional[List[str]], index: Mapping[str, int], name: str) -> str:
    position = index.get(name)
    return row[position].strip() if row is not None and position is not None and position < len(row) else ""


def quarter_end_of(name: str) -> date:
    """The quarter-end in a stored zip's name `<YYYY-MM-DD>-<sha256>.zip`."""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-[0-9a-f]{64}\.zip$", name)
    if match is None:
        raise ValueError(f"{name!r} is not a stored CDR zip (<quarter-end>-<sha256>.zip)")
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_quarter(payload: bytes, quarter_end: date) -> Tuple[List[Row], List[dict], str]:
    """The nine banks' rows from one quarter's bulk zip, the holes found, and the file's own "as of" stamp.

    A bank is read from the consolidated column (`RCFA`) when it has both items there, else from the domestic-offices
    column (`RCOA`). A bank that is not in the file, has a blank item, or reports tier 1 capital above total leverage
    exposure (impossible: the exposure includes the assets that capital funds) is a hole, never a guess.

    Raises:
        ValueError: if the file is not a zip, or its schedules or `Readme.txt` are missing.
    """
    digest = hashlib.sha256(payload).hexdigest()
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise ValueError(f"the {quarter_end} file is not a zip") from error
    with archive:
        stamp = re.search(r"as of (\S+)", archive.read("Readme.txt").decode("latin-1"))
        if stamp is None:
            raise ValueError(f"the {quarter_end} file's Readme.txt has no 'as of' stamp")
        por_head, por = _table(archive, "Bulk POR")
        rcri_head, rcri = _table(archive, "Schedule RCRI ")
    updated = {int(r[0]): datetime.fromisoformat(r[por_head.index("Last Date/Time Submission Updated On")]) for r in por}
    by_id = {int(r[0]): r for r in rcri}
    index = {name: position for position, name in enumerate(rcri_head)}
    rows: List[Row] = []
    holes: List[dict] = []

    def hole(idrssd: int, reason: str, detail: str, kept: bool = False) -> None:
        holes.append({"quarter_end": quarter_end.isoformat(), "idrssd": idrssd, "institution": BANKS[idrssd],
                      "reason": reason, "row_kept": kept, "detail": detail})

    for idrssd in BANKS:
        if idrssd not in updated:
            hole(idrssd, "not_a_filer", "no row in the Call Bulk POR file")
            continue
        raw = by_id.get(idrssd)
        chosen = None
        for form in COLUMN_FORMS:
            tier1, exposure = (_cell(raw, index, form + item) for item in (TIER1_ITEM, EXPOSURE_ITEM))
            if tier1 and exposure:
                chosen = (form, tier1, exposure, _cell(raw, index, form + REPORTED_RATIO_ITEM))
                break
        if chosen is None:
            seen = {item: next((_cell(raw, index, form + item) for form in COLUMN_FORMS
                                if _cell(raw, index, form + item)), "") for item in (TIER1_ITEM, EXPOSURE_ITEM)}
            blank = [item for item, value in seen.items() if not value]
            hole(idrssd, "item_blank", f"item(s) {', '.join(blank)} blank in RCFA and RCOA (filed: tier 1 "
                 f"{seen[TIER1_ITEM] or 'blank'}, exposure {seen[EXPOSURE_ITEM] or 'blank'})")
            continue
        form, tier1, exposure, reported = chosen
        row = Row(quarter_end=quarter_end, idrssd=idrssd, institution=BANKS[idrssd], latest_update=updated[idrssd],
                  column_form=form, tier1_capital_kusd=int(tier1), total_leverage_exposure_kusd=int(exposure),
                  reported_slr_pct=float(reported.rstrip("%")) if reported else None, source_zip_sha256=digest)
        if row.total_leverage_exposure_kusd <= 0 or row.tier1_capital_kusd > row.total_leverage_exposure_kusd:
            hole(idrssd, "tier1_exceeds_exposure", f"tier 1 capital {tier1} against total leverage exposure {exposure} "
                 f"(thousands): a ratio above 100% is not a ratio")
            continue
        rows.append(row)
    return rows, holes, stamp.group(1)


def withhold_locked(rows: Iterable[Row]) -> Tuple[List[Row], List[dict]]:
    """The rows whose latest update is not on a day the parent's lockbox holds, and a hole for each that is.

    A figure last updated on a locked day is not read, and its earlier version cannot be recovered from the bulk file.
    """
    kept: List[Row] = []
    holes: List[dict] = []
    for row in rows:
        if development.is_locked(row.latest_update.date()):
            holes.append({"quarter_end": row.quarter_end.isoformat(), "idrssd": row.idrssd, "institution": row.institution,
                          "reason": "updated_after_development_end", "row_kept": False,
                          "detail": f"last updated {row.latest_update.isoformat()}, on a day the parent's lockbox holds"})
        else:
            kept.append(row)
    return kept, holes


def notes(rows: Iterable[Row]) -> List[dict]:
    """The holes in a kept row's columns: no requirement set, exclusion status unknown, ratio differs from the reported."""
    out = []
    for row in rows:
        base = {"quarter_end": row.quarter_end.isoformat(), "idrssd": row.idrssd, "institution": row.institution,
                "row_kept": True}
        if row.requirement_pct is None:
            out.append({**base, "reason": "requirement_not_set",
                        "detail": "the requirement table (docs/decisions/slr-requirement.md) has no value for this quarter; headroom is blank"})
        if row.exclusion_status:
            out.append({**base, "reason": "exclusion_status_unknown",
                        "detail": "inside the April 2020 to March 2021 exclusion window (row 16(e)); the subsidiary's "
                                  "election is not in the bulk file"})
        if row.reported_slr_pct is not None and abs(row.slr_pct - row.reported_slr_pct) > RATIO_TOLERANCE_PP:
            out.append({**base, "reason": "ratio_differs_from_reported",
                        "detail": f"computed {row.slr_pct:.4f}% against reported {row.reported_slr_pct:.4f}%"})
    return out


# ---------------------------------------------------------------------------------------------------------------
# The extract


def _fmt(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.4f}"


def write_extract(rows: Iterable[Row]) -> bytes:
    """The tracked CSV: one row per bank and quarter, oldest quarter first."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXTRACT_COLUMNS)
    for row in sorted(rows, key=lambda r: (r.quarter_end, r.idrssd)):
        writer.writerow((row.quarter_end.isoformat(), row.idrssd, row.institution, VINTAGE,
                         row.latest_update.isoformat(), row.available_from.isoformat(), row.column_form,
                         row.tier1_capital_kusd, row.total_leverage_exposure_kusd, _fmt(row.reported_slr_pct),
                         _fmt(row.slr_pct), _fmt(row.requirement_pct), _fmt(row.headroom_pp), row.exclusion_status,
                         row.measure, row.source_zip_sha256))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against the rules that built it.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `EXTRACT_COLUMNS`, a row is not labelled
            `latest_filed`, a stored derived column (ratio, requirement, headroom, status) is not what the figures give,
            or a (bank, quarter) is listed twice.
        LookAheadError: if a row was last updated on a day the parent's lockbox holds.
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
        row = Row(quarter_end=date.fromisoformat(item["quarter_end"]), idrssd=int(item["idrssd"]),
                  institution=item["institution"], latest_update=datetime.fromisoformat(item["latest_update"]),
                  column_form=item["column_form"], tier1_capital_kusd=int(item["tier1_capital_kusd"]),
                  total_leverage_exposure_kusd=int(item["total_leverage_exposure_kusd"]),
                  reported_slr_pct=float(item["reported_slr_pct"]) if item["reported_slr_pct"] else None,
                  source_zip_sha256=item["source_zip_sha256"])
        key = (row.quarter_end, row.idrssd)
        if key in seen:
            raise ValueError(f"{path.name}: {row.institution} {row.quarter_end} is listed twice")
        seen.add(key)
        if item["vintage"] != VINTAGE:
            raise ValueError(f"{path.name}: {row.institution} {row.quarter_end} is labelled {item['vintage']!r}, not {VINTAGE!r}")
        for column, expected in (("slr_pct", _fmt(row.slr_pct)), ("requirement_pct", _fmt(row.requirement_pct)),
                                 ("headroom_pp", _fmt(row.headroom_pp)), ("exclusion_status", row.exclusion_status),
                                 ("measure", row.measure), ("available_from", row.available_from.isoformat())):
            if item[column] != expected:
                raise ValueError(f"{path.name}: {row.institution} {row.quarter_end} stores {column} {item[column]!r}, "
                                 f"the figures give {expected!r}")
        if development.is_locked(row.latest_update.date()):
            raise LookAheadError(f"{row.institution} {row.quarter_end} was last updated {row.latest_update}, on a day "
                                 f"the parent's lockbox holds")
        rows.append(row)
    return rows


def worst_case_lag_days(rows: Iterable[Row]) -> int:
    """The longest gap, in calendar days, from a quarter-end to the start of the day a figure is available."""
    return max((row.available_from.date() - row.quarter_end).days for row in rows)


def check_declared_lag(entry: Mapping, rows: Iterable[Row]) -> None:
    """Refuse a declaration under which some figure would be read before it was last updated, or any later than needed.

    The declared lag is the measured maximum and not above it, as for the H.8 groups.

    Raises:
        ValueError: if the declaration is not record_date / calendar_days.
        LookAheadError: naming the first (bank, quarter) available after its declared availability.
        StaleReadError: if the declared lag is longer than the longest in the extract.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    lag = entry["release_lag"]
    if lag.get("basis") != "record_date" or lag.get("unit") != "calendar_days":
        raise ValueError(f"an SLR source must be declared record_date/calendar_days, not {lag}")
    moment = time.fromisoformat(lag["available_time"])
    for row in rows:
        declared = datetime.combine(row.quarter_end + timedelta(days=int(lag["days"])), moment, tzinfo=NEW_YORK)
        if row.available_from > declared:
            raise LookAheadError(f"{row.institution} {row.quarter_end} is available from {row.available_from}, after its "
                                 f"declared availability {declared}")
    worst = worst_case_lag_days(rows)
    if int(lag["days"]) > worst:
        raise StaleReadError(f"the declared lag of {lag['days']} days is longer than the {worst} days the slowest figure "
                             f"in the extract took: values would be read later than needed")


# ---------------------------------------------------------------------------------------------------------------
# Reading as of an instant


def latest_public(rows: Iterable[Row], idrssd: int, at: datetime) -> Optional[Row]:
    """The bank's latest quarter whose figures are public at `at`, or None.

    Raises:
        ValueError: if `at` has no time zone.
    """
    if at.tzinfo is None:
        raise ValueError("the decision instant must be timezone-aware")
    public = [row for row in rows if row.idrssd == idrssd and row.available_from <= at]
    return max(public, key=lambda row: row.quarter_end, default=None)


def read(rows: Iterable[Row], idrssd: int, quarter_end: date, at: datetime) -> Row:
    """One bank's figures for a quarter, as read at the decision instant `at`.

    Raises:
        ValueError: if the bank-quarter is not in the extract, or `at` has no time zone.
        LookAheadError: if the figures were last updated, and so became available, after `at`.
        StaleReadError: if a later quarter of the bank is already public at `at` (the read is older than the latest
            admissible one).

    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    matches = [row for row in rows if row.idrssd == idrssd and row.quarter_end == quarter_end]
    if not matches:
        raise ValueError(f"no figures for bank {idrssd} for the quarter ended {quarter_end}")
    row = matches[0]
    latest = latest_public(rows, idrssd, at)
    if row.available_from > at:
        raise LookAheadError(f"{row.institution} {quarter_end} is available from {row.available_from}, after the "
                             f"decision instant {at}")
    if latest is not None and latest.quarter_end > quarter_end:
        raise StaleReadError(f"{row.institution} {quarter_end} is read at {at}, when the quarter ended "
                             f"{latest.quarter_end} is already public")
    return row


def observations(rows: Iterable[Row], field: str, *, source_sha: str):
    """One field of the extract as the parent's point-in-time rows, one series per bank (`<field>:<idrssd>`).

    Each row is dated the quarter-end and public from its latest-update time. The headroom of a quarter with no
    requirement is not an observation. The main measure only: State Street is read by `sensitivity_observations`.
    """
    return _observations([row for row in rows if row.measure == MAIN], field, source_sha, prefix="")


def sensitivity_observations(rows: Iterable[Row], field: str, *, source_sha: str):
    """The labelled State Street sensitivity as point-in-time rows, one series per field (`sensitivity_<field>:<idrssd>`)."""
    return _observations([row for row in rows if row.measure == SENSITIVITY], field, source_sha, prefix="sensitivity_")


def _observations(rows: Iterable[Row], field: str, source_sha: str, *, prefix: str):
    from repo_model.data import PointInTimeObservation

    if field not in FIELDS:
        raise ValueError(f"{field!r} is not an SLR field; they are {list(FIELDS)}")
    pick = {"slr_tier1_capital": lambda r: float(r.tier1_capital_kusd),
            "slr_total_leverage_exposure": lambda r: float(r.total_leverage_exposure_kusd),
            "slr_ratio": lambda r: r.slr_pct, "slr_headroom": lambda r: r.headroom_pp}[field]
    out = []
    for row in rows:
        value = pick(row)
        if value is None:
            continue
        out.append(PointInTimeObservation(series_id=f"{prefix}{field}:{row.idrssd}", ref_date=row.quarter_end,
                                          available_at=row.available_from, value=value,
                                          vintage_id=f"{VINTAGE}-{row.latest_update.isoformat()}", source_sha=source_sha))
    return out


# ---------------------------------------------------------------------------------------------------------------
# The coverage record


def coverage(rows: Sequence[Row], holes: Sequence[dict], quarters: Sequence[date]) -> Dict:
    """Every hole and refusal from `quarters`, by filer and quarter, with its reason, and the counts."""
    ordered = sorted(holes, key=lambda h: (h["quarter_end"], h["idrssd"], h["reason"]))
    counts: Dict[str, int] = {}
    for item in ordered:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return {"quarters": [q.isoformat() for q in quarters], "banks": len(BANKS),
            "bank_quarters": len(BANKS) * len(quarters), "rows": len(rows),
            "reasons": dict(sorted(counts.items())), "holes": ordered}
