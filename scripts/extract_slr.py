#!/usr/bin/env python3
"""Cut the SLR-headroom extract from the stored CDR bulk zips (#63; `repo_liquidity.slr`).

    PYTHONPATH=src python3 scripts/extract_slr.py --zips DIR --manifest cdr_manifest.json [--check]

`--zips` holds the quarter files `scripts/archive_cdr.py` stores (`<quarter-end>-<sha256>.zip`, never overwritten) and
`--manifest` is the archive manifest it wrote, so each zip's retrieval time is the one recorded when it was fetched. The
zips are not tracked. Written, from the 34 quarter-ends 2018-03-31 to 2026-06-30:

- `tests/fixtures/snapshots/slr_headroom/slr_latest_filed.csv` and its `.manifest.json`: one row per bank and quarter;
- `slr_latest_filed.sources.json`: each zip's name, SHA-256, size, "as of" stamp and retrieval time;
- `slr_latest_filed.coverage.json`: every hole and refusal, by filer and quarter, with its reason;
- `docs/research/slr-headroom-coverage.md`: the same, in words (generated, never hand-edited).

Nothing is read past the parent's development end: a figure last updated on a locked day is withheld and listed. The
declared lag in `declarations/ffiec_call_slr.json` must be the measured worst case. `--check` rebuilds in memory and
compares. Nothing is scored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from repo_model.ingest import SnapshotArtifact

from repo_liquidity import declaration, development, slr

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/snapshots/slr_headroom"
COVERAGE_MD = ROOT / "docs/research/slr-headroom-coverage.md"
URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
FIRST_QUARTER, LAST_QUARTER = date(2018, 3, 31), date(2026, 6, 30)


def _json(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def cut(zips: Path, archive_manifest: Path):
    manifest = json.loads(archive_manifest.read_text(encoding="utf-8"))
    entries = {}
    for entry in manifest["entries"]:
        quarter = date.fromisoformat(entry["quarter"])
        if FIRST_QUARTER <= quarter <= LAST_QUARTER:
            if quarter in entries:
                raise ValueError(f"the archive manifest holds two files for {quarter}; name the one to read")
            entries[quarter] = entry
    quarters = sorted(entries)
    expected = 1 + (LAST_QUARTER.year - FIRST_QUARTER.year) * 4 + (LAST_QUARTER.month - FIRST_QUARTER.month) // 3
    if len(quarters) != expected:
        raise ValueError(f"the archive manifest holds {len(quarters)} quarters in range, not {expected}")
    kept, holes, sources = [], [], []
    for quarter in quarters:
        entry = entries[quarter]
        path = zips / entry["file"]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"] or slr.quarter_end_of(path.name) != quarter:
            raise ValueError(f"{path.name} is not the bytes its name and the manifest say")
        rows, found, as_of = slr.parse_quarter(payload, quarter)
        rows, locked = slr.withhold_locked(rows)
        kept += rows
        holes += found + locked
        sources.append({"quarter_end": quarter.isoformat(), "file": entry["file"], "download_name": entry["download_name"],
                        "sha256": entry["sha256"], "size": entry["size"], "as_of": as_of,
                        "retrieved_utc": entry["first_retrieved_utc"]})
    holes += slr.notes(kept)
    extract = slr.write_extract(kept)
    declared = int(declaration.overlay()[slr.SOURCE_ID]["release_lag"]["days"]) if slr.SOURCE_ID in declaration.overlay() else None
    worst = slr.worst_case_lag_days(kept)
    if declared != worst:
        raise ValueError(f"declarations/ffiec_call_slr.json declares {declared} days; the measured worst case is {worst}")
    record = slr.coverage(kept, holes, quarters)
    artifact = SnapshotArtifact(
        source_id=slr.SOURCE_ID, path=Path(slr.SOURCE_ID) / slr.EXTRACT_NAME,
        retrieved_at=max(item["retrieved_utc"] for item in sources), sha256=hashlib.sha256(extract).hexdigest(),
        url=URL, byte_count=len(extract)).as_dict()
    sources_record = {"product": "Call Reports -- Single Period", "format": "Tab Delimited", "url": URL,
                      "vintage": slr.VINTAGE, "development_end": development.development_end().isoformat(),
                      "zips": sources}
    files = {
        slr.EXTRACT_NAME: extract,
        slr.EXTRACT_NAME + ".manifest.json": _json(artifact),
        slr.SOURCES_NAME: _json(sources_record),
        slr.COVERAGE_NAME: _json(record),
    }
    summary = {"quarters": len(quarters), "rows": len(kept), "worst_case_lag_days": worst, "reasons": record["reasons"]}
    return files, summary, render_markdown(kept, record, sources_record)


def render_markdown(rows, record, sources) -> str:
    by_bank = {}
    for row in rows:
        by_bank.setdefault(row.idrssd, []).append(row)
    lines = [
        "# SLR headroom: coverage of the latest-filed extract (generated)",
        "",
        "**Generated by `scripts/extract_slr.py`; never hand-edited.** Hypothesis and step: H7m, groundwork G5 (candidate D),",
        "#63. Inputs built, nothing scored. The figures are the *latest-filed* ones, labelled `vintage = latest_filed`",
        "(`docs/decisions/data-meaning.md` row 16, amended 13 October 2026), each available from the day after its",
        "latest-update date and never earlier. They are not first prints.",
        "",
        f"- Quarters: {record['quarters'][0]} to {record['quarters'][-1]} ({len(record['quarters'])}).",
        f"- Nine G-SIB depository subsidiaries: {record['bank_quarters']} bank-quarters, {record['rows']} rows in the extract.",
        f"- Nothing past the parent's development end ({sources['development_end']}): a figure last updated on a later day",
        "  is withheld.",
        "",
        "## Holes and refusals, by reason",
        "",
        "| reason | count | row kept |",
        "|---|---|---|",
    ]
    kept_by_reason = {h["reason"]: h["row_kept"] for h in record["holes"]}
    for reason, count in record["reasons"].items():
        lines.append(f"| `{reason}` | {count} | {'yes' if kept_by_reason[reason] else 'no'} |")
    lines += ["", "## Every hole and refusal (filer, quarter, why)", "", "| quarter-end | filer | reason | kept | detail |",
              "|---|---|---|---|---|"]
    for h in record["holes"]:
        lines.append(f"| {h['quarter_end']} | {h['institution']} ({h['idrssd']}) | `{h['reason']}` | "
                     f"{'yes' if h['row_kept'] else 'no'} | {h['detail']} |")
    lines += ["", "## The filed ratio, by bank (computed, in percent; no aggregate)", "",
              "| filer | quarters | min | max | latest quarter |", "|---|---|---|---|---|"]
    for idrssd, items in by_bank.items():
        ratios = [r.slr_pct for r in items]
        last = max(items, key=lambda r: r.quarter_end)
        lines.append(f"| {slr.BANKS[idrssd]} ({idrssd}) | {len(items)} | {min(ratios):.2f} | {max(ratios):.2f} | "
                     f"{last.quarter_end} ({last.slr_pct:.2f}) |")
    lines += ["", "## Not checked", "",
              "- The item numbers against the current FFIEC 031 instructions (row 16(a)).",
              "- The posting lag between a submission and its public availability (not recorded); the whole day after the",
              "  update is skipped instead.",
              "- The time zone of the update stamps (none is given); read as New York time, covered by the same skipped day.",
              "- Each subsidiary's 2020-21 election status: the item descriptions in the bulk files are cut to about 40",
              "  characters and none names an election, so every row in the window is flagged `exclusion_status_unknown`.",
              "- Which requirement applies from 2026-04-01: row 16 does not set it, so those rows carry no headroom.",
              "- Whether every IDRSSD in `slr.BANKS` is the bank meant. Only State Street's was checked, after it proved wrong:",
              "  93619 (a trust subsidiary of about $65 million) was replaced by 35301, the bank, on 15 October 2026.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--zips", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--markdown", type=Path, default=COVERAGE_MD)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files, summary, markdown = cut(args.zips, args.manifest)
    if args.check:
        stale = [name for name, payload in files.items()
                 if not (args.output / name).is_file() or (args.output / name).read_bytes() != payload]
        if not args.markdown.is_file() or args.markdown.read_text(encoding="utf-8") != markdown:
            stale.append(str(args.markdown))
        print(json.dumps({**summary, "stale": stale}, indent=2))
        return 1 if stale else 0
    args.output.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (args.output / name).write_bytes(payload)
    args.markdown.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
