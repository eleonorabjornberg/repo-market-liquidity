#!/usr/bin/env python3
"""Cut the RC-A anchor extract from the stored CDR bulk zips (#43; `repo_liquidity.rca`).

    PYTHONPATH=src python3 scripts/extract_rca.py --zips DIR --manifest cdr_manifest.json [--check]

`--zips` holds the quarter files `scripts/archive_cdr.py` stores (`<quarter-end>-<sha256>.zip`, never overwritten) and
`--manifest` is the archive manifest it wrote, so each zip's retrieval time is the one recorded when it was fetched. The
zips are not tracked. Written, from the 34 quarter-ends 2018-03-31 to 2026-06-30:

- `tests/fixtures/snapshots/rca_anchor/rca_latest_filed.csv` and its `.manifest.json`: one row per group and quarter;
- `rca_latest_filed.sources.json`: each zip's name, SHA-256, size, "as of" stamp and retrieval time;
- `rca_latest_filed.coverage.json`: every hole and withholding, by group and quarter, with its reason, and the lag profile;
- `docs/research/rca-anchor-coverage.md`: the same, in words (generated, never hand-edited).

Nothing is read past the parent's development end: a group with a member last updated on a locked day is withheld and
listed. The declared lag in `declarations/ffiec_call_rca.json` must be the measured worst case. `--check` rebuilds in
memory and compares. Nothing is scored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from repo_model.ingest import SnapshotArtifact

from repo_liquidity import declaration, development, rca

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/snapshots/rca_anchor"
COVERAGE_MD = ROOT / "docs/research/rca-anchor-coverage.md"
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
    kept, holes, sources, profile = [], [], [], {}
    for quarter in quarters:
        entry = entries[quarter]
        path = zips / entry["file"]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"] or rca.quarter_end_of(path.name) != quarter:
            raise ValueError(f"{path.name} is not the bytes its name and the manifest say")
        rows, found, as_of, quarter_profile = rca.parse_quarter(payload, quarter)
        profile[quarter.isoformat()] = quarter_profile
        rows, locked = rca.withhold_locked(rows)
        kept += rows
        holes += found + locked
        sources.append({"quarter_end": quarter.isoformat(), "file": entry["file"], "download_name": entry["download_name"],
                        "sha256": entry["sha256"], "size": entry["size"], "as_of": as_of,
                        "retrieved_utc": entry["first_retrieved_utc"]})
    extract = rca.write_extract(kept)
    declared = int(declaration.overlay()[rca.SOURCE_ID]["release_lag"]["days"]) if rca.SOURCE_ID in declaration.overlay() else None
    worst = rca.worst_case_lag_days(kept)
    if declared != worst:
        raise ValueError(f"declarations/ffiec_call_rca.json declares {declared} days; the measured worst case is {worst}")
    record = rca.coverage(kept, holes, quarters, profile)
    artifact = SnapshotArtifact(
        source_id=rca.SOURCE_ID, path=Path(rca.SOURCE_ID) / rca.EXTRACT_NAME,
        retrieved_at=max(item["retrieved_utc"] for item in sources), sha256=hashlib.sha256(extract).hexdigest(),
        url=URL, byte_count=len(extract)).as_dict()
    sources_record = {"product": "Call Reports -- Single Period", "format": "Tab Delimited", "url": URL,
                      "vintage": rca.VINTAGE, "development_end": development.development_end().isoformat(),
                      "zips": sources}
    files = {
        rca.EXTRACT_NAME: extract,
        rca.EXTRACT_NAME + ".manifest.json": _json(artifact),
        rca.SOURCES_NAME: _json(sources_record),
        rca.COVERAGE_NAME: _json(record),
    }
    summary = {"quarters": len(quarters), "rows": len(kept), "worst_case_lag_days": worst, "reasons": record["reasons"]}
    return files, summary, render_markdown(kept, record, sources_record)


def render_markdown(rows, record, sources) -> str:
    by_group = {}
    for row in rows:
        by_group.setdefault(row.group, []).append(row)
    lines = [
        "# RC-A anchor: coverage of the latest-filed extract (generated)",
        "",
        "**Generated by `scripts/extract_rca.py`; never hand-edited.** Hypothesis and step: H7m, groundwork G4 (candidate C),",
        "#43. Inputs built, nothing scored. The figures are the *latest-filed* ones, labelled `vintage = latest_filed`",
        "(`docs/decisions/data-meaning.md` row 16, amended 13 October 2026). A group's figure is a sum over its members, so it",
        "is available from the day after its **slowest member's** latest update and never earlier. They are not first prints.",
        "",
        f"- Quarters: {record['quarters'][0]} to {record['quarters'][-1]} ({len(record['quarters'])}).",
        f"- Two domestic groups: the 25 largest filers by total assets (a labelled stand-in for the Board's panel) and every",
        f"  other filer that carries item 0090. {record['rows']} of {record['group_quarters']} group-quarters are in the extract.",
        f"- Nothing past the parent's development end ({sources['development_end']}): a group with a member last updated on a",
        "  later day is withheld whole.",
        "",
        "## Holes and withholdings, by reason",
        "",
        "| reason | count | row kept |",
        "|---|---|---|",
    ]
    kept_by_reason = {h["reason"]: h["row_kept"] for h in record["holes"]}
    for reason, count in record["reasons"].items():
        lines.append(f"| `{reason}` | {count} | {'yes' if kept_by_reason[reason] else 'no'} |")
    if not record["reasons"]:
        lines.append("| none | 0 | |")
    lines += ["", "## Every hole and withholding (quarter, group, why)", "", "| quarter-end | group | reason | kept | detail |",
              "|---|---|---|---|---|"]
    for h in record["holes"]:
        lines.append(f"| {h['quarter_end']} | {h['group']} | `{h['reason']}` | {'yes' if h['row_kept'] else 'no'} | {h['detail']} |")
    lines += ["", "## How stale the anchor is: when each group became public", "",
              "Days from quarter-end to the start of the day each group's figure is available (the slowest member's latest",
              "update), by quarter. Under the amended answer 16(d) this is the earliest a model may read the quarter.", "",
              "| quarter-end | large: filers | large: available after (days) | small: filers | small: available after (days) |",
              "|---|---|---|---|---|"]
    index = {(row.quarter_end.isoformat(), row.group): row for row in rows}
    for quarter in record["quarters"]:
        cells = []
        for group in rca.GROUPS:
            row = index.get((quarter, group))
            cells += [str(row.filers), str((row.available_from.date() - row.quarter_end).days)] if row else ["", "withheld"]
        lines.append(f"| {quarter} | " + " | ".join(cells) + " |")
    lines += ["", "## Diagnostic: the share of each group's balance that was public by a given lag",
              "",
              "Not read by any model: it only shows what a partial-sum reading would have had. A blank is a lag that ends after",
              "the parent's development end.", "",
              "| quarter-end | group | " + " | ".join(f"{lag} days" for lag in record["profile_lags_days"]) + " |",
              "|---|---|" + "---|" * len(record["profile_lags_days"])]
    for quarter in record["quarters"]:
        for group in rca.GROUPS:
            values = record["lag_profile"][quarter].get(group, {})
            cells = ["" if values.get(str(lag)) is None else f"{100 * values[str(lag)]:.0f}%"
                     for lag in record["profile_lags_days"]]
            lines.append(f"| {quarter} | {group} | " + " | ".join(cells) + " |")
    lines += ["", "## Not checked", "",
              "- The item against the current FFIEC 031/041 instructions (data-meaning answer 17(b), Nicholas's caveat): the",
              "  mnemonic and label are read from the bulk file. www.ffiec.gov refuses automated requests (CAPTCHA).",
              "- The Board's panel of large domestically chartered banks: the 25 largest filers by total assets stand in for it.",
              "- Which filers are commercial banks as against the savings institutions the H.8 leaves out.",
              "- Why the item is filled for a minority of filers only.",
              "- The posting lag between a submission and its public availability (not recorded): the whole day after the",
              "  update is skipped instead. The update stamps carry no time zone and are read as New York time.", ""]
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
