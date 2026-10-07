"""The Stage 4 freeze holds (`docs/decisions/stage-4-freeze.md`, `scripts/stage4_freeze.py`).

The declaration's checksum must equal the one pinned in the decision record. A change to any frozen definition, to the
fold settings, to the frozen rows of a rate table, to the overlay or to the package pins moves it; a row appended to a
rate table after an FOMC does not.
"""

import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "decisions" / "stage-4-freeze.md"


def _freeze():
    spec = importlib.util.spec_from_file_location("stage4_freeze", ROOT / "scripts" / "stage4_freeze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned(field):
    found = re.findall(rf"^- \*\*{re.escape(field)}:\*\* `([^`]+)`", RECORD.read_text(encoding="utf-8"), re.MULTILINE)
    if len(found) != 1:
        raise AssertionError(f"{field!r} is pinned {len(found)} times in {RECORD.name}, not once")
    return found[0]


class Stage4FreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.freeze = _freeze()

    def _copy(self, tmp):
        for path in [p for p, _ in self.freeze.SOURCE] + list(self.freeze.RATE_TABLES) + [
                self.freeze.OVERLAY, self.freeze.PANEL_MANIFEST, "pyproject.toml"]:
            target = Path(tmp) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        return Path(tmp)

    def test_the_declaration_matches_the_pinned_checksum(self):
        self.assertEqual(self.freeze.checksum(), _pinned("Declaration checksum"))

    def test_an_edited_definition_moves_the_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._copy(tmp)
            self.assertEqual(self.freeze.checksum(repo), _pinned("Declaration checksum"))
            path = repo / "src" / "repo_liquidity" / "curve_feature.py"
            text = path.read_text(encoding="utf-8")
            self.assertIn("        if b < 0:\n", text)
            path.write_text(text.replace("        if b < 0:\n", "        if b < -1e-12:\n", 1), encoding="utf-8")
            self.assertNotEqual(self.freeze.checksum(repo), _pinned("Declaration checksum"))

    def test_an_edited_frozen_rate_row_moves_the_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._copy(tmp)
            path = repo / self.freeze.RATE_TABLES[0]
            path.write_text(path.read_text(encoding="utf-8").replace(",1.75,", ",1.70,", 1), encoding="utf-8")
            self.assertNotEqual(self.freeze.checksum(repo), _pinned("Declaration checksum"))

    def test_an_appended_rate_row_leaves_the_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._copy(tmp)
            for table in self.freeze.RATE_TABLES:
                path = repo / table
                last = path.read_text(encoding="utf-8").splitlines()[-1]
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(last.replace("2026-09-1", "2099-09-1") + "\n")
            self.assertEqual(self.freeze.checksum(repo), _pinned("Declaration checksum"))

    def test_a_changed_setting_moves_the_checksum(self):
        from repo_liquidity import curve_feature

        saved = curve_feature.REFIT_EVERY
        try:
            curve_feature.REFIT_EVERY = saved + 1
            self.assertNotEqual(self.freeze.checksum(), _pinned("Declaration checksum"))
        finally:
            curve_feature.REFIT_EVERY = saved

    def test_the_freeze_covers_the_carry_rule_and_the_constrained_fit(self):
        hashed = self.freeze.source_sha256()["src/repo_liquidity/curve_feature.py"]
        for name in ("_refit_curve", "fit_constrained", "require_on_or_before", "require_as_of", "feature_value",
                     "with_training_feature", "CURVE_READS"):
            self.assertIn(name, hashed)


if __name__ == "__main__":
    unittest.main()
