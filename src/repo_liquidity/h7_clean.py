"""H7m, development: the calendar-clean variants of candidates C and D (`docs/stages/h7-calendar-clean.md`, directive #147).

Four variants of candidate C are run, declared next to the current C (which stays as the baseline, in `h7_candidate_c`), under
the rulings on Q1-Q6 (`docs/stages/h7-calendar-clean.md` section 9). D and its variants are **not run** (D dropped under #142,
Q5); their code stays here, tested, and is not called by the run.

====  ===========  ===========  ============================  =====================================
 #    Candidate    Days         Objective                     Left side
====  ===========  ===========  ============================  =====================================
CV1   C            clean        sum of absolute deviations    corridor position (SOFR)
CV2   C            clean        sum of absolute deviations    corridor-normalised EFFR (Q2)
CV3   C            clean        least squares                 corridor position (SOFR); (a) only
CV4   C            all          sum of absolute deviations    corridor position (SOFR); (b) only
====  ===========  ===========  ============================  =====================================

What changes against a baseline, and nothing else:

* **Which days a refit fits on** (CV1 to CV3). A scored day is dropped from the days a refit fits on, and from the days its
  bootstrap resamples, when the parent's `settlement_day` or `quarter_end_window` is 1 on it, or the parent's
  `turn_days.turn_label` is not None on it (Q1). Each is read from the parent, never re-implemented: the first two through its
  `InformationRule` at the day's own decision instant, the label for the scored day alone (`read_turn`). The counted-episode rule
  is taken over the clean days. A dropped day is still served, by the refit in force. CV4 fits every day the baseline does.
* **The objective** (CV1, CV2, CV4). The sum of absolute deviations of the left side from Stage 2's curve
  `a + b x max(k - D, 0)`, `b >= 0`, `k` on `h7_candidate_c.KINK_GRID`. `lad_curve` returns the optimum over the whole kink
  grid. CV3 keeps the baseline's least squares (`ls_curve`).
* **The tie rule** (finding #54). Kinks tied within `KINK_TIE_RTOL` of the least objective go to the smaller kink, which is
  not part of the estimate. The three starts of the outer search are compared at the end of a refit: two starts whose objectives
  are tied and whose parameters differ by more than one grid step in any parameter make the refit **not identified**. It serves
  no estimate and is never replaced by a picked vector (`combine_starts`). It holds for every variant (Q3), CV3 included.
* **Reported, not changed.** Each fitted refit records the Politis-White block length of its training residuals
  (`politis_white_block`), to be read beside goalpost 2. The bootstrap's mean block stays 10.

Reads nothing but through the parent's as-of rule and the group series' and SLR rows' own availability times. Nothing is scored
here: `variant_path` returns each refit's path and its gaps for goalposts 1 and 2 (`summarise`).

Solver. The inner fit is the exact least-absolute-deviation line with a non-negative slope, found for every kink at once: the
objective after profiling out the intercept (the median residual) is convex and piecewise linear in the slope, so a
golden-section search over the slope, started on a bracket that is doubled until the optimum is inside it, reaches the
optimum to a relative `SOLVER_RTOL` of the objective. `tests/test_h7_clean.py` checks it against brute force over every
two-point vertex and the `b = 0` boundary. numpy is the approved extra of `docs/decisions/dependencies.md` (Stage 4).
"""

from __future__ import annotations

import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor
from datetime import date, time
from typing import Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import numpy as np
from repo_model import asof, data, satiation
from repo_model.asof import InformationRule
from repo_model.data import DailyObservation, next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError, SplitError

from repo_liquidity import demand_curve, declaration, goalposts, scheduled
from repo_liquidity import h7_candidate_c as c
from repo_liquidity import h7_candidate_d as d
from repo_liquidity import h7_estimator as h7

#: The curve's kink grid: candidate C's, in the units of aggregate deployable liquidity (a share of bank assets).
KINK_GRID = c.KINK_GRID
#: The parent's tolerance for "tied" (`satiation.KINK_TIE_RTOL`, #747): relative to the least objective.
KINK_TIE_RTOL = satiation.KINK_TIE_RTOL
#: The solver returns an objective within this relative distance of the optimum.
SOLVER_RTOL = 1e-10
SERVING_LAG = h7.SERVING_LAG
BLOCK_LENGTH, LEVEL, SEED = h7.BLOCK_LENGTH, h7.LEVEL, h7.SEED
MAX_PASSES = c.MAX_PASSES
DECISION_TIME = time(16, 0)
#: The parent's flags the exclusion set reads through its rule (`docs/stages/h7-calendar-clean.md` section 2(a)): both are
#: calendar or scheduled inputs read at the scored day itself. The third clause, the turn-day label, is read by `read_turn`.
FLAG_FEATURES = ("settlement_day", "quarter_end_window")
#: The reason a refit serves nothing.
NO_EPISODE, NO_FIT, NOT_IDENTIFIED, FITTED = "no counted episode", "no fit", "not identified", "fitted"
#: Golden-section contraction and the iterations it takes to shrink a bracket by 1e-15.
_GOLDEN = (5 ** 0.5 - 1) / 2
_ITERATIONS = 64
#: The iterations every kink gets before the clearly worse ones are dropped (`lad_curve`).
_COARSE = 30

#: The left sides: the baseline's SOFR corridor position, and EFFR's position in the same corridor (Q2).
CORRIDOR, EFFR_CORRIDOR = "corridor", "effr_corridor"
OBJECTIVES = ("lad", "ls")
DAYS = ("clean", "all")


class Variant(NamedTuple):
    """One declared variant: the days it fits on (`clean` or `all`), its objective (`lad` or `ls`) and its left side."""

    id: str
    candidate: str
    days: str
    objective: str
    left: str


#: The variants the run fits (section 9 of the declaration, Q2 and Q4). CV3 is (a) only, CV4 is (b) only.
VARIANTS: Tuple[Variant, ...] = (
    Variant("CV1", "C", "clean", "lad", CORRIDOR), Variant("CV2", "C", "clean", "lad", EFFR_CORRIDOR),
    Variant("CV3", "C", "clean", "ls", CORRIDOR), Variant("CV4", "C", "all", "lad", CORRIDOR),
)
#: D's variants are declared and implemented, and not run: Eleonora's #142 ruling (b), D dropped (Q5). They do not count.
D_VARIANTS: Tuple[Variant, ...] = tuple(Variant("D" + v.id[1:], "D", v.days, v.objective, v.left) for v in VARIANTS)
D_NOT_RUN = "not run (D dropped under #142)"
#: One grid step of each searched parameter: the shares (C), and D's level, slope, small and foreign-related shares.
STEPS_C: Tuple[float, ...] = (0.01, 0.01, 0.01)
STEPS_D: Tuple[float, ...] = (0.01, 0.1, 0.01, 0.01)


# -- the exclusion set ------------------------------------------------------------------------------------------------


class Flags(NamedTuple):
    """The parent's two flags for one scored day, and the day they were read for. None is a hole in an input. `unread` marks a
    day the rule cannot form an information set for (the panel's second row has too little history for the target's lag): its
    flags were not read, so it cannot be certified clean and leaves the days a refit fits on."""

    day: date
    settlement_day: Optional[float]
    quarter_end_window: Optional[float]
    unread: bool = False
    #: The parent's `turn_days.turn_label` of the day: a label when it is a turn day, else None (Q1).
    turn: Optional[str] = None

    def dropped(self) -> bool:
        """Whether the day leaves the days a refit fits on: one of the three clauses of the exclusion set holds.

        Raises:
            ValueError: a flag is a hole, so whether the day is a calendar day is not known.
        """
        if self.unread:
            return True
        if self.settlement_day is None or self.quarter_end_window is None:
            raise ValueError(f"{self.day}: a calendar flag is a hole, so whether it is a clean day is not known")
        return self.settlement_day == 1.0 or self.quarter_end_window == 1.0 or self.turn is not None


def with_quarter_end_window(rows: Sequence[DailyObservation]) -> List[DailyObservation]:
    """The rows with the parent's opt-in `quarter_end_window` column, a function of the date alone (`data.quarter_end_window`)."""
    return [DailyObservation(row.date, {**row.values, "quarter_end_window": data.quarter_end_window(row.date)}) for row in rows]


def flag_rule(registry: Optional[Mapping[str, Mapping]] = None) -> InformationRule:
    """The rule that reads the two flags: the parent's, under Phase 3's registry, at 16:00 on the day before."""
    return InformationRule(declaration.registry() if registry is None else registry, FLAG_FEATURES,
                           decision_time=DECISION_TIME, horizon=1)


def parent_turn_label() -> Callable[[date], Optional[str]]:
    """The parent's `repo_model.turn_days.turn_label`: a label for the month's last business day and the first business day
    after it, else None. Read from the parent, never re-implemented here.

    Raises:
        ValueError: the parent at this tree's pin has no `turn_days` (it comes with the pin move, #149), so the exclusion set's
            third clause cannot be read and nothing may be fitted.
    """
    import importlib

    try:
        return importlib.import_module("repo_model.turn_days").turn_label
    except ImportError as error:
        raise ValueError("repo_model.turn_days is absent at the pin of this tree; the turn-day clause of the exclusion set "
                         "(Q1) cannot be read until the pin moves (#149), so no variant may be fitted yet") from error


def read_turn(turn_label: Callable[[date], Optional[str]], scored: date, read: date) -> Optional[str]:
    """The turn-day label of the scored day, read for the day `read`.

    Raises:
        LookAheadError: `read` is not the scored day. The label is read for the day's own date and no other.
    """
    if read != scored:
        raise LookAheadError(f"the turn-day label of {scored} was read for {read}; it is read for the scored day only")
    return turn_label(read)


def check_flag_reads(info: asof.InformationSet) -> None:
    """A flag is a calendar or scheduled input and is read at the scored day itself.

    Raises:
        LookAheadError: a calendar or scheduled read is at any row other than the scored one.
    """
    for read in info.reads:
        if read.kind in (asof.KIND_CALENDAR, asof.KIND_SCHEDULED) and read.row != info.scored_index:
            raise LookAheadError(f"{read.feature!r} for the scored row {info.scored_index} was read at row {read.row}; "
                                 "a calendar flag is read at the day's own decision instant, for that day only")


def read_flags(rows: Sequence[DailyObservation], rule: InformationRule,
               turn_label: Optional[Callable[[date], Optional[str]]] = None) -> Dict[date, Flags]:
    """The flags of every scored day (row `i + 1`, scored from the reads at row `i`), through `rule`, and its turn-day label.

    `rows` must carry `quarter_end_window` (`with_quarter_end_window`). `turn_label` is the parent's `turn_days.turn_label`
    (`parent_turn_label()` when None).

    Raises:
        LookAheadError: the rule refuses a read, or a flag or the label is read for any day but the scored one.
        StaleReadError: a read is older than the latest value public at the decision instant.
        ValueError: the parent has no turn-day label at this pin, or its holiday table does not cover a day.
    """
    labeller = parent_turn_label() if turn_label is None else turn_label
    dates = [row.date for row in rows]
    out: Dict[date, Flags] = {}
    for i in range(len(rows) - 1):
        scored = rows[i + 1]
        turn = read_turn(labeller, scored.date, scored.date)
        extended = h7._extended(dates, i)
        try:
            info = rule.information_set(extended, i + 1)
        except SplitError:
            out[scored.date] = Flags(scored.date, None, None, True, turn)
            continue
        rule.check(extended, info)
        check_flag_reads(info)
        values = rule.observation(rows, info).values
        out[scored.date] = Flags(scored.date, values.get("settlement_day"), values.get("quarter_end_window"), False, turn)
    return out


def clean_days(days: Sequence, flags: Mapping[date, Flags]) -> List:
    """`days` less those whose flags drop them. Each day reads its own flags.

    Raises:
        LookAheadError: the flags found for a day were read for another day.
        ValueError: a day has no flags, or a flag is a hole.
    """
    out = []
    for x in days:
        flag = flags.get(x.day)
        if flag is None:
            raise ValueError(f"{x.day} has no calendar flags")
        if flag.day != x.day:
            raise LookAheadError(f"the flags for {x.day} were read for {flag.day}")
        if not flag.dropped():
            out.append(x)
    return out


# -- the exact absolute-deviation fit ---------------------------------------------------------------------------------


class Curve(NamedTuple):
    """Stage 2's curve fitted by absolute deviation: the kink, the intercept, the slope and the objective."""

    kink: float
    intercept: float
    slope: float
    objective: float


def _profile(z: np.ndarray, y: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """The intercept (the median residual) and the objective at slopes `b`, one row per slope."""
    resid = y[None, :] - b[:, None] * z
    mid = (resid.shape[1] - 1) // 2
    a = np.partition(resid, mid, axis=1)[:, mid]
    return a, np.abs(resid - a[:, None]).sum(axis=1)


class _State(NamedTuple):
    """A golden-section search over the slope, one row per regressor: the bracket, its two interior points and their objectives,
    the objective at slope 0, and whether the row has any spread in `z`."""

    lo: np.ndarray
    hi: np.ndarray
    x1: np.ndarray
    x2: np.ndarray
    f1: np.ndarray
    f2: np.ndarray
    f0: np.ndarray
    a0: np.ndarray
    live: np.ndarray


def _start(z: np.ndarray, y: np.ndarray) -> _State:
    zero = np.zeros(z.shape[0])
    a0, f0 = _profile(z, y, zero)
    spread = z.max(axis=1) - z.min(axis=1)
    live = spread > 0.0
    hi = np.where(live, 2.0 * (y.max() - y.min() + 1e-12) / np.where(live, spread, 1.0), 0.0)
    # grow the bracket until the objective at its top no longer falls: the objective is convex, so the optimum is then inside
    for _ in range(64):
        f_hi = _profile(z, y, hi)[1]
        f_half = _profile(z, y, hi / 2.0)[1]
        grow = live & (f_hi < f_half - SOLVER_RTOL * np.maximum(f_half, 1e-300))
        if not grow.any():
            break
        hi = np.where(grow, hi * 2.0, hi)
    x1, x2 = hi - _GOLDEN * hi, _GOLDEN * hi
    return _State(zero, hi, x1, x2, _profile(z, y, x1)[1], _profile(z, y, x2)[1], f0, a0, live)


def _advance(z: np.ndarray, y: np.ndarray, state: _State, iterations: int) -> _State:
    lo, hi, x1, x2, f1, f2 = state[:6]
    for _ in range(iterations):
        left = f1 <= f2  # the minimum is in [lo, x2]
        hi = np.where(left, x2, hi)
        lo = np.where(left, lo, x1)
        new1 = hi - _GOLDEN * (hi - lo)
        new2 = lo + _GOLDEN * (hi - lo)
        probe = np.where(left, new1, new2)
        fp = _profile(z, y, probe)[1]
        x1, x2 = np.where(left, new1, x2), np.where(left, x1, new2)
        f1, f2 = np.where(left, fp, f2), np.where(left, f1, fp)
    return state._replace(lo=lo, hi=hi, x1=x1, x2=x2, f1=f1, f2=f2)


def _finish(z: np.ndarray, y: np.ndarray, state: _State) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    b = np.where(state.live, (state.lo + state.hi) / 2.0, 0.0)
    a, f = _profile(z, y, b)
    boundary = state.f0 <= f * (1.0 + SOLVER_RTOL)  # the boundary b = 0 is a candidate of its own
    return np.where(boundary, state.a0, a), np.where(boundary, 0.0, b), np.where(boundary, state.f0, f)


def lad_lines(z: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The exact least-absolute-deviation line `y = a + b z` with `b >= 0` for each row of `z` (one regressor per row).

    Returns the intercepts, the slopes and the objectives. A row with no spread in `z` has slope 0 and the median intercept.
    """
    return _finish(z, y, _advance(z, y, _start(z, y), _ITERATIONS))


def lad_curve(xs: Sequence[float], ys: Sequence[float], grid: Optional[Sequence[float]] = None) -> Optional[Curve]:
    """The best broken stick `a + b x max(k - x, 0)`, `b >= 0`, by absolute deviation, over `grid`.

    A kink with no point on one side of it is skipped, as `demand_curve.fit_broken_stick` skips it. Kinks whose objectives are
    within `KINK_TIE_RTOL` of the least go to the smaller kink. None when no kink has points on both sides.

    Every kink is searched for `_COARSE` iterations first. The objective is Lipschitz in the slope, so the bracket's width bounds
    how far the optimum can lie below the best value seen; a kink whose bound is above the best seen by more than the tie
    tolerance cannot be the best or tied with it, and is dropped. Only the survivors are searched to the end.
    """
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    candidates = np.asarray(KINK_GRID if grid is None else grid, dtype=float)
    below = np.searchsorted(np.sort(x), candidates, side="left")  # the points strictly below each kink
    kinks = candidates[(below > 0) & (below < len(x))]
    if len(kinks) == 0:
        return None
    z = np.maximum(kinks[:, None] - x[None, :], 0.0)
    state = _advance(z, y, _start(z, y), _COARSE)
    inside = np.minimum(state.f1, state.f2)  # objectives at points inside the bracket, which holds a minimiser
    bound = np.maximum(inside - z.sum(axis=1) * (state.hi - state.lo), 0.0)
    keep = bound <= np.minimum(inside, state.f0).min() * (1.0 + 2.0 * KINK_TIE_RTOL)
    kept = np.flatnonzero(keep)
    sub = _State(*[arr[kept] for arr in state])
    a, b, f = _finish(z[kept], y, _advance(z[kept], y, sub, _ITERATIONS - _COARSE))
    best = f.min()
    pick = int(np.argmax(f <= best * (1.0 + KINK_TIE_RTOL)))  # the first (smallest) kink among the tied
    return Curve(float(kinks[kept[pick]]), float(a[pick]), float(b[pick]), float(f[pick]))


def ls_curve(xs: Sequence[float], ys: Sequence[float], grid: Optional[Sequence[float]] = None) -> Optional[Curve]:
    """The baseline's least-squares broken stick (`demand_curve.fit_broken_stick`), with its rejection of a negative slope.

    This is what the current candidate C fits (`h7_candidate_c._evaluate`) and what CV3 keeps: only the days differ. None when
    no kink has points on both sides, or the slope is negative.
    """
    try:
        fit = demand_curve.fit_broken_stick(np.asarray(xs, dtype=float).tolist(), np.asarray(ys, dtype=float).tolist(),
                                            KINK_GRID if grid is None else grid)
    except ValueError:
        return None
    return Curve(fit.kink, fit.intercept, fit.slope, fit.sse) if fit.slope >= 0.0 else None


def curve_for(objective: str) -> Callable[..., Optional[Curve]]:
    """`lad_curve` or `ls_curve`, looked up when called.

    Raises:
        ValueError: the objective is neither.
    """
    if objective == "lad":
        return lad_curve
    if objective == "ls":
        return ls_curve
    raise ValueError(f"the objective is one of {OBJECTIVES}, not {objective!r}")


# -- the outer search and the three starts ----------------------------------------------------------------------------


class Searched(NamedTuple):
    params: Tuple[float, ...]
    curve: Curve


class Combined(NamedTuple):
    """The outcome of a refit's three starts: its status, the chosen parameters and curve, whether every start agreed, and the
    span of the tied parameters when the refit is not identified."""

    status: str
    chosen: Optional[Searched]
    starts_agree: Optional[bool]
    span: Optional[Tuple[float, ...]]


def descend(start: Sequence[float], grids: Sequence[Sequence[float]], evaluate: Callable[[Tuple[float, ...]], Optional[Curve]]
            ) -> Optional[Searched]:
    """The baselines' coordinate search over `grids` from `start`, under the absolute-deviation objective.

    A value replaces the current one only when its objective is lower by more than `KINK_TIE_RTOL`, so a coordinate's tied
    values resolve to the smaller one, as in the baselines.
    """
    current = tuple(start)
    best = evaluate(current)
    for _ in range(MAX_PASSES):
        improved = False
        for g, grid in enumerate(grids):
            for value in grid:
                candidate = current[:g] + (value,) + current[g + 1:]
                curve = evaluate(candidate)
                if curve is not None and (best is None or curve.objective < best.objective * (1.0 - KINK_TIE_RTOL)):
                    current, best, improved = candidate, curve, True
        if not improved:
            break
    return None if best is None else Searched(current, best)


def combine_starts(results: Sequence[Searched], steps: Sequence[float]) -> Combined:
    """The tie rule's point 3 (`docs/stages/h7-calendar-clean.md` section 2(b)).

    Starts whose objectives are within `KINK_TIE_RTOL` of the least are tied. If two tied starts differ by more than one grid
    step in any parameter, the refit is **not identified**: no estimate, and no picked vector. Otherwise the lowest objective
    wins, then the smaller parameter vector in the order the parameters are listed.
    """
    if not results:
        return Combined(NO_FIT, None, None, None)
    least = min(r.curve.objective for r in results)
    tied = [r for r in results if r.curve.objective <= least * (1.0 + KINK_TIE_RTOL)]
    span = tuple(max(r.params[j] for r in tied) - min(r.params[j] for r in tied) for j in range(len(steps)))
    agree = all(r.params == results[0].params for r in results)
    if any(s > step + 1e-9 for s, step in zip(span, steps)):
        return Combined(NOT_IDENTIFIED, None, agree, span)
    chosen = min(tied, key=lambda r: (r.curve.objective, r.params))
    return Combined(FITTED, chosen, agree, span)


# -- the bootstrap draws ----------------------------------------------------------------------------------------------


#: What a draw needs, set before the draws run. Worker processes are forked after it is set, so they inherit it.
_CONTEXT: Dict[str, object] = {}


def _draw(index: np.ndarray) -> Optional[Tuple[float, ...]]:
    """One bootstrap draw: the parameters refitted on the days `index` resamples, searching from the refit's own parameters."""
    ctx = _CONTEXT
    reserves, assets, ys = ctx["reserves"][index], ctx["assets"][index], ctx["ys"][index]
    curve = curve_for(ctx["objective"])
    if ctx["kind"] == "C":
        evaluate = lambda p: curve(_xs_c(p, reserves, assets), ys)  # noqa: E731
    else:
        heads = ctx["heads"][index]
        evaluate = lambda p: curve(_xs_d(p, reserves, assets, heads), ys)  # noqa: E731
    found = descend(ctx["start"], ctx["grids"], evaluate)
    return None if found is None else found.params


def run_draws(context: Mapping[str, object], replications: int, size: int, seed: int, workers: int = 1
              ) -> List[Tuple[float, ...]]:
    """The refitted parameters of `replications` stationary-bootstrap draws of `size` days, in draw order.

    The indices come from one generator seeded with `seed`, as the baselines' draws do, and are taken before any draw runs, so
    the result does not depend on `workers`. A draw that cannot be fitted is left out.
    """
    rng = random.Random(seed)
    indices = [np.asarray(stationary_bootstrap_indices(size, BLOCK_LENGTH, rng)) for _ in range(replications)]
    _CONTEXT.clear()
    _CONTEXT.update(context)
    if workers <= 1 or replications < 2:
        found = [_draw(index) for index in indices]
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as pool:
            found = list(pool.map(_draw, indices, chunksize=max(1, replications // (workers * 8))))
    _CONTEXT.clear()
    return [f for f in found if f is not None]


# -- the left side and the training days -------------------------------------------------------------------------------


def left_sides(rows: Sequence[DailyObservation], on_rrp_rate: Optional[Callable[[date], Optional[float]]] = None
               ) -> Dict[str, Dict[date, Optional[float]]]:
    """Each scored day's EFFR position in the corridor, `(EFFR - ON RRP rate) / (IORB - ON RRP rate)` (Q2): the corridor
    position of `demand_curve.corridor_position`, with EFFR in place of SOFR and the ON RRP rate in force on the day. It replaces
    raw `effr_minus_iorb_bp`, which is not offered beside it. None where a leg or the rate is missing. The SOFR corridor position
    is the baseline day's own.

    Raises:
        ValueError: if the rows carry no `effr` column, or a day's corridor is not positive.
    """
    if not any("effr" in row.values for row in rows):
        raise ValueError("the rows carry no effr column: build them with nyfed_effr_inputs (scripts/h7_calendar_clean.py)")
    if on_rrp_rate is None:
        publications = scheduled.load_on_rrp_rates()
        on_rrp_rate = lambda day: scheduled.rate_in_force(publications, day)  # noqa: E731
    out: Dict[date, Optional[float]] = {}
    for row in rows:
        effr, iorb, floor = row.values.get("effr"), row.values.get("iorb"), on_rrp_rate(row.date)
        out[row.date] = None if effr is None or iorb is None or floor is None else demand_curve.corridor_position(
            sofr=float(effr), iorb=float(iorb), on_rrp_rate=float(floor))
    return {EFFR_CORRIDOR: out}


def _left(left_side: str, series: Mapping[str, Mapping[date, Optional[float]]], x) -> Optional[float]:
    return x.corridor if left_side == CORRIDOR else series[left_side].get(x.day)


def training_days(days: Sequence, cutoff: date, flags: Optional[Mapping[date, Flags]], left_side: str,
                  series: Mapping[str, Mapping[date, Optional[float]]], usable: Callable[[object], bool], *, clean: bool = True,
                  episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED):
    """The days a refit at `cutoff` fits on, with the labels of its counted episodes.

    A day is usable when it is on or before the cutoff, `usable` holds (a group week, and for D a headroom) and its left side is
    known; with `clean` the dropped days (`clean_days`) leave (`flags` may be None without it, CV4); an episode counts with at
    least `min_scarce` of the days that remain whose ratio is below 13%.
    """
    pool = [x for x in days if x.day <= cutoff and usable(x) and _left(left_side, series, x) is not None]
    if clean:
        pool = clean_days(pool, flags)
    chosen: List = []
    labels: List[str] = []
    for label, first, last in episodes:
        inside = [x for x in pool if first <= x.day <= last]
        if sum(1 for x in inside if x.ratio is not None and x.ratio < demand_curve.SCARCE_BELOW) >= min_scarce:
            chosen.extend(inside)
            labels.append(label)
    return sorted(chosen, key=lambda x: x.day), tuple(labels)


def _dropped(days, cutoff, left_side, series, usable, episodes, labels, sample) -> int:
    """How many days of the counted episodes, on or before the cutoff, the exclusion set took out of the sample."""
    spans = [(first, last) for label, first, last in episodes if label in labels]
    inside = [x for x in days if x.day <= cutoff and usable(x) and _left(left_side, series, x) is not None
              and any(first <= x.day <= last for first, last in spans)]
    return len(inside) - len(sample)


# -- the Politis-White block length of a refit's residuals (reported beside goalpost 2, changes nothing) ----------------


def politis_white_block(residuals: Sequence[float], c: float = 2.0) -> Optional[float]:
    """The optimal mean block length of the stationary bootstrap for a residual series, by Politis and White (2004) with the
    correction of Patton, Politis and White (2009).

    With `n` residuals (taken in time order, centred), `K = max(5, ceil(sqrt(log10 n)))` and the sample autocovariances `R(k)`:
    `m` is the smallest lag from which `K` successive autocorrelations are all below `c sqrt(log10(n) / n)` (the largest allowed
    lag, `ceil(sqrt n) + K`, if none), the window is `M = 2 max(m, 1)` with the flat-top taper `lambda(t) = 1` for `t <= 1/2` and
    `2 (1 - t)` above, and the block is `(2 G^2 / D)^(1/3) n^(1/3)` with `G = 2 sum_k lambda(k/M) k R(k)` and
    `D = 2 (R(0) + 2 sum_k lambda(k/M) R(k))^2`, never above `ceil(min(3 sqrt n, n / 3))` and never below 1. None for fewer
    than ten residuals, or residuals with no variation, or no long-run variance.

    This is the figure of Lens C (repo-market-model#958) that the declaration asks to report: it is the mean block a series
    like this one would want, to set beside the mean block of 10 the bootstrap uses.
    """
    x = np.asarray(residuals, dtype=float)
    n = len(x)
    if n < 10:
        return None
    x = x - x.mean()
    scale = float(np.sqrt((x * x).mean()))
    if not scale > 0.0 or scale < 1e-12 * max(1.0, float(np.abs(np.asarray(residuals, dtype=float)).max())):
        return None
    k_n = max(5, int(np.ceil(np.sqrt(np.log10(n)))))
    m_max = min(int(np.ceil(np.sqrt(n))) + k_n, n - 1)
    cov = np.array([float(x[: n - k] @ x[k:]) / n for k in range(m_max + 1)])
    rho = np.abs(cov[1:] / cov[0])  # lags 1 .. m_max
    critical = c * np.sqrt(np.log10(n) / n)
    m_hat = m_max
    for m in range(0, m_max - k_n + 1):
        if np.all(rho[m: m + k_n] < critical):  # lags m + 1 .. m + k_n
            m_hat = m
            break
    window = min(2 * max(m_hat, 1), m_max)
    lags = np.arange(1, window + 1)
    t = lags / window
    taper = np.where(t <= 0.5, 1.0, 2.0 * (1.0 - t))
    long_run = cov[0] + 2.0 * float((taper * cov[1: window + 1]).sum())
    g = 2.0 * float((taper * lags * cov[1: window + 1]).sum())
    if not long_run * long_run > 0.0:
        return None
    block = (2.0 * g * g / (2.0 * long_run * long_run)) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return round(float(min(max(block, 1.0), np.ceil(min(3.0 * np.sqrt(n), n / 3.0)))), 2)


def curve_residuals(curve: Curve, xs: Sequence[float], ys: Sequence[float]) -> List[float]:
    """The left side less Stage 2's curve at the fitted `curve`, day by day in the order given."""
    x = np.asarray(xs, dtype=float)
    return (np.asarray(ys, dtype=float) - (curve.intercept + curve.slope * np.maximum(curve.kink - x, 0.0))).tolist()


def baseline_residuals_c(days: Sequence[c.DayC], refit: c.RefitC, *, episodes=demand_curve.EPISODES,
                         min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[float]:
    """The training residuals of a refit of the current candidate C, on the days it fitted on. Empty when it did not fit."""
    if not refit.fitted:
        return []
    sample, _ = c.training_days(days, refit.cutoff, episodes=episodes, min_scarce=min_scarce)
    xs = _xs_c(refit.shares, np.array([x.week.reserves_bn for x in sample]), np.array([x.week.assets_bn for x in sample]))
    return curve_residuals(Curve(refit.kink, refit.intercept, refit.slope, refit.sse), xs, [x.corridor for x in sample])


# -- candidate C ------------------------------------------------------------------------------------------------------


def _xs_c(shares, reserves: np.ndarray, assets: np.ndarray) -> np.ndarray:
    return np.maximum(reserves - np.asarray(shares) * assets, 0.0).sum(axis=1) / assets.sum(axis=1)


def fit_c(sample: Sequence[c.DayC], ys: Sequence[float], starts: Sequence[Sequence[float]] = c.START_SHARES, *,
          objective: str = "lad") -> Combined:
    """The three shares over `sample`, whose left side is `ys`, by `objective` (absolute deviation or least squares), with the
    tie rule."""
    reserves = np.array([x.week.reserves_bn for x in sample])
    assets = np.array([x.week.assets_bn for x in sample])
    curve = curve_for(objective)
    evaluate = lambda shares: curve(_xs_c(shares, reserves, assets), ys)  # noqa: E731
    found = [descend(s, (c.SHARE_GRID,) * len(c.GROUPS), evaluate) for s in starts]
    return combine_starts([r for r in found if r is not None], STEPS_C)


def _record(combined: Combined, **extra) -> Dict[str, object]:
    record = {"status": combined.status, "fitted": combined.status == FITTED}
    if combined.span is not None:
        record["tied_span"] = list(combined.span)
    if combined.chosen is not None:
        curve = combined.chosen.curve
        record.update(kink=curve.kink, intercept=curve.intercept, slope=curve.slope, objective=curve.objective,
                      starts_agree=combined.starts_agree)
    record.update(extra)
    return record


def refit_c(days: Sequence[c.DayC], cutoff: date, flags: Optional[Mapping[date, Flags]], left_side: str,
            series: Mapping[str, Mapping[date, Optional[float]]], *, replications: int, seed: int = SEED, workers: int = 1,
            clean: bool = True, objective: str = "lad", episodes=demand_curve.EPISODES,
            min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> c.RefitC:
    """The refit at `cutoff` of C's shares, with the bootstrap draws of its shares.

    `clean` fits on the days the exclusion set leaves (CV1 to CV3) or on every day the baseline does (CV4, `flags` may be None);
    `objective` is `"lad"` (absolute deviation) or `"ls"` (least squares, CV3). A refit with no counted episode, no fit, or no
    identification is not fitted and has no draws.

    Raises:
        LookAheadError: a day of the sample is after `cutoff`, or a flag was read for another day.
        ValueError: the objective is unknown.
    """
    curve_for(objective)
    usable = lambda x: x.week is not None  # noqa: E731
    sample, labels = training_days(days, cutoff, flags, left_side, series, usable, clean=clean, episodes=episodes,
                                   min_scarce=min_scarce)
    for x in sample:
        if x.day > cutoff:
            raise LookAheadError(f"the shares for the refit at {cutoff} would be fitted on {x.day}, after its cutoff")
    breaks = tuple(sorted({x.week.week_ending for x in sample if x.week.break_week}))
    dropped = _dropped(days, cutoff, left_side, series, usable, episodes, labels, sample)
    if not sample:
        return c.RefitC(cutoff, None, False, None, None, None, None, 0, labels, None, breaks, (),
                        _record(Combined(NO_EPISODE, None, None, None), dropped=dropped, objective_kind=objective))
    ys = [_left(left_side, series, x) for x in sample]
    ys_array = np.asarray(ys, dtype=float)
    combined = fit_c(sample, ys, objective=objective)
    if combined.status != FITTED:
        return c.RefitC(cutoff, None, False, None, None, None, None, len(sample), labels, combined.starts_agree, breaks, (),
                        _record(combined, dropped=dropped, objective_kind=objective))
    shares, curve = combined.chosen
    reserves, assets = np.array([x.week.reserves_bn for x in sample]), np.array([x.week.assets_bn for x in sample])
    block = politis_white_block(curve_residuals(curve, _xs_c(shares, reserves, assets), ys_array))
    context = {"kind": "C", "objective": objective, "reserves": reserves, "assets": assets, "ys": ys_array, "start": shares,
               "grids": (c.SHARE_GRID,) * len(c.GROUPS)}
    draws = run_draws(context, replications, len(sample), seed, workers)
    return c.RefitC(cutoff, shares, True, curve.kink, curve.intercept, curve.slope, curve.objective, len(sample), labels,
                    combined.starts_agree, breaks, tuple(draws),
                    _record(combined, dropped=dropped, replications=replications, draws=len(draws), objective_kind=objective,
                            pw_block=block))


# -- candidate D ------------------------------------------------------------------------------------------------------


def _xs_d(params, reserves: np.ndarray, assets: np.ndarray, heads: np.ndarray) -> np.ndarray:
    level, slope, small, foreign = params
    large = np.clip(level + slope * heads / assets[:, d.SLR_GROUP], 0.0, d.MAX_BUFFER)
    buffers = np.stack([large, np.full(len(large), small), np.full(len(large), foreign)], axis=1)
    return np.maximum(reserves - buffers * assets, 0.0).sum(axis=1) / assets.sum(axis=1)


def _usable_d(x: d.DayD) -> bool:
    return x.week is not None and x.headroom is not None and x.headroom.headroom_bn is not None


def refit_d(days: Sequence[d.DayD], cutoff: date, flags: Optional[Mapping[date, Flags]], left_side: str,
            series: Mapping[str, Mapping[date, Optional[float]]], *, replications: int, seed: int = SEED, workers: int = 1,
            clean: bool = True, objective: str = "lad", episodes=demand_curve.EPISODES,
            min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> d.RefitD:
    """The refit at `cutoff` of D's four parameters on the days that have a headroom, as `refit_c` does for C.

    A day with no headroom is not a training day (finding #142). D is **not run** (dropped under #142, Q5): this is kept,
    tested, and not called by `scripts/h7_calendar_clean.py`.
    """
    curve = curve_for(objective)
    sample, labels = training_days(days, cutoff, flags, left_side, series, _usable_d, clean=clean, episodes=episodes,
                                   min_scarce=min_scarce)
    for x in sample:
        if x.day > cutoff:
            raise LookAheadError(f"the parameters for the refit at {cutoff} would be fitted on {x.day}, after its cutoff")
    breaks = tuple(sorted({x.week.week_ending for x in sample if x.week.break_week}))
    dropped = _dropped(days, cutoff, left_side, series, _usable_d, episodes, labels, sample)
    if not sample:
        return d.RefitD(cutoff, None, False, None, None, None, None, 0, labels, None, breaks, (),
                        _record(Combined(NO_EPISODE, None, None, None), dropped=dropped, objective_kind=objective))
    ys = [_left(left_side, series, x) for x in sample]
    ys_array = np.asarray(ys, dtype=float)
    reserves = np.array([x.week.reserves_bn for x in sample])
    assets = np.array([x.week.assets_bn for x in sample])
    heads = np.array([x.headroom.headroom_bn for x in sample])
    grids = (d.LEVEL_GRID, d.SLOPE_GRID, c.SHARE_GRID, c.SHARE_GRID)
    evaluate = lambda p: curve(_xs_d(p, reserves, assets, heads), ys)  # noqa: E731
    found = [descend(s, grids, evaluate) for s in d.START_PARAMETERS]
    combined = combine_starts([r for r in found if r is not None], STEPS_D)
    if combined.status != FITTED:
        return d.RefitD(cutoff, None, False, None, None, None, None, len(sample), labels, combined.starts_agree, breaks, (),
                        _record(combined, dropped=dropped, objective_kind=objective))
    params, fitted_curve = combined.chosen
    block = politis_white_block(curve_residuals(fitted_curve, _xs_d(params, reserves, assets, heads), ys_array))
    context = {"kind": "D", "objective": objective, "reserves": reserves, "assets": assets, "heads": heads, "ys": ys_array,
               "start": params, "grids": grids}
    draws = [d.Params(*p) for p in run_draws(context, replications, len(sample), seed, workers)]
    fitted = d.Params(*params)
    return d.RefitD(cutoff, fitted, True, fitted_curve.kink, fitted_curve.intercept, fitted_curve.slope, fitted_curve.objective,
                    len(sample), labels, combined.starts_agree, breaks, tuple(draws),
                    _record(combined, dropped=dropped, replications=replications, draws=len(draws), objective_kind=objective,
                            pw_block=block,
                            headroom_slope_sign="negative" if fitted.slope < 0 else "positive" if fitted.slope > 0 else "zero"))


# -- the real-time path and the goalposts -----------------------------------------------------------------------------


class VariantPath(NamedTuple):
    """One refit's real-time path: the refit, its served estimates, the gap to the previous refit on each served day, the
    served days it left missing, and the served days that read an H.8 break week."""

    refit: object
    estimates: List[h7.Estimate]
    gaps: Dict[date, float]
    missing_days: int
    break_days: Tuple[date, ...]


def variant_path(days: Sequence, cutoffs: Sequence[date], refit_fn: Callable[[date], object],
                 value_fn: Callable[[object, object], Optional[float]],
                 interval_fn: Callable[[object, object], Optional[Tuple[float, float]]]) -> List[VariantPath]:
    """Each refit's path over the days it serves, as the baselines' `real_time_path`. Computed, not scored.

    `refit_fn(cutoff)` is a refit; `value_fn(day, refit_params)` the day's estimate (None when the day cannot be served);
    `interval_fn(refit, day)` its interval. Refit `k` serves from the second business day after its cutoff to the day before
    refit `k + 1` serves from, dropped days included. A refit that is not fitted serves nothing.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [next_business_day(cut, SERVING_LAG) for cut in cutoffs]
    refits = [refit_fn(cut) for cut in cutoffs]
    out: List[VariantPath] = []
    for k, fit in enumerate(refits):
        end = starts[k + 1] if k + 1 < len(starts) else None
        estimates: List[h7.Estimate] = []
        gaps: Dict[date, float] = {}
        breaks: List[date] = []
        missing = 0
        for x in (x for x in days if x.day >= starts[k] and (end is None or x.day < end)):
            value = None if not fit.fitted or x.ratio is None else value_fn(x, fit.shares if hasattr(fit, "shares") else fit.params)
            if value is None:
                missing += 1
                continue
            span = interval_fn(fit, x)
            estimates.append(h7.Estimate(x.day, x.ratio, value, None if span is None else span[0],
                                         None if span is None else span[1], x.state))
            if x.week.break_week:
                breaks.append(x.day)
            if k > 0 and refits[k - 1].fitted:
                before = value_fn(x, refits[k - 1].shares if hasattr(refits[k - 1], "shares") else refits[k - 1].params)
                if before is not None:
                    gaps[x.day] = abs(value - before)
        out.append(VariantPath(fit, estimates, gaps, missing, tuple(breaks)))
    return out


def _signature(sample, labels, left_side, series) -> Tuple:
    """Everything a refit's fit depends on: the days it fits on, what each read and its left side."""
    return (labels, tuple((x.day, x.ratio, _left(left_side, series, x),
                           x.week.reserves_bn, x.week.assets_bn, getattr(getattr(x, "headroom", None), "headroom_bn", None))
                          for x in sample))


def _memoised(refit_fn, sample_fn):
    """`refit_fn(cutoff)` computed once for each distinct training sample: a refit is a function of its sample alone (the
    bootstrap seed is fixed), so two cutoffs that fit on the same days share one refit, with each its own cutoff."""
    cache: Dict[Tuple, object] = {}

    def refit(cutoff: date):
        key = sample_fn(cutoff)
        if key not in cache:
            cache[key] = refit_fn(cutoff)
        return cache[key]._replace(cutoff=cutoff)

    return refit


def path_c(days: Sequence[c.DayC], cutoffs: Sequence[date], flags: Optional[Mapping[date, Flags]], left_side: str,
           series: Mapping[str, Mapping[date, Optional[float]]], *, replications: int, seed: int = SEED, workers: int = 1,
           clean: bool = True, objective: str = "lad", episodes=demand_curve.EPISODES,
           min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[VariantPath]:
    """A variant of C over `cutoffs`: `left_side` is `"corridor"` or `"effr_corridor"`, `clean` and `objective` as `refit_c`
    (CV1: the defaults; CV2: the EFFR position; CV3: `objective="ls"`; CV4: `clean=False`)."""
    def sample_key(cut):
        return _signature(*training_days(days, cut, flags, left_side, series, lambda x: x.week is not None, clean=clean,
                                         episodes=episodes, min_scarce=min_scarce), left_side, series)

    refit = _memoised(lambda cut: refit_c(days, cut, flags, left_side, series, replications=replications, seed=seed,
                                          workers=workers, clean=clean, objective=objective, episodes=episodes,
                                          min_scarce=min_scarce), sample_key)
    return variant_path(days, cutoffs, refit,
                        lambda x, shares: None if x.week is None else c.deployable(x.week, shares),
                        lambda fit, x: None if x.week is None else c.interval(fit, x.week))


def path_d(days: Sequence[d.DayD], cutoffs: Sequence[date], flags: Optional[Mapping[date, Flags]], left_side: str,
           series: Mapping[str, Mapping[date, Optional[float]]], *, replications: int, seed: int = SEED, workers: int = 1,
           clean: bool = True, objective: str = "lad", episodes=demand_curve.EPISODES,
           min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[VariantPath]:
    """A variant of D over `cutoffs` (not run: D is dropped under #142). A served day with no headroom is missing."""
    def sample_key(cut):
        return _signature(*training_days(days, cut, flags, left_side, series, _usable_d, clean=clean, episodes=episodes,
                                         min_scarce=min_scarce), left_side, series)

    refit = _memoised(lambda cut: refit_d(days, cut, flags, left_side, series, replications=replications, seed=seed,
                                          workers=workers, clean=clean, objective=objective, episodes=episodes,
                                          min_scarce=min_scarce), sample_key)
    return variant_path(days, cutoffs, refit,
                        lambda x, params: d.deployable(x.week, x.headroom.headroom_bn, params) if _usable_d(x) else None,
                        lambda fit, x: d.interval(fit, x.week, x.headroom.headroom_bn) if _usable_d(x) else None)


def baseline_path_c(days: Sequence[c.DayC], cutoffs: Sequence[date], *, replications: int, seed: int = SEED,
                    episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[VariantPath]:
    """The current candidate C over `cutoffs`, as `h7_candidate_c.real_time_path` gives it, with one refit for each distinct
    training sample (`_memoised`). `tests/test_h7_clean.py` checks that the two paths are the same."""
    def sample_key(cut):
        sample, labels = c.training_days(days, cut, episodes=episodes, min_scarce=min_scarce)
        return (labels, tuple((x.day, x.ratio, x.corridor, x.week.reserves_bn, x.week.assets_bn) for x in sample))

    refit = _memoised(lambda cut: c.refit_c(days, cut, replications=replications, seed=seed, episodes=episodes,
                                            min_scarce=min_scarce), sample_key)
    return variant_path(days, cutoffs, refit, lambda x, shares: None if x.week is None else c.deployable(x.week, shares),
                        lambda fit, x: None if x.week is None else c.interval(fit, x.week))


def baseline_path_d(days: Sequence[d.DayD], cutoffs: Sequence[date], *, replications: int, seed: int = SEED,
                    episodes=demand_curve.EPISODES, min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> List[VariantPath]:
    """The current candidate D over `cutoffs`, as `h7_candidate_d.real_time_path` gives it, with one refit for each distinct
    training sample."""
    def sample_key(cut):
        sample, labels = d.training_days(days, cut, episodes=episodes, min_scarce=min_scarce)
        return (labels, tuple((x.day, x.ratio, x.corridor, x.week.reserves_bn, x.week.assets_bn, x.headroom.headroom_bn)
                              for x in sample))

    refit = _memoised(lambda cut: d.refit_d(days, cut, replications=replications, seed=seed, episodes=episodes,
                                            min_scarce=min_scarce), sample_key)
    return variant_path(days, cutoffs, refit,
                        lambda x, params: d.deployable(x.week, x.headroom.headroom_bn, params) if _usable_d(x) else None,
                        lambda fit, x: d.interval(fit, x.week, x.headroom.headroom_bn) if _usable_d(x) else None)


def check_no_future(rows: Sequence[DailyObservation], cutoffs: Sequence[date], build: Callable[[Sequence[DailyObservation]], Tuple],
                    left_side: str, usable: Callable[[object], bool], *, clean: bool = True, episodes=demand_curve.EPISODES,
                    min_scarce: int = demand_curve.MIN_SCARCE_DAYS_REVISED) -> None:
    """Refuse a refit whose training sample is not what the panel cut at its own cutoff gives.

    A refit depends on the panel only through its training sample (the days, what each read, its left side and its flags), so
    each cutoff's sample is rebuilt from `rows` up to and including the cutoff row and compared with the one built on all of
    `rows`. `build(rows)` returns the scored days, the flags and the left-side series.

    Raises:
        LookAheadError: a refit's sample differs from the cut panel's, so it depended on a later row.
    """
    days, flags, series = build(rows)
    for cutoff in cutoffs:
        cut_days, cut_flags, cut_series = build([row for row in rows if row.date <= cutoff])
        now = training_days(days, cutoff, flags, left_side, series, usable, clean=clean, episodes=episodes, min_scarce=min_scarce)
        then = training_days(cut_days, cutoff, cut_flags, left_side, cut_series, usable, clean=clean, episodes=episodes,
                             min_scarce=min_scarce)
        if _signature(*now, left_side, series) != _signature(*then, left_side, cut_series):
            raise LookAheadError(f"the training sample of the refit at {cutoff} is not the one the panel cut at that row gives; "
                                 "the refit depended on a later row")


def summarise(paths: Sequence) -> Dict[str, object]:
    """Goalposts 1 and 2 on development days, beside the refit counts (`docs/stages/h7-calendar-clean.md` section 5).

    Works on any path with `refit`, `estimates`, `gaps` and `missing_days` (the baselines' `PathC` and `PathD` included).
    Goalpost 1 reads the gaps on every served day, with the not-fitted refits counted beside it and not as a breach; goalpost 2
    reads the widths, a served day with no interval counting as over the limit. Development evidence, never a verdict.
    """
    gaps: Dict[date, float] = {}
    widths: List[Optional[float]] = []
    status: Dict[str, int] = {}
    for p in paths:
        gaps.update(p.gaps)
        record = p.refit.record
        key = str(record.get("status", FITTED if p.refit.fitted else "not fitted"))
        status[key] = status.get(key, 0) + 1
        for e in p.estimates:
            widths.append(None if e.lower is None or e.upper is None else e.upper - e.lower)
        widths.extend([None] * p.missing_days)
    served = [w for w in widths if w is not None]
    first = goalposts.stability_goalpost(gaps)
    second = goalposts.sharpness_goalpost(widths)
    return {
        "refits": len(paths), "refit_status": status, "not_fitted_refits": sum(not p.refit.fitted for p in paths),
        "goalpost_1": {**first, "worst": None if first["worst"] is None else
                       {"day": first["worst"]["day"].isoformat(), "gap_points": c.points(first["worst"]["gap"])}},
        "goalpost_2": {**second, "median_points": None if second["median"] is None else c.points(second["median"]),
                       "median_served_points": None if not served else c.points(float(np.median(served)))},
        "served_days": sum(len(p.estimates) for p in paths), "missing_days": sum(p.missing_days for p in paths),
    }


# -- the panel rows with EFFR ------------------------------------------------------------------------------------------


#: The parent's snapshot root of the effective federal funds rate, which the version-1 build does not read.
EFFR_ROOT = "nyfed_effr_inputs"


def build_rows():
    """The measurement panel's rows (version 1's columns, byte for byte) with the parent's opt-in `effr` column added.

    Built as `panel.build` builds version 1 from the tracked fixtures, with no network, except that the parent's EFFR snapshots
    are read as well and `effr` is a requested column. Returns the rows and a dict of the pins: the parent's commit, the
    version-1 digest the rows reproduce (checked against its manifest) and the digest of the `effr` series.

    Raises:
        ValueError: the version-1 columns do not reproduce the manifest's digest, a column is refused, or the dates are not
            the published panel's.
    """
    import hashlib
    import json
    import tempfile
    from datetime import datetime
    from pathlib import Path

    from repo_model.data import build_daily_panel

    from repo_liquidity import h41, panel, parent_root, scheduled

    manifest_path = parent_root() / "metadata" / "funding_panel_manifest.json"
    published = json.loads(manifest_path.read_text(encoding="utf-8"))
    cutoff = datetime.fromisoformat(published["build_cutoff"])
    decision = time.fromisoformat(published["decision_time"])
    published_columns = tuple(published["built_columns"])
    with tempfile.TemporaryDirectory() as tmp:
        rows, _snapshot, retrieved = panel._parent_rows(Path(tmp), roots=panel.PARENT_RAW_ROOTS + (EFFR_ROOT,))
    extract_sha = hashlib.sha256(panel.H41_EXTRACT.read_bytes()).hexdigest()
    extra_rows = h41.observations(h41.load_extract(panel.H41_EXTRACT), source_sha=extract_sha)
    with declaration.phase3_declaration(), panel._weekly_carry():
        built = build_daily_panel(list(rows) + extra_rows, declaration.registry(), build_cutoff=cutoff, decision_time=decision,
                                  columns=published_columns + declaration.BUILT_COLUMNS + ("effr",),
                                  snapshot_retrieved_at=retrieved)
    if built.refusals:
        raise ValueError(f"the build refused {dict(built.refusals)}")
    observations = scheduled.with_scheduled(built.observations, decision_time=decision)
    version1 = panel.load_manifest(1)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v1.csv"
        panel._write(observations, version1["columns"], path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != version1["sha256"]:
        raise ValueError(f"the version-1 columns of these rows are {digest}, not the manifest's {version1['sha256']}")
    effr = "".join(f"{row.date.isoformat()},{row.values.get('effr')}\n" for row in observations)
    pins = {"parent_commit": panel._parent_commit(), "panel_version": 1, "panel_sha256": digest,
            "effr_series_sha256": hashlib.sha256(effr.encode()).hexdigest(), "rows": len(observations),
            "first_day": observations[0].date.isoformat(), "last_day": observations[-1].date.isoformat()}
    return observations, pins
