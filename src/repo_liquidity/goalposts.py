"""H7m, groundwork G6: the three goalposts, the test, the verdict and the power study's building blocks.

`docs/decisions/measurement-protocol.md` v1 decides everything here (§3 goalpost 1, §4 goalpost 2, §5 goalpost 3, §6 the
test, §9 the verdict and the spending, §11 missing data); `docs/stages/h7-g6.md` declares what the protocol leaves to the
power study. Nothing is scored: a candidate estimator is never imported here. R and S are the parent's
(`repo_model.scarcity`, read by `h7_estimator.asof_days` through `repo_model.asof.InformationRule`), the stationary
bootstrap is the parent's (`repo_model.metrics.stationary_bootstrap_indices`), and the nominal levels, the draws and the
verdict names are the parent's scoring protocol (`repo_model.scoring_protocol`). None is rebuilt.

Ranking is low to high: an event is expected to sit low, so a concordant (event, other) pair has the event's estimate
below the other's, ties counting half (`deployable.auc`).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, Iterator, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import numpy as np
from repo_model import scoring_protocol
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError

from repo_liquidity import deployable
from repo_liquidity.h7_estimator import Day

#: §3: every served day's gap between refit k and k - 1 strictly under this, in shares of bank assets (0.5 points).
STABILITY_LIMIT = deployable.STABILITY_LIMIT
#: §4: the median width of the 90% interval strictly under this (3 points).
WIDTH_LIMIT = deployable.WIDTH_LIMIT
#: §5: the minimum meaningful effect, in AUROC points. The power study checks that it is detectable.
MME = 0.05
#: §9: the one-sided level of the upper bound a "killed" verdict is read at: the 95% bound, mirroring the lower bound
#: (marked question Q4, decided by Eleonora on 15 Oct 2026).
FUTILITY_LEVEL = 0.05
#: §9: at least this many stress events must have been logged for a "supported" verdict.
EVENT_FLOOR = 10
#: §11: more than this share of missing days voids a registration.
MISSING_LIMIT = 0.05
#: §6: the stationary bootstrap's mean block length, in business days (the parent's).
BLOCK_LENGTH = scoring_protocol.BLOCK_LENGTH
#: §9: the looks, in confirmation days (the parent's).
LOOKS = scoring_protocol.CHECKPOINTS
#: The last day the development panel holds (the parent's lockbox, `docs/decisions/lockbox.md`).
DEVELOPMENT_END = date(2026, 9, 3)
#: The first day a material-use event can occur (`deployable.EVENTS_FROM`).
EVENTS_FROM = deployable.EVENTS_FROM
#: The material-use event: the Fed's repo operations accepted on the day, USD billions, at or above this
#: (`docs/decisions/data-meaning.md`, answer 14).
MATERIAL_USE_BN = 1.0
#: `docs/stages/h7-g6.md` §5: the standard deviation of the tie-breaking noise, in units of sigma (the sd of R).
NOISE_SD = 0.1
#: The largest shift, in units of sigma, the calibration tries.
SHIFT_MAX = 20.0
#: `docs/stages/h7-g6.md` §4: the study's seed; a window's seed is this plus the window's first index.
STUDY_SEED = 20261014
#: `docs/stages/h7-g6.md` §5: a calibrated planting's realised gain is within this of its target, or the target is refused.
CALIBRATION_TOLERANCE = 1e-4
_CHUNK = 5000


# -- goalposts 1 and 2 ------------------------------------------------------------------------------------------------


def stability_goalpost(gaps: Mapping[date, float], missing_refits: int = 0, *, limit: float = STABILITY_LIMIT) -> Dict:
    """§3 and §11. Holds only if every gap is strictly under `limit` and no scheduled refit is missing.

    A missing refit, or one that did not converge, is a breach: there is no fallback.
    """
    breaches = sum(gap >= limit for gap in gaps.values())
    worst = max(gaps.items(), key=lambda item: item[1]) if gaps else None
    return {"holds": breaches == 0 and missing_refits == 0, "limit": limit, "days_compared": len(gaps),
            "breaches": breaches, "missing_refits": missing_refits,
            "worst": None if worst is None else {"day": worst[0], "gap": worst[1]}}


def sharpness_goalpost(widths: Sequence[Optional[float]], *, limit: float = WIDTH_LIMIT) -> Dict:
    """§4 and §11. The median width of the daily 90% interval is strictly under `limit`; a missing day counts as over it."""
    if not widths:
        return {"holds": False, "limit": limit, "days": 0, "missing": 0, "median": None}
    filled = [math.inf if width is None else width for width in widths]
    median = statistics.median(filled)
    return {"holds": median < limit, "limit": limit, "days": len(filled), "missing": sum(w is None for w in widths),
            "median": median}


# -- goalpost 3: the statistic (§5) -----------------------------------------------------------------------------------


class Gain(NamedTuple):
    """The stratified AUROC of an estimate minus R's, pooled by events; strata used and dropped; events in the used ones."""

    value: float
    strata: int
    dropped: int
    events: int


def _check(*columns: Sequence) -> None:
    if len({len(column) for column in columns}) != 1:
        raise ValueError(f"the columns have different lengths: {[len(column) for column in columns]}")


def stratified_gain(estimate: Sequence[Optional[float]], ratio: Sequence[float], state: Sequence[float],
                    event: Sequence[int]) -> Gain:
    """§5: within each S level, AUROC(estimate) minus AUROC(R) for separating event days; the levels pooled by events.

    A missing estimate (None) is R on that day (§11), so it cannot gain. A level with no event or no other day is dropped
    and counted. With nothing to compare the gain is 0.0.

    Raises:
        ValueError: if the columns differ in length.
    """
    _check(estimate, ratio, state, event)
    filled = [r if e is None else e for e, r in zip(estimate, ratio)]
    weighted = events = used = dropped = 0
    for level in sorted(set(state)):
        rows = [i for i, s in enumerate(state) if s == level]
        labels = [event[i] for i in rows]
        a = deployable.auc([filled[i] for i in rows], labels)
        b = deployable.auc([ratio[i] for i in rows], labels)
        if a is None or b is None:
            dropped += 1
            continue
        count = sum(labels)
        weighted += count * (a - b)
        events += count
        used += 1
    return Gain(weighted / events if events else 0.0, used, dropped, events)


def unstratified_gain(estimate: Sequence[Optional[float]], ratio: Sequence[float], event: Sequence[int]) -> Optional[float]:
    """§5, reported and not deciding: AUROC(estimate) minus AUROC(R) over all days, or None if a class is empty."""
    _check(estimate, ratio, event)
    filled = [r if e is None else e for e, r in zip(estimate, ratio)]
    a, b = deployable.auc(filled, event), deployable.auc(ratio, event)
    return None if a is None or b is None else a - b


# -- goalpost 3: the test (§6) ----------------------------------------------------------------------------------------


def _concordance(positive: np.ndarray, other: np.ndarray) -> np.ndarray:
    """1 where an event's estimate is below another day's, 1/2 on a tie."""
    return (positive[:, None] < other[None, :]).astype(float) + 0.5 * (positive[:, None] == other[None, :])


def bootstrap_gains(estimate: Sequence[Optional[float]], ratio: Sequence[float], state: Sequence[float],
                    event: Sequence[int], indices: Iterable[Sequence[int]]) -> np.ndarray:
    """The §5 statistic on each resample of `indices` (rows resampled together), as `stratified_gain` computes it.

    Within a level the AUROC difference is a bilinear form in the resample's counts, so the draws are evaluated in
    chunks; a draw with no event or no other day in a level drops that level, as `stratified_gain` does.
    """
    _check(estimate, ratio, state, event)
    n = len(ratio)
    filled = np.array([r if e is None else e for e, r in zip(estimate, ratio)], dtype=float)
    ratio_a, state_a, event_a = np.asarray(ratio, dtype=float), np.asarray(state, dtype=float), np.asarray(event)
    blocks = []
    for level in sorted(set(state)):
        pos = np.flatnonzero((state_a == level) & (event_a == 1))
        neg = np.flatnonzero((state_a == level) & (event_a == 0))
        if len(pos) and len(neg):
            blocks.append((pos, neg, _concordance(filled[pos], filled[neg]) - _concordance(ratio_a[pos], ratio_a[neg])))
    out: List[float] = []
    iterator = iter(indices)
    while True:
        chunk = [idx for _, idx in zip(range(_CHUNK), iterator)]
        if not chunk:
            break
        counts = np.zeros((len(chunk), n))
        for row, idx in enumerate(chunk):
            counts[row] = np.bincount(np.asarray(idx), minlength=n)
        weighted = np.zeros(len(chunk))
        events = np.zeros(len(chunk))
        for pos, neg, difference in blocks:
            p, q = counts[:, pos], counts[:, neg]
            total_p, total_q = p.sum(axis=1), q.sum(axis=1)
            live = (total_p > 0) & (total_q > 0)
            numerator = ((p @ difference) * q).sum(axis=1)
            weighted += np.where(live, numerator / np.where(live, total_q, 1.0), 0.0)
            events += np.where(live, total_p, 0.0)
        out.extend(np.where(events > 0, weighted / np.where(events > 0, events, 1.0), 0.0))
    return np.array(out)


def nominal_level(look: int) -> float:
    """The one-sided level the bootstrap bound is read at, at look `look` (0-based): the parent's Lan-DeMets boundaries."""
    return scoring_protocol.nominal_levels()[look]


def draws_for(look: int) -> int:
    """The draws at a look: the parent's interim draws before the last look, its ordinary draws at the last."""
    return scoring_protocol.INTERIM_DRAWS if look < len(LOOKS) - 1 else scoring_protocol.DRAWS


@dataclass(frozen=True)
class InformationTest:
    point: float
    lower: float
    upper: Optional[float]
    level: float
    draws: int
    events: int
    strata: int
    dropped: int
    #: The events in the window, as protocol §9 ("10 stress events logged") counts them. `events` is those in usable strata.
    window_events: int


def window_seed(start: int) -> int:
    """`h7-g6.md` §4: the study's seed plus the window's first index."""
    return STUDY_SEED + start


def information_test(estimate: Sequence[Optional[float]], ratio: Sequence[float], state: Sequence[float],
                     event: Sequence[int], *, look: int, seed: int, draws: Optional[int] = None,
                     futility_level: Optional[float] = None,
                     indices: Optional[Sequence[Sequence[int]]] = None) -> InformationTest:
    """§6: the §5 statistic with its one-sided lower bound at look `look`'s nominal level (and an upper bound, if asked).

    `indices` are resamples already drawn (by `stationary_bootstrap_indices` from `seed`), so that several estimates
    over the same days can share them; `draws` is then their number.

    Raises:
        scoring_protocol.UnresolvedLevel: if `draws` cannot resolve the level (a bound needs a draw beyond it).
        ValueError: if the columns differ in length.
    """
    draws = (draws_for(look) if indices is None else len(indices)) if draws is None else draws
    level = nominal_level(look)
    for what, value in (("lower", level), ("upper", futility_level)):
        if value is not None and min(value, 1.0 - value) * draws < 1.0:
            raise scoring_protocol.UnresolvedLevel(
                f"the {what} bound at level {value:.6g} needs a draw beyond it; {draws} draws resolve no level "
                f"below {1.0 / draws:.6g}")
    point = stratified_gain(estimate, ratio, state, event)
    if indices is None:
        rng = random.Random(seed)
        indices = (stationary_bootstrap_indices(len(ratio), BLOCK_LENGTH, rng) for _ in range(draws))
    gains = bootstrap_gains(estimate, ratio, state, event, indices)
    lower = float(np.quantile(gains, level))
    upper = None if futility_level is None else float(np.quantile(gains, 1.0 - futility_level))
    return InformationTest(point.value, lower, upper, level, draws, point.events, point.strata, point.dropped,
                           sum(event))


def verdict(test: InformationTest, *, look: int, goalposts_held: bool, futility_level: float = FUTILITY_LEVEL,
            mme: float = MME, floor: int = EVENT_FLOOR) -> str:
    """§9. Supported, killed, inconclusive, or (at the last look) not shown.

    `futility_level` defaults to `FUTILITY_LEVEL`, the one-sided 95% upper bound (marked question Q4 in
    `docs/stages/h7-g6.md`, decided by Eleonora on 15 Oct 2026). `test` must have been made with an upper bound unless the verdict is settled without one.

    Raises:
        ValueError: if a kill must be judged and the test has no upper bound.
    """
    if not goalposts_held:
        return scoring_protocol.KILLED
    if test.lower > 0.0 and test.point >= mme and test.window_events >= floor:
        return scoring_protocol.SUPPORTED
    if test.upper is None:
        raise ValueError(f"no upper bound at futility level {futility_level}: it cannot be judged against the MME")
    if test.upper < mme:
        return scoring_protocol.KILLED
    return scoring_protocol.NOT_SHOWN if look == len(LOOKS) - 1 else scoring_protocol.INCONCLUSIVE


def registration_void(*, missing: int, days: int) -> bool:
    """§11: more than 5% missing days voids the registration.

    Raises:
        ValueError: if there are no days.
    """
    if days <= 0:
        raise ValueError(f"a share of missing days needs days, got {days}")
    return missing / days > MISSING_LIMIT


# -- the planted signal (`docs/stages/h7-g6.md` §5) --------------------------------------------------------------------


def sd(values: Sequence[float]) -> float:
    return statistics.pstdev(values)


def plant(ratio: Sequence[float], event: Sequence[int], c: float, *, sigma: float, seed: int) -> List[float]:
    """R plus tie-breaking noise, lowered by `c` sigma on event days."""
    rng = random.Random(seed)
    return [r + rng.gauss(0.0, NOISE_SD * sigma) - c * sigma * y for r, y in zip(ratio, event)]


class CalibrationCase(NamedTuple):
    """One series a planting is calibrated on: its columns, and the seed of its tie-breaking noise."""

    ratio: Sequence[float]
    state: Sequence[float]
    event: Sequence[int]
    seed: int


def calibrate_over(target: float, cases: Sequence[CalibrationCase], *, sigma: float, tolerance: float = 1e-9,
                   gain_tolerance: float = CALIBRATION_TOLERANCE) -> Optional[float]:
    """The shift `c` whose planted estimates have the §5 gain `target` on average over `cases`, by bisection; None if
    unreachable.

    The statistic moves in steps (a stratum with few other days moves it by whole pairs), so the bisection ends on the end
    of its last bracket nearer the target, and the shift is returned only if that mean gain is within `gain_tolerance` of
    the target (`h7-g6.md` §5).

    Raises:
        ValueError: if there are no cases, or no shift lands within `gain_tolerance` of the target.
    """
    if not cases:
        raise ValueError("a calibration needs at least one series")
    if target == 0.0:
        return 0.0

    def gain(c: float) -> float:
        return sum(stratified_gain(plant(x.ratio, x.event, c, sigma=sigma, seed=x.seed), x.ratio, x.state, x.event).value
                   for x in cases) / len(cases)

    low, high = 0.0, SHIFT_MAX
    if gain(high) < target:
        return None
    for _ in range(100):
        middle = 0.5 * (low + high)
        if gain(middle) < target:
            low = middle
        else:
            high = middle
        if high - low < tolerance:
            break
    best = min((low, high), key=lambda c: abs(gain(c) - target))
    miss = abs(gain(best) - target)
    if miss > gain_tolerance:
        raise ValueError(f"no shift plants the gain {target} to within {gain_tolerance}: the nearest, {best:.9g} sigma, "
                         f"is {miss:.3g} away")
    return best


def calibrate(target: float, ratio: Sequence[float], state: Sequence[float], event: Sequence[int], *, sigma: float,
              seed: int, tolerance: float = 1e-9, gain_tolerance: float = CALIBRATION_TOLERANCE) -> Optional[float]:
    """`calibrate_over` one series: the shift `c` whose planted estimate has the §5 gain `target` on these days."""
    return calibrate_over(target, [CalibrationCase(ratio, state, event, seed)], sigma=sigma, tolerance=tolerance,
                          gain_tolerance=gain_tolerance)


# -- windows, eras and intervals ---------------------------------------------------------------------------------------


def windows(n: int, length: int, step: int) -> List[Tuple[int, int]]:
    """`(start, end)` index pairs (end exclusive) of every window of `length` days that starts at a multiple of `step`."""
    return [(start, start + length) for start in range(0, n - length + 1, step)]


def era(day: date) -> str:
    """The era of a window's first day: to 2020, 2021-24, or 2025 on."""
    return "to 2020" if day.year <= 2020 else "2021-24" if day.year <= 2024 else "2025 on"


ERAS = ("to 2020", "2021-24", "2025 on")


def wilson(successes: float, n: float, z: float = 1.959963984540054) -> Tuple[float, float]:
    """The Wilson 95% interval for a share of `successes` in `n` (`n` may be an effective, fractional count)."""
    if n <= 0:
        raise ValueError(f"an interval needs n > 0, got {n}")
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def effective_windows(count: int, length: int, step: int) -> float:
    """Windows overlap by `length - step` days, so they carry `count * step / length` independent windows' information."""
    return min(float(count), count * step / length)


class Power(NamedTuple):
    """A supported share with its Wilson interval at the effective number of windows."""

    share: float
    low: float
    high: float
    effective: float


def power(successes: int, windows_: int, length: int, step: int) -> Power:
    """The share of `windows_` windows supported, with its 95% Wilson interval at `effective_windows`.

    Windows overlap, so the interval is taken at the information they carry, not at their number (finding #95).

    Raises:
        ValueError: if there are no windows, or more successes than windows.
    """
    if windows_ <= 0:
        raise ValueError(f"a power needs windows, got {windows_}")
    if not 0 <= successes <= windows_:
        raise ValueError(f"{successes} windows supported of {windows_}")
    effective = effective_windows(windows_, length, step)
    share = successes / windows_
    low, high = wilson(share * effective, effective)
    return Power(share, low, high, effective)


def days_to_events(event: Sequence[int], start: int, *, floor: int = EVENT_FLOOR) -> Optional[int]:
    """The days from `start` (inclusive) until `floor` events have been logged, or None if the series ends first."""
    seen = 0
    for offset, value in enumerate(event[start:], start=1):
        seen += value
        if seen >= floor:
            return offset
    return None


# -- a clustered event process (`docs/stages/h7-g6.md` §9, Part B) -----------------------------------------------------


class EventProcess(NamedTuple):
    """A two-state Markov chain on the daily event indicator: P(event | quiet day before) and P(event | event day before)."""

    start: float
    stay: float
    transitions_from_quiet: int
    transitions_from_event: int

    @property
    def stationary(self) -> float:
        """The long-run share of event days."""
        return self.start / (1.0 - self.stay + self.start)


def fit_event_process(event: Sequence[int]) -> EventProcess:
    """The chain's two probabilities as the shares of observed transitions (the maximum-likelihood fit).

    Raises:
        ValueError: if the series never leaves one of the two states (the probability is then not estimated).
    """
    pairs = list(zip(event, event[1:]))
    from_quiet = [b for a, b in pairs if a == 0]
    from_event = [b for a, b in pairs if a == 1]
    if not from_quiet or not from_event:
        raise ValueError(f"the event process needs a transition out of each state, got {len(from_quiet)} from a quiet "
                         f"day and {len(from_event)} from an event day")
    return EventProcess(sum(from_quiet) / len(from_quiet), sum(from_event) / len(from_event), len(from_quiet),
                        len(from_event))


def simulate_events(process: EventProcess, n: int, rng: random.Random) -> List[int]:
    """`n` daily event indicators from the chain, the first drawn from its stationary share."""
    out: List[int] = []
    previous = int(rng.random() < process.stationary)
    for _ in range(n):
        out.append(previous)
        previous = int(rng.random() < (process.stay if previous else process.start))
    return out


# -- the days the study reads ------------------------------------------------------------------------------------------


class LabelledDay(NamedTuple):
    day: date
    event: int
    ratio: float
    state: float


class Labelled(NamedTuple):
    days: List[LabelledDay]
    dropped: Dict[str, int]


def is_material_use(accepted_bn: float) -> bool:
    """The material-use event on a day with `accepted_bn` USD billions accepted (`data-meaning.md`, answer 14)."""
    return accepted_bn >= MATERIAL_USE_BN


def labelled_days(days: Sequence[Day], accepted: Mapping[date, Optional[float]], *, last_day: date = DEVELOPMENT_END,
                  first_day: date = EVENTS_FROM) -> Labelled:
    """The scored days from `first_day` with an event label, a ratio and a state; the others dropped and counted.

    `days` are `h7_estimator.asof_days` (R and S as the parent reads them at each decision instant); `accepted` is the
    parent's `fed_repo_accepted` by date, None where the parent has no operation row.

    Raises:
        LookAheadError: if a day is after `last_day`.
    """
    late = [d.day for d in days if d.day > last_day]
    if late:
        raise LookAheadError(f"the power study reads no day after {last_day}; got {late[0]}")
    out: List[LabelledDay] = []
    dropped = {"no label": 0, "no ratio": 0, "no state": 0}
    for d in days:
        if d.day < first_day:
            continue
        amount = accepted.get(d.day)
        if amount is None:
            dropped["no label"] += 1
        elif d.ratio is None:
            dropped["no ratio"] += 1
        elif d.state is None:
            dropped["no state"] += 1
        else:
            out.append(LabelledDay(d.day, int(is_material_use(amount)), d.ratio, d.state))
    return Labelled(out, dropped)


# -- the third record's calendar (`docs/stages/h7-g6.md` §11) -----------------------------------------------------------

#: §11.3: coupons settling on or before this day of the month are the mid-month settlement, after it the month-end one.
MID_MONTH_LAST_DAY = 20

#: §11.3: the ridge on the five slopes of the calendar-tied process (none on the intercept).
RIDGE = 1.0

#: §11.3: the fit stops when no coefficient moves by more than this, or after this many steps (an error).
FIT_TOLERANCE = 1e-10
FIT_STEPS = 100

#: The panel columns the flags are read from: the ones the parent's `repo_model.risk_dates` reads for its scheduled days.
COUPONS_COLUMN = "treasury_settlement_coupons"
QUARTER_END_COLUMN = "quarter_end"


class Calendar(NamedTuple):
    """The calendar flags of one day (§11.3), each 0 or 1. A year-end is also a quarter-end."""

    coupon_mid: int
    coupon_end: int
    quarter_end: int
    year_end: int


def calendar_flags(day: date, values: Mapping[str, Optional[float]]) -> Calendar:
    """The flags of `day` from the parent's panel row `values`.

    Raises:
        ValueError: if a calendar column is missing or empty (a hole is a data error, never a zero).
    """
    coupons, quarter_end = values.get(COUPONS_COLUMN), values.get(QUARTER_END_COLUMN)
    if coupons is None or quarter_end is None:
        raise ValueError(f"{day}: a calendar column is missing ({COUPONS_COLUMN}={coupons}, {QUARTER_END_COLUMN}={quarter_end})")
    settles = float(coupons) > 0.0
    quarter = float(quarter_end) == 1.0
    return Calendar(int(settles and day.day <= MID_MONTH_LAST_DAY), int(settles and day.day > MID_MONTH_LAST_DAY),
                    int(quarter), int(quarter and day.month == 12))


def calendar_class(flags: Calendar) -> int:
    """§11.4 option (ii): 3 for a quarter-end, else 2 for a month-end settlement, else 1 for a mid-month one, else 0."""
    if flags.quarter_end:
        return 3
    if flags.coupon_end:
        return 2
    return 1 if flags.coupon_mid else 0


def calendar_strata(state: Sequence[float], flags: Sequence[Calendar]) -> List[float]:
    """The scarcity state crossed with the calendar class (§11.4 option (ii)), one value per stratum.

    Raises:
        ValueError: if the columns differ in length.
    """
    if len(state) != len(flags):
        raise ValueError(f"{len(state)} states but {len(flags)} calendar rows")
    return [10.0 * s + calendar_class(f) for s, f in zip(state, flags)]


def independent_process(event: Sequence[int]) -> EventProcess:
    """§11.3 process 1: every day an event with the observed share, so `start == stay` and there is no memory.

    Raises:
        ValueError: if the series has no event or no quiet day.
    """
    events = sum(event)
    if not event or events == 0 or events == len(event):
        raise ValueError(f"the independent process needs both event and quiet days, got {events} events in {len(event)} days")
    share = events / len(event)
    return EventProcess(share, share, len(event) - events, events)


class CalendarProcess(NamedTuple):
    """§11.3 process 3: `logit P(E_t) = b0 + b1 E(t-1) + b2 coupon_mid + b3 coupon_end + b4 quarter_end + b5 year_end`."""

    coefficients: Tuple[float, ...]
    #: The observed share of event days in the fitting window: the state before day 0 is drawn from it.
    share: float
    days: int
    events: int
    ridge: float
    #: The consecutive pairs the fit used.
    pairs: int

    def probability(self, previous: int, flags: Calendar) -> float:
        b = self.coefficients
        z = b[0] + b[1] * previous + b[2] * flags.coupon_mid + b[3] * flags.coupon_end + b[4] * flags.quarter_end \
            + b[5] * flags.year_end
        return 1.0 / (1.0 + math.exp(-z))


def fit_calendar_process(event: Sequence[int], flags: Sequence[Calendar], *, ridge: float = RIDGE) -> CalendarProcess:
    """The penalised maximum-likelihood fit of §11.3, by Newton's method from zero, on the pairs `(t-1, t)`.

    Raises:
        ValueError: if the columns differ in length, the penalty is negative, the series has no event or no quiet day,
            or the fit has not converged after `FIT_STEPS` steps.
    """
    if len(event) != len(flags):
        raise ValueError(f"{len(event)} event days but {len(flags)} calendar rows")
    if ridge < 0.0:
        raise ValueError(f"the ridge penalty cannot be negative, got {ridge}")
    events = sum(event)
    if len(event) < 2 or events == 0 or events == len(event):
        raise ValueError(f"the calendar-tied process needs both event and quiet days, got {events} events in {len(event)} days")
    previous, today = event[:-1], event[1:]
    design = np.array([[1.0, p, f.coupon_mid, f.coupon_end, f.quarter_end, f.year_end]
                       for p, f in zip(previous, flags[1:])], dtype=float)
    y = np.asarray(today, dtype=float)
    penalised = np.array([0.0, 1.0, 1.0, 1.0, 1.0, 1.0]) * ridge
    beta = np.zeros(design.shape[1])
    for _ in range(FIT_STEPS):
        p = 1.0 / (1.0 + np.exp(-(design @ beta)))
        gradient = design.T @ (p - y) + 2.0 * penalised * beta
        hessian = (design * (p * (1.0 - p))[:, None]).T @ design + 2.0 * np.diag(penalised)
        step = np.linalg.pinv(hessian) @ gradient
        beta = beta - step
        if float(np.max(np.abs(step))) <= FIT_TOLERANCE:
            return CalendarProcess(tuple(float(b) for b in beta), events / len(event), len(event), events, ridge,
                                   len(today))
    raise ValueError(f"the calendar-tied fit has not converged after {FIT_STEPS} steps (separated data needs a penalty)")


def simulate_calendar_events(process: CalendarProcess, flags: Sequence[Calendar], rng: random.Random) -> List[int]:
    """One event indicator per day of `flags`, the state before day 0 drawn from the window's observed share (§11.3)."""
    out: List[int] = []
    previous = int(rng.random() < process.share)
    for day_flags in flags:
        previous = int(rng.random() < process.probability(previous, day_flags))
        out.append(previous)
    return out
