"""Stage 6: deployable liquidity, candidates A and B (`docs/stages/stage-6.md`).

Deployable liquidity on day T is the reserves ratio known at T's decision instant minus the buffer banks want to keep,
both as shares of bank assets (multiplied by bank assets for dollars). Each candidate gives the buffer as a refit
would see it in real time, with a 90% interval.

- **A, the curve's bend.** The bend of Stage 2's corridor-position curve, fitted only on scarce-episode days (Stage 2's
  revised test: episode 1 to 2020-03-13, episode 2 calendar 2025, each counting with at least 60 days below 13%). The
  first episode's bend holds until the second counts; then the second's. Its interval is the stationary bootstrap of the
  bend.
- **B, the latent buffer re-identified.** Stage 3b's extended Kalman filter (`anchored`) with drift held at 0, jumps only
  at the reform dates or at one break, and a third head in place of ON RRP take-up: the gap TGCR - ON RRP rate in basis
  points (Nicholas, answer 12). Filtered estimates only; the interval is the filter's own.

Both are read by a forecast for T at its decision instant: A's bend at the refit in force; B's filtered buffer two
observation days before T, as Stage 3c reads it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from repo_liquidity import anchored, demand_curve, latent
from repo_liquidity.curve_feature import require_on_or_before  # noqa: F401 - re-exported for A's cutoff guard

#: Stage 3c's stability bar, in shares of bank assets.
STABILITY_LIMIT = 0.005
#: The interval bar: the width of the parent's 11-14% sensitivity range.
WIDTH_LIMIT = 0.03
Z90 = 1.6448536269514722
#: The first day a material-use event can occur (Nicholas, answer 5: the Fed's repo operations from 2019-09-17).
EVENTS_FROM = date(2019, 9, 17)
#: The standing-facility era, for the reported split of the score (Nicholas's caveat, answer 14).
FACILITY_ERA = date(2021, 1, 1)


# -- shared ---------------------------------------------------------------------------------------------------------


def auc(scores: Sequence[float], labels: Sequence[int]) -> Optional[float]:
    """The area under the ROC curve for `labels` (1 an event) ranked by `scores`, low scores first; ties count half.

    Low deployable liquidity should mark an event, so a score is the liquidity itself and events should sit low.
    None if either class is empty.
    """
    positives = [s for s, y in zip(scores, labels) if y == 1]
    negatives = [s for s, y in zip(scores, labels) if y == 0]
    if not positives or not negatives:
        return None
    ordered = sorted(negatives)
    import bisect

    total = 0.0
    for score in positives:
        below = len(ordered) - bisect.bisect_right(ordered, score)
        ties = bisect.bisect_right(ordered, score) - bisect.bisect_left(ordered, score)
        total += below + 0.5 * ties
    return total / (len(positives) * len(negatives))


def stability(gaps: Mapping[str, float], *, limit: float = STABILITY_LIMIT) -> Dict:
    """Stage 3c's bar on each served day's gap between refit k and refit k - 1: every gap strictly under `limit`."""
    if not gaps:
        return {"shown": False, "days_compared": 0, "worst": None, "note": "no day was served by two refits"}
    day, worst = max(gaps.items(), key=lambda item: item[1])
    ordered = sorted(gaps.values())
    return {"shown": worst < limit, "limit": limit, "days_compared": len(gaps),
            "worst": {"day": day, "gap": worst},
            "median": ordered[len(ordered) // 2], "p95": ordered[int(0.95 * (len(ordered) - 1))],
            "days_at_or_over_limit": sum(gap >= limit for gap in gaps.values())}


def widths(intervals: Iterable[Tuple[float, float]], *, limit: float = WIDTH_LIMIT) -> Dict:
    values = sorted(upper - lower for lower, upper in intervals)
    if not values:
        return {"shown": False, "note": "no interval"}
    median = values[len(values) // 2]
    return {"shown": median < limit, "limit": limit, "median": median, "max": values[-1], "days": len(values)}


# -- A: the curve's bend ----------------------------------------------------------------------------------------------


class Day(NamedTuple):
    day: date
    x: float          # reserves over bank assets, known at the day's decision instant
    corridor: float   # SOFR's corridor position that day


@dataclass(frozen=True)
class BendEstimate:
    episode: str
    bend: float
    lower: float
    upper: float
    days: int
    scarce_days: int


def episode_days(rows: Sequence[Day], episode) -> List[Day]:
    _label, first, last = episode
    return [row for row in rows if first <= row.day <= last]


def bend_at(rows: Sequence[Day], *, cutoff: date, replications: int = demand_curve.REPLICATIONS) -> BendEstimate:
    """A's bend for the refit at `cutoff`: the second episode's once it counts, else the first's.

    Raises:
        LookAheadError: if a day after `cutoff` would enter the fit.
        ValueError: if the first episode does not count at `cutoff`.
    """
    seen = [row for row in rows if row.day <= cutoff]
    require_on_or_before([row.day for row in seen], cutoff)
    first, second = demand_curve.EPISODES
    chosen = None
    for episode in (second, first):
        days = episode_days(seen, episode)
        scarce = sum(row.x < demand_curve.SCARCE_BELOW for row in days)
        if scarce >= demand_curve.MIN_SCARCE_DAYS_REVISED:
            chosen = (episode, days, scarce)
            break
    if chosen is None:
        raise ValueError(f"no episode counts at {cutoff}")
    (label, _start, _end), days, scarce = chosen
    xs, ys = [row.x for row in days], [row.corridor for row in days]
    fit = demand_curve.fit_broken_stick(xs, ys)
    lower, upper = demand_curve.kink_interval(xs, ys, seed=demand_curve.seed_for(f"stage6a {label} {cutoff}"),
                                              replications=replications)
    return BendEstimate(label, fit.kink, lower, upper, len(days), scarce)


def sample_a(rows) -> List[Day]:
    """Every day of the window with its as-of ratio and corridor position (Stage 2's `demand_curve.sample`)."""
    return [Day(day.day, day.ratio, day.corridor) for day in demand_curve.sample(rows) if day.corridor is not None]


# -- B: the latent buffer, re-identified ---------------------------------------------------------------------------

HEADS_B = ("corridor_position", "sofr_dispersion_bp", "tgcr_minus_on_rrp_bp")
#: The 19 parameters: Stage 3b's 13, then the gap head's level, slope, noise and three calendar terms.
PARAM_NAMES_B = anchored.PARAM_NAMES + ("a_gap", "b_gap", "r_gap", "c_gap_quarter_end", "c_gap_month_end",
                                         "c_gap_tax_date")
_GAP_CALENDAR = slice(16, 19)
#: Drift held at 0 (`docs/stages/stage-6.md`, B): the drift parameter is held here, far out in the logistic's tail.
HELD_DRIFT = {1: anchored.HELD_OFF}
#: One-break candidates: the first day of each quarter from 2020 Q2 to 2024 Q4 (declared in the B record).
BREAK_FIRST = date(2020, 4, 1)
BREAK_LAST = date(2024, 10, 1)


class ObservationB(NamedTuple):
    day: date
    x: float
    y: Tuple[Optional[float], Optional[float], Optional[float]]
    kind: str


def break_grid(cutoff: date) -> List[date]:
    out, year, month = [], BREAK_FIRST.year, BREAK_FIRST.month
    while date(year, month, 1) <= min(BREAK_LAST, cutoff):
        out.append(date(year, month, 1))
        month += 3
        if month > 12:
            year, month = year + 1, month - 12
    return out


def natural_b(params: Sequence[float]) -> Tuple[float, ...]:
    out = list(anchored.natural(params[:13])) + list(params[13:])
    for i in (14, 15):
        out[i] = math.exp(params[i])
    return tuple(out)


def params_b_from_3b(params: Sequence[float]) -> Tuple[float, ...]:
    """Stage 3b's parameters with an idle gap head (level 0, slope 1, noise 1, no calendar terms)."""
    return tuple(params) + (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def start_params_b_example() -> Tuple[float, ...]:
    params = list(params_b_from_3b((0.0,) * 13))
    params[1] = anchored.HELD_OFF
    return tuple(params)


def _run_b(observations: Sequence[ObservationB], params: Sequence[float], anchor: anchored.Anchor, jump_days,
           scale: float, keep: bool):
    values = natural_b(params)
    q, j = values[1], values[2]
    heads = ((anchor.intercept, anchor.slope, values[3], anchored._CORRIDOR_CALENDAR),
             (values[7], values[8], values[9], anchored._DISPERSION_CALENDAR),
             (values[13], values[14], values[15], _GAP_CALENDAR))
    jumps = set(jump_days)
    z, variance = params[0], anchored.INITIAL_VARIANCE
    loglike = 0.0
    path: List[anchored.State] = []
    sigmoid = anchored._sigmoid
    for index, obs in enumerate(observations):
        if index > 0:
            variance += q + (j if obs.day in jumps else 0.0)
        for i, value in enumerate(obs.y):
            if value is None:
                continue
            a, slope, r, part = heads[i]
            sig = sigmoid(z)
            b = anchored.BUFFER_MAX * sig
            g = latent.softplus(b - obs.x, scale)
            h = slope * sigmoid((b - obs.x) / scale) * anchored.BUFFER_MAX * sig * (1.0 - sig)
            s = h * h * variance + r
            if not s > 0.0:
                return -math.inf, path
            v = value - (a + slope * g + anchored._calendar(params, part, obs.kind))
            gain = variance * h / s
            z += gain * v
            variance *= (1.0 - gain * h)
            loglike += -0.5 * (math.log(2 * math.pi * s) + v * v / s)
        if keep:
            sig = sigmoid(z)
            slope_bz = anchored.BUFFER_MAX * sig * (1.0 - sig)
            path.append(anchored.State(obs.day, anchored.BUFFER_MAX * sig, slope_bz * slope_bz * variance, z,
                                       variance))
    return loglike, path


def filter_path_b(observations, params, *, anchor, jump_days, scale: float = latent.SCALE) -> List[anchored.State]:
    return _run_b(observations, params, anchor, jump_days, scale, keep=True)[1]


def objective_b(observations, params, *, anchor, jump_days, scale: float = latent.SCALE) -> float:
    try:
        value = _run_b(observations, params, anchor, jump_days, scale, keep=False)[0]
    except (OverflowError, ValueError):
        return anchored.IMPOSSIBLE
    return value if math.isfinite(value) else anchored.IMPOSSIBLE


def start_params_b(observations: Sequence[ObservationB], anchor: anchored.Anchor) -> Tuple[float, ...]:
    three = [anchored.Observation(o.day, o.x, (o.y[0], o.y[1]), o.kind) for o in observations]
    base = list(anchored.start_params(three, anchor))
    gaps = [o.y[2] for o in observations if o.y[2] is not None]
    mean = sum(gaps) / len(gaps) if gaps else 0.0
    sd = (math.sqrt(sum((g - mean) ** 2 for g in gaps) / (len(gaps) - 1)) if len(gaps) > 1 else 1.0) or 1.0
    base[1] = anchored.HELD_OFF
    return tuple(base) + (mean, math.log(sd / 0.02), math.log((0.5 * sd) ** 2), 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class FitB:
    params: Tuple[float, ...]
    loglike: float
    converged: bool
    cutoff: date
    jump_days: Tuple[date, ...]


def fit_b(observations, *, anchor, jump_days, cutoff: date, start=None, maxiter: int = 400) -> FitB:
    """Maximum likelihood with drift held at 0 (statsmodels GenericLikelihoodModel, Nelder-Mead then BFGS)."""
    import numpy as np
    from statsmodels.base.model import GenericLikelihoodModel

    latent.require_before(observations, cutoff)
    anchored.require_anchor_before(cutoff, anchor)
    observations = list(observations)
    begin = list(start if start is not None else start_params_b(observations, anchor))
    for index, value in HELD_DRIFT.items():
        begin[index] = value
    free = [i for i in range(len(PARAM_NAMES_B)) if i not in HELD_DRIFT]

    def full(z):
        params = list(begin)
        for k, i in enumerate(free):
            params[i] = float(z[k])
        return params

    class _Model(GenericLikelihoodModel):
        def loglike(self, z):
            return objective_b(observations, full(z), anchor=anchor, jump_days=jump_days)

    model = _Model(endog=np.zeros(len(observations)), exog=np.ones((len(observations), 1)))
    model.exog_names[:] = ["const"]
    result = model.fit(start_params=np.asarray([begin[i] for i in free], dtype=float), method="nm",
                       maxiter=maxiter, disp=0)
    result = model.fit(start_params=result.params, method="bfgs", maxiter=maxiter, disp=0)
    params = tuple(full(result.params))
    return FitB(params, objective_b(observations, params, anchor=anchor, jump_days=jump_days),
                bool(result.mle_retvals.get("converged", False)), cutoff, tuple(jump_days))


def start_grid_b(observations, anchor) -> List[Tuple[str, Tuple[float, ...]]]:
    base = start_params_b(observations, anchor)
    return [("data", base)] + [(f"buffer_{b}", (anchored._logit(b / anchored.BUFFER_MAX),) + tuple(base[1:]))
                               for b in anchored.START_BUFFERS]


def _fit_b_job(job) -> FitB:
    observations, kwargs = job
    import warnings

    warnings.simplefilter("ignore")
    return fit_b(observations, **kwargs)


def fit_best_b(observations, *, anchor, jump_days, cutoff, previous=None, mapper=map, starts=None) -> FitB:
    """`fit_b` from the previous answer (if given) and every start of `start_grid_b`; the highest likelihood wins."""
    grid = start_grid_b(observations, anchor) if starts is None else starts
    if previous is not None:
        grid = [("previous", tuple(previous))] + list(grid)
    jobs = [(list(observations), dict(anchor=anchor, jump_days=list(jump_days), cutoff=cutoff, start=start))
            for _label, start in grid]
    fits = list(mapper(_fit_b_job, jobs))
    return max(fits, key=lambda f: f.loglike)


def assemble_b(rows) -> List[ObservationB]:
    """Stage 3b's observations (`anchored.assemble`) with the gap TGCR - ON RRP rate in force that day, in bp."""
    from repo_liquidity import scheduled

    floors = scheduled.load_on_rrp_rates()
    by_day = {row.date: row.values for row in rows}
    out = []
    for obs in anchored.assemble(rows):
        values = by_day[obs.day]
        floor = scheduled.rate_in_force(floors, obs.day)
        gap = None if floor is None or values.get("tgcr") is None else round(100.0 * (values["tgcr"] - floor), 6)
        out.append(ObservationB(obs.day, obs.x, (obs.y[0], obs.y[1], gap), obs.kind))
    return out
