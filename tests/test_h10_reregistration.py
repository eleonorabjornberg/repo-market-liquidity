"""H10's re-registration at the new parent pin (#152; Eleonora's ruling on #149, 20 October 2026, option 2).

`docs/research/h10-reregistration.md` states the method digest at the pin the repository is at, the digest it replaces, the
digest's parts and the sha256 of each part. This module checks the record against the tree. It registers nothing: the
registration is Eleonora's attested act on #23, and until she makes it H10's registration at 8fd2cf8 (digest `cc7bab6e...49b1`)
stands.

**Since #200** the page is the record of the registration of 22 October 2026 (digest `43bf1303...15bb`, the parent at `08ff67e`),
which Eleonora made on #23. It is not edited. The tree moved to the post-#1312 pin and to 18:00, so its digest is no longer the
one the code gives at head: this module checks the page against the registered digest (`h10_registration`), not against
`h10_live.method_digest()`. The page for the next registration, and its checks against the code at head, are
`docs/research/h10-reregistration-2.md` and `tests/test_h10_reregistration_2.py`.

The guard here is a consistency guard on a closed record, not a leakage or availability guard. The check that a changed covered
file makes a page stale, with its recorded mutation, moved to `tests/test_h10_reregistration_2.py`.
"""

import pathlib
import re
import unittest

from repo_liquidity import h10_registration

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "research" / "h10-reregistration.md"
OLD_PIN = "8fd2cf8c72e7d5c6e81c509651b684b690054a6f"
#: The pin and the Phase 3 panel the page was written at (the registration of 22 October 2026).
PAGE_PIN = h10_registration.REGISTERED_PARENT
PAGE_PANEL_SHA256 = "4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999"
REGISTERED_RECORD_SHA256 = "642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9"
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
    def test_the_digest_in_the_record_is_the_registered_one(self):
        self.assertEqual(stated("method_digest() at the new pin"), h10_registration.REGISTERED_DIGEST)

    def test_the_old_digest_in_the_record_is_the_one_registered_on_19_october_and_differs(self):
        self.assertEqual(stated("method_digest() at 8fd2cf8, registered on #23"), OLD_DIGEST)
        self.assertNotEqual(OLD_DIGEST, h10_registration.REGISTERED_DIGEST)

    def test_the_record_names_the_pin_and_the_panel_digest_it_was_written_at(self):
        text = RECORD.read_text(encoding="utf-8")
        self.assertIn(PAGE_PIN, text)
        self.assertIn(OLD_PIN, text)
        self.assertIn(PAGE_PANEL_SHA256, text)

    def test_the_record_says_which_parts_changed_between_the_pins(self):
        changed = sorted(key for key, (old, new) in parts_table().items() if old != new)
        self.assertEqual(changed, ["src/repo_liquidity/h10_apply.py"])
        self.assertEqual(parts_table()["docs/decisions/h10-method.md"][1], REGISTERED_RECORD_SHA256)

    def test_the_record_part_is_the_method_record_registered_on_23(self):
        self.assertEqual(stated("record_sha256()"), REGISTERED_RECORD_SHA256)

    def test_the_paste_ready_text_carries_the_digest_and_the_pin(self):
        text = RECORD.read_text(encoding="utf-8")
        paste = text.split("## The registration text", 1)[1]
        for needle in (h10_registration.REGISTERED_DIGEST, PAGE_PIN, PAGE_PANEL_SHA256, REGISTERED_RECORD_SHA256, "new declaration"):
            self.assertIn(needle, paste)


if __name__ == "__main__":
    unittest.main()
