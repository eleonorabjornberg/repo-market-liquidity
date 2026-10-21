"""The Phase 3 measurement panel (Stage 1a).

Built from tracked fixtures only, with no network:

- the parent's raw roots `funding_inputs` (the published panel's inputs), `on_rrp_inputs`, `h8_inputs` and
  `srf_inputs`, parsed by the parent's own `ingest` at the pinned commit;
- this repository's H.4.1 first-print extract (`repo_liquidity.h41`);
- this repository's scheduled tables (`repo_liquidity.scheduled`).

Versions 2 and 3 also read the 2019 to 2021 repo operations through `repo_liquidity.fed_repo`, deleted on 12 October
2026 in favour of the parent's `repo_model.fed_liquidity` (`docs/decisions/data-meaning.md`). Their manifests are
development records: they are verified at the commit and parent pin they were made from (`scripts/verify_records.py`),
and this module no longer builds them. Version 1 is a record too since the pin moved to 08ff67e (#149): the parent's
Desk test-trade rule changed 391 of its `srf_take_up` rows, so the same build now gives version 4
(`docs/stages/panel-v4.md`).

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
#: The Stage 1a correction's panel (`docs/stages/stage-1a-correction.md`). Version 1 is kept byte for byte, because
#: the Stage 2, 3 and 3b records name its digest.
MANIFEST_V2 = ROOT / "metadata" / "phase3_panel_v2_manifest.json"
#: Stage 1b's panel (`docs/stages/stage-1b.md`): version 2 plus the first-wave indicators.
MANIFEST_V3 = ROOT / "metadata" / "phase3_panel_v3_manifest.json"
#: Version 1's build at the pin of 08ff67e (#149; Eleonora, 21 October 2026, "publish the panel as a new version"): the
#: same columns and dates. The parent's Desk test-trade rule (its #933) moved 391 `srf_take_up` rows
#: (`results/panel/v4_changes.json`), so version 1 no longer rebuilds at this pin and stays as published. The numbers 2
#: and 3 were taken by the Stage 1a correction and Stage 1b, so this is version 4.
MANIFEST_V4 = ROOT / "metadata" / "phase3_panel_v4_manifest.json"
MANIFESTS = {1: MANIFEST, 2: MANIFEST_V2, 3: MANIFEST_V3, 4: MANIFEST_V4}
#: The versions kept only as records (see the module docstring).
RECORD_VERSIONS = (1, 2, 3)
#: The version the readers build at the current pin.
CURRENT_VERSION = 4
H41_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_treasury_first_print.csv"
H41_MBS_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_mbs_first_print.csv"
PARENT_RAW_ROOTS = ("funding_inputs", "on_rrp_inputs", "h8_inputs", "srf_inputs")


@contextmanager
def _weekly_carry():
    """Carry the weekly H.4.1 column forward as the parent carries its weekly columns (at most 13 days)."""
    from repo_model import data

    saved = data.CARRY_FORWARD_COLUMNS
    data.CARRY_FORWARD_COLUMNS = MappingProxyType(
        {**saved, h41.SERIES: data.WEEKLY_CARRY_MAX_STALENESS_DAYS,
         h41.MBS_SERIES: data.WEEKLY_CARRY_MAX_STALENESS_DAYS})
    try:
        yield
    finally:
        data.CARRY_FORWARD_COLUMNS = saved


def _parent_rows(workdir: Path, roots=PARENT_RAW_ROOTS):
    from repo_model.data import load_point_in_time_panel
    from repo_model.ingest import build_point_in_time_snapshot, load_snapshot_manifest

    snapshots = parent_root() / "tests" / "fixtures" / "snapshots"
    artifacts = [
        load_snapshot_manifest(path)
        for root in roots
        for path in sorted((snapshots / root).glob("*/*.manifest.json"))
    ]
    long_path = workdir / "phase3_point_in_time.csv"
    snapshot = build_point_in_time_snapshot(
        artifacts, long_path, registry_path=parent_root() / "metadata" / "sources.json")
    retrieved = {artifact.sha256: artifact.retrieved_at for artifact in artifacts}
    return load_point_in_time_panel(long_path), snapshot, retrieved


def build(output: Path, version: int) -> Dict:
    """Build the panel to `output` (CSV) and return its manifest.

    Version 4 is Stage 1a's panel (version 1) built at the pin of 08ff67e. Versions 1 to 3 are records only
    (`RECORD_VERSIONS`): version 1 is verified at the commit and parent pin it was made from, and a rebuild at this
    pin is version 4, not version 1.

    Raises:
        ValueError: for a version that is not built here, if the published columns do not reproduce the parent's
            digest, if a Phase 3 column is refused, or if the dates differ from the published panel's.
    """
    from repo_model.data import build_daily_panel, verify_daily_panel, write_daily_panel

    if version in RECORD_VERSIONS:
        raise ValueError(f"panel version {version} is a record; it is verified at the commit and parent pin it was "
                         "made from (scripts/verify_records.py), and a rebuild at this pin is version "
                         f"{CURRENT_VERSION}")
    if version not in MANIFESTS:
        raise ValueError(f"the panel has versions {sorted(MANIFESTS)}, not {version!r}")

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

    built_columns = declaration.BUILT_COLUMNS
    extract_sha = hashlib.sha256(H41_EXTRACT.read_bytes()).hexdigest()
    extra_rows = h41.observations(h41.load_extract(H41_EXTRACT), source_sha=extract_sha)

    with declaration.phase3_declaration(), _weekly_carry():
        phase3 = build_daily_panel(list(rows) + extra_rows, declaration.registry(), build_cutoff=cutoff,
                                   decision_time=decision, columns=published_columns + built_columns,
                                   snapshot_retrieved_at=retrieved)
    if phase3.refusals:
        raise ValueError(f"the Phase 3 build refused {dict(phase3.refusals)}")
    if [row.date for row in phase3.observations] != [row.date for row in published.observations]:
        raise ValueError("the Phase 3 panel's dates are not the published panel's")

    observations = scheduled.with_scheduled(phase3.observations, decision_time=decision)
    phase3_columns = list(built_columns) + list(declaration.SCHEDULED_COLUMNS)
    columns = list(published_columns) + phase3_columns
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
        "phase3_columns": phase3_columns,
        "coverage": _coverage(observations, phase3_columns),
        "holes": {column: phase3.holes.get(column, 0) for column in built_columns},
        "refusals": dict(phase3.refusals),
        "sha256": digest,
        "version": version,
        "v1_sha256": load_manifest(1)["sha256"],
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


def write_manifest(manifest: Dict, version: int) -> None:
    MANIFESTS[version].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(version: int) -> Dict:
    return json.loads(MANIFESTS[version].read_text(encoding="utf-8"))
