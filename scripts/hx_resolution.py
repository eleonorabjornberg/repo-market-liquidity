"""HX step 2 (#210): write the resolution fact of SOFR's interquartile width over development (`docs/research/hx-resolution.json`).

Descriptive only: how many distinct values the width takes, over every development day and over the calendar-clean days W1
fits on. Nothing is fitted or scored, and no day after 2026-09-03 is read.

Usage: python3 scripts/hx_resolution.py [--check]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUTPUT = ROOT / "docs" / "research" / "hx-resolution.json"


def main() -> int:
    from repo_model.data import load_daily_panel

    from repo_liquidity import dispersion_estimator, panel

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed file differs")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "phase3_panel.csv"
        panel.build(path, version=panel.CURRENT_VERSION)
        record = dispersion_estimator.resolution_record(load_daily_panel(path))
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.check:
        return 0 if OUTPUT.read_text(encoding="utf-8") == text else 1
    OUTPUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
