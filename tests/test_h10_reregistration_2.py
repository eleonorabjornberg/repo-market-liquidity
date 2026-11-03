"""H10's second re-registration, prepared at the post-#1312 parent pin (#200; Eleonora's rulings of 29 October 2026).

`docs/research/h10-reregistration-2.md` states the method digest at the tree this module runs in, the digest registered on #23
on 22 October 2026 (`43bf1303...15bb`), the digest's parts and the sha256 of each part at both, and the decision instant. This
module checks the page against the tree. It registers nothing: the registration is Eleonora's attested act on #23, and until she
makes it the registration of 22 October stands (`repo_liquidity.h10_registration`).

The guards are consistency guards (the page cannot state a digest the code does not give, nor an instant the code does not
use), not leakage or availability guards. Recorded mutations (30 October 2026, CPython 3.11, the parent at 2032de4, applied in the
working tree and reverted):

* in `src/repo_liquidity/h10_apply.py`, `DECISION_TIME = time(18, 0)` changed to `DECISION_TIME = time(17, 0)`: four tests failed with
  `AssertionError`: `test_the_new_digest_in_the_page_is_the_one_the_code_gives_at_the_pin` (the digest moved),
  `test_each_part_in_the_page_is_the_sha256_of_the_part_at_the_pin`, `test_the_paste_ready_text_carries_the_commit_the_digest_the_pin_and_the_instant`
  and `test_the_page_states_the_decision_instant_the_code_uses` (`time(17, 0) != time(18, 0)`).
* the same file, `REPORT_DAYS = 10` changed to `REPORT_DAYS = 11`: three tests failed with `AssertionError`: the digest, the parts and the paste-ready text.
"""

import hashlib
import pathlib
import re
import unittest
from datetime import time
from unittest import mock

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, h10_apply, h10_live, h10_registration, panel

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "research" / "h10-reregistration-2.md"
OLD_PIN = "08ff67e27bc3d7e357491cf8e1da59793702b3fb"
OLD_DIGEST = "43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb"


def stated(label: str) -> str:
    """The backticked 64-hex value in the page's table row that starts with `label`."""
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|\s*`([0-9a-f]{64})`", text, re.MULTILINE)
    assert match, f"the page has no row {label!r}"
    return match.group(1)


def parts_table() -> dict:
    """The page's parts table: part (without the pin) -> (sha256 as registered, sha256 at the new pin). A parts row is one
    whose second and third cells are both backticked hashes."""
    rows = {}
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("`") and re.fullmatch(r"`[0-9a-f]{64}`", cells[1]) \
                and re.fullmatch(r"`[0-9a-f]{64}`", cells[2]):
            rows[cells[0].strip("`")] = (cells[1].strip("`"), cells[2].strip("`"))
    return rows


class PageStatesTheDigestTests(unittest.TestCase):
    def test_the_new_digest_in_the_page_is_the_one_the_code_gives_at_the_pin(self):
        self.assertEqual(stated("method_digest() at the new pin"), h10_live.method_digest())

    def test_the_registered_digest_in_the_page_is_the_one_h10_registration_holds_and_differs(self):
        self.assertEqual(stated("method_digest() as registered on #23, 22 October 2026"), OLD_DIGEST)
        self.assertEqual(OLD_DIGEST, h10_registration.REGISTERED_DIGEST)
        self.assertNotEqual(OLD_DIGEST, h10_live.method_digest())

    def test_the_page_names_both_pins_and_the_panel_digests(self):
        text = PAGE.read_text(encoding="utf-8")
        for needle in (PARENT_COMMIT, OLD_PIN, PANEL_SHA256, panel.load_manifest(panel.CURRENT_VERSION)["sha256"],
                       panel.load_manifest(4)["sha256"]):
            self.assertIn(needle, text)

    def test_each_part_in_the_page_is_the_sha256_of_the_part_at_the_pin(self):
        table = parts_table()
        parts = h10_live.method_parts()
        self.assertEqual(len(table), len(parts))
        for name, content in parts:
            key = name.split(":", 1)[1] if ":" in name else name
            key = key.replace(f"parent@{PARENT_COMMIT}:", "")
            self.assertEqual(table[key][1], hashlib.sha256(content).hexdigest(), name)

    def test_the_page_says_which_parts_changed_since_the_registration(self):
        changed = sorted(key for key, (old, new) in parts_table().items() if old != new)
        self.assertEqual(changed, sorted([
            "src/repo_liquidity/attribution.py", "src/repo_liquidity/h10_apply.py", "src/repo_liquidity/h10_live.py", "src/repo_model/onset.py",
            "src/repo_model/asof.py", "constants"]))

    def test_the_record_part_is_the_method_record_registered_on_23(self):
        self.assertEqual(stated("record_sha256()"), h10_live.record_sha256())

    def test_the_page_states_the_decision_instant_the_code_uses(self):
        """The one line is `h10_apply.DECISION_TIME`; the page says its value, and the constants part of the digest carries it."""
        self.assertEqual(h10_apply.DECISION_TIME, time(18, 0))
        self.assertIn("DECISION_TIME = time(18, 0)", PAGE.read_text(encoding="utf-8"))
        self.assertEqual(h10_live.decided_constants()["decision_time"], "18:00:00")
        with mock.patch.object(h10_apply, "DECISION_TIME", time(17, 0)):
            self.assertEqual(h10_live.decided_constants()["decision_time"], "17:00:00")
            self.assertNotEqual(stated("method_digest() at the new pin"), h10_live.method_digest())

    def test_the_decision_instant_is_the_one_line_the_other_readings_follow(self):
        """`h10_apply.real_rule` and the record settings read `DECISION_TIME`; none restates the clock."""
        source = (ROOT / "src" / "repo_liquidity" / "h10_apply.py").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"time\(\s*1[0-9]\s*,", source)), 1)
        live = (ROOT / "src" / "repo_liquidity" / "h10_live.py").read_text(encoding="utf-8")
        self.assertNotRegex(live, r"time\(\s*1[0-9]\s*,")

    def test_the_paste_ready_text_carries_the_commit_the_digest_the_pin_and_the_instant(self):
        paste = PAGE.read_text(encoding="utf-8").split("## The registration text", 1)[1]
        for needle in (h10_live.method_digest(), PARENT_COMMIT, PANEL_SHA256, h10_live.record_sha256(), "18:00",
                       "new declaration", OLD_DIGEST):
            self.assertIn(needle, paste)

    def test_a_changed_covered_file_makes_the_page_stale(self):
        """If a value the digest covers changes, the digest the page states no longer matches, so the page cannot be merged
        stale. This test shows the same in-process for `REPORT_DAYS`; the recorded mutations are in the module docstring."""
        with mock.patch.object(h10_apply, "REPORT_DAYS", 11):
            with self.assertRaises(AssertionError):
                self.assertEqual(stated("method_digest() at the new pin"), h10_live.method_digest())


if __name__ == "__main__":
    unittest.main()
