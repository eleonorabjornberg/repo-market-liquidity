#!/usr/bin/env python3
"""Stage 4, the secondary result (`docs/stages/stage-4.md`): the pressure-probability Brier score with and without the feature.

    PYTHONPATH=src python3 scripts/stage4_brier.py

Model A is the parent's published exceedance predictor (the gbm with nested conformal PID), built by the parent's own
`exceedance-backtest` code from the command its published record declares. Model B is the same predictor with the
curve-implied spread (`curve_feature.CurveFeatureExceedance`, with the curve-pass remedy). Both are scored by
`baseline.rolling_exceedance_backtest` on the parent's fold grid to 2025-12-31, with the two pressure-probability
benchmarks (calendar climatology, the persistence-logistic model) beside them.

Model A is first checked against the published exceedance record: the same scored days, and the same Brier at every
declared threshold, to 1e-12. The secondary result is P(spread > +5 bp) at h = 1; the other declared thresholds are
reported beside it. Paired day by day by the parent's `benchmark_comparison_document`. Not part of the pass rule.
Writes `results/stage4/brier.json`. Nothing is published.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

from repo_liquidity import curve_feature, panel, parent_root

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage4" / "brier.json"
TOLERANCE = 1e-12
SECONDARY_TAU = "5"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _brier_by_tau(report):
    out = {}
    for position, tau in enumerate(report.taus):
        predicted, _, realized = report.at_tau(position)
        out[f"{tau:g}"] = sum((p - o) ** 2 for p, o in zip(predicted, realized)) / len(realized)
    return out


def main():
    from repo_model import baseline
    from repo_model.data import load_stress_thresholds
    from repo_model.evaluation_splits import load_split_declaration
    from repo_model.onset import LEAP_JUMP_BP

    pass_module = _load("stage4_curve_pass", ROOT / "scripts" / "stage4_curve_pass.py")
    published = json.loads((parent_root() / curve_feature.PUBLISHED_EXCEEDANCE_RECORD).read_text(encoding="utf-8"))
    rows, manifest = pass_module.load_rows()
    taus = tuple(float(tau) for tau in
                 load_stress_thresholds(parent_root() / "metadata" / "stress_thresholds.json")["taus_bp"])
    splits = load_split_declaration(parent_root() / "metadata" / "evaluation_splits.json")

    with tempfile.TemporaryDirectory() as tmp, curve_feature.stage4_declaration():
        panel_path = Path(tmp) / "phase3_panel_v3.csv"
        panel.build(panel_path, version=curve_feature.PANEL_VERSION)
        digest = baseline.panel_sha256(panel_path)

        def run(predictor, name, features, online=None, leap=True):
            return baseline.rolling_exceedance_backtest(
                rows, predictor=predictor, model_name=name, features=features, registry=curve_feature.registry(),
                decision_time=curve_feature.DECISION_TIME, taus=taus, minimum_history=curve_feature.MINIMUM_HISTORY,
                refit_every=curve_feature.REFIT_EVERY, end=curve_feature.LAST_DAY,
                leap_jump_bp=LEAP_JUMP_BP[1] if leap else None, online_calibration=online)

        name_a, predictor_a, online_a, benchmarks = curve_feature.published_exceedance_arm()
        name_b, predictor_b, online_b, _ = curve_feature.published_exceedance_arm(with_feature=True)
        report_a = run(predictor_a, name_a, curve_feature.PUBLISHED_FEATURES, online_a)
        report_b = run(predictor_b, name_b, curve_feature.DECLARED_FEATURES, online_b)
        bench_reports = [(bench_name, run(bench, bench_name, features, leap=False))
                         for bench_name, features, bench in benchmarks]

        ours = _brier_by_tau(report_a)
        theirs = {key: entry["brier"] for key, entry in published["metrics"]["by_tau"].items()}
        gaps = {key: abs(ours[key] - theirs[key]) for key in theirs}
        check = {"held": (len(report_a.scored_dates) == published["metrics"]["scored_days"]
                          and set(ours) == set(theirs) and max(gaps.values()) <= TOLERANCE),
                 "scored_days": len(report_a.scored_dates), "published_scored_days": published["metrics"]["scored_days"],
                 "largest_gap": max(gaps.values()), "tolerance": TOLERANCE}

        with_without = baseline.benchmark_comparison_document(report_b, report_a, panel_sha256=digest, rows=rows,
                                                              declaration=splits)
        against = {bench_name: {"model_a": baseline.benchmark_comparison_document(report_a, bench, panel_sha256=digest,
                                                                                 rows=rows, declaration=splits),
                                "model_b": baseline.benchmark_comparison_document(report_b, bench, panel_sha256=digest,
                                                                                 rows=rows, declaration=splits)}
                   for bench_name, bench in bench_reports}

    out = {
        "stage": "4, the secondary result",
        "what": ("The pressure probability P(spread > tau) at h = 1, Brier, the published exceedance predictor with and "
                 "without the curve-implied spread, against calendar climatology and the persistence-logistic model. "
                 "The secondary result is tau = +5 bp; it is not part of the pass rule."),
        "model_a_reproduces_published": check,
        "with_without": with_without,
        "benchmarks": against,
        "curves": [{"cutoff": entry.cutoff.isoformat(), "kink": entry.curve.kink,
                    "carried_from": None if entry.carried_from is None else entry.carried_from.isoformat()}
                   for entry in predictor_b.curves],
        "provenance": pass_module.provenance(manifest),
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    five = with_without["by_tau"][SECONDARY_TAU]
    paired = five["paired_brier_difference"]
    print(f"model A reproduces: {check['held']} (largest gap {check['largest_gap']:.1e}); +5 bp Brier A "
          f"{five['benchmark_brier']:.6f}, B {five['model_brier']:.6f}, A minus B {paired['mean']:+.6f} "
          f"[{paired['interval']['lower']:+.6f}, {paired['interval']['upper']:+.6f}]")
    return 0 if check["held"] else 2


if __name__ == "__main__":
    sys.exit(main())
