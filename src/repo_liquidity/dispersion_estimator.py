"""HX step 2, milestone M1 (#210): the as-of estimator W1 over SOFR's interquartile width. Declared; nothing is scored.

`docs/research/dispersion-estimator.md` declares the form **before anything is fitted**. W1 is H7m candidate A's kink with
exactly one change of observable, the left side: the target day's `sofr_p75_p25_bp` (the hypothesis's primary measure,
`dispersion_volume.INPUTS`) in place of its SOFR - IORB spread, fitted on calendar-clean days only
(`docs/stages/h7-calendar-clean.md` section 2(a)). Everything else is the parent's and H7m's own:

* deployable liquidity on day T is the reserves ratio public at T's decision instant minus the kink of the reserve demand
  curve in force, in points of bank assets (`h7_estimator.points`); the kink is the parent's `satiation.fit_level`, whose
  fit is on any left side handed to it, and its 90% interval is `h7_estimator.refit`'s stationary bootstrap;
* a refit at cutoff `c` fits on days scored on or before `c` and serves from the second business day after it
  (`SERVING_LAG`), which is the first day on which the width of `c` itself is public (one business day, 15:00 ET);
* filtered, never smoothed; a refit that does not fit serves no estimate, with no fallback.

The width is a training label (an outcome of a day on or before the cutoff), never an input read at a decision instant, so
the leakage guards are the cutoff (`h7_estimator.refit`) and the publication lag of the width (`check_width_public`). The
kink carried between refits is guarded by `check_in_force`. Nothing here reads a day of the lockbox (`check_development`).

Standard library only, apart from the parent and `h7_estimator`'s own imports.
"""

from __future__ import annotations

import collections
from datetime import date, time
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence

from repo_model import lockbox
from repo_model.asof import InformationRule, StaleReadError
from repo_model.data import DailyObservation, next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import dispersion_volume, h7_clean
from repo_liquidity import h7_estimator as h7

NAME = "W1"
#: The left side: SOFR's interquartile width in basis points, the hypothesis's primary measure.
LEFT_COLUMN = "sofr_p75_p25_bp"
#: A refit serves from this many business days after its cutoff: the first day on which the width of the cutoff day is public.
SERVING_LAG = h7.SERVING_LAG
DECISION_TIME = time(16, 0)
#: The variant count (measurement protocol v1 section 10): 12 estimators in play are carried from
#: `docs/research/dispersion-volume-hypothesis.md` section 4, and W1 is one more.
VARIANTS_CARRIED = 12
VARIANTS_IN_PLAY = VARIANTS_CARRIED + 1
#: The last development day (`docs/decisions/lockbox.md`); a later day is in a locked tier.
LAST_DEVELOPMENT_DAY = date(2026, 9, 3)


class WidthDay(NamedTuple):
    """One scored day: the ratio public at its decision instant and its own width in bp (None where not read)."""

    day: date
    ratio: Optional[float]
    width: Optional[float]


def check_development(days: Sequence[date]) -> None:
    """Refuse a day in a locked tier of the parent's lockbox.

    Raises:
        LookAheadError: a day is locked.
    """
    lockbox.require_unlocked(days, where="dispersion_estimator")


def width_days(rows: Sequence[DailyObservation], rule: InformationRule) -> List[WidthDay]:
    """The scored days: the ratio public at each decision instant (`h7_estimator.asof_days`, through `rule`) and the scored
    row's own `LEFT_COLUMN` (`indicators.with_indicators` adds it to the panel's rows).

    Raises:
        LookAheadError: a scored day is locked, or the rule refuses a read.
        StaleReadError: a read is older than the latest value public at the decision instant.
    """
    base = h7.asof_days(rows, rule)
    out: List[WidthDay] = []
    for scored, day in zip(rows[1:], base):
        value = scored.values.get(LEFT_COLUMN)
        out.append(WidthDay(day.day, day.ratio, None if value is None else float(value)))
    return out


# -- one refit --------------------------------------------------------------------------------------------------------


def training_pairs(days: Sequence[WidthDay], cutoff: date, flags: Mapping[date, h7_clean.Flags]) -> List[WidthDay]:
    """The days a refit at `cutoff` fits on: scored on or before it, with a ratio and a width, and calendar-clean.

    Raises:
        ValueError: a day has no flags or a flag is a hole (`h7_clean.Flags.dropped`).
    """
    out = []
    for x in days:
        if x.day <= cutoff and x.ratio is not None and x.width is not None:
            if x.day not in flags:
                raise ValueError(f"{x.day} has no calendar flags")
            if not flags[x.day].dropped():
                out.append(x)
    return out


def fit_pairs(pairs: Sequence[WidthDay], cutoff: date, *, replications: int, seed: int = h7.SEED) -> h7.Refit:
    """The kink of the refit at `cutoff`, fitted on `pairs` alone (`h7_estimator.refit`, the width as the left side).

    Raises:
        LookAheadError: a pair is scored after `cutoff`.
        ValueError: a pair has no ratio or no width, or the window runs across the 2027-06-30 break.
    """
    if pairs:
        dispersion_volume.check_not_across_break(LEFT_COLUMN, min(p.day for p in pairs), max(cutoff, max(p.day for p in pairs)))
    return h7.refit([h7.Day(p.day, p.ratio, p.width, None) for p in pairs], cutoff, replications=replications, seed=seed)


def refit(days: Sequence[WidthDay], cutoff: date, flags: Mapping[date, h7_clean.Flags], *, replications: int,
          seed: int = h7.SEED) -> h7.Refit:
    """`fit_pairs` on the pairs `training_pairs` gives for `cutoff`."""
    return fit_pairs(training_pairs(days, cutoff, flags), cutoff, replications=replications, seed=seed)


def estimate(day: WidthDay, fit: h7.Refit) -> h7.Estimate:
    """Deployable liquidity on `day` under `fit`: the ratio less the kink, with the interval's ends from the fit's.

    Raises:
        ValueError: `fit` did not fit (it serves no estimate), or `day` has no ratio.
    """
    if not fit.fitted:
        raise ValueError(f"the refit at {fit.cutoff} did not fit; it serves no estimate")
    if day.ratio is None:
        raise ValueError(f"{day.day} has no ratio")
    lower = None if fit.upper is None else day.ratio - fit.upper
    upper = None if fit.lower is None else day.ratio - fit.lower
    return h7.Estimate(day.day, day.ratio, day.ratio - fit.level, lower, upper, None)


# -- the guards -------------------------------------------------------------------------------------------------------


def served_from(cutoff: date) -> date:
    """The first day a refit at `cutoff` serves."""
    return next_business_day(cutoff, SERVING_LAG)


def check_width_public(dates: Sequence[date], rule: InformationRule, cutoff: date, *, served: date) -> None:
    """Refuse a refit that serves before the width of its last training day is public.

    `rule` reads `LEFT_COLUMN` under `declaration.phase3_declaration()`. The latest width public at `served`'s decision instant
    must be that of `cutoff` or a later day.

    Raises:
        LookAheadError: the latest width public when `served` is decided is older than the cutoff's, so the refit's last
            training label was not yet public.
        StaleReadError: the rule's own staleness check.
    """
    extended = list(dates)
    while extended[-1] < served:
        extended.append(next_business_day(extended[-1], 1))
    last_row, served_row = extended.index(cutoff), extended.index(served)
    info = rule.information_set(extended, served_row)
    rule.check(extended, info)
    for read in info.reads:
        if read.feature == LEFT_COLUMN and read.row < last_row:
            raise LookAheadError(
                f"{LEFT_COLUMN} of {cutoff} is not public when {served} is decided (latest public: {extended[read.row]}); "
                "the refit would serve before its last training width is known")


def refit_in_force(cutoffs: Sequence[date], day: date) -> Optional[date]:
    """The cutoff of the latest refit that has begun to serve on `day`, or None before the first."""
    begun = [c for c in cutoffs if served_from(c) <= day]
    return max(begun) if begun else None


def check_in_force(cutoffs: Sequence[date], used: date, day: date) -> None:
    """Refuse an estimate on `day` from any refit but the one in force: an older one is stale, a later one is look-ahead.

    Raises:
        LookAheadError: the refit at `used` has not begun to serve on `day`.
        StaleReadError: a later refit is already in force on `day`.
    """
    if served_from(used) > day:
        raise LookAheadError(f"the refit at {used} serves from {served_from(used)}, after {day}")
    latest = refit_in_force(cutoffs, day)
    if used < latest:
        raise StaleReadError(f"the refit at {used} is carried on {day}, but the refit at {latest} is in force")


# -- the resolution fact ----------------------------------------------------------------------------------------------


def resolution(values: Sequence[Optional[float]]) -> Dict[str, object]:
    """How many distinct values the width takes: a descriptive fact, not a score."""
    present = [v for v in values if v is not None]
    counts = collections.Counter(present)
    modal, modal_count = (counts.most_common(1)[0] if counts else (None, 0))
    return {
        "days": len(present),
        "missing": len(values) - len(present),
        "distinct": len(counts),
        "minimum": min(present) if present else None,
        "maximum": max(present) if present else None,
        "modal_value": modal,
        "modal_share": round(modal_count / len(present), 6) if present else None,
    }


def resolution_record(rows: Sequence[DailyObservation]) -> Dict[str, object]:
    """The resolution fact over the development panel `rows`: every day, and the calendar-clean days W1 fits on.

    Development days only; nothing is fitted or scored.

    Raises:
        LookAheadError: a day is locked.
    """
    from repo_liquidity import indicators

    development = [r for r in rows if r.date <= LAST_DEVELOPMENT_DAY]
    check_development([r.date for r in development])
    measured = indicators.with_indicators(development)
    scored = h7_clean.with_quarter_end_window(measured)
    flags = h7_clean.read_flags(scored, h7_clean.flag_rule())
    widths = {r.date: r.values.get(LEFT_COLUMN) for r in measured}
    days = [r.date for r in measured[1:]]
    clean = [d for d in days if not flags[d].dropped()]
    return {
        "column": LEFT_COLUMN,
        "scored": False,
        "first_day": days[0].isoformat(),
        "last_day": days[-1].isoformat(),
        "all_days": resolution([widths[d] for d in days]),
        "calendar_clean_days": resolution([widths[d] for d in clean]),
        "calendar_days_dropped": len(days) - len(clean),
    }
