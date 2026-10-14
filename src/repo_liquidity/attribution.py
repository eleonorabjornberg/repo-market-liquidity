"""H10 step 1: the episode-attribution method, declared and tested on synthetic episodes (`docs/decisions/h10-method.md`).

For each pressure episode the rise in SOFR - IORB is split into Treasury settlement, TGA, reserves, quarter-end and a
residual. The method is a regression of the spread change on the driver changes, fitted with the episode left out so that
no episode explains itself, with Shapley shares over the drivers and an interval from the stationary bootstrap.

**Nothing here is applied to a real episode.** Applying it is step 2, after the record is merged. The tests build
synthetic series with planted shares.

The episode list is the model repo's and is never redefined here: `episode_onsets` reads `repo_model.onset.onset_flags`,
and `cross_check_onsets` compares it with `repo_model.pressure.onsets` at +5 bp. The as-of rule is the parent's
(`repo_model.asof.InformationRule`); `check_window_public` only asks it, and raises `LookAheadError` when an input of an
episode's window was not public at the report instant. Standard library only.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from repo_model import lockbox
from repo_model.splits import LookAheadError

#: The drivers, in the order the record names them. Treasury settlement and TGA are flows through the Treasury's
#: account, reserves is the level the banks hold, and quarter-end is the calendar column. Each is a column of the
#: parent's panel (`repo_model.contract.FEATURE_FIELDS`).
DRIVERS: Tuple[str, ...] = ("treasury_settlement", "tga", "reserve_balances", "quarter_end")
#: PROPOSED (amendment of 14 October 2026, finding #52; hers to set): ON RRP take-up added as a fifth driver, entering as
#: the window change like the others. `DRIVERS` stays the decided set until she merges the amendment.
ON_RRP = "on_rrp"
DRIVERS_WITH_ON_RRP: Tuple[str, ...] = DRIVERS + (ON_RRP,)
#: The benchmark's single driver (the record, section 4).
RESERVES_ONLY: Tuple[str, ...] = ("reserve_balances",)
#: The target series name, `DailyObservation.spread_bps`.
SPREAD = "spread_bps"

#: The values `docs/decisions/h10-method.md` sets (Eleonora's ruling on #37, 13 October 2026); they become the method only
#: when she merges the record.
#: The baseline is the mean of the panel days before the onset (the onset group's own calm days,
#: `repo_model.onset.ONSET_CALM_DAYS`), the window the onset day and the days after it.
BASELINE_DAYS = 5
WINDOW_DAYS = 5
#: Placebo windows per episode (the record, section 4: 20, changed from the 5 first proposed).
PLACEBO_WINDOWS = 20
#: The stationary bootstrap, as in the measurement protocol (section 6) and the parent's scoring protocol.
BLOCK_LENGTH = 10.0
DRAWS = 10_000
SEED = 20261013
LEVEL = 0.90
#: "Drivers named": the residual share is under this in more than `MAJORITY` of the development episodes (the plan, H10).
RESIDUAL_BAR = 0.5
MAJORITY = 0.5
#: At most this share of bootstrap draws may be unusable (a singular design) before the interval is refused.
MAX_UNUSABLE_DRAWS = 0.05

#: PROPOSED (amendment of 14 October 2026): the selection-aware null. Surrogate spreads per null, and the quantile of the
#: null's explained shares an episode must exceed.
NULL_DRAWS = 1000
NULL_QUANTILE = 0.95

Series = Mapping[str, Sequence[Optional[float]]]


@dataclass(frozen=True)
class Attribution:
    """One episode's attribution. `status` is "attributed" or "not attributable" (never dropped)."""

    start: int
    status: str
    reason: Optional[str] = None
    rise_bp: Optional[float] = None
    shares: Optional[Mapping[str, float]] = None
    #: beta_j * dx_j / rise from the full model's coefficients, reported beside the Shapley shares (the record, section 2).
    fixed_shares: Optional[Mapping[str, float]] = None
    residual_share: Optional[float] = None
    explained_share: Optional[float] = None
    intervals: Optional[Mapping[str, Tuple[float, float]]] = None
    residual_interval: Optional[Tuple[float, float]] = None
    unusable_draws: int = 0

    @property
    def residual_under_bar(self) -> bool:
        """The outcome rule's test for one episode. A not-attributable episode never counts as under the bar."""
        return self.status == "attributed" and abs(self.residual_share) < RESIDUAL_BAR


# --------------------------------------------------------------------------- the episode source (the model repo's)


def series_from_rows(rows, drivers: Sequence[str] = DRIVERS) -> Dict[str, List[Optional[float]]]:
    """The spread and the drivers, as columns, from the parent's `DailyObservation` rows."""
    columns: Dict[str, List[Optional[float]]] = {SPREAD: [float(row.spread_bps) for row in rows]}
    for name in drivers:
        columns[name] = [None if row.values.get(name) is None else float(row.values[name]) for row in rows]
    return columns


def episode_onsets(rows) -> List[int]:
    """Row positions of the pressure onsets: `repo_model.onset.onset_flags`, the onset group's own module."""
    from repo_model.onset import onset_flags

    check_development(row.date for row in rows)
    return [index for index, flag in enumerate(onset_flags(rows)) if flag]


def cross_check_onsets(rows) -> List[int]:
    """`episode_onsets`, after checking it gives the onset days of `repo_model.pressure.onsets` at +5 bp.

    Raises:
        ValueError: the two sources disagree. Eleonora picks the source under the plan's Q6.
    """
    from repo_model.onset import ONSET_THRESHOLD_BP
    from repo_model.pressure import onsets

    found = episode_onsets(rows)
    dates = [row.date for row in rows]
    other = list(onsets(rows, ONSET_THRESHOLD_BP, dates))
    if [dates[i] for i in found] != other:
        raise ValueError("onset.onset_flags and pressure.onsets disagree on the onset days")
    return found


def check_development(dates) -> None:
    """Refuse any day the model repo's lockbox holds (the plan, Q5: one lockbox, the parent's, read here).

    Raises:
        LookAheadError: a date is in a tier of the parent's lockbox that has not been opened.
    """
    lockbox.require_unlocked(dates, where="attribution")


def check_window_public(rule, dates: Sequence[date], start: int, report_index: int) -> None:
    """Every input of the window starting at `start` was public at the decision instant of `report_index`.

    The window is the baseline and the days after the onset. Each non-calendar input is read on its own declaration
    through the parent's `InformationRule.availability`; a calendar input is known in advance. The rule's first group
    is the spread itself (the outcome, SOFR - IORB), so the spread's publication time is checked with the drivers'.

    Raises:
        LookAheadError: an input of some window day is observable only after the report instant.
    """
    from repo_model.asof import KIND_CALENDAR

    deadline = rule.decision_instant(dates, report_index)
    for position in range(start - BASELINE_DAYS, start + WINDOW_DAYS):
        for group in rule.groups:
            if group.kind == KIND_CALENDAR:
                continue
            available = rule.availability(dates, group.fields, position)
            if available > deadline:
                raise LookAheadError(
                    f"{group.feature!r} for {dates[position]} is available at {available}, after the "
                    f"{deadline} report instant"
                )


# --------------------------------------------------------------------------- windows and the fitting sample


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    if any(v is None for v in values):
        return None
    return sum(values) / len(values)  # type: ignore[arg-type]


def change(values: Sequence[Optional[float]], start: int) -> Optional[float]:
    """The window mean minus the baseline mean for a window starting at `start`; None if any day is missing."""
    if start < BASELINE_DAYS or start + WINDOW_DAYS > len(values):
        return None
    after = _mean(values[start : start + WINDOW_DAYS])
    before = _mean(values[start - BASELINE_DAYS : start])
    if after is None or before is None:
        return None
    return after - before


def _changes(series: Series, drivers: Sequence[str], start: int) -> Optional[Tuple[float, Tuple[float, ...]]]:
    y = change(series[SPREAD], start)
    xs = [change(series[name], start) for name in drivers]
    if y is None or any(x is None for x in xs):
        return None
    return y, tuple(xs)  # type: ignore[arg-type]


def fitting_rows(
    series: Series, drivers: Sequence[str], left_out: Optional[int], last_start: Optional[int] = None
) -> Tuple[List[Tuple[float, ...]], List[float]]:
    """Every window of the sample as one regression row, less the windows that touch the left-out episode.

    A row is the driver changes and the spread change of the window starting at `t`. It is dropped when any day is
    missing, and when its baseline-plus-window overlaps the left-out episode's (`|t - left_out| < baseline + window`).
    """
    n = len(series[SPREAD])
    last = n - WINDOW_DAYS if last_start is None else min(last_start, n - WINDOW_DAYS)
    gap = BASELINE_DAYS + WINDOW_DAYS
    xs: List[Tuple[float, ...]] = []
    ys: List[float] = []
    for t in range(BASELINE_DAYS, last + 1):
        if left_out is not None and abs(t - left_out) < gap:
            continue
        row = _changes(series, drivers, t)
        if row is None:
            continue
        ys.append(row[0])
        xs.append(row[1])
    return xs, ys


# --------------------------------------------------------------------------- the regression and the Shapley shares


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting. A singular system is refused, not patched."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    scale = max((abs(v) for row in a for v in row), default=0.0)
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) <= 1e-12 * max(scale, 1.0):
            raise ValueError("the driver changes are collinear or constant in the fitting sample")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def _subsets(p: int) -> List[Tuple[int, ...]]:
    return [tuple(j for j in range(p) if mask >> j & 1) for mask in range(1 << p)]


def shapley(values: Mapping[Tuple[int, ...], float], p: int) -> List[float]:
    """Shapley values of the `p` drivers for the value function `values` (subset of indices -> prediction)."""
    out = [0.0] * p
    for j in range(p):
        for subset in _subsets(p):
            if j in subset:
                continue
            k = len(subset)
            weight = math.factorial(k) * math.factorial(p - k - 1) / math.factorial(p)
            with_j = tuple(sorted(subset + (j,)))
            out[j] += weight * (values[with_j] - values[subset])
    return out


def _normal_equations(xs, ys, indices: Sequence[int]):
    """X'X and X'y over `indices` of the rows, with no intercept: a window with no driver change predicts no rise."""
    p = len(xs[0])
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for i in indices:
        x, y = xs[i], ys[i]
        for a in range(p):
            xty[a] += x[a] * y
            for b in range(a, p):
                xtx[a][b] += x[a] * x[b]
    for a in range(p):
        for b in range(a):
            xtx[a][b] = xtx[b][a]
    return xtx, xty


def _predictions(xtx, xty, change_vector: Sequence[float]) -> Dict[Tuple[int, ...], float]:
    """The prediction of every sub-model (a regression on that subset of drivers, refitted) for one episode."""
    p = len(change_vector)
    values: Dict[Tuple[int, ...], float] = {(): 0.0}
    for subset in _subsets(p):
        if not subset:
            continue
        a = [[xtx[r][c] for c in subset] for r in subset]
        b = [xty[r] for r in subset]
        beta = _solve(a, b)
        values[subset] = sum(bj * change_vector[j] for bj, j in zip(beta, subset))
    return values


def _fixed_shares(xtx, xty, change_vector: Sequence[float], rise: float) -> List[float]:
    """beta_j * dx_j / rise, with beta from the full model's fit. Reported only; the Shapley shares are the method."""
    beta = _solve([row[:] for row in xtx], list(xty))
    return [bj * dj / rise for bj, dj in zip(beta, change_vector)]


def _shares(xtx, xty, change_vector: Sequence[float], rise: float) -> Tuple[List[float], float, float]:
    values = _predictions(xtx, xty, change_vector)
    phi = shapley(values, len(change_vector))
    full = values[tuple(range(len(change_vector)))]
    return [v / rise for v in phi], (rise - full) / rise, full / rise


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    position = q * (len(sorted_values) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


# --------------------------------------------------------------------------- one episode


def _point_fit(series: Series, start: int, drivers: Sequence[str], last_start: Optional[int]):
    """The point attribution of one window: an `Attribution` ("not attributable") or the fit's pieces."""
    target = _changes(series, drivers, start)
    if target is None:
        return Attribution(start, "not attributable", "an input of the window is missing or the window is incomplete")
    rise, d = target
    if not rise > 0:
        return Attribution(start, "not attributable", "the window shows no rise in the spread", rise_bp=rise)
    xs, ys = fitting_rows(series, drivers, start, last_start)
    if len(ys) <= len(drivers):
        return Attribution(start, "not attributable", "too few fitting rows", rise_bp=rise)
    try:
        xtx, xty = _normal_equations(xs, ys, range(len(ys)))
        shares, residual, explained = _shares(xtx, xty, d, rise)
        fixed = _fixed_shares(xtx, xty, d, rise)
    except ValueError as error:
        return Attribution(start, "not attributable", str(error), rise_bp=rise)
    return rise, d, xs, ys, shares, residual, explained, fixed


def point_attribution(
    series: Series, start: int, *, drivers: Sequence[str] = DRIVERS, last_start: Optional[int] = None
) -> Attribution:
    """`attribute` without the bootstrap interval: the shares and the residual of one window, nothing else."""
    drivers = tuple(drivers)
    fit = _point_fit(series, start, drivers, last_start)
    if isinstance(fit, Attribution):
        return fit
    rise, _, _, _, shares, residual, explained, fixed = fit
    return Attribution(
        start, "attributed", rise_bp=rise, shares=dict(zip(drivers, shares)), fixed_shares=dict(zip(drivers, fixed)),
        residual_share=residual, explained_share=explained,
    )


def attribute(
    series: Series,
    start: int,
    *,
    drivers: Sequence[str] = DRIVERS,
    draws: int = DRAWS,
    seed: int = SEED,
    block_length: float = BLOCK_LENGTH,
    level: float = LEVEL,
    last_start: Optional[int] = None,
    rule=None,
    dates: Optional[Sequence[date]] = None,
    report_index: Optional[int] = None,
) -> Attribution:
    """The shares of the rise in the window starting at `start`, fitted with that window's neighbourhood left out.

    A window with a missing input, an incomplete window, a rise of no more than zero, or a singular fit is returned
    as "not attributable" with the reason; it is never dropped. `last_start` truncates the fitting sample (a
    prospective report fits only on windows already public).

    The point shares come from the regression on the whole fitting sample. The interval is the percentile interval of
    the shares over `draws` stationary-bootstrap resamples of the fitting rows (the parent's
    `metrics.stationary_bootstrap_indices`), each refitted.

    A real episode is attributed with `rule`, `dates` and `report_index` all given: the window's spread and drivers must
    have been public at the report's decision instant (`check_window_public`). They are given together or not at all;
    the synthetic series of the method's tests carry no dates and pass none.

    Raises:
        LookAheadError: an input of the window was not public at the report instant.
        ValueError: only some of `rule`, `dates` and `report_index` are given.
    """
    from repo_model.metrics import stationary_bootstrap_indices

    given = [name for name, value in (("rule", rule), ("dates", dates), ("report_index", report_index)) if value is not None]
    if given and len(given) != 3:
        raise ValueError(f"rule, dates and report_index are given together; only {', '.join(given)} was")
    if rule is not None:
        check_window_public(rule, dates, start, report_index)
    drivers = tuple(drivers)
    fit = _point_fit(series, start, drivers, last_start)
    if isinstance(fit, Attribution):
        return fit
    rise, d, xs, ys, shares, residual, explained, fixed = fit
    p = len(drivers)

    rng = random.Random(seed * 1_000_003 + start)
    columns: List[List[float]] = [[] for _ in range(p)]
    residuals: List[float] = []
    unusable = 0
    for _ in range(draws):
        picks = stationary_bootstrap_indices(len(ys), block_length, rng)
        try:
            b_xtx, b_xty = _normal_equations(xs, ys, picks)
            s, r, _ = _shares(b_xtx, b_xty, d, rise)
        except ValueError:
            unusable += 1
            continue
        for j in range(p):
            columns[j].append(s[j])
        residuals.append(r)
    if unusable > MAX_UNUSABLE_DRAWS * draws:
        raise ValueError(f"{unusable} of {draws} bootstrap draws were unusable (a singular resample)")
    lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
    intervals = {
        name: (_percentile(sorted(col), lo), _percentile(sorted(col), hi)) for name, col in zip(drivers, columns)
    }
    residual_interval = (_percentile(sorted(residuals), lo), _percentile(sorted(residuals), hi))
    return Attribution(
        start,
        "attributed",
        rise_bp=rise,
        shares=dict(zip(drivers, shares)),
        fixed_shares=dict(zip(drivers, fixed)),
        residual_share=residual,
        explained_share=explained,
        intervals=intervals,
        residual_interval=residual_interval,
        unusable_draws=unusable,
    )


def explained_above_reserves(series: Series, start: int, **kwargs) -> Optional[float]:
    """The benchmark: the drivers' explained share minus that of reserves alone, for one episode. None if either is
    not attributable."""
    full = attribute(series, start, drivers=DRIVERS, **kwargs)
    alone = attribute(series, start, drivers=RESERVES_ONLY, **kwargs)
    if full.status != "attributed" or alone.status != "attributed":
        return None
    return full.explained_share - alone.explained_share


# --------------------------------------------------------------------------- the placebo and the outcome rule


def _day_type(series: Series, t: int) -> Tuple[bool, bool]:
    quarter_end = series["quarter_end"][t]
    settlement = series["treasury_settlement"][t]
    return (bool(quarter_end), bool(settlement and settlement > 0))


def placebo_starts(series: Series, onsets: Sequence[int], per_episode: int = PLACEBO_WINDOWS, seed: int = SEED) -> Dict[int, List[int]]:
    """For each episode, windows of the same length and day type that touch no episode.

    The day type is the start day's quarter-end flag and whether Treasury settlement is positive. A candidate is a
    start with complete inputs whose baseline and window overlap no onset's. The pick is seeded and sorted.
    """
    n = len(series[SPREAD])
    gap = BASELINE_DAYS + WINDOW_DAYS
    free = [
        t
        for t in range(BASELINE_DAYS, n - WINDOW_DAYS + 1)
        if all(abs(t - o) >= gap for o in onsets) and _changes(series, DRIVERS, t) is not None
    ]
    rng = random.Random(seed)
    picks: Dict[int, List[int]] = {}
    for onset in onsets:
        wanted = _day_type(series, onset)
        matches = [t for t in free if _day_type(series, t) == wanted]
        picks[onset] = sorted(rng.sample(matches, min(per_episode, len(matches))))
    return picks


def outcome(attributions: Sequence[Attribution]) -> dict:
    """The plan's rule: "drivers named" when the residual share is under 50% in more than half the episodes.

    Every episode is in the denominator, a not-attributable one as a miss.
    """
    total = len(attributions)
    under = sum(1 for a in attributions if a.residual_under_bar)
    fraction = under / total if total else 0.0
    return {
        "episodes": total,
        "under_bar": under,
        "not_attributable": sum(1 for a in attributions if a.status != "attributed"),
        "fraction": fraction,
        "outcome": "drivers named" if total and fraction > MAJORITY else "residual dominates",
    }


# --------------------------------------------------------------------------- the selection-aware null (amendment, PROPOSED)


@dataclass(frozen=True)
class SelectionNull:
    """The explained shares of episodes the onset rule picks from a spread with no driver effect. `bar` is its
    `quantile`; an episode beats the null when its explained share is above it."""

    bar: float
    quantile: float
    draws: int
    episodes: int
    explained: Tuple[float, ...]


def coefficients(series: Series, drivers: Sequence[str] = DRIVERS) -> Dict[str, float]:
    """The full model's coefficients, fitted on every complete window of the sample (no episode left out)."""
    drivers = tuple(drivers)
    xs, ys = fitting_rows(series, drivers, None)
    xtx, xty = _normal_equations(xs, ys, range(len(ys)))
    return dict(zip(drivers, _solve(xtx, xty)))


def rule_onsets(spread: Sequence[float]) -> List[int]:
    """Row positions the model repo's onset rule (`repo_model.onset.onset_flags`) picks from a spread series."""
    from types import SimpleNamespace

    from repo_model.onset import onset_flags

    return [i for i, flag in enumerate(onset_flags([SimpleNamespace(spread_bps=v) for v in spread])) if flag]


def driver_free_spread(series: Series, drivers: Sequence[str] = DRIVERS) -> List[float]:
    """The spread less the drivers' fitted effect, at its original level: a series that carries no driver effect.

    The effect is `sum_j beta_j x_j` on each day with every driver present, with beta from `coefficients`; the mean of
    that effect is added back so the level the onset rule thresholds is kept. A day with a driver missing is unchanged."""
    drivers = tuple(drivers)
    beta = coefficients(series, drivers)
    effect: List[Optional[float]] = []
    for t in range(len(series[SPREAD])):
        values = [series[name][t] for name in drivers]
        effect.append(None if any(v is None for v in values) else sum(beta[name] * v for name, v in zip(drivers, values)))
    present = [e for e in effect if e is not None]
    centre = sum(present) / len(present)
    return [y if e is None else y - e + centre for y, e in zip(series[SPREAD], effect)]


def selection_null(
    series: Series,
    drivers: Sequence[str] = DRIVERS,
    *,
    draws: int = NULL_DRAWS,
    seed: int = SEED,
    block_length: float = BLOCK_LENGTH,
    quantile: float = NULL_QUANTILE,
) -> SelectionNull:
    """The null for how episodes are selected (the amendment, section 9).

    Each draw takes the driver-free spread (`driver_free_spread`), resamples it by the stationary bootstrap (so its
    persistence is kept and its link to the real drivers is cut), picks onsets from the resample with the model repo's
    rule, and attributes each pick against the real drivers: one fit on every complete window of that resample, then the
    shares of the pick (`_shares`). The fit does not leave the pick out, which only raises the null's explained share, so
    the bar is conservative. The bar is `quantile` of the explained shares pooled over the draws.

    Raises:
        ValueError: the rule picks no attributable episode from any draw (nothing to set a bar on).
    """
    from repo_model.metrics import stationary_bootstrap_indices

    drivers = tuple(drivers)
    n = len(series[SPREAD])
    base = driver_free_spread(series, drivers)
    dx = {}
    for t in range(BASELINE_DAYS, n - WINDOW_DAYS + 1):
        moved = [change(series[name], t) for name in drivers]
        if all(v is not None for v in moved):
            dx[t] = tuple(moved)
    rng = random.Random(seed)
    explained: List[float] = []
    for _ in range(draws):
        spread = [base[i] for i in stationary_bootstrap_indices(n, block_length, rng)]
        picks = [t for t in rule_onsets(spread) if t in dx]
        if not picks:
            continue
        xs = list(dx.values())
        ys = [change(spread, t) for t in dx]
        try:
            xtx, xty = _normal_equations(xs, ys, range(len(ys)))
            _solve([row[:] for row in xtx], list(xty))
        except ValueError:
            continue
        for t in picks:
            rise = ys[list(dx).index(t)]
            if not rise > 0:
                continue
            explained.append(_shares(xtx, xty, dx[t], rise)[2])
    if not explained:
        raise ValueError("the onset rule picks no attributable episode from a spread with no driver effect")
    ranked = sorted(explained)
    return SelectionNull(_percentile(ranked, quantile), quantile, draws, len(ranked), tuple(ranked))


def beats_null(attribution_: Attribution, null: SelectionNull) -> bool:
    """The amendment's test of one episode: attributed, and its explained share is above the null's bar."""
    return attribution_.status == "attributed" and attribution_.explained_share > null.bar


def outcome_with_null(attributions: Sequence[Attribution], null: SelectionNull) -> dict:
    """The plan's rule, with an episode counted only if it is under the residual bar and beats the null.

    Every episode is in the denominator, a not-attributable one as a miss."""
    total = len(attributions)
    counted = sum(1 for a in attributions if a.residual_under_bar and beats_null(a, null))
    fraction = counted / total if total else 0.0
    return {
        "episodes": total,
        "under_bar": sum(1 for a in attributions if a.residual_under_bar),
        "beats_null": sum(1 for a in attributions if beats_null(a, null)),
        "counted": counted,
        "not_attributable": sum(1 for a in attributions if a.status != "attributed"),
        "fraction": fraction,
        "outcome": "drivers named" if total and fraction > MAJORITY else "residual dominates",
    }
