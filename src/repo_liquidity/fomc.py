"""The FOMC meeting calendar, as the parent holds it (parent #1038; directive #149).

A thin reader over `repo_model.fomc_calendar`, the parent's point-in-time calendar: every meeting with the instant it
became public and, for the one cancelled meeting, the instant its cancellation did. Nothing here is a calendar of its
own and no meeting date is written in this module (never re-implement the parent's calendar). A meeting is returned only
through the parent's `visible_at`, and each one returned has passed the parent's `require_public` (`LookAheadError` if
not).

The saved Board page (`tests/fixtures/snapshots/fomc_calendar/`) is a cross-check only, in `tests/test_fomc.py`.

Instants are naive America/New_York wall-clock datetimes, as in the parent.

Standard library only (the parent's `repo_model` is imported).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Tuple

from repo_model.fomc_calendar import Meeting, load_calendar, require_public, visible_at

__all__ = ["Meeting", "load", "meetings_at", "require_public"]


def load() -> Tuple[Meeting, ...]:
    """Every meeting of the parent's calendar, in start order (`repo_model.fomc_calendar.load_calendar`)."""
    return load_calendar()


def meetings_at(as_of: datetime, calendar: Optional[Sequence[Meeting]] = None) -> Tuple[Meeting, ...]:
    """The meetings public at `as_of`, and not yet cancelled then, in start order.

    Raises:
        ValueError: if `as_of` is not a naive wall-clock datetime.
        LookAheadError: if a meeting that reached the result was not public at `as_of`.
    """
    if not isinstance(as_of, datetime) or as_of.tzinfo is not None:
        raise ValueError("as_of is a naive America/New_York wall-clock datetime")
    meetings = load() if calendar is None else calendar
    seen = [meeting for meeting in meetings if visible_at(meeting, as_of)]
    return tuple(require_public(meeting, as_of) for meeting in seen)
