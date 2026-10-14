#!/usr/bin/env python3
"""H7m, groundwork G6: the power study for goalpost 3 (`docs/stages/h7-g6.md`, declared before any number).

    PYTHONPATH=src python3 scripts/g6_power_study.py            # writes results/g6/power_study.json
    PYTHONPATH=src python3 scripts/g6_power_study.py --smoke    # three windows per length, 2,000 draws, prints only

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
from datetime import datetime, time
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "g6"

from repo_model import fed_liquidity, measurement_fields, scarcity  # noqa: E402
from repo_model.asof import InformationRule  # noqa: E402
from repo_model.data import load_daily_panel  # noqa: E402
from repo_model.metrics import stationary_bootstrap_indices  # noqa: E402

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, goalposts as gp, h7_estimator, panel, parent_root  # noqa: E402

SEED = 20261014
STEP = 20
GRID = (0.0, 0.02, 0.035, 0.05, 0.065, 0.08, 0.10, 0.125, 0.15)
POWER_TARGET = 0.80

_DATA = {}


def load():
    """The labelled days: R and S through the as-of rule, the event from the parent's `fed_liquidity`."""
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
    return labelled, {"panel_sha256": manifest["sha256"], "panel_rows": len(rows), "panel_last_day": rows[-1].date.isoformat(),
                      "repo_operation_coverage_end": coverage_end.isoformat(), "assemble": summary}


def _window_task(task):
    length, look, start = task
    labelled, sigma, shifts, smoke = _DATA["labelled"], _DATA["sigma"], _DATA["shifts"], _DATA["smoke"]
    days = labelled[start:start + length]
    ratio, state, event = [d.ratio for d in days], [d.state for d in days], [d.event for d in days]
    seed = SEED + start * 10 + look
    draws = 2000 if smoke else gp.draws_for(look)
    rng = random.Random(seed)
    indices = [stationary_bootstrap_indices(length, gp.BLOCK_LENGTH, rng) for _ in range(draws)]
    out = {}
    for target, c in shifts.items():
        estimate = gp.plant(ratio, event, c, sigma=sigma, seed=seed)
        test = gp.information_test(estimate, ratio, state, event, look=look, seed=seed, indices=indices) if not smoke \
            else gp.information_test(estimate, ratio, state, event, look=1 if look == 0 else look, seed=seed, indices=indices)
        out[target] = {"point": test.point, "lower": test.lower, "events": test.events, "strata": test.strata,
                       "dropped": test.dropped,
                       "supported": bool(test.lower > 0.0 and test.point >= gp.MME and test.events >= gp.EVENT_FLOOR)}
    return {"length": length, "start": start, "first_day": days[0].day.isoformat(), "events": sum(event), "results": out}


def _share(rows, key):
    n = len(rows)
    return sum(r[key] for r in rows) / n if n else None


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
        realised[str(target)] = gp.stratified_gain(gp.plant(ratio, event, c, sigma=sigma, seed=SEED), ratio, state, event).value
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

    table = []
    for length in gp.LOOKS:
        mine = [w for w in windows if w["length"] == length]
        for scope in ("pooled",) + gp.ERAS:
            group = mine if scope == "pooled" else [w for w in mine if era_of(w) == scope]
            if not group:
                table.append({"length": length, "era": scope, "windows": 0})
                continue
            n_eff = gp.effective_windows(len(group), length, STEP)
            events = sorted(w["events"] for w in group)
            row = {"length": length, "era": scope, "windows": len(group), "effective_windows": n_eff,
                   "events_per_window": {"min": events[0], "median": median(events), "max": events[-1]},
                   "windows_at_the_event_floor": sum(e >= gp.EVENT_FLOOR for e in events), "gains": {}}
            for target in shifts:
                results = [w["results"][target] for w in group]
                supported = sum(r["supported"] for r in results)
                detected = sum(r["lower"] > 0.0 for r in results)
                at_mme = sum(r["point"] >= gp.MME for r in results)
                testable = [r for r in results if r["events"] >= gp.EVENT_FLOOR]
                low, high = gp.wilson(supported * n_eff / len(group), n_eff)
                row["gains"][str(target)] = {
                    "supported": supported / len(group), "supported_interval": [low, high],
                    "lower_above_zero": detected / len(group), "point_at_or_above_mme": at_mme / len(group),
                    "supported_among_windows_at_the_event_floor": (sum(r["supported"] for r in testable) / len(testable)
                                                                   if testable else None),
                    "mean_point": sum(r["point"] for r in results) / len(results)}
            table.append(row)

    detectable = {}
    for scope in ("pooled",) + gp.ERAS:
        row = next((r for r in table if r["length"] == gp.LOOKS[-1] and r["era"] == scope), None)
        if not row or not row["windows"]:
            detectable[scope] = {"mme_power": None, "smallest_grid_gain_at_80": None}
            continue
        power = {float(t): g["supported"] for t, g in row["gains"].items()}
        reaching = [t for t, p in sorted(power.items()) if t > 0 and p >= POWER_TARGET]
        detectable[scope] = {"mme_power": power.get(gp.MME), "mme_detectable": power.get(gp.MME, 0) >= POWER_TARGET,
                             "smallest_grid_gain_at_80": reaching[0] if reaching else None}

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

    return {
        "what": "H7m G6: power of goalpost 3 on development data, by replay of R plus a planted signal "
                "(docs/stages/h7-g6.md). No candidate is scored. Development evidence, never a verdict.",
        "smoke": smoke,
        "pins": {"parent": PARENT_COMMIT, "panel_digest": PANEL_SHA256},
        "provenance": provenance,
        "days": {"scored": len(days), "first": days[0].day.isoformat(), "last": days[-1].day.isoformat(),
                 "events": sum(event), "dropped": labelled.dropped,
                 "events_by_era": {e: sum(d.event for d in days if gp.era(d.day) == e) for e in gp.ERAS},
                 "days_by_era": {e: sum(gp.era(d.day) == e for d in days) for e in gp.ERAS}},
        "declaration": {"seed": SEED, "step": STEP, "grid": list(GRID), "lengths": list(gp.LOOKS),
                        "draws": {str(n): (2000 if smoke else gp.draws_for(i)) for i, n in enumerate(gp.LOOKS)},
                        "nominal_levels": {str(n): gp.nominal_level(i) for i, n in enumerate(gp.LOOKS)},
                        "block_length": gp.BLOCK_LENGTH, "mme": gp.MME, "event_floor": gp.EVENT_FLOOR,
                        "noise_sd_in_sigma": gp.NOISE_SD, "sigma": sigma},
        "planting": {"shift_in_sigma": {str(t): c for t, c in shifts.items()}, "realised_gain_on_the_whole_span": realised},
        "power": table,
        "detectable_at_250_days": detectable,
        "days_to_the_event_floor": to_floor,
        "windows": windows,
        "seconds": round(clock.time() - began, 1),
    }


def _pct(value):
    return "n/a" if value is None else f"{100 * value:.0f}%"


def tables(record):
    """The markdown tables of `docs/research/h7m-power-study.md`, copied from the record and never recomputed."""
    out = []
    days = record["days"]
    out += ["| Era (of the day) | Scored days | Events |", "|---|---|---|"]
    out += [f"| {e} | {days['days_by_era'][e]} | {days['events_by_era'][e]} |" for e in gp.ERAS]
    out += [f"| all | {days['scored']} | {days['events']} |", ""]
    gains = [str(g) for g in record["declaration"]["grid"]]
    for length in gp.LOOKS:
        out += [f"**{length}-day windows** (power = share of windows supported; 95% Wilson interval at the effective "
                f"number of windows)", "",
                "| Era of the first day | Windows (effective) | Events per window (min / median / max) | Windows with "
                "at least 10 events | " + " | ".join(f"gain {g}" for g in gains) + " |",
                "|---|---|---|---|" + "---|" * len(gains)]
        for row in record["power"]:
            if row["length"] != length:
                continue
            if not row["windows"]:
                out.append(f"| {row['era']} | 0 | none | none |" + " none |" * len(gains))
                continue
            e = row["events_per_window"]
            cells = []
            for g in gains:
                v = row["gains"][g]
                low, high = v["supported_interval"]
                cells.append(f"{_pct(v['supported'])} ({_pct(low)}–{_pct(high)})")
            out.append(f"| {row['era']} | {row['windows']} ({row['effective_windows']:.1f}) | {e['min']} / "
                       f"{e['median']:g} / {e['max']} | {row['windows_at_the_event_floor']} | " + " | ".join(cells) + " |")
        out.append("")
    out += ["**Among the windows with at least 10 events** (supported share; pooled over eras)", "",
            "| Window | Windows at the floor | " + " | ".join(f"gain {g}" for g in gains) + " |",
            "|---|---|" + "---|" * len(gains)]
    for length in gp.LOOKS:
        row = next(r for r in record["power"] if r["length"] == length and r["era"] == "pooled")
        out.append(f"| {length} days | {row['windows_at_the_event_floor']} of {row['windows']} | " + " | ".join(
            _pct(row["gains"][g]["supported_among_windows_at_the_event_floor"]) for g in gains) + " |")
    out += ["", "**Size and the mean statistic at gain 0** (pooled)", "",
            "| Window | Supported | Lower bound above 0 | Point at or above the MME | Mean point |", "|---|---|---|---|---|"]
    for length in gp.LOOKS:
        v = next(r for r in record["power"] if r["length"] == length and r["era"] == "pooled")["gains"]["0.0"]
        out.append(f"| {length} days | {_pct(v['supported'])} | {_pct(v['lower_above_zero'])} | "
                   f"{_pct(v['point_at_or_above_mme'])} | {v['mean_point']:+.4f} |")
    out += ["", "**Days to 10 events** (from every 20th scored day; era of the start)", "",
            "| Era | Starts | Never reach 10 | Median days | 90th percentile |", "|---|---|---|---|---|"]
    for e, v in record["days_to_the_event_floor"].items():
        out.append(f"| {e} | {v['starts']} | {v['never_reached']} | {v['median']:g} | {v['p90']} |")
    out += ["", "**The MME at 250 days**", "", "| Scope | Power at 0.05 | Detectable (80%) | Smallest grid gain at 80% |",
            "|---|---|---|---|"]
    for scope, v in record["detectable_at_250_days"].items():
        out.append(f"| {scope} | {_pct(v.get('mme_power'))} | {v.get('mme_detectable', 'n/a')} | "
                   f"{v.get('smallest_grid_gain_at_80') or 'none on the grid'} |")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--tables", action="store_true", help="print the markdown tables of the recorded study")
    args = parser.parse_args(argv)
    if args.tables:
        print(tables(json.loads((RESULTS / "power_study.json").read_text(encoding="utf-8"))))
        return 0
    record = run(args.smoke)
    if args.smoke:
        print(json.dumps({k: record[k] for k in ("days", "planting", "detectable_at_250_days", "days_to_the_event_floor",
                                                  "seconds")}, indent=1, default=str))
        return 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "power_study.json"
    out.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
