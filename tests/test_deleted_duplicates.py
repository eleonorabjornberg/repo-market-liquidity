"""The duplicates of repo-market-model are deleted, and nothing here reaches for them (`docs/decisions/deleted-duplicates.md`).

Eleonora, 12 October 2026 (repo-market-model#643): "the liquidity repo ingests its own data, and duplicates are deleted
in favour of this repo." The Fed repo operations are read from `repo_model.fed_liquidity` and the IORB notes from
`repo_model.announced_iorb`, at the pin. The files are gone; the importers are found with an AST walk, so relative and
multi-line imports count.
"""

import ast
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DELETED_FILES = (
    "src/repo_liquidity/fed_repo.py",
    "tests/test_fed_repo.py",
    "scripts/fetch_temp_repo.py",
    "tests/fixtures/snapshots/nyfed_temp_repo",
    "tests/fixtures/snapshots/fomc_notes/iorb_rate.csv",
    "tests/fixtures/snapshots/fomc_notes/iorb_rate.csv.manifest.json",
    # The one saved page only the IORB table cited (the 1 May 2019 note); the parent keeps its own pages.
    "tests/fixtures/snapshots/fomc_notes/pages/monetary20190501a1.htm.gz",
)
#: Stage 5a's schedule, retired (repo-market-model#643, S3); `live.py` and `scripts/stage5a_log.py` stay as the record.
RETIRED_FILES = (".github/workflows/live-log.yml",)
#: `scheduled.py`'s IORB part, replaced by `repo_model.announced_iorb`.
DELETED_SCHEDULED_NAMES = ("IORB_RATE_TABLE", "IORB_COLUMN", "load_iorb_rates", "iorb_in_force_values")


def _python_files():
    for directory in ("src", "scripts", "tests"):
        yield from sorted((ROOT / directory).rglob("*.py"))


def _reaches_a_deleted_name(path: Path):
    """Each line of `path` that imports `fed_repo` or reads one of `scheduled`'s deleted IORB names."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[-1] == "fed_repo" for alias in node.names):
                found.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")
            if module[-1] == "fed_repo" or any(alias.name == "fed_repo" for alias in node.names):
                found.append(node.lineno)
            if module[-1] == "scheduled" and any(alias.name in DELETED_SCHEDULED_NAMES for alias in node.names):
                found.append(node.lineno)
        elif (isinstance(node, ast.Attribute) and node.attr in DELETED_SCHEDULED_NAMES
              and isinstance(node.value, ast.Name) and node.value.id == "scheduled"):
            found.append(node.lineno)
    return found


class DeletedDuplicateTests(unittest.TestCase):
    def test_the_deleted_files_are_gone(self):
        self.assertEqual([path for path in DELETED_FILES + RETIRED_FILES if (ROOT / path).exists()], [])
        self.assertTrue((ROOT / "src" / "repo_liquidity" / "live.py").exists())
        self.assertTrue((ROOT / "scripts" / "stage5a_log.py").exists())

    def test_fed_repo_is_not_importable(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("repo_liquidity.fed_repo")

    def test_scheduled_keeps_its_rates_and_caps_but_not_iorb(self):
        from repo_liquidity import scheduled

        self.assertEqual([name for name in DELETED_SCHEDULED_NAMES if hasattr(scheduled, name)], [])
        for name in ("load_srf_rates", "load_on_rrp_rates", "load_runoff_caps", "with_scheduled"):
            self.assertTrue(callable(getattr(scheduled, name)), name)

    def test_nothing_reaches_a_deleted_name(self):
        """Recorded mutation (12 October 2026): `from repo_liquidity import fed_repo  # noqa` added as the last line
        of `src/repo_liquidity/panel.py`. This test failed with AssertionError naming `src/repo_liquidity/panel.py`
        and that line."""
        found = {str(path.relative_to(ROOT)): lines for path in _python_files()
                 if path.name != Path(__file__).name and (lines := _reaches_a_deleted_name(path))}
        self.assertEqual(found, {})

    def test_the_successors_are_the_models(self):
        from repo_model import announced_iorb, fed_liquidity

        self.assertTrue(callable(fed_liquidity.assemble))
        self.assertTrue(callable(announced_iorb.load_announcements))


if __name__ == "__main__":
    unittest.main()
