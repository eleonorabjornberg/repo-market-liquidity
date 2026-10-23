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
* Rows: the measurement panel version 4 (`h10_apply.PANEL_VERSION`) from the tracked fixtures (digest checked) with the parent's opt-in `effr` column, to
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
import hashlib
import json
import math
import sys
import time as clock
from datetime import date
from pathlib import Path

from repo_liquidity import demand_curve, goalposts
from repo_liquidity.h10_apply import PANEL_VERSION
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
    """The measurement panel's rows (the current version's columns, byte for byte) with the parent's opt-in `effr` column added.

    Built as `panel.build` builds the current version from the tracked fixtures, with no network, except that the parent's EFFR snapshots
    are read as well. Returns the rows and a dict of the pins.

    Raises:
        ValueError: the current version's columns do not reproduce the manifest's digest, a column is refused, or the dates differ.
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
    manifest = panel.load_manifest(PANEL_VERSION)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v1.csv"
        panel._write(observations, manifest["columns"], path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"the version-{PANEL_VERSION} columns of these rows are {digest}, not the manifest's {manifest['sha256']}")
    effr = "".join(f"{row.date.isoformat()},{row.values.get('effr')}\n" for row in observations)
    pins = {"parent_commit": panel._parent_commit(), "panel_version": PANEL_VERSION, "panel_sha256": digest,
            "effr_series_sha256": hashlib.sha256(effr.encode()).hexdigest(), "rows": len(observations),
            "first_day": observations[0].date.isoformat(), "last_day": observations[-1].date.isoformat()}
    return observations, pins


def _rule():
    from datetime import time

    from repo_model import scarcity
    from repo_model.asof import InformationRule

    from repo_liquidity import declaration

    # Phase 3's registry, as `h7_kink.flag_rule` and `demand_curve` use: the legs include `bank_total_assets` (the D1 overlay),
    # which the parent's bare registry does not classify at the pin.
    with declaration.phase3_declaration():
        return InformationRule(declaration.registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)


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
    if "superseded" in record:
        lines += ["", f"Goalposts 1 and 2 are read in points (limits 0.5 and 3). This record replaces the one with sha256 "
                  f"`{record['superseded']['sha256']}`: {record['superseded']['reason']} The breach counts of goalpost 1 are removed: "
                  f"{k.BREACHES_NOTE}."]
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


#: Clean training days at the first and the last refit of the run, and the refits, as `results/h7/kink.json` records them (V3).
TIMING_SIZES = (436, 1864)
TIMING_REFITS = 69


def refit_sizes(first, last, refits):
    """The training-window sizes of `refits` refits growing evenly from `first` to `last`."""
    if refits < 2:
        return [first]
    return [round(first + (last - first) * i / (refits - 1)) for i in range(refits)]


def estimate_core_seconds(small, large, sizes):
    """Core-seconds of one estimator over refits of `sizes` days, from one refit timed at each of two window sizes.

    `small` and `large` are (days, seconds) pairs; the cost between and beyond them follows the power law through the two."""
    (n0, t0), (n1, t1) = small, large
    power = math.log(t1 / t0) / math.log(n1 / n0)
    return sum(t0 * (n / n0) ** power for n in sizes)


def wall_seconds(core_seconds, workers):
    """The refits are independent (`real_time_path`), so `workers` processes divide the core time."""
    return core_seconds / workers


def _timed(variant, size, replications, target):
    """Seconds for one refit of `variant` at `target` draws on a synthetic window of `size` days (measured at `replications`)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import test_h7_kink as t

    quarter = size // 4
    days = t._pairs(size, intercepts=(1, 3, 2, 4), regime_lengths=(quarter, quarter, quarter, size - 3 * quarter), noise=0.5)
    started = clock.time()
    k.refit_on(days, days[-1].day, variant, replications=replications)
    return (clock.time() - started) * target / replications


def timing(replications, target, workers=1, sizes=TIMING_SIZES, refits=TIMING_REFITS):
    """Estimate the run on a synthetic window; reads no real day.

    One refit per estimator is timed at the first and at the last window size, at `replications` draws, scaled to `target`
    draws (the bootstrap is the cost). The power law through the two is summed over the refits' sizes and divided by `workers`.
    Review of 06beb39: the earlier harness timed all refits at the largest window, which overstated this run about tenfold.
    The figure is for the machine it runs on: run it on the machine that will do the run.
    """
    schedule = refit_sizes(sizes[0], sizes[1], refits)
    total = 0.0
    for variant in (k.BASELINE,) + k.VARIANTS:
        small = (sizes[0], _timed(variant, sizes[0], replications, target))
        large = (sizes[1], _timed(variant, sizes[1], replications, target))
        seconds = estimate_core_seconds(small, large, schedule)
        total += seconds
        print(f"{variant.id}: {small[1]:.1f} s per refit at {small[0]} days, {large[1]:.1f} s at {large[0]} ({target} draws); "
              f"{seconds / 60:.1f} core-minutes over {refits} refits")
    print(f"about {total / 3600:.2f} core-hours for {refits} refits of all seven; about {wall_seconds(total, workers) / 60:.0f} minutes "
          f"with {workers} workers on this machine")
    return 0


#: The record as 06beb39 published it, whose goalposts compared points with limits in shares (#166); replaced under #167.
SUPERSEDED_SHA256 = "f6292a314a792961e52c6fbe5a64f14db5be8e08f76fff61102fa04d198a7395"
SUPERSEDED_REASON = ("goalposts 1 and 2 compared gaps and widths in points with limits in shares (0.005 and 0.03) instead of points "
                     "(0.5 and 3); recomputed in points from the record's medians, worst gaps and unfitted refits, nothing re-run "
                     "(Eleonora's ruling on repo-market-liquidity#166, directive #167). The superseded record was never on main.")


def restate(output):
    """Rewrite `output` with goalposts 1 and 2 in points (`k.restate_goalposts`); only the record whose sha256 is the superseded one."""
    raw = output.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SUPERSEDED_SHA256:
        print(f"{output} is not the record with sha256 {SUPERSEDED_SHA256}: nothing restated", file=sys.stderr)
        return 1
    record = k.restate_goalposts(json.loads(raw), superseded=SUPERSEDED_SHA256, reason=SUPERSEDED_REASON)
    output.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"restated {output}; now render the page")
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
    parser.add_argument("--restate", action="store_true",
                        help="restate goalposts 1 and 2 in points from the record (#167); runs nothing, and refuses any other record")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.timing:
        return timing(20, args.replications, args.workers)
    if args.restate:
        return restate(args.output)
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
    after = k.after_training_start(table)
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
