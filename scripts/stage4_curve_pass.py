#!/usr/bin/env python3
"""Stage 4, the curve pass (`docs/stages/stage-4.md`): the curve alone, at every refit of the fold grid.

    PYTHONPATH=src python3 scripts/stage4_curve_pass.py

Builds panel version 3 from tracked fixtures and adds the scheduled IORB in memory. On the parent's fold grid (minimum
history 61, refit every 21, decision 16:00, to 2025-12-31), it takes each refit's training frame as the fold loop
would hand it over and fits the constrained curve on it (`curve_feature.fit_curve`). No gbm is fitted and no forecast
is scored. It writes `results/stage4/curve_pass.json`.

If any refit's curve fails, the record lists each failure with what a diagnosis needs: the training window, the days
on the scarce side, the reason, and the unconstrained Stage 2 fit on the same days. The run then stops for Eleonora's
remedy (the plan's "The curve pass"). Standard library only.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from repo_liquidity import PARENT_COMMIT, PANEL_SHA256, curve_feature, demand_curve, panel

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage4" / "curve_pass.json"


def provenance(manifest):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "metadata", "tests", "scripts"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"commit": commit, "tree_modified": bool(dirty), "parent_commit": PARENT_COMMIT,
            "parent_panel_sha256": PANEL_SHA256, "phase3_panel_version": curve_feature.PANEL_VERSION,
            "phase3_panel_sha256": manifest["sha256"]}


def load_rows():
    from repo_model.data import load_daily_panel

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "phase3_panel.csv"
        manifest = panel.build(path, version=curve_feature.PANEL_VERSION)
        recorded = panel.load_manifest(version=curve_feature.PANEL_VERSION)
        if manifest["sha256"] != recorded["sha256"]:
            raise ValueError(f"panel version {curve_feature.PANEL_VERSION} rebuilt to {manifest['sha256']}, "
                             f"not its manifest's {recorded['sha256']}")
        rows = curve_feature.with_stage4_columns(load_daily_panel(path))
    return rows, manifest


def refit_frames(rows):
    """Each refit's training frame, as `baseline._as_of_folds` hands it to the fitter, under model B's declaration."""
    from repo_model.asof import InformationRule, fold_grid, refit_blocks

    rule = InformationRule(curve_feature.registry(), curve_feature.DECLARED_FEATURES,
                           decision_time=curve_feature.DECISION_TIME)
    dates = [row.date for row in rows]
    grid = fold_grid(dates, rule.registry, decision_time=rule.decision_time,
                     minimum_history=curve_feature.MINIMUM_HISTORY, horizon=rule.horizon)
    grid = [index for index in grid if dates[index] <= curve_feature.LAST_DAY]
    for block in refit_blocks(grid, curve_feature.REFIT_EVERY):
        info = rule.information_set(dates, block[0])
        rule.check(dates, info)
        yield dates[block[0]], rule.frame(rows, info)


def main():
    rows, manifest = load_rows()
    refits, failures = [], []
    with curve_feature.stage4_declaration():
        rule = curve_feature.curve_rule()
        for first_scored, frame in refit_frames(rows):
            cutoff = frame[-1].date
            xs, ys, days = curve_feature.curve_sample(frame, rule, cutoff=cutoff)
            entry = {"first_scored": first_scored.isoformat(), "train_start": frame[0].date.isoformat(),
                     "cutoff": cutoff.isoformat(), "train_rows": len(frame), "curve_days": len(xs),
                     "scarce_days": sum(x < demand_curve.SCARCE_BELOW for x in xs),
                     "ratio_range": [round(min(xs), 6), round(max(xs), 6)] if xs else None}
            try:
                curve = curve_feature.fit_constrained(xs, ys)
            except curve_feature.CurveFailure as failure:
                entry["failed"] = str(failure)
                try:
                    free = demand_curve.fit_broken_stick(xs, ys)
                    entry["unconstrained"] = {"kink": free.kink, "intercept": round(free.intercept, 9),
                                              "slope": round(free.slope, 9)}
                except ValueError as error:
                    entry["unconstrained"] = {"failed": str(error)}
                failures.append(entry)
            else:
                entry.update({"kink": curve.kink, "intercept": round(curve.intercept, 9),
                              "slope": round(curve.slope, 9)})
            refits.append(entry)
    document = {
        "stage": "4, the curve pass",
        "what": ("The constrained curve (slope at or above 0) fitted alone at every refit of the parent's fold grid, "
                 "on the training frame the fold loop hands the fitter. No gbm is fitted and nothing is scored."),
        "settings": {"minimum_history": curve_feature.MINIMUM_HISTORY, "refit_every": curve_feature.REFIT_EVERY,
                     "decision_time": curve_feature.DECISION_TIME.isoformat(timespec="minutes"),
                     "end": curve_feature.LAST_DAY.isoformat(), "grid": [demand_curve.GRID[0], demand_curve.GRID[-1],
                                                                         len(demand_curve.GRID)],
                     "scarce_below": demand_curve.SCARCE_BELOW},
        "verdict": "goes ahead" if not failures else "stops: a refit's curve failed",
        "failures": len(failures),
        "refits": refits,
        "provenance": provenance(manifest),
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(f"{len(refits)} refits, {len(failures)} failed: {document['verdict']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
