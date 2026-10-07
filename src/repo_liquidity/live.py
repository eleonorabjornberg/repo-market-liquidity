"""Stage 5a: the daily log's guards (`docs/stages/stage-5a.md`).

- **The FOMC guard.** The frozen declaration reads IORB and the ON RRP rate from two tables extended after each FOMC
  by a reviewed pull request. A day whose decision instant follows a scheduled FOMC statement that either table does
  not yet cover is refused (`ValueError`), so a missed update is a visible refusal, never a stale rate. The scheduled
  statements are `metadata/fomc_calendar.json`, read from the Board's calendar page, saved as a fixture.
- **Development days are never logged.** The log starts after the development window (to 2025-12-31). Days before its
  schedule is turned on are not confirmatory; that is the scoring's rule, not a refusal here.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import List, Mapping, NamedTuple, Optional, Sequence

from repo_liquidity import scheduled

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ROOT / "metadata" / "fomc_calendar.json"
CALENDAR_PAGE = ROOT / "tests" / "fixtures" / "snapshots" / "fomc_calendar" / "fomccalendars.htm.gz"
#: FOMC statements are released at 14:00 New York time, the time every rate-table row carries.
STATEMENT_TIME = time(14, 0)
#: The development window's last day (`docs/decisions/evaluation.md`).
LAST_DEVELOPMENT_DAY = date(2025, 12, 31)


class Statement(NamedTuple):
    meeting: str
    instant: datetime


def load_fomc_calendar() -> List[Statement]:
    """The scheduled FOMC statements, in order.

    Raises:
        ValueError: if the saved page does not match its manifest, or the calendar's time is not the statements'.
    """
    manifest = json.loads(CALENDAR_PAGE.with_name(CALENDAR_PAGE.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(CALENDAR_PAGE.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{CALENDAR_PAGE.name} does not match its manifest ({digest} != {manifest['sha256']})")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8"))
    if time.fromisoformat(calendar["statement_time"]) != STATEMENT_TIME or calendar["timezone"] != "America/New_York":
        raise ValueError(f"{CALENDAR.name}: statements are at {STATEMENT_TIME} America/New_York")
    return [Statement(entry["meeting"], datetime.combine(date.fromisoformat(entry["statement_date"]), STATEMENT_TIME))
            for entry in calendar["statements"]]


def table_coverage() -> Mapping[str, datetime]:
    """The last announcement each rate table carries."""
    return {scheduled.IORB_RATE_TABLE.name: scheduled.load_iorb_rates()[-1].announced_at,
            scheduled.ON_RRP_RATE_TABLE.name: scheduled.load_on_rrp_rates()[-1].announced_at}


def require_tables_cover(decision_instant: datetime, tables: Mapping[str, datetime],
                         statements: Optional[Sequence[Statement]] = None) -> None:
    """Raise unless every rate table covers the latest scheduled statement made by `decision_instant`.

    Raises:
        ValueError: naming the statement and each table that does not yet carry it.
    """
    statements = load_fomc_calendar() if statements is None else statements
    made = [statement for statement in statements if statement.instant <= decision_instant]
    if not made:
        return
    statement = made[-1]
    behind = [name for name, last in sorted(tables.items()) if last < statement.instant]
    if behind:
        raise ValueError(f"the FOMC statement of {statement.meeting} ({statement.instant}) precedes the "
                         f"{decision_instant} decision, but {', '.join(behind)} do not yet carry it; extend the tables "
                         f"by a reviewed pull request before this day is logged")


def require_loggable(day: date) -> None:
    """Raise if `day` is in the development window.

    Raises:
        ValueError: for a day on or before `LAST_DEVELOPMENT_DAY`.
    """
    if day <= LAST_DEVELOPMENT_DAY:
        raise ValueError(f"{day} is in the development window (to {LAST_DEVELOPMENT_DAY}); the log never writes it")
