"""H7m, development step 2: candidate C, the buffer set by H.8 bank group (`docs/stages/h7-step2.md`).

Aggregate deployable liquidity on day T is the sum over the three H.8 groups of max(group reserves - share x group assets, 0),
over the groups' total assets: a share of bank assets, as step 1's `R - k` is. The group reserves are #43's weekly series
(`repo_liquidity.group_reserves`, an approximation: H.4.1 reserves split by the groups' cash-asset shares); the assets are the
H.8 first prints of the same week. Each day reads the latest week public at its decision instant.

The three shares are fitted so that the aggregate, through Stage 2's broken stick (`demand_curve.fit_broken_stick`), best
explains the corridor position in the counted scarce episodes, on training rows only: a refit with cutoff `c` fits on days
scored on or before `c` and serves from the second business day after it, as in step 1. A refit with no counted episode is not
fitted and serves no estimate; there is no fallback. Its interval is a stationary bootstrap of the shares. A break week of the
H.8 groups (data-meaning answer 17(c), Q18) is flagged, never refused and never adjusted.

Reads nothing but through the parent's as-of rule and the group series' own `public_at`; rebuilds none of the parent's guards.
Nothing is scored here: `real_time_path` returns each refit's path and its gap to the previous refit for step 5.
"""

from __future__ import annotations

import random
from datetime import date, datetime
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from repo_model import satiation
from repo_model.asof import InformationRule, StaleReadError
from repo_model.data import DailyObservation, next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError

from repo_liquidity import demand_curve, development, group_reserves, h7_estimator as h7, h8, scheduled

GROUPS = ("large_domestic", "small_domestic", "foreign_related")
SERVING_LAG = h7.SERVING_LAG
BLOCK_LENGTH, LEVEL, SEED = h7.BLOCK_LENGTH, h7.LEVEL, h7.SEED
points, dollars = h7.points, h7.dollars

#: A group's buffer share of its own assets: 0 to 30% in steps of 1%.
SHARE_GRID: Tuple[float, ...] = tuple(round(0.01 * i, 2) for i in range(31))
#: The curve's kink in the units of aggregate deployable liquidity (a share of bank assets): 0.05 to 8 points, steps of 0.05.
KINK_GRID: Tuple[float, ...] = tuple(round(0.0005 * i, 4) for i in range(1, 161))
#: The fixed starts of the coordinate search over the shares.
START_SHARES: Tuple[Tuple[float, ...], ...] = ((0.05,) * 3, (0.10,) * 3, (0.20,) * 3)
MAX_PASSES = 20
ALTERNATIVES = ("as_observed", "all_large_domestic", "proportional_to_assets")


class GroupWeek(NamedTuple):
    """One H.8 week: the three groups' reserves (an approximation) and total assets, in USD billions, and when it is public."""

    week_ending: date
    public_at: datetime
    reserves_bn: Tuple[float, ...]
    assets_bn: Tuple[float, ...]
    break_week: bool


class DayC(NamedTuple):
    """One scored day: the all-banks ratio and state public at its decision instant, the corridor position of its own SOFR,
    and the latest group week public at that instant."""

    day: date
    instant: datetime
    ratio: Optional[float]
    corridor: Optional[float]
    state: Optional[float]
    week: Optional[GroupWeek]


class FitC(NamedTuple):
    shares: Tuple[float, ...]
    kink: float
    intercept: float
    slope: float
    sse: float
    starts_agree: bool


class RefitC(NamedTuple):
    cutoff: date
    shares: Optional[Tuple[float, ...]]
    fitted: bool
    kink: Optional[float]
    intercept: Optional[float]
    slope: Optional[float]
    sse: Optional[float]
    pairs: int
    episodes: Tuple[str, ...]
    starts_agree: Optional[bool]
    break_weeks: Tuple[date, ...]
    draws: Tuple[Tuple[float, ...], ...]
    record: Dict[str, object]


class PathC(NamedTuple):
    """One refit's real-time path, as step 1's `RefitPath`, and the served days that read an H.8 break week."""

    refit: RefitC
    estimates: List[h7.Estimate]
    gaps: Dict[date, float]
    missing_days: int
    break_days: Tuple[date, ...]


# -- the estimand -----------------------------------------------------------------------------------------------------


def _check_shares(shares: Sequence[float]) -> None:
    if len(shares) != len(GROUPS) or any(not 0.0 <= s < 1.0 for s in shares):
        raise ValueError(f"the buffer shares must be {len(GROUPS)} numbers in [0, 1), not {tuple(shares)}")


def group_contributions(week: GroupWeek, shares: Sequence[float]) -> Tuple[float, ...]:
    """Each group's reserves above its own buffer (never negative), as a share of the groups' total assets."""
    _check_shares(shares)
    total = sum(week.assets_bn)
    return tuple(max(r - s * a, 0.0) / total for r, s, a in zip(week.reserves_bn, shares, week.assets_bn))


def deployable(week: GroupWeek, shares: Sequence[float]) -> float:
    """Aggregate deployable liquidity: the groups' reserves above their buffers, over their total assets."""
    return sum(group_contributions(week, shares))


def distribution(week: GroupWeek, shares: Sequence[float]) -> Dict[str, Dict[str, object]]:
    """The protocol's three declared alternatives for how the same reserves spread across the groups (section 8): as
    observed, all held by the large domestic banks, and in proportion to group assets. Each holds the week's total reserves
    of the three groups; each gives the aggregate and the group-by-group terms."""
    total = sum(week.reserves_bn)
    assets = sum(week.assets_bn)
    spread = {
        "as_observed": tuple(week.reserves_bn),
        "all_large_domestic": (total,) + (0.0,) * (len(GROUPS) - 1),
        "proportional_to_assets": tuple(total * a / assets for a in week.assets_bn),
    }
    out: Dict[str, Dict[str, object]] = {}
    for name in ALTERNATIVES:
        moved = week._replace(reserves_bn=spread[name])
        groups = group_contributions(moved, shares)
        out[name] = {"aggregate": sum(groups), "groups": groups, "reserves_bn": sum(spread[name])}
    return out


# -- the as-of read ---------------------------------------------------------------------------------------------------


def read_week(weeks: Sequence[GroupWeek], instant: datetime) -> Optional[GroupWeek]:
    """The latest week public at `instant`, or None when none is."""
    public = [w for w in weeks if w.public_at <= instant]
    return max(public, key=lambda w: w.week_ending) if public else None


def sample_c(rows: Sequence[DailyObservation], rule: InformationRule, weeks: Sequence[GroupWeek], *,
             on_rrp_rate: Optional[Callable[[date], Optional[float]]] = None) -> List[DayC]:
    """The scored days with the group week public at each one's decision instant.

    The ratio and the scarcity state are step 1's (`h7_estimator.asof_days`, through `rule`); the corridor position is
    Stage 2's, with the ON RRP rate in force that day (a realized outcome, never an input).

    Raises:
        LookAheadError: a scored day is in a locked tier, the rule refuses a read, or a week is read before it was public.
        StaleReadError: a read is older than the latest value public at the decision instant.
    """
    if on_rrp_rate is None:
        publications = scheduled.load_on_rrp_rates()
        on_rrp_rate = lambda day: scheduled.rate_in_force(publications, day)  # noqa: E731
    days = h7.asof_days(rows, rule)
    dates = [row.date for row in rows]
    out: List[DayC] = []
    for index, day in enumerate(days):
        scored = rows[index + 1]
        instant = rule.decision_instant(dates, index + 1)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=h8.NEW_YORK)  # the rule's decision time is New York local time
        sofr, iorb, floor = scored.values.get("sofr"), scored.values.get("iorb"), on_rrp_rate(scored.date)
        corridor = None if sofr is None or iorb is None or floor is None else demand_curve.corridor_position(
            sofr=float(sofr), iorb=float(iorb), on_rrp_rate=floor)
        out.append(DayC(day.day, instant, day.ratio, corridor, day.state, read_week(weeks, instant)))
    check_reads(out, weeks)
    return out


def check_reads(days: Sequence[DayC], weeks: Sequence[GroupWeek]) -> None:
    """Every group week a day read was public at its decision instant and was the latest public one.

    Raises:
        LookAheadError: a day read a week that was public only after its decision instant.
        StaleReadError: a day read a week when a later week was public at its instant.
    """
    for d in days:
        latest = read_week(weeks, d.instant)
        if d.week is not None and d.week.public_at > d.instant:
            raise LookAheadError(f"{d.day} read the week ending {d.week.week_ending}, public at {d.week.public_at}, after "
                                 f"its decision instant {d.instant}")
        if latest is not None and (d.week is None or d.week.week_ending < latest.week_ending):
            have = None if d.week is None else d.week.week_ending
            raise StaleReadError(f"{d.day} read the week ending {have}, but the week ending {latest.week_ending} was "
                                 f"public at {d.instant}")


# -- one refit --------------------------------------------------------------------------------------------------------


def training_days(days: Sequence[DayC], cutoff: date, *, episodes=demand_curve.EPISODES,
                  min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> Tuple[List[DayC], Tuple[str, ...]]:
    """The days a refit at `cutoff` fits on: every day, up to the cutoff, of each counted episode, that has a group week and
    a corridor position. An episode counts with at least `min_scarce` such days whose ratio is below 13%."""
    usable = [d for d in days if d.day <= cutoff and d.week is not None and d.corridor is not None]
    chosen: List[DayC] = []
    labels: List[str] = []
    for label, first, last in episodes:
        inside = [d for d in usable if first <= d.day <= last]
        if sum(1 for d in inside if d.ratio is not None and d.ratio < demand_curve.SCARCE_BELOW) >= min_scarce:
            chosen.extend(inside)
            labels.append(label)
    return sorted(chosen, key=lambda d: d.day), tuple(labels)


def _evaluate(shares, reserves, assets, ys) -> Optional[demand_curve.Fit]:
    totals = [sum(a) for a in assets]
    xs = [sum(max(r - s * a, 0.0) for r, s, a in zip(res, shares, ass)) / total
          for res, ass, total in zip(reserves, assets, totals)]
    try:
        fit = demand_curve.fit_broken_stick(xs, ys, KINK_GRID)
    except ValueError:
        return None
    return fit if fit.slope >= 0.0 else None


def _descend(start, reserves, assets, ys) -> Optional[Tuple[Tuple[float, ...], demand_curve.Fit]]:
    current = tuple(start)
    best = _evaluate(current, reserves, assets, ys)
    for _ in range(MAX_PASSES):
        improved = False
        for g in range(len(GROUPS)):
            for value in SHARE_GRID:
                candidate = current[:g] + (value,) + current[g + 1:]
                fit = _evaluate(candidate, reserves, assets, ys)
                if fit is not None and (best is None or fit.sse < best.sse - 1e-12):
                    current, best, improved = candidate, fit, True
        if not improved:
            break
    return None if best is None else (current, best)


def fit_shares(sample: Sequence[DayC], starts: Sequence[Sequence[float]] = START_SHARES) -> Optional[FitC]:
    """The three shares that best explain the corridor position through the broken stick, over `sample`.

    A coordinate search over `SHARE_GRID` from each start, least squares, ties to the smaller share. None when no start gives
    a fit with a non-negative slope. `starts_agree` says whether every start ended at the same shares.
    """
    reserves = [d.week.reserves_bn for d in sample]
    assets = [d.week.assets_bn for d in sample]
    ys = [d.corridor for d in sample]
    results = [r for r in (_descend(start, reserves, assets, ys) for start in starts) if r is not None]
    if not results:
        return None
    shares, fit = min(results, key=lambda r: (round(r[1].sse, 12), r[0]))
    return FitC(shares, fit.kink, fit.intercept, fit.slope, fit.sse, all(r[0] == shares for r in results))


def fit_refit(sample: Sequence[DayC], cutoff: date, *, labels: Tuple[str, ...] = (), replications: int,
              seed: int = SEED) -> RefitC:
    """The refit at `cutoff` fitted on `sample` alone, with the bootstrap draws of its shares.

    `replications` of 0 skips the draws. A sample that cannot fit is `fitted` False, with no draws.

    Raises:
        LookAheadError: if a day of `sample` is after `cutoff`.
    """
    for d in sample:
        if d.day > cutoff:
            raise LookAheadError(f"the shares for the refit at {cutoff} would be fitted on {d.day}, after its cutoff")
    breaks = tuple(sorted({d.week.week_ending for d in sample if d.week.break_week}))
    fit = fit_shares(sample) if sample else None
    if fit is None:
        return RefitC(cutoff, None, False, None, None, None, None, len(sample), labels, None, breaks, (), {"fitted": False})
    draws: List[Tuple[float, ...]] = []
    rng = random.Random(seed)
    for _ in range(replications):
        index = stationary_bootstrap_indices(len(sample), BLOCK_LENGTH, rng)
        again = fit_shares([sample[j] for j in index], starts=(fit.shares,))
        if again is not None:
            draws.append(again.shares)
    record = {"fitted": True, "kink": fit.kink, "intercept": fit.intercept, "slope": fit.slope, "sse": fit.sse,
              "starts_agree": fit.starts_agree, "replications": replications, "draws": len(draws)}
    return RefitC(cutoff, fit.shares, True, fit.kink, fit.intercept, fit.slope, fit.sse, len(sample), labels,
                  fit.starts_agree, breaks, tuple(draws), record)


def refit_c(days: Sequence[DayC], cutoff: date, *, replications: int, seed: int = SEED, episodes=demand_curve.EPISODES,
            min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> RefitC:
    """`fit_refit` on the days `training_days` gives for `cutoff`."""
    sample, labels = training_days(days, cutoff, episodes=episodes, min_scarce=min_scarce)
    return fit_refit(sample, cutoff, labels=labels, replications=replications, seed=seed)


def interval(refit: RefitC, week: GroupWeek) -> Optional[Tuple[float, float]]:
    """The 90% interval of a week's aggregate over the refit's bootstrap draws, widened to hold the point estimate."""
    if not refit.fitted or not refit.draws:
        return None
    point = deployable(week, refit.shares)
    values = sorted(deployable(week, shares) for shares in refit.draws)
    tail = (1.0 - LEVEL) / 2.0
    return min(satiation.quantile(values, tail), point), max(satiation.quantile(values, 1.0 - tail), point)


# -- the real-time path -----------------------------------------------------------------------------------------------


def real_time_path(days: Sequence[DayC], cutoffs: Sequence[date], *, replications: int, seed: int = SEED,
                   episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[PathC]:
    """Each refit's real-time path over the days it serves. Computed, not scored.

    As step 1's: refit `k` serves from the second business day after its cutoff to the day before refit `k + 1` serves from;
    on every day refit `k > 0` serves, `gaps` holds the absolute difference between its estimate and refit `k - 1`'s, when both
    fitted. A refit that did not fit serves no estimate; its days are in `missing_days`. `break_days` lists the served days
    that read an H.8 break week.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [next_business_day(cut, SERVING_LAG) for cut in cutoffs]
    refits = [refit_c(days, cut, replications=replications, seed=seed, episodes=episodes, min_scarce=min_scarce)
              for cut in cutoffs]
    out: List[PathC] = []
    for k, fit in enumerate(refits):
        end = starts[k + 1] if k + 1 < len(starts) else None
        served = [d for d in days if d.day >= starts[k] and (end is None or d.day < end)]
        estimates: List[h7.Estimate] = []
        gaps: Dict[date, float] = {}
        breaks: List[date] = []
        missing = 0
        for d in served:
            if not fit.fitted or d.week is None or d.ratio is None:
                missing += 1
                continue
            value = deployable(d.week, fit.shares)
            span = interval(fit, d.week)
            estimates.append(h7.Estimate(d.day, d.ratio, value, None if span is None else span[0],
                                         None if span is None else span[1], d.state))
            if d.week.break_week:
                breaks.append(d.day)
            if k > 0 and refits[k - 1].fitted:
                gaps[d.day] = abs(value - deployable(d.week, refits[k - 1].shares))
        out.append(PathC(fit, estimates, gaps, missing, tuple(breaks)))
    return out


# -- the leakage check ------------------------------------------------------------------------------------------------


def check_no_future(rows: Sequence[DailyObservation], rule: InformationRule, weeks: Sequence[GroupWeek],
                    path: Sequence[PathC], *, on_rrp_rate: Optional[Callable[[date], Optional[float]]] = None,
                    replications: int, seed: int = SEED, episodes=demand_curve.EPISODES,
                    min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> None:
    """Refuse a refit that is not what the panel cut at its own cutoff gives.

    Each refit is rebuilt from `rows` up to and including its cutoff row, through the rule and the group weeks, and compared.

    Raises:
        LookAheadError: a refit's shares, or whether it fitted, differ from the cut panel's, so it depended on a later row.
    """
    for p in path:
        cutoff = p.refit.cutoff
        cut = [row for row in rows if row.date <= cutoff]
        again = refit_c(sample_c(cut, rule, weeks, on_rrp_rate=on_rrp_rate), cutoff, replications=replications, seed=seed,
                        episodes=episodes, min_scarce=min_scarce)
        if again.fitted != p.refit.fitted or again.shares != p.refit.shares:
            raise LookAheadError(
                f"the refit at {cutoff} has shares {p.refit.shares}, but the panel cut at that row gives {again.shares}; "
                "the refit depended on a later row"
            )


# -- the tracked series -----------------------------------------------------------------------------------------------


def tracked_weeks() -> List[GroupWeek]:
    """#43's tracked weekly group-reserves series with the H.8 first-print total assets of each week.

    The extract is checked against its manifest on load and re-verified against its inputs (`group_reserves.verify`).

    Raises:
        LookAheadError: a week is public in a locked tier of the parent's lockbox.
        ValueError: the extract does not match its inputs.
    """
    rows = group_reserves.load_extract(group_reserves.DIRECTORY / group_reserves.EXTRACT_NAME)
    inputs = group_reserves.tracked_inputs()
    group_reserves.verify(rows, inputs["prints"], inputs["reserves"])
    totals = {p.week_ending: tuple(p.values[f"h8_{g}_total_assets"] for g in GROUPS) for p in inputs["prints"]}
    out = [GroupWeek(r.week_ending, r.public_at, (r.large_domestic_bn, r.small_domestic_bn, r.foreign_related_bn),
                     totals[r.week_ending], r.h8_break_week) for r in sorted(rows, key=lambda r: r.week_ending)]
    for w in out:
        if development.is_locked(w.public_at.date()):
            raise LookAheadError(f"the week ending {w.week_ending} is public on {w.public_at.date()}, in a locked tier")
    return out
