#!/usr/bin/env python3
"""H10 step 3 (#77): write or check the published development table.

    PYTHONPATH=src python3 scripts/emit_h10_table.py           # rewrites docs/research/h10-development-table.md
    PYTHONPATH=src python3 scripts/emit_h10_table.py --check   # exits 1 if the page is not what the records render to

The page is rendered from `results/h10/development.json` and `results/h10/sensitivity_onrrp_interaction.json` and is never
hand-edited. Nothing is re-fitted or re-run.
"""

import argparse
import sys

from repo_liquidity import h10_publish


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare the tracked page with the rendering; write nothing")
    args = parser.parse_args()
    text = h10_publish.render_tracked()
    if args.check:
        current = h10_publish.PAGE.read_text(encoding="utf-8") if h10_publish.PAGE.is_file() else None
        if current != text:
            print(f"{h10_publish.PAGE} is stale: run scripts/emit_h10_table.py", file=sys.stderr)
            return 1
        print("h10 table: ok")
        return 0
    h10_publish.PAGE.write_text(text, encoding="utf-8")
    print(f"wrote {h10_publish.PAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
