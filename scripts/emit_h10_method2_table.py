#!/usr/bin/env python3
"""H10's second declaration, step 2 (#209): write or check the development page.

    PYTHONPATH=src python3 scripts/emit_h10_method2_table.py           # rewrites docs/research/h10-method2-development-table.md
    PYTHONPATH=src python3 scripts/emit_h10_method2_table.py --check   # exits 1 if the page is not what the records render to

The page is rendered from `results/h10/development_2.json` and the registered `results/h10/development.json`, which it shows
unchanged, and is never hand-edited. Nothing is re-fitted. Until the Mac run has come back there is no record, and no page.
"""

import argparse
import sys

from repo_liquidity import h10_apply_2 as h2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare the tracked page with the rendering; write nothing")
    args = parser.parse_args()
    if not h2.RECORD.is_file():
        if args.check:
            print("h10 method 2 table: no record yet (the Mac run has not come back)")
            return 0
        print(f"{h2.RECORD} does not exist: run scripts/h10_method2_step2.py assemble first", file=sys.stderr)
        return 2
    text = h2.render_tracked()
    if args.check:
        current = h2.PAGE.read_text(encoding="utf-8") if h2.PAGE.is_file() else None
        if current != text:
            print(f"{h2.PAGE} is stale: run scripts/emit_h10_method2_table.py", file=sys.stderr)
            return 1
        print("h10 method 2 table: ok")
        return 0
    h2.PAGE.write_text(text, encoding="utf-8")
    print(f"wrote {h2.PAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
