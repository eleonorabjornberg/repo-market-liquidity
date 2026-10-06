#!/usr/bin/env python3
"""Stage 2: describe the reserve demand curve and test whether its bend is stable enough to model.

    PYTHONPATH=src python3 scripts/stage2_demand_curve.py [--check]

Builds the Phase 3 panel from tracked fixtures (`scripts/build_panel.py`), reads each day's reserves ratio as of
its decision instant, and writes `results/stage2/demand_curve.json`: the binned curve, the broken-stick bend with its
90% interval pooled and per regime, the reported splits (ON RRP buffer present or gone, the 2021 and 2023 reform
dates), the same fit on the 75th percentile, and the verdict under `docs/decisions/stage-2-bend.md`. Nothing is
forecast, scored or published (`docs/decisions/publish-rule.md`). `--check` recomputes and compares.
"""

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from repo_liquidity import demand_curve as dc
from repo_liquidity import panel, parent_root

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage2" / "demand_curve.json"
#: Reform dates in 2021 and 2023 (`docs/decisions/reform-dates.md`), used as reported split points.
REFORM_BREAKS = (date(2021, 3, 31), date(2021, 7, 29), date(2023, 3, 12), date(2023, 7, 12), date(2023, 12, 13))
ON_RRP_BUFFER_BN = 100.0


def compute():
    from repo_model.data import load_daily_panel
    from repo_model.evaluation_splits import load_split_declaration

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "phase3_panel.csv"
        manifest = panel.build(path)
        days = dc.sample(load_daily_panel(path))
    splits = load_split_declaration(parent_root() / "metadata" / "evaluation_splits.json")

    regimes = {}
    for label in splits.regime_labels:
        group = [d for d in days if splits.regime(d.day) == label]
        if group:
            regimes[label] = dc.describe(group, f"regime {label}")
    eligible = {label: tuple(entry["kink_interval_90"]) for label, entry in regimes.items()
                if entry["scarce_days"] >= dc.MIN_SCARCE_DAYS and entry.get("fit")}
    pooled = dc.describe(days, "pooled")
    verdict = dc.stability_verdict(pooled=tuple(pooled["kink_interval_90"]), regimes=eligible)

    buffer = {
        "on_rrp_at_or_above_100bn": dc.describe([d for d in days if d.on_rrp_bn is not None
                                                 and d.on_rrp_bn >= ON_RRP_BUFFER_BN], "on_rrp >= 100bn"),
        "on_rrp_below_100bn": dc.describe([d for d in days if d.on_rrp_bn is not None
                                           and d.on_rrp_bn < ON_RRP_BUFFER_BN], "on_rrp < 100bn"),
    }
    edges = [days[0].day] + list(REFORM_BREAKS) + [date(2026, 1, 1)]
    reforms = {}
    for start, end in zip(edges, edges[1:]):
        group = [d for d in days if start <= d.day < end]
        if group:
            reforms[f"{start.isoformat()} to {end.isoformat()}"] = dc.describe(group, f"reform {start}")
    tail_days = [d for d in days if d.p75_spread_bp is not None]
    tail = dc.describe([dc.Day(d.day, d.ratio, d.p75_spread_bp, None, d.on_rrp_bn) for d in tail_days],
                       "p75 pooled")

    return {
        "stage": "2",
        "what": "Descriptive. The spread SOFR - IORB (bp) on day T against reserves / bank assets known at T's "
                "decision instant; broken stick spread = a + b * max(k - ratio, 0). Nothing is forecast or scored.",
        "decided_rule": "docs/decisions/stage-2-bend.md",
        "settings": {
            "window": [days[0].day.isoformat(), days[-1].day.isoformat()],
            "scarce_below": dc.SCARCE_BELOW, "min_scarce_days": dc.MIN_SCARCE_DAYS,
            "sharp_width": dc.SHARP_WIDTH, "block_length": dc.BLOCK_LENGTH,
            "replications": dc.REPLICATIONS, "level": dc.LEVEL,
            "grid": [dc.GRID[0], dc.GRID[-1], 0.0005], "decision_time": dc.DECISION_TIME.isoformat(),
        },
        "provenance": {
            "panel_sha256": manifest["sha256"], "parent_commit": manifest["parent_commit"],
            "parent_panel_sha256": manifest["parent_panel_sha256"], "splits_sha256": splits.sha256,
        },
        "days": len(days),
        "pooled": pooled,
        "binned_curve": dc.binned_curve(days),
        "regimes": regimes,
        "verdict": verdict,
        "reported_only": {"on_rrp_buffer": buffer, "reform_periods": reforms, "p75_spread": tail},
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    record = compute()
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.check:
        if RECORD.read_text(encoding="utf-8") != text:
            print("the recomputed record differs from results/stage2/demand_curve.json", file=sys.stderr)
            return 1
        print("matches results/stage2/demand_curve.json")
        return 0
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(text, encoding="utf-8")
    print(json.dumps(record["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
