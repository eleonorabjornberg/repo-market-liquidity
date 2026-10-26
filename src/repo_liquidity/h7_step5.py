"""H7m, development step 5: the three goalposts on development days (`docs/stages/h7-step5.md`, directive #178).

Pure functions over a window of days, the estimators' daily records and the parent's R and S. Nothing is fitted and nothing is
decided: a reading is a point with a 90% bootstrap interval, placed against the MME in words, beside its splits. The deciding
statistic is protocol section 5's, `goalposts.stratified_gain`; the bootstrap is `goalposts.bootstrap_gains` on the parent's
`stationary_bootstrap_indices`; the AUROC is `deployable.auc` (ranked low to high, ties half). R and S are the parent's, read by
`h7_estimator.asof_days`; the estimates are the account's (`results/h7/distribution-account.json`).

An AUROC is a gain over a constant score (which scores exactly one half), so the same tested bootstrap serves the benchmarks' own
scores.
"""

from __future__ import annotations

import random
import statistics
from datetime import date
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import numpy as np
from repo_model import scoring_protocol
from repo_model.data import next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError

from repo_liquidity import goalposts as gp
from repo_liquidity import h7_account

#: The development seed of the resamples; a split's seed is this plus its position in the split list (`h7-step5.md` section 3).
SEED = 20261024
#: The parent's draws (`scoring_protocol.DRAWS`, 10,000) and mean block length (10), protocol section 6.
DRAWS = scoring_protocol.DRAWS
BLOCK_LENGTH = gp.BLOCK_LENGTH
#: The interval is the one-sided 95% lower bound (section 6) and the one-sided 95% upper bound (`goalposts.FUTILITY_LEVEL`).
LOWER_LEVEL = 0.05
UPPER_LEVEL = 1.0 - gp.FUTILITY_LEVEL
MME = gp.MME
EVENT_FLOOR = gp.EVENT_FLOOR
WIDTH_LIMIT_POINTS = 3.0
SERVING_LAG = h7_account.SERVING_LAG
#: The account's per-day columns are points of bank assets; R is a share.
POINTS = 100.0
#: The last day any record serves; the records' fits end here (`h7-step5.md`, Q5).
LAST_DAY = date(2025, 12, 31)

GOALPOST_ONE_C = "unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6)"
GOALPOST_ONE_A = "as in A's restated record (results/h7/kink.json)"
DAY_TYPES = ("quarter_end", "month_end", "tax_date", "ordinary")
ERA_FROM = date(2021, 1, 1)
SPLIT_KINDS = ("all", "regime", "day_type", "era")


class Window(NamedTuple):
    """The scored days, each with the parent's R and S at its decision instant and its material-use event."""

    days: List[date]
    ratio: List[float]
    state: List[float]
    event: List[int]


class Estimates(NamedTuple):
    """One estimator on the window: its estimate as a share (None where it serves no day), its 90% interval's width in points
    (None where it has none), and the window positions it serves."""

    estimate: List[Optional[float]]
    width: List[Optional[float]]
    served: List[int]


class Reading(NamedTuple):
    """An AUROC or a gain, in AUROC points, with its 90% interval; the events in the strata it used, the strata used and dropped."""

    point: float
    lower: float
    upper: float
    events: int
    strata: int
    dropped: int


# -- guards -----------------------------------------------------------------------------------------------------------------


def check_cutoffs(daily: Mapping) -> None:
    """Refuse an estimate read for a day before its refit's serving day (the second business day after the refit's cutoff).

    Raises:
        LookAheadError: a day in the record is earlier than the serving day of the refit that made its estimate.
    """
    for day, cutoff in zip(daily["days"], daily["cutoff"]):
        served, made = date.fromisoformat(day), date.fromisoformat(cutoff)
        first = next_business_day(made, SERVING_LAG)
        if served < first:
            raise LookAheadError(f"an estimate is read for {served}, made by the refit at {made}, before its serving day {first}")


def check_window(days: Sequence[date], *, last_day: date = LAST_DAY) -> None:
    """Refuse a window day after the records' window or in a locked tier of the parent's lockbox.

    Raises:
        LookAheadError: a day is after `last_day`, or is locked.
    """
    from repo_liquidity import development

    late = [d for d in days if d > last_day]
    if late:
        raise LookAheadError(f"step 5 reads no day after {last_day}; got {min(late)}")
    locked = [d for d in days if development.is_locked(d)]
    if locked:
        raise LookAheadError(f"step 5 scores no locked day (docs/decisions/lockbox.md); got {min(locked)}")


# -- reading an estimator's record --------------------------------------------------------------------------------------------


def align(daily: Mapping, window_days: Sequence[date]) -> Estimates:
    """The account's `as_observed` aggregate and interval on the window: a share, and a width in points, per window day.

    A window day the record does not serve is None. The record's columns are points of bank assets, rounded to four places.

    Raises:
        LookAheadError: a served day is before its refit's serving day.
        ValueError: a served day is not a window day.
    """
    check_cutoffs(daily)
    position = {d: i for i, d in enumerate(window_days)}
    n = len(window_days)
    estimate: List[Optional[float]] = [None] * n
    width: List[Optional[float]] = [None] * n
    served: List[int] = []
    column = daily["as_observed"]
    for i, day in enumerate(daily["days"]):
        when = date.fromisoformat(day)
        if when not in position:
            raise ValueError(f"the record serves {when}, which is not a day of the window")
        j = position[when]
        aggregate, lower, upper = column["aggregate"][i], column["lower"][i], column["upper"][i]
        if aggregate is None:
            continue
        estimate[j] = aggregate / POINTS
        width[j] = None if lower is None or upper is None else upper - lower
        served.append(j)
    return Estimates(estimate, width, sorted(served))


# -- the readings ---------------------------------------------------------------------------------------------------------------


def draw_indices(n: int, draws: int, seed: int) -> List[Tuple[int, ...]]:
    """`draws` stationary-bootstrap resamples of `range(n)`, mean block `BLOCK_LENGTH`, from `seed`."""
    rng = random.Random(seed)
    return [stationary_bootstrap_indices(n, BLOCK_LENGTH, rng) for _ in range(draws)]


def _interval(draws: np.ndarray) -> Tuple[float, float]:
    return float(np.quantile(draws, LOWER_LEVEL)), float(np.quantile(draws, UPPER_LEVEL))


def _gain(estimate: Sequence[Optional[float]], benchmark: Sequence[float], state: Sequence[float], event: Sequence[int],
          indices: Sequence[Sequence[int]]) -> Reading:
    """The section 5 statistic (`goalposts.stratified_gain`) with the 5th and 95th percentiles of its resamples."""
    if not len(benchmark):
        return Reading(0.0, 0.0, 0.0, 0, 0, 0)
    point = gp.stratified_gain(estimate, benchmark, state, event)
    lower, upper = _interval(gp.bootstrap_gains(estimate, benchmark, state, event, indices))
    return Reading(point.value, lower, upper, point.events, point.strata, point.dropped)


def own_auroc(score: Sequence[float], state: Sequence[float], event: Sequence[int],
              indices: Sequence[Sequence[int]]) -> Reading:
    """The AUROC of `score` (ranked low to high), pooled over the levels of `state` by events; a constant `state` is unstratified.

    A constant scores exactly one half, so the AUROC is one half plus the gain over a constant score. With no event or no other
    day in any level it is one half, over no events.
    """
    flat = [0.0] * len(score)
    g = _gain(score, flat, state, event, indices)
    return Reading(0.5 + g.point, 0.5 + g.lower, 0.5 + g.upper, g.events, g.strata, g.dropped)


def readings(window: Window, estimate: Sequence[Optional[float]], indices: Sequence[Sequence[int]], *,
             served_indices: Optional[Sequence[Sequence[int]]] = None) -> Dict[str, Reading]:
    """The information gain against R, against S and against R+S (`h7-step5.md` section 3), with intervals.

    * `vs_r`: AUROC(estimate) minus AUROC(R) over all days; a missing estimate takes R (protocol section 11).
    * `vs_rs`: the section 5 statistic, stratified by S; a missing estimate takes R.
    * `vs_s`: AUROC(estimate) minus AUROC(-S) over the days the estimator serves (S ranked high-state-is-stress); the resamples
      `served_indices` are over those days (`indices` if the estimator serves every day).
    """
    n = len(window.ratio)
    flat = [0.0] * n
    served = [i for i, e in enumerate(estimate) if e is not None]
    out = {"vs_r": _gain(estimate, window.ratio, flat, window.event, indices),
           "vs_rs": _gain(estimate, window.ratio, window.state, window.event, indices)}
    if len(served) == n:
        use = indices
    elif served and served_indices is None:
        raise ValueError(f"{len(served)} of {n} days are served: resamples over the served days are needed for the gain against S")
    else:
        use = served_indices if served_indices is not None else []
    out["vs_s"] = _gain([estimate[i] for i in served], [-window.state[i] for i in served], [0.0] * len(served),
                        [window.event[i] for i in served], use)
    return out


def position(reading: Reading, mme: float = MME) -> str:
    """Where the interval sits against the MME, in words. It is never a pass or a fail."""
    if reading.lower >= mme:
        return "at or above the MME"
    if reading.upper < mme:
        return "below the MME"
    return "straddles the MME"


def reading_row(reading: Reading) -> Dict[str, object]:
    row: Dict[str, object] = dict(reading._asdict())
    row["position"] = position(reading)
    return row


# -- goalposts 1 and 2 ------------------------------------------------------------------------------------------------------------


def width_reading(widths: Sequence[Optional[float]], *, limit: float = WIDTH_LIMIT_POINTS) -> Dict[str, object]:
    """Goalpost 2's median width in points, with a missing day counted as over the bar (sections 4 and 11), and beside it the
    median over the days that have an interval. The bar is strict. Words only: "under the bar" or "not under the bar"."""
    filled = [float("inf") if w is None else w for w in widths]
    served = [w for w in widths if w is not None]
    median = statistics.median(filled) if filled else float("inf")
    served_median = statistics.median(served) if served else None
    return {"limit_points": limit, "days": len(widths), "missing": len(widths) - len(served),
            "median_points": None if median == float("inf") else median,
            "position": "under the bar" if median < limit else "not under the bar",
            "served_median_points": served_median,
            "served_position": None if served_median is None else ("under the bar" if served_median < limit else "not under the bar")}


def goalpost_one_a(recorded: Mapping) -> Dict[str, object]:
    """A's goalpost 1 as its restated record has it. Nothing is recomputed (#166)."""
    return {"reading": GOALPOST_ONE_A, "recorded": dict(recorded)}


def goalpost_one_c() -> Dict[str, object]:
    """C's goalpost 1: unreadable on development data, read prospectively. Never computed, never a pass or a fail."""
    return {"reading": GOALPOST_ONE_C}


# -- the splits -------------------------------------------------------------------------------------------------------------------


def splits(days: Sequence[date], regimes: Sequence[str], types: Sequence[str]) -> Dict[Tuple[str, str], List[int]]:
    """The pooled window, then each declared regime, each pressure-day type and the days from 2021 (the standing-facility split),
    as window positions. The regimes and the types each partition the window; an empty split is left out.

    Raises:
        ValueError: the columns differ in length.
    """
    if not len(days) == len(regimes) == len(types):
        raise ValueError(f"{len(days)} days, {len(regimes)} regimes and {len(types)} day types differ in length")
    out: Dict[Tuple[str, str], List[int]] = {("all", "all"): list(range(len(days)))}
    for label in dict.fromkeys(regimes):
        out[("regime", label)] = [i for i, r in enumerate(regimes) if r == label]
    present = set(types)
    for label in DAY_TYPES:
        if label in present:
            out[("day_type", label)] = [i for i, t in enumerate(types) if t == label]
    unknown = present - set(DAY_TYPES)
    if unknown:
        raise ValueError(f"unknown pressure-day types {sorted(unknown)}")
    era = [i for i, d in enumerate(days) if d >= ERA_FROM]
    if era:
        out[("era", "2021 on")] = era
    return out


def _label(key: Tuple[str, str]) -> str:
    return f"{key[0]}: {key[1]}"


# -- the whole record -------------------------------------------------------------------------------------------------------------


def _take(values: Sequence, positions: Sequence[int]) -> List:
    return [values[i] for i in positions]


def score_all(window: Window, regimes: Sequence[str], types: Sequence[str], estimates: Mapping[str, Estimates], *, draws: int,
              seed: int, reasons: Mapping[str, str]) -> Dict[str, object]:
    """Every estimator's goalposts 2 and 3, and R, S and R+S, on the window and on every split.

    `reasons` gives a not-scorable estimator's reason from the records. The resamples of a split are drawn once from
    `seed + the split's position` and shared by every estimator on its days; the gain against S is bootstrapped over the days an
    estimator serves, from the same seed. Goalpost 1 is not computed here (it is read from the records by the script).
    """
    keys = list(splits(window.days, regimes, types))
    by_key = splits(window.days, regimes, types)
    cache: Dict[Tuple[int, int], List[Tuple[int, ...]]] = {}

    def resamples(position_: int, n: int) -> List[Tuple[int, ...]]:
        if (position_, n) not in cache:
            cache[(position_, n)] = draw_indices(n, draws, seed + position_)
        return cache[(position_, n)]

    split_rows: Dict[str, object] = {}
    benchmarks: Dict[str, Dict[str, object]] = {"R": {}, "S": {}, "R+S": {}}
    for p, key in enumerate(keys):
        rows = by_key[key]
        ratio, state, event = (_take(window.ratio, rows), _take(window.state, rows), _take(window.event, rows))
        events = sum(event)
        split_rows[_label(key)] = {"kind": key[0], "label": key[1], "days": len(rows), "events": events,
                                   "under_event_floor": events < EVENT_FLOOR,
                                   "first_day": window.days[rows[0]].isoformat(), "last_day": window.days[rows[-1]].isoformat()}
        idx = resamples(p, len(rows))
        flat = [0.0] * len(rows)
        benchmarks["R"][_label(key)] = own_auroc(ratio, flat, event, idx)._asdict()
        benchmarks["S"][_label(key)] = own_auroc([-s for s in state], flat, event, idx)._asdict()
        benchmarks["R+S"][_label(key)] = own_auroc(ratio, state, event, idx)._asdict()

    out_estimators: Dict[str, object] = {}
    n_window = len(window.days)
    for name, est in estimates.items():
        missing = n_window - len(est.served)
        if not est.served:
            out_estimators[name] = {"status": "not scorable", "served_days": 0, "missing_days": missing, "missing_share": 1.0,
                                    "reason": reasons.get(name, "it serves no day of the window")}
            continue
        gp2: Dict[str, object] = {}
        gp3: Dict[str, Dict[str, object]] = {"vs_r": {}, "vs_s": {}, "vs_rs": {}}
        served_set = set(est.served)
        for p, key in enumerate(keys):
            rows = by_key[key]
            gp2[_label(key)] = width_reading(_take(est.width, rows))
            sub_est = _take(est.estimate, rows)
            kept = [j for j, i in enumerate(rows) if i in served_set]
            sub = Window([window.days[i] for i in rows], _take(window.ratio, rows), _take(window.state, rows),
                         _take(window.event, rows))
            got = readings(sub, sub_est, resamples(p, len(rows)), served_indices=resamples(p, len(kept)) if kept else None)
            for kind, reading in got.items():
                gp3[kind][_label(key)] = reading_row(reading)
        out_estimators[name] = {"status": "scored", "served_days": len(est.served), "missing_days": missing,
                                "missing_share": missing / n_window, "goalpost_2": gp2, "goalpost_3": gp3}
    return {"splits": split_rows, "benchmarks": benchmarks, "estimators": out_estimators}


# -- a synthetic window of the real size, for the timing --------------------------------------------------------------------------


def synthetic_window(n: int, events: int, *, seed: int) -> Window:
    """A synthetic window of `n` days with exactly `events` events and the four S levels, to time the bootstrap before any real
    day is scored."""
    rng = random.Random(seed)
    days = [date(2020, 3, 17)]
    while len(days) < n:
        days.append(next_business_day(days[-1], 1))
    ratio = [0.12 + rng.gauss(0.0, 0.02) for _ in range(n)]
    order = sorted(range(n), key=lambda i: ratio[i])
    state = [0.0] * n
    for rank, i in enumerate(order):
        state[i] = float(min(3, int(4 * (n - rank) / n)))
    chosen = set(rng.sample(range(n), events))
    return Window(days, ratio, state, [int(i in chosen) for i in range(n)])
