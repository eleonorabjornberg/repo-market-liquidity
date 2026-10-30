"""H10 prospective confirmation: the live entry point and the frozen method's digest (directive #87; finding #81).

The model repo owns the live record. Its job calls `attribute_onset` at this repository's commit, once for each new onset,
and publishes the row it returns. This module runs no schedule, writes no log and registers nothing. It decides nothing
about the method: the method is `docs/decisions/h10-method.md` (sections 1 to 10) and the code is
`repo_liquidity.attribution` and `repo_liquidity.h10_apply`; this module only calls them with the report instant fixed.

**The report instant** is the decision instant (`h10_apply.DECISION_TIME`, 18:00) of a panel day at most `REPORT_DAYS` (10) panel days after the onset
(plan, Q7; record section 3). Everything read is read as of that instant (record section 6): the window's spread and drivers
must have been public (`attribution.check_window_public`, through the parent's `InformationRule`), and the fitting sample,
the placebo windows and the selection null use only windows already public then. Rows after the last public day are cut off
before any of them is built. A row dated after the report day is refused, not cut off (`check_no_row_after_report`).

**Development evidence only until the confirmation design is decided and a registration is made, which is Eleonora's
attested act.** Standard library only.
"""

from __future__ import annotations

import functools
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, attribution, h10_apply, h10_registration, parent_root
from repo_liquidity.attribution import BASELINE_DAYS, DRIVERS_WITH_ON_RRP, WINDOW_DAYS
from repo_liquidity.h10_apply import REPORT_DAYS
from repo_model import lockbox
from repo_model.contract import ON_RRP_DEPLETION_BREAK_BN
from repo_model.splits import LookAheadError

ROOT = Path(__file__).resolve().parents[2]
#: The frozen method, in the order it is hashed: the decision record, then the code files that carry the method, its tables
#: and the live entry point (the as-of cut, the regime split and `counted`; finding #119, point 4). A path is shown in the
#: digest by the name beside it, so the digest does not depend on where the checkout is.
METHOD_FILES: Tuple[Tuple[str, Path], ...] = (
    ("record:docs/decisions/h10-method.md", ROOT / "docs" / "decisions" / "h10-method.md"),
    ("code:src/repo_liquidity/attribution.py", ROOT / "src" / "repo_liquidity" / "attribution.py"),
    ("code:src/repo_liquidity/h10_apply.py", ROOT / "src" / "repo_liquidity" / "h10_apply.py"),
    ("code:src/repo_liquidity/h10_live.py", ROOT / "src" / "repo_liquidity" / "h10_live.py"),
)
#: The parent code a live result depends on, read from the imported `repo_model` tree and named in the digest by the pinned
#: commit and the file: the onset rule, the pressure onsets it is cross-checked with, `InformationRule`, the contract that
#: holds `ON_RRP_DEPLETION_BREAK_BN`, and the stationary bootstrap. Guards that only refuse a run are not a part of the parent's side.
PARENT_METHOD_FILES: Tuple[str, ...] = (
    "src/repo_model/onset.py",
    "src/repo_model/pressure.py",
    "src/repo_model/asof.py",
    "src/repo_model/contract.py",
    "src/repo_model/metrics.py",
)


# --------------------------------------------------------------------------- the method digest


def record_sha256() -> str:
    """The sha256 of the method record file alone: the number PR #78's page called "method record sha256"."""
    return hashlib.sha256(METHOD_FILES[0][1].read_bytes()).hexdigest()


def decided_constants() -> dict:
    """The decided values of the method, read from the code that uses them, as a JSON-able mapping."""
    return {
        "baseline_days": attribution.BASELINE_DAYS,
        "window_days": attribution.WINDOW_DAYS,
        "placebo_windows": attribution.PLACEBO_WINDOWS,
        "placebo_rise_floor_bp": attribution.PLACEBO_RISE_FLOOR_BP,
        "block_length": attribution.BLOCK_LENGTH,
        "draws": attribution.DRAWS,
        "seed": attribution.SEED,
        "level": attribution.LEVEL,
        "residual_bar": attribution.RESIDUAL_BAR,
        "majority": attribution.MAJORITY,
        "max_unusable_draws": attribution.MAX_UNUSABLE_DRAWS,
        "null_draws": attribution.NULL_DRAWS,
        "null_quantile": attribution.NULL_QUANTILE,
        "drivers": list(attribution.DRIVERS_WITH_ON_RRP),
        "report_days": h10_apply.REPORT_DAYS,
        "decision_time": h10_apply.DECISION_TIME.isoformat(),
        "on_rrp_depletion_break_bn": ON_RRP_DEPLETION_BREAK_BN,
    }


def method_parts() -> List[Tuple[str, bytes]]:
    """The named parts the digest covers, in the fixed order they are hashed: the record, the code files, the parent files
    (named by the pinned commit) and the constants."""
    parts = [(name, path.read_bytes()) for name, path in METHOD_FILES]
    root = parent_root()
    parts.extend((f"parent@{PARENT_COMMIT}:{relative}", (root / relative).read_bytes()) for relative in PARENT_METHOD_FILES)
    parts.append(("constants", json.dumps(decided_constants(), sort_keys=True, separators=(",", ":")).encode("utf-8")))
    return parts


def method_digest() -> str:
    """One sha256 over the frozen method: each part is hashed as `name NUL length NUL bytes`, in `method_parts` order.

    This is not PR #78's number. That was the sha256 of the record file alone (`record_sha256`), taken before section 10
    (the 2 bp placebo floor, PR #88) amended the record; today's record has a different sha256, and this digest covers the
    code and the constants as well. `tests/test_h10_live.py` reproduces #78's number from the record as it stood then.
    """
    digest = hashlib.sha256()
    for name, content in method_parts():
        digest.update(name.encode("utf-8") + b"\0" + str(len(content)).encode("ascii") + b"\0" + content)
    return digest.hexdigest()


# --------------------------------------------------------------------------- the stamp: what the row was computed from


def rows_sha256(panel_rows) -> str:
    """The sha256 of the rows as given: each row's date, spread and values as sorted compact JSON, one per line, in order."""
    digest = hashlib.sha256()
    for row in panel_rows:
        line = json.dumps([row.date.isoformat(), row.spread_bps, sorted(row.values.items())], separators=(",", ":"))
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


@functools.lru_cache(maxsize=1)
def published_panel_rows_sha256() -> str:
    """`rows_sha256` of the pinned published panel to the development end (`h10_apply.load_development`, which refuses a
    rebuild that is not the manifest's)."""
    return rows_sha256(h10_apply.load_development()[0])


def _parent_git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(parent_root()), *args], check=True, capture_output=True, text=True).stdout.strip()


def imported_parent_commit() -> Optional[str]:
    """The commit of the checkout `repo_model` is imported from, read now; None if it is not a git checkout."""
    try:
        return _parent_git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return None


def imported_parent_clean() -> Optional[bool]:
    """Whether that checkout has no modified tracked file; None if it is not a git checkout."""
    try:
        return _parent_git("status", "--porcelain", "--untracked-files=no") == ""
    except (OSError, subprocess.CalledProcessError):
        return None


def check_parent_at_pin(allow_unpinned_parent: bool) -> Tuple[Optional[str], Optional[bool]]:
    """The imported `repo_model` commit and whether its tree is clean, after checking they are `PARENT_COMMIT` and clean.

    Raises:
        ValueError: the imported `repo_model` is not a clean checkout of `PARENT_COMMIT` and no override is passed.
    """
    commit, clean = imported_parent_commit(), imported_parent_clean()
    if not allow_unpinned_parent:
        if commit != PARENT_COMMIT:
            raise ValueError(f"the imported repo_model is at {commit}, not the pinned {PARENT_COMMIT}")
        if not clean:
            raise ValueError(f"the imported repo_model at {commit} has modified tracked files")
    return commit, clean


# --------------------------------------------------------------------------- the guards of the live read (#200)

#: The locked tiers of the parent's lockbox (`metadata/lockbox.json`) that the live path may read: the open-ended `blind` tier.
#: No comparison scores it (scoring protocol #640, section 3 of its rulings: scoring confirmation days opens them, by her own
#: attested action), so a day in it does not refuse the live path (Eleonora, 30 October 2026, repo-market-model#1324, option 2).
#: A locked tier not named here is refused through `lockbox.require_unlocked`.
LIVE_READABLE_TIERS: Tuple[str, ...] = ("blind",)


def check_no_row_after_report(dates: Sequence[date], report_date: date) -> None:
    """Refuse any row dated after the report day: no day after the report instant is read.

    Raises:
        LookAheadError: a row is dated after `report_date`.
    """
    late = [day for day in dates if day > report_date]
    if late:
        raise LookAheadError(f"the rows hold {len(late)} day(s) after the report day {report_date} (first {min(late)}); "
                             f"a live attribution reads no day after its report instant")


def check_scored_tiers(dates: Sequence[date]) -> None:
    """Refuse a day in a locked tier of the parent's lockbox that the live path may not read (`LIVE_READABLE_TIERS` are read).

    Raises:
        LookAheadError: a day is in a locked tier a comparison scores.
    """
    readable = [tier for tier in lockbox.load_lockbox(lockbox.DEFAULT_LOCKBOX) if tier.name in LIVE_READABLE_TIERS]
    scored = [day for day in dates if lockbox.locked_tier(day, readable) is None]
    lockbox.require_unlocked(scored, where="h10_live")


def check_live_dates(dates) -> None:
    """The lockbox check the live path makes in place of `attribution.check_development`."""
    check_scored_tiers(list(dates))


# --------------------------------------------------------------------------- the entry point


def _index(dates: Sequence[date], day: date, what: str) -> int:
    try:
        return list(dates).index(day)
    except ValueError:
        raise ValueError(f"the {what} date {day} is not a day of the panel rows") from None


def last_public_start(rule, dates: Sequence[date], report_index: int, onset_index: int) -> Optional[int]:
    """The latest window start, from the onset's own on, whose whole window (baseline and days) was public at the decision
    instant of `report_index`; None if not even the onset's window was. A window is public when `check_window_public` passes,
    and an earlier start is no later than a later one, so the scan stops at the first that passes."""
    for start in range(report_index - WINDOW_DAYS + 1, onset_index - 1, -1):
        try:
            attribution.check_window_public(rule, dates, start, report_index)
        except LookAheadError:
            continue
        return start
    return None


def attribute_onset(panel_rows, rule, onset_date: date, report_date: date, *, draws: int = attribution.DRAWS,
                    null_draws: int = attribution.NULL_DRAWS, allow_unpinned_parent: bool = False,
                    registered_digest: str = h10_registration.REGISTERED_DIGEST) -> dict:
    """Attribute one onset with the frozen method, as of the decision instant of `report_date`. A JSON-able row in the
    columns of the development table (`results/h10/development.json`), plus the method digest and the parent pin.

    `panel_rows` are the parent's `DailyObservation` rows, in date order; `rule` is the parent's `InformationRule` over the
    spread and the five drivers (`h10_apply.real_rule`). Rows after the last day public at the report instant are never
    read. An onset that cannot be attributed (an input missing, no rise in the spread, a singular fit) is returned as
    "not attributable" with the reason, never dropped.

    Raises:
        LookAheadError: a row is dated after `report_date` (checked first, before any fit, placebo or null is built); a day
            of the rows is in a locked tier of the parent's lockbox that a comparison scores (the open-ended `blind` tier is
            not refused, `LIVE_READABLE_TIERS`); or an input of the onset's window was not public at the report instant.
        ValueError: the onset or report date is not a day of the rows; the report is before the onset or more than
            `REPORT_DAYS` panel days after it (plan, Q7); the onset is not an onset under the parent's rule; the imported
            `repo_model` is not a clean checkout of `PARENT_COMMIT` (unless `allow_unpinned_parent`, which the row records); this
            code's `method_digest()` is not the digest registered on #23 (`h10_registration.REGISTERED_DIGEST`, #200). The
            live job passes nothing for `registered_digest`; only a test of the computation passes another.
    """
    h10_registration.check_registered(method_digest(), registered_digest)
    imported_commit, imported_clean = check_parent_at_pin(allow_unpinned_parent)
    rows = list(panel_rows)
    dates = [row.date for row in rows]
    if report_date < onset_date:
        raise ValueError(f"the report {report_date} is before the onset {onset_date}")
    check_no_row_after_report(dates, report_date)
    check_scored_tiers(dates)
    onset_index = _index(dates, onset_date, "onset")
    report_index = _index(dates, report_date, "report")
    if report_index - onset_index > REPORT_DAYS:
        raise ValueError(f"the onset {onset_date} is more than {REPORT_DAYS} panel days before the report {report_date}")
    last = last_public_start(rule, dates, report_index, onset_index)
    if last is None:
        visible = rows[: report_index + 1]
    else:
        visible = rows[: last + WINDOW_DAYS]
    onsets = attribution.cross_check_onsets(visible, check=check_live_dates)
    if onset_index not in onsets:
        raise ValueError(f"{onset_date} is not an onset under the parent's rule")

    drivers = DRIVERS_WITH_ON_RRP
    series = attribution.series_from_rows(visible, drivers)
    result = attribution.attribute(series, onset_index, rule=rule, dates=dates[: report_index + 1], report_index=report_index,
                                   drivers=drivers, draws=draws, seed=attribution.SEED)

    on_rrp = series[attribution.ON_RRP][onset_index]
    row = {
        "onset": onset_date.isoformat(), "index": onset_index, "report_day": report_date.isoformat(),
        "status": result.status, "reason": result.reason, "rise_bp": result.rise_bp,
        "regime": None if on_rrp is None else ("depleted" if on_rrp < ON_RRP_DEPLETION_BREAK_BN else "abundant"),
        "quarter_end": bool(series["quarter_end"][onset_index]), "on_rrp_at_onset": on_rrp,
        "under_bar": False, "beats_null": False, "counted": False,
        "method_digest": method_digest(), "parent_commit": PARENT_COMMIT, "parent_panel_sha256": PANEL_SHA256,
        "last_day_read": visible[-1].date.isoformat(),
        "panel_rows_sha256": rows_sha256(rows),
        "rows_are_published_panel": rows_sha256(rows) == published_panel_rows_sha256(),
        "imported_parent_commit": imported_commit, "imported_parent_clean": imported_clean,
        "parent_override": allow_unpinned_parent,
    }
    if result.status != "attributed":
        return row
    placebo_windows = attribution.placebo_starts(series, onsets, attribution.PLACEBO_WINDOWS, attribution.SEED)[onset_index]
    placebo = [attribution.point_attribution(series, s, drivers=drivers) for s in placebo_windows]
    null = attribution.selection_null(series, drivers, draws=null_draws, seed=attribution.SEED)
    row.update(
        shares={name: h10_apply._share(result.shares[name], result.intervals[name]) for name in drivers},
        fixed_shares=dict(result.fixed_shares),
        residual=h10_apply._share(result.residual_share, result.residual_interval),
        explained_share=result.explained_share,
        explained_above_reserves=attribution.explained_above_reserves(series, onset_index, drivers),
        placebo=h10_apply.placebo_summary(placebo, result.explained_share),
        placebo_floored=h10_apply.floored_placebo_summary(placebo, result.explained_share),
        unusable_draws=result.unusable_draws,
        under_bar=abs(result.residual_share) < attribution.RESIDUAL_BAR,
        beats_null=result.explained_share > null.bar,
    )
    row["counted"] = row["under_bar"] and row["beats_null"]
    return row
