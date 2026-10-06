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

from repo_liquidity import declaration, fed_repo, h41, indicators, parent_root, scheduled

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "metadata" / "phase3_panel_manifest.json"
#: The Stage 1a correction's panel (`docs/stages/stage-1a-correction.md`). Version 1 is kept byte for byte, because
#: the Stage 2, 3 and 3b records name its digest.
MANIFEST_V2 = ROOT / "metadata" / "phase3_panel_v2_manifest.json"
#: Stage 1b's panel (`docs/stages/stage-1b.md`): version 2 plus the first-wave indicators.
MANIFEST_V3 = ROOT / "metadata" / "phase3_panel_v3_manifest.json"
MANIFESTS = {1: MANIFEST, 2: MANIFEST_V2, 3: MANIFEST_V3}
H41_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_treasury_first_print.csv"
H41_MBS_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h41" / "h41_mbs_first_print.csv"
PARENT_RAW_ROOTS = ("funding_inputs", "on_rrp_inputs", "h8_inputs", "srf_inputs")
#: Stage 1b reads the parent's EFFR snapshots too; earlier versions do not, so their builds are unchanged.
PARENT_RAW_ROOTS_V3 = PARENT_RAW_ROOTS + ("nyfed_effr_inputs",)


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


def build(output: Path, version: int = 1) -> Dict:
    """Build the panel to `output` (CSV) and return its manifest.

    Version 1 is Stage 1a's panel. Version 2 adds the Stage 1a correction's columns: the weekly MBS change, the
    2019 to 2021 temporary repo operations, and the derived repo take-up, its facility and the material-use event.

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
        rows, snapshot, retrieved = _parent_rows(workdir, PARENT_RAW_ROOTS_V3 if version >= 3 else PARENT_RAW_ROOTS)
        parent_registry = declaration.parent_registry()

        published = build_daily_panel(rows, parent_registry, build_cutoff=cutoff, decision_time=decision,
                                      columns=published_columns, snapshot_retrieved_at=retrieved)
        published_path = workdir / "published_columns.csv"
        write_daily_panel(published, published_path, source_shas=snapshot.source_shas)
        parent_digest = verify_daily_panel(published_path, published_manifest_path)

    if version not in MANIFESTS:
        raise ValueError(f"the panel has versions {sorted(MANIFESTS)}, not {version!r}")
    built_columns = {1: declaration.BUILT_COLUMNS, 2: declaration.BUILT_COLUMNS_V2,
                     3: declaration.BUILT_COLUMNS_V3}[version]
    extract_sha = hashlib.sha256(H41_EXTRACT.read_bytes()).hexdigest()
    extra_rows = h41.observations(h41.load_extract(H41_EXTRACT), source_sha=extract_sha)
    v2_shas = {}
    if version >= 2:
        mbs_sha = hashlib.sha256(H41_MBS_EXTRACT.read_bytes()).hexdigest()
        extra_rows += h41.observations(h41.load_extract(H41_MBS_EXTRACT), source_sha=mbs_sha, series=h41.MBS_SERIES)
        operations, repo_sha = fed_repo.load_snapshots()
        for term, series in (("Overnight", fed_repo.SERIES), ("Term", fed_repo.TERM_SERIES)):
            extra_rows += fed_repo.observations(fed_repo.daily_take_up(operations, term=term), series=series,
                                                source_sha=repo_sha)
        extra_rows += fed_repo.observations(fed_repo.term_outstanding(operations),
                                            series=fed_repo.TERM_OUTSTANDING_SERIES, source_sha=repo_sha)
        v2_shas = {"h41_mbs_extract_sha256": mbs_sha, "temp_repo_snapshots_sha256": repo_sha}

    with declaration.phase3_declaration(), _weekly_carry():
        phase3 = build_daily_panel(list(rows) + extra_rows, declaration.registry(), build_cutoff=cutoff,
                                   decision_time=decision, columns=published_columns + built_columns,
                                   snapshot_retrieved_at=retrieved)
    if phase3.refusals:
        raise ValueError(f"the Phase 3 build refused {dict(phase3.refusals)}")
    if [row.date for row in phase3.observations] != [row.date for row in published.observations]:
        raise ValueError("the Phase 3 panel's dates are not the published panel's")

    observations = scheduled.with_scheduled(phase3.observations, decision_time=decision)
    derived_columns = []
    if version >= 2:
        observations = _with_repo_take_up(observations)
        derived_columns = list(declaration.DERIVED_COLUMNS_V2)
    if version >= 3:
        observations = indicators.with_indicators(observations)
        derived_columns += list(indicators.COLUMNS)
    phase3_columns = list(built_columns) + list(declaration.SCHEDULED_COLUMNS) + derived_columns
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
    }
    if version >= 2:
        manifest.update(v2_shas, version=version, v1_sha256=_v1_digest())
    if version >= 3:
        manifest.update(v2_sha256=json.loads(MANIFEST_V2.read_text(encoding="utf-8"))["sha256"],
                        measurement_breaks={day: list(columns)
                                            for day, columns in indicators.MEASUREMENT_BREAKS.items()})
    return manifest


def _v1_digest() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["sha256"]


def _with_repo_take_up(observations):
    """Each row with the derived repo take-up, its facility, and the material-use events (standing facility, and all
    Fed repo operations from the start)."""
    from repo_model.data import DailyObservation

    out = []
    for row in observations:
        take_up, facility = fed_repo.combined({"date": row.date, **row.values})
        values = dict(row.values, fed_repo_take_up=take_up, fed_repo_facility=facility,
                      srf_material_use=fed_repo.material_use(row.values.get("srf_take_up")),
                      fed_repo_material_use=fed_repo.repo_material_use({"date": row.date, **row.values}))
        out.append(DailyObservation(date=row.date, values=values))
    return out


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


def write_manifest(manifest: Dict, version: int = 1) -> None:
    MANIFESTS[version].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(version: int = 1) -> Dict:
    return json.loads(MANIFESTS[version].read_text(encoding="utf-8"))
