"""H7m, development step 1: deployable liquidity and the distance to the kink, as one slow variable (`docs/stages/h7-step1.md`).

Deployable liquidity on day T is `R_T - k_T`: the parent's reserves ratio at T's decision instant minus the kink of the reserve
demand curve in force at the refit that serves T, both as shares of bank assets. The kink is the parent's fitted satiation
level (`repo_model.satiation.fit_level`). R and the scarcity state S are the parent's own functions of what the as-of rule
reads (`scarcity.reserves_ratio`, `scarcity.reserve_scarcity_state`); this module reads nothing but through
`repo_model.asof.InformationRule`, and rebuilds none of its guards.

A refit with cutoff `c` is fitted on the pairs whose scored day is on or before `c` (the ratio public at that day's own
decision and that day's SOFR - IORB spread) and serves the days from the second business day after `c`, up to the day the
next refit serves from. Filtered, never smoothed. A refit that cannot fit (too few pairs, or no candidate with a
non-negative slope) is reported as not fitted and serves no estimate: there is no fallback to the parent's fixed 0.12.

Nothing is scored here. `real_time_path` returns each refit's path and its gap to the previous refit on every day both
serve, so that step 5 can read goalpost 1 (`docs/decisions/measurement-protocol.md` §3).
"""

from __future__ import annotations

import random
from datetime import date, time
from typing import Dict, List, NamedTuple, Optional, Sequence

from repo_model import lockbox, scarcity, satiation
# The parent's date extension (business days appended to the dates handed to the rule, so a lag at the last real row is
# dated the same whatever follows it). Private in the parent, imported at the pin rather than copied (directive #58).
from repo_model.satiation import _EXTRA_DATES, _extended  # noqa: F401
from repo_model.asof import InformationRule
from repo_model.data import DailyObservation, next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError, SplitError

#: A refit serves from this many business days after its cutoff (Stage 3c's lag, `docs/stages/stage-3c.md:28`).
SERVING_LAG = 2
DECISION_TIME = time(16, 0)
#: The interval's conventions are the parent's (`scarcity.BOOTSTRAP_*`).
BLOCK_LENGTH = scarcity.BOOTSTRAP_BLOCK_LENGTH
LEVEL = scarcity.BOOTSTRAP_LEVEL
SEED = scarcity.BOOTSTRAP_SEED


class Day(NamedTuple):
    """One scored day: the ratio and the state public at its decision instant, and its own SOFR - IORB spread in bp."""

    day: date
    ratio: Optional[float]
    spread: Optional[float]
    state: Optional[float]


class Refit(NamedTuple):
    cutoff: date
    level: float
    fitted: bool
    lower: Optional[float]
    upper: Optional[float]
    pairs: int
    record: Dict[str, object]


class Estimate(NamedTuple):
    day: date
    ratio: float
    deployable: float
    lower: Optional[float]
    upper: Optional[float]
    state: Optional[float]


class RefitPath(NamedTuple):
    """One refit's real-time path: its served days, the gap to the previous refit on each, and the days it left missing."""

    refit: Refit
    estimates: List[Estimate]
    gaps: Dict[date, float]
    missing_days: int


def points(share: float) -> float:
    """Points of bank assets in a share of them."""
    return 100.0 * share


def dollars(share: float, bank_assets_bn: float) -> float:
    """USD billions in a share of `bank_assets_bn`."""
    return share * bank_assets_bn


# -- the as-of days ---------------------------------------------------------------------------------------------------


def asof_days(rows: Sequence[DailyObservation], rule: InformationRule) -> List[Day]:
    """The scored days with what was public at their decision instants: row `i + 1` is scored from the reads at row `i`.

    `rule` reads the state's three legs (`scarcity.LEGS`) under `scarcity.measurement_declaration()`. Each leg is read at
    its own latest public row. A day with a leg missing has no ratio and no state.

    Raises:
        LookAheadError: if a scored day is in a locked tier of the parent's lockbox, or the rule refuses a read.
        StaleReadError: if a read is older than the latest value public at the decision instant.
    """
    dates = [row.date for row in rows]
    out: List[Day] = []
    for i in range(len(rows) - 1):
        scored = rows[i + 1]
        spread = _spread(scored)
        extended = _extended(dates, i)
        try:
            info = rule.information_set(extended, i + 1)
        except SplitError:
            out.append(Day(scored.date, None, spread, None))
            continue
        rule.check(extended, info)
        read = {r.feature: r.row for r in info.reads}
        if any(leg not in read for leg in scarcity.LEGS):
            out.append(Day(scored.date, None, spread, None))
            continue
        reserves, assets, on_rrp = (rows[read[leg]].values.get(leg) for leg in scarcity.LEGS)
        ratio = None if reserves is None or assets is None else scarcity.reserves_ratio(float(reserves), float(assets))
        state = scarcity.reserve_scarcity_state(reserves, assets, on_rrp)
        out.append(Day(scored.date, ratio, spread, None if state is None else float(state)))
    lockbox.require_unlocked([d.day for d in out], where="h7_estimator.asof_days")
    return out


def _spread(row: DailyObservation) -> Optional[float]:
    sofr, iorb = row.values.get("sofr"), row.values.get("iorb")
    return None if sofr is None or iorb is None else (float(sofr) - float(iorb)) * 100.0


# -- one refit --------------------------------------------------------------------------------------------------------


def training_pairs(days: Sequence[Day], cutoff: date) -> List[Day]:
    """The days a refit at `cutoff` may fit on: scored on or before it, with a ratio and a spread."""
    return [d for d in days if d.day <= cutoff and d.ratio is not None and d.spread is not None]


def _require_on_or_before(days: Sequence[Day], cutoff: date) -> None:
    for d in days:
        if d.day > cutoff:
            raise LookAheadError(f"the kink for the refit at {cutoff} would be fitted on {d.day}, after its cutoff")


def refit(pairs: Sequence[Day], cutoff: date, *, replications: int, seed: int = SEED) -> Refit:
    """The kink of the refit at `cutoff`, fitted on `pairs` alone, with a stationary-bootstrap 90% interval.

    `replications` of 0 skips the interval. A refit that did not fit (the parent returns its fixed level) is `fitted`
    False, with no interval.

    Raises:
        LookAheadError: if a pair is scored after `cutoff`.
        ValueError: if a pair has no ratio or no spread.
    """
    _require_on_or_before(pairs, cutoff)
    if any(p.ratio is None or p.spread is None for p in pairs):
        raise ValueError("a training pair needs a ratio and a spread")
    ratios = [p.ratio for p in pairs]
    spreads = [p.spread for p in pairs]
    level, record = satiation.fit_level(ratios, spreads)
    fitted = bool(record.get("fitted"))
    lower = upper = None
    if fitted and replications > 0:
        rng = random.Random(seed)
        draws = []
        for _ in range(replications):
            index = stationary_bootstrap_indices(len(pairs), BLOCK_LENGTH, rng)
            draw, draw_record = satiation.fit_level([ratios[j] for j in index], [spreads[j] for j in index])
            if draw_record.get("fitted"):
                draws.append(draw)
        if draws:
            draws.sort()
            tail = (1.0 - LEVEL) / 2.0
            lower = min(satiation.quantile(draws, tail), level)
            upper = max(satiation.quantile(draws, 1.0 - tail), level)
    return Refit(cutoff, float(level), fitted, lower, upper, len(pairs), dict(record))


def refit_on(days: Sequence[Day], cutoff: date, *, replications: int, seed: int = SEED) -> Refit:
    """`refit` on the pairs `training_pairs` gives for `cutoff`."""
    return refit(training_pairs(days, cutoff), cutoff, replications=replications, seed=seed)


# -- the real-time path -----------------------------------------------------------------------------------------------


def real_time_path(
    days: Sequence[Day], cutoffs: Sequence[date], *, replications: int, seed: int = SEED
) -> List[RefitPath]:
    """Each refit's real-time path over the days it serves. Computed, not scored.

    Refit `k` at `cutoffs[k]` serves the days from the second business day after its cutoff to the day before refit
    `k + 1` serves from; the last serves to the final day. On every day refit `k > 0` serves, `gaps` holds the absolute
    difference between its estimate and refit `k - 1`'s for that day, when both fitted. A refit that did not fit serves no
    estimate: its days are counted in `missing_days`.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [next_business_day(c, SERVING_LAG) for c in cutoffs]
    refits = [refit_on(days, c, replications=replications, seed=seed) for c in cutoffs]
    out: List[RefitPath] = []
    for k, fit in enumerate(refits):
        end = starts[k + 1] if k + 1 < len(starts) else None
        served = [d for d in days if d.day >= starts[k] and (end is None or d.day < end)]
        estimates: List[Estimate] = []
        gaps: Dict[date, float] = {}
        missing = 0
        for d in served:
            if not fit.fitted or d.ratio is None:
                missing += 1
                continue
            lower = None if fit.upper is None else d.ratio - fit.upper
            upper = None if fit.lower is None else d.ratio - fit.lower
            estimates.append(Estimate(d.day, d.ratio, d.ratio - fit.level, lower, upper, d.state))
            if k > 0 and refits[k - 1].fitted:
                gaps[d.day] = abs((d.ratio - fit.level) - (d.ratio - refits[k - 1].level))
        out.append(RefitPath(fit, estimates, gaps, missing))
    return out


# -- the leakage check ------------------------------------------------------------------------------------------------


def check_no_future(
    rows: Sequence[DailyObservation], rule: InformationRule, path: Sequence[RefitPath], *, replications: int,
    seed: int = SEED,
) -> None:
    """Refuse a refit that is not what the panel cut at its own cutoff gives.

    Each refit is rebuilt from `rows` up to and including its cutoff row, through the rule, and compared.

    Raises:
        LookAheadError: a refit's kink, or whether it fitted, differs from the cut panel's, so it depended on a later row.
    """
    for p in path:
        cutoff = p.refit.cutoff
        cut = [row for row in rows if row.date <= cutoff]
        again = refit_on(asof_days(cut, rule), cutoff, replications=replications, seed=seed)
        if again.fitted != p.refit.fitted or abs(again.level - p.refit.level) > 1e-12:
            raise LookAheadError(
                f"the refit at {cutoff} has kink {p.refit.level}, but the panel cut at that row gives {again.level}; "
                "the refit depended on a later row"
            )
