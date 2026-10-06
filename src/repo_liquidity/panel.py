"""The Phase 3 measurement panel (Stage 1a).

Built from tracked fixtures only, with no network:

- the parent's raw roots `funding_inputs` (the published panel's inputs), `on_rrp_inputs`, `h8_inputs` and
  `srf_inputs`, parsed by the parent's own `ingest` at the pinned commit;
- this repository's H.4.1 first-print extract (`repo_liquidity.h41`);
- this repository's scheduled tables (`repo_liquidity.scheduled`).

Before anything else the build checks that the published columns, built alone, reproduce the parent's published
panel digest, as the parent's `scripts/scarcity_validation.py` does. Phase 3's built columns are then priced by the
parent's `data.build_daily_panel` under Phase 3's declaration (`repo_liquidity.declaration`), and the scheduled
columns are written on each row at its decision instant. Nothing is scored.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from types import MappingProxyType
from typing import Dict, List, Sequence

from repo_liquidity import declaration, h41, parent_root, scheduled

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "metadata" / "phase3_panel_manifest.json"
H41_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_treasury_first_print.csv"
PARENT_RAW_ROOTS = ("funding_inputs", "on_rrp_inputs", "h8_inputs", "srf_inputs")


@contextmanager
def _weekly_carry():
    """Carry the weekly H.4.1 column forward as the parent carries its weekly columns (at most 13 days)."""
    from repo_model import data

    saved = data.CARRY_FORWARD_COLUMNS
    data.CARRY_FORWARD_COLUMNS = MappingProxyType(
        {**saved, h41.SERIES: data.WEEKLY_CARRY_MAX_STALENESS_DAYS})
    try:
        yield
    finally:
        data.CARRY_FORWARD_COLUMNS = saved


def _parent_rows(workdir: Path):
    from repo_model.data import load_point_in_time_panel
    from repo_model.ingest import build_point_in_time_snapshot, load_snapshot_manifest

    snapshots = parent_root() / "tests" / "fixtures" / "snapshots"
    artifacts = [
        load_snapshot_manifest(path)
        for root in PARENT_RAW_ROOTS
        for path in sorted((snapshots / root).glob("*/*.manifest.json"))
    ]
    long_path = workdir / "phase3_point_in_time.csv"
    snapshot = build_point_in_time_snapshot(
        artifacts, long_path, registry_path=parent_root() / "metadata" / "sources.json")
    retrieved = {artifact.sha256: artifact.retrieved_at for artifact in artifacts}
    return load_point_in_time_panel(long_path), snapshot, retrieved


def build(output: Path) -> Dict:
    """Build the panel to `output` (CSV) and return its manifest.

    Raises:
        ValueError: if the published columns do not reproduce the parent's digest, if a Phase 3 column is refused,
            or if the dates differ from the published panel's.
    """
    from repo_model.data import build_daily_panel, verify_daily_panel, write_daily_panel

    published_manifest_path = parent_root() / "metadata" / "funding_panel_manifest.json"
    published_manifest = json.loads(published_manifest_path.read_text(encoding="utf-8"))
    cutoff = datetime.fromisoformat(published_manifest["build_cutoff"])
    decision = time.fromisoformat(published_manifest["decision_time"])
    published_columns = tuple(published_manifest["built_columns"])

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        rows, snapshot, retrieved = _parent_rows(workdir)
        parent_registry = declaration.parent_registry()

        published = build_daily_panel(rows, parent_registry, build_cutoff=cutoff, decision_time=decision,
                                      columns=published_columns, snapshot_retrieved_at=retrieved)
        published_path = workdir / "published_columns.csv"
        write_daily_panel(published, published_path, source_shas=snapshot.source_shas)
        parent_digest = verify_daily_panel(published_path, published_manifest_path)

    extract_sha = hashlib.sha256(H41_EXTRACT.read_bytes()).hexdigest()
    h41_rows = h41.observations(h41.load_extract(H41_EXTRACT), source_sha=extract_sha)

    with declaration.phase3_declaration(), _weekly_carry():
        phase3 = build_daily_panel(list(rows) + h41_rows, declaration.registry(), build_cutoff=cutoff,
                                   decision_time=decision, columns=published_columns + declaration.BUILT_COLUMNS,
                                   snapshot_retrieved_at=retrieved)
    if phase3.refusals:
        raise ValueError(f"the Phase 3 build refused {dict(phase3.refusals)}")
    if [row.date for row in phase3.observations] != [row.date for row in published.observations]:
        raise ValueError("the Phase 3 panel's dates are not the published panel's")

    observations = scheduled.with_scheduled(phase3.observations, decision_time=decision)
    columns = list(published_columns) + list(declaration.BUILT_COLUMNS) + list(declaration.SCHEDULED_COLUMNS)
    _write(observations, columns, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()

    manifest = {
        "note": "Generated by scripts/build_panel.py; never edited by hand.",
        "parent_commit": _parent_commit(),
        "parent_panel_sha256": parent_digest,
        "h41_extract_sha256": extract_sha,
        "srf_table_sha256": hashlib.sha256(scheduled.SRF_TABLE.read_bytes()).hexdigest(),
        "caps_table_sha256": hashlib.sha256(scheduled.CAPS_TABLE.read_bytes()).hexdigest(),
        "overlay_sha256": hashlib.sha256(declaration.OVERLAY_PATH.read_bytes()).hexdigest(),
        "build_cutoff": cutoff.isoformat(),
        "decision_time": decision.isoformat(),
        "start_date": observations[0].date.isoformat(),
        "end_date": observations[-1].date.isoformat(),
        "columns": columns,
        "phase3_columns": list(declaration.BUILT_COLUMNS) + list(declaration.SCHEDULED_COLUMNS),
        "coverage": _coverage(observations, list(declaration.BUILT_COLUMNS) + list(declaration.SCHEDULED_COLUMNS)),
        "holes": {column: phase3.holes.get(column, 0) for column in declaration.BUILT_COLUMNS},
        "refusals": dict(phase3.refusals),
        "sha256": digest,
    }
    return manifest


def _parent_commit() -> str:
    import subprocess

    return subprocess.run(["git", "-C", str(parent_root()), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def _write(observations, columns: Sequence[str], path: Path) -> None:
    lines = [",".join(["date", *columns])]
    for row in observations:
        cells = [row.date.isoformat()]
        for column in columns:
            value = row.values.get(column)
            cells.append("" if value is None else format(value, ".15g"))
        lines.append(",".join(cells))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _coverage(observations, columns: Sequence[str]) -> Dict[str, Dict]:
    out = {}
    for column in columns:
        present = [row.date for row in observations if row.values.get(column) is not None]
        out[column] = {
            "first": present[0].isoformat() if present else None,
            "last": present[-1].isoformat() if present else None,
            "missing_rows": len(observations) - len(present),
        }
    return out


def write_manifest(manifest: Dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest() -> Dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))
