"""H10 prospective confirmation: the live entry point and the frozen method's digest (directive #87; finding #81).

The model repo owns the live record. Its job calls `attribute_onset` at this repository's commit, once for each new onset,
and publishes the row it returns. This module runs no schedule, writes no log and registers nothing. It decides nothing
about the method: the method is `docs/decisions/h10-method.md` (sections 1 to 10) and the code is
`repo_liquidity.attribution` and `repo_liquidity.h10_apply`; this module only calls them with the report instant fixed.

**The report instant** is the decision instant (16:00) of a panel day at most `REPORT_DAYS` (10) panel days after the onset
(plan, Q7; record section 3). Everything read is read as of that instant (record section 6): the window's spread and drivers
must have been public (`attribution.check_window_public`, through the parent's `InformationRule`), and the fitting sample,
the placebo windows and the selection null use only windows already public then. Rows after the last public day are cut off
before any of them is built.

**Development evidence only until the confirmation design is decided and a registration is made, which is Eleonora's
attested act.** Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, attribution, h10_apply
from repo_liquidity.attribution import BASELINE_DAYS, DRIVERS_WITH_ON_RRP, WINDOW_DAYS
from repo_liquidity.h10_apply import REPORT_DAYS
from repo_model.splits import LookAheadError

ROOT = Path(__file__).resolve().parents[2]
#: The frozen method, in the order it is hashed: the decision record, then the two code files that carry the method and its
#: tables. A path is shown in the digest by the name beside it, so the digest does not depend on where the checkout is.
METHOD_FILES: Tuple[Tuple[str, Path], ...] = (
    ("record:docs/decisions/h10-method.md", ROOT / "docs" / "decisions" / "h10-method.md"),
    ("code:src/repo_liquidity/attribution.py", ROOT / "src" / "repo_liquidity" / "attribution.py"),
    ("code:src/repo_liquidity/h10_apply.py", ROOT / "src" / "repo_liquidity" / "h10_apply.py"),
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
    }


def method_parts() -> List[Tuple[str, bytes]]:
    """The named parts the digest covers, in the fixed order they are hashed: the record, the code files, the constants."""
    parts = [(name, path.read_bytes()) for name, path in METHOD_FILES]
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
                    null_draws: int = attribution.NULL_DRAWS) -> dict:
    """Attribute one onset with the frozen method, as of the decision instant of `report_date`. A JSON-able row in the
    columns of the development table (`results/h10/development.json`), plus the method digest and the parent pin.

    `panel_rows` are the parent's `DailyObservation` rows, in date order; `rule` is the parent's `InformationRule` over the
    spread and the five drivers (`h10_apply.real_rule`). Rows after the last day public at the report instant are never
    read. An onset that cannot be attributed (an input missing, no rise in the spread, a singular fit) is returned as
    "not attributable" with the reason, never dropped.

    Raises:
        LookAheadError: a day of the rows is in a locked tier of the parent's lockbox, or an input of the onset's window was
            not public at the report instant.
        ValueError: the onset or report date is not a day of the rows; the report is before the onset or more than
            `REPORT_DAYS` panel days after it (plan, Q7); the onset is not an onset under the parent's rule.
    """
    rows = list(panel_rows)
    dates = [row.date for row in rows]
    attribution.check_development(dates)
    onset_index = _index(dates, onset_date, "onset")
    report_index = _index(dates, report_date, "report")
    if report_index < onset_index:
        raise ValueError(f"the report {report_date} is before the onset {onset_date}")
    if report_index - onset_index > REPORT_DAYS:
        raise ValueError(f"the onset {onset_date} is more than {REPORT_DAYS} panel days before the report {report_date}")
    last = last_public_start(rule, dates, report_index, onset_index)
    if last is None:
        visible = rows[: report_index + 1]
    else:
        visible = rows[: last + WINDOW_DAYS]
    onsets = attribution.cross_check_onsets(visible)
    if onset_index not in onsets:
        raise ValueError(f"{onset_date} is not an onset under the parent's rule")

    drivers = DRIVERS_WITH_ON_RRP
    series = attribution.series_from_rows(visible, drivers)
    result = attribution.attribute(series, onset_index, rule=rule, dates=dates[: report_index + 1], report_index=report_index,
                                   drivers=drivers, draws=draws, seed=attribution.SEED)

    from repo_model.contract import ON_RRP_DEPLETION_BREAK_BN

    on_rrp = series[attribution.ON_RRP][onset_index]
    row = {
        "onset": onset_date.isoformat(), "index": onset_index, "report_day": report_date.isoformat(),
        "status": result.status, "reason": result.reason, "rise_bp": result.rise_bp,
        "regime": None if on_rrp is None else ("depleted" if on_rrp < ON_RRP_DEPLETION_BREAK_BN else "abundant"),
        "quarter_end": bool(series["quarter_end"][onset_index]), "on_rrp_at_onset": on_rrp,
        "under_bar": False, "beats_null": False, "counted": False,
        "method_digest": method_digest(), "parent_commit": PARENT_COMMIT, "parent_panel_sha256": PANEL_SHA256,
        "last_day_read": visible[-1].date.isoformat(),
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
        unusable_draws=result.unusable_draws,
        under_bar=abs(result.residual_share) < attribution.RESIDUAL_BAR,
        beats_null=result.explained_share > null.bar,
    )
    row["counted"] = row["under_bar"] and row["beats_null"]
    return row
