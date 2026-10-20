"""H7m, development: A's re-specified kink, the six declared variants (`docs/stages/h7-kink.md` with its section 7, directive #151).

Step 1's kink is the parent's `satiation.fit_level` (squares, one intercept, every training pair). A variant changes one or more of
three axes and nothing else; the baseline is the parent's fit on the same pairs, and `BASELINE` is not a new variant:

====  ==============  ===========  ==========  =================
 #    Pairs           Left side    Objective   Intercepts
====  ==============  ===========  ==========  =================
V1    calendar-clean  SOFR - IORB  squares     one
V2    all             SOFR - IORB  absolute    one
V3    all             SOFR - IORB  squares     one per width
V4    calendar-clean  SOFR - IORB  absolute    one
V5    calendar-clean  SOFR - IORB  absolute    one per width
V6    calendar-clean  EFFR - IORB  absolute    one per width
====  ==============  ===========  ==========  =================

Every variant trains only on pairs scored **after 2018-06-13** (section 7(i): the 25 bp corridor regime is left out).

* **Calendar-clean pairs.** A pair is dropped when the parent's `settlement_day` or `quarter_end_window` is 1 on its scored day
  (both read through `repo_model.asof.InformationRule` at the day's own decision instant), or when
  `repo_model.turn_days.turn_label(T)` is not `None` (section 7(ii); the label does not exist at the pin, so a real-day fit cannot
  be built until the pin moves, `parent_turn_label`). A dropped day is still served by the refit in force.
* **The regime** of a pair is the width of the corridor, IORB less the ON RRP offering rate in force, **read at announcement**:
  both rates as public at the scored day's decision instant, never at the effective date (`width_regimes`). A regime is a run of
  one width: a repeated width is a new regime. A day with no ON RRP rate has no regime and leaves the regime variants.
* **The tie rule** (finding #54) is the parent's (#747, `satiation.KINK_TIE_RTOL`), at the objective in use: grid points within
  the tolerance of the least objective that span more than one grid step make the refit **not identified**. It serves nothing, and
  is never replaced by a picked point or by the fixed 0.12.

Reads nothing but through the parent's as-of rule and the announcement-keyed tables. Nothing is scored here: `real_time_path`
returns each refit's path and its gaps, and `summarise` reads goalposts 1 and 2 (`docs/decisions/measurement-protocol.md` §3, §4).
numpy is the approved extra of `docs/decisions/dependencies.md` (Stage 4).
"""

from __future__ import annotations

import math
import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, time
from typing import Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple

import numpy as np
from repo_model import asof, data, satiation
from repo_model.announced_iorb import ANNOUNCED_CHANGE, IorbAnnouncement, announced_iorb_features
from repo_model.asof import InformationRule
from repo_model.data import DailyObservation, next_business_day
from repo_model.metrics import stationary_bootstrap_indices
from repo_model.splits import LookAheadError, SplitError

from repo_liquidity import declaration, goalposts
from repo_liquidity import h7_estimator as h7
from repo_liquidity import scheduled

#: Section 7(i): a pair is scored after this day.
TRAIN_AFTER = date(2018, 6, 13)
#: Section 2(c): a regime with fewer pairs than this at a refit leaves the refit not fitted.
REGIME_FLOOR = 50
#: Section 2(c) with 7(i): the widths in bp, in time order, once the 25 bp regime is left out. The run stops on any difference.
EXPECTED_WIDTHS: Tuple[int, ...] = (20, 15, 10, 15)
KINK_GRID = satiation.KINK_GRID
KINK_MINIMUM_PAIRS = satiation.KINK_MINIMUM_PAIRS
KINK_TIE_RTOL = satiation.KINK_TIE_RTOL
BLOCK_LENGTH, LEVEL, SEED = h7.BLOCK_LENGTH, h7.LEVEL, h7.SEED
SERVING_LAG = h7.SERVING_LAG
DECISION_TIME = time(16, 0)
#: The parent's flags the exclusion set reads (section 2(a)).
FLAG_FEATURES = ("settlement_day", "quarter_end_window")
#: The objective in use is solved to a relative distance of this from its optimum.
SOLVER_RTOL = 1e-10
_GOLDEN = (5 ** 0.5 - 1) / 2
_ITERATIONS = 64


class Variant(NamedTuple):
    id: str
    clean: bool
    left: str  # "spread" (SOFR - IORB, bp) or "effr" (EFFR - IORB, bp)
    objective: str  # "squares" or "lad"
    intercepts: str  # "one" or "regime"


BASELINE = Variant("B", False, "spread", "squares", "one")
VARIANTS: Tuple[Variant, ...] = (
    Variant("V1", True, "spread", "squares", "one"),
    Variant("V2", False, "spread", "lad", "one"),
    Variant("V3", False, "spread", "squares", "regime"),
    Variant("V4", True, "spread", "lad", "one"),
    Variant("V5", True, "spread", "lad", "regime"),
    Variant("V6", True, "effr", "lad", "regime"),
)


class KDay(NamedTuple):
    """One scored day: the ratio public at its decision instant, both left sides in bp, its width regime, and whether it is clean."""

    day: date
    ratio: Optional[float]
    spread: Optional[float]
    effr: Optional[float]
    regime: Optional[int]
    clean: bool


def left_side(x: KDay, variant: Variant) -> Optional[float]:
    return x.effr if variant.left == "effr" else x.spread


# -- the exclusion set ------------------------------------------------------------------------------------------------------


class TurnDaysUnavailable(ValueError):
    """The parent has no `turn_days.turn_label` at this pin."""


def parent_turn_label() -> Callable[[date], Optional[str]]:
    """The parent's `turn_days.turn_label` (section 7(ii)), read from the parent and never re-implemented.

    Raises:
        TurnDaysUnavailable: the parent at this pin has no such module; a real-day fit waits for the pin move (#149).
    """
    try:
        from repo_model import turn_days
    except ImportError as error:
        raise TurnDaysUnavailable(
            "repo_model.turn_days does not exist at the pinned parent commit; the fit on real days waits for the pin move (#149)"
        ) from error
    return turn_days.turn_label


class Flags(NamedTuple):
    """The parent's two flags for one scored day. `unread` marks a day the rule cannot form an information set for: it cannot be
    certified clean and leaves the days a refit fits on."""

    day: date
    settlement_day: Optional[float]
    quarter_end_window: Optional[float]
    unread: bool = False

    def dropped(self) -> bool:
        """Raises ValueError: a flag is a hole, so whether the day is a calendar day is not known."""
        if self.unread:
            return True
        if self.settlement_day is None or self.quarter_end_window is None:
            raise ValueError(f"{self.day}: a calendar flag is a hole, so whether it is a clean day is not known")
        return self.settlement_day == 1.0 or self.quarter_end_window == 1.0


def with_quarter_end_window(rows: Sequence[DailyObservation]) -> List[DailyObservation]:
    """The rows with the parent's opt-in `quarter_end_window` column, a function of the date alone (`data.quarter_end_window`)."""
    return [DailyObservation(r.date, {**r.values, "quarter_end_window": data.quarter_end_window(r.date)}) for r in rows]


def flag_rule(registry: Optional[Mapping[str, Mapping]] = None) -> InformationRule:
    """The rule that reads the two flags: the parent's, under Phase 3's registry, at 16:00 on the day before."""
    return InformationRule(declaration.registry() if registry is None else registry, FLAG_FEATURES,
                           decision_time=DECISION_TIME, horizon=1)


def check_flag_reads(info: asof.InformationSet) -> None:
    """Raises LookAheadError: a calendar or scheduled read is at any row other than the scored one."""
    for read in info.reads:
        if read.kind in (asof.KIND_CALENDAR, asof.KIND_SCHEDULED) and read.row != info.scored_index:
            raise LookAheadError(f"{read.feature!r} for the scored row {info.scored_index} was read at row {read.row}; "
                                 "a calendar flag is read at the day's own decision instant, for that day only")


def read_flags(rows: Sequence[DailyObservation], rule: InformationRule) -> Dict[date, Flags]:
    """The flags of every scored day (row `i + 1`, scored from the reads at row `i`), through `rule`.

    `rows` must carry `quarter_end_window` (`with_quarter_end_window`).

    Raises:
        LookAheadError: the rule refuses a read, or a flag is read for any day but the scored one.
        StaleReadError: a read is older than the latest value public at the decision instant.
    """
    dates = [row.date for row in rows]
    out: Dict[date, Flags] = {}
    for i in range(len(rows) - 1):
        scored = rows[i + 1]
        extended = h7._extended(dates, i)
        try:
            info = rule.information_set(extended, i + 1)
        except SplitError:
            out[scored.date] = Flags(scored.date, None, None, True)
            continue
        rule.check(extended, info)
        check_flag_reads(info)
        values = rule.observation(rows, info).values
        out[scored.date] = Flags(scored.date, values.get("settlement_day"), values.get("quarter_end_window"))
    return out


def read_turn_labels(days: Sequence[KDay], label_fn: Callable[[date], Optional[str]]) -> Dict[date, Optional[str]]:
    """The parent's turn label of every scored day, read for that day alone (section 7(ii))."""
    return {x.day: label_fn(x.day) for x in days}


def mark_clean(days: Sequence[KDay], flags: Mapping[date, Flags], turn_labels: Mapping[date, Optional[str]]) -> List[KDay]:
    """`days` with `clean` set: not dropped by either flag and not a turn day. Each day reads its own flags.

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
        out.append(x._replace(clean=bool(x.clean and not flag.dropped() and turn_labels.get(x.day) is None)))
    return out


# -- the width regimes ------------------------------------------------------------------------------------------------------


class Width(NamedTuple):
    """The corridor width in bp as public at a scored day's decision instant, and the run (regime) it belongs to."""

    width: Optional[int]
    regime: Optional[int]


class Run(NamedTuple):
    regime: int
    width: int
    first: date
    last: date
    days: int


def check_public(publication: scheduled.Publication, instant: datetime, day: date) -> None:
    """Raises LookAheadError: `publication` was announced after the decision `instant` that reads it for `day`."""
    if publication.announced_at > instant:
        raise LookAheadError(
            f"the rate effective {publication.effective} was read for {day}, but it was announced at {publication.announced_at}, "
            f"after the decision instant {instant}; a width is read at its announcement, never at its effective date"
        )


def _publication_at(publications: Sequence[scheduled.Publication], instant: datetime, day: date) -> Optional[scheduled.Publication]:
    """The latest publication made at or before `instant` and effective on or before `day`."""
    known = [p for p in publications if p.announced_at <= instant and p.effective <= day]
    if not known:
        return None
    pub = max(known, key=lambda p: (p.effective, p.announced_at))
    check_public(pub, instant, day)
    return pub


def width_regimes(rows: Sequence[DailyObservation], publications: Sequence[scheduled.Publication],
                  notes: Sequence[IorbAnnouncement], *, decision_time: time) -> Dict[date, Width]:
    """Each scored day's corridor width, IORB less the ON RRP offering rate, both as public at its decision instant.

    IORB for day T is the previous row's `iorb` plus the change announced at or before T's decision instant and effective by T
    (the parent's `announced_iorb`); the ON RRP rate is the latest publication announced by then and effective by T. The first
    row has no decision instant. A day with either rate missing has no width and no regime. A regime is a run of one width.

    Raises:
        LookAheadError: a rate was read that was announced after the decision instant.
    """
    dates = [row.date for row in rows]
    changes = announced_iorb_features(dates, notes, decision_time=decision_time)
    moment = decision_time.replace(tzinfo=None)
    out: Dict[date, Width] = {dates[0]: Width(None, None)}
    previous, regime = None, -1
    for i in range(1, len(rows)):
        instant = datetime.combine(dates[i - 1], moment)
        pub = _publication_at(publications, instant, dates[i])
        iorb, change = rows[i - 1].values.get("iorb"), changes[i][ANNOUNCED_CHANGE]
        if pub is None or iorb is None or change is None:
            out[dates[i]] = Width(None, None)
            continue
        width = int(round((float(iorb) + change / 100.0 - pub.values[0]) * 100.0))
        if width != previous:
            regime, previous = regime + 1, width
        out[dates[i]] = Width(width, regime)
    return out


def regime_table(widths: Mapping[date, Width]) -> List[Run]:
    """The regimes in time order: the width, the first and last day, the days."""
    runs: Dict[int, List] = {}
    for day in sorted(widths):
        w = widths[day]
        if w.regime is None:
            continue
        entry = runs.setdefault(w.regime, [w.width, day, day, 0])
        entry[2], entry[3] = day, entry[3] + 1
    return [Run(r, v[0], v[1], v[2], v[3]) for r, v in sorted(runs.items())]


def check_expected(table: Sequence[Run], expected: Sequence[int] = EXPECTED_WIDTHS) -> None:
    """Section 2(c): the table must be the list expected in the number of regimes and in every width.

    Raises:
        ValueError: it differs; the run stops and reports a finding rather than choosing.
    """
    got = tuple(r.width for r in table)
    if got != tuple(expected):
        raise ValueError(f"the regime table {list(got)} differs from the list expected {list(expected)}: "
                         "stop and report a finding, do not choose")


# -- the exact fits ---------------------------------------------------------------------------------------------------------


def _groups(groups: np.ndarray) -> Tuple[np.ndarray, int]:
    _, inverse = np.unique(groups, return_inverse=True)
    return inverse.reshape(-1), int(inverse.max()) + 1 if len(inverse) else 0


def _live(z: np.ndarray, inverse: np.ndarray, count: int) -> np.ndarray:
    """Whether a row of `z` has spread inside some group, so that the slope is identified."""
    live = np.zeros(z.shape[0], dtype=bool)
    for g in range(count):
        zg = z[:, inverse == g]
        if zg.shape[1] > 1:
            live |= (zg.max(axis=1) - zg.min(axis=1)) > 0.0
    return live


def _lad_profile(z: np.ndarray, y: np.ndarray, inverse: np.ndarray, count: int, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Each group's intercept (its median residual) and the objective, at slopes `b` (one per row of `z`)."""
    resid = y[None, :] - b[:, None] * z
    intercepts = np.zeros((z.shape[0], count))
    total = np.zeros(z.shape[0])
    for g in range(count):
        part = resid[:, inverse == g]
        mid = (part.shape[1] - 1) // 2
        a = np.partition(part, mid, axis=1)[:, mid]
        intercepts[:, g] = a
        total += np.abs(part - a[:, None]).sum(axis=1)
    return intercepts, total


def lad_lines(z: np.ndarray, y: np.ndarray, groups: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The exact least-absolute-deviation fit `y = a_g + b z`, `b >= 0`, one intercept per group, for each row of `z`.

    The objective after profiling out the intercepts (each group's median residual) is convex and piecewise linear in the slope,
    so a golden-section search over the slope, on a bracket doubled until the optimum is inside it, reaches the optimum to a
    relative `SOLVER_RTOL`. The boundary `b = 0` is a candidate of its own. A row with no spread of `z` inside any group is
    flat (`b = 0`).

    Returns:
        The intercepts (rows by groups, in the order of the sorted group values), the slopes and the objectives.
    """
    z, y = np.asarray(z, dtype=float), np.asarray(y, dtype=float)
    inverse, count = _groups(np.asarray(groups))
    live = _live(z, inverse, count)
    zero = np.zeros(z.shape[0])
    a0, f0 = _lad_profile(z, y, inverse, count, zero)
    span = z.max(axis=1) - z.min(axis=1)
    hi = np.where(live, 2.0 * (y.max() - y.min() + 1e-12) / np.where(span > 0, span, 1.0), 0.0)
    for _ in range(64):  # grow the bracket until the objective at its top no longer falls
        f_hi = _lad_profile(z, y, inverse, count, hi)[1]
        f_half = _lad_profile(z, y, inverse, count, hi / 2.0)[1]
        grow = live & (f_hi < f_half - SOLVER_RTOL * np.maximum(f_half, 1e-300))
        if not grow.any():
            break
        hi = np.where(grow, hi * 2.0, hi)
    lo = zero.copy()
    x1, x2 = hi - _GOLDEN * hi, _GOLDEN * hi
    f1, f2 = _lad_profile(z, y, inverse, count, x1)[1], _lad_profile(z, y, inverse, count, x2)[1]
    for _ in range(_ITERATIONS):
        left = f1 <= f2  # the minimum is in [lo, x2]
        hi = np.where(left, x2, hi)
        lo = np.where(left, lo, x1)
        new1, new2 = hi - _GOLDEN * (hi - lo), lo + _GOLDEN * (hi - lo)
        probe = np.where(left, new1, new2)
        fp = _lad_profile(z, y, inverse, count, probe)[1]
        x1, x2 = np.where(left, new1, x2), np.where(left, x1, new2)
        f1, f2 = np.where(left, fp, f2), np.where(left, f1, fp)
    b = np.where(live, (lo + hi) / 2.0, 0.0)
    a, f = _lad_profile(z, y, inverse, count, b)
    boundary = f0 <= f * (1.0 + SOLVER_RTOL)
    return np.where(boundary[:, None], a0, a), np.where(boundary, 0.0, b), np.where(boundary, f0, f)


def squares_lines(z: np.ndarray, y: np.ndarray, groups: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The least-squares fit `y = a_g + b z`, one intercept per group, for each row of `z`: the group-demeaned slope.

    The slope is **not** constrained to be non-negative (the caller skips a negative one, as the parent does); a row with no
    spread of `z` inside any group has slope 0. Returns the intercepts, the slopes and the sums of squares.
    """
    z, y = np.asarray(z, dtype=float), np.asarray(y, dtype=float)
    inverse, count = _groups(np.asarray(groups))
    zc, yc = np.empty_like(z), np.empty_like(y)
    z_mean, y_mean = np.empty((z.shape[0], count)), np.empty(count)
    for g in range(count):
        mask = inverse == g
        z_mean[:, g] = z[:, mask].mean(axis=1)
        y_mean[g] = y[mask].mean()
        zc[:, mask] = z[:, mask] - z_mean[:, [g]]
        yc[mask] = y[mask] - y_mean[g]
    sxx = (zc * zc).sum(axis=1)
    live = sxx > 0.0
    b = np.where(live, (zc * yc[None, :]).sum(axis=1) / np.where(live, sxx, 1.0), 0.0)
    f = ((yc[None, :] - b[:, None] * zc) ** 2).sum(axis=1)
    return y_mean[None, :] - b[:, None] * z_mean, b, f


# -- one refit --------------------------------------------------------------------------------------------------------------


class KinkFit(NamedTuple):
    fitted: bool
    kink: Optional[float]
    slope: Optional[float]
    intercepts: Optional[Dict[int, float]]
    objective: Optional[float]
    reason: Optional[str]
    tied: Optional[Tuple[float, float]]
    pairs: int
    regime_counts: Dict[int, int]


def training_days(days: Sequence[KDay], cutoff: date, variant: Variant) -> List[KDay]:
    """The days a refit at `cutoff` may fit on: scored after the training start and on or before the cutoff, with a ratio and the
    variant's left side; clean ones only for a clean variant; with a regime only for a regime variant."""
    return [x for x in days
            if x.day <= cutoff and x.day > TRAIN_AFTER and x.ratio is not None and left_side(x, variant) is not None
            and (x.clean or not variant.clean) and (x.regime is not None or variant.intercepts != "regime")]


def unregimed_days(days: Sequence[KDay], cutoff: date) -> List[date]:
    """The days in the training window that have no regime (no ON RRP rate public), reported."""
    return [x.day for x in days if TRAIN_AFTER < x.day <= cutoff and x.ratio is not None and x.regime is None]


def regime_counts(pairs: Sequence[KDay]) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for x in pairs:
        counts[x.regime] = counts.get(x.regime, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (kv[0] is None, kv[0])))


def _not_fitted(reason: str, n: int, counts: Dict[int, int], tied: Optional[Tuple[float, float]] = None) -> KinkFit:
    return KinkFit(False, None, None, None, None, reason, tied, n, counts)


def fit_kink(pairs: Sequence[KDay], variant: Variant, *, grid: Sequence[float] = KINK_GRID,
             minimum_pairs: int = KINK_MINIMUM_PAIRS, regime_floor: int = REGIME_FLOOR) -> KinkFit:
    """The kink `k` on `grid` minimising the variant's objective of `left = a_g + b max(0, k - ratio)`, `b >= 0`.

    With fewer than `minimum_pairs` pairs, a regime (for a regime variant) with fewer than `regime_floor` pairs, or no candidate
    with a non-negative slope, the refit is not fitted. So it is when the kink is not identified (finding #54, #747): grid points
    whose objective is within `KINK_TIE_RTOL` of the least span more than one grid step. A point is never picked among them and
    the fixed 0.12 is never served.
    """
    n = len(pairs)
    counts = regime_counts(pairs) if variant.intercepts == "regime" else {0: n}
    if n < minimum_pairs:
        return _not_fitted("too few pairs", n, counts)
    short = {r: c for r, c in counts.items() if c < regime_floor}
    if short:
        r, c = min(short.items())
        return _not_fitted(f"regime {r} has {c} pairs, fewer than {regime_floor}", n, counts)
    x = np.array([p.ratio for p in pairs], dtype=float)
    y = np.array([left_side(p, variant) for p in pairs], dtype=float)
    groups = np.array([p.regime if variant.intercepts == "regime" else 0 for p in pairs])
    ks = np.asarray(grid, dtype=float)
    z = np.maximum(ks[:, None] - x[None, :], 0.0)
    solve = lad_lines if variant.objective == "lad" else squares_lines
    a, b, f = solve(z, y, groups)
    inverse, count = _groups(groups)
    feasible = _live(z, inverse, count) & (b >= 0.0)
    if not feasible.any():
        return _not_fitted("no candidate with a non-negative slope", n, counts)
    least = float(f[feasible].min())
    tol = KINK_TIE_RTOL * max(least, 1e-12)
    tied = np.flatnonzero(feasible & (np.abs(f - least) <= tol))
    if tied.max() - tied.min() > 1:
        lo, hi = float(ks[tied.min()]), float(ks[tied.max()])
        return _not_fitted(f"not identified (tied objective over [{lo}, {hi}])", n, counts, (lo, hi))
    best = int(tied[np.argmin(f[tied])])
    keys = sorted(set(int(g) for g in groups))
    return KinkFit(True, float(ks[best]), float(b[best]), {key: float(a[best, j]) for j, key in enumerate(keys)}, float(f[best]),
                   None, None, n, counts)


def residuals(pairs: Sequence[KDay], variant: Variant, fit: KinkFit) -> List[float]:
    """Each pair's left side less the fitted curve (the training residuals a refit leaves)."""
    if not fit.fitted:
        raise ValueError("a refit that did not fit has no residuals")
    out = []
    for p in pairs:
        key = p.regime if variant.intercepts == "regime" else 0
        out.append(left_side(p, variant) - fit.intercepts[key] - fit.slope * max(0.0, fit.kink - p.ratio))
    return out


def _require_on_or_before(pairs: Sequence[KDay], cutoff: date) -> None:
    for x in pairs:
        if x.day > cutoff:
            raise LookAheadError(f"the kink for the refit at {cutoff} would be fitted on {x.day}, after its cutoff")


def refit(pairs: Sequence[KDay], cutoff: date, variant: Variant, *, replications: int, seed: int = SEED) -> h7.Refit:
    """The variant's kink at `cutoff`, fitted on `pairs` alone, with a stationary-bootstrap 90% interval.

    `replications` of 0 skips the interval. A draw that does not fit (too few pairs, a short regime, not identified) is left out.

    Raises:
        LookAheadError: a pair is scored after `cutoff`.
    """
    _require_on_or_before(pairs, cutoff)
    fit = fit_kink(pairs, variant)
    record = fit._asdict()
    lower = upper = None
    if fit.fitted and replications > 0:
        rng = random.Random(seed)
        draws = []
        for _ in range(replications):
            index = stationary_bootstrap_indices(len(pairs), BLOCK_LENGTH, rng)
            draw = fit_kink([pairs[j] for j in index], variant)
            if draw.fitted:
                draws.append(draw.kink)
        if draws:
            draws.sort()
            tail = (1.0 - LEVEL) / 2.0
            lower = min(satiation.quantile(draws, tail), fit.kink)
            upper = max(satiation.quantile(draws, 1.0 - tail), fit.kink)
        record["draws_fitted"] = len(draws)
    return h7.Refit(cutoff, float(fit.kink) if fit.fitted else math.nan, fit.fitted, lower, upper, len(pairs), record)


def refit_on(days: Sequence[KDay], cutoff: date, variant: Variant, *, replications: int, seed: int = SEED) -> h7.Refit:
    """`refit` on the pairs `training_days` gives for `cutoff`."""
    return refit(training_days(days, cutoff, variant), cutoff, variant, replications=replications, seed=seed)


# -- the real-time path -----------------------------------------------------------------------------------------------------


#: What the worker processes of `real_time_path` read (set before they fork; a refit is a function of these and its cutoff alone).
_JOB: Tuple = ()


def _refit_job(cutoff: date) -> h7.Refit:
    days, variant, replications, seed = _JOB
    return refit_on(days, cutoff, variant, replications=replications, seed=seed)


def real_time_path(days: Sequence[KDay], cutoffs: Sequence[date], variant: Variant, *, replications: int,
                   seed: int = SEED, workers: int = 1) -> List[h7.RefitPath]:
    """Each refit's real-time path over the days it serves, as `h7_estimator.real_time_path`: refit `k` serves from the second
    business day after its cutoff to the day before refit `k + 1` serves from. A dropped day is still served. A refit that did not
    fit serves nothing; its days are counted in `missing_days`. Computed, not scored.

    `workers` only spreads the refits over processes; every refit is a function of its cutoff alone, so the result does not depend on it.

    Raises:
        ValueError: `cutoffs` are not strictly increasing.
    """
    global _JOB
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [next_business_day(c, SERVING_LAG) for c in cutoffs]
    if workers > 1:
        _JOB = (days, variant, replications, seed)
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as pool:
            refits = list(pool.map(_refit_job, cutoffs))
    else:
        refits = [refit_on(days, c, variant, replications=replications, seed=seed) for c in cutoffs]
    out: List[h7.RefitPath] = []
    for i, fit in enumerate(refits):
        end = starts[i + 1] if i + 1 < len(starts) else None
        estimates: List[h7.Estimate] = []
        gaps: Dict[date, float] = {}
        missing = 0
        for x in days:
            if x.day < starts[i] or (end is not None and x.day >= end):
                continue
            if not fit.fitted or x.ratio is None:
                missing += 1
                continue
            lower = None if fit.upper is None else x.ratio - fit.upper
            upper = None if fit.lower is None else x.ratio - fit.lower
            estimates.append(h7.Estimate(x.day, x.ratio, x.ratio - fit.level, lower, upper, None))
            if i > 0 and refits[i - 1].fitted:
                gaps[x.day] = abs((x.ratio - fit.level) - (x.ratio - refits[i - 1].level))
        out.append(h7.RefitPath(fit, estimates, gaps, missing))
    return out


def common_served_days(paths: Mapping[str, Sequence[h7.RefitPath]]) -> Set[date]:
    """The days every estimator in `paths` serves an estimate for: the days a comparison is read on (the #137 ruling)."""
    sets = [{e.day for p in path for e in p.estimates} for path in paths.values()]
    return set.intersection(*sets) if sets else set()


def summarise(path: Sequence[h7.RefitPath], days: Optional[Set[date]] = None) -> Dict:
    """Goalposts 1 and 2 for one estimator (`goalposts.stability_goalpost`, `sharpness_goalpost`), on `days` when given.

    Gaps and widths are in points of bank assets. A refit that did not fit is a breach of goalpost 1 and counted.
    """
    not_fitted = sum(1 for p in path if not p.refit.fitted)
    gaps = {d: h7.points(g) for p in path for d, g in p.gaps.items() if days is None or d in days}
    served = [e for p in path for e in p.estimates if days is None or e.day in days]
    widths = [None if e.lower is None or e.upper is None else h7.points(e.upper - e.lower) for e in served]
    return {"served_days": len(served), "not_fitted": not_fitted,
            "goalpost_1": goalposts.stability_goalpost(gaps, not_fitted), "goalpost_2": goalposts.sharpness_goalpost(widths),
            "worst_gap_points": max(gaps.values()) if gaps else None}


# -- the block length, reported beside goalpost 2 ---------------------------------------------------------------------------


def politis_white_block(values: Sequence[float]) -> Optional[float]:
    """The Politis-White (2004, with Patton-Politis-White 2009's correction) optimal mean block length of the stationary
    bootstrap for `values`, flat-top lag window, capped at the series length. None for a constant series or fewer than 10 values.
    Reported beside goalpost 2 only (the #147 ruling): the bootstrap stays as declared.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 10 or float(x.std()) == 0.0:
        return None
    x = x - x.mean()
    k_n = max(5, int(math.sqrt(math.log10(n))))
    k_max = int(math.sqrt(n)) + k_n
    gamma = np.array([float((x[: n - k] * x[k:]).sum() / n) for k in range(k_max + 1)])
    rho = gamma / gamma[0]
    crit = 2.0 * math.sqrt(math.log10(n) / n)
    m_hat = k_max - k_n
    for m in range(0, k_max - k_n + 1):
        if all(abs(rho[m + j]) < crit for j in range(1, k_n + 1)):
            m_hat = m
            break
    big_m = min(2 * max(m_hat, 1), k_max)
    ks = np.arange(-big_m, big_m + 1)
    t = np.abs(ks) / big_m
    lam = np.where(t <= 0.5, 1.0, np.where(t <= 1.0, 2.0 * (1.0 - t), 0.0))
    g_k = gamma[np.abs(ks)]
    g_big = float((lam * np.abs(ks) * g_k).sum())
    g_zero = float((lam * g_k).sum())
    d_sb = 2.0 * g_zero ** 2
    if d_sb <= 0.0:
        return None
    return min(float((2.0 * g_big ** 2 / d_sb) ** (1.0 / 3.0) * n ** (1.0 / 3.0)), float(n))


# -- building the days and the leakage check --------------------------------------------------------------------------------


def build_days(rows: Sequence[DailyObservation], rule: InformationRule, *, publications: Sequence[scheduled.Publication],
               notes: Sequence[IorbAnnouncement], decision_time: time = DECISION_TIME,
               label_fn: Callable[[date], Optional[str]]) -> List[KDay]:
    """The scored days with what was public at their decision instants: the ratio and spread (`h7_estimator.asof_days`, through
    the parent's rule and its lockbox), `effr_minus_iorb_bp` of the scored row, the width regime read at announcement, and whether
    the day is clean (both flags through the parent's rule, and the turn label).

    Raises:
        ValueError: the rows carry no `effr` column.
        LookAheadError: a read is refused by the rule, or the day is in a locked tier.
    """
    if not any("effr" in row.values for row in rows):
        raise ValueError("the rows carry no effr column: build them with nyfed_effr_inputs (scripts/h7_kink_run.py)")
    base = h7.asof_days(rows, rule)
    by_date = {row.date: row for row in rows}
    widths = width_regimes(rows, publications, notes, decision_time=decision_time)
    days = [KDay(d.day, d.ratio, d.spread, by_date[d.day].effr_minus_iorb_bp, widths[d.day].regime, True) for d in base]
    flags = read_flags(with_quarter_end_window(rows), flag_rule())
    return mark_clean(days, flags, read_turn_labels(days, label_fn))


def _signature(days: Sequence[KDay]) -> Tuple:
    return tuple((x.day, x.ratio, x.spread, x.effr, x.regime, x.clean) for x in days)


def check_no_future(days: Sequence[KDay], cutoff: date, build: Callable[[date], Sequence[KDay]]) -> None:
    """Refuse days that are not what the panel cut at `cutoff` gives: `build(until)` builds the days from the rows up to `until`.

    Raises:
        LookAheadError: a day up to the cutoff differs when built from the cut panel, so it depended on a later row.
    """
    mine = [x for x in days if x.day <= cutoff]
    then = [x for x in build(cutoff) if x.day <= cutoff]
    if _signature(mine) != _signature(then):
        raise LookAheadError(f"the days up to {cutoff} differ when built from the panel cut at that row; a day depended on a later row")
