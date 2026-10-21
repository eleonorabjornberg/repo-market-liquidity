#!/usr/bin/env python3
"""H7m, groundwork G6: the power study for goalpost 3 (`docs/stages/h7-g6.md`, declared before any number).

This is the second record (directive #106; `docs/stages/h7-g6.md` §9 and §10). The first is archived in
`archive/h7m-power-study-1/`.

    PYTHONPATH=src python3 scripts/g6_power_study.py            # writes docs/research/h7m-power-study-2.json
    PYTHONPATH=src python3 scripts/g6_power_study.py --smoke    # three windows per length, 2,000 draws, prints only
    PYTHONPATH=src python3 scripts/g6_power_study.py --tables   # prints the markdown tables of the recorded study

The third record (directive #126; `docs/stages/h7-g6.md` §11) re-declares Part B with a calendar-tied event process, fresh seeds
and power-raising options. It runs on Eleonora's Mac, never in the cloud, and never as a smoke run on the real days:

    PYTHONPATH=src python3 scripts/g6_power_study.py --third --process independent   # docs/research/h7m-power-study-3.independent.json
    PYTHONPATH=src python3 scripts/g6_power_study.py --third --process two_state
    PYTHONPATH=src python3 scripts/g6_power_study.py --third --process calendar
    PYTHONPATH=src python3 scripts/g6_power_study.py --third --assemble              # writes docs/research/h7m-power-study-3.json
    PYTHONPATH=src python3 scripts/g6_power_study.py --third --tables                # prints the markdown tables of the third record

The estimate is R plus a planted signal. No candidate (A, B, step 1's estimator, C) is scored. Development evidence only.
"""

import argparse
import hashlib
import json
import multiprocessing
import random
import sys
import tempfile
import time as clock
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "research"

from repo_model import fed_liquidity, measurement_fields, scarcity  # noqa: E402
from repo_model.asof import InformationRule  # noqa: E402
from repo_model.data import load_daily_panel  # noqa: E402
from repo_model.metrics import stationary_bootstrap_indices  # noqa: E402

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, goalposts as gp, h7_estimator, panel, parent_root  # noqa: E402

SEED = gp.STUDY_SEED
STEP = 20
GRID = (0.0, 0.02, 0.035, 0.05, 0.065, 0.08, 0.10, 0.125, 0.15)
POWER_TARGET = 0.80
RECORD = RESULTS / "h7m-power-study-2.json"

#: `docs/stages/h7-g6.md` §10 (Part B), declared before any run of it.
PART_B_FROM = date(2025, 1, 1)
PART_B_LENGTH = 250
PART_B_LOOK = 2
PART_B_REPLICATES = 400
PART_B_FLOOR_SERIES = 2000
PART_B_FLOOR_DAYS = 1000
PART_B_FLOOR_SEED = SEED + 100000
PART_B_REFERENCE_SERIES = 200
PART_B_REFERENCE_SEED = SEED + 200000

#: `docs/stages/h7-g6.md` §11, declared before any number of the third record. The base no earlier record used (§11.2).
THIRD_SEED = 2026101900
THIRD_RECORD = RESULTS / "h7m-power-study-3.json"
THIRD_LENGTHS = (250, 500, 750)
THIRD_PROCESSES = ("independent", "two_state", "calendar")
THIRD_TESTS = ("section5", "calendar_strata")
THIRD_REPLICATES = 400
THIRD_REFERENCE = 200
THIRD_FLOOR_SERIES = 2000
THIRD_FLOOR_DAYS = 1000
THIRD_LOOK = 2
THIRD_FROM = PART_B_FROM

_DATA = {}


def load(calendar=None):
    """The labelled days: R and S through the as-of rule, the event from the parent's `fed_liquidity`.

    A dict passed as `calendar` is filled with each panel day's `goalposts.Calendar` (`docs/stages/h7-g6.md` §11.3), for
    each labelled day; a hole in a calendar column on a labelled day is a data error.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        manifest = panel.build(path, version=1)
        recorded = panel.load_manifest(version=1)
        if manifest["sha256"] != recorded["sha256"]:
            raise ValueError(f"panel version 1 rebuilt to {manifest['sha256']}, not its manifest's {recorded['sha256']}")
        rows = load_daily_panel(path)
    snapshots = parent_root() / "tests" / "fixtures" / "snapshots" / "repo_ops_inputs"
    coverage_end = fed_liquidity.declared_coverage_end(fed_liquidity.NYFED_REPO_OPS_SOURCE_ID)
    assembled, summary = fed_liquidity.assemble(rows, snapshots, cutoff=datetime.fromisoformat(manifest["build_cutoff"]),
                                                end=coverage_end)
    accepted = {row.date: row.values.get("fed_repo_accepted") for row in assembled}
    with scarcity.measurement_declaration():
        rule = InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)
        days = h7_estimator.asof_days(rows, rule)
    # Days after the labels' end are read for R and S but carry no label: they are dropped, not scored, and counted.
    labelled = gp.labelled_days(days, accepted)
    if calendar is not None:
        values = {row.date: row.values for row in rows}
        calendar.update({d.day: gp.calendar_flags(d.day, values[d.day]) for d in labelled.days})
    return labelled, {"panel_sha256": manifest["sha256"], "panel_rows": len(rows), "panel_last_day": rows[-1].date.isoformat(),
                      "repo_operation_coverage_end": coverage_end.isoformat(), "assemble": summary}


def _supported(test):
    """§4 and `docs/stages/h7-g6.md` §9 point 1: the lower bound above 0, the point at the MME, 10 events in the window."""
    return bool(test.lower > 0.0 and test.point >= gp.MME and test.window_events >= gp.EVENT_FLOOR)


def _outcome(test):
    return {"point": test.point, "lower": test.lower, "window_events": test.window_events, "usable_events": test.events,
            "strata": test.strata, "dropped": test.dropped, "supported": _supported(test)}


def _test(estimate, ratio, state, event, *, look, seed, indices):
    smoke = _DATA["smoke"]
    return gp.information_test(estimate, ratio, state, event, look=look if not smoke or look else 1, seed=seed,
                               indices=indices)


def _window_task(task):
    length, look, start = task
    labelled, sigma, shifts, smoke = _DATA["labelled"], _DATA["sigma"], _DATA["shifts"], _DATA["smoke"]
    days = labelled[start:start + length]
    ratio, state, event = [d.ratio for d in days], [d.state for d in days], [d.event for d in days]
    seed = gp.window_seed(start)
    draws = 2000 if smoke else gp.draws_for(look)
    rng = random.Random(seed)
    indices = [stationary_bootstrap_indices(length, gp.BLOCK_LENGTH, rng) for _ in range(draws)]
    out = {}
    for target, c in shifts.items():
        estimate = gp.plant(ratio, event, c, sigma=sigma, seed=seed)
        out[target] = _outcome(_test(estimate, ratio, state, event, look=look, seed=seed, indices=indices))
    return {"length": length, "start": start, "first_day": days[0].day.isoformat(), "events": sum(event), "results": out}


def _replicate_task(k):
    """Part B (`docs/stages/h7-g6.md` §10): replicate `k`'s 250 real-R days with a simulated event series."""
    days, sigma, shifts, smoke, process = (_DATA["span"], _DATA["sigma"], _DATA["shifts_b"], _DATA["smoke"],
                                          _DATA["process"])
    seed = gp.window_seed(k)
    event = gp.simulate_events(process, PART_B_LENGTH, random.Random(f"events:{seed}"))
    ratio, state = [d.ratio for d in days], [d.state for d in days]
    draws = 2000 if smoke else gp.draws_for(PART_B_LOOK)
    rng = random.Random(seed)
    indices = [stationary_bootstrap_indices(PART_B_LENGTH, gp.BLOCK_LENGTH, rng) for _ in range(draws)]
    out = {}
    for target, c in shifts.items():
        estimate = gp.plant(ratio, event, c, sigma=sigma, seed=seed)
        out[target] = _outcome(_test(estimate, ratio, state, event, look=PART_B_LOOK, seed=seed, indices=indices))
    return {"replicate": k, "events": sum(event), "results": out}


def _reading(supported, count, length, step):
    """A supported count with its share, interval and effective windows (`goalposts.power`); None where nothing is counted."""
    if not count:
        return {"supported": supported, "windows": 0, "share": None, "interval": None, "effective_windows": None}
    p = gp.power(supported, count, length, step)
    return {"supported": supported, "windows": count, "share": p.share, "interval": [p.low, p.high],
            "effective_windows": p.effective}


def _smallest_at_80(row, key):
    power = {float(t): g[key]["share"] for t, g in row["gains"].items()}
    reaching = [t for t, p in sorted(power.items()) if t > 0 and p is not None and p >= POWER_TARGET]
    return power, (reaching[0] if reaching else None)


def run(smoke):
    labelled, provenance = load()
    days = labelled.days
    ratio, state, event = [d.ratio for d in days], [d.state for d in days], [d.event for d in days]
    sigma = gp.sd(ratio)
    shifts, realised = {}, {}
    for target in GRID:
        c = gp.calibrate(target, ratio, state, event, sigma=sigma, seed=SEED)
        if c is None:
            realised[str(target)] = None
            continue
        shifts[target] = c
        gain = gp.stratified_gain(gp.plant(ratio, event, c, sigma=sigma, seed=SEED), ratio, state, event).value
        realised[str(target)] = {"gain": gain, "miss": gain - target}
    _DATA.update(labelled=days, sigma=sigma, shifts=shifts, smoke=smoke)

    tasks = []
    for look, length in enumerate(gp.LOOKS):
        starts = [s for s, _ in gp.windows(len(days), length, STEP)]
        tasks += [(length, look, s) for s in (starts[:3] if smoke else starts)]
    began = clock.time()
    with multiprocessing.get_context("fork").Pool(4) as pool:
        windows = pool.map(_window_task, tasks, chunksize=1)

    def era_of(w):
        return gp.era(days[w["start"]].day)

    def spread(values):
        values = sorted(values)
        return {"min": values[0], "median": median(values), "max": values[-1]}

    table = []
    for length in gp.LOOKS:
        mine = [w for w in windows if w["length"] == length]
        for scope in ("pooled",) + gp.ERAS:
            group = mine if scope == "pooled" else [w for w in mine if era_of(w) == scope]
            if not group:
                table.append({"length": length, "era": scope, "windows": 0})
                continue
            at_floor = [w for w in group if w["events"] >= gp.EVENT_FLOOR]
            row = {"length": length, "era": scope, "windows": len(group),
                   "effective_windows": gp.effective_windows(len(group), length, STEP),
                   "events_per_window": spread([w["events"] for w in group]),
                   "usable_events_per_window": spread([next(iter(w["results"].values()))["usable_events"] for w in group]),
                   "windows_at_the_event_floor": len(at_floor),
                   "effective_windows_at_the_event_floor": gp.effective_windows(len(at_floor), length, STEP),
                   "gains": {}}
            for target in shifts:
                results = [w["results"][target] for w in group]
                floor_results = [w["results"][target] for w in at_floor]
                row["gains"][str(target)] = {
                    "all_windows": _reading(sum(r["supported"] for r in results), len(results), length, STEP),
                    "windows_at_the_floor": _reading(sum(r["supported"] for r in floor_results), len(floor_results),
                                                     length, STEP),
                    "lower_above_zero": sum(r["lower"] > 0.0 for r in results) / len(results),
                    "point_at_or_above_mme": sum(r["point"] >= gp.MME for r in results) / len(results),
                    "mean_point": sum(r["point"] for r in results) / len(results)}
            table.append(row)

    detectable = {}
    for scope in ("pooled",) + gp.ERAS:
        row = next((r for r in table if r["length"] == gp.LOOKS[-1] and r["era"] == scope), None)
        if not row or not row["windows"]:
            detectable[scope] = None
            continue
        entry = {}
        for key in ("all_windows", "windows_at_the_floor"):
            power, smallest = _smallest_at_80(row, key)
            mme = row["gains"][str(gp.MME)][key]
            entry[key] = {"mme_power": power.get(gp.MME), "mme_interval": mme["interval"], "windows": mme["windows"],
                          "mme_detectable": None if power.get(gp.MME) is None else power[gp.MME] >= POWER_TARGET,
                          "smallest_grid_gain_at_80": smallest}
        detectable[scope] = entry

    floors = defaultdict(list)
    for start in range(0, len(days), STEP):
        floors[gp.era(days[start].day)].append(gp.days_to_events(event, start))
    to_floor = {}
    for scope in gp.ERAS:
        values = floors.get(scope, [])
        reached = sorted(v for v in values if v is not None)
        to_floor[scope] = {"starts": len(values), "never_reached": len(values) - len(reached),
                           "median": median(reached) if reached else None,
                           "p90": reached[int(0.9 * (len(reached) - 1))] if reached else None}

    part_b = run_part_b(days, sigma, shifts, smoke)

    return {
        "what": "H7m G6, second record: power of goalpost 3 on development data, by replay of R plus a planted signal "
                "(docs/stages/h7-g6.md §9 and §10). No candidate is scored. Development evidence, never a verdict.",
        "smoke": smoke,
        "pins": {"parent": PARENT_COMMIT, "panel_digest": PANEL_SHA256},
        "provenance": provenance,
        "days": {"scored": len(days), "first": days[0].day.isoformat(), "last": days[-1].day.isoformat(),
                 "events": sum(event), "dropped": labelled.dropped,
                 "events_by_era": {e: sum(d.event for d in days if gp.era(d.day) == e) for e in gp.ERAS},
                 "days_by_era": {e: sum(gp.era(d.day) == e for d in days) for e in gp.ERAS}},
        "declaration": {"seed": SEED, "seed_rule": "20261014 + the window's first index", "step": STEP,
                        "grid": list(GRID), "lengths": list(gp.LOOKS),
                        "draws": {str(n): (2000 if smoke else gp.draws_for(i)) for i, n in enumerate(gp.LOOKS)},
                        "nominal_levels": {str(n): gp.nominal_level(i) for i, n in enumerate(gp.LOOKS)},
                        "block_length": gp.BLOCK_LENGTH, "mme": gp.MME, "event_floor": gp.EVENT_FLOOR,
                        "event_floor_counts": "events in the window",
                        "calibration_tolerance": gp.CALIBRATION_TOLERANCE,
                        "noise_sd_in_sigma": gp.NOISE_SD, "sigma": sigma},
        "planting": {"shift_in_sigma": {str(t): c for t, c in shifts.items()}, "realised_gain_on_the_whole_span": realised},
        "power": table,
        "detectable_at_250_days": detectable,
        "days_to_the_event_floor": to_floor,
        "part_b": part_b,
        "windows": windows,
        "seconds": round(clock.time() - began, 1),
    }


def _reference_cases(span, process, count):
    """`docs/stages/h7-g6.md` §10: the series Part B's shifts are calibrated on, none of them a replicate."""
    ratio, state = [d.ratio for d in span], [d.state for d in span]
    cases = []
    for j in range(count):
        seed = PART_B_REFERENCE_SEED + j
        cases.append(gp.CalibrationCase(ratio, state, gp.simulate_events(process, len(span), random.Random(f"events:{seed}")),
                                        seed))
    return cases


def run_part_b(days, sigma, grid_shifts, smoke):
    """`docs/stages/h7-g6.md` §10: the clustered event process fitted to 2025-01-01 on, days to the floor, power at 250 days."""
    span = [d for d in days if d.day >= PART_B_FROM]
    if len(span) < PART_B_LENGTH:
        raise ValueError(f"{len(span)} labelled days from {PART_B_FROM}, fewer than the {PART_B_LENGTH} Part B needs")
    process = gp.fit_event_process([d.event for d in span])
    series = 50 if smoke else PART_B_FLOOR_SERIES
    reaching = []
    for k in range(series):
        simulated = gp.simulate_events(process, PART_B_FLOOR_DAYS, random.Random(PART_B_FLOOR_SEED + k))
        reaching.append(gp.days_to_events(simulated, 0))
    reached = sorted(v for v in reaching if v is not None)
    to_floor = {"series": series, "days_per_series": PART_B_FLOOR_DAYS, "never_reached": series - len(reached),
                "share_never_reached": (series - len(reached)) / series,
                "share_reached_within_250": sum(v <= 250 for v in reached) / series,
                "mean_of_those_that_reach": sum(reached) / len(reached) if reached else None,
                "median_of_those_that_reach": median(reached) if reached else None,
                "p90_of_those_that_reach": reached[int(0.9 * (len(reached) - 1))] if reached else None}

    fitted_on = span
    span = span[:PART_B_LENGTH]
    cases = _reference_cases(span, process, 20 if smoke else PART_B_REFERENCE_SERIES)
    shifts, realised = {}, {}
    for target in grid_shifts:
        c = gp.calibrate_over(target, cases, sigma=sigma)
        if c is None:
            realised[str(target)] = None
            continue
        shifts[target] = c
        mean = sum(gp.stratified_gain(gp.plant(x.ratio, x.event, c, sigma=sigma, seed=x.seed), x.ratio, x.state,
                                      x.event).value for x in cases) / len(cases)
        realised[str(target)] = {"mean_gain": mean, "miss": mean - target}
    _DATA.update(span=span, process=process, shifts_b=shifts)
    replicates = 12 if smoke else PART_B_REPLICATES
    with multiprocessing.get_context("fork").Pool(4) as pool:
        results = pool.map(_replicate_task, range(replicates), chunksize=1)
    at_floor = [r for r in results if r["events"] >= gp.EVENT_FLOOR]
    gains = {}
    for target in shifts:
        everything = [r["results"][target] for r in results]
        floor = [r["results"][target] for r in at_floor]
        row = {}
        for key, group in (("all_replicates", everything), ("replicates_at_the_floor", floor)):
            supported = sum(r["supported"] for r in group)
            low, high = gp.wilson(supported, len(group)) if group else (None, None)
            row[key] = {"supported": supported, "replicates": len(group),
                        "share": supported / len(group) if group else None, "interval": [low, high]}
        row["mean_point"] = sum(r["point"] for r in everything) / len(everything)
        row["point_at_or_above_mme"] = sum(r["point"] >= gp.MME for r in everything) / len(everything)
        gains[str(target)] = row
    events = sorted(r["events"] for r in results)
    return {"process": {"calibration_window": [fitted_on[0].day.isoformat(), fitted_on[-1].day.isoformat()],
                        "days": len(fitted_on), "events": sum(d.event for d in fitted_on), "start": process.start, "stay": process.stay,
                        "stationary": process.stationary,
                        "transitions_from_quiet": process.transitions_from_quiet,
                        "transitions_from_event": process.transitions_from_event},
            "days_to_the_event_floor": to_floor,
            "planting": {"reference_series": len(cases), "shift_in_sigma": {str(t): c for t, c in shifts.items()},
                         "mean_gain_on_the_reference_series": realised},
            "power_at_250_days": {"first_day": span[0].day.isoformat(), "replicates": replicates, "draws":
                                  2000 if smoke else gp.draws_for(PART_B_LOOK), "replicates_at_the_event_floor": len(at_floor),
                                  "events_per_replicate": {"min": events[0], "median": median(events), "max": events[-1]},
                                  "gains": gains}}


# -- the third record (`docs/stages/h7-g6.md` §11) ---------------------------------------------------------------------


def third_days(days, length, *, baseline=THIRD_LENGTHS[0]):
    """§11.4 option (i): the baseline length is the first `length` labelled days from 2025-01-02, exactly as in §10; a longer
    one is the last `length` labelled days, because fewer than 500 labelled days exist from 2025-01-02.

    Raises:
        ValueError: if there are fewer than `length` such days.
    """
    span = [d for d in days if d.day >= THIRD_FROM][:length] if length == baseline else list(days[-length:])
    if len(span) < length:
        raise ValueError(f"{len(span)} labelled days for a window of {length}")
    return span


def _flags(span, calendar):
    missing = [d.day for d in span if d.day not in calendar]
    if missing:
        raise ValueError(f"no calendar row for {missing[0]} (and {len(missing) - 1} more labelled days)")
    return [calendar[d.day] for d in span]


def _third_events(name, process, flags, n, seed):
    """`n` simulated event indicators for the process `name`, from the separate stream of §11.2."""
    rng = random.Random(f"events:{name}:{seed}")
    if name == "calendar":
        return gp.simulate_calendar_events(process, flags[:n], rng)
    return gp.simulate_events(process, n, rng)


_CLASSES = {"none": gp.Calendar(0, 0, 0, 0), "coupon_mid": gp.Calendar(1, 0, 0, 0), "coupon_end": gp.Calendar(0, 1, 0, 0),
            "quarter_end": gp.Calendar(0, 1, 1, 0), "year_end": gp.Calendar(0, 1, 1, 1)}


def _third_fit(name, fit_days, fit_flags):
    """The process `name` fitted to the labelled days of the fitting window (§11.3), and the record of its fit."""
    event = [d.event for d in fit_days]
    base = {"calendar_window": [fit_days[0].day.isoformat(), fit_days[-1].day.isoformat()], "days": len(event),
            "events": sum(event)}
    if name == "independent":
        process = gp.independent_process(event)
        return process, {**base, "share": process.start}
    if name == "two_state":
        process = gp.fit_event_process(event)
        return process, {**base, "start": process.start, "stay": process.stay, "stationary": process.stationary,
                         "transitions_from_quiet": process.transitions_from_quiet,
                         "transitions_from_event": process.transitions_from_event}
    process = gp.fit_calendar_process(event, fit_flags)
    implied = {f"previous_{state}": {label: process.probability(previous, flags) for label, flags in _CLASSES.items()}
               for previous, state in ((0, "quiet"), (1, "event"))}
    return process, {**base, "coefficients": list(process.coefficients),
                     "coefficient_names": ["intercept", "previous_event", "coupon_mid", "coupon_end", "quarter_end",
                                           "year_end"], "ridge": process.ridge, "pairs": process.pairs,
                     "share": process.share, "implied_probabilities": implied}


def _third_replicate(task):
    """One replicate of one cell: the planted estimate at each grid gain, tested by both tests on shared resamples."""
    key, k = task
    ctx, draws = _DATA["third"][key], _DATA["third_draws"]
    seed = THIRD_SEED + k
    event = _third_events(ctx["name"], ctx["process"], ctx["flags"], len(ctx["ratio"]), seed)
    rng = random.Random(seed)
    indices = [stationary_bootstrap_indices(len(ctx["ratio"]), gp.BLOCK_LENGTH, rng) for _ in range(draws)]
    out = {}
    for target, c in ctx["shifts"].items():
        estimate = gp.plant(ctx["ratio"], event, c, sigma=ctx["sigma"], seed=seed)
        out[target] = {test: _outcome(gp.information_test(estimate, ctx["ratio"], state, event, look=THIRD_LOOK, seed=seed,
                                                           indices=indices))
                       for test, state in (("section5", ctx["state"]), ("calendar_strata", ctx["strata"]))}
    return {"replicate": k, "events": sum(event), "results": out}


def _third_rows(results, at_floor, shifts):
    """Per grid gain and test: the two readings with their counts and Wilson intervals (§11.5)."""
    tests = {}
    for test in THIRD_TESTS:
        rows = {}
        for target in shifts:
            everything = [r["results"][target][test] for r in results]
            floor = [r["results"][target][test] for r in at_floor]
            row = {}
            for key, group in (("all_replicates", everything), ("replicates_at_the_floor", floor)):
                supported = sum(r["supported"] for r in group)
                low, high = gp.wilson(supported, len(group)) if group else (None, None)
                row[key] = {"supported": supported, "replicates": len(group),
                            "share": supported / len(group) if group else None, "interval": [low, high]}
            row["mean_point"] = sum(r["point"] for r in everything) / len(everything)
            row["point_at_or_above_mme"] = sum(r["point"] >= gp.MME for r in everything) / len(everything)
            row["mean_strata"] = sum(r["strata"] for r in everything) / len(everything)
            row["mean_dropped"] = sum(r["dropped"] for r in everything) / len(everything)
            rows[str(target)] = row
        tests[test] = {"gains": rows}
    return tests


def _third_floor(name, process, fit_flags, series, length):
    """§11.5: days until 10 events are logged, on `series` simulated series of `length` days from day 0 of the fitting window."""
    cycled = [fit_flags[i % len(fit_flags)] for i in range(length)]
    reaching = [gp.days_to_events(_third_events(name, process, cycled, length, THIRD_SEED + 100000 + k), 0)
                for k in range(series)]
    reached = sorted(v for v in reaching if v is not None)
    return {"series": series, "days_per_series": length, "never_reached": series - len(reached),
            "share_never_reached": (series - len(reached)) / series,
            "share_reached_within_250": sum(v <= 250 for v in reached) / series,
            "mean_of_those_that_reach": sum(reached) / len(reached) if reached else None,
            "median_of_those_that_reach": median(reached) if reached else None,
            "p90_of_those_that_reach": reached[int(0.9 * (len(reached) - 1))] if reached else None}


def run_third(days, calendar, *, processes=THIRD_PROCESSES, lengths=THIRD_LENGTHS, baseline=None, grid=GRID,
              replicates=THIRD_REPLICATES, reference=THIRD_REFERENCE, floor_series=THIRD_FLOOR_SERIES,
              floor_days=THIRD_FLOOR_DAYS, draws=None, workers=4, provenance=None):
    """`docs/stages/h7-g6.md` §11: the labelled `days` and their `calendar`, for each process and window length.

    Raises:
        ValueError: if a labelled day has no calendar row, or a window has too few days.
    """
    began = clock.time()
    baseline = lengths[0] if baseline is None else baseline
    draws = gp.draws_for(THIRD_LOOK) if draws is None else draws
    sigma = gp.sd([d.ratio for d in days])
    fit_days = [d for d in days if d.day >= THIRD_FROM]
    fit_flags = _flags(fit_days, calendar)
    entries, contexts = {}, {}
    for name in processes:
        process, fit = _third_fit(name, fit_days, fit_flags)
        entries[name] = {"fit": fit, "days_to_the_event_floor": _third_floor(name, process, fit_flags, floor_series,
                                                                              floor_days), "cells": {}}
        for length in lengths:
            span = third_days(days, length, baseline=baseline)
            flags = _flags(span, calendar)
            ratio, state = [d.ratio for d in span], [d.state for d in span]
            cases = [gp.CalibrationCase(ratio, state, _third_events(name, process, flags, length,
                                                                    THIRD_SEED + 200000 + j), THIRD_SEED + 200000 + j)
                     for j in range(reference)]
            shifts, realised = {}, {}
            for target in grid:
                c = gp.calibrate_over(target, cases, sigma=sigma)
                if c is None:
                    realised[str(target)] = None
                    continue
                shifts[target] = c
                mean = sum(gp.stratified_gain(gp.plant(x.ratio, x.event, c, sigma=sigma, seed=x.seed), x.ratio, x.state,
                                              x.event).value for x in cases) / len(cases)
                realised[str(target)] = {"mean_gain": mean, "miss": mean - target}
            contexts[(name, length)] = {"name": name, "process": process, "flags": flags, "ratio": ratio, "state": state,
                                        "strata": gp.calendar_strata(state, flags), "sigma": sigma, "shifts": shifts}
            entries[name]["cells"][str(length)] = {
                "length": length, "first_day": span[0].day.isoformat(), "last_day": span[-1].day.isoformat(),
                "days": len(span), "planting": {"reference_series": len(cases),
                                                "shift_in_sigma": {str(t): c for t, c in shifts.items()},
                                                "mean_gain_on_the_reference_series": realised}}
    _DATA.update(third=contexts, third_draws=draws)
    tasks = [((name, length), k) for name in processes for length in lengths for k in range(replicates)]
    if workers > 1:
        with multiprocessing.get_context("fork").Pool(workers) as pool:
            done = pool.map(_third_replicate, tasks, chunksize=1)
    else:
        done = [_third_replicate(task) for task in tasks]
    for (key, _), result in zip(tasks, done):
        entries[key[0]]["cells"][str(key[1])].setdefault("_results", []).append(result)
    for name in processes:
        for cell in entries[name]["cells"].values():
            results = cell.pop("_results")
            at_floor = [r for r in results if r["events"] >= gp.EVENT_FLOOR]
            events = sorted(r["events"] for r in results)
            shifts = contexts[(name, cell["length"])]["shifts"]
            cell.update({"replicates": len(results), "replicates_at_the_event_floor": len(at_floor),
                         "events_per_replicate": {"min": events[0], "median": median(events), "max": events[-1]},
                         "tests": _third_rows(results, at_floor, shifts)})
    return {
        "what": "H7m G6, third record: Part B re-declared with a calendar-tied event process, fresh seeds and power-raising "
                "options (docs/stages/h7-g6.md §11). No candidate is scored. Development evidence, never a verdict.",
        "smoke": False,
        "pins": {"parent": PARENT_COMMIT, "panel_digest": PANEL_SHA256},
        "provenance": provenance or {},
        "days": {"scored": len(days), "first": days[0].day.isoformat(), "last": days[-1].day.isoformat(),
                 "events": sum(d.event for d in days)},
        "declaration": {"seed": THIRD_SEED, "seed_rule": "2026101900 + the replicate's index; +100000 days to the floor; "
                                                         "+200000 reference series",
                        "grid": list(grid), "lengths": list(lengths), "baseline_length": baseline,
                        "tests": list(THIRD_TESTS), "processes": list(THIRD_PROCESSES), "look": THIRD_LOOK,
                        "draws": draws, "nominal_level": gp.nominal_level(THIRD_LOOK), "block_length": gp.BLOCK_LENGTH,
                        "mme": gp.MME, "event_floor": gp.EVENT_FLOOR, "event_floor_counts": "events in the window",
                        "replicates": replicates, "reference_series": reference, "floor_series": floor_series,
                        "floor_days": floor_days, "ridge": gp.RIDGE, "calibration_tolerance": gp.CALIBRATION_TOLERANCE,
                        "noise_sd_in_sigma": gp.NOISE_SD, "sigma": sigma},
        "processes": entries,
        "seconds": round(clock.time() - began, 1),
    }


def assemble_third(parts):
    """The third record from its per-process parts, in the declared order.

    Raises:
        ValueError: if a process is missing or repeated, or the parts differ in pins, provenance, days or declaration.
    """
    names = [name for part in parts for name in part["processes"]]
    if sorted(names) != sorted(THIRD_PROCESSES):
        raise ValueError(f"the third record needs one part per process {THIRD_PROCESSES}, got {names}")
    first = parts[0]
    for part in parts[1:]:
        for key in ("pins", "provenance", "days"):
            if part[key] != first[key]:
                raise ValueError(f"the parts differ in {key!r}: they were not made from the same tree")
        if {**part["declaration"], "processes": None} != {**first["declaration"], "processes": None}:
            raise ValueError("the parts differ in their declaration")
    out = {key: first[key] for key in ("what", "smoke", "pins", "provenance", "days", "declaration")}
    by_name = {name: part["processes"][name] for part in parts for name in part["processes"]}
    out["processes"] = {name: by_name[name] for name in THIRD_PROCESSES}
    out["seconds"] = round(sum(part["seconds"] for part in parts), 1)
    return out


def tables_third(record):
    """The markdown tables of the third record (`docs/stages/h7-g6.md` §11), copied from the record and never recomputed."""
    out = []
    declared = record["declaration"]
    for name, entry in record["processes"].items():
        fit, floor = entry["fit"], entry["days_to_the_event_floor"]
        out += [f"### Process: {name}", "",
                f"Fitted to {fit['calendar_window'][0]} to {fit['calendar_window'][1]} ({fit['days']} labelled days, "
                f"{fit['events']} events): " + ", ".join(
                    f"{k} {v:.4f}" if isinstance(v, float) else f"{k} {v}" for k, v in fit.items()
                    if k not in ("calendar_window", "days", "events", "coefficients", "coefficient_names",
                                 "implied_probabilities")), ""]
        if name == "calendar":
            out += ["| " + " | ".join(fit["coefficient_names"]) + " |", "|" + "---|" * len(fit["coefficient_names"]),
                    "| " + " | ".join(f"{c:+.4f}" for c in fit["coefficients"]) + " |", "",
                    "| Fitted P(event) | " + " | ".join(next(iter(fit["implied_probabilities"].values()))) + " |",
                    "|---|" + "---|" * len(_CLASSES)]
            out += [f"| {state} | " + " | ".join(f"{p:.4f}" for p in row.values()) + " |"
                    for state, row in fit["implied_probabilities"].items()] + [""]
        out += [f"**Days until 10 events are logged** ({floor['series']} simulated series of {floor['days_per_series']} days)",
                "", "| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median | 90th percentile |",
                "|---|---|---|---|---|",
                f"| {_pct(floor['share_never_reached'])} ({floor['never_reached']} of {floor['series']}) | "
                f"{_pct(floor['share_reached_within_250'])} | "
                f"{'none' if floor['mean_of_those_that_reach'] is None else format(floor['mean_of_those_that_reach'], '.1f')} | "
                f"{floor['median_of_those_that_reach']} | {floor['p90_of_those_that_reach']} |", ""]
        for length, cell in entry["cells"].items():
            e = cell["events_per_replicate"]
            out += [f"**{name}, {length} days** ({cell['first_day']} to {cell['last_day']}; {cell['replicates']} replicates, "
                    f"{declared['draws']:,} draws; events per replicate {e['min']} / {e['median']:g} / {e['max']}; "
                    f"{cell['replicates_at_the_event_floor']} replicates hold at least 10). Each cell: supported share "
                    "(supported/replicates; 95% Wilson interval)", "",
                    "| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every "
                    "replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; "
                    "calendar_strata) |", "|---|---|---|---|---|---|"]
            for gain in cell["tests"]["section5"]["gains"]:
                cells = []
                for test in THIRD_TESTS:
                    row = cell["tests"][test]["gains"][gain]
                    for key in ("all_replicates", "replicates_at_the_floor"):
                        r = row[key]
                        cells.append("none" if r["share"] is None else
                                     f"{_pct(r['share'])} ({r['supported']}/{r['replicates']}; {_pct(r['interval'][0])}–"
                                     f"{_pct(r['interval'][1])})")
                a, b = (cell["tests"][t]["gains"][gain] for t in THIRD_TESTS)
                out.append(f"| {gain}{' (size)' if float(gain) == 0.0 else ''} | " + " | ".join(cells) + " | "
                           f"{a['mean_strata']:.1f} / {a['mean_dropped']:.1f}; {b['mean_strata']:.1f} / "
                           f"{b['mean_dropped']:.1f} |")
            planting = cell["planting"]
            out += ["", f"Planting: shifts in sigma on the {planting['reference_series']} reference series " + ", ".join(
                f"{t}: {c:.4f} (miss {planting['mean_gain_on_the_reference_series'][t]['miss']:+.1e})"
                for t, c in planting["shift_in_sigma"].items()), ""]
    return "\n".join(out)


def _pct(value):
    return "n/a" if value is None else f"{100 * value:.0f}%"


def _cell(reading):
    if reading["share"] is None:
        return "none"
    low, high = reading["interval"]
    return f"{_pct(reading['share'])} ({reading['supported']}/{reading['windows']}; {_pct(low)}–{_pct(high)})"


def tables(record):
    """The markdown tables of `docs/research/h7m-power-study-2.md`, copied from the record and never recomputed."""
    out = []
    days = record["days"]
    out += ["| Era (of the day) | Scored days | Events |", "|---|---|---|"]
    out += [f"| {e} | {days['days_by_era'][e]} | {days['events_by_era'][e]} |" for e in gp.ERAS]
    out += [f"| all | {days['scored']} | {days['events']} |", ""]
    gains = [str(g) for g in record["declaration"]["grid"]]
    for length in gp.LOOKS:
        for key, name, count in (("all_windows", "every window", "windows"),
                                 ("windows_at_the_floor", "windows at the floor (10 events in the window)",
                                  "windows_at_the_event_floor")):
            out += [f"**{length}-day windows, {name}.** Each cell: supported share (supported/windows; 95% Wilson "
                    f"interval at the effective number of windows)", "",
                    "| Era of the first day | Windows (effective) | Events in the window (min / median / max) | "
                    "Events in usable strata (min / median / max) | " + " | ".join(f"gain {g}" for g in gains) + " |",
                    "|---|---|---|---|" + "---|" * len(gains)]
            for row in record["power"]:
                if row["length"] != length:
                    continue
                if not row["windows"]:
                    out.append(f"| {row['era']} | 0 | none | none |" + " none |" * len(gains))
                    continue
                e, u = row["events_per_window"], row["usable_events_per_window"]
                if key == "all_windows":
                    shown = f"{row['windows']} ({row['effective_windows']:.2f})"
                else:
                    shown = f"{row['windows_at_the_event_floor']} of {row['windows']} " \
                            f"({row['effective_windows_at_the_event_floor']:.2f})"
                out.append(f"| {row['era']} | {shown} | {e['min']} / {e['median']:g} / {e['max']} | {u['min']} / "
                           f"{u['median']:g} / {u['max']} | " + " | ".join(_cell(row["gains"][g][key]) for g in gains) + " |")
            out.append("")
    out += ["**Size** (the supported share at gain 0, pooled over eras; the two readings side by side)", "",
            "| Window | Every window | Windows at the floor | Lower bound above 0 (every window) | Point at or above "
            "the MME (every window) | Mean point (every window) |", "|---|---|---|---|---|---|"]
    for length in gp.LOOKS:
        v = next(r for r in record["power"] if r["length"] == length and r["era"] == "pooled")["gains"]["0.0"]
        out.append(f"| {length} days | {_cell(v['all_windows'])} | {_cell(v['windows_at_the_floor'])} | "
                   f"{_pct(v['lower_above_zero'])} | {_pct(v['point_at_or_above_mme'])} | {v['mean_point']:+.4f} |")
    out += ["", "**Days to 10 events** (observed, from every 20th scored day; era of the start)", "",
            "| Era | Starts | Never reach 10 | Median days | 90th percentile |", "|---|---|---|---|---|"]
    for e, v in record["days_to_the_event_floor"].items():
        out.append(f"| {e} | {v['starts']} | {v['never_reached']} | "
                   f"{'none' if v['median'] is None else format(v['median'], 'g')} | {v['p90']} |")
    out += ["", "**The MME at 250 days** (power at gain 0.05, both readings)", "",
            "| Scope | Every window | Detectable (80%) | Smallest grid gain at 80% | Windows at the floor | Detectable (80%) "
            "| Smallest grid gain at 80% |", "|---|---|---|---|---|---|---|"]
    for scope, v in record["detectable_at_250_days"].items():
        if v is None:
            out.append(f"| {scope} | none | none | none | none | none | none |")
            continue
        cells = []
        for key in ("all_windows", "windows_at_the_floor"):
            r = v[key]
            if r["mme_power"] is None:
                cells += ["none", "none", "none"]
                continue
            low, high = r["mme_interval"]
            cells += [f"{_pct(r['mme_power'])} ({_pct(low)}–{_pct(high)}; {r['windows']} windows)", str(r["mme_detectable"]),
                      str(r["smallest_grid_gain_at_80"] or "none on the grid")]
        out.append(f"| {scope} | " + " | ".join(cells) + " |")
    out += ["", "**Planting: realised gain on the whole span against the target** (tolerance "
            f"{record['declaration']['calibration_tolerance']:g})", "",
            "| Target | Shift (sigma) | Realised gain | Miss |", "|---|---|---|---|"]
    for t, c in record["planting"]["shift_in_sigma"].items():
        r = record["planting"]["realised_gain_on_the_whole_span"][t]
        null = " (the null: tie-breaking noise only)" if float(t) == 0.0 else ""
        out.append(f"| {t}{null} | {c:.6f} | {r['gain']:.6f} | {r['miss']:+.2e} |")
    return "\n".join(out)


def tables_part_b(record):
    """The markdown tables of Part B (`docs/stages/h7-g6.md` §10), copied from the record and never recomputed."""
    b = record["part_b"]
    p, f, w = b["process"], b["days_to_the_event_floor"], b["power_at_250_days"]
    out = ["| Process fitted to | Labelled days | Events | P(event, after a quiet day) | P(event, after an event day) | "
           "Long-run share | Transitions from quiet / event |", "|---|---|---|---|---|---|---|",
           f"| {p['calibration_window'][0]} to {p['calibration_window'][1]} | {p['days']} | {p['events']} | "
           f"{p['start']:.4f} | {p['stay']:.4f} | {p['stationary']:.4f} | {p['transitions_from_quiet']} / "
           f"{p['transitions_from_event']} |", "",
           f"**Days until 10 events are logged**, from day 0 ({f['series']} simulated series of {f['days_per_series']} days)", "",
           "| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median (of those that reach) | "
           "90th percentile (of those that reach) |", "|---|---|---|---|---|",
           f"| {_pct(f['share_never_reached'])} ({f['never_reached']} of {f['series']}) | "
           f"{_pct(f['share_reached_within_250'])} | {f['mean_of_those_that_reach']:.1f} | "
           f"{f['median_of_those_that_reach']:g} | {f['p90_of_those_that_reach']} |", "",
           f"**Power at 250 days** ({w['replicates']} replicates from {w['first_day']}, {w['draws']:,} draws; events per "
           f"replicate {w['events_per_replicate']['min']} / {w['events_per_replicate']['median']:g} / "
           f"{w['events_per_replicate']['max']}; {w['replicates_at_the_event_floor']} replicates hold at least 10). "
           "Each cell: supported share (supported/replicates; 95% Wilson interval at the replicates)", "",
           "| Gain | Every replicate | Replicates at the floor | Point at or above the MME | Mean point |",
           "|---|---|---|---|---|"]
    planting = b["planting"]
    for g, row in w["gains"].items():
        cells = []
        for key in ("all_replicates", "replicates_at_the_floor"):
            r = row[key]
            cells.append("none" if r["share"] is None else
                         f"{_pct(r['share'])} ({r['supported']}/{r['replicates']}; {_pct(r['interval'][0])}–"
                         f"{_pct(r['interval'][1])})")
        out.append(f"| {g}{' (size)' if g == '0.0' else ''} | {cells[0]} | {cells[1]} | "
                   f"{_pct(row['point_at_or_above_mme'])} | {row['mean_point']:+.4f} |")
    out += ["", f"**Planting: mean gain on the {planting['reference_series']} reference series against the target**", "",
            "| Target | Shift (sigma) | Mean gain | Miss |", "|---|---|---|---|"]
    for t, c in planting["shift_in_sigma"].items():
        r = planting["mean_gain_on_the_reference_series"][t]
        null = " (the null)" if float(t) == 0.0 else ""
        out.append(f"| {t}{null} | {c:.6f} | {r['mean_gain']:.6f} | {r['miss']:+.2e} |")
    return "\n".join(out)


def _third_part(name):
    return RESULTS / f"h7m-power-study-3.{name}.json"


def main_third(args):
    """The third record: one process to its part, the parts joined, or the tables printed."""
    if args.tables:
        print(tables_third(json.loads(THIRD_RECORD.read_text(encoding="utf-8"))))
        return 0
    if args.assemble:
        parts = [json.loads(_third_part(name).read_text(encoding="utf-8")) for name in THIRD_PROCESSES]
        record, path = assemble_third(parts), THIRD_RECORD
    else:
        calendar = {}
        labelled, provenance = load(calendar)
        names = (args.process,) if args.process else THIRD_PROCESSES
        record = run_third(labelled.days, calendar, processes=names, provenance=provenance)
        path = _third_part(args.process) if args.process else THIRD_RECORD
    RESULTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    print(path, hashlib.sha256(path.read_bytes()).hexdigest())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--tables", action="store_true", help="print the markdown tables of the recorded study")
    parser.add_argument("--third", action="store_true", help="the third record (docs/stages/h7-g6.md §11); runs on the Mac")
    parser.add_argument("--process", choices=THIRD_PROCESSES, help="with --third: one process, written to its own part")
    parser.add_argument("--assemble", action="store_true", help="with --third: join the three parts into the record")
    args = parser.parse_args(argv)
    if (args.process or args.assemble) and not args.third:
        parser.error("--process and --assemble belong to --third")
    if args.third:
        if args.smoke:
            parser.error("the third record is never run, not even as a smoke run, on the real days outside her Mac run")
        return main_third(args)
    if args.tables:
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        print(tables(record))
        print("\n<!-- part b -->\n")
        print(tables_part_b(record))
        return 0
    record = run(args.smoke)
    if args.smoke:
        print(json.dumps({k: record[k] for k in ("days", "planting", "detectable_at_250_days", "days_to_the_event_floor",
                                                  "part_b", "seconds")}, indent=1, default=str))
        print(tables(record))
        print(tables_part_b(record))
        return 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    print(RECORD, hashlib.sha256(RECORD.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
