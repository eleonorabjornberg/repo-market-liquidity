"""The Fed's repo take-up: the 2019 to 2021 temporary operations, then the standing facility.

`docs/stages/stage-1a-correction.md`, items 2 and 3, from Nicholas Beroud's answers 5 and 13
(`docs/decisions/data-meaning.md`):

- **before 2019-09-17** no Fed repo was offered, so take-up is a structural zero;
- **from 2019-09-17 to 2021-07-28** the Desk's temporary open market operations are take-up from a different facility.
  They are read here from the NY Fed's operation results, saved under `tests/fixtures/snapshots/nyfed_temp_repo/`;
- **from 2021-07-29** the standing facility's take-up is the parent's `nyfed_srf`, as Stage 1a reads it.

Nicholas's answer to question 14 (issue #1, 6 October 2026): take-up is the overnight operations plus the term repos
**outstanding** on the day, from settlement to maturity, because a term repo's cash stays in the system for its term.
The material-use event ($1bn or more, a threshold he fixed in advance) counts each operation on its **operation date**,
overnight and term alike, because that is when the demand showed. His caveat, for the record: in 2019 and 2020 the
Fed set the term offering sizes, partly to cover year-end, so take-up reflects the Fed's design as well as market
demand. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "tests" / "fixtures" / "snapshots" / "nyfed_temp_repo"
URL = "https://markets.newyorkfed.org/api/rp/results/search.json?startDate={first}&endDate={last}"

FIRST_OPERATION = date(2019, 9, 17)
LAST_OPERATION = date(2021, 7, 28)
SERIES = "temp_repo_take_up"
#: Term repos accepted on their operation date (for the material-use event).
TERM_SERIES = "temp_repo_term_take_up"
#: Term repos outstanding on the day, settlement to maturity (for take-up).
TERM_OUTSTANDING_SERIES = "temp_repo_term_outstanding"
#: The standing facility's material-use threshold, USD billions (Nicholas, answer 13).
MATERIAL_USE_BN = 1.0
#: `fed_repo_facility` codes.
NONE, TEMPORARY, STANDING = 0.0, 1.0, 2.0
NEW_YORK = ZoneInfo("America/New_York")


def _small_value_exercise(operation: Mapping[str, object]) -> bool:
    """The parent's test (`ingest._is_small_value_exercise`): the Desk names its operational tests in the note."""
    note = operation.get("note")
    return isinstance(note, str) and "small value exercise" in note.lower()


def daily_take_up(operations: Iterable[Mapping[str, object]], *, term: str) -> Dict[date, float]:
    """USD billions accepted per operation date, over the Desk's repo operations of `term` in the window.

    Raises:
        ValueError: on a kept operation with no numeric `totalAmtAccepted`.
    """
    totals: Dict[date, int] = {}
    for operation in operations:
        if operation.get("operationType") != "Repo" or operation.get("term") != term:
            continue
        day = date.fromisoformat(str(operation["operationDate"]))
        if not FIRST_OPERATION <= day <= LAST_OPERATION or _small_value_exercise(operation):
            continue
        accepted = operation.get("totalAmtAccepted")
        if isinstance(accepted, bool) or not isinstance(accepted, (int, float)):
            raise ValueError(f"the repo operation on {day} has no numeric totalAmtAccepted ({accepted!r})")
        totals[day] = totals.get(day, 0) + accepted
    return {day: round(total / 1e9, 9) for day, total in sorted(totals.items())}


def term_outstanding(operations: Iterable[Mapping[str, object]]) -> Dict[date, float]:
    """USD billions of the Desk's term repos outstanding on each weekday of the window: settled on or before the day
    and maturing after it. A weekday with nothing outstanding is 0.0, since the operations were on offer.

    Raises:
        ValueError: on a kept term operation with no numeric amount, settlement date or maturity date.
    """
    spans = []
    for operation in operations:
        if operation.get("operationType") != "Repo" or operation.get("term") != "Term":
            continue
        day = date.fromisoformat(str(operation["operationDate"]))
        if not FIRST_OPERATION <= day <= LAST_OPERATION or _small_value_exercise(operation):
            continue
        accepted = operation.get("totalAmtAccepted")
        if isinstance(accepted, bool) or not isinstance(accepted, (int, float)):
            raise ValueError(f"the term repo on {day} has no numeric totalAmtAccepted ({accepted!r})")
        try:
            settled = date.fromisoformat(str(operation["settlementDate"]))
            matures = date.fromisoformat(str(operation["maturityDate"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"the term repo on {day} has no valid settlement or maturity date") from error
        spans.append((settled, matures, accepted))
    out: Dict[date, float] = {}
    day = FIRST_OPERATION
    while day <= LAST_OPERATION:
        if day.weekday() < 5:
            out[day] = round(sum(a for s, m, a in spans if s <= day < m) / 1e9, 9)
        day += timedelta(days=1)
    return out


def available_at(day: date) -> datetime:
    """16:00 New York on the next weekday: the parent's `nyfed_srf` declaration for the same endpoint."""
    current = day + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return datetime.combine(current, time(16, 0), tzinfo=NEW_YORK)


def observations(totals: Mapping[date, float], *, series: str, source_sha: str):
    """Daily totals as the parent's point-in-time rows."""
    from repo_model.data import PointInTimeObservation

    return [PointInTimeObservation(series_id=series, ref_date=day, available_at=available_at(day), value=value,
                                   vintage_id=f"nyfed-rp-{day.isoformat()}", source_sha=source_sha)
            for day, value in sorted(totals.items())]


def load_snapshots(directory: Path = SNAPSHOTS) -> Tuple[List[Mapping[str, object]], str]:
    """Every saved search's operations, checked against its manifest, and one sha256 over the snapshots.

    Raises:
        ValueError: if a snapshot's bytes do not match its manifest.
    """
    operations, digests = [], []
    for manifest_path in sorted(directory.glob("*.json.manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        path = manifest_path.with_name(manifest["path"])
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["sha256"]:
            raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
        digests.append(digest)
        operations += json.loads(raw)["repo"]["operations"]
    return operations, hashlib.sha256("".join(digests).encode()).hexdigest()


def combined(row: Mapping[str, object]) -> Tuple[Optional[float], Optional[float]]:
    """A panel row's repo take-up and the facility it came from.

    `row` carries the row's date and its values of `temp_repo_take_up` and `srf_take_up`. Panel rows are dated by the
    day the values refer to; the parent's `asof.InformationRule` applies each source's publication lag when a row is
    read. A row dated before the first operation is a structural zero: no Fed repo was offered.

    Raises:
        ValueError: if a row carries both facilities.
    """
    temporary, standing = row.get(SERIES), row.get("srf_take_up")
    if temporary is not None and standing is not None:
        raise ValueError(f"{row['date']} reads both the temporary operations and the standing facility")
    if standing is not None:
        return standing, STANDING
    if temporary is not None:
        # A day with no overnight operation stays missing (a hole, never filled), whatever term repos are outstanding.
        return round(temporary + (row.get(TERM_OUTSTANDING_SERIES) or 0.0), 9), TEMPORARY
    if row["date"] < FIRST_OPERATION:
        return 0.0, NONE
    return None, None


def repo_material_use(row: Mapping[str, object]) -> Optional[float]:
    """The material-use event on every row from the start: 1.0 when the operations of the row's own date accepted
    `MATERIAL_USE_BN` or more in total, overnight and term alike (question 14), else 0.0.

    Before the first operation there were none, so 0.0. During the temporary operations a day's overnight and term
    operations are added. From the standing facility it is the facility's take-up. Missing on a day with no operation.
    """
    standing, overnight, term = row.get("srf_take_up"), row.get(SERIES), row.get(TERM_SERIES)
    if standing is not None:
        return material_use(standing)
    if overnight is not None or term is not None:
        return material_use((overnight or 0.0) + (term or 0.0))
    if row["date"] < FIRST_OPERATION:
        return 0.0
    return None


def material_use(take_up: Optional[float]) -> Optional[float]:
    """1.0 on take-up of at least `MATERIAL_USE_BN`, 0.0 below it, missing when take-up is."""
    if take_up is None:
        return None
    return 1.0 if take_up >= MATERIAL_USE_BN else 0.0


def write_snapshot(payload: bytes, first: date, last: date, retrieved_at: str, directory: Path = SNAPSHOTS) -> Path:
    """Save one search response unmodified, with its manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"rp_{first.isoformat()}_{last.isoformat()}.json"
    path.write_bytes(payload)
    manifest = {"path": path.name, "sha256": hashlib.sha256(payload).hexdigest(), "retrieved_at": retrieved_at,
                "url": URL.format(first=first.isoformat(), last=last.isoformat())}
    path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def check_declared_lag(registry: Mapping[str, Mapping], dates, observations) -> None:
    """Refuse a declaration under which some day's results would be read before they were public.

    Each observation's `available_at` is compared with the parent's `asof.declared_availability` for its field on the
    panel's dates. A day that is not a panel date cannot be read, and is skipped.

    Raises:
        LookAheadError: naming the first day public after its declared availability.
    """
    from repo_model.asof import declared_availability
    from repo_model.splits import LookAheadError

    position = {day: index for index, day in enumerate(dates)}
    for obs in observations:
        if obs.ref_date not in position:
            continue
        declared = declared_availability(registry, "nyfed_temp_repo", obs.series_id, dates, position[obs.ref_date])
        # The parent states declared instants as naive New York times.
        public = obs.available_at.astimezone(NEW_YORK).replace(tzinfo=None)
        if declared is None or public > declared:
            raise LookAheadError(
                f"{obs.series_id} for {obs.ref_date} is public at {public:%Y-%m-%d %H:%M}, after its "
                f"declared availability of {declared:%Y-%m-%d %H:%M}" if declared else
                f"{obs.series_id} for {obs.ref_date} has no declared availability")
