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
import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, development, h41, h8, scheduled

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "snapshots"

H41_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h41"
H41_AGENCY_EXTRACT = H41_DIR / "h41_agency_first_print.csv"
H41_MBS_EXTRACT = H41_DIR / "h41_mbs_first_print.csv"
#: The columns of the agency-securities snapshot (#30). The change columns are the releases' weekly changes in the
#: week average as printed, in millions of dollars; `agency_securities_change_musd` is their sum (answer 15).
AGENCY_SECURITIES_COLUMNS = ("week_ended", "release_date", "agency_debt_change_musd", "mbs_change_musd",
                             "agency_securities_change_musd", "url", "page_sha256")

#: The weekly first-print series (#26): the tracked extract each is a copy of. Its manifest carries the weeks and
#: releases it spans, and the SHA-256 of each archived release page behind it (the pages are not tracked).
WEEKLY: Dict[str, Path] = {
    "h8_groups": ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups" / h8.EXTRACT_NAME,
}

#: The published series and the tracked table each is built from. The three FOMC series are copies of their tables;
#: `agency_securities` is computed from two H.4.1 first-print extracts (see `build`); the weekly series are copies of
#: their extracts.
SERIES: Dict[str, Path] = {
    "on_rrp_rate": scheduled.ON_RRP_RATE_TABLE,
    "srf_rate": scheduled.SRF_TABLE,
    "runoff_caps": scheduled.CAPS_TABLE,
    "agency_securities": H41_AGENCY_EXTRACT,
    **WEEKLY,
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
    (its URL). The `page_sha256` is the agency extract's: the archive injects per-request tokens into every page, so
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
        lines.append(",".join((debt.week_ended.isoformat(), debt.release_date.isoformat(),
                               str(debt.change_from_prior_week), str(backed.change_from_prior_week),
                               str(both.change_from_prior_week), a["url"], a["page_sha256"])))
        pages[a["url"]] = a["page_sha256"]
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


def _build_weekly(series: str, table: Path, root: Path, repo_commit: str) -> dict:
    """The snapshot of a weekly first-print extract: the extract's bytes, and the releases it was cut from.

    The extract is read through `h8.load_extract`, which refuses one that does not match its own manifest. Each row
    names the SHA-256 of the release page that first printed it; the manifest lists them under `source_pages`, keyed by
    release date, and the build refuses an extract whose rows name a page the releases record does not list.
    """
    prints = h8.load_extract(table)
    data = table.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    releases = json.loads(table.with_name(h8.RELEASES_NAME).read_text(encoding="utf-8"))
    pages = {record["release_date"]: record["sha256"] for record in releases["releases"]}
    for item in prints:
        if pages.get(item.release_date.isoformat()) != item.release_sha256:
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
        "columns": list(h8.EXTRACT_COLUMNS),
        "rows": len(prints),
        "first_week": prints[0].week_ending.isoformat(),
        "last_week": prints[-1].week_ending.isoformat(),
        "last_release": prints[-1].release_date.isoformat(),
        "source_table": str(table.relative_to(ROOT)),
        "source_pages": pages,
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
