"""Digest-named snapshots of this repository's published series (#25; `docs/decisions/snapshots.md`, a draft).

A series is published at two paths under `snapshots/<series>/`:
- `manifest.json`, a stable path, which says which bytes are the series now;
- `<sha256>.csv`, the bytes themselves, named by their own digest. A file is never edited or deleted once published;
  a changed series gets a new file and a new manifest.

The manifest carries the digest, the row count and span, the saved page behind each row (by digest), the parent pin
and panel digest (`repo_liquidity.PARENT_COMMIT`, `PANEL_SHA256`) and the commit of this repository the snapshot was
built from. A reader names the digest it expects, so a later change to the series cannot reach it unseen. Standard
library only.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, contenthash, development, h41, h8, rca, scheduled, slr

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "snapshots"

H41_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h41"
H41_AGENCY_EXTRACT = H41_DIR / "h41_agency_first_print.csv"
H41_MBS_EXTRACT = H41_DIR / "h41_mbs_first_print.csv"
#: The columns of the agency-securities snapshot (#30). The change columns are the releases' weekly changes in the
#: week average as printed, in millions of dollars; `agency_securities_change_musd` is their sum (answer 15).
AGENCY_SECURITIES_COLUMNS = ("week_ended", "release_date", "agency_debt_change_musd", "mbs_change_musd",
                             "agency_securities_change_musd", "url", "fetch_sha256", "content_sha256")
#: The columns the agency-securities content hash covers (the values, not the URL or the fetch hash), as whole millions.
AGENCY_CONTENT_COLUMNS = ("week_ended", "release_date", "agency_debt_change_musd", "mbs_change_musd",
                          "agency_securities_change_musd")
#: Said in the manifest of every snapshot that carries a fetch hash (finding #40, #89).
HASH_NOTE = ("fetch_sha256 identifies the fetch, not the release (finding #40); content_sha256 identifies the "
             "extracted values")


def agency_row_content_sha256(row) -> str:
    """The content hash of one agency-securities row (a mapping by column name), from its values alone."""
    return contenthash.content_sha256(AGENCY_CONTENT_COLUMNS, [[row[c] for c in AGENCY_CONTENT_COLUMNS]],
                                      {c: 0 for c in AGENCY_CONTENT_COLUMNS[2:]})

#: The weekly first-print series (#26): the tracked extract each is a copy of, plus the `break_ids` column of the breaks
#: record (#47). Its manifest carries the weeks and
#: releases it spans, and the SHA-256 of each archived release page behind it (the pages are not tracked).
WEEKLY: Dict[str, Path] = {
    "h8_groups": ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups" / h8.EXTRACT_NAME,
}

#: The SLR headroom of the nine G-SIB depository subsidiaries (#63): the tracked latest-filed extract, published as it
#: stands (every row labelled `vintage = latest_filed`; row 16 of `docs/decisions/data-meaning.md`).
SLR_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "slr_headroom"
SLR_EXTRACT = SLR_DIR / slr.EXTRACT_NAME

#: The RC-A anchor of the group reserves (#43): the tracked latest-filed extract of the two domestic groups, published as it
#: stands (every row labelled `vintage = latest_filed`; row 16 of `docs/decisions/data-meaning.md`). The weekly
#: group-reserves series does not read it (her ruling of 14 October 2026, option (i)) and is tracked, not published.
RCA_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "rca_anchor"
RCA_EXTRACT = RCA_DIR / rca.EXTRACT_NAME

#: The published series and the tracked table each is built from. The three FOMC series are copies of their tables;
#: `agency_securities` is computed from two H.4.1 first-print extracts (see `build`); the weekly series are copies of
#: their extracts.
SERIES: Dict[str, Path] = {
    "on_rrp_rate": scheduled.ON_RRP_RATE_TABLE,
    "srf_rate": scheduled.SRF_TABLE,
    "runoff_caps": scheduled.CAPS_TABLE,
    "agency_securities": H41_AGENCY_EXTRACT,
    **WEEKLY,
    "slr_headroom": SLR_EXTRACT,
    "rca_anchor": RCA_EXTRACT,
}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _check_series(series: str) -> Path:
    if series not in SERIES:
        raise ValueError(f"unknown series {series!r}; published series are {sorted(SERIES)}")
    return SERIES[series]


def manifest_path(series: str, root: Path = ROOT) -> Path:
    _check_series(series)
    return root / "snapshots" / series / "manifest.json"


def load_manifest(series: str, root: Path = ROOT) -> dict:
    """The series' current manifest."""
    return json.loads(manifest_path(series, root).read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _agency_securities_bytes(agency_extract: Path, mbs_extract: Path):
    """The agency-securities snapshot's bytes, and the page each row was read from.

    Both extracts are read through `h41.load_extract`, which refuses one that does not match its own manifest. A row is
    the agency-debt change plus the MBS change of the same release, so both extracts must name the same release page
    (its URL). The `fetch_sha256` is the agency extract's: the archive injects per-request tokens into every page, so
    each fetch of one page has its own digest, and the MBS extract's differs from it. What ties the rows to one
    release is `scripts/fetch_h41.py --row agency`, which checked every week's Treasury and MBS rows on the page it
    fetched against the tracked extracts.
    """
    agency, mbs = h41.load_extract(agency_extract), h41.load_extract(mbs_extract)
    total = h41.agency_securities(agency, mbs)

    def raw(path: Path):
        with path.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    lines = [",".join(AGENCY_SECURITIES_COLUMNS)]
    pages = {}
    for debt, backed, both, a, m in zip(agency, mbs, total, raw(agency_extract), raw(mbs_extract)):
        if a["url"] != m["url"]:
            raise ValueError(f"the week ended {debt.week_ended}: the agency-debt and MBS rows were read from "
                             f"different releases ({a['url']} and {m['url']})")
        values = {"week_ended": debt.week_ended.isoformat(), "release_date": debt.release_date.isoformat(),
                  "agency_debt_change_musd": str(debt.change_from_prior_week),
                  "mbs_change_musd": str(backed.change_from_prior_week),
                  "agency_securities_change_musd": str(both.change_from_prior_week)}
        lines.append(",".join((*(values[c] for c in AGENCY_CONTENT_COLUMNS), a["url"], a["fetch_sha256"],
                               agency_row_content_sha256(values))))
        pages[a["url"]] = a["fetch_sha256"]
    return ("\n".join(lines) + "\n").encode("utf-8"), pages, total


def _build_agency_securities(root: Path, repo_commit: str, agency_extract: Path, mbs_extract: Path) -> dict:
    data, pages, total = _agency_securities_bytes(agency_extract, mbs_extract)
    digest = hashlib.sha256(data).hexdigest()
    (root / "snapshots" / "agency_securities").mkdir(parents=True, exist_ok=True)
    relative = f"snapshots/agency_securities/{digest}.csv"
    (root / relative).write_bytes(data)
    manifest = {
        "series": "agency_securities",
        "path": relative,
        "sha256": digest,
        "columns": list(AGENCY_SECURITIES_COLUMNS),
        "rows": len(total),
        "first_announced": f"{total[0].release_date.isoformat()}T{h41.RELEASE_TIME.strftime('%H:%M')}",
        "last_announced": f"{total[-1].release_date.isoformat()}T{h41.RELEASE_TIME.strftime('%H:%M')}",
        "last_effective": total[-1].week_ended.isoformat(),
        "source_table": _relative(agency_extract),
        "source_tables": [_relative(agency_extract), _relative(mbs_extract)],
        "source_pages": pages,
        "hash_note": HASH_NOTE,
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "repo_commit": repo_commit,
    }
    manifest_path("agency_securities", root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                                        encoding="utf-8")
    return manifest


def _unlocked(source: bytes):
    """The rate table's bytes without the rows the model repo's lockbox holds (#59, finding #55).

    A row is dated by its announcement (the day it became public). The tracked table keeps every row, because the
    Stage 4 freeze and the records read it there; the snapshot is the part of it a reader may see. Returns the bytes,
    the kept rows and the announcement dates left out.
    """
    lines = source.decode("utf-8").splitlines()
    rows: List[dict] = list(csv.DictReader(lines))
    kept, omitted = [lines[0]], []
    kept_rows: List[dict] = []
    for line, row in zip(lines[1:], rows):
        if development.is_locked(date.fromisoformat(row["announcement_date"])):
            omitted.append(row["announcement_date"])
        else:
            kept.append(line)
            kept_rows.append(row)
    return ("\n".join(kept) + "\n").encode("utf-8"), kept_rows, omitted


def build(series: str, root: Path = ROOT, *, repo_commit: str, agency_extract: Optional[Path] = None) -> dict:
    """Write the series' snapshot and manifest under `root/snapshots/<series>/`, and return the manifest.

    The table is read through `scheduled` (which refuses one that does not match its own manifest), so a snapshot is
    always of a verified table. `agency_securities` is read the same way through `h41.load_extract`; `agency_extract`
    names another agency-debt extract for it (tests).

    Raises:
        ValueError: if `series` is not published, `repo_commit` is not a full 40-character hash, a saved page
            behind a row is missing, or an H.4.1 extract does not match its manifest.
    """
    table = _check_series(series)
    if not _HEX40.match(repo_commit):
        raise ValueError(f"repo_commit must be a full 40-character lowercase hash, got {repo_commit!r}")
    if series in WEEKLY:
        return _build_weekly(series, table, root, repo_commit)
    if series == "slr_headroom":
        return _build_slr(table, root, repo_commit)
    if series == "rca_anchor":
        return _build_rca(table, root, repo_commit)
    if series == "agency_securities":
        return _build_agency_securities(root, repo_commit, agency_extract or table, H41_MBS_EXTRACT)
    scheduled._verified_rows(table)
    source = table.read_bytes()
    data, rows, omitted = _unlocked(source)
    digest = hashlib.sha256(data).hexdigest()
    pages = {}
    for row in rows:
        page = scheduled.NOTES / "pages" / row["page"]
        if not page.exists():
            raise ValueError(f"{table.name}: the saved page {row['page']} is missing")
        pages[row["page"]] = hashlib.sha256(page.read_bytes()).hexdigest()
    directory = root / "snapshots" / series
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"snapshots/{series}/{digest}.csv"
    (root / relative).write_bytes(data)
    manifest = {
        "series": series,
        "path": relative,
        "sha256": digest,
        "columns": list(rows[0]),
        "rows": len(rows),
        "first_announced": f"{rows[0]['announcement_date']}T{rows[0]['announcement_time']}",
        "last_announced": f"{rows[-1]['announcement_date']}T{rows[-1]['announcement_time']}",
        "last_effective": rows[-1]["effective_date"],
        "source_table": str(table.relative_to(ROOT)),
        "source_table_sha256": hashlib.sha256(source).hexdigest(),
        "locked_rows_omitted": omitted,
        "source_pages": pages,
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "repo_commit": repo_commit,
    }
    manifest_path(series, root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _build_slr(table: Path, root: Path, repo_commit: str) -> dict:
    """The snapshot of the SLR-headroom extract: its bytes, labelled as amended (latest-filed) figures.

    The extract is read through `slr.load_extract`, which refuses one that does not match its manifest, is not labelled
    `latest_filed`, or holds a figure updated on a day the parent's lockbox holds. The manifest says in words that the
    figures are not first prints, names the stored zips by digest, and points at the coverage record.
    """
    rows = slr.load_extract(table)
    data = table.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    sources = json.loads(table.with_name(slr.SOURCES_NAME).read_text(encoding="utf-8"))
    coverage = table.with_name(slr.COVERAGE_NAME)
    used = {row.source_zip_sha256 for row in rows}
    pages = {item["quarter_end"]: item["sha256"] for item in sources["zips"]}
    restored_record = sources.get("restored")
    listed = set(pages.values()) | set(restored_record["source_zips"] if restored_record else ())
    unknown = sorted(used - listed)
    if unknown:
        raise ValueError(f"{table.name}: a row names the zip {unknown[0]}, which the sources record does not list")
    directory = root / "snapshots" / "slr_headroom"
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"snapshots/slr_headroom/{digest}.csv"
    (root / relative).write_bytes(data)
    manifest = {
        "series": "slr_headroom",
        "path": relative,
        "sha256": digest,
        "columns": list(slr.EXTRACT_COLUMNS),
        "rows": len(rows),
        "vintage": slr.VINTAGE,
        "vintage_note": ("Latest-filed Call Report figures, amended since their first filing, not first prints: each "
                         "(bank, quarter) value is available only from the day after its latest-update time. "
                         "docs/decisions/data-meaning.md row 16 (ruling of 13 October 2026, reading 2)."),
        "measure_note": ("The `measure` column is `main` for all nine banks. State Street is read at the bank of the G-SIB, "
                         "State Street Bank and Trust Company (IDRSSD 35301), and is in the main measure (Eleonora, 15 "
                         "October 2026). This replaces her decision on repo-market-liquidity#69 (Q2, 14 October 2026), "
                         "made on the figures of State Street Bank and Trust Company, N.A. (IDRSSD 93619), a trust "
                         "subsidiary read by mistake. A reader of the main measure still filters on `measure == main`."),
        "requirement_note": ("`requirement_pct` and `headroom_pp` follow the requirement table of "
                             "docs/decisions/slr-requirement.md (a draft until Eleonora merges it): 6.0% for quarter-ends "
                             "2018-01-01 to 2026-03-31, and no value from 2026-04-01, where the rule is bank-specific."),
        "first_quarter": min(row.quarter_end for row in rows).isoformat(),
        "last_quarter": max(row.quarter_end for row in rows).isoformat(),
        "last_update": max(row.latest_update for row in rows).isoformat(),
        "source_table": str(table.relative_to(ROOT)),
        "source_zips": pages,
        **({"restored_rows": {
            "rows": sum(1 for row in rows if row.restored_from),
            "superseded_sha256": restored_record["superseded_sha256"],
            "superseded_path": restored_record["superseded_path"],
            "note": ("Filings made on or before the development end that a later amendment replaced in the bulk files "
                     "(Eleonora's ruling of 19 October 2026 on finding #120; #123). Each row carries its own "
                     "`available_from` and `source_zip_sha256` as stored in the superseded snapshot, and names it in "
                     "`restored_from`. Their zips are lost (finding #94), so they are not in `source_zips`."),
            "source_zips": restored_record["source_zips"]}} if restored_record else {}),
        "source_zips_record": str(table.with_name(slr.SOURCES_NAME).relative_to(ROOT)),
        "coverage": {"path": str(coverage.relative_to(ROOT)), "sha256": hashlib.sha256(coverage.read_bytes()).hexdigest()},
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "repo_commit": repo_commit,
    }
    manifest_path("slr_headroom", root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _build_rca(table: Path, root: Path, repo_commit: str) -> dict:
    """The snapshot of the RC-A anchor extract: its bytes, labelled as amended (latest-filed) sums.

    The extract is read through `rca.load_extract`, which refuses one that does not match its manifest, is not labelled
    `latest_filed`, or holds a group with a member updated on a day the parent's lockbox holds. The manifest says in words
    that the figures are not first prints and the groups an approximation, names the stored zips by digest, and points at
    the coverage record (which carries how stale the anchor is).
    """
    rows = rca.load_extract(table)
    data = table.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    sources = json.loads(table.with_name(rca.SOURCES_NAME).read_text(encoding="utf-8"))
    coverage = table.with_name(rca.COVERAGE_NAME)
    used = {row.source_zip_sha256 for row in rows}
    pages = {item["quarter_end"]: item["sha256"] for item in sources["zips"]}
    unknown = sorted(used - set(pages.values()))
    if unknown:
        raise ValueError(f"{table.name}: a row names the zip {unknown[0]}, which the sources record does not list")
    directory = root / "snapshots" / "rca_anchor"
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"snapshots/rca_anchor/{digest}.csv"
    (root / relative).write_bytes(data)
    manifest = {
        "series": "rca_anchor",
        "path": relative,
        "sha256": digest,
        "columns": list(rca.EXTRACT_COLUMNS),
        "rows": len(rows),
        "vintage": rca.VINTAGE,
        "vintage_note": ("Latest-filed Call Report sums, amended since their first filing, not first prints: each group's "
                         "figure is available only from the day after its slowest member's latest-update time. "
                         "docs/decisions/data-meaning.md row 16 (ruling of 13 October 2026, reading 2)."),
        "groups_note": ("The groups are an approximation (ruling of 14 October 2026 on PR #50, Q3): the 25 filers with the "
                        "largest total assets stand in for the Board's panel of large domestic banks; the small group is every "
                        "other filer that carries RC-A item 0090. The foreign-related group has no anchor: its weekly level is "
                        "the H.8 foreign-related cash assets, an approximation (ruling of 14 October 2026, option a)."),
        "first_quarter": min(row.quarter_end for row in rows).isoformat(),
        "last_quarter": max(row.quarter_end for row in rows).isoformat(),
        "last_update": max(row.latest_update for row in rows).isoformat(),
        "source_table": str(table.relative_to(ROOT)),
        "source_zips": pages,
        "source_zips_record": str(table.with_name(rca.SOURCES_NAME).relative_to(ROOT)),
        "coverage": {"path": str(coverage.relative_to(ROOT)), "sha256": hashlib.sha256(coverage.read_bytes()).hexdigest()},
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "repo_commit": repo_commit,
    }
    manifest_path("rca_anchor", root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _build_weekly(series: str, table: Path, root: Path, repo_commit: str) -> dict:
    """The snapshot of a weekly first-print extract: the extract's bytes, and the releases it was cut from.

    The extract is read through `h8.load_extract`, which refuses one that does not match its own manifest. Each row
    names the SHA-256 of the release page that first printed it; the manifest lists them under `source_pages`, keyed by
    release date, and the build refuses an extract whose rows name a page the releases record does not list.
    """
    prints = h8.load_extract(table)
    record = h8.load_moves()
    flags = h8.break_flags(record)
    unknown = sorted(week for week in flags if week not in {item.week_ending for item in prints})
    if unknown:
        raise ValueError(f"{table.name}: the breaks record flags the week ending {unknown[0]}, which is not in the extract")
    # The snapshot is the extract's rows with one more column: the id of the break that starts at the week, if any.
    with table.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(h8.SNAPSHOT_COLUMNS)
    for row, item in zip(rows, prints):
        writer.writerow([row[column] for column in h8.EXTRACT_COLUMNS] + [flags.get(item.week_ending, "")])
    data = buffer.getvalue().encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    releases = json.loads(table.with_name(h8.RELEASES_NAME).read_text(encoding="utf-8"))
    pages = {record["release_date"]: record["fetch_sha256"] for record in releases["releases"]}
    contents = {record["release_date"]: record["content_sha256"] for record in releases["releases"]}
    derived = h8.release_content_hashes(prints)
    for day, recorded in sorted(contents.items()):
        if recorded != derived.get(day):
            raise ValueError(f"{table.name}: the releases record gives the release of {day} content_sha256 {recorded}, "
                             f"but its values in the extract hash to {derived.get(day)}")
    for item in prints:
        if pages.get(item.release_date.isoformat()) != item.fetch_sha256:
            raise ValueError(f"{table.name}: the week ending {item.week_ending} names a page for the release of "
                             f"{item.release_date} that the releases record does not list")
    directory = root / "snapshots" / series
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"snapshots/{series}/{digest}.csv"
    (root / relative).write_bytes(data)
    manifest = {
        "series": series,
        "path": relative,
        "sha256": digest,
        "columns": list(h8.SNAPSHOT_COLUMNS),
        "breaks": {"source": str(h8.MOVES_PATH.relative_to(ROOT)),
                   "sha256": hashlib.sha256(h8.MOVES_PATH.read_bytes()).hexdigest(),
                   "weeks": {week.isoformat(): move for week, move in sorted(flags.items())}},
        "rows": len(prints),
        "first_week": prints[0].week_ending.isoformat(),
        "last_week": prints[-1].week_ending.isoformat(),
        "last_release": prints[-1].release_date.isoformat(),
        "source_table": str(table.relative_to(ROOT)),
        "source_pages": pages,
        "source_content_sha256": contents,
        "hash_note": HASH_NOTE,
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "repo_commit": repo_commit,
    }
    manifest_path(series, root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def read(series: str, *, sha256: Optional[str] = None, root: Path = ROOT) -> List[dict]:
    """The rows of the published snapshot, verified against the manifest.

    Args:
        sha256: the digest the caller expects; when given, the manifest must carry it.

    Raises:
        ValueError: if the expected digest is not the published one, or the file is not the bytes its name says.
    """
    manifest = load_manifest(series, root)
    if sha256 is not None and sha256 != manifest["sha256"]:
        raise ValueError(f"{series}: the published digest is {manifest['sha256']}, not {sha256}")
    path = root / manifest["path"]
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != manifest["sha256"] or path.name != actual + ".csv":
        raise ValueError(f"{path.name} does not match its manifest ({actual} != {manifest['sha256']})")
    return list(csv.DictReader(data.decode("utf-8").splitlines()))
