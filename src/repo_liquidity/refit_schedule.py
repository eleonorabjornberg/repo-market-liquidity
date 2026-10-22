"""H7m, groundwork: which refit schedule should the H7 runs use? A read-only comparison of candidate schedules (directive #161).

**Nothing is fitted here.** No kink, buffer, share or interval is computed, and no declaration is changed. The module sees an
estimator only as a function from a refit's cutoff to the *training sample* it would fit on (which days, which episodes or regimes
count, whether the estimator's own input rule lets it fit at all), so a schedule is judged on inputs alone.

A refit with cutoff `c` fits on days scored on or before `c` and serves from the second business day after `c` (`SERVING_LAG`, as
`h7_estimator`) to the day before the next refit serves from. Her ruling of 21 October 2026 fixes what counts:

* **Only refits that serve a scored day inside the window count.** A refit on the last row (2025-12-31) serves nothing, moves no
  goalpost and is listed apart. A unit (an episode, a corridor-width regime) *enters* only if some refit early enough to serve
  includes it.
* **A transition is a refit-to-refit step in which the training sample changes**: the number of chances the refit-gap goalpost
  (goalpost 1, `docs/decisions/measurement-protocol.md` section 3) has to move.

The information set. A schedule may use only what was public at each refit's decision instant. Every rule below finds its dates
by scanning the scored days in order and asking, on each, what the estimator's sample is *at that day* (`Estimator.sample_at`), so
a date is a function of the rows up to it. `check_schedule_no_future` tests that: the schedule built from the days up to a probe
date is the full schedule's refits up to it. The two rules that add a refit on the window's end (S1, S1b) depend on the declared
end of the window, a constant of the declaration and not of the data; they are marked and excluded from that comparison.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import date
from typing import Callable, Dict, FrozenSet, Hashable, List, NamedTuple, Optional, Sequence, Set, Tuple

from repo_model.splits import LookAheadError

#: A refit serves from this many business days after its cutoff (`h7_estimator.SERVING_LAG`).
SERVING_LAG = 2
#: The stride of the denser comparison schedule S6, and of the short cadence S5 uses after an entry, in scored days.
DENSE_EVERY = 10
SHORT_CADENCE = 5


class Sample(NamedTuple):
    """What an estimator would train on at one cutoff, from inputs alone.

    `signature` is equal for equal samples (so equal fits). `units` are the episodes or regimes that count at the cutoff (an
    episode with enough scarce days, a regime with enough pairs). `fit_possible` is the estimator's own input rule only: it says
    nothing of whether a fit would converge or be identified. `size` is the number of training days.
    """

    signature: Hashable
    units: FrozenSet[str]
    fit_possible: bool
    size: int


class Estimator(NamedTuple):
    name: str
    family: str
    units: Tuple[str, ...]
    sample_at: Callable[[date], Sample]


class Context(NamedTuple):
    """The scored days of the window, the first cutoff and the estimators a schedule is judged on."""

    days: Tuple[date, ...]
    start: date
    serving_start: Callable[[date], date]
    every: int
    boundaries: Tuple[date, ...]
    estimators: Tuple[Estimator, ...]
    dense: int = SHORT_CADENCE


class Schedule(NamedTuple):
    cutoffs: Tuple[date, ...]
    #: The cutoffs that exist because of the declared end of the window.
    window_dependent: FrozenSet[date]


class Rule(NamedTuple):
    id: str
    text: str
    build: Callable[[Context], Schedule]
    window_end_dependent: bool


# -- serving ------------------------------------------------------------------------------------------------------------


def served(ctx: Context, cutoffs: Sequence[date]) -> List[Tuple[date, Tuple[date, ...]]]:
    """Each refit with the scored days it serves: from its serving start to the day before the next refit serves from.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = [ctx.serving_start(c) for c in cutoffs]
    out = []
    for k, cutoff in enumerate(cutoffs):
        lo = bisect_left(ctx.days, starts[k])
        hi = bisect_left(ctx.days, starts[k + 1]) if k + 1 < len(cutoffs) else len(ctx.days)
        out.append((cutoff, tuple(ctx.days[lo:hi])))
    return out


def last_servable(ctx: Context) -> date:
    """The latest scored day whose refit would serve at least the window's last day."""
    last = ctx.days[-1]
    best = None
    for day in ctx.days:
        try:
            if ctx.serving_start(day) <= last:
                best = day
        except ValueError:  # beyond the holiday table: it serves nothing
            break
    if best is None:
        raise ValueError("no cutoff in the window serves a scored day")
    return best


# -- entry dates --------------------------------------------------------------------------------------------------------


def entry_dates(ctx: Context, estimator: Estimator) -> Dict[str, Optional[date]]:
    """For each unit of `estimator`, the first scored day on which it counts, read from the sample at that day alone."""
    found: Dict[str, Optional[date]] = {u: None for u in estimator.units}
    for i, c in enumerate(ctx.days):
        units = estimator.sample_at(c).units
        for u in estimator.units:
            if found[u] is None and u in units:
                found[u] = c
        if all(v is not None for v in found.values()):
            break
    return found


def _entries(ctx: Context, prefix: str) -> List[date]:
    """The distinct dates, after the start, on which a unit named `prefix...` first counts, over all estimators."""
    out: Set[date] = set()
    for est in ctx.estimators:
        for u, day in entry_dates(ctx, est).items():
            if u.startswith(prefix) and day is not None and day > ctx.start:
                out.add(day)
    return sorted(out)


# -- the rules ----------------------------------------------------------------------------------------------------------


def stride(ctx: Context, anchor: date, until: Optional[date] = None, every: Optional[int] = None) -> List[date]:
    """Every `every` scored days from `anchor`, stopping before `until`."""
    step = ctx.every if every is None else every
    first = bisect_left(ctx.days, anchor)
    out = list(ctx.days[first::step])
    return [d for d in out if until is None or d < until]


def anchored(ctx: Context, anchors: Sequence[date]) -> List[date]:
    """The stride restarted at each anchor: from the start, then from each later anchor, up to the next one."""
    points = sorted({ctx.start} | {a for a in anchors if a > ctx.start})
    out: List[date] = []
    for j, a in enumerate(points):
        out.extend(stride(ctx, a, points[j + 1] if j + 1 < len(points) else None))
    return sorted(set(out))


def _s0(ctx: Context) -> Schedule:
    return Schedule(tuple(stride(ctx, ctx.start)), frozenset())


def _s1(ctx: Context) -> Schedule:
    base, final = set(stride(ctx, ctx.start)), ctx.days[-1]
    return Schedule(tuple(sorted(base | {final})), frozenset({final} - base))


def _s1b(ctx: Context) -> Schedule:
    base, last = set(stride(ctx, ctx.start)), last_servable(ctx)
    return Schedule(tuple(sorted(base | {last})), frozenset({last} - base))


def _s2(ctx: Context) -> Schedule:
    return Schedule(tuple(anchored(ctx, _entries(ctx, "episode:"))), frozenset())


def _boundaries(ctx: Context) -> List[date]:
    days = set(ctx.days)
    return [b for b in ctx.boundaries if b in days and b > ctx.start]


def _s3(ctx: Context) -> Schedule:
    return Schedule(tuple(sorted(set(stride(ctx, ctx.start)) | set(_boundaries(ctx)))), frozenset())


def _s3r(ctx: Context) -> Schedule:
    return Schedule(tuple(anchored(ctx, _boundaries(ctx))), frozenset())


def _s3f(ctx: Context) -> Schedule:
    return Schedule(tuple(sorted(set(stride(ctx, ctx.start)) | set(_entries(ctx, "regime:")))), frozenset())


def _s4(ctx: Context) -> Schedule:
    extra = set(_entries(ctx, "episode:")) | set(_entries(ctx, "regime:"))
    return Schedule(tuple(sorted(set(stride(ctx, ctx.start)) | extra)), frozenset())


def _s5(ctx: Context) -> Schedule:
    base = set(_s4(ctx).cutoffs)
    for e in _entries(ctx, "episode:"):
        i = bisect_left(ctx.days, e)
        m = 1
        while i + ctx.dense * m < len(ctx.days) and ctx.dense * m < ctx.every:
            base.add(ctx.days[i + ctx.dense * m])
            m += 1
    return Schedule(tuple(sorted(base)), frozenset())


def _s6(ctx: Context) -> Schedule:
    return Schedule(tuple(stride(ctx, ctx.start, every=DENSE_EVERY)), frozenset())


RULES: Tuple[Rule, ...] = (
    Rule("S0", "the current schedule: every 21 scored days from the first cutoff", _s0, False),
    Rule("S1", "S0 plus a final refit on the last row (her #160 option (b), now in #150)", _s1, True),
    Rule("S1b", "S0 plus a final refit on the last cutoff that serves a scored day", _s1b, True),
    Rule("S2", "the stride restarted on the day each episode reaches its floor", _s2, False),
    Rule("S3", "S0 plus a refit on the first day of each corridor-width regime", _s3, False),
    Rule("S3r", "the stride restarted on the first day of each corridor-width regime", _s3r, False),
    Rule("S3f", "S0 plus a refit on the day each regime reaches its 50-pair floor", _s3f, False),
    Rule("S4", "S0 plus one refit on the day each episode and each regime first counts", _s4, False),
    Rule("S5", "S4 plus a refit every 5 scored days for a stride after each episode's entry", _s5, False),
    Rule("S6", "a denser stride: every 10 scored days (a bound on cost, not a proposal)", _s6, False),
)
SCHEDULES: Dict[str, Rule] = {r.id: r for r in RULES}


# -- reading a schedule on one estimator --------------------------------------------------------------------------------


def evaluate(ctx: Context, estimator: Estimator, cutoffs: Sequence[date]) -> Dict[str, object]:
    """What a schedule gives `estimator`, from inputs alone. Counts only refits that serve a scored day.

    `distinct_samples` and `transitions_changed` are over the serving refits in time order. `transitions_fittable` keeps the
    changed transitions whose two ends both pass the estimator's own input rule; `dead_serving` counts the serving refits
    that do not (they serve no estimate, and `dead_days` counts the scored days they leave without one). `units` gives, for each episode or regime, the first serving refit whose sample counts
    it (None: it never enters) and the scored days served by refits that count it.
    """
    pairs = served(ctx, cutoffs)
    serving = [(c, days) for c, days in pairs if days]
    samples = [estimator.sample_at(c) for c, _ in serving]
    changed = [a.signature != b.signature for a, b in zip(samples, samples[1:])]
    fittable = [ch and a.fit_possible and b.fit_possible for ch, a, b in zip(changed, samples, samples[1:])]
    units: Dict[str, Dict[str, object]] = {}
    for u in estimator.units:
        hits = [(c, days) for (c, days), s in zip(serving, samples) if u in s.units]
        units[u] = {"first_serving_refit": hits[0][0].isoformat() if hits else None,
                    "days_served_with_unit": sum(len(days) for _, days in hits)}
    return {
        "refits": len(pairs), "serving": len(serving), "served_days": sum(len(days) for _, days in serving),
        "dead_days": sum(len(days) for (_, days), s in zip(serving, samples) if not s.fit_possible),
        "not_serving": [c.isoformat() for c, days in pairs if not days],
        "distinct_samples": len({s.signature for s in samples}),
        "distinct_fittable": len({s.signature for s in samples if s.fit_possible}),
        "dead_serving": sum(1 for s in samples if not s.fit_possible),
        "transitions_changed": sum(changed), "transitions_fittable": sum(fittable),
        "units": units,
    }


def live_days(ctx: Context, estimator: Estimator, cutoffs: Sequence[date]) -> FrozenSet[date]:
    """The scored days served by a refit that passes the estimator's own input rule: the days it could have an estimate on."""
    return frozenset(d for c, days in served(ctx, cutoffs) if days and estimator.sample_at(c).fit_possible for d in days)


def compare_to_declared(ctx: Context, cutoffs: Sequence[date], declared: Sequence[date]) -> Dict[str, object]:
    """What a candidate schedule changes against a declared one: the refits added and removed, and the scored days whose serving
    refit is not the one the declared schedule gave them."""
    def owner(schedule):
        return {d: c for c, days in served(ctx, schedule) for d in days}
    new, old = owner(cutoffs), owner(declared)
    return {
        "added": [c.isoformat() for c in sorted(set(cutoffs) - set(declared))],
        "removed": [c.isoformat() for c in sorted(set(declared) - set(cutoffs))],
        "kept": len(set(cutoffs) & set(declared)),
        "days_with_a_new_serving_refit": sum(1 for d in ctx.days if new.get(d) != old.get(d)),
    }


# -- the leakage check --------------------------------------------------------------------------------------------------


def check_schedule_no_future(rule: Rule, make_context: Callable[[Sequence[date]], Context], days: Sequence[date],
                             probes: Sequence[date]) -> None:
    """Refuse a rule whose refit dates depend on data after them.

    `make_context(prefix)` builds the context from the scored days up to a probe. The schedule built from those days alone must be
    the full schedule's refits up to the probe. The refits that exist because of the window's end are left out of both.

    Raises:
        LookAheadError: a schedule built from the days up to a probe differs from the full schedule's refits up to it.
    """
    full = rule.build(make_context(days))
    kept = [c for c in full.cutoffs if c not in full.window_dependent]
    for p in probes:
        cut = rule.build(make_context(days[: bisect_left(days, p) + 1]))
        got = [c for c in cut.cutoffs if c not in cut.window_dependent]
        want = [c for c in kept if c <= p]
        if got != want:
            raise LookAheadError(
                f"the schedule {rule.id} built from the days up to {p} differs from the full schedule's refits up to it: "
                f"{[c.isoformat() for c in got]} against {[c.isoformat() for c in want]}"
            )
