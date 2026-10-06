"""Stage 3: the latent buffer, filtered by an extended Kalman filter (`docs/stages/stage-3.md`).

State: the desired buffer B_t, in units of the reserves ratio. It drifts (variance q per business day) and may jump on
a reform date (variance q + j). Four heads observe it, each y = a + b * f(B) + e with e ~ N(0, r):

0. the corridor position, f = g = softplus(B - x) at scale `SCALE`;
1. SOFR dispersion (p75 - p25, bp), f = g;
2. ON RRP take-up, log(1 + $bn), f = D = x - B;
3. standing repo facility take-up, log(1 + $bn), f = g; missing before the facility.

x is the reserves ratio known at the day's decision instant. Missing observations are skipped. Parameters by maximum
likelihood (statsmodels `GenericLikelihoodModel`, the `state-space` extra). Filtered estimates only: nothing here
smooths. A forecast for day T uses the filter through T - 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import List, NamedTuple, Optional, Sequence, Tuple

#: The smooth kink's scale, in units of the ratio (`docs/stages/stage-3.md`).
SCALE = 0.005
HEADS = ("corridor_position", "sofr_dispersion_bp", "log_on_rrp", "log_srf")
#: Heads that read the scarcity g; the rest read deployable liquidity D.
SCARCITY_HEADS = (0, 1, 3)
INITIAL_VARIANCE = 0.02 ** 2
PARAM_NAMES = ("b0", "q", "j") + tuple(
    f"{kind}_{head}" for head in HEADS for kind in ("a", "b", "r"))
#: Bounds (`docs/stages/stage-3.md`, estimation): the buffer between 0 and 30% of bank assets, a daily drift of at most
#: 0.2 points, a jump of at most 5 points, and each slope with the sign the model states. The optimizer works on
#: unconstrained values; `natural` maps them.
BUFFER_MAX = 0.30
DRIFT_SD_MAX = 0.002
JUMP_SD_MAX = 0.05


class Observation(NamedTuple):
    day: date
    x: float
    y: Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]


class State(NamedTuple):
    day: date
    mean: float
    variance: float


@dataclass(frozen=True)
class Fit:
    params: Tuple[float, ...]
    loglike: float
    converged: bool
    cutoff: date
    scale: float


def softplus(z: float, scale: float) -> float:
    """scale * log(1 + exp(z / scale)), stable at both ends."""
    u = z / scale
    if u > 30:
        return z
    if u < -30:
        return 0.0
    return scale * math.log1p(math.exp(u))


def _sigmoid(u: float) -> float:
    if u >= 0:
        return 1.0 / (1.0 + math.exp(-u))
    e = math.exp(u)
    return e / (1.0 + e)


def natural(params: Sequence[float]) -> Tuple[float, ...]:
    """Unconstrained optimizer values to (b0, q, j, a_i, b_i, r_i ...): bounded, slopes positive, variances positive."""
    out = [BUFFER_MAX * _sigmoid(params[0]), (DRIFT_SD_MAX * _sigmoid(params[1])) ** 2,
           (JUMP_SD_MAX * _sigmoid(params[2])) ** 2]
    for i in range(4):
        a, b, r = params[3 + 3 * i], params[4 + 3 * i], params[5 + 3 * i]
        out += [a, math.exp(b), math.exp(r)]
    return tuple(out)


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def unconstrained(values: Sequence[float]) -> Tuple[float, ...]:
    """The inverse of `natural`."""
    out = [_logit(values[0] / BUFFER_MAX), _logit(math.sqrt(values[1]) / DRIFT_SD_MAX),
           _logit(math.sqrt(values[2]) / JUMP_SD_MAX)]
    for i in range(4):
        out += [values[3 + 3 * i], math.log(values[4 + 3 * i]), math.log(values[5 + 3 * i])]
    return tuple(out)


def _run(observations: Sequence[Observation], params: Sequence[float], jump_days, scale: float, keep: bool):
    values = natural(params)
    b, q, j = values[0], values[1], values[2]
    heads = [(values[3 + 3 * i], values[4 + 3 * i], values[5 + 3 * i]) for i in range(4)]
    jumps = set(jump_days)
    mean, variance = b, INITIAL_VARIANCE
    loglike = 0.0
    path: List[State] = []
    for index, obs in enumerate(observations):
        if index > 0:
            variance += q + (j if obs.day in jumps else 0.0)
        for i, value in enumerate(obs.y):
            if value is None:
                continue
            a, slope, r = heads[i]
            if i in SCARCITY_HEADS:
                f = softplus(mean - obs.x, scale)
                df = _sigmoid((mean - obs.x) / scale)
            else:
                f = obs.x - mean
                df = -1.0
            h = slope * df
            s = h * h * variance + r
            v = value - (a + slope * f)
            gain = variance * h / s
            mean += gain * v
            variance *= (1.0 - gain * h)
            loglike += -0.5 * (math.log(2 * math.pi * s) + v * v / s)
        if keep:
            path.append(State(obs.day, mean, variance))
    return loglike, path


def loglike(observations, params, *, jump_days, scale: float = SCALE) -> float:
    return _run(observations, params, jump_days, scale, keep=False)[0]


def filter_path(observations, params, *, jump_days, scale: float = SCALE) -> List[State]:
    """The filtered state B_t|t for every observation day (never smoothed)."""
    return _run(observations, params, jump_days, scale, keep=True)[1]


def require_before(observations: Sequence[Observation], cutoff: date) -> None:
    """Refuse observations dated after a refit's cutoff.

    Recorded mutation (6 October 2026): replacing the body's `if late:` with `if False:` makes
    `test_latent.GuardTests.test_a_fit_given_an_observation_after_its_cutoff_is_refused` fail with
    AssertionError: LookAheadError not raised.

    Raises:
        LookAheadError: naming the first late day.
    """
    from repo_model.splits import LookAheadError

    late = [obs.day for obs in observations if obs.day > cutoff]
    if late:
        raise LookAheadError(f"a refit with cutoff {cutoff} was given an observation dated {late[0]}")


def start_params(observations: Sequence[Observation]) -> Tuple[float, ...]:
    """Data-scaled starting values (unconstrained): each head's mean and spread, a buffer at the median ratio."""
    xs = sorted(obs.x for obs in observations)
    values = [xs[len(xs) // 2], 0.0003 ** 2, 0.01 ** 2]
    for i in range(4):
        ys = [obs.y[i] for obs in observations if obs.y[i] is not None]
        if not ys:
            values += [0.0, 1.0, 1.0]
            continue
        m = sum(ys) / len(ys)
        sd = math.sqrt(sum((v - m) ** 2 for v in ys) / max(len(ys) - 1, 1)) or 1.0
        values += [m, sd / 0.02, (0.5 * sd) ** 2]
    return unconstrained(values)


def fit(observations: Sequence[Observation], *, jump_days, cutoff: date, scale: float = SCALE,
        start: Optional[Sequence[float]] = None, maxiter: int = 400) -> Fit:
    """Maximum-likelihood parameters on observations up to `cutoff` (statsmodels GenericLikelihoodModel)."""
    import numpy as np
    from statsmodels.base.model import GenericLikelihoodModel

    require_before(observations, cutoff)
    observations = list(observations)

    class _Model(GenericLikelihoodModel):
        def loglike(self, params):
            value = loglike(observations, params, jump_days=jump_days, scale=scale)
            return value if math.isfinite(value) else -1e12

    model = _Model(endog=np.zeros(len(observations)), exog=np.ones((len(observations), 1)))
    model.exog_names[:] = ["const"]
    begin = np.asarray(start if start is not None else start_params(observations), dtype=float)
    result = model.fit(start_params=begin, method="nm", maxiter=maxiter, disp=0)
    result = model.fit(start_params=result.params, method="bfgs", maxiter=maxiter, disp=0)
    params = tuple(float(v) for v in result.params)  # unconstrained; `natural(params)` for reporting
    converged = bool(result.mle_retvals.get("converged", False))
    return Fit(params=params, loglike=loglike(observations, params, jump_days=jump_days, scale=scale),
               converged=converged, cutoff=cutoff, scale=scale)


def forecast_state(path: Sequence[State], days: Sequence[date], target: date) -> State:
    """The state a forecast for `target` may read: the filter through the panel day two before it.

    Raises:
        LookAheadError: if no such state exists in `path`.
    """
    from repo_model.splits import LookAheadError

    position = days.index(target)
    if position < 2:
        raise LookAheadError(f"no state is public before {target}'s decision instant")
    wanted = days[position - 2]
    for state in path:
        if state.day == wanted:
            return state
    raise LookAheadError(f"the path has no state for {wanted}")


def assemble(rows) -> List[Observation]:
    """Stage 3's observations from the Phase 3 panel rows, to 2025-12-31.

    x is the reserves ratio known at each day's decision instant and the corridor position uses the ON RRP rate in
    force that day, both from Stage 2's `demand_curve.sample`. The other heads are the day's own published values:
    SOFR's 75th minus 25th percentile, and ON RRP and facility take-up (missing before the facility).
    """
    from repo_liquidity import demand_curve

    by_day = {row.date: row.values for row in rows}
    out = []
    for day in demand_curve.sample(rows):
        values = by_day[day.day]
        p25, p75 = values.get("sofr_p25"), values.get("sofr_p75")
        on_rrp, srf = values.get("on_rrp"), values.get("srf_take_up")
        out.append(Observation(day.day, day.ratio, (
            day.corridor,
            None if p25 is None or p75 is None else round(100.0 * (p75 - p25), 6),
            None if on_rrp is None else math.log1p(max(on_rrp, 0.0)),
            None if srf is None else math.log1p(max(srf, 0.0)),
        )))
    return out


def jump_days(observations: Sequence[Observation], reform_dates: Sequence[date]) -> List[date]:
    """Each reform date mapped to the first observation day on or after it."""
    days = [obs.day for obs in observations]
    out = []
    for when in reform_dates:
        later = [day for day in days if day >= when]
        if later:
            out.append(later[0])
    return out
