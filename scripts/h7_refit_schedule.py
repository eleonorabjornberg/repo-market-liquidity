#!/usr/bin/env python3
"""H7m, groundwork: the refit-schedule analysis (directive #161; her follow-up of 21 October 2026 to finding #160). Read-only.

    PYTHONPATH=src:<parent at the pin>/src python3 scripts/h7_refit_schedule.py            # compute; write the record and the page
    PYTHONPATH=src python3 scripts/h7_refit_schedule.py --render [--check]                 # print the page from the record

**Nothing is fitted.** No kink, buffer, share or interval is computed, and no declaration is changed. For each candidate schedule
(`repo_liquidity.refit_schedule.RULES`) and each estimator of the two runs (A's baseline and six kink variants of #154; C's
baseline and four calendar-clean variants of #150), the script reads the training sample the estimator would have at each refit,
from the inputs alone: `h7_kink.training_days` and the width-regime table (A), `h7_candidate_c.training_days` and
`h7_clean.training_days` (C), on the rows `build_rows()` gives. It reports the refits, the refits that serve a scored day, the
episodes and regimes that enter and at which refit, the distinct training samples, and the refit-to-refit transitions in which the
sample changes.

It needs the code of #150 (`h7_clean`, `scripts/h7_calendar_clean.py`) and of #154 (`h7_kink`, `scripts/h7_kink_run.py`), which
are imported when the inputs are read, not before: until both are on `main` the inputs cannot be read, and `--render` alone runs.
The record (`docs/research/h7-refit-schedule.json`) and the page (`docs/research/h7-refit-schedule.md`) are written by this script
and never edited by hand.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Sequence

from repo_liquidity import demand_curve
from repo_liquidity import refit_schedule as rs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "research" / "h7-refit-schedule.json"
PAGE = ROOT / "docs" / "research" / "h7-refit-schedule.md"
FIRST_CUTOFF = date(2020, 3, 13)
REFIT_EVERY = 21
#: The schedule each run declared: A's (#154) is the stride, C's (#150, her option (b) on #160) is the stride and the last row.
DECLARED = {"A": "S0", "C": "S1"}
ESTIMATOR_ORDER = ("B", "V1", "V2", "V3", "V4", "V5", "V6", "C", "CV1", "CV2", "CV3", "CV4")
PROBE_EVERY = 10


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# -- the inputs (needs #150 and #154) -----------------------------------------------------------------------------------


def read_inputs():
    """The context the schedules are judged on, the pins and the regime table, from the real rows. Fits nothing.

    Raises:
        ImportError: `h7_clean` or `h7_kink` is not in this tree (#150 and #154 are not both on `main`).
        ValueError: the window's days differ between A's inputs and C's, or the declared schedules differ from the runs'.
    """
    from repo_model import scarcity
    from repo_model.data import next_business_day

    from repo_liquidity import h7_candidate_c as c
    from repo_liquidity import h7_clean as h
    from repo_liquidity import h7_kink as k

    kr = _load("h7_kink_run", ROOT / "scripts" / "h7_kink_run.py")
    cc = _load("h7_calendar_clean", ROOT / "scripts" / "h7_calendar_clean.py")

    # A's days, as scripts/h7_kink_run.py builds them.
    rows_k, pins = kr.build_rows()
    rows_k = [row for row in rows_k if row.date <= demand_curve.LAST_DAY]
    publications, notes = kr._tables()
    table = k.regime_table(k.width_regimes(rows_k, publications, notes, decision_time=k.DECISION_TIME))
    after = k.after_training_start(table)
    k.check_expected(after)
    label_fn, rule = k.parent_turn_label(), kr._rule()
    with scarcity.measurement_declaration():
        days_k = k.build_days(rows_k, rule, publications=publications, notes=notes, label_fn=label_fn)

    # C's days, as scripts/h7_calendar_clean.py builds them.
    rows_c, _ = h.build_rows()
    rows_c = [row for row in rows_c if row.date <= demand_curve.LAST_DAY]
    days_c = cc._build_c(rows_c, c.tracked_weeks())
    flags, series = cc._inputs(rows_c)

    days = tuple(x.day for x in days_k)
    if days != tuple(x.day for x in days_c):
        raise ValueError("A's scored days and C's differ")

    width = {r.regime: r.width for r in after}
    regime_names = {r.regime: f"regime:{r.regime} ({r.width} bp)" for r in after}

    def a_estimator(variant):
        regimed = variant.intercepts == "regime"

        @functools.lru_cache(maxsize=None)
        def sample_at(cutoff):
            pairs = k.training_days(days_k, cutoff, variant)
            counts = k.regime_counts(pairs) if regimed else {}
            short = any(n < k.REGIME_FLOOR for n in counts.values())
            units = frozenset(regime_names[r] for r, n in counts.items() if n >= k.REGIME_FLOOR and r in regime_names)
            return rs.Sample(hash(tuple(x.day for x in pairs)), units, len(pairs) >= k.KINK_MINIMUM_PAIRS and not short, len(pairs))
        names = tuple(regime_names[r.regime] for r in after) if regimed else ()
        return rs.Estimator(variant.id, "A", names, sample_at)

    episodes = tuple(f"episode:{label}" for label, _, _ in demand_curve.EPISODES)

    def c_estimator(name, training):
        @functools.lru_cache(maxsize=None)
        def sample_at(cutoff):
            sample, labels = training(cutoff)
            return rs.Sample((hash(tuple(x.day for x in sample)), labels), frozenset(f"episode:{label}" for label in labels),
                             bool(labels), len(sample))
        return rs.Estimator(name, "C", episodes, sample_at)

    estimators = [a_estimator(v) for v in (k.BASELINE,) + k.VARIANTS]
    estimators.append(c_estimator("C", lambda cutoff: c.training_days(days_c, cutoff)))
    for v in h.VARIANTS:
        estimators.append(c_estimator(v.id, lambda cutoff, v=v: h.training_days(
            days_c, cutoff, flags, v.left, series, lambda x: x.week is not None, clean=v.days == "clean")))

    start = next(d for d in days if d >= FIRST_CUTOFF)
    boundaries = tuple(r.first for r in after[1:])
    ctx = rs.Context(days=days, start=start, serving_start=lambda d: next_business_day(d, rs.SERVING_LAG), every=REFIT_EVERY,
                     boundaries=boundaries, estimators=tuple(estimators))
    # The two declared schedules must be the runs' own.
    if list(rs.SCHEDULES["S0"].build(ctx).cutoffs) != list(kr._cutoffs(days_k, None)):
        raise ValueError("S0 is not the stride scripts/h7_kink_run.py declares")
    if list(rs.SCHEDULES["S1"].build(ctx).cutoffs) != list(cc._cutoffs(days_c, None)):
        raise ValueError("S1 is not the schedule scripts/h7_calendar_clean.py declares")
    import hashlib

    code = ("src/repo_liquidity/h7_kink.py", "src/repo_liquidity/h7_clean.py", "src/repo_liquidity/h7_candidate_c.py",
            "scripts/h7_kink_run.py", "scripts/h7_calendar_clean.py")
    inputs = {
        "pins": pins,
        "input_code_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in code},
        "window": {"first_scored_day": days[0].isoformat(), "last_scored_day": days[-1].isoformat(), "scored_days": len(days),
                   "first_cutoff": start.isoformat(), "refit_every": REFIT_EVERY},
        "regime_table": [{"regime": r.regime, "width_bp": r.width, "first": r.first.isoformat(), "last": r.last.isoformat(),
                          "days": r.days} for r in table],
        "regime_floor": k.REGIME_FLOOR, "kink_minimum_pairs": k.KINK_MINIMUM_PAIRS,
        "episodes": [{"label": label, "first": first.isoformat(), "last": last.isoformat()}
                     for label, first, last in demand_curve.EPISODES],
        "episode_floor": demand_curve.MIN_SCARCE_DAYS_REVISED,
    }
    return ctx, inputs


# -- the analysis (pure over the context) -------------------------------------------------------------------------------


def analyse(ctx: rs.Context, inputs: Dict, probe_every: int = PROBE_EVERY) -> Dict:
    """The record: every rule's refits, every estimator's counts under it, the entry dates, the changes against the declared
    schedules and the information-set check. Fits nothing."""
    by_name = {e.name: e for e in ctx.estimators}
    order = [n for n in ESTIMATOR_ORDER if n in by_name]
    probes = [d for d in ctx.days if d >= ctx.start][::probe_every]

    def make_context(prefix):
        return ctx._replace(days=tuple(prefix))

    declared = {fam: rs.SCHEDULES[rid].build(ctx).cutoffs for fam, rid in DECLARED.items()}
    rules, results, versus, common = {}, {}, {}, {}
    for rule in rs.RULES:
        schedule = rule.build(ctx)
        rs.check_schedule_no_future(rule, make_context, ctx.days, probes)
        pairs = rs.served(ctx, schedule.cutoffs)
        rules[rule.id] = {
            "text": rule.text, "cutoffs": [c.isoformat() for c in schedule.cutoffs], "refits": len(pairs),
            "serving": sum(1 for _, days in pairs if days),
            "not_serving": [c.isoformat() for c, days in pairs if not days],
            "window_end_dependent": rule.window_end_dependent,
            "window_dependent_cutoffs": sorted(c.isoformat() for c in schedule.window_dependent),
            "no_future_probes": len(probes),
        }
        results[rule.id] = {n: rs.evaluate(ctx, by_name[n], schedule.cutoffs) for n in order}
        versus[rule.id] = {fam: rs.compare_to_declared(ctx, schedule.cutoffs, cut) for fam, cut in declared.items()}
        common[rule.id] = {}
        for fam in ("A", "C"):
            live = [rs.live_days(ctx, by_name[n], schedule.cutoffs) for n in order if by_name[n].family == fam]
            common[rule.id][fam] = {"scored_days_after_first_serve": len([d for d in ctx.days if d >= ctx.serving_start(ctx.start)]),
                                    "days_every_estimator_can_have_an_estimate": len(frozenset.intersection(*live))}
    entries = {n: {u: (d.isoformat() if d else None) for u, d in rs.entry_dates(ctx, by_name[n]).items()} for n in order}
    return {
        "note": "Generated by scripts/h7_refit_schedule.py; never edited by hand. Nothing is fitted: inputs only.",
        "tier": "development", "directive": "repo-market-liquidity#161", "hypothesis": "H7m", "declared": DECLARED,
        **inputs,
        "estimators": {n: {"family": by_name[n].family, "units": list(by_name[n].units)} for n in order},
        "boundaries": [b.isoformat() for b in ctx.boundaries],
        "rules": rules, "results": results, "entry_dates": entries, "versus_declared": versus,
        "common_live_days": common,
    }


# -- the page -----------------------------------------------------------------------------------------------------------


def _cell(r: Dict) -> str:
    return f"{r['distinct_samples']} / {r['transitions_changed']}"


def markdown(record: Dict) -> str:
    ids = [r.id for r in rs.RULES if r.id in record["rules"]]  # the record is written with sorted keys; the page keeps the order
    est = {n: record["estimators"][n] for n in ESTIMATOR_ORDER if n in record["estimators"]}
    rules = {i: record["rules"][i] for i in ids}
    results = {i: record["results"][i] for i in ids}
    versus = {i: record["versus_declared"][i] for i in ids}
    fam = {f: [n for n in est if est[n]["family"] == f] for f in ("A", "C")}
    w = record["window"]
    out = [
        "# H7m: which refit schedule? (read-only, nothing fitted)", "",
        "Printed from `docs/research/h7-refit-schedule.json` by `scripts/h7_refit_schedule.py --render`; never edited by hand. "
        "Tier: development. Directive: repo-market-liquidity#161. **No fit, no kink, no buffer, no interval, no declaration changed.** "
        "Every number below is a count of training days, refits or transitions read from the inputs.", "",
        f"Window: {w['scored_days']} scored days, {w['first_scored_day']} to {w['last_scored_day']}; the first cutoff is "
        f"{w['first_cutoff']}, and a refit serves from the second business day after its cutoff. A refit that serves no scored "
        "day is listed apart and does not count (her ruling of 21 October, addition 1).", "",
        "Parent pin " + str(record["pins"]["parent_commit"]) + ", panel digest " + str(record["pins"]["panel_sha256"]) + ". "
        "The code that reads the inputs, by sha256: " + "; ".join(f"`{p}` {h[:12]}" for p, h in sorted(record["input_code_sha256"].items())) +
        " (`h7_kink` and `h7_clean` are in #154 and #150, not yet on `main`).", "",
        "## Candidates", "",
        "| Id | Rule | Refits | Serving a scored day | Serving none | Refit that exists because of the window's end |",
        "|---|---|---|---|---|---|",
    ]
    for rid, r in rules.items():
        out.append(f"| {rid} | {r['text']} | {r['refits']} | {r['serving']} | {', '.join(r['not_serving']) or 'none'} | "
                   f"{', '.join(r['window_dependent_cutoffs']) or 'none'} |")
    out += ["", "The information set: every rule finds its dates by scanning the scored days in order and reading the sample at "
            "that day alone. `check_schedule_no_future` rebuilt each schedule from the days up to "
            f"{rules['S0']['no_future_probes']} probe dates and found it equal to the full schedule's refits up to each; the refits "
            "that exist because of the window's end (S1, S1b) are left out of that comparison, as they depend on the declared end of "
            "the window and not on a row.", ""]
    out += ["## Distinct training samples / refit-to-refit transitions in which the sample changes", "",
            "Over the refits that serve a scored day. A transition is a chance for goalpost 1 to move.", ""]
    for f, label in (("A", "A (the kink, #154)"), ("C", "C (the H.8 shares, #150)")):
        out += [f"### {label}", "", "| Schedule | " + " | ".join(fam[f]) + " |", "|---|" + "---|" * len(fam[f])]
        for rid in rules:
            out.append(f"| {rid} | " + " | ".join(_cell(results[rid][n]) for n in fam[f]) + " |")
        out.append("")
    out += ["### The same, counting only transitions whose two refits both pass the estimator's own input rule", "",
            "| Schedule | " + " | ".join(est) + " |", "|---|" + "---|" * len(est)]
    for rid in rules:
        out.append(f"| {rid} | " + " | ".join(f"{results[rid][n]['distinct_fittable']} / {results[rid][n]['transitions_fittable']}"
                                              for n in est) + " |")
    out += ["", "## Refits that serve a day and cannot fit, and the scored days they leave without an estimate", "",
            "The estimator's own input rule only. A kink refit with a regime under the floor of " + str(record["regime_floor"]) +
            " pairs is not fitted and serves no estimate; a C refit with no counted episode is not fitted. Cell: refits / days.", "",
            "| Schedule | " + " | ".join(est) + " |", "|---|" + "---|" * len(est)]
    for rid in rules:
        out.append(f"| {rid} | " + " | ".join(f"{results[rid][n]['dead_serving']} / {results[rid][n]['dead_days']}" for n in est) + " |")
    out += ["", "## Scored days on which every estimator of a family can have an estimate", "",
            "A comparison between variants is read on the days all of them serve (the #137 ruling), so this is the most days a "
            "comparison can use under the schedule, before any fit fails to converge or to identify a kink.", "",
            "| Schedule | A (7 estimators) | C (5 estimators) |", "|---|---|---|"]
    for rid in ids:
        c = record["common_live_days"][rid]
        out.append(f"| {rid} | {c['A']['days_every_estimator_can_have_an_estimate']} | {c['C']['days_every_estimator_can_have_an_estimate']} |")
    out += ["", "## Episodes and regimes: the first day each counts, and the refit that first serves it", "",
            "| Estimator | Unit | First day it counts | " + " | ".join(f"{rid}: refit (days served with it)" for rid in rules) + " |",
            "|---|---|---|" + "---|" * len(rules)]
    for n in est:
        for u in est[n]["units"]:
            cells = []
            for rid in rules:
                x = results[rid][n]["units"][u]
                cells.append("never" if x["first_serving_refit"] is None else f"{x['first_serving_refit']} ({x['days_served_with_unit']})")
            out.append(f"| {n} | {u} | {record['entry_dates'][n][u] or 'never'} | " + " | ".join(cells) + " |")
    out += ["", "## Regime table (corridor width, read at announcement)", "", "| Regime | Width (bp) | First day | Last day | Days |",
            "|---|---|---|---|---|"]
    for r in record["regime_table"]:
        out.append(f"| {r['regime']} | {r['width_bp']} | {r['first']} | {r['last']} | {r['days']} |")
    out += ["", "## What each schedule changes against the one declared", "",
            "A's declared schedule is " + record["declared"]["A"] + " (#154, run on the Mac); C's is " + record["declared"]["C"] +
            " (#150, not yet run). \"Days with a new serving refit\" counts scored days that a different refit would serve.", "",
            "| Schedule | A: added | A: removed | A: days with a new serving refit | C: added | C: removed | C: days with a new serving refit |",
            "|---|---|---|---|---|---|---|"]
    for rid, v in versus.items():
        a, c = v["A"], v["C"]
        out.append(f"| {rid} | {len(a['added'])} | {len(a['removed'])} | {a['days_with_a_new_serving_refit']} | {len(c['added'])} | "
                   f"{len(c['removed'])} | {c['days_with_a_new_serving_refit']} |")
    out += ["", "## Fits the schedule asks for (distinct training samples that pass the input rule, summed over the estimators)", "",
            "| Schedule | A (7 estimators) | C (5 estimators) |", "|---|---|---|"]
    for rid in rules:
        out.append(f"| {rid} | {sum(results[rid][n]['distinct_fittable'] for n in fam['A'])} | "
                   f"{sum(results[rid][n]['distinct_fittable'] for n in fam['C'])} |")
    out += ["", "## Refit dates", ""]
    for rid, r in rules.items():
        out += [f"**{rid}** ({r['refits']}): " + ", ".join(r["cutoffs"]), ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--page", type=Path, default=PAGE)
    parser.add_argument("--render", action="store_true", help="print the page from the record; read no input")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.render:
        text = markdown(json.loads(args.output.read_text(encoding="utf-8")))
        if args.check:
            if not args.page.is_file() or args.page.read_text(encoding="utf-8") != text:
                print(f"{args.page} is stale: run scripts/h7_refit_schedule.py --render", file=sys.stderr)
                return 1
            print("h7 refit schedule page: ok")
            return 0
        args.page.write_text(text, encoding="utf-8")
        print(f"wrote {args.page}")
        return 0
    try:
        ctx, inputs = read_inputs()
    except ImportError as error:
        print(f"not run: the code of #150 and #154 is not both in this tree ({error})", file=sys.stderr)
        return 2
    record = analyse(ctx, inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.page.write_text(markdown(record), encoding="utf-8")
    print(f"wrote {args.output} and {args.page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
