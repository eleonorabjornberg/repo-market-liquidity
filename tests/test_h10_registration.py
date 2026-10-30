"""H10's live entry point refuses a row made by code that is not the registered method (#200, step 5).

The parent's decision instant moved to 18:00 (repo-market-model#1315) and H10's moved with it, so `main` carries a method whose
digest is not the one Eleonora registered on #23 on 22 October 2026 (`43bf1303...15bb`, this repository at `7838483` with
the parent at `08ff67e`). Until she registers the new method, a live H10 row must come from the registered code and never from
`main`. `h10_live.attribute_onset` enforces it through `h10_registration.check_registered`.

**Recorded mutation** (30 October 2026, CPython 3.11, the parent at 2032de4, applied in the working tree and reverted):
in `src/repo_liquidity/h10_registration.py`, `check_registered`, the line `if digest != registered:` changed to
`if False:`. `test_the_entry_point_refuses_a_digest_that_is_not_the_registered_one` failed with
`AssertionError: ValueError not raised`.
"""

import pathlib
import unittest
from datetime import date, timedelta

from repo_liquidity import h10_live, h10_registration
from test_h10_live import FAST, make_rows, stub_rule

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RegisteredDigestTests(unittest.TestCase):
    def test_the_registration_file_is_not_a_part_of_the_method_digest(self):
        """The registered digest cannot live in a file the digest covers: it would have to equal its own hash."""
        covered = {path.resolve() for _, path in h10_live.METHOD_FILES}
        self.assertNotIn((ROOT / "src" / "repo_liquidity" / "h10_registration.py").resolve(), covered)

    def test_the_registered_digest_is_the_one_of_22_october(self):
        self.assertEqual(h10_registration.REGISTERED_DIGEST,
                         "43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb")
        self.assertEqual(h10_registration.REGISTERED_COMMIT, "7838483")
        self.assertEqual(h10_registration.REGISTERED_PARENT, "08ff67e27bc3d7e357491cf8e1da59793702b3fb")

    def test_the_entry_point_refuses_a_digest_that_is_not_the_registered_one(self):
        """The guard: with the default registered digest, this tree's method (a different digest) is refused, before any row."""
        rows, onset = make_rows(), date(2025, 1, 1) + timedelta(days=100)
        self.assertNotEqual(h10_live.method_digest(), h10_registration.REGISTERED_DIGEST)
        with self.assertRaises(ValueError) as caught:
            h10_live.attribute_onset(rows, stub_rule(), onset, onset + timedelta(days=10), draws=20, null_draws=20)
        self.assertIn(h10_registration.REGISTERED_DIGEST, str(caught.exception))
        self.assertIn(h10_registration.REGISTERED_COMMIT, str(caught.exception))

    def test_the_entry_point_gives_a_row_when_the_digest_is_the_registered_one(self):
        rows, onset = make_rows(), date(2025, 1, 1) + timedelta(days=100)
        row = h10_live.attribute_onset(rows[:111], stub_rule(), onset, onset + timedelta(days=10), **FAST)
        self.assertEqual(row["method_digest"], h10_live.method_digest())

    def test_the_check_names_both_digests(self):
        h10_registration.check_registered("a" * 64, "a" * 64)
        with self.assertRaises(ValueError) as caught:
            h10_registration.check_registered("a" * 64, "b" * 64)
        self.assertIn("a" * 64, str(caught.exception))
        self.assertIn("b" * 64, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
