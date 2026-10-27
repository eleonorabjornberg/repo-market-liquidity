#!/usr/bin/env python3
"""H7m, development step 5: the three goalposts on development days for every estimator in play, and for R, S and R+S
(`docs/stages/h7-step5.md`, directive #178).

    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py --timing
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py [--draws 10000]
        [--output results/h7/step5-scores.json] [--page docs/research/h7-step5.md]
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py --render [--check]

Reads, and re-fits nothing of, the three records on main (`results/h7/kink.json`, `results/h7/calendar-clean.json`,
`results/h7/distribution-account.json`), reads R and S from the parent through `h7_estimator.asof_days` and the stress event from the
parent's `fed_liquidity`, and writes `results/h7/step5-scores.json` and the Markdown printed from it. Neither is ever edited by hand.
It gives no verdict; the tier is "development".

* `--timing` times the whole scoring on a synthetic window of the real size (1,447 days, 98 events) at the real number of draws,
  with a synthetic estimator per scorable estimator, and reads no real day.
* Both tracked records must carry this tree's parent pin, panel digest and window, or the run stops.
"""

import argparse
import hashlib
import json
import sys
import time as clock
from datetime import date, datetime, time
from pathlib import Path

from repo_model import fed_liquidity, measurement_fields, scarcity
from repo_model.asof import InformationRule

from repo_liquidity import anchored, demand_curve, parent_root
from repo_liquidity import goalposts as gp
from repo_liquidity import h7_account as account
from repo_liquidity import h7_clean as h
from repo_liquidity import h7_estimator
from repo_liquidity import h7_step5 as s5

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "h7" / "step5-scores.json"
PAGE = ROOT / "docs" / "research" / "h7-step5.md"
CLEAN = ROOT / "results" / "h7" / "calendar-clean.json"
KINK = ROOT / "results" / "h7" / "kink.json"
ACCOUNT = ROOT / "results" / "h7" / "distribution-account.json"
SOURCES = {"kink": KINK, "calendar_clean": CLEAN, "distribution_account": ACCOUNT}
#: The estimators in play, in the order of the records: A's baseline and variants, then C and its variants.
A_IDS = ("B", "V1", "V2", "V3", "V4", "V5", "V6")
C_IDS = ("C", "CV1", "CV2", "CV3", "CV4")
#: The account's key for each: A as defined is `A_<id>`; C's are their own.
ACCOUNT_KEY = {**{i: f"A_{i}" for i in A_IDS}, **{i: i for i in C_IDS}}
NOT_RUN = ("D", "DV1", "DV2", "DV3", "DV4")
#: The rounding of the account's per-day columns (four places of a point), so a recomputed A figure is checked to it.
ROUNDING = 5.5e-5
MEDIAN_TOLERANCE = 1.0e-3
TWO_HOURS = 2 * 3600


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha(name, path, record):
    """The sha256 step 5 records for a source. For the account it is that of the record step 5 read figures from: the account was
    republished without the rows of "A through the group machinery" (#182, #186), which step 5 never reads, and it names the record
    it replaces. Every row step 5 reads is byte-equal in both (`tests/test_h7_step5_record.py`), so no step-5 figure moves and the
    pin stays what it was."""
    if name == "distribution_account" and "superseded" in record:
        return record["superseded"]["sha256"]
    return _sha(path)


def _check_pins(pins, records):
    """Every tracked record was made at this tree's parent pin, panel and window."""
    for name, record in records.items():
        theirs = record["pins"]
        for key in ("parent_commit", "panel_version", "panel_sha256", "effr_series_sha256", "rows", "first_day", "last_day"):
            if theirs[key] != pins[key]:
                raise ValueError(f"the {name} record has {key} {theirs[key]!r}, but this run has {pins[key]!r}")
        if record["window_end"] != demand_curve.LAST_DAY.isoformat():
            raise ValueError(f"the {name} record's window ends {record['window_end']}, not {demand_curve.LAST_DAY}")


def _rule():
    return InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)


def _parent_days(rows):
    """R and S as the parent's functions of what the as-of rule serves, on every scored day to the records' last day."""
    with scarcity.measurement_declaration():
        return h7_estimator.asof_days([r for r in rows if r.date <= demand_curve.LAST_DAY], _rule())


def _labels(rows):
    """The parent's `fed_repo_accepted` by date, through its own assembly at the panel's build cutoff."""
    manifest = json.loads((parent_root() / "metadata" / "funding_panel_manifest.json").read_text(encoding="utf-8"))
    snapshots = parent_root() / "tests" / "fixtures" / "snapshots" / "repo_ops_inputs"
    end = fed_liquidity.declared_coverage_end(fed_liquidity.NYFED_REPO_OPS_SOURCE_ID)
    assembled, _summary = fed_liquidity.assemble(rows, snapshots, cutoff=datetime.fromisoformat(manifest["build_cutoff"]), end=end)
    return {row.date: row.values.get("fed_repo_accepted") for row in assembled}


def _recorded_goalpost_2(name, kink, clean):
    """The earlier record's own goalpost-2 median in points and its served days, for the cross-check."""
    if name in A_IDS:
        g = kink["summaries"][name]["all_served_days"]
        return g["goalpost_2"].get("median"), g["served_days"]
    s = clean["estimators"][name]["summary"]
    return s["goalpost_2"].get("median_served_points"), s["served_days"]


def _not_scorable_reason(name, kink, clean):
    if name in C_IDS:
        entry = clean["estimators"][name]["summary"]
        status = ", ".join(f"{v} {k_}" for k_, v in entry["refit_status"].items())
        return (f"the refit in force did not fit on any window day: {entry['not_fitted_refits']} of {len(clean['cutoffs'])} refits "
                f"were not fitted (calendar-clean record, refit status: {status}); it serves no day and is not re-fitted")
    g = kink["summaries"][name]["all_served_days"]
    return f"it serves no day ({g['not_fitted']} refits not fitted); it is not re-fitted"


def build(draws=s5.DRAWS):
    clean = json.loads(CLEAN.read_text(encoding="utf-8"))
    kink = json.loads(KINK.read_text(encoding="utf-8"))
    acc = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    rows, pins = h.build_rows()
    _check_pins(pins, {"calendar-clean": clean, "kink": kink, "distribution-account": acc})
    days = _parent_days(rows)
    labelled = gp.labelled_days(days, _labels(rows), last_day=demand_curve.LAST_DAY)
    first_served = min(date.fromisoformat(e["daily"]["days"][0]) for e in acc["estimators"].values() if e["daily"]["days"])
    last_served = max(date.fromisoformat(e["daily"]["days"][-1]) for e in acc["estimators"].values() if e["daily"]["days"])
    kept = [d for d in labelled.days if first_served <= d.day <= last_served]
    s5.check_window([d.day for d in kept])
    window = s5.Window([d.day for d in kept], [d.ratio for d in kept], [d.state for d in kept], [d.event for d in kept])

    declaration = anchored.split_declaration()
    by_day = {row.date: row.values for row in rows}
    regimes = [declaration.regime(day) for day in window.days]
    types = [declaration.reporting_day_type(day, by_day[day]) for day in window.days]

    checks = {"served_days_match_record": [], "widths_match_record": [], "a_equals_r_minus_the_kink": []}
    estimates, goalpost_one, recorded_g2, reasons = {}, {}, {}, {}
    ratios = dict(zip((d.day for d in days), (d.ratio for d in days)))
    for name, key in ACCOUNT_KEY.items():
        daily = acc["estimators"][key]["daily"]
        est = s5.align(daily, window.days)
        estimates[name] = est
        median, served = _recorded_goalpost_2(name, kink, clean)
        if len(est.served) != served:
            raise ValueError(f"{name} serves {len(est.served)} window days, the tracked record says {served}")
        checks["served_days_match_record"].append(name)
        widths = [w for w in est.width if w is not None]
        if widths:
            mine = s5.width_reading(est.width)["served_median_points"]
            if median is None or abs(mine - median) > MEDIAN_TOLERANCE:
                raise ValueError(f"{name}'s median served width is {mine}, the tracked record says {median}")
            checks["widths_match_record"].append(name)
        recorded_g2[name] = median
        if name in A_IDS:
            refits = account.a_refits_from_record(kink["estimators"][name]["refits"])
            cutoffs = [date.fromisoformat(x) for x in kink["cutoffs"]]
            index = account.serving_index(window.days, cutoffs)
            for i in est.served:
                fit = refits[index[window.days[i]]]
                want = s5.POINTS * (ratios[window.days[i]] - fit.kink)
                if abs(est.estimate[i] * s5.POINTS - want) > ROUNDING:
                    raise ValueError(f"{name} on {window.days[i]}: the account has {est.estimate[i] * s5.POINTS}, R - k is {want}")
            checks["a_equals_r_minus_the_kink"].append(name)
            goalpost_one[name] = s5.goalpost_one_a(kink["summaries"][name]["all_served_days"]["goalpost_1"])
        else:
            goalpost_one[name] = s5.goalpost_one_c()
        if not est.served:
            reasons[name] = _not_scorable_reason(name, kink, clean)

    scored = s5.score_all(window, regimes, types, estimates, draws=draws, seed=s5.SEED, reasons=reasons)
    for name, entry in scored["estimators"].items():
        entry["family"] = "A" if name in A_IDS else "C"
        entry["account_key"] = ACCOUNT_KEY[name]
        entry["calendar_days"] = acc["estimators"][ACCOUNT_KEY[name]]["calendar_days"]
        entry["goalpost_1"] = goalpost_one[name]
        entry["goalpost_2_recorded_median_points"] = recorded_g2[name]
    in_play = list(A_IDS) + list(C_IDS)
    return {
        "note": "Generated by scripts/h7_step5.py; never edited by hand.",
        "tier": "development", "directive": "repo-market-liquidity#178", "stage": "docs/stages/h7-step5.md",
        "decides_nothing": "A development reading is never a verdict (docs/decisions/measurement-protocol.md section 1).",
        "pins": pins,
        "window": {"first_day": window.days[0].isoformat(), "last_day": window.days[-1].isoformat(), "days": len(window.days),
                   "events": sum(window.event), "dropped_unlabelled": labelled.dropped,
                   "labelled_days_before_the_first_served_day": sum(d.day < first_served for d in labelled.days),
                   "s_levels": {str(int(s)): sum(x == s for x in window.state) for s in sorted(set(window.state))}},
        "settings": {"draws": draws, "block_length": s5.BLOCK_LENGTH, "seed": s5.SEED, "lower_level": s5.LOWER_LEVEL,
                     "upper_level": s5.UPPER_LEVEL, "mme": s5.MME, "event_floor": s5.EVENT_FLOOR,
                     "width_limit_points": s5.WIDTH_LIMIT_POINTS, "estimate_unit": "share of bank assets (account points / 100)",
                     "interval": "the 5th and 95th percentiles of the resamples, no look spent",
                     "stress_event_bn": gp.MATERIAL_USE_BN},
        "sources": {name: {"path": str(path.relative_to(ROOT)), "sha256": _source_sha(name, path, acc if name == "distribution_account" else {})}
                    for name, path in SOURCES.items()},
        "checks": checks,
        "splits": scored["splits"], "benchmarks": scored["benchmarks"], "estimators": scored["estimators"],
        "variant_count": {
            "estimators_in_play": len(in_play), "variants_in_play": len(in_play) - 2,
            "scored": [n for n in in_play if scored["estimators"][n]["status"] == "scored"],
            "not_scorable": [n for n in in_play if scored["estimators"][n]["status"] == "not scorable"],
            "declared_and_not_run": list(NOT_RUN),
            "recorded_additions": {"kink_record": kink["variant_count"], "calendar_clean_record": clean["variant_count_added"]},
            "stages_2_to_6": "stated by no record; not counted here",
        },
    }


# -- the timing -------------------------------------------------------------------------------------------------------------------


def timing(draws):
    """Time the whole scoring on a synthetic window of the real size, with a synthetic estimator per scorable estimator."""
    import random

    started = clock.time()
    window = s5.synthetic_window(1447, 98, seed=1)
    rng = random.Random(2)
    regimes = ["2020" if d.year == 2020 else "2021-23" if d.year < 2024 else "2024" if d.year == 2024 else "2025-26" for d in window.days]
    types = [rng.choice(("quarter_end", "month_end", "tax_date", "ordinary", "ordinary", "ordinary")) for _ in window.days]
    estimates = {}
    for i in range(9):
        est = [r - 0.09 + rng.gauss(0.0, 0.004) - 0.03 * y for r, y in zip(window.ratio, window.event)]
        estimates[f"X{i}"] = s5.Estimates(est, [rng.uniform(2.0, 4.0) for _ in est], list(range(len(est))))
    estimates["Y"] = s5.Estimates([None] * 1447, [None] * 1447, [])
    scored = s5.score_all(window, regimes, types, estimates, draws=draws, seed=s5.SEED, reasons={})
    seconds = clock.time() - started
    print(f"timing: {len(estimates)} synthetic estimators, {len(scored['splits'])} splits, {draws} draws, 1447 days, 98 events: "
          f"{seconds:.1f} s ({'under' if seconds < TWO_HOURS else 'over'} the two-hour line of {TWO_HOURS} s)", flush=True)
    return seconds


# -- the page ---------------------------------------------------------------------------------------------------------------------


def _f(value, places=3):
    return "n/a" if value is None else f"{value:.{places}f}"


def _cell(row):
    if row["events"] == 0:
        return "no usable event"
    return f"{row['point']:+.3f} [{row['lower']:+.3f}, {row['upper']:+.3f}]"


def _head(record, labels):
    """The split labels as column heads; a split under the event floor carries a dagger."""
    return [label + (" †" if record["splits"][label]["under_event_floor"] else "") for label in labels]


def _auc(row):
    return f"{row['point']:.3f} [{row['lower']:.3f}, {row['upper']:.3f}]"


def markdown(record):
    """The Markdown printed from the record. Never edited by hand."""
    pins, w, st = record["pins"], record["window"], record["settings"]
    labels = list(record["splits"])
    scored = [n for n, e in record["estimators"].items() if e["status"] == "scored"]
    lines = ["# H7m: the three goalposts, scored on development days (step 5)", "",
             "Generated from `results/h7/step5-scores.json` by `scripts/h7_step5.py --render`; never edited by hand.",
             f"Tier: **{record['tier']}**. Development evidence, **not a verdict**. {record['decides_nothing']} Stage document: "
             f"`{record['stage']}`. No estimator is re-fitted; every estimate is the account's (`results/h7/distribution-account.json`).", "",
             f"Panel version {pins['panel_version']} `{pins['panel_sha256']}`; parent `{pins['parent_commit']}`. Window {w['first_day']} to "
             f"{w['last_day']}: {w['days']} scored days, {w['events']} stress events (a day with Fed repo operations accepted of "
             f"${st['stress_event_bn']:.0f} bn or more). Scarcity-state days by level: "
             + ", ".join(f"S={k_}: {v}" for k_, v in w["s_levels"].items()) + ". "
             f"{st['draws']} stationary-bootstrap draws, mean block {st['block_length']}, seed {st['seed']} plus the split's position; "
             f"intervals are the 5th and 95th percentiles, no look spent. The MME is {st['mme']} AUROC points; the event floor is "
             f"{st['event_floor']}. Estimates are in shares of bank assets; widths in points. Sources: "
             + ", ".join(f"`{s['path']}` (`{s['sha256'][:12]}`)" for s in record["sources"].values()) + ".", "",
             "A gain is AUROC(estimate) minus AUROC of the benchmark, ranked low to high, ties half, in AUROC points. Against R: all days; "
             "against R+S: within each scarcity-state level, pooled by events (protocol section 5); against S: AUROC(-S), on the days the "
             "estimator serves. A missing estimate takes R's place for R and R+S (section 11). A position against the MME is in words only.", "",
             "## Goalpost 1 (stable)", "",
             "| Estimator | Calendar days | Reading |", "|---|---|---|"]
    for name, e in record["estimators"].items():
        g = e["goalpost_1"]
        if "recorded" in g:
            r = g["recorded"]
            worst = r["worst"]
            text = (f"{g['reading']}: worst gap {worst['gap']:.2f} points on {worst['day']} over {r['days_compared']} days compared; "
                    f"{r['missing_refits']} missing refits; bar {r['limit']} points; holds: {str(r['holds']).lower()}") if worst else \
                f"{g['reading']}: no day compared"
        else:
            text = g["reading"]
        lines.append(f"| {name} | {e['calendar_days']} | {text} |")
    lines += ["", "## Goalpost 2 (sharp): median 90% interval width, points, against the 3-point bar", "",
              "A missing day counts as over the bar (sections 4 and 11); the median over the days with an interval is beside it (the form "
              "A's record gives).", "",
              "| Estimator | Window days | Missing | Median, missing counted over | Position | Median over served days | Position |",
              "|---|---|---|---|---|---|---|"]
    for name in scored:
        row = record["estimators"][name]["goalpost_2"]["all: all"]
        lines.append(f"| {name} | {row['days']} | {row['missing']} | {_f(row['median_points'], 2)} | {row['position']} | "
                     f"{_f(row['served_median_points'], 2)} | {row['served_position'] or 'n/a'} |")
    lines += ["", "## Goalpost 3 (informative): the information gain, pooled", "",
              "| Estimator | Missing share | Against R | Against S | Against R+S | R+S against the MME |", "|---|---|---|---|---|---|"]
    for name in scored:
        e = record["estimators"][name]
        g = e["goalpost_3"]
        lines.append(f"| {name} | {e['missing_share']:.1%} | {_cell(g['vs_r']['all: all'])} | {_cell(g['vs_s']['all: all'])} | "
                     f"{_cell(g['vs_rs']['all: all'])} | {g['vs_rs']['all: all']['position']} |")
    over = [n for n in scored if record["estimators"][n]["missing_share"] > gp.MISSING_LIMIT]
    lines += ["", "Missing days take R's place (section 11). More than 5% missing days would void a registration; that is a registration "
              "rule, reported here and not applied: " + (", ".join(f"{n} ({record['estimators'][n]['missing_share']:.1%})" for n in over)
                                                         if over else "none") + " over the line.",
              "", "## Not scorable", ""]
    for name, e in record["estimators"].items():
        if e["status"] != "scored":
            lines.append(f"- {name}: not scorable. {e['reason']}.")
    lines += ["", "## R, S and R+S, scored on the same days (AUROC, 90% interval)", "",
              "R+S is R within a scarcity-state level, pooled by events (section 5 fits no model). Each is computed here and not cited from Stage 6.", "",
              "| Split | Days | Events | R | S | R+S |", "|---|---|---|---|---|---|"]
    for label in labels:
        s = record["splits"][label]
        flag = " (under the event floor)" if s["under_event_floor"] else ""
        lines.append(f"| {label}{flag} | {s['days']} | {s['events']} | {_auc(record['benchmarks']['R'][label])} | "
                     f"{_auc(record['benchmarks']['S'][label])} | {_auc(record['benchmarks']['R+S'][label])} |")
    heads = _head(record, labels)
    lines += ["", "## Splits: the gain against R+S (the section 5 statistic) by regime and by pressure-day type", "",
              "Each split is bootstrapped on its own days. † marks a split under the event floor of 10 events: it is reported and labelled, "
              "never dropped. \"no usable event\" means the split (or every scarcity-state level in it) has no event or no other day.", "",
              "| Estimator | " + " | ".join(heads) + " |", "|---|" + "---|" * len(labels)]
    for name in scored:
        g = record["estimators"][name]["goalpost_3"]["vs_rs"]
        lines.append(f"| {name} | " + " | ".join(_cell(g[label]) for label in labels) + " |")
    for kind, title in (("vs_r", "against R"), ("vs_s", "against S")):
        lines += ["", f"## Splits: the gain {title}", "",
                  "| Estimator | " + " | ".join(heads) + " |", "|---|" + "---|" * len(labels)]
        for name in scored:
            g = record["estimators"][name]["goalpost_3"][kind]
            lines.append(f"| {name} | " + " | ".join(_cell(g[label]) for label in labels) + " |")
    lines += ["", "## Splits: goalpost 2, median width in points (missing counted over the bar)", "",
              "| Estimator | " + " | ".join(heads) + " |", "|---|" + "---|" * len(labels)]
    for name in scored:
        g = record["estimators"][name]["goalpost_2"]
        lines.append(f"| {name} | " + " | ".join(_f(g[label]["median_points"], 2) for label in labels) + " |")
    v = record["variant_count"]
    lines += ["", "## The variant count (for step 6)", "",
              f"- Estimators declared and run: {v['estimators_in_play']} (A's B and six variants, C and four variants), of which "
              f"{v['variants_in_play']} are variants; scored: {', '.join(v['scored'])}; not scorable: {', '.join(v['not_scorable'])}.",
              f"- Declared and not run: {', '.join(v['declared_and_not_run'])} (D dropped under #142).",
              f"- Added by the records: the kink record {v['recorded_additions']['kink_record']}, the calendar-clean record "
              f"{v['recorded_additions']['calendar_clean_record']}. The count from Stages 2 to 6: {v['stages_2_to_6']}.",
              "- How a not-scorable estimator counts is a marked question (Q4 in the stage document); the default counts it.", "",
              "## Checks the run made", "",
              f"- Served-day counts equal to the tracked records': {', '.join(record['checks']['served_days_match_record'])}.",
              f"- Median served widths equal to the tracked records' (to 0.001 point): {', '.join(record['checks']['widths_match_record'])}.",
              f"- A's account equals 100 x (R - k of the refit in force) on every served day, to the rounding: "
              f"{', '.join(record['checks']['a_equals_r_minus_the_kink'])}.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=s5.DRAWS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--page", type=Path, default=PAGE)
    parser.add_argument("--timing", action="store_true", help="time the scoring on a synthetic window of the real size; read no real day")
    parser.add_argument("--render", action="store_true", help="print the page from the record; run nothing")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.timing:
        timing(args.draws)
        return 0
    if args.render:
        text = markdown(json.loads(args.output.read_text(encoding="utf-8")))
        if args.check:
            if not args.page.is_file() or args.page.read_text(encoding="utf-8") != text:
                print(f"{args.page} is stale: run scripts/h7_step5.py --render", file=sys.stderr)
                return 1
            print("h7 step 5 page: ok")
            return 0
        args.page.write_text(text, encoding="utf-8")
        print(f"wrote {args.page}")
        return 0
    started = clock.time()
    record = build(args.draws)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(account.dump_record(record), encoding="utf-8")
    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(markdown(json.loads(args.output.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {args.output} and {args.page} ({clock.time() - started:.0f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
