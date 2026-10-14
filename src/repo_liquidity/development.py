"""The development tier's end, read from the model repo's lockbox on every call (one lockbox, never a copy).

`repo-market-model docs/decisions/lockbox.md` decides which days a comparison may read. This repository keeps no
second copy of those dates: a module that needs the last readable day, or to know whether one day is locked, asks the
parent's `repo_model.lockbox` here. Standard library only.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from repo_model import lockbox


def locked_tiers():
    """The parent's tiers that have not been opened, read from its declaration at call time."""
    return lockbox.locked_tiers(lockbox.DEFAULT_LOCKBOX)


def is_locked(day: date) -> bool:
    """Whether the parent's lockbox holds `day` (a tier that has not been opened contains it)."""
    return lockbox.locked_tier(day, locked_tiers()) is not None


def development_end() -> Optional[date]:
    """The last day before the earliest locked tier, or None when the parent's lockbox holds nothing."""
    tiers = locked_tiers()
    if not tiers:
        return None
    return min(tier.start for tier in tiers) - timedelta(days=1)
