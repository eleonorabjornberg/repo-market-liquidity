"""The parent is importable at the pinned commit, and its as-of guard is the one in use.

Checked once per run, against the parent the suite actually imports:

- its source tree is a clean checkout of `PARENT_COMMIT`;
- `pyproject.toml` pins the same commit;
- the panel, rebuilt by the parent from its tracked fixtures, has the published digest.

The parent reads its `metadata/` relative to its own source tree, so it is installed
editable from a checkout at the pin (see the CI workflow), never copied here.
"""

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest

import repo_liquidity

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The parent's published build of its panel (its REPRODUCIBILITY.md).
BUILD_ARGS = (
    "--raw-root", "tests/fixtures/snapshots/funding_inputs",
    "--registry", "metadata/sources.json",
    "--build-cutoff", "2026-09-08T21:31:42+00:00",
    "--decision-time", "16:00:00",
)


def parent_root():
    import repo_model

    return pathlib.Path(repo_model.__file__).resolve().parents[2]


def git(*args):
    return subprocess.run(
        ["git", "-C", str(parent_root()), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


class ParentPinTests(unittest.TestCase):
    def test_the_parent_package_imports(self):
        import repo_model.asof  # noqa: F401

    def test_the_pin_is_one_full_commit(self):
        self.assertRegex(repo_liquidity.PARENT_COMMIT, r"^[0-9a-f]{40}$")
        self.assertRegex(repo_liquidity.PANEL_SHA256, r"^[0-9a-f]{64}$")

    def test_the_imported_parent_is_a_clean_checkout_of_the_pin(self):
        root = parent_root()
        self.assertTrue(
            (root / ".git").exists(),
            f"repo_model is imported from {root}, which is not a checkout of the parent; "
            "install it editable from a checkout at PARENT_COMMIT",
        )
        self.assertEqual(git("rev-parse", "HEAD"), repo_liquidity.PARENT_COMMIT)
        self.assertEqual(git("status", "--porcelain", "--untracked-files=no"), "")

    def test_pyproject_pins_the_same_commit(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        (parent,) = [d for d in project["dependencies"] if d.startswith("repo-market-model")]
        self.assertTrue(parent.endswith("@" + repo_liquidity.PARENT_COMMIT), parent)

    def test_the_panel_rebuilds_to_the_published_digest(self):
        root = parent_root()
        manifest = json.loads((root / "metadata" / "funding_panel_manifest.json").read_text())
        self.assertEqual(manifest["sha256"], repo_liquidity.PANEL_SHA256)
        with tempfile.TemporaryDirectory() as tmp:
            panel = pathlib.Path(tmp) / "funding_panel.csv"
            subprocess.run(
                [sys.executable, "-B", "-m", "repo_model.cli", "build", *BUILD_ARGS, "--output", str(panel)],
                cwd=root, check=True, capture_output=True, text=True,
            )
            self.assertEqual(hashlib.sha256(panel.read_bytes()).hexdigest(), repo_liquidity.PANEL_SHA256)


if __name__ == "__main__":
    unittest.main()
