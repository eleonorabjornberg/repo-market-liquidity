"""The development records of Stages 1 to 6, at head: byte-unchanged, and verified where they were made.

Option (a) of L0 (#21): each record is verified at the commit and parent pin it was made from, by
`scripts/verify_records.py`, which CI runs (the `records` job). The head suite checks only that the record files are
byte-unchanged, and that each one names the pin it was made at.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path

from repo_liquidity import records

ROOT = Path(__file__).resolve().parents[1]


def _freeze():
    spec = importlib.util.spec_from_file_location("stage4_freeze", ROOT / "scripts" / "stage4_freeze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _provenance_commits(value, trail=()):
    """Every `parent_commit` anywhere in a JSON record, with where it sits."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "parent_commit":
                yield trail + (key,), item
            else:
                yield from _provenance_commits(item, trail + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _provenance_commits(item, trail + (index,))


class RecordBytesTests(unittest.TestCase):
    def test_the_record_commit_and_pin_are_full_commits(self):
        self.assertRegex(records.RECORD_COMMIT, r"^[0-9a-f]{40}$")
        self.assertRegex(records.RECORD_PIN, r"^[0-9a-f]{40}$")

    def test_every_record_file_is_byte_unchanged(self):
        """Recorded mutation (12 October 2026): a space appended to `results/stage3/latent.json`. This test failed
        with AssertionError naming that file."""
        self.assertEqual(records.changed(ROOT), [])

    def test_every_file_under_results_and_metadata_is_a_listed_record(self):
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "results", "metadata"], check=True,
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(tracked), sorted({**records.RECORD_FILES, **records.OWN_CHECK}))

    def test_a_record_made_after_l0_names_the_test_that_checks_it(self):
        """A record made after L0 is not byte-pinned here (its stage may be re-run only as a new record); it is listed with
        the test file that checks it, and that file exists."""
        for path, test in records.OWN_CHECK.items():
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertTrue((ROOT / test).is_file(), test)
            self.assertNotIn(path, records.RECORD_FILES)

    def test_every_record_names_the_pin_it_was_made_at(self):
        found = 0
        for path in records.RECORD_FILES:
            if not path.endswith(".json"):
                continue
            for where, commit in _provenance_commits(json.loads((ROOT / path).read_text(encoding="utf-8"))):
                self.assertEqual(commit, records.RECORD_PIN, (path, where))
                found += 1
        self.assertGreater(found, 10)

    def test_the_stage4_freeze_checksum_is_unchanged(self):
        text = (ROOT / "docs" / "decisions" / "stage-4-freeze.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^- \*\*Declaration checksum:\*\* `([^`]+)`", text, re.MULTILINE),
                         [records.FREEZE_CHECKSUM])

    def test_ci_verifies_the_records_at_their_commit(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/verify_records.py", workflow)

    def test_the_digests_are_sha256_of_the_bytes(self):
        path = "metadata/phase3_panel_manifest.json"
        self.assertEqual(records.RECORD_FILES[path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


class FreezeAtHeadTests(unittest.TestCase):
    def test_the_stage4_freeze_refuses_at_head_with_a_value_error(self):
        """The freeze hashes the deleted IORB table and `scheduled`'s deleted IORB names, and the parent pin it was
        made at; at head it cannot be recomputed, and says where it is verified."""
        with self.assertRaises(ValueError) as caught:
            _freeze().checksum()
        self.assertIn("verify_records.py", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
