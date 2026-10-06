"""The Fed's 2019 to 2021 repo operations and the combined repo take-up (`docs/stages/stage-1a-correction.md`).

Items 2 and 3: the temporary open market operations from 2019-09-17 to 2021-07-28 are take-up from a different
facility; before them take-up is a structural zero; from 2021-07-29 it is the standing facility's. The facility's
material use is take-up of $1bn or more.
"""

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from repo_liquidity import fed_repo


def op(day, amount, term="Overnight", kind="Repo", note="", settle=None, mature=None):
    return {"operationDate": day, "operationType": kind, "term": term, "totalAmtAccepted": amount, "note": note,
            "settlementDate": settle or day, "maturityDate": mature}


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


class TermOutstandingTests(unittest.TestCase):
    """Question 14 (Nicholas, 6 October 2026): a term repo counts while it is outstanding, settlement to maturity."""

    def test_a_term_repo_is_outstanding_from_settlement_until_the_day_before_maturity(self):
        ops = [op("2019-12-16", 50_000_000_000, term="Term", mature="2020-01-17"),
               op("2019-12-17", 6_100_000_000, term="Term", mature="2019-12-30")]
        out = fed_repo.term_outstanding(ops)
        self.assertEqual(out[date(2019, 12, 16)], 50.0)
        self.assertEqual(out[date(2019, 12, 17)], 56.1)
        self.assertEqual(out[date(2019, 12, 27)], 56.1)
        self.assertEqual(out[date(2019, 12, 30)], 50.0)
        self.assertEqual(out[date(2020, 1, 16)], 50.0)
        self.assertEqual(out[date(2020, 1, 17)], 0.0)

    def test_every_weekday_of_the_window_carries_a_value_and_no_weekend_does(self):
        out = fed_repo.term_outstanding([])
        self.assertEqual(min(out), fed_repo.FIRST_OPERATION)
        self.assertEqual(max(out), fed_repo.LAST_OPERATION)
        self.assertTrue(all(day.weekday() < 5 for day in out))
        self.assertEqual(set(out.values()), {0.0})

    def test_a_term_repo_without_a_maturity_is_refused(self):
        with self.assertRaises(ValueError):
            fed_repo.term_outstanding([op("2019-12-16", 1_000_000_000, term="Term")])


class AvailabilityTests(unittest.TestCase):
    def test_a_day_is_public_at_16_00_on_the_next_weekday(self):
        rows = fed_repo.observations({date(2019, 9, 20): 1.0}, series=fed_repo.SERIES, source_sha="x")
        self.assertEqual(rows[0].available_at, datetime(2019, 9, 23, 16, 0, tzinfo=ZoneInfo("America/New_York")))
        self.assertEqual(rows[0].ref_date, date(2019, 9, 20))


class CombinedTests(unittest.TestCase):
    def combine(self, day, temporary=None, standing=None, term=None):
        return fed_repo.combined({"date": day, "temp_repo_take_up": temporary, "srf_take_up": standing,
                                  "temp_repo_term_outstanding": term})

    def test_the_temporary_take_up_adds_the_term_repos_outstanding(self):
        self.assertEqual(self.combine(date(2019, 12, 17), temporary=20.0, term=56.1), (76.1, fed_repo.TEMPORARY))

    def test_a_day_with_no_overnight_operation_stays_missing_whatever_is_outstanding(self):
        self.assertEqual(self.combine(date(2020, 4, 9), term=10.0), (None, None))

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


class RepoMaterialUseTests(unittest.TestCase):
    """Question 14: the event counts each operation on its operation date, overnight and term alike."""

    def event(self, day, overnight=None, term=None, standing=None):
        return fed_repo.repo_material_use({"date": day, "temp_repo_take_up": overnight,
                                           "temp_repo_term_take_up": term, "srf_take_up": standing})

    def test_before_the_first_operation_there_is_no_event(self):
        self.assertEqual(self.event(date(2019, 9, 16)), 0.0)

    def test_a_temporary_day_counts_overnight_and_term_accepted_that_day(self):
        self.assertEqual(self.event(date(2019, 12, 16), overnight=0.5, term=0.6), 1.0)
        self.assertEqual(self.event(date(2019, 12, 16), overnight=0.5), 0.0)
        self.assertEqual(self.event(date(2019, 12, 16), term=2.0), 1.0)

    def test_a_standing_facility_day_is_its_take_up(self):
        self.assertEqual(self.event(date(2025, 12, 31), standing=74.6), 1.0)
        self.assertEqual(self.event(date(2025, 12, 30), standing=0.003), 0.0)

    def test_a_day_with_nothing_read_after_the_zero_is_missing(self):
        self.assertIsNone(self.event(date(2020, 6, 1)))


class MaterialUseTests(unittest.TestCase):
    def test_material_use_is_take_up_of_at_least_one_billion(self):
        self.assertEqual([fed_repo.material_use(v) for v in (None, 0.0, 0.003, 0.999, 1.0, 74.6)],
                         [None, 0.0, 0.0, 0.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
