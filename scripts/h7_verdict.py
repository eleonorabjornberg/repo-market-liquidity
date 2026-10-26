#!/usr/bin/env python3
"""H7m stage verdict (directive #187): writes `results/h7/verdict.json` and `docs/stages/h7m-verdict.md` from the tracked records.

    python3 -B scripts/h7_verdict.py            write both
    python3 -B scripts/h7_verdict.py --check    exit 1 if either is not what the records give

Reads the tracked records only; fits and scores nothing, and needs no parent.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_liquidity import h7_verdict as v  # noqa: E402

RECORD = ROOT / "results" / "h7" / "verdict.json"
PAGE = ROOT / "docs" / "stages" / "h7m-verdict.md"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    record = v.build(ROOT)
    problems = v.check_figures(record, v.load_records(ROOT)) + [f"untyped number at {p}" for p in v.untyped_numbers(record)]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    page = v.markdown(record)
    if args.check:
        stale = [p.name for p, t in ((RECORD, text), (PAGE, page)) if not p.is_file() or p.read_text(encoding="utf-8") != t]
        if stale:
            print("stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("ok")
        return 0
    RECORD.write_text(text, encoding="utf-8")
    PAGE.write_text(page, encoding="utf-8")
    print(f"wrote {RECORD.relative_to(ROOT)} and {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
