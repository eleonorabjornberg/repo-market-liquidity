"""H7m, development step 4: the account of the bank distribution for A and C (`docs/stages/h7-step4.md`, directive #144).

Aggregate deployable liquidity under the three declared alternatives of `docs/decisions/measurement-protocol.md` section 8 (the
reserves of the three H.8 groups as observed, all held by the large domestic banks, in proportion to group assets), per served
day, with the 90% interval where the estimator has one, and the group-by-group terms for the estimators that model groups. The
alternatives are step 2's own (`h7_candidate_c.distribution`); nothing here fits anything, scores anything or decides anything.

Three views are built from refits that earlier steps made:

* `account_c`: C or a calendar-clean variant of C, from its refits' shares and bootstrap draws (`h7_candidate_c.RefitC`).
* `account_a_own`: A as defined, `R - k`. It has no per-group term, so every alternative gives the same figure.
* `account_a_grouped`: A's kink read as every group's buffer share, through step 2's machinery (a marked reading, step 4 section 2).

A refit serves from the second business day after its cutoff to the day before the next refit serves from, as in every earlier
step. Reads nothing but through the days `h7_candidate_c.sample_c` gives (the parent's as-of rule, and its lockbox refusal).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from repo_model import satiation
from repo_model.data import next_business_day
from repo_model.splits import LookAheadError

from repo_liquidity import h7_candidate_c as c

ALTERNATIVES = c.ALTERNATIVES
SERVING_LAG = c.SERVING_LAG
LEVEL = c.LEVEL
#: Why a day after the first refit's serving day is not served.
NOT_FITTED = "the refit in force did not fit"
NO_WEEK = "no H.8 group week public at the decision instant"
NO_RATIO = "no all-banks reserves ratio at the decision instant"
#: Tolerance when comparing a re-run refit's shares with the tracked record's.
SHARE_TOLERANCE = 1e-12


class Figure(NamedTuple):
    """One alternative's aggregate on one day, as a share of bank assets, with its 90% interval and its group terms (if any)."""

    aggregate: float
    lower: Optional[float]
    upper: Optional[float]
    groups: Optional[Tuple[float, ...]]


class ServedDay(NamedTuple):
    day: date
    cutoff: date
    break_week: bool
    figures: Dict[str, Figure]


class Account(NamedTuple):
    name: str
    served: List[ServedDay]
    missing: Dict[date, str]


class ARefit(NamedTuple):
    """One refit of A as the kink run's record holds it: the kink and its 90% interval, as shares of bank assets."""

    cutoff: date
    fitted: bool
    kink: Optional[float]
    lower: Optional[float]
    upper: Optional[float]


# -- the serving schedule ---------------------------------------------------------------------------------------------


def serving_starts(cutoffs: Sequence[date]) -> List[date]:
    """The first day each refit serves: the second business day after its cutoff."""
    return [next_business_day(cut, SERVING_LAG) for cut in cutoffs]


def serving_index(days: Sequence[date], cutoffs: Sequence[date]) -> Dict[date, int]:
    """For each day from the first refit's serving day on, the index of the refit that serves it.

    Raises:
        ValueError: if `cutoffs` are not strictly increasing.
    """
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("the refit cutoffs must be strictly increasing")
    starts = serving_starts(cutoffs)
    out: Dict[date, int] = {}
    for day in days:
        k = None
        for i, start in enumerate(starts):
            if day >= start:
                k = i
        if k is not None:
            out[day] = k
    return out


def check_served_after_cutoff(served: Sequence[ServedDay]) -> None:
    """Refuse a day served by a refit before the refit's serving day.

    Raises:
        LookAheadError: a served day is earlier than the second business day after its refit's cutoff.
    """
    for s in served:
        first = next_business_day(s.cutoff, SERVING_LAG)
        if s.day < first:
            raise LookAheadError(f"{s.day} is served by the refit at {s.cutoff}, before its serving day {first}")


def check_weeks_public(days: Sequence[c.DayC]) -> None:
    """Refuse a day whose group week was public only after its decision instant.

    Raises:
        LookAheadError: a day read a week public after its decision instant.
    """
    for d in days:
        if d.week is not None and d.week.public_at > d.instant:
            raise LookAheadError(f"{d.day} read the week ending {d.week.week_ending}, public at {d.week.public_at}, after its "
                                 f"decision instant {d.instant}")


def _serving(days: Sequence[c.DayC], cutoffs: Sequence[date], refits: Sequence) -> Tuple[Dict[date, int], List[date]]:
    if len(refits) != len(cutoffs):
        raise ValueError(f"there must be one refit for each cutoff: {len(refits)} refits, {len(cutoffs)} cutoffs")
    check_weeks_public(days)
    index = serving_index([d.day for d in days], cutoffs)
    return index, serving_starts(cutoffs)


# -- C ----------------------------------------------------------------------------------------------------------------------


def _quantiles(values: Sequence[float], point: float) -> Tuple[float, float]:
    ordered = sorted(values)
    tail = (1.0 - LEVEL) / 2.0
    return min(satiation.quantile(ordered, tail), point), max(satiation.quantile(ordered, 1.0 - tail), point)


def account_c(name: str, days: Sequence[c.DayC], cutoffs: Sequence[date], refits: Sequence[c.RefitC]) -> Account:
    """C's account, or a calendar-clean variant's: each served day's aggregate under the three alternatives, group by group,
    with the interval of the refit's bootstrap draws under each alternative (widened to hold the point, as `c.interval`).

    A day is missing when its refit did not fit, it has no all-banks ratio, or it has no group week.

    Raises:
        ValueError: the refits and cutoffs differ in number, or the cutoffs are not increasing.
        LookAheadError: a day read a week public after its decision instant, or is served before its refit's lag.
    """
    index, _starts = _serving(days, cutoffs, refits)
    served: List[ServedDay] = []
    missing: Dict[date, str] = {}
    for d in days:
        if d.day not in index:
            continue
        k = index[d.day]
        fit = refits[k]
        if not fit.fitted:
            missing[d.day] = NOT_FITTED
        elif d.ratio is None:
            missing[d.day] = NO_RATIO
        elif d.week is None:
            missing[d.day] = NO_WEEK
        else:
            point = c.distribution(d.week, fit.shares)
            spread = [c.distribution(d.week, draw) for draw in fit.draws]
            figures: Dict[str, Figure] = {}
            for alt in ALTERNATIVES:
                lower = upper = None
                if spread:
                    lower, upper = _quantiles([s[alt]["aggregate"] for s in spread], point[alt]["aggregate"])
                figures[alt] = Figure(point[alt]["aggregate"], lower, upper, tuple(point[alt]["groups"]))
            served.append(ServedDay(d.day, cutoffs[k], d.week.break_week, figures))
    check_served_after_cutoff(served)
    return Account(name, served, missing)


# -- A ----------------------------------------------------------------------------------------------------------------------


def a_refits_from_record(rows: Sequence[Mapping]) -> List[ARefit]:
    """A's refits from the kink run's record (`results/h7/kink.json`, `estimators.<id>.refits`).

    Raises:
        ValueError: a fitted refit has no kink or no interval.
    """
    out = []
    for row in rows:
        fitted = bool(row["fitted"])
        if fitted and (row.get("kink") is None or row.get("lower") is None or row.get("upper") is None):
            raise ValueError(f"the fitted refit at {row['cutoff']} has no kink or no interval in the record")
        out.append(ARefit(date.fromisoformat(row["cutoff"]), fitted, row["kink"] if fitted else None,
                          row["lower"] if fitted else None, row["upper"] if fitted else None))
    return out


def account_a_own(name: str, days: Sequence[c.DayC], cutoffs: Sequence[date], refits: Sequence[ARefit]) -> Account:
    """A as defined: `R - k` on each served day, the all-banks ratio at the decision instant minus the kink in force.

    A has no per-group term, so moving the same reserves between the groups moves nothing: each alternative holds the same
    figure, and no group terms exist. The interval is the kink's, flipped: `[R - upper, R - lower]`. A day needs a ratio only.
    """
    index, _starts = _serving(days, cutoffs, refits)
    served: List[ServedDay] = []
    missing: Dict[date, str] = {}
    for d in days:
        if d.day not in index:
            continue
        k = index[d.day]
        fit = refits[k]
        if not fit.fitted:
            missing[d.day] = NOT_FITTED
        elif d.ratio is None:
            missing[d.day] = NO_RATIO
        else:
            figure = Figure(d.ratio - fit.kink, d.ratio - fit.upper, d.ratio - fit.lower, None)
            served.append(ServedDay(d.day, cutoffs[k], d.week is not None and d.week.break_week,
                                    {alt: figure for alt in ALTERNATIVES}))
    check_served_after_cutoff(served)
    return Account(name, served, missing)


def account_a_grouped(name: str, days: Sequence[c.DayC], cutoffs: Sequence[date], refits: Sequence[ARefit]) -> Account:
    """A's kink read as every group's buffer share, through step 2's machinery (a marked reading, step 4 section 2).

    Each group's reserves above `k` of its own assets, never negative, over the groups' total assets, under each alternative.
    The aggregate does not increase with `k`, so the interval is the aggregate at the kink's upper end (lower bound) and lower
    end (upper bound). A day needs a ratio (A serves only where it has one) and a group week.
    """
    index, _starts = _serving(days, cutoffs, refits)
    served: List[ServedDay] = []
    missing: Dict[date, str] = {}
    for d in days:
        if d.day not in index:
            continue
        k = index[d.day]
        fit = refits[k]
        if not fit.fitted:
            missing[d.day] = NOT_FITTED
        elif d.ratio is None:
            missing[d.day] = NO_RATIO
        elif d.week is None:
            missing[d.day] = NO_WEEK
        else:
            at = {end: c.distribution(d.week, (end,) * len(c.GROUPS)) for end in (fit.kink, fit.lower, fit.upper)}
            figures: Dict[str, Figure] = {}
            for alt in ALTERNATIVES:
                point = at[fit.kink][alt]
                ends = (at[fit.upper][alt]["aggregate"], at[fit.lower][alt]["aggregate"])
                figures[alt] = Figure(point["aggregate"], min(ends + (point["aggregate"],)), max(ends + (point["aggregate"],)),
                                      tuple(point["groups"]))
            served.append(ServedDay(d.day, cutoffs[k], d.week.break_week, figures))
    check_served_after_cutoff(served)
    return Account(name, served, missing)


# -- the summary ------------------------------------------------------------------------------------------------------------


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _alternative_row(served: Sequence[ServedDay], alt: str, *, groups: bool) -> Dict[str, object]:
    figures = [s.figures[alt] for s in served]
    aggregates = [f.aggregate for f in figures]
    widths = [f.upper - f.lower for f in figures if f.lower is not None and f.upper is not None]
    base = [s.figures["as_observed"].aggregate for s in served]
    row: Dict[str, object] = {
        "days": len(figures), "median_points": c.points(_median(aggregates)), "min_points": c.points(min(aggregates)),
        "max_points": c.points(max(aggregates)), "days_at_zero": sum(1 for v in aggregates if v == 0.0),
        "median_width_points": c.points(_median(widths)) if widths else None,
        "median_difference_points": c.points(_median([v - b for v, b in zip(aggregates, base)])),
    }
    if groups and all(f.groups is not None for f in figures):
        row["groups"] = {g: {"median_points": c.points(_median([f.groups[i] for f in figures])),
                             "days_at_zero": sum(1 for f in figures if f.groups[i] == 0.0)}
                         for i, g in enumerate(c.GROUPS)}
    return row


def summarise(account: Account) -> Dict[str, object]:
    """Counts, medians, ranges, zero days, the median interval width and the difference from the as-observed figure, in points
    of bank assets, for each alternative, over all served days and by calendar year. An account that serves nothing says so."""
    served = account.served
    out: Dict[str, object] = {"served_days": len(served), "missing_days": len(account.missing),
                              "missing_reasons": {r: sum(1 for v in account.missing.values() if v == r)
                                                  for r in sorted(set(account.missing.values()))},
                              "break_week_days": sum(1 for s in served if s.break_week), "alternatives": {}, "by_year": {}}
    if not served:
        return out
    groups = served[0].figures["as_observed"].groups is not None
    out["alternatives"] = {alt: _alternative_row(served, alt, groups=groups) for alt in ALTERNATIVES}
    for year in sorted({s.day.year for s in served}):
        inside = [s for s in served if s.day.year == year]
        out["by_year"][str(year)] = {"days": len(inside), "median_points": {
            alt: c.points(_median([s.figures[alt].aggregate for s in inside])) for alt in ALTERNATIVES}}
    return out


def daily(account: Account) -> Dict[str, object]:
    """The per-day columns, in points of bank assets rounded to four places: one list for each figure, in served-day order."""
    def pts(value):
        return None if value is None else round(c.points(value), 4)

    out: Dict[str, object] = {"days": [s.day.isoformat() for s in account.served],
                              "cutoff": [s.cutoff.isoformat() for s in account.served],
                              "break_week": [int(s.break_week) for s in account.served]}
    for alt in ALTERNATIVES:
        out[alt] = {"aggregate": [pts(s.figures[alt].aggregate) for s in account.served],
                    "lower": [pts(s.figures[alt].lower) for s in account.served],
                    "upper": [pts(s.figures[alt].upper) for s in account.served]}
        if account.served and account.served[0].figures[alt].groups is not None:
            out[alt]["groups"] = {g: [pts(s.figures[alt].groups[i]) for s in account.served] for i, g in enumerate(c.GROUPS)}
    out["missing"] = {day.isoformat(): reason for day, reason in sorted(account.missing.items())}
    return out


# -- the tracked record -----------------------------------------------------------------------------------------------------


def check_against_record(refits: Sequence[c.RefitC], record: Sequence[Mapping]) -> None:
    """Refuse refits that are not the ones the tracked record of the earlier run holds, cutoff by cutoff.

    Raises:
        ValueError: the cutoffs, the fitted flags or the fitted shares differ from the record's.
    """
    if len(refits) != len(record):
        raise ValueError(f"{len(refits)} refits, but the record holds {len(record)}")
    for fit, row in zip(refits, record):
        if fit.cutoff.isoformat() != row["cutoff"]:
            raise ValueError(f"the refit at {fit.cutoff} is the record's refit at {row['cutoff']}")
        if bool(fit.fitted) != bool(row["fitted"]):
            raise ValueError(f"the refit at {fit.cutoff} fitted {fit.fitted}, the record says {row['fitted']}")
        if fit.fitted:
            recorded = row["parameters"]
            if len(recorded) != len(fit.shares) or any(abs(x - y) > SHARE_TOLERANCE for x, y in zip(fit.shares, recorded)):
                raise ValueError(f"the refit at {fit.cutoff} has shares {fit.shares}, the record says {tuple(recorded)}")


def _scalar_list(value) -> bool:
    return isinstance(value, list) and all(not isinstance(v, (list, dict)) for v in value)


def _dump(value, depth: int) -> str:
    pad = "  " * (depth + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{pad}{json.dumps(k)}: {_dump(value[k], depth + 1)}" for k in sorted(value)]
        return "{\n" + ",\n".join(items) + "\n" + "  " * depth + "}"
    if isinstance(value, list):
        if _scalar_list(value):
            return json.dumps(value, allow_nan=False)
        items = [f"{pad}{_dump(v, depth + 1)}" for v in value]
        return "[\n" + ",\n".join(items) + "\n" + "  " * depth + "]"
    return json.dumps(value, allow_nan=False)


def dump_record(record: Mapping) -> str:
    """The record as text: keys sorted, two-space indent, every list of plain values on one line, a final newline."""
    return _dump(dict(record), 0) + "\n"
