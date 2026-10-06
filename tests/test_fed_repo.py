"""The Fed's 2019 to 2021 repo operations and the combined repo take-up (`docs/stages/stage-1a-correction.md`).

Items 2 and 3: the temporary open market operations from 2019-09-17 to 2021-07-28 are take-up from a different
facility; before them take-up is a structural zero; from 2021-07-29 it is the standing facility's. The facility's
material use is take-up of $1bn or more.
"""

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from repo_liquidity import fed_repo


def op(day, amount, term="Overnight", kind="Repo", note=""):
    return {"operationDate": day, "operationType": kind, "term": term, "totalAmtAccepted": amount, "note": note}


class DailyTakeUpTests(unittest.TestCase):
    def test_overnight_operations_are_summed_per_day_in_billions(self):
        ops = [op("2019-09-17", 53_150_000_000), op("2019-09-18", 75_000_000_000),
               op("2019-09-18", 1_000_000_000), op("2019-09-18", 30_000_000_000, term="Term")]
        self.assertEqual(fed_repo.daily_take_up(ops, term="Overnight"),
                         {date(2019, 9, 17): 53.15, date(2019, 9, 18): 76.0})
        self.assertEqual(fed_repo.daily_take_up(ops, term="Term"), {date(2019, 9, 18): 30.0})

    def test_only_repo_operations_inside_the_window_are_read(self):
        ops = [op("2019-05-13", 65_000_000), op("2019-09-16", 5_000_000_000), op("2021-07-29", 1_000_000_000),
               op("2019-10-01", 9_000_000_000, kind="Reverse Repo"), op("2019-10-01", 2_000_000_000)]
        self.assertEqual(fed_repo.daily_take_up(ops, term="Overnight"), {date(2019, 10, 1): 2.0})

    def test_a_small_value_exercise_is_not_take_up(self):
        ops = [op("2020-01-02", 10_000_000, note="Small Value Exercise (SVE)"), op("2020-01-02", 0)]
        self.assertEqual(fed_repo.daily_take_up(ops, term="Overnight"), {date(2020, 1, 2): 0.0})

    def test_an_operation_without_a_numeric_amount_is_refused(self):
        with self.assertRaises(ValueError):
            fed_repo.daily_take_up([op("2020-01-02", None)], term="Overnight")


class AvailabilityTests(unittest.TestCase):
    def test_a_day_is_public_at_16_00_on_the_next_weekday(self):
        rows = fed_repo.observations({date(2019, 9, 20): 1.0}, series=fed_repo.SERIES, source_sha="x")
        self.assertEqual(rows[0].available_at, datetime(2019, 9, 23, 16, 0, tzinfo=ZoneInfo("America/New_York")))
        self.assertEqual(rows[0].ref_date, date(2019, 9, 20))


class CombinedTests(unittest.TestCase):
    def combine(self, day, temporary=None, standing=None):
        return fed_repo.combined({"date": day, "temp_repo_take_up": temporary, "srf_take_up": standing})

    def test_before_the_first_operation_take_up_is_a_structural_zero(self):
        self.assertEqual(self.combine(date(2019, 9, 16)), (0.0, fed_repo.NONE))
        self.assertEqual(self.combine(date(2018, 4, 3)), (0.0, fed_repo.NONE))

    def test_from_the_first_operation_a_day_with_no_operation_is_missing(self):
        self.assertEqual(self.combine(date(2019, 9, 17)), (None, None))

    def test_the_temporary_operations_then_the_standing_facility(self):
        self.assertEqual(self.combine(date(2019, 9, 18), temporary=53.15), (53.15, fed_repo.TEMPORARY))
        self.assertEqual(self.combine(date(2021, 8, 2), standing=0.0), (0.0, fed_repo.STANDING))

    def test_a_row_with_nothing_readable_after_the_zero_is_missing_not_zero(self):
        self.assertEqual(self.combine(date(2020, 6, 1)), (None, None))

    def test_both_facilities_on_one_row_is_refused(self):
        with self.assertRaises(ValueError):
            self.combine(date(2021, 7, 30), temporary=0.0, standing=0.0)


class MaterialUseTests(unittest.TestCase):
    def test_material_use_is_take_up_of_at_least_one_billion(self):
        self.assertEqual([fed_repo.material_use(v) for v in (None, 0.0, 0.003, 0.999, 1.0, 74.6)],
                         [None, 0.0, 0.0, 0.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
