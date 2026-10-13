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
from pathlib import Path
from typing import Dict, List, Optional

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, scheduled

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "snapshots"

#: The published series and the tracked table each is built from.
SERIES: Dict[str, Path] = {
    "on_rrp_rate": scheduled.ON_RRP_RATE_TABLE,
    "srf_rate": scheduled.SRF_TABLE,
    "runoff_caps": scheduled.CAPS_TABLE,
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


def build(series: str, root: Path = ROOT, *, repo_commit: str) -> dict:
    """Write the series' snapshot and manifest under `root/snapshots/<series>/`, and return the manifest.

    The table is read through `scheduled` (which refuses one that does not match its own manifest), so a snapshot is
    always of a verified table.

    Raises:
        ValueError: if `series` is not published, `repo_commit` is not a full 40-character hash, or a saved page
            behind a row is missing.
    """
    table = _check_series(series)
    if not _HEX40.match(repo_commit):
        raise ValueError(f"repo_commit must be a full 40-character lowercase hash, got {repo_commit!r}")
    scheduled._verified_rows(table)
    data = table.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rows: List[dict] = list(csv.DictReader(data.decode("utf-8").splitlines()))
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
