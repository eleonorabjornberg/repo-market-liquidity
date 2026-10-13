#!/usr/bin/env python3
"""Cut the declared H.8 breaks out of the saved "Notes on Data" page (#26; data-meaning answer 17(c)).

    # fetch once (needs network access to federalreserve.gov), then cut:
    curl -sS -o h8notes.htm https://www.federalreserve.gov/releases/h8/h8notes.htm
    PYTHONPATH=src python3 scripts/extract_h8_breaks.py --page h8notes.htm --retrieved-at 2026-10-13T16:00:00Z
    PYTHONPATH=src python3 scripts/extract_h8_breaks.py --check

The page is saved gzipped under `tests/fixtures/h8_notes/` (its SHA-256 is of the unzipped bytes). Every note from the
extract's first week to 2026-09-03 becomes one dated event in `docs/research/h8-group-breaks.json`, with its text verbatim.
`--check` re-cuts from the saved page and compares with the tracked record, writing nothing.
"""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

from repo_liquidity import h8

#: What the notes archive does not carry, so what this record does not declare (answer 17(c) names them).
NOT_IN_THE_NOTES = (
    "The reassessment of the large-bank panel (the top 25 by domestic assets) at each benchmark, and the replacement of "
    "a bank on a merger or a departure: the notes archive lists no such event, so no date is declared for them. Where "
    "large and small levels were restated, the first-print extract differs from later vintages "
    "(docs/research/h8-groups-due-diligence.md, revisions).",
    "The 2023 failures and acquisitions (Silicon Valley Bank, Signature Bank, First Republic): the notes of 22 and 29 "
    "March 2023 record domestically chartered banks divesting $87 billion in assets to nonbank institutions in each week, "
    "which is declared as stated, but no note names a bank or a group, and none is dated for First Republic.",
)


def build(page: bytes, retrieved_at: str) -> dict:
    return {
        "source": {"url": h8.NOTES_URL, "retrieved_at": retrieved_at, "sha256": hashlib.sha256(page).hexdigest(),
                   "saved_as": str(h8.NOTES_PAGE.relative_to(h8.NOTES_PAGE.parents[3]))},
        "first_as_of": h8.FIRST_WEEK.isoformat(),
        "last_as_of": h8.LAST_RELEASE.isoformat(),
        "events": h8.parse_notes(page),
        "not_in_the_notes": list(NOT_IN_THE_NOTES),
    }


def encode(record: dict) -> bytes:
    return (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--page", type=Path)
    parser.add_argument("--retrieved-at")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        page = gzip.decompress(h8.NOTES_PAGE.read_bytes())
        tracked = json.loads(h8.BREAKS_PATH.read_text(encoding="utf-8"))
        rebuilt = build(page, tracked["source"]["retrieved_at"])
        stale = rebuilt != tracked
        print("stale" if stale else "the breaks record is the saved page's notes")
        return 1 if stale else 0
    if args.page is None or args.retrieved_at is None:
        parser.error("--page and --retrieved-at are required unless --check")
    page = args.page.read_bytes()
    record = build(page, args.retrieved_at)
    h8.NOTES_PAGE.parent.mkdir(parents=True, exist_ok=True)
    h8.NOTES_PAGE.write_bytes(gzip.compress(page, mtime=0))
    h8.BREAKS_PATH.write_bytes(encode(record))
    print(f"{len(record['events'])} events, page sha256 {record['source']['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
