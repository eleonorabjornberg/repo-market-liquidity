"""Stage 3b: the buffer on a fixed curve, filtered by an extended Kalman filter (`docs/stages/stage-3b.md`).

State: z_t, with the desired buffer B_t = BUFFER_MAX * logistic(z_t), so B stays between 0 and BUFFER_MAX. It drifts
(variance q per business day) and may jump on a reform date (variance q + j). Two heads observe it, each
y = a + b * g + c[type] + e with e ~ N(0, r), where g = softplus(B - x) at scale `latent.SCALE` and type is the day's
pressure-day type under the parent's split declaration:

0. the corridor position, with a and b fixed at Stage 2's 2018 to March 2020 curve (`load_anchor`);
1. SOFR dispersion (p75 - p25, bp), with a and b estimated.

ON RRP and facility take-up are not in the state. Parameters by maximum likelihood (statsmodels
`GenericLikelihoodModel`, the `state-space` extra). Filtered estimates only.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from repo_liquidity import latent

ROOT = Path(__file__).resolve().parents[2]
STAGE_2_RECORD = ROOT / "results" / "stage2" / "demand_curve.json"
ANCHOR_EPISODE = "2018 to March 2020"

HEADS = ("corridor_position", "sofr_dispersion_bp")
#: Pressure-day types with a calendar term; "ordinary" days carry none.
CALENDAR = ("quarter_end", "month_end", "tax_date")
PARAM_NAMES = (("buffer_0", "drift_sd", "jump_sd", "r_corridor_position")
               + tuple(f"c_corridor_position_{kind}" for kind in CALENDAR)
               + ("a_sofr_dispersion_bp", "b_sofr_dispersion_bp", "r_sofr_dispersion_bp")
               + tuple(f"c_sofr_dispersion_bp_{kind}" for kind in CALENDAR))
BUFFER_MAX = 0.30
#: Bounds in z (`docs/stages/stage-3b.md`): about 0.2 points a day and 5 points a jump near a 10% buffer.
DRIFT_SD_MAX = 0.03
JUMP_SD_MAX = 0.75
#: An unconstrained value that holds a standard deviation at (numerically) 0.
HELD_OFF = -40.0
INITIAL_VARIANCE = 1.0
#: Initial buffers the multi-start grid tries (`docs/stages/stage-3b.md`, amendment of 6 October 2026).
START_BUFFERS = (0.05, 0.09, 0.13, 0.17)
_CORRIDOR_CALENDAR = slice(4, 7)
_DISPERSION_CALENDAR = slice(10, 13)


class Anchor(NamedTuple):
    intercept: float
    slope: float
    last_day: date


class Observation(NamedTuple):
    day: date
    x: float
    y: Tuple[Optional[float], Optional[float]]
    kind: str


class State(NamedTuple):
    day: date
    mean: float       # the buffer B
    variance: float   # B's variance, mapped from z's
    z: float
    z_variance: float


@dataclass(frozen=True)
class Fit:
    params: Tuple[float, ...]
    loglike: float
    converged: bool
    cutoff: date
    scale: float


def load_anchor(path: Path = STAGE_2_RECORD) -> Tuple[Anchor, str]:
    """Stage 2's broken-stick curve for 2018 to March 2020, and the record's sha256."""
    raw = path.read_bytes()
    episode = json.loads(raw)["revised_test"]["episodes"][ANCHOR_EPISODE]
    anchor = Anchor(intercept=episode["fit"]["intercept"], slope=episode["fit"]["slope_per_unit"],
                    last_day=date.fromisoformat(episode["last"]))
    return anchor, hashlib.sha256(raw).hexdigest()


def split_declaration():
    """The parent's pressure-day declaration, as it stands at the pin."""
    from repo_model.evaluation_splits import load_split_declaration

    from repo_liquidity import parent_root

    return load_split_declaration(parent_root() / "metadata" / "evaluation_splits.json")


def _sigmoid(u: float) -> float:
    if u >= 0:
        return 1.0 / (1.0 + math.exp(-u))
    e = math.exp(u)
    return e / (1.0 + e)


def natural(params: Sequence[float]) -> Tuple[float, ...]:
    """Unconstrained optimizer values to natural ones: the buffer, standard deviations, positive slope and noises."""
    out = list(params)
    out[0] = BUFFER_MAX * _sigmoid(params[0])
    out[1] = (DRIFT_SD_MAX * _sigmoid(params[1])) ** 2
    out[2] = (JUMP_SD_MAX * _sigmoid(params[2])) ** 2
    for i in (3, 8, 9):
        out[i] = math.exp(params[i])
    return tuple(out)


def _calendar(params, part: slice, kind: str) -> float:
    if kind not in CALENDAR:
        return 0.0
    return params[part][CALENDAR.index(kind)]


def _run(observations: Sequence[Observation], params: Sequence[float], anchor: Anchor, jump_days, scale: float,
         keep: bool):
    values = natural(params)
    q, j = values[1], values[2]
    heads = ((anchor.intercept, anchor.slope, values[3], _CORRIDOR_CALENDAR),
             (values[7], values[8], values[9], _DISPERSION_CALENDAR))
    jumps = set(jump_days)
    z, variance = params[0], INITIAL_VARIANCE
    loglike = 0.0
    path: List[State] = []
    for index, obs in enumerate(observations):
        if index > 0:
            variance += q + (j if obs.day in jumps else 0.0)
        for i, value in enumerate(obs.y):
            if value is None:
                continue
            a, slope, r, part = heads[i]
            sig = _sigmoid(z)
            b = BUFFER_MAX * sig
            g = latent.softplus(b - obs.x, scale)
            h = slope * _sigmoid((b - obs.x) / scale) * BUFFER_MAX * sig * (1.0 - sig)
            s = h * h * variance + r
            if not s > 0.0:  # a noise that underflowed to 0: the optimizer's point is impossible, not an error
                return -math.inf, path
            v = value - (a + slope * g + _calendar(params, part, obs.kind))
            gain = variance * h / s
            z += gain * v
            variance *= (1.0 - gain * h)
            loglike += -0.5 * (math.log(2 * math.pi * s) + v * v / s)
        if keep:
            sig = _sigmoid(z)
            slope_bz = BUFFER_MAX * sig * (1.0 - sig)
            path.append(State(obs.day, BUFFER_MAX * sig, slope_bz * slope_bz * variance, z, variance))
    return loglike, path


def loglike(observations, params, *, anchor: Anchor, jump_days, scale: float = latent.SCALE) -> float:
    return _run(observations, params, anchor, jump_days, scale, keep=False)[0]


def filter_path(observations, params, *, anchor: Anchor, jump_days, scale: float = latent.SCALE) -> List[State]:
    """The filtered buffer for every observation day (never smoothed)."""
    return _run(observations, params, anchor, jump_days, scale, keep=True)[1]


#: The objective's value at a parameter point the model cannot evaluate (a non-finite likelihood or an overflow).
IMPOSSIBLE = -1e12


def objective(observations, params, *, anchor: Anchor, jump_days, scale: float = latent.SCALE) -> float:
    """The likelihood the optimizer maximizes: `loglike`, or `IMPOSSIBLE` where it overflows or is not finite."""
    try:
        value = loglike(observations, params, anchor=anchor, jump_days=jump_days, scale=scale)
    except OverflowError:
        return IMPOSSIBLE
    return value if math.isfinite(value) else IMPOSSIBLE


def require_anchor_before(cutoff: date, anchor: Anchor) -> None:
    """Refuse a refit dated before the fixed curve's last day of data.

    Recorded mutation: see `test_anchored.GuardTests.test_a_refit_before_the_curves_last_day_is_refused`.

    Raises:
        LookAheadError: naming the cutoff and the curve's last day.
    """
    from repo_model.splits import LookAheadError

    if cutoff < anchor.last_day:
        raise LookAheadError(f"a refit with cutoff {cutoff} would use a curve fitted on data to {anchor.last_day}")


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def start_params(observations: Sequence[Observation], anchor: Anchor) -> Tuple[float, ...]:
    """Data-scaled starting values (unconstrained): a buffer at the median ratio, each head's spread."""
    xs = sorted(obs.x for obs in observations)

    def spread(i):
        ys = [obs.y[i] for obs in observations if obs.y[i] is not None]
        if len(ys) < 2:
            return 0.0, 1.0
        m = sum(ys) / len(ys)
        return m, math.sqrt(sum((v - m) ** 2 for v in ys) / (len(ys) - 1)) or 1.0

    _, corridor_sd = spread(0)
    mean, sd = spread(1)
    return ((_logit(xs[len(xs) // 2] / BUFFER_MAX), _logit(0.005 / DRIFT_SD_MAX), _logit(0.1 / JUMP_SD_MAX),
             math.log((0.5 * corridor_sd) ** 2), 0.0, 0.0, 0.0,
             mean, math.log(sd / 0.02), math.log((0.5 * sd) ** 2), 0.0, 0.0, 0.0))


def fit(observations: Sequence[Observation], *, anchor: Anchor, jump_days, cutoff: date,
        scale: float = latent.SCALE, start: Optional[Sequence[float]] = None,
        held: Optional[Mapping[int, float]] = None, maxiter: int = 400) -> Fit:
    """Maximum-likelihood parameters on observations up to `cutoff`, with `held` parameters (index to unconstrained
    value) kept where they are (statsmodels GenericLikelihoodModel)."""
    import numpy as np
    from statsmodels.base.model import GenericLikelihoodModel

    latent.require_before(observations, cutoff)
    require_anchor_before(cutoff, anchor)
    observations = list(observations)
    held = dict(held or {})
    begin = list(start if start is not None else start_params(observations, anchor))
    for index, value in held.items():
        begin[index] = value
    free = [i for i in range(len(PARAM_NAMES)) if i not in held]

    def full(z) -> List[float]:
        params = list(begin)
        for k, i in enumerate(free):
            params[i] = float(z[k])
        return params

    class _Model(GenericLikelihoodModel):
        def loglike(self, z):
            return objective(observations, full(z), anchor=anchor, jump_days=jump_days, scale=scale)

    model = _Model(endog=np.zeros(len(observations)), exog=np.ones((len(observations), 1)))
    model.exog_names[:] = ["const"]
    z0 = np.asarray([begin[i] for i in free], dtype=float)
    result = model.fit(start_params=z0, method="nm", maxiter=maxiter, disp=0)
    result = model.fit(start_params=result.params, method="bfgs", maxiter=maxiter, disp=0)
    params = tuple(full(result.params))
    return Fit(params=params, loglike=objective(observations, params, anchor=anchor, jump_days=jump_days, scale=scale),
               converged=bool(result.mle_retvals.get("converged", False)), cutoff=cutoff, scale=scale)


def start_grid(observations: Sequence[Observation], anchor: Anchor) -> List[Tuple[float, ...]]:
    """The data-scaled start, then the same start with each initial buffer in `START_BUFFERS`."""
    base = start_params(observations, anchor)
    return [base] + [(_logit(b / BUFFER_MAX),) + tuple(base[1:]) for b in START_BUFFERS]


def _fit_job(job) -> Fit:
    observations, kwargs = job
    return fit(observations, **kwargs)


def fit_best(observations: Sequence[Observation], *, anchor: Anchor, jump_days, cutoff: date,
             scale: float = latent.SCALE, previous: Optional[Sequence[float]] = None,
             held: Optional[Mapping[int, float]] = None, maxiter: int = 400,
             mapper=map) -> Tuple[Fit, List[Tuple[str, Fit]]]:
    """`fit` from every start (the previous answer first, if given, then `start_grid`); the highest likelihood wins.

    `mapper` runs the starts (the built-in `map`, or a process pool's). Returns the winning fit and every
    (start label, fit) tried, in order.
    """
    starts: List[Tuple[str, Sequence[float]]] = [] if previous is None else [("previous", previous)]
    grid = start_grid(observations, anchor)
    starts += [("data", grid[0])] + [(f"buffer_{b}", s) for b, s in zip(START_BUFFERS, grid[1:])]
    jobs = [(list(observations), dict(anchor=anchor, jump_days=list(jump_days), cutoff=cutoff, scale=scale,
                                      start=tuple(start), held=held, maxiter=maxiter)) for _, start in starts]
    tried = list(zip([label for label, _ in starts], mapper(_fit_job, jobs)))
    best = max((f for _, f in tried), key=lambda f: f.loglike if math.isfinite(f.loglike) else -math.inf)
    return best, tried


def assemble(rows) -> List[Observation]:
    """Stage 3b's observations from the Phase 3 panel rows, to 2025-12-31.

    x and the corridor position come from Stage 2's `demand_curve.sample`, as in Stage 3. Dispersion is the day's SOFR
    75th minus 25th percentile. The type is the day's pressure-day type, read from its own calendar columns.
    """
    from repo_liquidity import demand_curve

    declaration = split_declaration()
    by_day = {row.date: row.values for row in rows}
    out = []
    for day in demand_curve.sample(rows):
        values = by_day[day.day]
        p25, p75 = values.get("sofr_p25"), values.get("sofr_p75")
        out.append(Observation(day.day, day.ratio, (
            day.corridor,
            None if p25 is None or p75 is None else round(100.0 * (p75 - p25), 6),
        ), declaration.day_type(values)))
    return out


def beside(rows, days: Sequence[date]) -> Dict[str, Dict[str, Optional[float]]]:
    """ON RRP and facility take-up ($bn), monthly medians over `days`, reported beside the buffer and never filtered."""
    by_day = {row.date: row.values for row in rows}
    months: Dict[str, Dict[str, List[float]]] = {}
    for day in days:
        values = by_day[day]
        month = months.setdefault(day.strftime("%Y-%m"), {"on_rrp_bn": [], "srf_take_up_bn": []})
        for key, column in (("on_rrp_bn", "on_rrp"), ("srf_take_up_bn", "srf_take_up")):
            if values.get(column) is not None:
                month[key].append(values[column])

    def median(v):
        if not v:
            return None
        v = sorted(v)
        mid = len(v) // 2
        return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 3)

    return {m: {k: median(v) for k, v in cols.items()} for m, cols in sorted(months.items())}
