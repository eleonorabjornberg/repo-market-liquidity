"""Scheduled inputs: the standing repo facility's rate, the ON RRP offering rate and the FOMC runoff caps.

Both are announced before they take effect, so each is a scheduled input under the parent's information-set rule
(`metadata/sources_phase3.json`, `scheduled_availability`): the value for row T is read at T's decision instant,
16:00 New York on the panel day before T, from the publications made at or before that instant and effective on or
before T. The pattern is the parent's `announced_iorb`.

The tables live in `tests/fixtures/snapshots/fomc_notes/`, each row read from a saved federalreserve.gov page, with
a sha256 manifest per table. Standard library only.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Tuple

NOTES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "snapshots" / "fomc_notes"
SRF_TABLE = NOTES / "srf_rate.csv"
CAPS_TABLE = NOTES / "runoff_caps.csv"
ON_RRP_RATE_TABLE = NOTES / "on_rrp_rate.csv"

#: The facility's first operation (the FOMC established it on 28 July 2021): no rate before it.
SRF_INCEPTION = date(2021, 7, 29)

SRF_COLUMN = "srf_rate"
ON_RRP_RATE_COLUMN = "on_rrp_rate"
CAP_COLUMNS = ("runoff_cap_treasury_bn", "runoff_cap_mbs_bn")


class Publication(NamedTuple):
    announced_at: datetime
    effective: date
    values: Tuple[float, ...]
    raw_values: Tuple[str, ...]
    page: str


def _verified_rows(path: Path) -> List[dict]:
    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _publications(path: Path, value_columns: Sequence[str]) -> List[Publication]:
    rows = []
    for row in _verified_rows(path):
        if row["timezone"] != "America/New_York":
            raise ValueError(f"{path.name}: timezone {row['timezone']!r}")
        announced = datetime.combine(date.fromisoformat(row["announcement_date"]),
                                     time.fromisoformat(row["announcement_time"]))
        effective = date.fromisoformat(row["effective_date"])
        if effective <= announced.date():
            raise ValueError(f"{path.name}: effective {effective} is not after its announcement {announced}")
        raw = tuple(row[column] for column in value_columns)
        rows.append(Publication(announced, effective, tuple(float(value) for value in raw), raw, row["page"]))
    return rows


def load_srf_rates() -> List[Publication]:
    return _publications(SRF_TABLE, ("rate_percent",))


def load_on_rrp_rates() -> List[Publication]:
    return _publications(ON_RRP_RATE_TABLE, ("rate_percent",))


def load_runoff_caps() -> List[Publication]:
    return _publications(CAPS_TABLE, ("treasury_cap_bn", "mbs_cap_bn"))


def write_manifest(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".manifest.json").write_text(
        json.dumps({"path": path.name, "sha256": digest}, indent=2) + "\n", encoding="utf-8")
    return digest


def _in_force(rows: Sequence[Publication], instant: datetime, day: date) -> Optional[Publication]:
    """The latest publication made at or before `instant` and effective on or before `day`."""
    known = [row for row in rows if row.announced_at <= instant and row.effective <= day]
    if not known:
        return None
    return max(known, key=lambda row: (row.effective, row.announced_at))


def _values(dates: Sequence[date], rows: Sequence[Publication], decision_time: time):
    moment = decision_time.replace(tzinfo=None)
    out = [None]
    for index in range(1, len(dates)):
        out.append(_in_force(rows, datetime.combine(dates[index - 1], moment), dates[index]))
    return out


def rate_in_force(rows: Sequence[Publication], day: date) -> Optional[float]:
    """The rate in force on `day` by effective date, whenever announced: for a realized outcome, never a model input."""
    row = max((r for r in rows if r.effective <= day), key=lambda r: r.effective, default=None)
    return None if row is None else row.values[0]


def srf_rate_values(dates: Sequence[date], *, decision_time: time, rows=None) -> List[Optional[float]]:
    """The facility's rate on each row, read at its decision instant; missing before the facility existed."""
    rows = load_srf_rates() if rows is None else rows
    return [None if row is None or day < SRF_INCEPTION else row.values[0]
            for day, row in zip(dates, _values(dates, rows, decision_time))]


def on_rrp_rate_values(dates: Sequence[date], *, decision_time: time, rows=None) -> List[Optional[float]]:
    """The ON RRP offering rate on each row, read at its decision instant."""
    rows = load_on_rrp_rates() if rows is None else rows
    return [None if row is None else row.values[0] for row in _values(dates, rows, decision_time)]


#: Stage 4 (`docs/stages/stage-4.md`): the IORB in force on each row, read at its decision instant. Not built into any
#: panel version; `curve_feature.with_stage4_columns` adds it in memory.
IORB_COLUMN = "iorb_in_force"


def load_iorb_rates() -> List[Publication]:
    """The parent's own dated table of IORB (IOER) implementation notes, checked against its manifest."""
    from repo_model import announced_iorb

    from repo_liquidity import parent_root

    table = parent_root() / "tests" / "fixtures" / "snapshots" / "fed-iorb-announcements" / "iorb_changes.csv"
    return [Publication(note.announced_at, note.effective, (note.rate_bps / 100.0,), (str(note.rate_bps),), "")
            for note in announced_iorb.load_announcements(table)]


def iorb_in_force_values(dates: Sequence[date], *, decision_time: time, rows=None) -> List[Optional[float]]:
    """The IORB in force on each row, in percent, read at its decision instant."""
    rows = load_iorb_rates() if rows is None else rows
    return [None if row is None else row.values[0] for row in _values(dates, rows, decision_time)]


def runoff_cap_values(dates: Sequence[date], *, decision_time: time, rows=None) -> List[Optional[Tuple[float, float]]]:
    """The (Treasury, MBS) monthly runoff caps in force on each row, read at its decision instant."""
    rows = load_runoff_caps() if rows is None else rows
    return [None if row is None else row.values for row in _values(dates, rows, decision_time)]


def with_scheduled(observations, *, decision_time: time):
    """`observations` with the scheduled columns added on every row.

    Raises:
        ValueError: if a row already carries one of the columns.
    """
    from repo_model.data import DailyObservation

    columns = (SRF_COLUMN, ON_RRP_RATE_COLUMN) + CAP_COLUMNS
    for row in observations:
        clash = [column for column in columns if column in row.values]
        if clash:
            raise ValueError(f"{row.date} already carries {clash}")
    dates = [row.date for row in observations]
    rates = srf_rate_values(dates, decision_time=decision_time)
    floors = on_rrp_rate_values(dates, decision_time=decision_time)
    caps = runoff_cap_values(dates, decision_time=decision_time)
    out = []
    for row, rate, floor, cap in zip(observations, rates, floors, caps):
        values = dict(row.values)
        values[SRF_COLUMN] = rate
        values[ON_RRP_RATE_COLUMN] = floor
        values[CAP_COLUMNS[0]] = None if cap is None else cap[0]
        values[CAP_COLUMNS[1]] = None if cap is None else cap[1]
        out.append(DailyObservation(row.date, values))
    return out


def _cross_check(rows, directory: str, operation_type: str, rate_key: str, first: Optional[date]) -> int:
    """Check every overnight operation in the parent's snapshots ran at the rate this table puts in force that day.

    Returns the number of operation days checked.

    Raises:
        ValueError: on the first day whose operation rate differs from the table.
    """
    from repo_liquidity import parent_root

    checked = 0
    for path in sorted((parent_root() / "tests/fixtures/snapshots" / directory).glob("*.json")):
        if path.name.endswith(".manifest.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for operation in payload.get("repo", {}).get("operations", []):
            if operation.get("operationType") != operation_type or operation.get("term") != "Overnight":
                continue
            day = date.fromisoformat(operation["operationDate"])
            if first is not None and day < first:
                continue
            rates = {detail.get(rate_key) for detail in operation.get("details", [])}
            rates.discard(None)
            if not rates:
                continue
            row = max((r for r in rows if r.effective <= day), key=lambda r: r.effective, default=None)
            expected = None if row is None else row.values[0]
            if expected is None or any(abs(rate - expected) > 1e-9 for rate in rates):
                raise ValueError(f"{day}: {operation_type} rate {sorted(rates)} but the table has {expected}")
            checked += 1
    return checked


def cross_check_srf_operations() -> int:
    return _cross_check(load_srf_rates(), "srf_inputs/nyfed_srf", "Repo", "percentOfferingRate", SRF_INCEPTION)


def cross_check_on_rrp_operations() -> int:
    return _cross_check(load_on_rrp_rates(), "on_rrp_inputs/nyfed_on_rrp", "Reverse Repo", "percentOfferingRate",
                        None)
