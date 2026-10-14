"""The weekly group-reserves series (#43, H7m groundwork G4): H.8 group cash assets set against H.4.1 reserves.

Eleonora's rulings of 14 October 2026 on PR #50 (option a for the foreign-related group, option (i) for the domestic
split) make every group level the H.8 group's cash assets, first print, labelled an approximation; the residual is H.4.1
reserves less the three. The builder is tested on small synthetic inputs; the tracked extract is tested on the real one cut
by `scripts/build_group_reserves.py` from tracked inputs only. No test scores anything.
"""

import hashlib
import json
import pathlib
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta

from repo_model.splits import LookAheadError

from repo_liquidity import group_reserves as gr
from repo_liquidity import h8

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "group_reserves"
EXTRACT = DIRECTORY / gr.EXTRACT_NAME
NY = h8.NEW_YORK
Q1 = date(2021, 3, 31)  # a Wednesday


def week(i):
    return Q1 + timedelta(days=7 * i)


def prints(weeks=range(0, 8), large=100.0, small=50.0, foreign=80.0, step=1.0):
    """H.8 first prints: large and small cash `large + step * i`, `small + step * i`; foreign as given; released nine days after."""
    out = []
    for i in weeks:
        w = week(i)
        values = {field: 0.0 for field in h8.FIELDS}
        values["h8_large_domestic_cash_assets"] = large + step * i
        values["h8_small_domestic_cash_assets"] = small + step * i
        values["h8_foreign_related_cash_assets"] = foreign
        out.append(h8.FirstPrint(week_ending=w, release_date=w + timedelta(days=9), values=values, release_sha256="0" * 64))
    return out


def reserves(weeks=range(0, 8), value=300.0):
    """H.4.1 reserves in billions, public from the Monday after the week (before the H.8 print)."""
    return {week(i): (value, datetime.combine(week(i) + timedelta(days=5), datetime.min.time(), tzinfo=NY)) for i in weeks}


class BuildTests(unittest.TestCase):
    def build(self, **kwargs):
        args = dict(prints=prints(), reserves=reserves(), breaks={})
        args.update(kwargs)
        return gr.build(**args)

    def test_each_group_is_its_h8_cash_assets_first_print_with_no_anchor(self):
        rows, holes = self.build()
        by_week = {r.week_ending: r for r in rows}
        self.assertEqual(holes, [])
        self.assertEqual(by_week[week(0)].large_domestic_bn, 100.0)
        self.assertEqual(by_week[week(4)].large_domestic_bn, 104.0)
        self.assertEqual(by_week[week(4)].small_domestic_bn, 54.0)
        self.assertEqual({r.foreign_related_bn for r in rows}, {80.0})

    def test_the_residual_is_reserves_less_the_three_groups_and_is_not_clipped(self):
        rows, _ = self.build()
        self.assertEqual(rows[0].other_bn, round(300.0 - 100.0 - 50.0 - 80.0, 6))
        self.assertFalse(rows[0].other_negative)
        negative, _ = self.build(reserves=reserves(value=200.0))
        self.assertEqual(negative[0].other_bn, round(200.0 - 100.0 - 50.0 - 80.0, 6))
        self.assertTrue(negative[0].other_negative)

    def test_a_week_is_public_when_the_later_of_the_h8_print_and_the_reserves_is(self):
        """Leakage guard: a row is public only when both of its inputs are.

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves._public_at`, `max(h8.available_at(...),
        reserve_at)` replaced by `min(...)`. This test then fails: `AssertionError` (the row is public at 2021-04-09 16:15
        where the later reserves instant, 2021-04-11, is expected).
        """
        later = {week(i): (300.0, datetime.combine(week(i) + timedelta(days=11), datetime.min.time(), tzinfo=NY))
                 for i in range(0, 8)}
        rows, _ = self.build(reserves=later)
        self.assertEqual(rows[0].public_at, later[week(0)][1])
        rows, _ = self.build()
        self.assertEqual(rows[0].public_at, h8.available_at(week(0) + timedelta(days=9)))

    def test_a_break_week_is_flagged_and_still_a_row(self):
        """A level is a first print, not a ratio, so a break is not a refusal; the week is flagged for the reader."""
        rows, holes = self.build(breaks={week(3): "move-xx"})
        self.assertEqual(holes, [])
        self.assertEqual([r.week_ending for r in rows if r.h8_break_week], [week(3)])

    def test_a_week_without_reserves_is_a_hole(self):
        rows, holes = self.build(reserves={k: v for k, v in reserves().items() if k != week(2)})
        self.assertEqual([h["reason"] for h in holes], ["reserves_missing"])
        self.assertNotIn(week(2), {r.week_ending for r in rows})

    def test_the_decision_instants_need_a_time_zone(self):
        naive = {week(i): (300.0, datetime(2021, 4, 5)) for i in range(0, 8)}
        with self.assertRaises(ValueError):
            self.build(reserves=naive)


class VerifyTests(unittest.TestCase):
    def rows(self):
        return gr.build(prints=prints(), reserves=reserves(), breaks={})[0]

    def test_a_built_series_verifies(self):
        self.assertIsNone(gr.verify(self.rows(), prints(), reserves()))

    def test_verify_refuses_a_row_public_before_its_inputs_are(self):
        """Leakage guard: a stored row cannot be public before the later of its two inputs.

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves.verify`, the test
        `row.public_at < ready` replaced by `False`. This test then fails: `AssertionError: LookAheadError not raised`.
        """
        rows = self.rows()
        bad = [gr.Row(**{**rows[0].__dict__, "public_at": datetime(2021, 4, 3, tzinfo=NY)})]
        with self.assertRaises(LookAheadError):
            gr.verify(bad, prints(), reserves())

    def test_verify_refuses_a_level_that_is_not_the_first_print(self):
        rows = self.rows()
        bad = [gr.Row(**{**rows[0].__dict__, "large_domestic_bn": 1.0})]
        with self.assertRaises(ValueError):
            gr.verify(bad, prints(), reserves())

    def test_verify_refuses_a_week_the_inputs_do_not_hold(self):
        rows = self.rows()
        with self.assertRaises(ValueError):
            gr.verify(rows, prints(weeks=range(1, 8)), reserves())


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = gr.tracked_inputs()
        cls.rows = gr.load_extract(EXTRACT)
        cls.coverage = json.loads((DIRECTORY / gr.COVERAGE_NAME).read_text(encoding="utf-8"))

    def test_the_tracked_extract_is_what_the_tracked_inputs_build(self):
        rows, holes = gr.build(**self.inputs)
        self.assertEqual(gr.write_extract(rows), EXTRACT.read_bytes())
        self.assertEqual(gr.coverage(rows, holes, self.inputs["prints"]), self.coverage)

    def test_every_h8_week_is_a_row_or_a_listed_hole(self):
        weeks = len(self.inputs["prints"])
        self.assertEqual(len(self.rows) + sum(self.coverage["reasons"].values()), weeks)
        self.assertEqual(len(self.coverage["holes"]), sum(self.coverage["reasons"].values()))
        self.assertTrue(set(self.coverage["reasons"]) <= set(gr.REFUSALS))

    def test_the_series_has_rows(self):
        self.assertGreater(len(self.rows), 0)

    def test_every_row_verifies_against_the_inputs(self):
        gr.verify(self.rows, self.inputs["prints"], self.inputs["reserves"])

    def test_no_row_is_public_after_the_development_end(self):
        from repo_liquidity import development

        self.assertTrue(all(not development.is_locked(r.public_at.date()) for r in self.rows))

    def test_break_weeks_are_flagged_as_the_h8_record_has_them(self):
        flagged = {r.week_ending for r in self.rows if r.h8_break_week}
        self.assertEqual(flagged, {w for w in self.inputs["breaks"] if w in {r.week_ending for r in self.rows}})

    def test_a_negative_residual_is_flagged_and_counted(self):
        flagged = [r for r in self.rows if r.other_negative]
        self.assertEqual(len(flagged), self.coverage["other_negative_weeks"])


class LoadGuardTests(unittest.TestCase):
    def copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for path in DIRECTORY.glob(gr.EXTRACT_NAME + "*"):
            shutil.copy(path, tmp.name)
        return pathlib.Path(tmp.name) / gr.EXTRACT_NAME

    def test_an_edited_extract_is_refused(self):
        path = self.copy()
        text = path.read_text()
        path.write_text(text.replace(",", ";", 1))
        with self.assertRaises(ValueError):
            gr.load_extract(path)

    def test_columns_that_are_not_the_declared_ones_are_refused(self):
        path = self.copy()
        data = path.read_text().replace("week_ending", "week", 1)
        path.write_text(data)
        manifest = path.with_name(path.name + ".manifest.json")
        record = json.loads(manifest.read_text())
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            gr.load_extract(path)


if __name__ == "__main__":
    unittest.main()
