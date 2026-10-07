#!/usr/bin/env python3
"""Stage 5a, must-show 2 (`docs/stages/stage-5a.md`): a replayed day reproduces the development run.

    PYTHONPATH=src python3 scripts/stage5a_replay.py

For the first scored day of every 2025 refit block, the log's forecast core (`live.forecast`) is run on the
development panel cut at that day. Each arm's CRPS, from its forecast quantiles and the realized spread, must equal
`results/stage4/comparison.json`'s per-origin loss for that day, to 1e-9 bp. Each arm's P(spread > +5 bp) and
P(spread > +10 bp) must equal the development run's, to 1e-12.

The development probabilities are recomputed here by the same code as `scripts/stage4_brier.py`, because that record
keeps the Brier score, not each day's probability. Before any comparison, their Brier scores must equal the record's.
Writes `results/stage5a/replay.json`. Scores nothing new and publishes nothing.
"""

import importlib.util
import json
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage5a" / "replay.json"
CRPS_TOLERANCE_BP = 1e-9
PROBABILITY_TOLERANCE = 1e-12
FIRST_DAY = date(2025, 1, 1)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pass_module():
    return _load("stage4_curve_pass", ROOT / "scripts" / "stage4_curve_pass.py")


def replay_days(rows):
    """The first scored day of every refit block in 2025, on the parent's fold grid."""
    from repo_model.asof import InformationRule, fold_grid, refit_blocks

    from repo_liquidity import curve_feature

    rule = InformationRule(curve_feature.registry(), curve_feature.DECLARED_FEATURES,
                           decision_time=curve_feature.DECISION_TIME)
    dates = [row.date for row in rows]
    grid = [index for index in fold_grid(dates, rule.registry, decision_time=rule.decision_time,
                                         minimum_history=curve_feature.MINIMUM_HISTORY, horizon=rule.horizon)
            if dates[index] <= curve_feature.LAST_DAY]
    return [dates[block[0]] for block in refit_blocks(grid, curve_feature.REFIT_EVERY) if dates[block[0]] >= FIRST_DAY]


def development_probabilities(rows):
    """Each 2025 day's P(spread > tau) from the development run, for both arms, with the run's Brier scores."""
    from repo_model import baseline
    from repo_model.onset import LEAP_JUMP_BP

    from repo_liquidity import curve_feature, live

    taus = live.declared_taus()
    out, brier = {}, {}
    for arm, with_feature, features in (("model_a", False, curve_feature.PUBLISHED_FEATURES),
                                        ("model_b", True, curve_feature.DECLARED_FEATURES)):
        name, predictor, online, _benchmarks = curve_feature.published_exceedance_arm(with_feature=with_feature)
        report = baseline.rolling_exceedance_backtest(
            rows, predictor=predictor, model_name=name, features=features, registry=curve_feature.registry(),
            decision_time=curve_feature.DECISION_TIME, taus=taus, minimum_history=curve_feature.MINIMUM_HISTORY,
            refit_every=curve_feature.REFIT_EVERY, end=curve_feature.LAST_DAY, leap_jump_bp=LEAP_JUMP_BP[1],
            online_calibration=online)
        out[arm], brier[arm] = {}, {}
        for position, tau in enumerate(report.taus):
            predicted, _, realized = report.at_tau(position)
            brier[arm][f"{tau:g}"] = sum((p - o) ** 2 for p, o in zip(predicted, realized)) / len(realized)
            for day, value in zip(report.scored_dates, predicted):
                if day >= FIRST_DAY:
                    out[arm].setdefault(day.isoformat(), {})[f"+{tau:g}bp"] = value
    return out, brier


def _replay_one(day_iso):
    """Worker: the log's forecast core on the development panel cut at `day`."""
    import warnings

    warnings.simplefilter("ignore")
    from repo_liquidity import curve_feature, live

    rows, _manifest = _pass_module().load_rows()
    day = date.fromisoformat(day_iso)
    cut = [row for row in rows if row.date <= day]
    with curve_feature.stage4_declaration():
        result = live.forecast(cut)
    result["realized_bps"] = cut[-1].spread_bps
    return day_iso, result


def main():
    from repo_model.metrics import crps_from_quantiles

    from repo_liquidity import curve_feature

    pass_module = _pass_module()
    rows, manifest = pass_module.load_rows()
    comparison = json.loads((ROOT / "results" / "stage4" / "comparison.json").read_text(encoding="utf-8"))
    brier_record = json.loads((ROOT / "results" / "stage4" / "brier.json").read_text(encoding="utf-8"))
    losses = {entry["scored_date"]: entry for entry in comparison["parent_document"]["comparison"]["per_origin"]}

    with curve_feature.stage4_declaration():
        days = replay_days(rows)
        probabilities, brier = development_probabilities(rows)
    recorded = brier_record["with_without"]["by_tau"]
    brier_check = {tau: {"model_a": [brier["model_a"][tau], recorded[tau]["benchmark_brier"]],
                         "model_b": [brier["model_b"][tau], recorded[tau]["model_brier"]]}
                   for tau in ("5", "10")}
    brier_held = all(abs(ours - theirs) <= PROBABILITY_TOLERANCE
                     for arms in brier_check.values() for ours, theirs in arms.values())

    # Spawned, not forked: the parent process has already initialised OpenMP through the development run.
    with ProcessPoolExecutor(max_workers=3, mp_context=multiprocessing.get_context("spawn")) as pool:
        replayed = dict(pool.map(_replay_one, [day.isoformat() for day in days]))

    entries, held = [], brier_held
    for day in days:
        key = day.isoformat()
        result = replayed[key]
        levels = result["distributions"]["levels"]
        entry = {"day": key, "curve": result["curve"]}
        for arm, loss_key in (("model_a", "loss_a_bps"), ("model_b", "loss_b_bps")):
            crps = crps_from_quantiles(levels, result["distributions"][arm]["quantiles_bps"], result["realized_bps"])
            gap = abs(crps - losses[key][loss_key])
            cells = {cell: [result["probabilities"][arm][cell], probabilities[arm][key][cell]]
                     for cell in ("+5bp", "+10bp")}
            probability_gap = max(abs(ours - theirs) for ours, theirs in cells.values())
            entry[arm] = {"crps_bps": crps, "development_crps_bps": losses[key][loss_key], "crps_gap_bp": gap,
                          "probabilities": cells, "probability_gap": probability_gap}
            held = held and gap <= CRPS_TOLERANCE_BP and probability_gap <= PROBABILITY_TOLERANCE
        entries.append(entry)

    out = {
        "stage": "5a, must-show 2: replay",
        "what": ("The log's forecast core on the development panel cut at the first scored day of every 2025 refit "
                 "block, against the Stage 4 development run."),
        "held": held,
        "tolerances": {"crps_bp": CRPS_TOLERANCE_BP, "probability": PROBABILITY_TOLERANCE},
        "development_brier_reproduces_record": {"held": brier_held, "by_tau": brier_check},
        "days": entries,
        "provenance": pass_module.provenance(manifest),
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    worst_crps = max(entry[arm]["crps_gap_bp"] for entry in entries for arm in ("model_a", "model_b"))
    worst_probability = max(entry[arm]["probability_gap"] for entry in entries for arm in ("model_a", "model_b"))
    print(f"replay {'held' if held else 'did not hold'}: {len(entries)} days, largest CRPS gap {worst_crps:.2e} bp, "
          f"largest probability gap {worst_probability:.2e}; development Brier reproduces: {brier_held}")
    return 0 if held else 2


if __name__ == "__main__":
    sys.exit(main())
