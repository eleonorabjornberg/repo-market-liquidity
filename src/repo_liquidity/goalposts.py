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
    return InformationTest(point.value, lower, upper, level, draws, point.events, point.strata, point.dropped)


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
    if test.lower > 0.0 and test.point >= mme and test.events >= floor:
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


def calibrate(target: float, ratio: Sequence[float], state: Sequence[float], event: Sequence[int], *, sigma: float,
              seed: int, tolerance: float = 1e-5) -> Optional[float]:
    """The shift `c` whose planted estimate has the §5 gain `target` on these days, by bisection; None if unreachable."""
    if target == 0.0:
        return 0.0

    def gain(c: float) -> float:
        return stratified_gain(plant(ratio, event, c, sigma=sigma, seed=seed), ratio, state, event).value

    low, high = 0.0, SHIFT_MAX
    if gain(high) < target:
        return None
    for _ in range(80):
        middle = 0.5 * (low + high)
        if gain(middle) < target:
            low = middle
        else:
            high = middle
        if high - low < tolerance:
            break
    return 0.5 * (low + high)


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


def days_to_events(event: Sequence[int], start: int, *, floor: int = EVENT_FLOOR) -> Optional[int]:
    """The days from `start` (inclusive) until `floor` events have been logged, or None if the series ends first."""
    seen = 0
    for offset, value in enumerate(event[start:], start=1):
        seen += value
        if seen >= floor:
            return offset
    return None


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
