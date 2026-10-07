#!/usr/bin/env python3
"""The Stage 4 freeze (`docs/stages/stage-4.md`, "After the run"): the declaration and its checksum.

    PYTHONPATH=src python3 scripts/stage4_freeze.py           # print the declaration's checksum
    PYTHONPATH=src python3 scripts/stage4_freeze.py --json    # print the declaration itself

The declaration is everything that decides a Stage 4 forecast:
- both arms' commands, as the parent's own code builds them;
- the declared features;
- the fold settings;
- the panel version and its digest;
- the parent pin and its panel digest;
- the package pins and the Stage 4 overlay;
- the source of every definition the forecasts reach, hashed definition by definition as the parent's final-test
  freeze hashes its own (`scripts/final_test_preregistration.py`, `_source_hashes`).

The two rate tables are extended after each FOMC by a reviewed pull request (Eleonora, 7 October 2026), so only their
rows at the freeze are hashed: a later row may be appended; an earlier one may not change.

The checksum is pinned in `docs/decisions/stage-4-freeze.md`, and `tests/test_stage4_freeze.py` refuses a tree whose
declaration no longer matches it. Standard library only.
"""

import ast
import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Tuple

REPO = Path(__file__).resolve().parents[1]

#: The definitions a Stage 4 forecast reaches, as `(repo-relative path, (root names,))`; each root's transitive
#: closure over the file's top-level definitions is hashed.
SOURCE = (
    ("src/repo_liquidity/curve_feature.py", ("CurveFeatureFitter", "CurveFeatureExceedance", "CurveFeatureModel",
                                             "published_arm", "published_exceedance_arm", "with_stage4_columns",
                                             "stage4_declaration", "registry", "curve_rule", "DECLARED_FEATURES",
                                             "PANEL_VERSION", "DECISION_TIME")),
    ("src/repo_liquidity/scheduled.py", ("load_iorb_rates", "load_on_rrp_rates", "iorb_in_force_values",
                                         "rate_in_force", "with_scheduled")),
    ("src/repo_liquidity/demand_curve.py", ("corridor_position", "GRID", "fit_broken_stick")),
    ("src/repo_liquidity/declaration.py", ("phase3_declaration", "registry", "merge", "FIELDS")),
    ("src/repo_liquidity/panel.py", ("build",)),
)
#: The rate tables, appended to after each FOMC: the rows at the freeze are fixed.
RATE_TABLES = ("tests/fixtures/snapshots/fomc_notes/iorb_rate.csv", "tests/fixtures/snapshots/fomc_notes/on_rrp_rate.csv")
#: The rows each table had at the freeze (header excluded).
RATE_TABLE_ROWS = {"tests/fixtures/snapshots/fomc_notes/iorb_rate.csv": 31,
                   "tests/fixtures/snapshots/fomc_notes/on_rrp_rate.csv": 32}
OVERLAY = "metadata/sources_stage4.json"
PANEL_MANIFEST = "metadata/phase3_panel_v3_manifest.json"


def _definitions(tree: ast.Module) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node
    return out


@lru_cache(maxsize=None)
def _source_hashes(text: str, roots: Tuple[str, ...]) -> Tuple[Tuple[str, str], ...]:
    """sha256 of each top-level definition reached from `roots`, by name.

    Raises:
        ValueError: if a root is not a top-level definition of the file.
    """
    tree = ast.parse(text)
    definitions = _definitions(tree)
    missing = [root for root in roots if root not in definitions]
    if missing:
        raise ValueError(f"not top-level definitions: {missing}")
    reached, queue = set(), list(roots)
    while queue:
        name = queue.pop()
        if name in reached:
            continue
        reached.add(name)
        for node in ast.walk(definitions[name]):
            if isinstance(node, ast.Name) and node.id in definitions and node.id not in reached:
                queue.append(node.id)
    return tuple(sorted((name, hashlib.sha256(ast.get_source_segment(text, definitions[name]).encode()).hexdigest())
                        for name in reached))


def source_sha256(repo: Path = REPO, source: Iterable = SOURCE) -> Dict[str, Dict[str, str]]:
    return {path: dict(_source_hashes((repo / path).read_text(encoding="utf-8"), tuple(roots)))
            for path, roots in source}


def rate_table_prefixes(repo: Path = REPO, rows: Dict[str, int] = None) -> Dict[str, Dict]:
    """Each rate table's header and first `rows[path]` rows, hashed; `rows` defaults to the frozen counts."""
    rows = RATE_TABLE_ROWS if rows is None else rows
    out = {}
    for path in RATE_TABLES:
        lines = (repo / path).read_text(encoding="utf-8").splitlines(keepends=True)
        count = rows[path]
        if count > len(lines) - 1:
            raise ValueError(f"{path} has {len(lines) - 1} rows, fewer than the {count} frozen")
        out[path] = {"rows": count, "sha256": hashlib.sha256("".join(lines[:count + 1]).encode()).hexdigest()}
    return out


def _relative(argv):
    from repo_liquidity import parent_root

    prefix = str(parent_root()) + "/"
    return [arg.replace(prefix, "PARENT/") for arg in argv]


def _extras(repo: Path) -> Dict[str, list]:
    import tomllib

    project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {"dependencies": project["dependencies"],
            "optional": {name: sorted(pins) for name, pins in project["optional-dependencies"].items()}}


def declaration(repo: Path = REPO) -> dict:
    from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, curve_feature

    return {
        "stage": "4",
        "model_a": {"model": "gbm", "features": list(curve_feature.PUBLISHED_FEATURES),
                    "command": _relative(curve_feature.published_command())},
        "model_b": {"model": "gbm_curve_implied_spread", "features": list(curve_feature.DECLARED_FEATURES),
                    "added_regressor": curve_feature.FEATURE,
                    "curve": "Stage 2's broken stick on corridor position, slope at or above 0, refit as of each refit",
                    "curve_failure": "carry the latest fitted curve; stop if none (amendment of 7 October 2026)"},
        "exceedance_command": _relative(curve_feature.published_exceedance_command()),
        "settings": {"minimum_history": curve_feature.MINIMUM_HISTORY, "refit_every": curve_feature.REFIT_EVERY,
                     "decision_time": curve_feature.DECISION_TIME.isoformat(timespec="minutes"), "horizon": 1},
        "panel": {"version": curve_feature.PANEL_VERSION,
                  "sha256": json.loads((repo / PANEL_MANIFEST).read_text(encoding="utf-8"))["sha256"]},
        "parent": {"commit": PARENT_COMMIT, "panel_sha256": PANEL_SHA256},
        "packages": _extras(repo),
        "overlay_sha256": hashlib.sha256((repo / OVERLAY).read_bytes()).hexdigest(),
        "rate_tables": rate_table_prefixes(repo),
        "source_sha256": source_sha256(repo),
    }


def checksum(repo: Path = REPO) -> str:
    return hashlib.sha256(json.dumps(declaration(repo), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    if "--json" in sys.argv[1:]:
        print(json.dumps(declaration(), indent=1, sort_keys=True))
    else:
        print(checksum())
