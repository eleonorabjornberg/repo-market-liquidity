#!/usr/bin/env python3
"""Build the Phase 3 measurement panel and write its manifest.

    PYTHONPATH=src python3 scripts/build_panel.py [--version 2] [--output data/processed/phase3_panel.csv] [--check]

Builds from tracked fixtures alone (the parent's at the pin, and this repository's), with no network. Writes the
panel CSV (not tracked) and `metadata/phase3_panel_manifest.json` (tracked, generated, never edited by hand).
`--check` writes nothing and exits 1 if the build differs from the tracked manifest. `--version 2` builds the Stage 1a
correction's panel (`metadata/phase3_panel_v2_manifest.json`); version 1 is Stage 1a's. Nothing is scored.
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
    parser.add_argument("--version", type=int, choices=sorted(panel.MANIFESTS), default=1)
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
