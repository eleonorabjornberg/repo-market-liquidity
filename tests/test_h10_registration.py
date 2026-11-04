"""H10's live entry point refuses a row made by code that is not the registered method (#200, step 5).

The registered digest is the method digest of this tree with the parent at the pin. `h10_live.attribute_onset` refuses a row
whose digest is not `h10_registration.REGISTERED_DIGEST`, through `h10_registration.check_registered`.

**Recorded mutation** (4 November 2026, CPython 3.11, the parent at 2032de4, applied in the working tree and reverted):
in `src/repo_liquidity/h10_registration.py`, `check_registered`, the line `if digest != registered:` changed to
`if False:`. `test_the_check_names_both_digests` failed with `AssertionError: ValueError not raised`, and
`test_the_entry_point_refuses_a_digest_that_is_not_the_registered_one` failed with an `AssertionError` (the old digest was not
in the message of the `ValueError` the entry point raised later, on the rows after the report day).

Since #202 the constants are the ones of Eleonora's registration of 3 November 2026 (`54b5f151...8770`, this repository at
`ba1860cb`, the parent at `2032de4`); the 22 October digest is used below only as a registered digest this tree does not give.
"""

import pathlib
import unittest
from datetime import date, timedelta

import repo_liquidity
from repo_liquidity import h10_live, h10_registration
from test_h10_live import FAST, make_rows, stub_rule

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RegisteredDigestTests(unittest.TestCase):
    def test_the_registration_file_is_not_a_part_of_the_method_digest(self):
        """The registered digest cannot live in a file the digest covers: it would have to equal its own hash."""
        covered = {path.resolve() for _, path in h10_live.METHOD_FILES}
        self.assertNotIn((ROOT / "src" / "repo_liquidity" / "h10_registration.py").resolve(), covered)

    def test_the_registered_constants_are_the_ones_of_3_november(self):
        """Eleonora's registration of 3 November 2026 on #23 (comment 6618862828): the method digest, the commit of this
        repository it was made at (#201's merge) and the parent pin it names."""
        self.assertEqual(h10_registration.REGISTERED_DIGEST,
                         "54b5f151c757b1cff5d3ebe6e8ce202bd41cafc4d8104effb00f3da4617c8770")
        self.assertEqual(h10_registration.REGISTERED_COMMIT, "ba1860cb096b3c7f92a6975e6908be7a480e459c")
        self.assertEqual(h10_registration.REGISTERED_PARENT, "2032de4a7d7802289bc5a78dfc02599752bc7c5c")
        self.assertEqual(h10_registration.REGISTERED_PARENT, repo_liquidity.PARENT_COMMIT)

    def test_this_tree_at_the_pin_has_the_registered_digest(self):
        """The method digest of a clean tree with the parent at the pin is the registered one: a change to a covered file,
        or a parent checkout other than the pin, fails here."""
        self.assertEqual(h10_live.method_digest(), h10_registration.REGISTERED_DIGEST)

    def test_the_entry_point_refuses_a_digest_that_is_not_the_registered_one(self):
        """The guard: a registered digest that is not this tree's (the 22 October one) is refused, before any row."""
        rows, onset = make_rows(), date(2025, 1, 1) + timedelta(days=100)
        old = "43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb"
        self.assertNotEqual(h10_live.method_digest(), old)
        with self.assertRaises(ValueError) as caught:
            h10_live.attribute_onset(rows, stub_rule(), onset, onset + timedelta(days=10), draws=20, null_draws=20,
                                     registered_digest=old)
        self.assertIn(old, str(caught.exception))
        self.assertIn(h10_registration.REGISTERED_COMMIT, str(caught.exception))

    def test_the_entry_point_passes_the_registration_check_with_nothing_passed(self):
        """The live job passes no `registered_digest`: at the pin the default constant is this tree's digest, so no row is
        refused by the registration guard."""
        rows, onset = make_rows(), date(2025, 1, 1) + timedelta(days=100)
        row = h10_live.attribute_onset(rows[:111], stub_rule(), onset, onset + timedelta(days=10), draws=20, null_draws=20)
        self.assertEqual(row["method_digest"], h10_registration.REGISTERED_DIGEST)

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
