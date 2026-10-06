#!/usr/bin/env python3
"""Stage 3: fit the latent buffer walk-forward and test what `docs/stages/stage-3.md` says it must show.

    PYTHONPATH=src python3 scripts/stage3_latent.py

Builds the Phase 3 panel from tracked fixtures, assembles the four observation heads to 2025-12-31, refits every 21
business days on the observations public at each refit (filtered states only), and writes
`results/stage3/latent.json`: the walk-forward buffer path, refit stability, the 2025 vs 2018 to March 2020
benchmark, the full-window fit, the sensitivities the directive names, and a corridor-only fit as a labelled
diagnostic. Nothing is scored or published. Needs the `state-space` extra.
"""

import json
import math
import sys
import tempfile
import warnings
from datetime import date
from pathlib import Path

from repo_liquidity import latent, panel

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage3" / "latent.json"
REFORMS = (date(2021, 3, 31), date(2021, 7, 29), date(2023, 3, 12), date(2023, 7, 12), date(2023, 12, 13))
LEGAL = (date(2021, 3, 31), date(2023, 3, 12))
MIN_HISTORY = 120
REFIT_EVERY = 21
STABILITY_LIMIT = 0.005
EPISODE_1 = (date(2018, 1, 1), date(2020, 3, 13))
EPISODE_2 = (date(2025, 1, 1), date(2025, 12, 31))


def summary(fit, observations, jumps, scale):
    path = latent.filter_path(observations, fit.params, jump_days=jumps, scale=scale)
    return {
        "converged": fit.converged, "loglike": round(fit.loglike, 4),
        "params": dict(zip(latent.PARAM_NAMES, [round(v, 8) for v in latent.natural(fit.params)])),
        "buffer_means": {"2018 to March 2020": _mean(path, EPISODE_1), "2025": _mean(path, EPISODE_2)},
        "path_monthly": {s.day.isoformat(): round(s.mean, 5) for s in path if _month_end(path, s)},
    }


def _mean(path, window):
    values = [s.mean for s in path if window[0] <= s.day <= window[1]]
    return round(sum(values) / len(values), 6) if values else None


def _month_end(path, state):
    later = [s for s in path if s.day > state.day]
    return not later or later[0].day.month != state.day.month


def main():
    from repo_model.data import load_daily_panel

    warnings.simplefilter("ignore")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        manifest = panel.build(path)
        observations = latent.assemble(load_daily_panel(path))
    jumps = latent.jump_days(observations, REFORMS)
    legal = latent.jump_days(observations, LEGAL)

    # Walk-forward: refit every 21 observation days on what is public at the refit.
    cutoffs = list(range(MIN_HISTORY - 1, len(observations), REFIT_EVERY))
    refits, start, walk = [], None, {}
    for k, index in enumerate(cutoffs):
        cutoff = observations[index].day
        seen = observations[: index + 1]
        fit = latent.fit(seen, jump_days=[d for d in jumps if d <= cutoff], cutoff=cutoff, start=start)
        start = fit.params
        end = cutoffs[k + 1] if k + 1 < len(cutoffs) else len(observations) - 1
        # The refit's own filtered path through the next refit's cutoff (filtered, never smoothed).
        horizon = observations[: end + 1]
        states = latent.filter_path(horizon, fit.params, jump_days=[d for d in jumps if d <= horizon[-1].day])
        refits.append({"cutoff": cutoff, "fit": fit, "states": {s.day: s for s in states}})
        for s in states[index + 1: end + 1]:
            walk[s.day] = s
        print(f"refit {k + 1}/{len(cutoffs)} {cutoff} converged={fit.converged}", flush=True)

    # 1. Stability: consecutive refits on every date both cover (each through its own cutoff).
    worst = {"difference": 0.0}
    differences = []
    for before, after in zip(refits, refits[1:]):
        for day, state in before["states"].items():
            if day > before["cutoff"] or day not in after["states"]:
                continue
            gap = abs(after["states"][day].mean - state.mean)
            differences.append(gap)
            if gap > worst["difference"]:
                worst = {"difference": round(gap, 6), "day": day.isoformat(),
                         "refits": [before["cutoff"].isoformat(), after["cutoff"].isoformat()]}
    differences.sort()
    stability = {
        "limit": STABILITY_LIMIT, "worst": worst,
        "median": round(differences[len(differences) // 2], 6),
        "p95": round(differences[int(0.95 * (len(differences) - 1))], 6),
        "pairs_compared": len(differences),
        "shown": worst["difference"] < STABILITY_LIMIT,
    }

    # 2. The like-for-like benchmark on the walk-forward path.
    def period(window):
        states = [s for d, s in walk.items() if window[0] <= d <= window[1]]
        mean = sum(s.mean for s in states) / len(states)
        sd = sum(math.sqrt(s.variance) for s in states) / len(states)
        return {"days": len(states), "first": min(walk_d for walk_d in walk if window[0] <= walk_d <= window[1]).isoformat(),
                "mean": round(mean, 6), "mean_sd": round(sd, 6)}

    p1, p2 = period(EPISODE_1), period(EPISODE_2)
    difference = p2["mean"] - p1["mean"]
    sd = math.sqrt(p1["mean_sd"] ** 2 + p2["mean_sd"] ** 2)
    benchmark = {"2018 to March 2020": p1, "2025": p2, "difference": round(difference, 6),
                 "interval_90": [round(difference - 1.645 * sd, 6), round(difference + 1.645 * sd, 6)],
                 "shown": difference - 1.645 * sd > 0}

    # 3. Full-window fit and the directive's sensitivities, plus a corridor-only diagnostic.
    last = observations[-1].day
    full = latent.fit(observations, jump_days=jumps, cutoff=last)
    sensitivities = {}
    for name, scale, jdays in (("scale_0.002", 0.002, jumps), ("scale_0.01", 0.01, jumps),
                               ("legal_breaks_only", latent.SCALE, legal)):
        f = latent.fit(observations, jump_days=jdays, cutoff=last, scale=scale, start=full.params)
        sensitivities[name] = summary(f, observations, jdays, scale)
    corridor_only = [latent.Observation(o.day, o.x, (o.y[0], None, None, None)) for o in observations]
    diag = latent.fit(corridor_only, jump_days=jumps, cutoff=last)
    diagnosis = {"corridor_only": summary(diag, corridor_only, jumps, latent.SCALE),
                 "note": "Diagnosis only, not the directive's model: the corridor head alone, to see what the "
                         "other three heads do to the buffer."}

    record = {
        "stage": "3",
        "directive": "docs/stages/stage-3.md",
        "settings": {"min_history": MIN_HISTORY, "refit_every": REFIT_EVERY, "scale": latent.SCALE,
                     "jump_days": [d.isoformat() for d in jumps], "bounds": {
                         "buffer_max": latent.BUFFER_MAX, "drift_sd_max": latent.DRIFT_SD_MAX,
                         "jump_sd_max": latent.JUMP_SD_MAX},
                     "window": [observations[0].day.isoformat(), last.isoformat()]},
        "provenance": {"panel_sha256": manifest["sha256"], "parent_commit": manifest["parent_commit"]},
        "refits": len(refits),
        "refits_converged": sum(r["fit"].converged for r in refits),
        "must_show": {"stability": stability, "benchmark": benchmark,
                      "shown": stability["shown"] and benchmark["shown"]},
        "walk_forward_monthly": {d.isoformat(): [round(s.mean, 5), round(math.sqrt(s.variance), 5)]
                                 for d, s in sorted(walk.items())
                                 if not any(o > d and (o.year, o.month) == (d.year, d.month) for o in walk)},
        "full_window": summary(full, observations, jumps, latent.SCALE),
        "sensitivities": sensitivities,
        "diagnosis": diagnosis,
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record["must_show"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
