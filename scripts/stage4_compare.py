#!/usr/bin/env python3
"""Stage 4, the comparison (`docs/stages/stage-4.md`): the published gbm with and without the curve-implied spread.

    PYTHONPATH=src python3 scripts/stage4_compare.py

Builds panel version 3 from tracked fixtures (checked against its manifest) and adds the scheduled IORB in memory.
Model A is the parent's published gbm with nested conformal PID, built by the parent's own `compare` code. Model B is
the same fitter with the curve-implied spread added (`curve_feature.CurveFeatureFitter`, with the curve-pass remedy).
`baseline.paired_model_comparison` scores both on the parent's fold grid to 2025-12-31, CRPS at h = 1.

Must-show 1 is checked first: model A's scored origins and per-origin CRPS must equal the published record's model B
(the gbm) to 1e-9 bp. If they do not, the record carries the mismatch and no verdict, and the script exits 2.

Then: the verdict (the parent's `crps_verdict`, under evaluation.md's labels), the splits by regime and pressure-day
type (`baseline.add_comparison_splits`), as-of persistence against each arm (paired by day, from the published
record's persistence losses on the same origins), and the curve each refit used. Writes
`results/stage4/comparison.json`. Nothing is published.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

from repo_liquidity import curve_feature, parent_root

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage4" / "comparison.json"
MODEL_A = "gbm"
MODEL_B = "gbm_curve_implied_spread"
TOLERANCE_BP = 1e-9
#: evaluation.md's labels for the parent's `crps_verdict`.
LABELS = {"pass": "shown better", "not distinguishable": "not shown", "worse": "shown worse"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reproduction(per_origin, published):
    """Must-show 1: model A against the published gbm, origin by origin."""
    ours = [(entry["scored_date"], entry["loss_a_bps"]) for entry in per_origin]
    theirs = [(entry["scored_date"], entry["loss_b_bps"]) for entry in published]
    if [day for day, _ in ours] != [day for day, _ in theirs]:
        missing = sorted(set(day for day, _ in theirs) - set(day for day, _ in ours))
        extra = sorted(set(day for day, _ in ours) - set(day for day, _ in theirs))
        return {"held": False, "origins": len(ours), "published_origins": len(theirs),
                "missing": missing[:20], "extra": extra[:20]}
    gaps = [abs(a - b) for (_, a), (_, b) in zip(ours, theirs)]
    worst = max(range(len(gaps)), key=gaps.__getitem__)
    return {"held": gaps[worst] <= TOLERANCE_BP, "origins": len(ours), "tolerance_bp": TOLERANCE_BP,
            "largest_gap_bp": gaps[worst], "largest_gap_day": ours[worst][0]}


def beside_persistence(per_origin, published, seed_for):
    """As-of persistence against each arm, paired by day: persistence's loss minus the arm's (positive: arm better)."""
    from repo_model import baseline, metrics

    persistence = [entry["loss_a_bps"] for entry in published]
    out = {}
    for arm, key in (("model_a", "loss_a_bps"), ("model_b", "loss_b_bps")):
        differences = [p - entry[key] for p, entry in zip(persistence, per_origin)]
        seed = seed_for(arm)
        lower, upper = metrics.stationary_bootstrap_interval(
            lambda index: sum(differences[i] for i in index) / len(index), len(differences),
            block_length=2, seed=seed, replications=baseline.BOOTSTRAP_REPLICATIONS, level=baseline.BOOTSTRAP_LEVEL)
        mean = sum(differences) / len(differences)
        out[arm] = {"mean_difference_bps": mean, "interval": {"lower": lower, "upper": upper, "seed": seed,
                                                              "block_length": 2,
                                                              "replications": baseline.BOOTSTRAP_REPLICATIONS,
                                                              "level": baseline.BOOTSTRAP_LEVEL},
                    "sign_convention": "persistence's CRPS minus the arm's; positive means the arm was more accurate"}
    return out


def main():
    from repo_model import baseline, cli_eval
    from repo_model.evaluation_splits import load_split_declaration

    pass_module = _load("stage4_curve_pass", ROOT / "scripts" / "stage4_curve_pass.py")
    preregistration = _load("final_test_preregistration", parent_root() / "scripts" / "final_test_preregistration.py")
    published = json.loads((parent_root() / curve_feature.PUBLISHED_RECORD).read_text(encoding="utf-8"))
    rows, manifest = pass_module.load_rows()
    splits_path = parent_root() / "metadata" / "evaluation_splits.json"

    with tempfile.TemporaryDirectory() as tmp, curve_feature.stage4_declaration():
        panel_path = Path(tmp) / "phase3_panel_v3.csv"
        from repo_liquidity import panel

        panel.build(panel_path, version=curve_feature.PANEL_VERSION)
        registry_path = Path(tmp) / "registry.json"
        registry_path.write_text(json.dumps(curve_feature.registry(), sort_keys=True), encoding="utf-8")

        fit_a, online_a = curve_feature.published_arm()
        base_b, online_b = curve_feature.published_arm()
        fit_b = curve_feature.CurveFeatureFitter(base_b)
        seed = baseline.comparison_seed(manifest["sha256"], model_a=MODEL_A,
                                        features_a=curve_feature.PUBLISHED_FEATURES, model_b=MODEL_B,
                                        features_b=curve_feature.DECLARED_FEATURES,
                                        decision_time=curve_feature.DECISION_TIME)
        comparison = baseline.paired_model_comparison(
            rows, model_a=MODEL_A, fit_a=fit_a, features_a=curve_feature.PUBLISHED_FEATURES,
            model_b=MODEL_B, fit_b=fit_b, features_b=curve_feature.DECLARED_FEATURES,
            registry=curve_feature.registry(), decision_time=curve_feature.DECISION_TIME, seed=seed,
            minimum_history=curve_feature.MINIMUM_HISTORY, loss="crps", refit_every=curve_feature.REFIT_EVERY,
            end=curve_feature.LAST_DAY, online_calibration_a=online_a, online_calibration_b=online_b)
        document = baseline.paired_comparison_document(comparison, panel_path=panel_path,
                                                       registry_path=registry_path)
        cli_eval._declare_online_account(document, online_a, "calibration_account_a")
        cli_eval._declare_online_account(document, online_b, "calibration_account_b")

    per_origin = document["comparison"]["per_origin"]
    check = reproduction(per_origin, published["comparison"]["per_origin"])
    out = {
        "stage": "4, the comparison",
        "what": ("The parent's published gbm (nested conformal PID) with and without the curve-implied spread, paired "
                 "by day, CRPS at h = 1, development walk-forward to 2025-12-31 (docs/stages/stage-4.md)."),
        "sign_convention": document["comparison"]["sign_convention"],
        "must_show_1_reproduction": check,
        "curves": [{"cutoff": entry.cutoff.isoformat(), "kink": entry.curve.kink,
                    "intercept": round(entry.curve.intercept, 9), "slope": round(entry.curve.slope, 9),
                    "carried_from": None if entry.carried_from is None else entry.carried_from.isoformat()}
                   for entry in fit_b.curves],
        "provenance": pass_module.provenance(manifest),
    }
    if not check["held"]:
        out["verdict"] = None
        out["note"] = "Must-show 1 did not hold: model A is not the published gbm, so no verdict is reported."
        out["parent_document"] = document
        _write(out)
        print("must-show 1 failed:", check)
        return 2

    add = baseline.add_comparison_splits
    add(document, rows, load_split_declaration(splits_path))
    cell = {"mean_difference_bps": document["comparison"]["mean_difference_bps"],
            "interval": document["comparison"]["mean_difference_interval"]}
    label = preregistration.crps_verdict(cell)
    out["verdict"] = LABELS[label]
    out["verdict_rule"] = "evaluation.md: mean paired CRPS gain above 0 and its 90% stationary-bootstrap lower bound above 0"
    out["primary"] = {"mean_difference_bps": cell["mean_difference_bps"], "interval": cell["interval"],
                      "origins": len(per_origin), "crps_a_bps": document["comparison"]["model_a"]["crps_bps"],
                      "crps_b_bps": document["comparison"]["model_b"]["crps_bps"],
                      "splits": document["comparison"]["splits"]}

    def seed_for(arm):
        return baseline.comparison_seed(manifest["sha256"], model_a="persistence", features_a=("spread_bps",),
                                        model_b=MODEL_A if arm == "model_a" else MODEL_B,
                                        features_b=(curve_feature.PUBLISHED_FEATURES if arm == "model_a"
                                                    else curve_feature.DECLARED_FEATURES),
                                        decision_time=curve_feature.DECISION_TIME)

    out["beside_persistence"] = beside_persistence(per_origin, published["comparison"]["per_origin"], seed_for)
    out["parent_document"] = document
    _write(out)
    print(f"must-show 1 held ({check['origins']} origins, largest gap {check['largest_gap_bp']:.2e} bp); "
          f"verdict: {out['verdict']} (mean {cell['mean_difference_bps']:+.4f} bp, "
          f"90% [{cell['interval']['lower']:+.4f}, {cell['interval']['upper']:+.4f}])")
    return 0


def _write(document):
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(document, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
