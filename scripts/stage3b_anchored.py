#!/usr/bin/env python3
"""Stage 3b: fit the buffer on a fixed curve walk-forward and test what `docs/stages/stage-3b.md` says it must show.

    PYTHONPATH=src python3 scripts/stage3b_anchored.py

Builds the Phase 3 panel from tracked fixtures and assembles the two heads to 2025-12-31. Refits from the fixed
curve's last day (2020-03-13), then every 21 business days, on the observations public at each refit (filtered states
only). Writes `results/stage3b/anchored.json`: the walk-forward buffer path, refit stability, the 2025 vs 2018 to
March 2020 benchmark, the full-window fit, the directive's sensitivities, and ON RRP and facility take-up beside the
buffer. Nothing is scored or published. Needs the `state-space` extra.
"""

import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
import tempfile
import warnings
from datetime import date
from pathlib import Path

from repo_liquidity import anchored, latent, panel

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage3b" / "anchored.json"
REFORMS = (date(2021, 3, 31), date(2021, 7, 29), date(2023, 3, 12), date(2023, 7, 12), date(2023, 12, 13))
LEGAL = (date(2021, 3, 31), date(2023, 3, 12))
#: The standing repo facility's move to a fixed rate (`docs/decisions/reform-dates.md`, amendment of 6 October 2026).
SRF_FIXED_RATE = date(2025, 12, 11)
REFIT_EVERY = 21
STABILITY_LIMIT = 0.005
EPISODE_1 = (date(2018, 1, 1), date(2020, 3, 13))
EPISODE_2 = (date(2025, 1, 1), date(2025, 12, 31))
DRIFT = anchored.PARAM_NAMES.index("drift_sd")
CALENDAR_TERMS = [i for i, name in enumerate(anchored.PARAM_NAMES) if name.startswith("c_")]


def benchmark(path):
    """The directive's benchmark on a filtered path: period means, and the interval from the mean state sd."""
    def period(window):
        states = [s for s in path if window[0] <= s.day <= window[1]]
        return {"days": len(states), "first": states[0].day.isoformat(), "last": states[-1].day.isoformat(),
                "mean": round(sum(s.mean for s in states) / len(states), 6),
                "mean_sd": round(sum(math.sqrt(s.variance) for s in states) / len(states), 6)}

    p1, p2 = period(EPISODE_1), period(EPISODE_2)
    difference = p2["mean"] - p1["mean"]
    half = 1.645 * math.sqrt(p1["mean_sd"] ** 2 + p2["mean_sd"] ** 2)
    return {"2018 to March 2020": p1, "2025": p2, "difference": round(difference, 6),
            "interval_90": [round(difference - half, 6), round(difference + half, 6)],
            "shown": difference - half > 0}


def monthly(path):
    out = {}
    for s in path:
        out[s.day.strftime("%Y-%m")] = [round(s.mean, 5), round(math.sqrt(s.variance), 5)]
    return out


def summary(fit, observations, anchor, jumps, scale):
    path = anchored.filter_path(observations, fit.params, anchor=anchor, jump_days=jumps, scale=scale)
    return {
        "converged": fit.converged, "loglike": round(fit.loglike, 4),
        "params": dict(zip(anchored.PARAM_NAMES, [round(v, 8) for v in anchored.natural(fit.params)])),
        "benchmark": benchmark(path),
        "path_monthly": monthly(path),
    }


def main():
    warnings.simplefilter("ignore")
    with ProcessPoolExecutor(max_workers=4, initializer=warnings.simplefilter, initargs=("ignore",)) as pool:
        return _main(pool)


def _main(pool):
    from repo_model.data import load_daily_panel

    anchor, stage2_sha = anchored.load_anchor()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        manifest = panel.build(path)
        rows = load_daily_panel(path)
    observations = anchored.assemble(rows)
    days = [o.day for o in observations]
    jumps = latent.jump_days(observations, REFORMS)
    legal = latent.jump_days(observations, LEGAL)
    with_srf = latent.jump_days(observations, REFORMS + (SRF_FIXED_RATE,))

    # Walk-forward: the first refit on the curve's last day, then every 21 observation days.
    first = days.index(anchor.last_day)
    cutoffs = list(range(first, len(observations), REFIT_EVERY))
    refits, start, walk = [], None, {}
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
        refits.append({"cutoff": cutoff, "fit": fit, "states": {s.day: s for s in states}, "tried": tried})
        # The first refit's filter covers the training window (in-sample by construction); later ones only their block.
        for s in states[(0 if k == 0 else index + 1): end + 1]:
            walk[s.day] = s
        print(f"refit {k + 1}/{len(cutoffs)} {cutoff} converged={fit.converged}", flush=True)

    # 1. Stability: consecutive refits on every date both cover, each through its own cutoff.
    worst, differences, over = {"difference": 0.0}, [], {}
    for before, after in zip(refits, refits[1:]):
        for day, state in before["states"].items():
            if day > before["cutoff"] or day not in after["states"]:
                continue
            gap = abs(after["states"][day].mean - state.mean)
            differences.append(gap)
            if gap >= STABILITY_LIMIT:
                over.setdefault(after["cutoff"].isoformat(), []).append(day)
            if gap > worst["difference"]:
                worst = {"difference": round(gap, 6), "day": day.isoformat(),
                         "refits": [before["cutoff"].isoformat(), after["cutoff"].isoformat()]}
    differences.sort()
    stability = {"limit": STABILITY_LIMIT, "worst": worst,
                 "median": round(differences[len(differences) // 2], 6),
                 "p95": round(differences[int(0.95 * (len(differences) - 1))], 6),
                 "shown": worst["difference"] < STABILITY_LIMIT,
                 "pairs_compared": len(differences),
                 "share_at_or_over_limit": round(sum(d >= STABILITY_LIMIT for d in differences) / len(differences), 6),
                 "over_limit_by_refit": {cut: {"days": len(ds), "first": min(ds).isoformat(), "last": max(ds).isoformat()}
                                         for cut, ds in sorted(over.items())}}

    # 2. The benchmark on the walk-forward path.
    walk_path = [walk[d] for d in sorted(walk)]
    bench = benchmark(walk_path)

    # 3. Full window and the directive's sensitivities, reported and not judged.
    last = days[-1]
    full, full_tried = anchored.fit_best(observations, anchor=anchor, jump_days=jumps, cutoff=last, mapper=pool.map)
    sensitivities = {}
    for name, scale, jdays, held in (
            ("scale_0.002", 0.002, jumps, {}),
            ("scale_0.01", 0.01, jumps, {}),
            ("legal_breaks_only", latent.SCALE, legal, {}),
            ("steps_only_drift_held_at_0", latent.SCALE, jumps, {DRIFT: anchored.HELD_OFF}),
            ("no_calendar_terms", latent.SCALE, jumps, {i: 0.0 for i in CALENDAR_TERMS}),
            ("jump_also_at_2025-12-11", latent.SCALE, with_srf, {})):
        f, _ = anchored.fit_best(observations, anchor=anchor, jump_days=jdays, cutoff=last, scale=scale, held=held,
                                 previous=full.params, mapper=pool.map)
        sensitivities[name] = summary(f, observations, anchor, jdays, scale)

    record = {
        "stage": "3b",
        "directive": "docs/stages/stage-3b.md",
        "anchor": {"intercept": anchor.intercept, "slope": anchor.slope, "last_day": anchor.last_day.isoformat(),
                   "source": "results/stage2/demand_curve.json", "source_sha256": stage2_sha},
        "settings": {"refit_every": REFIT_EVERY, "scale": latent.SCALE,
                     "jump_days": [d.isoformat() for d in jumps],
                     "bounds": {"buffer_max": anchored.BUFFER_MAX, "drift_sd_max_z": anchored.DRIFT_SD_MAX,
                                "jump_sd_max_z": anchored.JUMP_SD_MAX},
                     "window": [days[0].isoformat(), last.isoformat()],
                     "split_declaration_sha256": anchored.split_declaration().sha256},
        "provenance": {"panel_sha256": manifest["sha256"], "parent_commit": manifest["parent_commit"]},
        "refits": len(refits),
        "refits_converged": sum(r["fit"].converged for r in refits),
        "refit_params": {r["cutoff"].isoformat(): {
            "converged": r["fit"].converged,
            **{name: round(v, 6) for name, v in zip(anchored.PARAM_NAMES, anchored.natural(r["fit"].params))
               if name in ("buffer_0", "drift_sd", "jump_sd", "b_sofr_dispersion_bp")},
            "loglike_by_start": {label: round(f.loglike, 4) for label, f in r["tried"]},
            "winning_start": next(label for label, f in r["tried"] if f is r["fit"])} for r in refits},
        "must_show": {"stability": stability, "benchmark": bench,
                      "shown": stability["shown"] and bench["shown"]},
        "walk_forward_monthly": monthly(walk_path),
        "full_window": {**summary(full, observations, anchor, jumps, latent.SCALE),
                        "loglike_by_start": {label: round(f.loglike, 4) for label, f in full_tried}},
        "multi_start": {"start_buffers": list(anchored.START_BUFFERS),
                        "rule": "docs/stages/stage-3b.md, amendment of 6 October 2026: every fit from several starts, "
                                "highest likelihood kept; written after the first run was seen"},
        "sensitivities": sensitivities,
        "beside_not_filtered": anchored.beside(rows, days),
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record["must_show"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
