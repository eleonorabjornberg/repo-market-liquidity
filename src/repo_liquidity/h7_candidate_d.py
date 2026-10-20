"""H7m, development step 3: candidate D, the SLR-bound group's buffer set by leverage headroom (`docs/stages/h7-step3.md`).

Aggregate deployable liquidity on day T is candidate C's (`h7_candidate_c`): the sum over the three H.8 groups of max(group
reserves - buffer x group assets, 0), over the groups' total assets. D changes one buffer. The large domestic group's share is
`clip(level + slope x h, 0, 0.30)` with `h` the nine G-SIB depository subsidiaries' leverage headroom in dollars (Tier 1 capital
over the required ratio, less total leverage exposure; USD billions, summed) over the group's total assets of the week the day
reads. The small domestic and foreign-related shares are fixed within a refit, as in C. A quarter with no requirement has no
headroom and D serves no estimate on days that read it; there is no fallback.

The four parameters are fitted so that the aggregate, through Stage 2's broken stick (`demand_curve.fit_broken_stick`), best
explains the corridor position in the counted scarce episodes, on training rows only, as C's shares are: a refit with cutoff `c`
fits on days scored on or before `c` that have a group week, a corridor position and a headroom, and serves from the second
business day after it. Its interval is a stationary bootstrap of the parameters.

A day reads the latest complete quarter of the nine banks public at its decision instant (every bank has a row with
`available_from` on or before it). The SLR snapshot is the latest-filed vintage (data-meaning row 16(d), ruling of 13 October
2026), so the early quarters become public long after they ended. An H.8 break week and a quarter whose 2020-21 exclusion status is
unknown are flagged, never refused and never adjusted.

Reads nothing but through the parent's as-of rule, the group series' and the SLR rows' own availability times; rebuilds none of the
parent's guards. Nothing is scored here: `real_time_path` returns each refit's path and its gap to the previous refit for step 5,
and `out_of_sample_2025` is Stage 6's own test as machinery, run on constructed data only.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import date, datetime
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from repo_model import satiation
from repo_model.asof import InformationRule, StaleReadError
from repo_model.data import DailyObservation, next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError

from repo_liquidity import demand_curve, h7_candidate_c as c, h7_estimator as h7, slr, snapshots

GROUPS = c.GROUPS
SERVING_LAG = h7.SERVING_LAG
BLOCK_LENGTH, LEVEL, SEED = h7.BLOCK_LENGTH, h7.LEVEL, h7.SEED
points, dollars = h7.points, h7.dollars

#: The SLR-bound group is the large domestic group (index 0 of `GROUPS`).
SLR_GROUP = 0
#: The large group's buffer share is kept inside zero and the top of the share grid.
MAX_BUFFER = 0.30
#: The level of the large group's buffer: 0 to 30% in steps of 1%. The slope: -1.0 to 1.0 in steps of 0.1.
LEVEL_GRID: Tuple[float, ...] = c.SHARE_GRID
SLOPE_GRID: Tuple[float, ...] = tuple(round(-1.0 + 0.1 * i, 1) for i in range(21))
KINK_GRID = c.KINK_GRID
#: The fixed starts of the coordinate search: (level, slope, small share, foreign-related share).
START_PARAMETERS: Tuple[Tuple[float, ...], ...] = ((0.05, 0.0, 0.05, 0.05), (0.10, -0.5, 0.10, 0.10), (0.20, 0.5, 0.20, 0.20))
MAX_PASSES = 20
ALTERNATIVES = c.ALTERNATIVES
#: The published `slr_headroom` snapshot D reads (PR #128; it supersedes 013b647e...).
SNAPSHOT_SHA256 = "4e9f87b518b3106ec5dc7d709f19e7f365e499c969fa5cb7ba9201e66f37e817"
STAGE2_RECORD = snapshots.ROOT / "results" / "stage2" / "demand_curve.json"
_USD_THOUSANDS_PER_BILLION = 1_000_000.0


class Params(NamedTuple):
    """The large group's buffer level and slope, and the small domestic and foreign-related buffer shares."""

    level: float
    slope: float
    small: float
    foreign: float


class HeadroomRead(NamedTuple):
    """The latest complete quarter of the nine banks public at an instant: its total headroom in USD billions (None when the
    quarter has no requirement), when the last of the nine became public, and whether its 2020-21 exclusion status is unknown."""

    quarter_end: date
    public_at: datetime
    headroom_bn: Optional[float]
    exclusion_unknown: bool


class DayD(NamedTuple):
    """One scored day: candidate C's day with the headroom read public at its decision instant."""

    day: date
    instant: datetime
    ratio: Optional[float]
    corridor: Optional[float]
    state: Optional[float]
    week: Optional[c.GroupWeek]
    headroom: Optional[HeadroomRead]


class FitD(NamedTuple):
    params: Params
    kink: float
    intercept: float
    slope: float
    sse: float
    starts_agree: bool


class RefitD(NamedTuple):
    cutoff: date
    params: Optional[Params]
    fitted: bool
    kink: Optional[float]
    intercept: Optional[float]
    slope: Optional[float]
    sse: Optional[float]
    pairs: int
    episodes: Tuple[str, ...]
    starts_agree: Optional[bool]
    break_weeks: Tuple[date, ...]
    draws: Tuple[Params, ...]
    record: Dict[str, object]


class PathD(NamedTuple):
    """One refit's real-time path as candidate C's, with the served days that read an unknown-exclusion quarter."""

    refit: RefitD
    estimates: List[h7.Estimate]
    gaps: Dict[date, float]
    missing_days: int
    break_days: Tuple[date, ...]
    exclusion_days: Tuple[date, ...]


class OutOfSample(NamedTuple):
    """Stage 6's own test for D: fitted on the first episode alone, does it predict the second episode's bend inside the
    interval? `inside` is None when nothing was predicted."""

    fitted: bool
    params: Optional[Params]
    kink: Optional[float]
    predicted_bend: Optional[float]
    inside: Optional[bool]
    interval: Tuple[float, float]
    days: int


# -- the headroom -----------------------------------------------------------------------------------------------------


def bank_headroom_bn(row: slr.Row) -> Optional[float]:
    """One bank's leverage headroom in USD billions: Tier 1 capital over the required ratio, less total leverage exposure.
    None when the quarter has no requirement."""
    requirement = row.requirement_pct
    if requirement is None:
        return None
    return (row.tier1_capital_kusd / (requirement / 100.0) - row.total_leverage_exposure_kusd) / _USD_THOUSANDS_PER_BILLION


def transform(week: c.GroupWeek, headroom_bn: float) -> float:
    """The headroom transform: dollars of headroom per dollar of the large domestic group's total assets that week."""
    return headroom_bn / week.assets_bn[SLR_GROUP]


def read_headroom(rows: Sequence[slr.Row], instant: datetime) -> Optional[HeadroomRead]:
    """The latest quarter for which all nine banks have a row public at `instant`, or None when there is none.

    Raises:
        ValueError: if `instant` has no time zone.
    """
    if instant.tzinfo is None:
        raise ValueError("the decision instant must be timezone-aware")
    by_quarter: Dict[date, Dict[int, slr.Row]] = {}
    for row in rows:
        by_quarter.setdefault(row.quarter_end, {})[row.idrssd] = row
    complete = [q for q, banks in by_quarter.items()
                if set(banks) >= set(slr.BANKS) and all(banks[b].available_from <= instant for b in slr.BANKS)]
    if not complete:
        return None
    quarter = max(complete)
    banks = [by_quarter[quarter][b] for b in slr.BANKS]
    each = [bank_headroom_bn(row) for row in banks]
    total = None if any(v is None for v in each) else sum(each)
    return HeadroomRead(quarter, max(row.available_from for row in banks), total,
                        any(row.exclusion_status == "unknown" for row in banks))


# -- the estimand -----------------------------------------------------------------------------------------------------


def _check_params(params: Params) -> None:
    if not 0.0 <= params.level <= MAX_BUFFER:
        raise ValueError(f"the level must be in [0, {MAX_BUFFER}], not {params.level}")
    if not SLOPE_GRID[0] <= params.slope <= SLOPE_GRID[-1]:
        raise ValueError(f"the slope must be in [{SLOPE_GRID[0]}, {SLOPE_GRID[-1]}], not {params.slope}")
    if not all(0.0 <= s <= MAX_BUFFER for s in (params.small, params.foreign)):
        raise ValueError(f"the small and foreign-related shares must be in [0, {MAX_BUFFER}], not {params[2:]}")


def shares_at(params: Params, week: c.GroupWeek, headroom_bn: Optional[float]) -> Tuple[float, ...]:
    """The three groups' buffer shares for a week and a total headroom. The large group's is `level + slope x h`, kept inside
    zero and `MAX_BUFFER`.

    Raises:
        ValueError: if there is no headroom, or a parameter is outside its range.
    """
    _check_params(params)
    if headroom_bn is None:
        raise ValueError("there is no headroom for this quarter: D serves no estimate")
    large = min(max(params.level + params.slope * transform(week, headroom_bn), 0.0), MAX_BUFFER)
    return (large, params.small, params.foreign)


def group_contributions(week: c.GroupWeek, headroom_bn: Optional[float], params: Params) -> Tuple[float, ...]:
    """Each group's reserves above its own buffer (never negative), as a share of the groups' total assets."""
    return c.group_contributions(week, shares_at(params, week, headroom_bn))


def deployable(week: c.GroupWeek, headroom_bn: Optional[float], params: Params) -> float:
    """Aggregate deployable liquidity: the groups' reserves above their buffers, over their total assets."""
    return sum(group_contributions(week, headroom_bn, params))


def distribution(week: c.GroupWeek, headroom_bn: Optional[float], params: Params) -> Dict[str, Dict[str, object]]:
    """The protocol's three declared alternatives (section 8) for D, with D's own buffers on the day: as observed, all reserves
    held by the large domestic banks, and in proportion to group assets. Each gives the aggregate and the group-by-group terms."""
    return c.distribution(week, shares_at(params, week, headroom_bn))


# -- the as-of read ---------------------------------------------------------------------------------------------------


def sample_d(rows: Sequence[DailyObservation], rule: InformationRule, weeks: Sequence[c.GroupWeek],
             slr_rows: Sequence[slr.Row], *, on_rrp_rate: Optional[Callable[[date], Optional[float]]] = None) -> List[DayD]:
    """The scored days with the group week and the headroom public at each one's decision instant.

    Candidate C's days (`h7_candidate_c.sample_c`: the ratio, state and corridor position through `rule`), each with the latest
    complete quarter of the nine banks public at its instant.

    Raises:
        LookAheadError: a scored day is in a locked tier, the rule refuses a read, or an input is read before it was public.
        StaleReadError: a read is older than the latest value public at the decision instant.
    """
    out = [DayD(x.day, x.instant, x.ratio, x.corridor, x.state, x.week, read_headroom(slr_rows, x.instant))
           for x in c.sample_c(rows, rule, weeks, on_rrp_rate=on_rrp_rate)]
    check_reads(out, weeks, slr_rows)
    return out


def check_reads(days: Sequence[DayD], weeks: Sequence[c.GroupWeek], slr_rows: Sequence[slr.Row]) -> None:
    """Every week and headroom a day read was public at its decision instant and was the latest public one.

    Raises:
        LookAheadError: a day read a week or a quarter that was public only after its decision instant.
        StaleReadError: a day read a week or a quarter when a later one was public at its instant.
    """
    c.check_reads([c.DayC(x.day, x.instant, x.ratio, x.corridor, x.state, x.week) for x in days], weeks)
    for x in days:
        latest = read_headroom(slr_rows, x.instant)
        if x.headroom is not None and x.headroom.public_at > x.instant:
            raise LookAheadError(f"{x.day} read the quarter ended {x.headroom.quarter_end}, public at {x.headroom.public_at}, "
                                 f"after its decision instant {x.instant}")
        if latest is not None and (x.headroom is None or x.headroom.quarter_end < latest.quarter_end):
            have = None if x.headroom is None else x.headroom.quarter_end
            raise StaleReadError(f"{x.day} read the quarter ended {have}, but the quarter ended {latest.quarter_end} was "
                                 f"public at {x.instant}")


# -- one refit --------------------------------------------------------------------------------------------------------


def _usable(x: DayD) -> bool:
    return x.week is not None and x.corridor is not None and x.headroom is not None and x.headroom.headroom_bn is not None


def training_days(days: Sequence[DayD], cutoff: date, *, episodes=demand_curve.EPISODES,
                  min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> Tuple[List[DayD], Tuple[str, ...]]:
    """The days a refit at `cutoff` fits on: every day, up to the cutoff, of each counted episode, that has a group week, a
    corridor position and a headroom. An episode counts with at least `min_scarce` such days whose ratio is below 13%."""
    usable = [x for x in days if x.day <= cutoff and _usable(x)]
    chosen: List[DayD] = []
    labels: List[str] = []
    for label, first, last in episodes:
        inside = [x for x in usable if first <= x.day <= last]
        if sum(1 for x in inside if x.ratio is not None and x.ratio < demand_curve.SCARCE_BELOW) >= min_scarce:
            chosen.extend(inside)
            labels.append(label)
    return sorted(chosen, key=lambda x: x.day), tuple(labels)


def _evaluate(params, reserves, assets, heads, ys) -> Optional[demand_curve.Fit]:
    level, slope, small, foreign = params
    xs = []
    for res, ass, head in zip(reserves, assets, heads):
        large = min(max(level + slope * head / ass[SLR_GROUP], 0.0), MAX_BUFFER)
        total = sum(ass)
        xs.append((max(res[0] - large * ass[0], 0.0) + max(res[1] - small * ass[1], 0.0)
                   + max(res[2] - foreign * ass[2], 0.0)) / total)
    try:
        fit = demand_curve.fit_broken_stick(xs, ys, KINK_GRID)
    except ValueError:
        return None
    return fit if fit.slope >= 0.0 else None


def _descend(start, reserves, assets, heads, ys) -> Optional[Tuple[Params, demand_curve.Fit]]:
    grids = (LEVEL_GRID, SLOPE_GRID, c.SHARE_GRID, c.SHARE_GRID)
    current = tuple(start)
    best = _evaluate(current, reserves, assets, heads, ys)
    for _ in range(MAX_PASSES):
        improved = False
        for g, grid in enumerate(grids):
            for value in grid:
                candidate = current[:g] + (value,) + current[g + 1:]
                fit = _evaluate(candidate, reserves, assets, heads, ys)
                if fit is not None and (best is None or fit.sse < best.sse - 1e-12):
                    current, best, improved = candidate, fit, True
        if not improved:
            break
    return None if best is None else (Params(*current), best)


def fit_parameters(sample: Sequence[DayD], starts: Sequence[Sequence[float]] = START_PARAMETERS) -> Optional[FitD]:
    """The four parameters that best explain the corridor position through the broken stick, over `sample`.

    A coordinate search over the grids from each start, least squares, ties to the lower value. None when no start gives a fit
    with a non-negative slope. `starts_agree` says whether every start ended at the same parameters.
    """
    reserves = [x.week.reserves_bn for x in sample]
    assets = [x.week.assets_bn for x in sample]
    heads = [x.headroom.headroom_bn for x in sample]
    ys = [x.corridor for x in sample]
    results = [r for r in (_descend(start, reserves, assets, heads, ys) for start in starts) if r is not None]
    if not results:
        return None
    params, fit = min(results, key=lambda r: (round(r[1].sse, 12), tuple(r[0])))
    return FitD(params, fit.kink, fit.intercept, fit.slope, fit.sse, all(r[0] == params for r in results))


def fit_refit(sample: Sequence[DayD], cutoff: date, *, labels: Tuple[str, ...] = (), replications: int,
              seed: int = SEED) -> RefitD:
    """The refit at `cutoff` fitted on `sample` alone, with the bootstrap draws of its parameters.

    `replications` of 0 skips the draws. A sample that cannot fit is `fitted` False, with no draws.

    Raises:
        LookAheadError: if a day of `sample` is after `cutoff`.
    """
    for x in sample:
        if x.day > cutoff:
            raise LookAheadError(f"the parameters for the refit at {cutoff} would be fitted on {x.day}, after its cutoff")
    breaks = tuple(sorted({x.week.week_ending for x in sample if x.week.break_week}))
    fit = fit_parameters(sample) if sample else None
    if fit is None:
        return RefitD(cutoff, None, False, None, None, None, None, len(sample), labels, None, breaks, (), {"fitted": False})
    draws: List[Params] = []
    rng = random.Random(seed)
    for _ in range(replications):
        index = stationary_bootstrap_indices(len(sample), BLOCK_LENGTH, rng)
        again = fit_parameters([sample[j] for j in index], starts=(tuple(fit.params),))
        if again is not None:
            draws.append(again.params)
    record = {"fitted": True, "kink": fit.kink, "intercept": fit.intercept, "slope": fit.slope, "sse": fit.sse,
              "starts_agree": fit.starts_agree, "replications": replications, "draws": len(draws),
              "headroom_slope_sign": "negative" if fit.params.slope < 0 else "positive" if fit.params.slope > 0 else "zero"}
    return RefitD(cutoff, fit.params, True, fit.kink, fit.intercept, fit.slope, fit.sse, len(sample), labels,
                  fit.starts_agree, breaks, tuple(draws), record)


def refit_d(days: Sequence[DayD], cutoff: date, *, replications: int, seed: int = SEED, episodes=demand_curve.EPISODES,
            min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> RefitD:
    """`fit_refit` on the days `training_days` gives for `cutoff`."""
    sample, labels = training_days(days, cutoff, episodes=episodes, min_scarce=min_scarce)
    return fit_refit(sample, cutoff, labels=labels, replications=replications, seed=seed)


def interval(refit: RefitD, week: c.GroupWeek, headroom_bn: float) -> Optional[Tuple[float, float]]:
    """The 90% interval of a day's aggregate over the refit's bootstrap draws, widened to hold the point estimate."""
    if not refit.fitted or not refit.draws:
        return None
    point = deployable(week, headroom_bn, refit.params)
    values = sorted(deployable(week, headroom_bn, params) for params in refit.draws)
    tail = (1.0 - LEVEL) / 2.0
    return min(satiation.quantile(values, tail), point), max(satiation.quantile(values, 1.0 - tail), point)


# -- the real-time path -----------------------------------------------------------------------------------------------


def real_time_path(days: Sequence[DayD], cutoffs: Sequence[date], *, replications: int, seed: int = SEED,
                   episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[PathD]:
    """Each refit's real-time path over the days it serves. Computed, not scored.

    As candidate C's: refit `k` serves from the second business day after its cutoff to the day before refit `k + 1` serves
    from; on every day refit `k > 0` serves, `gaps` holds the absolute difference between its estimate and refit `k - 1`'s, when
    both fitted. A refit that did not fit, or a served day with no week or no headroom, is in `missing_days`. `break_days` lists
    the served days that read an H.8 break week, `exclusion_days` those that read a quarter of unknown 2020-21 exclusion status.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [next_business_day(cut, SERVING_LAG) for cut in cutoffs]
    refits = [refit_d(days, cut, replications=replications, seed=seed, episodes=episodes, min_scarce=min_scarce)
              for cut in cutoffs]
    out: List[PathD] = []
    for k, fit in enumerate(refits):
        end = starts[k + 1] if k + 1 < len(starts) else None
        served = [x for x in days if x.day >= starts[k] and (end is None or x.day < end)]
        estimates: List[h7.Estimate] = []
        gaps: Dict[date, float] = {}
        breaks: List[date] = []
        excluded: List[date] = []
        missing = 0
        for x in served:
            if not fit.fitted or x.week is None or x.ratio is None or x.headroom is None or x.headroom.headroom_bn is None:
                missing += 1
                continue
            head = x.headroom.headroom_bn
            value = deployable(x.week, head, fit.params)
            span = interval(fit, x.week, head)
            estimates.append(h7.Estimate(x.day, x.ratio, value, None if span is None else span[0],
                                         None if span is None else span[1], x.state))
            if x.week.break_week:
                breaks.append(x.day)
            if x.headroom.exclusion_unknown:
                excluded.append(x.day)
            if k > 0 and refits[k - 1].fitted:
                gaps[x.day] = abs(value - deployable(x.week, head, refits[k - 1].params))
        out.append(PathD(fit, estimates, gaps, missing, tuple(breaks), tuple(excluded)))
    return out


# -- Stage 6's own test -----------------------------------------------------------------------------------------------


def stage2_bend_interval() -> Tuple[float, float]:
    """Stage 2's 90% interval for the 2025 bend, in units of the all-banks ratio, from its tracked record."""
    record = json.loads(STAGE2_RECORD.read_text(encoding="utf-8"))
    low, high = record["revised_test"]["episodes"]["2025"]["kink_interval_90"]
    return float(low), float(high)


def out_of_sample_2025(days: Sequence[DayD], *, interval: Optional[Tuple[float, float]] = None, replications: int = 0,
                       seed: int = SEED, episodes=demand_curve.EPISODES,
                       min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> OutOfSample:
    """Stage 6's own test for D: fitted on the first episode only, does it predict the second episode's bend inside Stage 2's
    90% interval for it (`stage2_bend_interval`, unless `interval` is given)?

    D is fitted with the first episode alone, at its last day. On the second episode's days that read a week and a headroom, D
    is regressed on the all-banks ratio by least squares (`D = a + b x ratio`); with `b > 0` the predicted bend is the ratio at
    which D equals the first episode's fitted kink, `(kink - a) / b`. Machinery only: step 5 runs it on real days.
    """
    span = stage2_bend_interval() if interval is None else (float(interval[0]), float(interval[1]))
    first, second = episodes[0], episodes[1]
    refit = refit_d(days, first[2], replications=replications, seed=seed, episodes=(first,), min_scarce=min_scarce)
    if not refit.fitted:
        return OutOfSample(False, None, None, None, None, span, 0)
    pairs = [(x.ratio, deployable(x.week, x.headroom.headroom_bn, refit.params)) for x in days
             if second[1] <= x.day <= second[2] and x.ratio is not None and x.week is not None
             and x.headroom is not None and x.headroom.headroom_bn is not None]
    n = len(pairs)
    predicted = None
    if n >= 2:
        mean_r, mean_d = sum(r for r, _ in pairs) / n, sum(v for _, v in pairs) / n
        var = sum((r - mean_r) ** 2 for r, _ in pairs)
        if var > 1e-12:
            b = sum((r - mean_r) * (v - mean_d) for r, v in pairs) / var
            if b > 0.0:
                predicted = (refit.kink - (mean_d - b * mean_r)) / b
    inside = None if predicted is None else span[0] <= predicted <= span[1]
    return OutOfSample(True, refit.params, refit.kink, predicted, inside, span, n)


# -- the leakage check ------------------------------------------------------------------------------------------------


def check_no_future(rows: Sequence[DailyObservation], rule: InformationRule, weeks: Sequence[c.GroupWeek],
                    slr_rows: Sequence[slr.Row], path: Sequence[PathD], *,
                    on_rrp_rate: Optional[Callable[[date], Optional[float]]] = None, replications: int, seed: int = SEED,
                    episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> None:
    """Refuse a refit that is not what the panel cut at its own cutoff gives.

    Each refit is rebuilt from `rows` up to and including its cutoff row, through the rule, the group weeks and the SLR rows,
    and compared.

    Raises:
        LookAheadError: a refit's parameters, or whether it fitted, differ from the cut panel's, so it depended on a later row.
    """
    for p in path:
        cutoff = p.refit.cutoff
        cut = [row for row in rows if row.date <= cutoff]
        again = refit_d(sample_d(cut, rule, weeks, slr_rows, on_rrp_rate=on_rrp_rate), cutoff, replications=replications,
                        seed=seed, episodes=episodes, min_scarce=min_scarce)
        if again.fitted != p.refit.fitted or again.params != p.refit.params:
            raise LookAheadError(
                f"the refit at {cutoff} has parameters {p.refit.params}, but the panel cut at that row gives {again.params}; "
                "the refit depended on a later row"
            )


# -- the tracked series -----------------------------------------------------------------------------------------------


def tracked_rows() -> List[slr.Row]:
    """The published `slr_headroom` snapshot's rows (the nine banks, latest-filed vintage), checked on load.

    The extract is read through `slr.load_extract` (its manifest, its derived columns, the lockbox), and its bytes must be the
    published snapshot's digest, `SNAPSHOT_SHA256`.

    Raises:
        LookAheadError: a row was last updated on a day the parent's lockbox holds.
        ValueError: the extract is not the published snapshot, or does not match its manifest.
    """
    path = snapshots.SLR_EXTRACT
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SNAPSHOT_SHA256:
        raise ValueError(f"{path.name} is {digest}, not the published snapshot {SNAPSHOT_SHA256}")
    return [row for row in slr.load_extract(path) if row.measure == slr.MAIN]


def tracked_weeks() -> List[c.GroupWeek]:
    """Candidate C's tracked weekly group series (D reads the group series through C's module, as its only reader)."""
    return c.tracked_weeks()
