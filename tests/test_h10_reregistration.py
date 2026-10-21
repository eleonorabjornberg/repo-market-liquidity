"""H10's re-registration at the new parent pin (#152; Eleonora's ruling on #149, 20 October 2026, option 2).

`docs/research/h10-reregistration.md` states the method digest at the pin the repository is at, the digest it replaces, the
digest's parts and the sha256 of each part. This module checks the record against the tree. It registers nothing: the
registration is Eleonora's attested act on #23, and until she makes it H10's registration at 8fd2cf8 (digest `cc7bab6e...49b1`)
stands.

The guard here is a consistency guard (the record cannot state a digest the code does not give), not a leakage or
availability guard; its one recorded mutation is in `test_a_changed_covered_file_makes_the_record_stale`.
"""

import hashlib
import pathlib
import re
import unittest
from unittest import mock

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, h10_apply, h10_live

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "research" / "h10-reregistration.md"
OLD_PIN = "8fd2cf8c72e7d5c6e81c509651b684b690054a6f"
OLD_DIGEST = "cc7bab6ea31ef51c839b17b237a8b92bd12afa60c191fe91f15d33286a1249b1"


def stated(label: str) -> str:
    """The backticked 64-hex value in the record's table row that starts with `label`."""
    text = RECORD.read_text(encoding="utf-8")
    match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|\s*`([0-9a-f]{64})`", text, re.MULTILINE)
    assert match, f"the record has no row {label!r}"
    return match.group(1)


def parts_table() -> dict:
    """The record's parts table: part (without the pin) -> (sha256 at 8fd2cf8, sha256 at the new pin). The parts' rows are the
    ones whose second and third cells are both backticked hashes."""
    rows = {}
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("`") and re.fullmatch(r"`[0-9a-f]{64}`", cells[1]) and re.fullmatch(r"`[0-9a-f]{64}`", cells[2]):
            rows[cells[0].strip("`")] = (cells[1].strip("`"), cells[2].strip("`"))
    return rows


class RecordStatesTheDigestTests(unittest.TestCase):
    def test_the_new_digest_in_the_record_is_the_one_the_code_gives_at_the_pin(self):
        self.assertEqual(stated("method_digest() at the new pin"), h10_live.method_digest())

    def test_the_old_digest_in_the_record_is_the_registered_one_and_differs(self):
        self.assertEqual(stated("method_digest() at 8fd2cf8, registered on #23"), OLD_DIGEST)
        self.assertNotEqual(OLD_DIGEST, h10_live.method_digest())

    def test_the_record_names_the_pin_and_the_panel_digest(self):
        text = RECORD.read_text(encoding="utf-8")
        self.assertIn(PARENT_COMMIT, text)
        self.assertIn(OLD_PIN, text)
        self.assertIn(PANEL_SHA256, text)

    def test_each_part_in_the_record_is_the_sha256_of_the_part_at_the_pin(self):
        table = parts_table()
        parts = h10_live.method_parts()
        self.assertEqual(len(table), len(parts))
        for name, content in parts:
            key = name.split(":", 1)[1] if ":" in name else name
            self.assertEqual(table[key][1], hashlib.sha256(content).hexdigest(), name)

    def test_the_record_says_which_parts_changed_between_the_pins(self):
        changed = sorted(key for key, (old, new) in parts_table().items() if old != new)
        self.assertEqual(changed, ["src/repo_liquidity/h10_apply.py"])

    def test_the_record_part_is_the_method_record_registered_on_23(self):
        self.assertEqual(stated("record_sha256()"), h10_live.record_sha256())

    def test_the_paste_ready_text_carries_the_commit_the_digest_and_the_pin(self):
        text = RECORD.read_text(encoding="utf-8")
        paste = text.split("## The registration text", 1)[1]
        for needle in (h10_live.method_digest(), PARENT_COMMIT, PANEL_SHA256, h10_live.record_sha256(), "new declaration"):
            self.assertIn(needle, paste)

    def test_a_changed_covered_file_makes_the_record_stale(self):
        """Killing check: if a file the digest covers changes, the digest the record states no longer matches, so the
        record cannot be merged stale. Recorded mutation (21 October 2026): in `src/repo_liquidity/h10_apply.py`, the line
        `REPORT_DAYS = 10` changed to `REPORT_DAYS = 11`; `test_the_new_digest_in_the_record_is_the_one_the_code_gives_at_the_pin`
        failed with AssertionError. This test shows the same in-process."""
        with mock.patch.object(h10_apply, "REPORT_DAYS", 11):
            with self.assertRaises(AssertionError):
                self.assertEqual(stated("method_digest() at the new pin"), h10_live.method_digest())


if __name__ == "__main__":
    unittest.main()
