#!/usr/bin/env python3
"""Build the Phase 3 measurement panel and write its manifest.

    PYTHONPATH=src python3 scripts/build_panel.py [--version 5] [--output data/processed/phase3_panel.csv] [--check]

Builds from tracked fixtures alone (the parent's at the pin, and this repository's), with no network. Writes the
panel CSV (not tracked) and the version's manifest under `metadata/` (tracked, generated, never edited by hand).
`--check` writes nothing and exits 1 if the build differs from the tracked manifest. Version 5, the default, is
Stage 1a's panel built at the current pin (`metadata/phase3_panel_v5_manifest.json`); versions 1 to 4 are records that
`panel.build` refuses (`scripts/verify_records.py` checks them at their own pin). Nothing is scored.
"""

import argparse
import json
import sys
from pathlib import Path

from repo_liquidity import panel

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/phase3_panel.csv")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--version", type=int, choices=sorted(panel.MANIFESTS), default=panel.CURRENT_VERSION)
    args = parser.parse_args(argv)
    manifest = panel.build(args.output, version=args.version)
    if args.check:
        if manifest != panel.load_manifest(args.version):
            print(f"the build differs from {panel.MANIFESTS[args.version].name}", file=sys.stderr)
            return 1
        print(f"matches the tracked manifest, sha256 {manifest['sha256']}")
        return 0
    panel.write_manifest(manifest, args.version)
    print(json.dumps({k: manifest[k] for k in ("sha256", "start_date", "end_date", "refusals")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
