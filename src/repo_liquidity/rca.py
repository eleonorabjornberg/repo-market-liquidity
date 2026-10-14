"""The quarterly anchor of the group reserves: RC-A "balances due from Federal Reserve Banks" (#43, G4 for H7m).

Nicholas's answer 17(b) asks for the weekly group shares to be anchored on the exact figure each institution reports for
its balance at the Federal Reserve Banks. This module reads the domestic half of that anchor from the FFIEC CDR bulk
files and publishes it, by group and quarter, as an input. Nothing is scored.

- **The item.** Schedule RC-A, "Balances due from Federal Reserve Banks": `RCFD0090` (consolidated), else `RCON0090`
  (domestic offices), thousands of dollars. Only a minority of filers carry it (`docs/research/rca-fed-balances-due-diligence.md`).
- **The two groups, a labelled approximation** (Eleonora's ruling of 14 October 2026 on PR #50, Q3; data-meaning answer
  17(c)). The large domestic group is the 25 filers with the largest total assets (`RCFD2170`, else `RCON2170`) in the
  quarter's file; the small domestic group is every other filer that carries the item. This is not the Board's panel
  (the Call Report files do not carry it) and the files do not separate commercial banks from the savings institutions
  the H.8 leaves out. The Board's list replaces the stand-in wherever one is found.
- **The foreign-related group has no anchor here.** Eleonora's ruling of 14 October 2026 (option a) uses the H.8
  foreign-related institutions' cash assets as that group's weekly level, labelled an approximation (cash assets, not
  reserves alone); no FFIEC 002 is read. The weekly series (`repo_liquidity.group_reserves`) no longer reads this anchor
  (her ruling of 14 October 2026, option (i)): it is a published input kept for a later, anchored version.
- **Vintage and availability** (data-meaning answer 16(d) as amended on 13 October 2026, PR #44): a bulk file carries
  only the **latest-filed** figure of each filer, so a figure is available only from its "Last Date/Time Submission
  Updated On" time (`Call Bulk POR`), and the extract labels every row `vintage = latest_filed`. A group's figure is a sum,
  so it is available only from the start of the New York day after the **slowest member's** latest update. That is the
  reading of the ruling that needs no threshold: a partial sum would put an undercount into the series with no rule for
  how much of the group is enough, and that rule is Eleonora's. The coverage record shows how far the choice reaches.
- **Nothing past the development tier.** A group-quarter with a member last updated on a day the parent's lockbox holds
  is withheld whole and listed; the loader refuses an extract that holds one (`LookAheadError`).

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

SOURCE_ID = "ffiec_call_rca"
NEW_YORK = ZoneInfo("America/New_York")
VINTAGE = "latest_filed"

GROUPS: Tuple[str, ...] = ("large_domestic", "small_domestic")
#: The number of largest filers, by total assets, that stand in for the Board's panel of large domestically chartered banks.
TOP_N = 25
FRB_ITEM, ASSETS_ITEM = "0090", "2170"
#: The lags, in days after quarter-end, at which the coverage record shows how much of a group's balance was public.
PROFILE_LAGS: Tuple[int, ...] = (45, 90, 180, 365)

FIELDS: Tuple[str, ...] = tuple(f"rca_{group}_frb_balances" for group in GROUPS)
_FIELD_GROUP = dict(zip(FIELDS, GROUPS))
EXTRACT_COLUMNS: Tuple[str, ...] = (
    "quarter_end", "group", "vintage", "filers", "latest_update", "available_from", "balances_kusd", "source_zip_sha256")
EXTRACT_NAME = "rca_latest_filed.csv"
SOURCES_NAME = "rca_latest_filed.sources.json"
COVERAGE_NAME = "rca_latest_filed.coverage.json"

#: Why a group-quarter is missing from the extract, or kept with a member left out.
REFUSALS = ("updated_after_development_end",)
KEPT_WITH_NOTE = ("large_member_item_blank",)


@dataclass(frozen=True)
class Row:
    """One group's latest-filed balances for one quarter: the sum over its members, and the slowest member's update."""

    quarter_end: date
    group: str
    filers: int
    balances_kusd: int
    latest_update: datetime
    source_zip_sha256: str

    @property
    def balances_bn(self) -> float:
        return round(self.balances_kusd / 1e6, 6)

    @property
    def available_from(self) -> datetime:
        """The start of the day after the slowest member's latest update, New York time (see the module note)."""
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


def _item(row: List[str], index: Mapping[str, int], item: str) -> Optional[int]:
    """The consolidated figure (`RCFD`), else the domestic-offices one (`RCON`), in thousands; None if neither is filed."""
    for prefix in ("RCFD", "RCON"):
        position = index.get(prefix + item)
        if position is not None and position < len(row) and row[position].strip():
            return int(float(row[position]))
    return None


def quarter_end_of(name: str) -> date:
    """The quarter-end in a stored zip's name `<YYYY-MM-DD>-<sha256>.zip`."""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-[0-9a-f]{64}\.zip$", name)
    if match is None:
        raise ValueError(f"{name!r} is not a stored CDR zip (<quarter-end>-<sha256>.zip)")
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_quarter(payload: bytes, quarter_end: date, top_n: int = TOP_N) -> Tuple[List[Row], List[dict], str, Dict[str, dict]]:
    """The two groups' rows from one quarter's bulk zip, the holes found, the file's own "as of" stamp, and the lag profile.

    The `top_n` filers with the largest total assets (ties broken by the smaller IDRSSD) are the large group. A filer
    among them that does not carry the item is left out of the sum and listed (`large_member_item_blank`); a filer outside
    them that does not carry it is simply not a member of the small group (most filers do not, and the item is not
    "zero" for them). The lag profile gives, per group, the share of the balance whose own latest update was within each
    of `PROFILE_LAGS` days of the quarter-end, and None for a lag that ends after the parent's development end. It is a
    diagnostic of how stale the anchor is and is read by no model.

    Raises:
        ValueError: if the file is not a zip, a schedule or `Readme.txt` is missing, or a filer that carries the item has
            no update time (it could not be dated).
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
        rc_head, rc = _table(archive, "Schedule RC ")
        rca_head, rca_rows = _table(archive, "Schedule RCA ")
    column = por_head.index("Last Date/Time Submission Updated On")
    updated = {int(r[0]): datetime.fromisoformat(r[column]) for r in por if len(r) > column and r[column].strip()}
    rc_index = {name: position for position, name in enumerate(rc_head)}
    rca_index = {name: position for position, name in enumerate(rca_head)}
    assets = {int(r[0]): _item(r, rc_index, ASSETS_ITEM) or 0 for r in rc}
    balances = {}
    for r in rca_rows:
        value = _item(r, rca_index, FRB_ITEM)
        if value is not None:
            balances[int(r[0])] = value
    largest = sorted(assets, key=lambda idrssd: (-assets[idrssd], idrssd))[:top_n]
    members = {"large_domestic": [i for i in largest if i in balances],
               "small_domestic": sorted(i for i in balances if i not in set(largest))}
    holes = [{"quarter_end": quarter_end.isoformat(), "group": "large_domestic", "idrssd": i,
              "reason": "large_member_item_blank", "row_kept": True,
              "detail": f"filer {i} is among the {top_n} largest by total assets and carries no item {FRB_ITEM}; "
                        f"it is left out of the group's sum"} for i in largest if i not in balances]
    rows: List[Row] = []
    profile: Dict[str, dict] = {}
    end = development.development_end()
    for group in GROUPS:
        ids = members[group]
        missing = [i for i in ids if i not in updated]
        if missing:
            raise ValueError(f"the {quarter_end} file: filer {missing[0]} carries item {FRB_ITEM} but has no update time "
                             f"in the Call Bulk POR file")
        if not ids:
            continue
        rows.append(Row(quarter_end=quarter_end, group=group, filers=len(ids),
                        balances_kusd=sum(balances[i] for i in ids), latest_update=max(updated[i] for i in ids),
                        source_zip_sha256=digest))
        total = sum(balances[i] for i in ids)
        profile[group] = {}
        for lag in PROFILE_LAGS:
            cutoff = quarter_end + timedelta(days=lag)
            if end is not None and cutoff > end:
                profile[group][str(lag)] = None
            else:
                public = sum(balances[i] for i in ids if updated[i].date() <= cutoff)
                profile[group][str(lag)] = round(public / total, 4) if total else None
    return rows, holes, stamp.group(1), profile


def withhold_locked(rows: Iterable[Row]) -> Tuple[List[Row], List[dict]]:
    """The rows whose slowest member was not last updated on a day the parent's lockbox holds, and a hole for each that was.

    A group with a member last updated on a locked day is withheld whole: that member's earlier figure cannot be
    recovered from the bulk file, and a sum without it is another quantity.
    """
    kept: List[Row] = []
    holes: List[dict] = []
    for row in rows:
        if development.is_locked(row.latest_update.date()):
            holes.append({"quarter_end": row.quarter_end.isoformat(), "group": row.group,
                          "reason": "updated_after_development_end", "row_kept": False,
                          "detail": f"a member was last updated {row.latest_update.isoformat()}, on a day the parent's "
                                    f"lockbox holds"})
        else:
            kept.append(row)
    return kept, holes


# ---------------------------------------------------------------------------------------------------------------
# The extract


def write_extract(rows: Iterable[Row]) -> bytes:
    """The tracked CSV: one row per group and quarter, oldest quarter first."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXTRACT_COLUMNS)
    for row in sorted(rows, key=lambda r: (r.quarter_end, r.group)):
        writer.writerow((row.quarter_end.isoformat(), row.group, VINTAGE, row.filers, row.latest_update.isoformat(),
                         row.available_from.isoformat(), row.balances_kusd, row.source_zip_sha256))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against the rules that built it.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `EXTRACT_COLUMNS`, a row is not labelled
            `latest_filed`, a stored derived column (`available_from`) is not what the update time gives, or a
            (group, quarter) is listed twice.
        LookAheadError: if a row has a member last updated on a day the parent's lockbox holds.
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
        if item["group"] not in GROUPS:
            raise ValueError(f"{path.name}: {item['group']!r} is not one of the groups {list(GROUPS)}")
        row = Row(quarter_end=date.fromisoformat(item["quarter_end"]), group=item["group"], filers=int(item["filers"]),
                  balances_kusd=int(item["balances_kusd"]), latest_update=datetime.fromisoformat(item["latest_update"]),
                  source_zip_sha256=item["source_zip_sha256"])
        key = (row.quarter_end, row.group)
        if key in seen:
            raise ValueError(f"{path.name}: {row.group} {row.quarter_end} is listed twice")
        seen.add(key)
        if item["vintage"] != VINTAGE:
            raise ValueError(f"{path.name}: {row.group} {row.quarter_end} is labelled {item['vintage']!r}, not {VINTAGE!r}")
        if item["available_from"] != row.available_from.isoformat():
            raise ValueError(f"{path.name}: {row.group} {row.quarter_end} stores available_from {item['available_from']!r}, "
                             f"the update time gives {row.available_from.isoformat()!r}")
        if development.is_locked(row.latest_update.date()):
            raise LookAheadError(f"{row.group} {row.quarter_end} has a member last updated {row.latest_update}, on a day "
                                 f"the parent's lockbox holds")
        rows.append(row)
    return rows


def worst_case_lag_days(rows: Iterable[Row]) -> int:
    """The longest gap, in calendar days, from a quarter-end to the start of the day a group's figure is available."""
    return max((row.available_from.date() - row.quarter_end).days for row in rows)


def check_declared_lag(entry: Mapping, rows: Iterable[Row]) -> None:
    """Refuse a declaration under which some figure would be read before it was last updated, or any later than needed.

    The declared lag is the measured maximum and not above it, as for the H.8 groups and the SLR extract.

    Raises:
        ValueError: if the declaration is not record_date / calendar_days.
        LookAheadError: naming the first (group, quarter) available after its declared availability.
        StaleReadError: if the declared lag is longer than the longest in the extract.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    lag = entry["release_lag"]
    if lag.get("basis") != "record_date" or lag.get("unit") != "calendar_days":
        raise ValueError(f"an RC-A anchor source must be declared record_date/calendar_days, not {lag}")
    moment = time.fromisoformat(lag["available_time"])
    for row in rows:
        declared = datetime.combine(row.quarter_end + timedelta(days=int(lag["days"])), moment, tzinfo=NEW_YORK)
        if row.available_from > declared:
            raise LookAheadError(f"{row.group} {row.quarter_end} is available from {row.available_from}, after its "
                                 f"declared availability {declared}")
    worst = worst_case_lag_days(rows)
    if int(lag["days"]) > worst:
        raise StaleReadError(f"the declared lag of {lag['days']} days is longer than the {worst} days the slowest figure "
                             f"in the extract took: values would be read later than needed")


# ---------------------------------------------------------------------------------------------------------------
# Reading as of an instant


def latest_public(rows: Iterable[Row], group: str, at: datetime) -> Optional[Row]:
    """The group's latest quarter whose figure is public at `at`, or None.

    Raises:
        ValueError: if `at` has no time zone.
    """
    if at.tzinfo is None:
        raise ValueError("the decision instant must be timezone-aware")
    public = [row for row in rows if row.group == group and row.available_from <= at]
    return max(public, key=lambda row: row.quarter_end, default=None)


def read(rows: Iterable[Row], group: str, quarter_end: date, at: datetime) -> Row:
    """One group's figure for a quarter, as read at the decision instant `at`.

    Raises:
        ValueError: if the group-quarter is not in the extract, or `at` has no time zone.
        LookAheadError: if the figure became available, after its slowest member's last update, later than `at`.
        StaleReadError: if a later quarter of the group is already public at `at` (the read is older than the latest
            admissible one).
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    rows = list(rows)
    matches = [row for row in rows if row.group == group and row.quarter_end == quarter_end]
    if not matches:
        raise ValueError(f"no figure for {group} for the quarter ended {quarter_end}")
    row = matches[0]
    latest = latest_public(rows, group, at)
    if row.available_from > at:
        raise LookAheadError(f"{group} {quarter_end} is available from {row.available_from}, after the decision instant {at}")
    if latest is not None and latest.quarter_end > quarter_end:
        raise StaleReadError(f"{group} {quarter_end} is read at {at}, when the quarter ended {latest.quarter_end} is "
                             f"already public")
    return row


def observations(rows: Iterable[Row], field: str, *, source_sha: str):
    """One field of the extract as the parent's point-in-time rows, in billions of dollars.

    Each row is dated the quarter-end and public from the day after its slowest member's latest update.
    """
    from repo_model.data import PointInTimeObservation

    if field not in _FIELD_GROUP:
        raise ValueError(f"{field!r} is not an RC-A anchor field; they are {list(FIELDS)}")
    group = _FIELD_GROUP[field]
    return [PointInTimeObservation(series_id=field, ref_date=row.quarter_end, available_at=row.available_from,
                                   value=row.balances_bn, vintage_id=f"{VINTAGE}-{row.latest_update.isoformat()}",
                                   source_sha=source_sha)
            for row in rows if row.group == group]


# ---------------------------------------------------------------------------------------------------------------
# The coverage record


def coverage(rows: Sequence[Row], holes: Sequence[dict], quarters: Sequence[date], profile: Mapping[str, Mapping]) -> Dict:
    """Every hole and withholding from `quarters`, by group and quarter, the counts, and the lag profile."""
    ordered = sorted(holes, key=lambda h: (h["quarter_end"], h["group"], h.get("idrssd", 0), h["reason"]))
    counts: Dict[str, int] = {}
    for item in ordered:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return {"quarters": [q.isoformat() for q in quarters], "groups": list(GROUPS),
            "group_quarters": len(GROUPS) * len(quarters), "rows": len(rows),
            "reasons": dict(sorted(counts.items())), "holes": ordered,
            "lag_profile": {key: dict(value) for key, value in sorted(profile.items())},
            "profile_lags_days": list(PROFILE_LAGS)}
