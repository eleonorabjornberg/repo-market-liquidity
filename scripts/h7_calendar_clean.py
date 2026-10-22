#!/usr/bin/env python3
"""H7m, the run of the calendar-clean variants of candidates C and D (`docs/stages/h7-calendar-clean.md`, directive #147).

    PYTHONPATH=src:<parent at the pin>/src python3 scripts/h7_calendar_clean.py [--replications 2000] [--workers 8]
        [--variants C,CV1,CV2,CV3,CV4] [--limit-refits N] [--output results/h7/calendar-clean.json] [--force]

Runs the current C (the baseline, unchanged) and the four variants of it on the development walk-forward (D and its variants are
not run: D dropped under #142, `docs/stages/h7-calendar-clean.md` section 9), and writes the
record `results/h7/calendar-clean.json` and the Markdown printed from it, `docs/research/h7-calendar-clean.md`. Neither is
ever edited by hand. `--render` prints the page again from the tracked record, and `--render --check` exits 1 if the tracked
page is not what the record renders to.

* Rows: the measurement panel version 4 (panel-v4.md) from the tracked fixtures (its digest is checked), with the parent's opt-in `effr`
  column, to `demand_curve.LAST_DAY`, as Stage 6's refits ran. Every scored day is read through the parent's rule, which
  refuses a locked day (`lockbox.require_unlocked`).
* Refits: the first at the first episode's last day, 2020-03-13, then every 21 observation days, as Stages 3c and 6, plus a
  final refit on the last row, 2025-12-31 (her ruling on finding #160, option (b); declaration section 11), for the baseline C and
  CV1 to CV4 alike. A refit serves from the second business day after its cutoff, so the final one serves no day of the window.
* Bootstrap: mean block 10, level 0.90, the parent's seed, `--replications` draws (2000, Stage 2's and Stage 6's count).
* Goalpost 1 (the worst gap between a refit and the one before, against 0.5 points) and goalpost 2 (the median 90% width,
  against 3 points) are read for each estimator and each variant is set beside its own baseline. Beside goalpost 2 the record
  gives each refit's Politis-White block length of its training residuals (reported only: the bootstrap's mean block stays 10).
  Development evidence only: no verdict, no locked day, no goalpost 3, nothing scored against the stress events (that is step 5).
* The exclusion set reads the parent's `turn_days.turn_label` (Q1), which exists from the pin of 08ff67e on: at the
  pin of 8fd2cf8 the run stops with a `ValueError` before fitting anything.
* Each variant's work is kept in `<output>.parts/<variant>.json` when it finishes, and a rerun reuses it (`--force` redoes it).

The record's tier is "development". Nothing here is a verdict (`docs/decisions/measurement-protocol.md` section 1).
"""

import argparse
import json
import sys
import time as clock
from datetime import date, time
from pathlib import Path

from repo_model import measurement_fields, scarcity
from repo_model.asof import InformationRule

from repo_liquidity import demand_curve, goalposts
from repo_liquidity import h7_candidate_c as c
from repo_liquidity import h7_clean as h

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "h7" / "calendar-clean.json"
PAGE = ROOT / "docs" / "research" / "h7-calendar-clean.md"
FIRST_CUTOFF = date(2020, 3, 13)
REFIT_EVERY = 21
BASELINES = ("C",)
ALL = BASELINES + tuple(v.id for v in h.VARIANTS)


def _rule():
    return InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)


def _build_c(rows, weeks):
    with scarcity.measurement_declaration():
        return c.sample_c(rows, _rule(), weeks)


def _inputs(rows):
    return h.read_flags(h.with_quarter_end_window(rows), h.flag_rule(), h.parent_turn_label()), h.left_sides(rows)


def _cutoffs(days, limit):
    """Every 21 observation days from 2020-03-13, plus a final refit on the last row, 2025-12-31 (her ruling on finding #160,
    option (b); `docs/stages/h7-calendar-clean.md` section 11), the same for the baseline C and CV1 to CV4. With `limit` the
    first `limit` refits of the stride only (a partial run, which has no final refit)."""
    first = next(i for i, x in enumerate(days) if x.day >= FIRST_CUTOFF)
    out = [x.day for x in days[first::REFIT_EVERY]]
    if limit is not None:
        return out[:limit]
    final = demand_curve.LAST_DAY
    if not any(x.day == final for x in days):
        raise ValueError(f"the final refit is on {final}, which is not a row of the window")
    return out if out[-1] == final else out + [final]


def _last_samples(days, cutoffs, flags, series, *, episodes=demand_curve.EPISODES, min_scarce=demand_curve.MIN_SCARCE_DAYS_REVISED):
    """The training sample of the baseline C and of each variant at the last two refits, without fitting anything: the days it
    fits on, the episodes that count and the days of those episodes the exclusion set takes out."""
    out = {}
    for cutoff in cutoffs[-2:]:
        sample, labels = c.training_days(days, cutoff, episodes=episodes, min_scarce=min_scarce)
        out.setdefault("C", []).append({"cutoff": cutoff.isoformat(), "training_days": len(sample), "episodes": list(labels),
                                        "dropped_days": 0})
        for v in h.VARIANTS:
            clean = v.days == "clean"
            usable = lambda x: x.week is not None  # noqa: E731
            sample, labels = h.training_days(days, cutoff, flags, v.left, series, usable, clean=clean, episodes=episodes,
                                             min_scarce=min_scarce)
            every, _ = h.training_days(days, cutoff, flags, v.left, series, usable, clean=False, episodes=episodes,
                                       min_scarce=min_scarce)
            out.setdefault(v.id, []).append({"cutoff": cutoff.isoformat(), "training_days": len(sample), "episodes": list(labels),
                                             "dropped_days": len(every) - len(sample)})
    return out


def _block(refit, block):
    """The Politis-White block length of a refit's training residuals: the refit's own record, else `block(refit)`."""
    if "pw_block" in refit.record:
        return refit.record["pw_block"]
    return None if block is None or not refit.fitted else block(refit)


def _refit_row(refit, block=None):
    record = refit.record
    params = getattr(refit, "shares", None) if hasattr(refit, "shares") else getattr(refit, "params", None)
    return {"cutoff": refit.cutoff.isoformat(), "status": record.get("status", "fitted" if refit.fitted else "no fit"),
            "fitted": refit.fitted, "parameters": None if params is None else list(params), "kink": refit.kink,
            "intercept": refit.intercept, "slope": refit.slope, "objective_or_sse": refit.sse, "training_days": refit.pairs,
            "dropped_days": record.get("dropped"), "episodes": list(refit.episodes), "starts_agree": refit.starts_agree,
            "tied_span": record.get("tied_span"), "draws": len(refit.draws), "break_weeks": [w.isoformat() for w in refit.break_weeks],
            "politis_white_block": _block(refit, block)}


def _block_summary(rows):
    blocks = sorted(r["politis_white_block"] for r in rows if r["politis_white_block"] is not None)
    if not blocks:
        return {"refits": 0, "median": None, "max": None}
    return {"refits": len(blocks), "median": blocks[len(blocks) // 2] if len(blocks) % 2 else (blocks[len(blocks) // 2 - 1] + blocks[len(blocks) // 2]) / 2,
            "max": blocks[-1]}


def _entry(paths, seconds, block=None):
    """One estimator's entry. `block(refit)` gives the Politis-White block length of a refit whose record does not hold it (the
    baseline's)."""
    summary = h.summarise(paths)
    rows = [_refit_row(p.refit, block) for p in paths]
    summary["politis_white_block"] = _block_summary(rows)
    return {"summary": summary, "refits": rows,
            "gaps_points": {day.isoformat(): c.points(gap) for p in paths for day, gap in sorted(p.gaps.items())},
            "break_days": sorted({day.isoformat() for p in paths for day in p.break_days}), "seconds": round(seconds, 1)}


def _episode_counts(days, flags, usable):
    out = {}
    pool = [x for x in days if usable(x)]
    for label, first, last in demand_curve.EPISODES:
        inside = [x for x in pool if first <= x.day <= last]
        clean = h.clean_days(inside, flags)
        scarce = lambda xs: sum(1 for x in xs if x.ratio is not None and x.ratio < demand_curve.SCARCE_BELOW)  # noqa: E731
        out[label] = {"training_days": len(inside), "scarce": scarce(inside), "clean_days": len(clean),
                      "clean_scarce": scarce(clean), "counts": scarce(inside) >= demand_curve.MIN_SCARCE_DAYS_REVISED}
    return out


def _compare(entries):
    out = {}
    for v in h.VARIANTS:
        variant, candidate, left = v.id, v.candidate, v.left
        if variant in entries and candidate in entries:
            mine, base = entries[variant]["summary"], entries[candidate]["summary"]
            out[variant] = {
                "against": candidate, "left_side": left, "days": v.days, "objective": v.objective,
                "pw_block_median": mine["politis_white_block"]["median"], "baseline_pw_block_median": base["politis_white_block"]["median"],
                "worst_gap_points": (mine["goalpost_1"]["worst"] or {}).get("gap_points"),
                "baseline_worst_gap_points": (base["goalpost_1"]["worst"] or {}).get("gap_points"),
                "median_width_points": mine["goalpost_2"]["median_points"],
                "baseline_median_width_points": base["goalpost_2"]["median_points"],
                "goalpost_1_holds": mine["goalpost_1"]["holds"], "baseline_goalpost_1_holds": base["goalpost_1"]["holds"],
                "goalpost_2_holds": mine["goalpost_2"]["holds"], "baseline_goalpost_2_holds": base["goalpost_2"]["holds"],
                "not_fitted_refits": mine["not_fitted_refits"], "baseline_not_fitted_refits": base["not_fitted_refits"],
                "refit_status": mine["refit_status"]}
    return out


def _fmt(value, places=3):
    if value is None:
        return "n/a"
    return "no interval" if value == float("inf") else f"{value:.{places}f}"


def _verdict(goalpost):
    """`holds` or `does not hold`, and `none compared` when no day was compared or served (so nothing was read)."""
    if not (goalpost.get("days_compared") or goalpost.get("days")):
        return "none compared"
    return "holds" if goalpost["holds"] else "does not hold"


def markdown(record):
    """The Markdown printed from the record. Never edited by hand."""
    lines = ["# H7m: the calendar-clean variants of candidate C (development)", "",
             "Generated from `results/h7/calendar-clean.json` by `scripts/h7_calendar_clean.py --render`; never edited by hand.",
             f"Tier: **{record['tier']}**. Development evidence, not a verdict. Declaration: `{record['declaration']}`. "
             f"Variants added: **{record['variant_count_added']}**.", "",
             f"Panel version {record['pins']['panel_version']} `{record['pins']['panel_sha256']}`; parent "
             f"`{record['pins']['parent_commit']}`; `effr` series `{record['pins']['effr_series_sha256']}`; days "
             f"{record['pins']['first_day']} to {record['window_end']}; {record['settings']['replications']} bootstrap draws; "
             f"{len(record['cutoffs'])} refits from {record['cutoffs'][0]} every {record['settings']['refit_every']} observation days"
             + (f", plus a final refit on {record['cutoffs'][-1]}." if record['cutoffs'][-1] == demand_curve.LAST_DAY.isoformat() else "."),
             "",
             "## The scarce episodes, with and without the calendar days", "",
             "The floor of 60 scarce days is read on all days, the same for every variant; the clean variants then fit on the "
             "counted episode's clean days (declaration section 10, her ruling on PR #150).", "",
             "| Candidate | Episode | Training days | Scarce | Clean days | Clean scarce | Counts (all variants) |",
             "|---|---|---|---|---|---|---|"]
    for candidate, episodes in record["episode_counts"].items():
        for label, e in episodes.items():
            lines.append(f"| {candidate} | {label} | {e['training_days']} | {e['scarce']} | {e['clean_days']} | "
                         f"{e['clean_scarce']} | {e['counts']} |")
    lines += ["", "## Goalposts 1 and 2 on development days", "",
              "| Estimator | Days | Objective | Left side | Refits | Not fitted | Status | Worst gap (pts) | Gp1 | Median width (pts) | Gp2 "
              "| Politis-White block, median (max) | Served days |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    specs = {v.id: v for v in h.VARIANTS}
    for name, entry in record["estimators"].items():
        s = entry["summary"]
        spec = specs.get(name)
        days, objective, left = (spec.days, spec.objective, spec.left) if spec else ("all", "ls", "corridor")
        status = ", ".join(f"{k}: {v}" for k, v in sorted(s["refit_status"].items()))
        worst = (s["goalpost_1"]["worst"] or {}).get("gap_points")
        block = s["politis_white_block"]
        pw = "n/a" if not block["refits"] else f"{_fmt(block['median'], 1)} ({_fmt(block['max'], 1)}) over {block['refits']} refits"
        lines.append(f"| {name} | {days} | {objective} | {left} | {s['refits']} | {s['not_fitted_refits']} | {status} | "
                     f"{_fmt(worst)} | {_verdict(s['goalpost_1'])} | {_fmt(s['goalpost_2']['median_points'])} | "
                     f"{_verdict(s['goalpost_2'])} | {pw} | {s['served_days']} |")
    lines += ["", "Goalpost 1 is read on the gaps between consecutive refits on the days both serve; a refit that is not fitted or "
              "not identified serves nothing, so it makes no gap and is counted beside the figure. Goalpost 2's median counts a "
              "served day with no interval, and a day a refit left unserved, as over the limit.", "",
              "The Politis-White block length (Politis and White 2004, with the correction of Patton, Politis and White 2009) is "
              "computed from each fitted refit's training residuals, taken in time order, and reported only. The bootstrap that "
              "gives the 90% interval keeps its mean block of "
              f"{record['settings']['block_length']}: a figure far above it means the interval may be too narrow, and whether a "
              "longer block is needed is Eleonora's call on that figure. Days dropped or separated between episodes are not "
              "closed up or marked, as in the bootstrap itself.", "",
              "## Each variant against its own baseline", "",
              "| Variant | Against | Worst gap | Baseline | Median width | Baseline | Not fitted | Baseline not fitted |",
              "|---|---|---|---|---|---|---|---|"]
    for variant, row in record["comparison"].items():
        lines.append(f"| {variant} | {row['against']} | {_fmt(row['worst_gap_points'])} | {_fmt(row['baseline_worst_gap_points'])} | "
                     f"{_fmt(row['median_width_points'])} | {_fmt(row['baseline_median_width_points'])} | "
                     f"{row['not_fitted_refits']} | {row['baseline_not_fitted_refits']} |")
    names = list(record["estimators"])
    lines += ["", "## Training sample size at each refit (days fitted on)", "",
              "| Refit | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for i, cutoff in enumerate(record["cutoffs"]):
        cells = [str(entry["refits"][i]["training_days"]) if i < len(entry["refits"]) and entry["refits"][i]["fitted"] else "not fitted"
                 for entry in record["estimators"].values()]
        lines.append(f"| {cutoff} | " + " | ".join(cells) + " |")
    lines += ["", f"Days whose flags the parent's rule cannot read (left out of every clean fit): "
              f"{', '.join(record['unread_flag_days']) or 'none'}.", "",
              "## Not run", ""]
    for name, reason in record["not_run"].items():
        lines.append(f"- {name}: {reason}; it does not count as a run variant.")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replications", type=int, default=demand_curve.REPLICATIONS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--variants", default=",".join(ALL))
    parser.add_argument("--limit-refits", type=int, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--page", type=Path, default=PAGE)
    parser.add_argument("--render", action="store_true", help="print the page from the record; run nothing")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.render:
        text = markdown(json.loads(args.output.read_text(encoding="utf-8")))
        if args.check:
            if not args.page.is_file() or args.page.read_text(encoding="utf-8") != text:
                print(f"{args.page} is stale: run scripts/h7_calendar_clean.py --render", file=sys.stderr)
                return 1
            print("h7 calendar-clean page: ok")
            return 0
        args.page.write_text(text, encoding="utf-8")
        print(f"wrote {args.page}")
        return 0
    wanted = [v for v in args.variants.split(",") if v]
    unknown = [v for v in wanted if v not in ALL]
    if unknown:
        parser.error(f"unknown variant {unknown}: D and its variants are {h.D_NOT_RUN}; the run has {', '.join(ALL)}")
    parts = args.output.with_name(args.output.stem + ".parts")
    parts.mkdir(parents=True, exist_ok=True)

    rows, pins = h.build_rows()
    rows = [row for row in rows if row.date <= demand_curve.LAST_DAY]
    weeks = c.tracked_weeks()
    days_c = _build_c(rows, weeks)
    flags, series = _inputs(rows)
    cutoffs = _cutoffs(days_c, args.limit_refits)
    print(f"{len(rows)} rows to {rows[-1].date}; {len(cutoffs)} refits {cutoffs[0]} .. {cutoffs[-1]}", flush=True)

    def variant_job(v):
        return lambda: h.path_c(days_c, cutoffs, flags, v.left, series, replications=args.replications, workers=args.workers,
                                clean=v.days == "clean", objective=v.objective)

    jobs = {"C": lambda: h.baseline_path_c(days_c, cutoffs, replications=args.replications)}
    jobs.update({v.id: variant_job(v) for v in h.VARIANTS})
    blocks = {"C": lambda refit: h.politis_white_block(h.baseline_residuals_c(days_c, refit))}
    entries = {}
    for name in wanted:
        part = parts / f"{name}.json"
        if part.exists() and not args.force:
            entries[name] = json.loads(part.read_text(encoding="utf-8"))
            print(f"{name}: reused {part.name}", flush=True)
            continue
        started = clock.time()
        paths = jobs[name]()
        entries[name] = _entry(paths, clock.time() - started, blocks.get(name))
        part.write_text(json.dumps(entries[name], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{name}: {entries[name]['seconds']} s, {entries[name]['summary']['refit_status']}", flush=True)

    # The leakage check: each variant refit's training sample is what the panel cut at its own cutoff gives.
    def build_c(cut):
        cut_flags, cut_series = _inputs(cut)
        return _build_c(cut, weeks), cut_flags, cut_series

    for v in h.VARIANTS:
        if v.id in wanted:
            h.check_no_future(rows, cutoffs, build_c, v.left, lambda x: x.week is not None, clean=v.days == "clean")
            print(f"{v.id}: no refit's sample depends on a later row", flush=True)

    record = {
        "note": "Generated by scripts/h7_calendar_clean.py; never edited by hand.",
        "tier": "development", "declaration": "docs/stages/h7-calendar-clean.md", "directive": "repo-market-liquidity#147",
        "variant_count_added": len(h.VARIANTS),
        "not_run": {name: h.D_NOT_RUN for name in ("D",) + tuple(v.id for v in h.D_VARIANTS)},
        "turn_label": "repo_model.turn_days.turn_label of the parent at the pin (Q1)", "pins": pins, "window_end": rows[-1].date.isoformat(),
        "settings": {"replications": args.replications, "refit_every": REFIT_EVERY, "first_cutoff": FIRST_CUTOFF.isoformat(),
                     "block_length": h.BLOCK_LENGTH, "level": h.LEVEL, "seed": h.SEED,
                     "stability_limit_points": c.points(goalposts.STABILITY_LIMIT),
                     "width_limit_points": c.points(goalposts.WIDTH_LIMIT)},
        "cutoffs": [day.isoformat() for day in cutoffs],
        "final_refit_samples": _last_samples(days_c, cutoffs, flags, series),
        "unread_flag_days": sorted(day.isoformat() for day, f in flags.items() if f.unread),
        "episode_counts": {"C": _episode_counts(days_c, flags, lambda x: x.week is not None and x.corridor is not None)},
        "estimators": entries, "comparison": _compare(entries),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(markdown(record), encoding="utf-8")
    print(f"wrote {args.output} and {args.page}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
