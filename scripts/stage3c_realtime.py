#!/usr/bin/env python3
"""Stage 3c: Stage 3b's model, judged on the real-time buffer (`docs/stages/stage-3c.md`).

    PYTHONPATH=src python3 scripts/stage3c_realtime.py

Repeats Stage 3b's walk-forward exactly (panel version 1, the same refits from the same starts, `anchored.fit_best`),
then applies Stage 3c's stability test (`anchored.realtime_stability`) and the benchmark, and writes
`results/stage3c/realtime.json`. It also reports Stage 3b's old test and the full-window shift beside them. Nothing
is scored or published. Needs the `state-space` extra.
"""

import importlib.util
import json
import math
import sys
import tempfile
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from repo_liquidity import anchored, latent, panel

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage3c" / "realtime.json"
STABILITY_LIMIT = 0.005


def _stage3b():
    spec = importlib.util.spec_from_file_location("stage3b", ROOT / "scripts" / "stage3b_anchored.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    warnings.simplefilter("ignore")
    with ProcessPoolExecutor(max_workers=4, initializer=warnings.simplefilter, initargs=("ignore",)) as pool:
        return _main(pool)


def _main(pool):
    from repo_model.data import load_daily_panel

    s3b = _stage3b()
    anchor, stage2_sha = anchored.load_anchor()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        manifest = panel.build(path, version=1)
        rows = load_daily_panel(path)
    observations = anchored.assemble(rows)
    days = [o.day for o in observations]
    jumps = latent.jump_days(observations, s3b.REFORMS)

    first = days.index(anchor.last_day)
    cutoffs = list(range(first, len(observations), s3b.REFIT_EVERY))
    refits, start, walk, old_states = [], None, {}, []
    for k, index in enumerate(cutoffs):
        cutoff = days[index]
        fit, tried = anchored.fit_best(observations[: index + 1], anchor=anchor,
                                       jump_days=[d for d in jumps if d <= cutoff], cutoff=cutoff, previous=start,
                                       mapper=pool.map)
        start = fit.params
        end = cutoffs[k + 1] if k + 1 < len(cutoffs) else len(observations) - 1
        horizon = observations[: end + 1]
        states = anchored.filter_path(horizon, fit.params, anchor=anchor,
                                      jump_days=[d for d in jumps if d <= horizon[-1].day])
        refits.append((index, fit))
        old_states.append({"cutoff": cutoff, "states": {s.day: s for s in states}})
        for s in states[(0 if k == 0 else index + 1): end + 1]:
            walk[s.day] = s
        print(f"refit {k + 1}/{len(cutoffs)} {cutoff} converged={fit.converged}", flush=True)

    # 1. Stage 3c's test: the buffer a forecast reads, refit in force against the refit before it.
    realtime = anchored.realtime_stability(observations, [(i, f.params) for i, f in refits], anchor=anchor,
                                           jump_days=jumps)
    worst = realtime["worst"]
    stability = {
        "test": "docs/stages/stage-3c.md, must-show 1",
        "limit": STABILITY_LIMIT,
        "days_compared": realtime["days_compared"],
        "worst": {**worst, "gap": round(worst["gap"], 6)},
        "median": round(realtime["median"], 6),
        "p95": round(realtime["p95"], 6),
        "days_at_or_over_limit": sorted(day for day, gap in realtime["gaps"].items() if gap >= STABILITY_LIMIT),
        "largest": [{"day": day, "gap": round(gap, 6)}
                    for day, gap in sorted(realtime["gaps"].items(), key=lambda item: -item[1])[:10]],
        "shown": worst["gap"] < STABILITY_LIMIT,
    }

    # 2. The benchmark, as in Stage 3b.
    walk_path = [walk[d] for d in sorted(walk)]
    bench = s3b.benchmark(walk_path)

    # 3. Reported: Stage 3b's old test, and the full-window shift.
    worst_old, differences = {"difference": 0.0}, []
    for before, after in zip(old_states, old_states[1:]):
        for day, state in before["states"].items():
            if day > before["cutoff"] or day not in after["states"]:
                continue
            gap = abs(after["states"][day].mean - state.mean)
            differences.append(gap)
            if gap > worst_old["difference"]:
                worst_old = {"difference": round(gap, 6), "day": day.isoformat(),
                             "refits": [before["cutoff"].isoformat(), after["cutoff"].isoformat()]}
    old_test = {"test": "docs/stages/stage-3b.md, must-show 1 (reported, not judged)", "worst": worst_old,
                "share_at_or_over_limit": round(sum(d >= STABILITY_LIMIT for d in differences) / len(differences), 6)}
    full, _ = anchored.fit_best(observations, anchor=anchor, jump_days=jumps, cutoff=days[-1], mapper=pool.map)
    full_path = anchored.filter_path(observations, full.params, anchor=anchor, jump_days=jumps)

    record = {
        "stage": "3c",
        "directive": "docs/stages/stage-3c.md",
        "anchor": {"intercept": anchor.intercept, "slope": anchor.slope, "last_day": anchor.last_day.isoformat(),
                   "source_sha256": stage2_sha},
        "settings": {"panel_version": 1, "refit_every": s3b.REFIT_EVERY, "scale": latent.SCALE,
                     "jump_days": [d.isoformat() for d in jumps], "start_buffers": list(anchored.START_BUFFERS),
                     "window": [days[0].isoformat(), days[-1].isoformat()]},
        "provenance": {"panel_sha256": manifest["sha256"], "parent_commit": manifest["parent_commit"]},
        "refits": len(refits),
        "refits_converged": sum(f.converged for _, f in refits),
        "must_show": {"stability": stability, "benchmark": bench,
                      "shown": stability["shown"] and bench["shown"]},
        "reported": {
            "old_stability_test": old_test,
            "full_window": {"loglike": round(full.loglike, 4), "benchmark": s3b.benchmark(full_path),
                            "caveats": "docs/stages/stage-3b.md, amendment 1: it needs drift between reform dates; "
                                       "the rise came in late 2022, not on a reform date; it vanishes at s = 0.002"},
        },
        "walk_forward_monthly": s3b.monthly(walk_path),
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record["must_show"], indent=2)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
