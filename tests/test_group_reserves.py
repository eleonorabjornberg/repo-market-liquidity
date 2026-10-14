"""The weekly group-reserves series (#43, H7m groundwork G4): the anchor, moved by H.8 group cash, set against H.4.1 reserves.

The builder is tested on small synthetic inputs; the tracked extract is tested on the real one cut by
`scripts/build_group_reserves.py` from tracked inputs only. No test scores anything.
"""

import hashlib
import json
import pathlib
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import group_reserves as gr
from repo_liquidity import h8, rca

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "group_reserves"
EXTRACT = DIRECTORY / gr.EXTRACT_NAME
NY = rca.NEW_YORK
Q1, Q2 = date(2021, 3, 31), date(2021, 6, 30)  # 2021-03-31 and 2021-06-30 are Wednesdays


def week(i):
    return Q1 + timedelta(days=7 * i)


def prints(weeks=range(0, 8), large=100.0, small=50.0, foreign=80.0, step=1.0):
    """H.8 first prints: large cash `large + step * i`, small and foreign as given; released nine days after the week."""
    out = []
    for i in weeks:
        w = week(i)
        values = {field: 0.0 for field in h8.FIELDS}
        values["h8_large_domestic_cash_assets"] = large + step * i
        values["h8_small_domestic_cash_assets"] = small + step * i
        values["h8_foreign_related_cash_assets"] = foreign
        out.append(h8.FirstPrint(week_ending=w, release_date=w + timedelta(days=9), values=values, release_sha256="0" * 64))
    return out


def anchor(quarter, group, bn, available):
    """An anchor row: `bn` billions, public from the start of `available`'s day (New York)."""
    return rca.Row(quarter, group, 25, int(bn * 1e6), datetime.combine(available - timedelta(days=1), datetime.min.time()), "0" * 64)


def anchors(available=date(2021, 4, 5), large=60.0, small=30.0):
    return [anchor(Q1, "large_domestic", large, available), anchor(Q1, "small_domestic", small, available)]


def reserves(weeks=range(0, 8), value=200.0):
    """H.4.1 reserves in billions, public from the Monday after the week (before the H.8 print)."""
    return {week(i): (value, datetime.combine(week(i) + timedelta(days=5), datetime.min.time(), tzinfo=NY)) for i in weeks}


class BuildTests(unittest.TestCase):
    def build(self, **kwargs):
        args = dict(prints=prints(), anchors=anchors(), reserves=reserves(), breaks={})
        args.update(kwargs)
        return gr.build(**args)

    def test_a_group_is_the_anchor_moved_by_the_ratio_of_the_group_cash_assets(self):
        rows, holes = self.build()
        by_week = {r.week_ending: r for r in rows}
        # The anchor week is the week of the quarter-end: large cash 100, small cash 50.
        self.assertEqual(by_week[week(0)].large_domestic_bn, 60.0)
        self.assertEqual(by_week[week(4)].large_domestic_bn, 60.0 * 104.0 / 100.0)
        self.assertEqual(by_week[week(4)].small_domestic_bn, 30.0 * 54.0 / 50.0)

    def test_the_foreign_related_group_is_the_h8_cash_assets(self):
        rows, _ = self.build(prints=prints(foreign=88.5))
        self.assertEqual({r.foreign_related_bn for r in rows}, {88.5})

    def test_the_residual_is_reserves_less_the_three_groups_and_is_not_clipped(self):
        rows, _ = self.build()
        first = rows[0]
        self.assertEqual(first.other_bn, round(200.0 - 60.0 - 30.0 - 80.0, 6))
        negative, _ = self.build(reserves=reserves(value=150.0))
        self.assertEqual(negative[0].other_bn, round(150.0 - 60.0 - 30.0 - 80.0, 6))
        self.assertTrue(negative[0].other_negative)
        self.assertFalse(rows[0].other_negative)

    def test_a_week_is_public_when_the_later_of_the_h8_print_and_the_reserves_is(self):
        later = {week(i): (200.0, datetime.combine(week(i) + timedelta(days=11), datetime.min.time(), tzinfo=NY))
                 for i in range(0, 8)}
        rows, _ = self.build(reserves=later)
        self.assertEqual(rows[0].public_at, later[week(0)][1])
        rows, _ = self.build()
        self.assertEqual(rows[0].public_at, h8.available_at(week(0) + timedelta(days=9)))

    def test_a_week_before_any_anchor_is_public_is_a_hole_and_not_a_guess(self):
        rows, holes = self.build(anchors=anchors(available=date(2021, 4, 20)))
        self.assertEqual(sorted({h["reason"] for h in holes}), ["no_anchor_public"])
        self.assertTrue(all(r.public_at >= datetime(2021, 4, 20, tzinfo=NY) for r in rows))
        self.assertEqual(len(rows) + len(holes), 8)

    def test_both_domestic_anchors_are_needed(self):
        only_large = [a for a in anchors() if a.group == "large_domestic"]
        rows, holes = self.build(anchors=only_large)
        self.assertEqual(rows, [])
        self.assertEqual({h["reason"] for h in holes}, {"no_anchor_public"})
        self.assertTrue(all("small_domestic" in h["detail"] for h in holes))

    def test_the_latest_public_quarter_is_the_anchor_and_a_later_one_is_used_once_public(self):
        newer = anchor(Q2, "large_domestic", 90.0, week(14) + timedelta(days=2))
        rows, _ = self.build(anchors=anchors() + [newer],
                             prints=prints(weeks=range(0, 20)), reserves=reserves(weeks=range(0, 20)))
        used = {r.week_ending: r.large_anchor_quarter for r in rows}
        self.assertEqual(used[week(0)], Q1)
        self.assertEqual(used[week(19)], Q2)
        for r in rows:
            self.assertTrue(rca.latest_public(anchors() + [newer], "large_domestic", r.public_at).quarter_end
                            == r.large_anchor_quarter)

    def test_a_move_across_a_break_is_refused_and_listed(self):
        """Break guard: the H.8 restates the large and small panels at a break week, so a move across one is a change of
        basis and not a flow (`h8.difference`).

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves.build`, the test
        `any(origin < b <= week for b in breaks)` replaced by `False`. This test then fails: the weeks after the break
        are built (`AssertionError: Lists differ`).
        """
        rows, holes = self.build(breaks={week(3): "move-xx"})
        self.assertEqual([r.week_ending for r in rows], [week(0), week(1), week(2)])
        self.assertEqual({h["reason"] for h in holes}, {"break_between_anchor_and_week"})
        self.assertEqual([h["week_ending"] for h in holes], [week(i).isoformat() for i in range(3, 8)])

    def test_a_break_at_the_anchor_week_itself_is_not_between(self):
        rows, holes = self.build(breaks={week(0): "move-xx"})
        self.assertEqual(len(rows), 8)

    def test_a_week_without_reserves_is_a_hole(self):
        rows, holes = self.build(reserves={k: v for k, v in reserves().items() if k != week(2)})
        self.assertEqual([h["reason"] for h in holes], ["reserves_missing"])
        self.assertNotIn(week(2), {r.week_ending for r in rows})

    def test_the_anchor_week_is_the_h8_week_nearest_the_quarter_end(self):
        weeks = [week(i) for i in range(0, 5)]
        self.assertEqual(gr.anchor_week(weeks, Q1), Q1)
        self.assertEqual(gr.anchor_week(weeks, Q1 + timedelta(days=3)), Q1)  # ties go to the earlier week
        self.assertEqual(gr.anchor_week(weeks, Q1 + timedelta(days=4)), week(1))
        with self.assertRaises(ValueError):
            gr.anchor_week(weeks, date(2030, 1, 1))

    def test_a_quarter_ending_after_the_week_is_refused(self):
        """Leakage guard: an anchor of a quarter that ends after a week cannot anchor it.

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves.build`, the test
        `found.quarter_end > week` replaced by `False`. This test then errors with `ValueError` from `anchor_week` (no
        H.8 week of the synthetic extract ends within 3 days of the quarter-end), not with `LookAheadError`.
        """
        late = anchors()
        late[0] = anchor(date(2021, 6, 30), "large_domestic", 60.0, date(2021, 4, 5))
        with self.assertRaises(LookAheadError):
            self.build(anchors=late)

    def test_a_cash_asset_of_zero_at_the_anchor_week_is_refused(self):
        data = prints()
        data[0].values["h8_large_domestic_cash_assets"] = 0.0
        with self.assertRaises(ValueError):
            self.build(prints=data)

    def test_the_decision_instants_need_a_time_zone(self):
        naive = {week(i): (200.0, datetime(2021, 4, 5)) for i in range(0, 8)}
        with self.assertRaises(ValueError):
            self.build(reserves=naive)


class VerifyTests(unittest.TestCase):
    def rows(self):
        return gr.build(prints=prints(weeks=range(0, 20)), anchors=anchors() + [anchor(Q2, "large_domestic", 90.0,
                        week(14) + timedelta(days=2)), anchor(Q2, "small_domestic", 40.0, week(14) + timedelta(days=2))],
                        reserves=reserves(weeks=range(0, 20)), breaks={})[0]

    def test_a_built_series_verifies(self):
        rows = self.rows()
        self.assertEqual(gr.verify(rows, anchors() + [anchor(Q2, "large_domestic", 90.0, week(14) + timedelta(days=2)),
                                                      anchor(Q2, "small_domestic", 40.0, week(14) + timedelta(days=2))]), None)

    def test_a_row_that_uses_an_anchor_not_yet_public_is_look_ahead(self):
        """Leakage guard: a row is built only from an anchor public at its own `public_at`.

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves.build`, the call
        `rca.latest_public(anchors, group, public_at)` replaced by the same call at `public_at + timedelta(days=36500)`.
        This test then fails: the rows pick the Q2 anchor, which is public only from December 2021, and `build` raises
        `LookAheadError` from its quarter-after-week guard (the Q2 quarter-end is after the weeks it would anchor), so the
        test errors where it expects rows on the Q1 anchor.
        """
        newer = [anchor(Q2, "large_domestic", 90.0, date(2021, 12, 1)), anchor(Q2, "small_domestic", 40.0, date(2021, 12, 1))]
        rows, _ = gr.build(prints=prints(weeks=range(0, 20)), anchors=anchors() + newer, reserves=reserves(weeks=range(0, 20)),
                           breaks={})
        self.assertEqual({r.large_anchor_quarter for r in rows}, {Q1})
        self.assertEqual({r.small_anchor_quarter for r in rows}, {Q1})

    def test_verify_refuses_a_row_whose_anchor_was_not_public_at_its_instant(self):
        rows = self.rows()
        bad = [gr.Row(**{**rows[0].__dict__, "public_at": datetime(2021, 4, 3, tzinfo=NY)})]
        with self.assertRaises(LookAheadError):
            gr.verify(bad, anchors())

    def test_verify_refuses_a_row_that_uses_an_older_anchor_than_the_latest_public(self):
        """Staleness guard: a row uses the latest anchor quarter public at its instant, not an older one.

        Recorded mutation (14 October 2026): in `repo_liquidity.group_reserves.verify`, the test
        `latest.quarter_end > row.large_anchor_quarter` replaced by `False`. This test then fails: no `StaleReadError`
        is raised.
        """
        pair = anchors() + [anchor(Q2, "large_domestic", 90.0, week(14) + timedelta(days=2)),
                            anchor(Q2, "small_domestic", 40.0, week(14) + timedelta(days=2))]
        row = [r for r in self.rows() if r.week_ending == week(19)][0]
        stale = gr.Row(**{**row.__dict__, "large_anchor_quarter": Q1})
        with self.assertRaises(StaleReadError):
            gr.verify([stale], pair)


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = gr.tracked_inputs()
        cls.rows = gr.load_extract(EXTRACT)
        cls.coverage = json.loads((DIRECTORY / gr.COVERAGE_NAME).read_text(encoding="utf-8"))

    def test_the_tracked_extract_is_what_the_tracked_inputs_build(self):
        rows, holes = gr.build(**self.inputs)
        self.assertEqual(gr.write_extract(rows), EXTRACT.read_bytes())
        self.assertEqual(gr.coverage(rows, holes, self.inputs["prints"], self.inputs), self.coverage)

    def test_every_h8_week_is_a_row_or_a_listed_hole(self):
        weeks = len(self.inputs["prints"])
        self.assertEqual(len(self.rows) + sum(self.coverage["reasons"].values()), weeks)
        self.assertEqual(len(self.coverage["holes"]), sum(self.coverage["reasons"].values()))
        self.assertTrue(set(self.coverage["reasons"]) <= set(gr.REFUSALS))

    def test_every_row_verifies_against_the_anchor_extract(self):
        gr.verify(self.rows, self.inputs["anchors"])

    def test_no_row_is_public_after_the_development_end(self):
        from repo_liquidity import development

        self.assertTrue(all(not development.is_locked(r.public_at.date()) for r in self.rows))

    def test_a_week_with_no_public_anchor_is_earlier_than_the_first_week_both_anchors_are(self):
        """The finding the series records: under the ruled vintage reading no group is public before the quarter's slowest
        member has updated, so the first weeks have no anchor."""
        first = max(min(a.available_from for a in self.inputs["anchors"] if a.group == group) for group in rca.GROUPS)
        by_week = {p.week_ending: p for p in self.inputs["prints"]}
        for hole in self.coverage["holes"]:
            if hole["reason"] == "no_anchor_public":
                release = by_week[date.fromisoformat(hole["week_ending"])].release_date
                self.assertLess(h8.available_at(release), first)

    def test_a_week_that_crosses_a_break_has_both_anchors_public(self):
        by_week = {p.week_ending: p for p in self.inputs["prints"]}
        for hole in self.coverage["holes"]:
            if hole["reason"] == "break_between_anchor_and_week":
                release = by_week[date.fromisoformat(hole["week_ending"])].release_date
                for group in rca.GROUPS:
                    self.assertIsNotNone(rca.latest_public(self.inputs["anchors"], group, h8.available_at(release)))

    def test_the_diagnostic_without_the_break_refusal_is_recorded_and_is_not_a_series(self):
        diag = self.coverage["diagnostic_without_break_refusal"]
        self.assertEqual(diag["rows"], self.coverage["reasons"].get("break_between_anchor_and_week", 0))

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
