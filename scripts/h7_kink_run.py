#!/usr/bin/env python3
"""H7m, the run of A's re-specified kink (`docs/stages/h7-kink.md` with its section 7, directive #151).

    PYTHONPATH=src:<parent>/src python3 scripts/h7_kink_run.py [--replications 2000] [--workers 8] [--variants B,V1,..,V6]
        [--limit-refits N] [--output results/h7/kink.json] [--force]
    PYTHONPATH=src:<parent>/src python3 scripts/h7_kink_run.py --timing      # synthetic window only; reads no real day
    PYTHONPATH=src:<parent>/src python3 scripts/h7_kink_run.py --render [--check]

Runs the baseline (the parent's fit on the same pairs) and V1 to V6 on the development walk-forward and writes the record
`results/h7/kink.json` and the Markdown printed from it, `docs/research/h7-kink.md`; neither is ever edited by hand.

* **It cannot run on real days at the pinned parent**: the exclusion set needs `repo_model.turn_days.turn_label` (section 7(ii)),
  which arrives with the pin move (#149). The script then exits 2 and reads nothing.
* Rows: the measurement panel version 1 from the tracked fixtures (digest checked) with the parent's opt-in `effr` column, to
  `demand_curve.LAST_DAY`. Every scored day is read through the parent's rule, which refuses a locked day.
* **First action:** derive the width regime table from the ON RRP and IORB announcements and print it. If its widths differ from
  `h7_kink.EXPECTED_WIDTHS` the run stops with a finding and fits nothing.
* Refits: the first at 2020-03-13, then every 21 observation days, to 2025-12-31, as Stages 3c and 6 and the #147 run. Bootstrap:
  mean block 10, level 0.90, the parent's seed, `--replications` draws (2000, Stage 2's and Stage 6's count).
* Every variant is read against the baseline **on the same served days**, for goalposts 1 and 2, with the clean training days per
  corridor regime at each refit (against the floor of 50) and the Politis-White block length of each refit's training residuals.
* Development evidence only: no verdict, no locked day, no goalpost 3. The record's tier is "development".
"""

import argparse
import json
import sys
import time as clock
from datetime import date
from pathlib import Path

from repo_liquidity import demand_curve, goalposts
from repo_liquidity import h7_estimator as h7
from repo_liquidity import h7_kink as k

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "h7" / "kink.json"
PAGE = ROOT / "docs" / "research" / "h7-kink.md"
FIRST_CUTOFF = date(2020, 3, 13)
REFIT_EVERY = 21
ALL = (k.BASELINE.id,) + tuple(v.id for v in k.VARIANTS)
BY_ID = {v.id: v for v in (k.BASELINE,) + k.VARIANTS}
EFFR_ROOT = "nyfed_effr_inputs"


def build_rows():
    """The measurement panel's rows (version 1's columns, byte for byte) with the parent's opt-in `effr` column added.

    Built as `panel.build` builds version 1 from the tracked fixtures, with no network, except that the parent's EFFR snapshots
    are read as well. Returns the rows and a dict of the pins.

    Raises:
        ValueError: the version-1 columns do not reproduce the manifest's digest, a column is refused, or the dates differ.
    """
    import hashlib
    import tempfile
    from datetime import datetime, time

    from repo_model.data import build_daily_panel

    from repo_liquidity import declaration, h41, panel, parent_root, scheduled

    manifest_path = parent_root() / "metadata" / "funding_panel_manifest.json"
    published = json.loads(manifest_path.read_text(encoding="utf-8"))
    cutoff = datetime.fromisoformat(published["build_cutoff"])
    decision = time.fromisoformat(published["decision_time"])
    published_columns = tuple(published["built_columns"])
    with tempfile.TemporaryDirectory() as tmp:
        rows, _snapshot, retrieved = panel._parent_rows(Path(tmp), roots=panel.PARENT_RAW_ROOTS + (EFFR_ROOT,))
    extract_sha = hashlib.sha256(panel.H41_EXTRACT.read_bytes()).hexdigest()
    extra_rows = h41.observations(h41.load_extract(panel.H41_EXTRACT), source_sha=extract_sha)
    with declaration.phase3_declaration(), panel._weekly_carry():
        built = build_daily_panel(list(rows) + extra_rows, declaration.registry(), build_cutoff=cutoff, decision_time=decision,
                                  columns=published_columns + declaration.BUILT_COLUMNS + ("effr",),
                                  snapshot_retrieved_at=retrieved)
    if built.refusals:
        raise ValueError(f"the build refused {dict(built.refusals)}")
    observations = scheduled.with_scheduled(built.observations, decision_time=decision)
    version1 = panel.load_manifest(1)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v1.csv"
        panel._write(observations, version1["columns"], path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != version1["sha256"]:
        raise ValueError(f"the version-1 columns of these rows are {digest}, not the manifest's {version1['sha256']}")
    effr = "".join(f"{row.date.isoformat()},{row.values.get('effr')}\n" for row in observations)
    pins = {"parent_commit": panel._parent_commit(), "panel_version": 1, "panel_sha256": digest,
            "effr_series_sha256": hashlib.sha256(effr.encode()).hexdigest(), "rows": len(observations),
            "first_day": observations[0].date.isoformat(), "last_day": observations[-1].date.isoformat()}
    return observations, pins


def _rule():
    from datetime import time

    from repo_model import measurement_fields, scarcity
    from repo_model.asof import InformationRule

    return InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)


def _cutoffs(days, limit):
    first = next(i for i, x in enumerate(days) if x.day >= FIRST_CUTOFF)
    out = [x.day for x in days[first::REFIT_EVERY]]
    return out if limit is None else out[:limit]


def _tables():
    from repo_model import announced_iorb

    from repo_liquidity import parent_root

    table = parent_root() / "tests" / "fixtures" / "snapshots" / "fed-iorb-announcements" / "iorb_changes.csv"
    return scheduled_publications(), announced_iorb.load_announcements(table)


def scheduled_publications():
    from repo_liquidity import scheduled

    return scheduled.load_on_rrp_rates()


def _refit_row(variant, path):
    fit = path.refit
    record = fit.record
    row = {"cutoff": fit.cutoff.isoformat(), "fitted": fit.fitted, "reason": record.get("reason"),
           "kink": record.get("kink"), "slope": record.get("slope"), "intercepts": record.get("intercepts"),
           "objective": record.get("objective"), "pairs": record.get("pairs"),
           "clean_days_per_regime": {str(r): c for r, c in (record.get("regime_counts") or {}).items()},
           "tied": record.get("tied"), "lower": fit.lower, "upper": fit.upper, "draws_fitted": record.get("draws_fitted")}
    return row


def _entry(variant, days, cutoffs, path, seconds):
    rows = []
    for p in path:
        row = _refit_row(variant, p)
        pairs = k.training_days(days, p.refit.cutoff, variant)
        if p.refit.fitted:
            fit = k.fit_kink(pairs, variant)
            row["politis_white_block"] = k.politis_white_block(k.residuals(pairs, variant, fit))
        else:
            row["politis_white_block"] = None
        row["unregimed_days"] = len(k.unregimed_days(days, p.refit.cutoff)) if variant.intercepts == "regime" else None
        rows.append(row)
    return {"refits": rows, "seconds": round(seconds, 1)}


def _summaries(paths, same):
    out = {}
    for name, path in paths.items():
        full, common = k.summarise(path), k.summarise(path, same)
        out[name] = {"all_served_days": full, "common_served_days": common}
    return out


def _compare(summaries):
    """Section 4: each variant against the baseline on the same served days, and the kill read as declared."""
    base = summaries[k.BASELINE.id]["common_served_days"]
    out = {}
    for v in k.VARIANTS:
        if v.id not in summaries:
            continue
        mine = summaries[v.id]["common_served_days"]
        out[v.id] = {
            "worst_gap_points": mine["worst_gap_points"], "baseline_worst_gap_points": base["worst_gap_points"],
            "reduces_worst_gap": (mine["worst_gap_points"] is not None and base["worst_gap_points"] is not None
                                  and mine["worst_gap_points"] < base["worst_gap_points"]),
            "median_width_points": mine["goalpost_2"]["median"], "baseline_median_width_points": base["goalpost_2"]["median"],
            "interval_wider_than_baseline": (v.clean and mine["goalpost_2"]["median"] is not None
                                             and base["goalpost_2"]["median"] is not None
                                             and mine["goalpost_2"]["median"] > base["goalpost_2"]["median"]),
            "not_fitted_refits": mine["not_fitted"], "baseline_not_fitted_refits": base["not_fitted"],
            "goalpost_1_holds": mine["goalpost_1"]["holds"], "goalpost_2_holds": mine["goalpost_2"]["holds"],
        }
    clean = [r for v, r in out.items() if BY_ID[v].clean]
    kill = {
        "no_specification_reduces_the_worst_gap": not any(r["reduces_worst_gap"] for r in out.values()),
        "clean_interval_wider_than_raw": {v: r["interval_wider_than_baseline"] for v, r in out.items() if BY_ID[v].clean},
        "note": "Section 4's kill is 'no specification reduces the worst refit gap below the baseline's, or the clean-day kink's "
                "interval (V1, V4, V5, V6) is wider than the raw one's in median width'. The second clause is reported per clean "
                "variant and not combined here; how the four are read together is the choice rule of protocol §7, not this run's.",
        "any_clean_interval_wider": any(r["interval_wider_than_baseline"] for r in clean),
    }
    return out, kill


def _fmt(value, places=3):
    return "n/a" if value is None else f"{value:.{places}f}"


def markdown(record):
    """The Markdown printed from the record. Never edited by hand."""
    lines = ["# H7m: A's re-specified kink, the six declared variants (development)", "",
             "Generated from `results/h7/kink.json` by `scripts/h7_kink_run.py --render`; never edited by hand.",
             f"Tier: **{record['tier']}**. Development evidence, not a verdict. Declaration: `{record['declaration']}` (with its "
             f"section 7). Variants run: **{record['variant_count']}**.", "",
             f"Panel version {record['pins']['panel_version']} `{record['pins']['panel_sha256']}`; parent "
             f"`{record['pins']['parent_commit']}`; days {record['pins']['first_day']} to {record['window_end']}; training from "
             f"after {record['training_after']}; {record['settings']['replications']} bootstrap draws; "
             f"{len(record['cutoffs'])} refits from {record['cutoffs'][0]} every {record['settings']['refit_every']} days.", "",
             "## The width regimes (read at announcement)", "", "| Regime | Width (bp) | First day | Last day | Days |", "|---|---|---|---|---|"]
    for r in record["regime_table"]:
        lines.append(f"| {r['regime']} | {r['width']} | {r['first']} | {r['last']} | {r['days']} |")
    lines += ["", "## Goalposts 1 and 2, every estimator on the same served days", "",
              "| Estimator | Not fitted | Worst gap (pts) | Gp1 | Median width (pts) | Gp2 | Same served days |", "|---|---|---|---|---|---|---|"]
    for name, s in record["summaries"].items():
        c = s["common_served_days"]
        lines.append(f"| {name} | {c['not_fitted']} | {_fmt(c['worst_gap_points'])} | {'holds' if c['goalpost_1']['holds'] else 'does not hold'} | "
                     f"{_fmt(c['goalpost_2']['median'])} | {'holds' if c['goalpost_2']['holds'] else 'does not hold'} | {c['served_days']} |")
    lines += ["", "## Each variant against the baseline", "", "| Variant | Worst gap | Baseline | Reduces it | Median width | Baseline | "
              "Wider (clean only) | Not fitted | Baseline not fitted |", "|---|---|---|---|---|---|---|---|---|"]
    for v, r in record["comparison"].items():
        lines.append(f"| {v} | {_fmt(r['worst_gap_points'])} | {_fmt(r['baseline_worst_gap_points'])} | {r['reduces_worst_gap']} | "
                     f"{_fmt(r['median_width_points'])} | {_fmt(r['baseline_median_width_points'])} | {r['interval_wider_than_baseline']} | "
                     f"{r['not_fitted_refits']} | {r['baseline_not_fitted_refits']} |")
    kill = record["kill"]
    lines += ["", f"Kill, as declared: no specification reduces the worst gap: **{kill['no_specification_reduces_the_worst_gap']}**; "
              f"clean-day interval wider than the raw one's, per variant: {kill['clean_interval_wider_than_raw']}. {kill['note']}", "",
              "## Clean training days per corridor regime at each refit (floor 50), and the Politis-White block length", "",
              "| Variant | Refit | Status | Days per regime | Block length |", "|---|---|---|---|---|"]
    for name, entry in record["estimators"].items():
        if not BY_ID[name].intercepts == "regime":
            continue
        for r in entry["refits"]:
            status = "fitted" if r["fitted"] else r["reason"]
            lines.append(f"| {name} | {r['cutoff']} | {status} | {r['clean_days_per_regime']} | {_fmt(r['politis_white_block'], 1)} |")
    lines.append("")
    return "\n".join(lines)


def timing(replications, target):
    """Time one refit of every estimator on a synthetic window the size of the real one; reads no real day.

    Measured at `replications` draws and scaled to `target` draws (the bootstrap is the cost)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import test_h7_kink as t

    days = t._pairs(1700, intercepts=(1, 3, 2, 4), regime_lengths=(400, 400, 400, 500), noise=0.5)
    cutoff = days[-1].day
    total = 0.0
    refits = len(range(0, 1500, REFIT_EVERY))
    for variant in (k.BASELINE,) + k.VARIANTS:
        started = clock.time()
        k.refit_on(days, cutoff, variant, replications=replications)
        seconds = clock.time() - started
        total += seconds * target / replications * refits
        print(f"{variant.id}: {seconds:.2f} s per refit at 1700 days, {replications} draws (about {seconds * target / replications:.0f} s at {target})")
    print(f"about {total / 3600:.1f} hours on one core for about {refits} refits of all seven (an upper bound: early refits have fewer days)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replications", type=int, default=demand_curve.REPLICATIONS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--variants", default=",".join(ALL))
    parser.add_argument("--limit-refits", type=int, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--page", type=Path, default=PAGE)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timing", action="store_true", help="time one refit per estimator on a synthetic window; real days untouched")
    parser.add_argument("--render", action="store_true", help="print the page from the record; run nothing")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.timing:
        return timing(20, args.replications)
    if args.render:
        text = markdown(json.loads(args.output.read_text(encoding="utf-8")))
        if args.check:
            if not args.page.is_file() or args.page.read_text(encoding="utf-8") != text:
                print(f"{args.page} is stale: run scripts/h7_kink_run.py --render", file=sys.stderr)
                return 1
            print("h7 kink page: ok")
            return 0
        args.page.write_text(text, encoding="utf-8")
        print(f"wrote {args.page}")
        return 0
    try:
        label_fn = k.parent_turn_label()
    except k.TurnDaysUnavailable as error:
        print(f"not run: {error}", file=sys.stderr)
        return 2

    wanted = [v for v in args.variants.split(",") if v]
    if k.BASELINE.id not in wanted:
        wanted.insert(0, k.BASELINE.id)
    parts = args.output.with_name(args.output.stem + ".parts")
    parts.mkdir(parents=True, exist_ok=True)

    rows, pins = build_rows()
    rows = [row for row in rows if row.date <= demand_curve.LAST_DAY]
    publications, notes = _tables()
    widths = k.width_regimes(rows, publications, notes, decision_time=k.DECISION_TIME)
    table = k.regime_table(widths)
    print("width regimes (read at announcement):", flush=True)
    for r in table:
        print(f"  regime {r.regime}: {r.width} bp, {r.first} to {r.last}, {r.days} days", flush=True)
    # The table is derived over every day, the 25 bp regime before the training start included; the run's list starts after it.
    after = [r for r in table if r.last > k.TRAIN_AFTER]
    try:
        k.check_expected(after)
    except ValueError as error:
        print(f"STOP, finding: {error}", file=sys.stderr)
        return 3

    rule = _rule()
    from repo_model import scarcity

    def build(cut_rows):
        with scarcity.measurement_declaration():
            return k.build_days(cut_rows, rule, publications=publications, notes=notes, label_fn=label_fn)

    days = build(rows)
    cutoffs = _cutoffs(days, args.limit_refits)
    print(f"{len(rows)} rows to {rows[-1].date}; {len(cutoffs)} refits {cutoffs[0]} .. {cutoffs[-1]}", flush=True)

    paths, entries = {}, {}
    for name in wanted:
        variant = BY_ID[name]
        part = parts / f"{name}.json"
        started = clock.time()
        paths[name] = k.real_time_path(days, cutoffs, variant, replications=args.replications, workers=args.workers)
        entries[name] = _entry(variant, days, cutoffs, paths[name], clock.time() - started)
        part.write_text(json.dumps(entries[name], indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        print(f"{name}: {entries[name]['seconds']} s", flush=True)

    # The leakage check: every refit's training days are what the panel cut at its own cutoff gives.
    by_date = {row.date: i for i, row in enumerate(rows)}
    for cutoff in cutoffs:
        k.check_no_future(days, cutoff, lambda until: build(rows[: by_date[until] + 1]))
    print("no refit's training days depend on a later row", flush=True)

    same = k.common_served_days(paths)
    summaries = _summaries(paths, same)
    comparison, kill = _compare(summaries)
    record = {
        "note": "Generated by scripts/h7_kink_run.py; never edited by hand.",
        "tier": "development", "declaration": "docs/stages/h7-kink.md", "directive": "repo-market-liquidity#151",
        "variant_count": len([n for n in wanted if n != k.BASELINE.id]), "pins": pins, "window_end": rows[-1].date.isoformat(),
        "training_after": k.TRAIN_AFTER.isoformat(),
        "settings": {"replications": args.replications, "refit_every": REFIT_EVERY, "first_cutoff": FIRST_CUTOFF.isoformat(),
                     "block_length": k.BLOCK_LENGTH, "level": k.LEVEL, "seed": k.SEED, "regime_floor": k.REGIME_FLOOR,
                     "stability_limit_points": h7.points(goalposts.STABILITY_LIMIT), "width_limit_points": h7.points(goalposts.WIDTH_LIMIT)},
        "cutoffs": [d.isoformat() for d in cutoffs],
        "regime_table": [{"regime": r.regime, "width": r.width, "first": r.first.isoformat(), "last": r.last.isoformat(), "days": r.days}
                         for r in table],
        "same_served_days": len(same), "estimators": entries, "summaries": summaries, "comparison": comparison, "kill": kill,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(markdown(record), encoding="utf-8")
    print(f"wrote {args.output} and {args.page}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
