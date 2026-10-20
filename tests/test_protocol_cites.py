"""The measurement protocol's cites into the parent resolve at the pin, so a cite cannot go stale silently.

`docs/decisions/measurement-protocol.md` cites parent code as `file.py:line` (R at `scarcity.py:161`, S at
`scarcity.py:194`). At the pin (`PARENT_COMMIT`) each such cite must name a file that exists and a line that opens a
`def` or `class`. A cite the protocol itself lists as superseded in its amendment section is the one exception: the
stress event's `fed_liquidity.py:163` was never a definition (finding #75, directive #124), and the amendment points
the event at `data-meaning.md` answer 14 and `goalposts.is_material_use`, which this file checks exist.

Recorded mutation (directive #124): `scarcity.py:194` changed to `scarcity.py:195` in the protocol's section 2 made
`CitesResolveTests.test_each_cite_opens_a_definition` fail with AssertionError (line 195 is a parameter line, not a def).
A second, on the exception: the amendment's "Superseded cite" label renamed made the same test fail with AssertionError
for `fed_liquidity.py:163`.
"""

import pathlib
import re
import unittest

import repo_liquidity
from repo_liquidity import goalposts

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "decisions" / "measurement-protocol.md"
DATA_MEANING = ROOT / "docs" / "decisions" / "data-meaning.md"

CITE = re.compile(r"`(?:repo_model/)?([a-z_0-9]+\.py):(\d+)`")
SUPERSEDED = re.compile(r"^- \*\*Superseded cite:\*\*(.*)$", re.MULTILINE)


def _parent_module(name):
    return repo_liquidity.parent_root() / "src" / "repo_model" / name


def _superseded(text):
    return {m.group(0) for line in SUPERSEDED.findall(text) for m in CITE.finditer(line)}


class CitesResolveTests(unittest.TestCase):
    def setUp(self):
        self.text = PROTOCOL.read_text(encoding="utf-8")

    def test_cites_exist(self):
        self.assertGreaterEqual(len(CITE.findall(self.text)), 3)

    def test_each_cite_opens_a_definition(self):
        superseded = _superseded(self.text)
        for m in CITE.finditer(self.text):
            if m.group(0) in superseded:
                continue
            name, line = m.group(1), int(m.group(2))
            path = _parent_module(name)
            self.assertTrue(path.is_file(), f"{name} does not exist in the parent at the pin")
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(line, len(lines), f"{name}:{line} is past the end of the file")
            self.assertRegex(lines[line - 1], r"^(def|class) ", f"{name}:{line} is not a definition: {lines[line - 1]!r}")


class AmendedEventTests(unittest.TestCase):
    def test_the_event_is_defined_where_the_amendment_says(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("goalposts.is_material_use", text)
        self.assertTrue(callable(goalposts.is_material_use))
        self.assertTrue(goalposts.is_material_use(1.0))
        self.assertFalse(goalposts.is_material_use(0.99))
        self.assertRegex(DATA_MEANING.read_text(encoding="utf-8"), r"(?m)^\| 14 \| 2019–21 term repos")


if __name__ == "__main__":
    unittest.main()
