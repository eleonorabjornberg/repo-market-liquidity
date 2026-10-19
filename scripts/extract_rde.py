#!/usr/bin/env python3
"""Store the NY Fed's RDE workbook and cut the estimates extract from it (#132; `repo_liquidity.rde`).

    # 1. Fetch with one plain request (see the directive), then store the file as fetched:
    curl -sS -L -D headers.txt -o download-data.xlsx \\
        https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/elasticity/download-data
    PYTHONPATH=src python3 scripts/extract_rde.py capture download-data.xlsx --retrieved-utc 2026-10-19T19:35:11Z

    # 2. Cut the extract from the latest stored workbook, or check that the tracked files are what it gives:
    PYTHONPATH=src python3 scripts/extract_rde.py cut [--check]

`capture` stores the workbook as `tests/fixtures/snapshots/rde/rde-<release date>-<sha256>.xlsx` and adds it to
`rde_captures.json`. A stored workbook is never overwritten or deleted: the Fed serves only its latest release, so a later
fetch that differs is a new vintage kept beside the old one. `cut` reads the vintage with the latest release date and
writes, in the same directory:

- `rde_estimates.csv` and its `.manifest.json`: one row per estimate date from the one the launch release headlined
  (2024-10-02), the back history before it left out;
- `rde_estimates.coverage.json`: the rows read, those withheld past the development end, and the sign and significance
  changes;
- `docs/research/rde-table.md`: the same in words (generated, never hand-edited).

Nothing is read past the parent's development end. The declared lag in `declarations/nyfed_rde.json` must be the measured
worst case. `--check` rebuilds in memory and compares. Nothing is scored or wired into a goalpost.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

from repo_model.ingest import SnapshotArtifact

from repo_liquidity import declaration, development, rde

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/snapshots/rde"
TABLE_MD = ROOT / "docs/research/rde-table.md"


def _json(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def capture(workbook: Path, retrieved_utc: str, output: Path) -> Path:
    """Store a fetched workbook beside the earlier ones and record it. Returns the stored path.

    Raises:
        ValueError: if the file is not a workbook the parser reads, or `retrieved_utc` is not a UTC time.
    """
    payload = workbook.read_bytes()
    rows, cover = rde.rows_from_workbook(payload)
    datetime.strptime(retrieved_utc, "%Y-%m-%dT%H:%M:%SZ")
    digest = hashlib.sha256(payload).hexdigest()
    name = f"rde-{cover['release_date'].isoformat()}-{digest}.xlsx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / name
    record_path = output / rde.CAPTURES_NAME
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {
        "url": rde.URL, "page": rde.PAGE_URL, "captures": []}
    if any(item["sha256"] == digest for item in record["captures"]):
        raise ValueError(f"{name} is already stored")
    path.write_bytes(payload)
    record["captures"].append({
        "file": name, "sha256": digest, "size": len(payload), "retrieved_utc": retrieved_utc,
        "release_date": cover["release_date"].isoformat(), "update_date": cover["update_date"].isoformat(),
        "estimates": len(rows), "first_estimate": rows[0].estimate_date.isoformat(),
        "last_estimate": rows[-1].estimate_date.isoformat()})
    record["captures"].sort(key=lambda item: (item["release_date"], item["retrieved_utc"]))
    record_path.write_bytes(_json(record))
    return path


def cut(directory: Path):
    record = json.loads((directory / rde.CAPTURES_NAME).read_text(encoding="utf-8"))
    latest = record["captures"][-1]
    payload = (directory / latest["file"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != latest["sha256"]:
        raise ValueError(f"{latest['file']} is not the bytes its name and the captures record say")
    rows, cover = rde.rows_from_workbook(payload)
    if cover["release_date"].isoformat() != latest["release_date"]:
        raise ValueError(f"{latest['file']}: the cover sheet's release date is {cover['release_date']}, the record says "
                         f"{latest['release_date']}")
    table, back_history = rde.split_back_history(rows)
    kept, holes = rde.withhold_locked(table)
    declared = declaration.overlay().get(rde.SOURCE_ID, {}).get("release_lag", {}).get("days")
    worst = rde.worst_case_lag_days(kept)
    if declared != worst:
        raise ValueError(f"declarations/nyfed_rde.json declares {declared} days; the measured worst case is {worst}")
    extract = rde.write_extract(kept)
    summary = rde.coverage(kept, holes, back_history)
    artifact = SnapshotArtifact(
        source_id=rde.SOURCE_ID, path=Path(rde.SOURCE_ID) / rde.EXTRACT_NAME, retrieved_at=latest["retrieved_utc"],
        sha256=hashlib.sha256(extract).hexdigest(), url=rde.URL, byte_count=len(extract)).as_dict()
    coverage = {**summary, "vintage": kept[0].vintage, "development_end": development.development_end().isoformat(),
                "captures": record["captures"]}
    files = {rde.EXTRACT_NAME: extract, rde.EXTRACT_NAME + ".manifest.json": _json(artifact),
             rde.COVERAGE_NAME: _json(coverage)}
    return files, {k: summary[k] for k in ("rows", "withheld", "worst_case_lag_days")}, render_markdown(kept, coverage)


def render_markdown(rows, coverage) -> str:
    changes = coverage["sign_changes"]
    significance = coverage["significance_changes"]
    ordered = sorted(rows, key=lambda r: r.estimate_date)
    lines = [
        "# NY Fed reserve demand elasticity: the table (generated)",
        "",
        "**Generated by `scripts/extract_rde.py`; never hand-edited.** Hypothesis and step: H7m, an external check on",
        "goalposts 1 and 3, #132 (Eleonora's ruling of 19 October 2026 on Lens B of repo-market-model#958). Inputs built,",
        "nothing scored, nothing wired into a goalpost. **Reported, never deciding**: R and S stay the deciding benchmarks.",
        "",
        f"- Vintage: `{coverage['vintage']}`. The page serves only its latest release, so each value is the one in that",
        "  release, not necessarily the one first printed; earlier releases are not recoverable here.",
        f"- Rows: {coverage['rows']} estimate dates, {coverage['first_estimate']} to {coverage['last_estimate']}. Read as",
        f"  public from {coverage['first_read_from'][:10]} (the launch) to {coverage['last_read_from'][:10]}, at 10:00",
        "  New York time on a third Thursday.",
        f"- Left out, the back history the launch carried: {coverage['back_history']['estimates']} estimate dates, "
        f"{coverage['back_history']['first']} to {coverage['back_history']['last']}. They stay in the stored workbook.",
        f"- Withheld, because their assigned release falls after the development end ({coverage['development_end']}):",
        f"  {coverage['withheld']} estimate dates"
        + (f" ({coverage['withheld_estimates'][0]['estimate_date']} to {coverage['withheld_estimates'][-1]['estimate_date']})."
           if coverage["withheld"] else "."),
        f"- Worst-case lag, estimate date to the day it is read as public: {coverage['worst_case_lag_days']} calendar days:",
        f"  an estimate waits for the first release at least {rde.UPDATE_TO_RELEASE_DAYS} days after its date.",
        "",
        "## Where the estimates sit",
        "",
        "| period | estimates | median of the main estimate | with the 95% interval wholly below zero | positive |",
        "|---|---|---|---|---|",
    ]
    for label, start, end in (("2024-10 to 2024-12", date(2024, 10, 1), date(2024, 12, 31)), ("2025", date(2025, 1, 1), date(2025, 12, 31)),
                              ("2026 to the development end", date(2026, 1, 1), date(2026, 12, 31))):
        part = [r for r in ordered if start <= r.estimate_date <= end]
        values = sorted(r.elasticity_p50 for r in part)
        lines.append(f"| {label} | {len(part)} | {values[len(values) // 2]:.3f} | "
                     f"{sum(r.elasticity_p97_5 < 0 for r in part)} | {sum(r.sign == 'positive' for r in part)} |")
    lines += ["", f"## Sign changes of the main estimate ({len(changes)})", "",
              "The sign of the 50th percentile. A positive value is the wrong sign for an elasticity of the rate to reserves,",
              "so a run of positive values is noise around zero in the abundant region, not a finding.", "",
              "| estimate date | from | to | read as public from |", "|---|---|---|---|"]
    lines += [f"| {c['estimate_date']} | {c['from']} | {c['to']} | {c['read_from'][:10]} |" for c in changes]
    lines += ["", f"## Dates at which the 95% interval starts or stops excluding zero ({len(significance)})", "",
              "The Fed's operational test: the transition from abundant to ample reserves is the level at which the estimate",
              "becomes statistically significant.", "", "| estimate date | the interval now excludes zero | read as public from |",
              "|---|---|---|"]
    lines += [f"| {c['estimate_date']} | {'yes' if c['interval_excludes_zero_95'] else 'no'} | {c['read_from'][:10]} |"
              for c in significance]
    if not significance:
        lines.append("| none | | |")
    last = ordered[-1]
    lines += ["", f"The last estimate read is {last.estimate_date}: {last.elasticity_p50:.3f} "
              f"[{last.elasticity_p2_5:.3f}, {last.elasticity_p97_5:.3f}], read as public from "
              f"{last.available_from.date()}.", "",
              "## Not checked", "",
              "- Whether the RDE's definition of scarce reserves matches H7's kink.",
              "- Which release first carried each estimate: the workbook does not say, so the availability is the rule in",
              "  `repo_liquidity.rde` (the first third-Thursday release at least 10 days after the estimate date), checked on",
              "  the one release stored (cover sheet: updated 5 October, released 15 October 2026).",
              "- The release time of 10:00 and the third Thursday in months where that day is a holiday: taken from the",
              "  ruling, not from a Fed statement; the stored release's own date (Thursday 15 October 2026) is the third Thursday.",
              "- Revisions: the values are those of the latest release (see above).",
              "- Whether the Oct 2026 re-estimate of earlier dates uses data from after the estimate date. The product is",
              "  described as real-time by construction; the staff report was not read for this.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    grab = sub.add_parser("capture", help="store a fetched workbook beside the earlier ones")
    grab.add_argument("workbook", type=Path)
    grab.add_argument("--retrieved-utc", required=True, help="the fetch time, e.g. 2026-10-19T19:35:11Z")
    grab.add_argument("--output", type=Path, default=OUTPUT)
    build = sub.add_parser("cut", help="cut the extract from the latest stored workbook")
    build.add_argument("--output", type=Path, default=OUTPUT)
    build.add_argument("--markdown", type=Path, default=TABLE_MD)
    build.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "capture":
        print(capture(args.workbook, args.retrieved_utc, args.output))
        return 0
    files, summary, markdown = cut(args.output)
    if args.check:
        stale = [name for name, payload in files.items()
                 if not (args.output / name).is_file() or (args.output / name).read_bytes() != payload]
        if not args.markdown.is_file() or args.markdown.read_text(encoding="utf-8") != markdown:
            stale.append(str(args.markdown))
        print(json.dumps({**summary, "stale": stale}, indent=2))
        return 1 if stale else 0
    for name, payload in files.items():
        (args.output / name).write_bytes(payload)
    args.markdown.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
