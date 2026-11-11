"""H10 with new drivers, step 1 (#204, amended by #208): the second declaration's driver set, its inputs' guards, the
facility event and the 30 June 2027 break.

`docs/decisions/h10-method-2.md` is the draft record. This module holds what the record states in code, under **new names**:
it imports `attribution` and `h10_apply` and changes neither. The registered method (`h10-method.md`, `attribution.DRIVERS*`,
`h10_apply`, `h10_live`, `h10_registration`, digest `54b5f151...8770`) is untouched, and none of this module is in
`h10_live.METHOD_FILES`.

**Nothing here attributes an episode or scores anything.** `attribute_2` is the entry point step 2 will call; here it is
tested only on the break. The as-of rule is the parent's (`repo_model.asof.InformationRule`), asked, never re-implemented.
Standard library only.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from typing import Dict, Mapping, Optional, Sequence, Tuple

from repo_liquidity import attribution, declaration, h10_apply, indicators
from repo_liquidity.attribution import Attribution
from repo_model.asof import StaleReadError, declared_availability
from repo_model.splits import LookAheadError

#: The four new drivers, each entering as the window change of its column, like the registered five (`attribution.change`).
#: The facility event (her rulings of 9 and 10 November 2026 on #204 and #208, data-meaning rows 13 and 14): material use of
#: the standing facility, $1bn or more on a day, or a 2019-21 term repo operation material on its operation date; the event,
#: not the amount, and one driver; SOFR volume and the 1st-to-99th percentile range of SOFR (both break at
#: 2027-06-30, row 11); the primary dealers' Treasury fails to deliver, a collateral driver (row 8).
FACILITY_EVENT = "facility_material_use"
SOFR_VOLUME = "sofr_volume"
SOFR_P99_P1 = "sofr_p99_p1_bp"
FAILS = "pd_fails_deliver_ust"
NEW_DRIVERS: Tuple[str, ...] = (FACILITY_EVENT, SOFR_VOLUME, SOFR_P99_P1, FAILS)
#: The registered five (`attribution.DRIVERS_WITH_ON_RRP`) then the four, in that order.
DRIVERS_2: Tuple[str, ...] = attribution.DRIVERS_WITH_ON_RRP + NEW_DRIVERS

#: The report window of this declaration, in panel days (her ruling Q3 of 10 November 2026): the fails' whole window is public
#: 11 panel days after an onset. The registered method's `h10_apply.REPORT_DAYS` (10) is not touched and still governs it.
REPORT_DAYS_2 = 11

#: Material use of the standing facility, in USD bn (data-meaning row 13), fixed in advance.
SRF_MATERIAL_BN = 1.0
#: The 2019-21 term repo operations (data-meaning row 14), declared in `metadata/sources_phase3.json`: available at 16:00 on the
#: next business day, as the standing facility (`nyfed_srf`) and the parent's `nyfed_repo_ops` are. `fed_repo_material_use` reads
#: these two fields (overnight and term accepted on the operation date) beside the standing facility's.
TERM_REPO_SOURCE = "nyfed_temp_repo"
TERM_REPO_FIELDS = ((TERM_REPO_SOURCE, "temp_repo_take_up"), (TERM_REPO_SOURCE, "temp_repo_term_take_up"))
#: When a day's operation results are public: the next business day, 16:00 (the Desk states no publication time).
FACILITY_PUBLISH_TIME = time(16, 0)

FAILS_SOURCE = "nyfed_pd_fails"
#: The Primary Dealer Statistics for a Wednesday as-of date are published the Thursday of the following week, at 16:30
#: (`declarations/nyfed_pd_fails.json`, copied from the parent's `nyfed_pd_financing`).
FAILS_PUBLISH_TIME = time(16, 30)
FAILS_PUBLISH_DAYS_AFTER_WEDNESDAY = 8

#: The 30 June 2027 break (mandatory clearing of Treasury repo; data-meaning row 11): read from the indicators' own break
#: table, not restated. The series of `NEW_DRIVERS` that it breaks.
_BREAK_KEY, _BREAK_COLUMNS = next(iter(indicators.MEASUREMENT_BREAKS.items()))
BREAK_DATE: date = date.fromisoformat(_BREAK_KEY)
BREAK_DRIVERS: Tuple[str, ...] = tuple(name for name in DRIVERS_2 if name in _BREAK_COLUMNS)
BREAK_REASON = (
    f"{' and '.join(BREAK_DRIVERS)} are not read on or after {BREAK_DATE.isoformat()}: mandatory clearing of Treasury repo "
    f"makes them a different measure (data-meaning row 11), and no re-based series is declared"
)


# --------------------------------------------------------------------------- the rule, and when a window is public


@contextmanager
def rule_2(drivers: Sequence[str] = DRIVERS_2):
    """The parent's as-of rule over the spread and `drivers`, under Phase 3's declaration, at H10's decision instant."""
    from repo_model.asof import InformationRule

    with declaration.phase3_declaration():
        yield InformationRule(declaration.registry(), list(drivers), decision_time=h10_apply.DECISION_TIME)


def report_panel_days(rule, dates: Sequence[date], start: int, *, limit: int = 40) -> Optional[int]:
    """The panel days after an onset at `start` on which the whole window (baseline and window) of `rule`'s inputs is public.

    This is the smallest `report - start` for which `attribution.check_window_public` accepts the window, the same test the
    registered method applies at `REPORT_DAYS`. None when no report day within `limit` panel days, or in the sample, is late
    enough.
    """
    for report in range(start + 1, min(start + limit, len(dates) - 1) + 1):
        try:
            attribution.check_window_public(rule, dates, start, report)
        except LookAheadError:
            continue
        return report - start
    return None


def report_index_2(start: int, count: int) -> int:
    """The panel day on which an episode starting at `start` is reported under this declaration: `REPORT_DAYS_2` panel days
    later (the registered method's `h10_apply.report_index` uses `REPORT_DAYS`).

    Raises:
        ValueError: that day is not in the sample of `count` panel days.
    """
    index = start + REPORT_DAYS_2
    if index >= count:
        raise ValueError("the report day is past the last development day")
    return index


def report_days_summary(dates: Sequence[date], inputs: Sequence[str] = (*NEW_DRIVERS, "tga")) -> Dict[str, dict]:
    """For each input, over every onset position of `dates` that has a full window and a report day in the sample, the
    fewest and most panel days until its whole window is public (with the spread's own lag), and how many onsets that is
    past this declaration's `REPORT_DAYS_2` (`over_report_days`) and past the registered `REPORT_DAYS`
    (`over_registered_report_days`). A calendar fact about the declared lags; no value is read and nothing is attributed."""
    out: Dict[str, dict] = {}
    starts = range(attribution.BASELINE_DAYS, len(dates) - attribution.WINDOW_DAYS)
    for name in inputs:
        with rule_2([name]) as rule:
            days = [d for d in (report_panel_days(rule, dates, s) for s in starts) if d is not None]
        out[name] = {
            "onsets": len(days), "min": min(days), "max": max(days),
            "over_report_days": sum(1 for d in days if d > REPORT_DAYS_2),
            "over_registered_report_days": sum(1 for d in days if d > h10_apply.REPORT_DAYS),
        }
    return out


# --------------------------------------------------------------------------- the facility event and its declared lag


def facility_event(srf_take_up: Optional[float], fed_repo_material_use: Optional[float]) -> Optional[float]:
    """The facility event on one panel day: 1.0 when the standing facility's take-up is `SRF_MATERIAL_BN` or more, or a
    2019-21 term repo operation was material on its own operation date (`fed_repo_material_use`, 1.0), else 0.0. The amount is
    not an input. A reading that is missing counts as an event only if the other says so; with no event and a missing reading
    the day is missing."""
    if (srf_take_up is not None and srf_take_up >= SRF_MATERIAL_BN) or (
        fed_repo_material_use is not None and fed_repo_material_use >= 1.0
    ):
        return 1.0
    if srf_take_up is None or fed_repo_material_use is None:
        return None
    return 0.0


def facility_series(srf_take_up: Sequence[Optional[float]], fed_repo_material_use: Sequence[Optional[float]]) -> list:
    """`facility_event` on every panel day. Raises ValueError when the two series are not the same length."""
    if len(srf_take_up) != len(fed_repo_material_use):
        raise ValueError(f"srf_take_up has {len(srf_take_up)} days, fed_repo_material_use {len(fed_repo_material_use)}")
    return [facility_event(a, b) for a, b in zip(srf_take_up, fed_repo_material_use)]


def check_declared_facility_lag(registry: Mapping, dates: Sequence[date]) -> None:
    """Every field of the facility event is declared public on the next business day at 16:00: not earlier, not later.

    `dates` is a calendar without market holidays; the last row has no next day and is skipped.

    Raises:
        LookAheadError: a day is declared public before the next business day's 16:00.
        StaleReadError: a day is declared public after it.
    """
    for source, field in declaration.FIELDS[FACILITY_EVENT]:
        for position in range(len(dates) - 1):
            published = datetime.combine(dates[position + 1], FACILITY_PUBLISH_TIME)
            declared = declared_availability(registry, source, field, dates, position)
            if declared < published:
                raise LookAheadError(
                    f"{source}.{field} for {dates[position]} is declared available at {declared}, before {published}")
            if declared > published:
                raise StaleReadError(
                    f"{source}.{field} for {dates[position]} is declared available at {declared}, later than {published}")


# --------------------------------------------------------------------------- the fails declaration against its schedule


def published_fails_instant(as_of: date) -> datetime:
    """When the New York Fed publishes the fails for the Wednesday `as_of`: the Thursday of the following week, 16:30.

    Raises:
        ValueError: `as_of` is not a Wednesday.
    """
    if as_of.weekday() != 2:
        raise ValueError(f"{as_of} is not a Wednesday; the Primary Dealer Statistics are as of Wednesdays")
    return datetime.combine(as_of + timedelta(days=FAILS_PUBLISH_DAYS_AFTER_WEDNESDAY), FAILS_PUBLISH_TIME)


def check_declared_fails_lag(entry: Mapping, dates: Sequence[date]) -> None:
    """Every Wednesday row of `dates` is declared public at its published instant: not earlier, and not later.

    `dates` is a calendar without market holidays, so that six panel rows after a Wednesday is the published Thursday; a
    week whose published Thursday is not a panel row is skipped.

    Raises:
        LookAheadError: a week is declared public before the schedule publishes it.
        StaleReadError: a week is declared public after it.
    """
    registry = {FAILS_SOURCE: entry}
    for position, day in enumerate(dates):
        if day.weekday() != 2:
            continue
        published = published_fails_instant(day)
        if published.date() not in dates:
            continue
        for field in entry["fields"]:
            declared = declared_availability(registry, FAILS_SOURCE, field, dates, position)
            if declared < published:
                raise LookAheadError(
                    f"{field} for the week of {day} is declared available at {declared}, before its published {published}")
            if declared > published:
                raise StaleReadError(
                    f"{field} for the week of {day} is declared available at {declared}, later than its published {published}")


# --------------------------------------------------------------------------- the 30 June 2027 break


def touches_break(dates: Sequence[date], start: int) -> bool:
    """The window starting at `start` (its baseline and its days) has a day on or after `BREAK_DATE`."""
    first = max(start - attribution.BASELINE_DAYS, 0)
    return any(day >= BREAK_DATE for day in dates[first : start + attribution.WINDOW_DAYS])


def mask_across_break(series: attribution.Series, dates: Sequence[date]) -> Dict[str, list]:
    """A copy of `series` whose `BREAK_DRIVERS` columns are missing on and after `BREAK_DATE`. Every other column is copied
    unchanged and the input is not modified. A window with a missing day has no change, so the fitting sample drops it.

    Raises:
        ValueError: `dates` and the series are not the same length.
    """
    out = {name: list(values) for name, values in series.items()}
    for name, values in out.items():
        if len(values) != len(dates):
            raise ValueError(f"{name} has {len(values)} days, the dates {len(dates)}")
    for name in BREAK_DRIVERS:
        if name in out:
            out[name] = [None if day >= BREAK_DATE else v for v, day in zip(out[name], dates)]
    return out


def break_refusal(dates: Sequence[date], start: int, drivers: Sequence[str] = DRIVERS_2) -> Optional[Attribution]:
    """"Not attributable", with the reason, for an onset whose window touches the break and whose driver set reads a
    series that the break breaks; None otherwise. Never dropped."""
    if any(name in BREAK_DRIVERS for name in drivers) and touches_break(dates, start):
        return Attribution(start, "not attributable", BREAK_REASON)
    return None


def attribute_2(series: attribution.Series, start: int, *, dates: Sequence[date], drivers: Sequence[str] = DRIVERS_2,
                **settings) -> Attribution:
    """`attribution.attribute` with the break applied: the break series are masked from `BREAK_DATE` on, and an onset whose
    window touches the break is "not attributable" for them, with the reason. `settings` are `attribute`'s (`rule`,
    `report_index`, `draws`, `seed`). `report_index` defaults to `report_index_2` (`REPORT_DAYS_2`), and an onset whose report
    day is past the sample is "not attributable" with that reason. Step 2 calls this; step 1 only tests the break."""
    refused = break_refusal(dates, start, drivers)
    if refused is not None:
        return refused
    if settings.get("report_index") is None:
        try:
            settings["report_index"] = report_index_2(start, len(dates))
        except ValueError as error:
            return Attribution(start, "not attributable", str(error))
    return attribution.attribute(mask_across_break(series, dates), start, dates=dates, drivers=drivers, **settings)
