"""The Fed's repo take-up: the 2019 to 2021 temporary operations, then the standing facility.

`docs/stages/stage-1a-correction.md`, items 2 and 3, from Nicholas Beroud's answers 5 and 13
(`docs/decisions/data-meaning.md`):

- **before 2019-09-17** no Fed repo was offered, so take-up is a structural zero;
- **from 2019-09-17 to 2021-07-28** the Desk's temporary open market operations are take-up from a different facility.
  They are read here from the NY Fed's operation results, saved under `tests/fixtures/snapshots/nyfed_temp_repo/`;
- **from 2021-07-29** the standing facility's take-up is the parent's `nyfed_srf`, as Stage 1a reads it.

Overnight operations are the take-up. Term operations are kept as their own column until Nicholas answers question 14
on issue #1. Material use of the standing facility is take-up of $1bn or more, a threshold he fixed in advance.
Standard library only.
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
TERM_SERIES = "temp_repo_term_take_up"
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
        return temporary, TEMPORARY
    if row["date"] < FIRST_OPERATION:
        return 0.0, NONE
    return None, None


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
