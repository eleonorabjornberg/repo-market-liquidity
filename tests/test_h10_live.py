"""H10 prospective confirmation: the live entry point and the method digest (directive #87; `docs/research/h10-live-interface.md`).

`h10_live.attribute_onset` attributes one onset with the frozen method, reading only what was public at the report instant.
Nothing is registered, scored or logged here, and no real onset after 2026-09-03 is read. The unit tests run on a synthetic
panel with a stub rule (a publication lag we choose); the panel tests run the real rule on the tracked panel.
"""

import hashlib
import json
import pathlib
import random
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from repo_model.splits import LookAheadError

from repo_liquidity import PARENT_COMMIT, attribution, h10_apply, h10_live
from repo_liquidity.attribution import DRIVERS_WITH_ON_RRP, SPREAD, WINDOW_DAYS

from lockbox_helper import reclosed_near_blind

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "decisions" / "h10-method.md"
BASE = datetime(2026, 1, 1)

#: The digest PR #78 published as "method record sha256": the record file alone, as it stood after H10 step 2.
PUBLISHED_IN_78 = "cae658c6d9a895d4db8f6427c81a11f7310fc79377528d71806e9f209c28f126"
#: The commit that file had that digest at, and the commit that amended it (section 10, the 2 bp placebo floor, PR #88).
RECORD_COMMIT_OF_78 = "9a32493"
RECORD_AMENDED_BY_88 = "9fee94f"


def make_rows(n=300, onset=100, seed=3, start=date(2025, 1, 1)):
    """A synthetic daily panel: a spread of a few bp that the drivers carry, with a jump over the five days from `onset`, drivers that carry it, one row per day."""
    rng = random.Random(seed)
    drivers = {name: [rng.gauss(0, 1) for _ in range(n)] for name in DRIVERS_WITH_ON_RRP}
    drivers["quarter_end"] = [1.0 if t % 40 == 7 else 0.0 for t in range(n)]
    spread = [1.0 + 0.5 * sum(drivers[name][t] for name in drivers if name != "quarter_end") + rng.gauss(0, 1.8) for t in range(n)]
    for t in range(onset, onset + WINDOW_DAYS):
        drivers["tga"][t] += 4.0
        spread[t] += 10.0
    rows = []
    for t in range(n):
        values = {name: drivers[name][t] for name in drivers}
        values["on_rrp"] = 50.0 + 10 * drivers["on_rrp"][t]
        rows.append(SimpleNamespace(date=start + timedelta(days=t), spread_bps=spread[t], values=values))
    return rows


def stub_rule(lag_days=2):
    """A rule under which the day at position i is public at the start of day i + lag; the report instant of index r is day r."""

    def availability(dates, fields, i):
        return BASE + timedelta(days=i + lag_days)

    return SimpleNamespace(
        groups=[SimpleNamespace(feature=SPREAD, kind="data", fields=("s",))],
        decision_instant=lambda dates, i: BASE + timedelta(days=i),
        availability=availability,
    )


#: `registered_digest` is the digest of this tree: these tests exercise the computation, not the registration guard (#200),
#: which `tests/test_h10_registration.py` tests, so that a refusal here is never the guard's.
FAST = dict(draws=20, null_draws=20, registered_digest=h10_live.method_digest())


def without_stamp(row):
    """The row without the sha256 of the rows given, which by design moves with rows the method never reads."""
    return {key: value for key, value in row.items() if key != "panel_rows_sha256"}


class EntryPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = make_rows()
        cls.onset = cls.rows[100].date
        cls.rule = stub_rule()

    def attribute(self, rows=None, report_offset=10, **kwargs):
        rows = self.rows if rows is None else rows
        report = rows[100 + report_offset].date
        return h10_live.attribute_onset(rows[: 100 + report_offset + 1], self.rule, self.onset, report, **{**FAST, **kwargs})

    def test_one_onset_gives_a_json_row_in_the_published_tables_columns(self):
        row = self.attribute()
        json.dumps(row)
        self.assertEqual(row["status"], "attributed")
        self.assertEqual(row["onset"], self.onset.isoformat())
        self.assertEqual(row["report_day"], self.rows[110].date.isoformat())
        record = json.loads((ROOT / "results" / "h10" / "development.json").read_text(encoding="utf-8"))
        attributed = next(e for e in record["episodes"] if e["status"] == "attributed")
        self.assertEqual(set(row) - set(attributed), {"method_digest", "parent_commit", "parent_panel_sha256", "last_day_read",
                                                      "placebo_floored", "panel_rows_sha256", "rows_are_published_panel",
                                                      "imported_parent_commit", "imported_parent_clean", "parent_override"})
        self.assertEqual(set(attributed) - set(row), set())
        self.assertEqual(set(row["shares"]), set(DRIVERS_WITH_ON_RRP))
        self.assertEqual(set(row["shares"]["tga"]), {"point", "low", "high"})

    def test_the_onset_is_attributed_by_the_method_not_by_a_second_implementation(self):
        row = self.attribute()
        series = attribution.series_from_rows(self.rows[: h10_live.last_public_start(self.rule, [r.date for r in self.rows], 110, 100) + WINDOW_DAYS],
                                              DRIVERS_WITH_ON_RRP)
        point = attribution.point_attribution(series, 100, drivers=DRIVERS_WITH_ON_RRP)
        self.assertAlmostEqual(row["residual"]["point"], point.residual_share, places=9)
        self.assertAlmostEqual(row["explained_share"], point.explained_share, places=9)
        self.assertAlmostEqual(sum(s["point"] for s in row["shares"].values()) + row["residual"]["point"], 1.0, places=6)

    def test_an_onset_more_than_ten_panel_days_before_the_report_is_refused(self):
        """Guard (plan, Q7): an onset is reported within 10 business days of its onset.

        Recorded mutation (directive #87): in `h10_live.attribute_onset`, `if report_index - onset_index > REPORT_DAYS:`
        changed to `> REPORT_DAYS + 1`. `test_an_onset_more_than_ten_panel_days_before_the_report_is_refused` then fails
        with AssertionError: ValueError not raised.
        """
        self.assertEqual(self.attribute(report_offset=10)["status"], "attributed")
        with self.assertRaises(ValueError):
            self.attribute(report_offset=11)

    def test_a_report_before_the_onset_or_off_the_panel_is_refused(self):
        with self.assertRaises(ValueError):
            h10_live.attribute_onset(self.rows[:100], self.rule, self.onset, self.rows[99].date, **FAST)
        with self.assertRaises(ValueError):
            h10_live.attribute_onset(self.rows, self.rule, self.onset, date(2031, 1, 1), **FAST)

    def test_a_day_that_is_not_an_onset_is_refused(self):
        with self.assertRaises(ValueError):
            h10_live.attribute_onset(self.rows[:111], self.rule, self.rows[101].date, self.rows[110].date, **FAST)
        with self.assertRaises(ValueError):
            h10_live.attribute_onset(self.rows[:111], self.rule, date(2020, 1, 1), self.rows[110].date, **FAST)

    def test_a_window_not_public_at_the_report_instant_is_leakage(self):
        """Leakage guard: the onset's own window must be public at the report instant (`h10-method.md` section 6).

        With a two-day publication lag, a report on day 100 + 3 has seen the spread only through day 101. Recorded mutation
        (directive #87): in `h10_live.attribute_onset`, the call `attribution.attribute(...)` replaced by
        `attribution.attribute_synthetic(series, start, drivers=..., draws=..., seed=...)`. This test then fails with
        AssertionError: LookAheadError not raised.
        """
        with self.assertRaises(LookAheadError):
            self.attribute(report_offset=3)
        self.assertEqual(self.attribute(report_offset=10)["status"], "attributed")

    def test_the_fit_and_the_null_use_only_windows_public_at_the_report_instant(self):
        """Leakage guard: rows the report instant has not seen, between the last public day and the report day, change nothing.

        With a two-day lag and a report on day 110, day 108 is the last public day; days 109 and 110 are not. Recorded
        mutation (directive #87): in `h10_live.attribute_onset`, the slice `rows[: last_start + WINDOW_DAYS]` replaced by
        `rows[: report_index + 1]`. This test then fails with AssertionError: {...} != {...} (the unseen rows move the fit).
        """
        altered = list(self.rows)
        for t in (109, 110):
            values = dict(altered[t].values, tga=altered[t].values["tga"] + 40.0, reserve_balances=altered[t].values["reserve_balances"] - 30.0)
            altered[t] = SimpleNamespace(date=altered[t].date, spread_bps=altered[t].spread_bps + 3.0, values=values)
        self.assertEqual(without_stamp(self.attribute(altered)), without_stamp(self.attribute()))

    def test_the_rows_handed_in_end_at_the_report_day(self):
        """The rows the live job hands in end on the report day: rows beyond it are refused, not trimmed (finding on 2500ecd)."""
        altered = list(self.rows[:111])
        for t in (109, 110):
            altered[t] = SimpleNamespace(date=altered[t].date, spread_bps=99.0, values=dict(altered[t].values, tga=1e6))
        self.assertEqual(without_stamp(self.attribute(altered)), without_stamp(self.attribute(self.rows[:111])))

    def test_a_publicly_visible_row_does_move_the_result(self):
        altered = list(self.rows)
        values = dict(altered[60].values, tga=altered[60].values["tga"] + 40.0)
        altered[60] = SimpleNamespace(date=altered[60].date, spread_bps=altered[60].spread_bps + 4.0, values=values)
        self.assertNotEqual(self.attribute(altered)["explained_share"], self.attribute()["explained_share"])

    def test_a_row_after_the_report_instant_is_leakage(self):
        """Leakage guard: no day after the report instant is read; a row dated after `report_date` is refused before any fit,
        placebo or null is built (ruling on 2500ecd, replacing the lockbox refusal).

        Recorded mutation: in `h10_live.check_no_row_after_report`, `if late:` changed to `if False:`. This test then fails
        with AssertionError: LookAheadError not raised (the late rows are cut off silently).
        """
        rows = make_rows(start=date(2026, 9, 4) - timedelta(days=50))
        with mock.patch.object(attribution, "attribute", side_effect=AssertionError("fitted")), \
                mock.patch.object(attribution, "selection_null", side_effect=AssertionError("null built")):
            with self.assertRaises(LookAheadError) as caught:
                h10_live.attribute_onset(rows[:112], self.rule, rows[100].date, rows[110].date, **FAST)
        self.assertIn(rows[111].date.isoformat(), str(caught.exception))
        with self.assertRaises(LookAheadError):
            h10_live.attribute_onset(self.rows, self.rule, self.onset, self.rows[110].date, **FAST)

    def test_a_live_attribution_reaching_into_the_blind_tier_succeeds(self):
        """The blind tier (from 2026-09-04) is not refused (Eleonora, 30 October 2026, repo-market-model#1324, option 2): a
        locked tier that no comparison scores does not refuse the live path. The report day is in it."""
        rows = make_rows(start=date(2026, 9, 4) - timedelta(days=50))
        self.assertLess(rows[49].date, date(2026, 9, 4))
        self.assertGreaterEqual(rows[50].date, date(2026, 9, 4))
        row = h10_live.attribute_onset(rows[:111], self.rule, rows[100].date, rows[110].date, **FAST)
        self.assertEqual(row["status"], "attributed")
        self.assertGreaterEqual(date.fromisoformat(row["report_day"]), date(2026, 9, 4))

    def test_a_day_in_a_tier_that_a_comparison_scores_is_refused(self):
        """Leakage guard: a locked tier the live path may not read stays refused through `lockbox.require_unlocked`. Today no
        locked tier is scored by a comparison (the near-blind tier is opened, #151; the blind tier is read, by ruling), so the
        declaration is patched to lock the near-blind tier again, and the same rows succeed under the tracked declaration.

        Recorded mutation: in `h10_live.check_scored_tiers`, the call `lockbox.require_unlocked(scored, ...)` replaced by `pass`.
        This test then fails with AssertionError: LookAheadError not raised.
        """
        rows = make_rows(start=date(2026, 1, 1))[:111]
        self.assertEqual(h10_live.attribute_onset(rows, self.rule, rows[100].date, rows[110].date, **FAST)["status"], "attributed")
        with reclosed_near_blind():
            with self.assertRaises(LookAheadError) as caught:
                h10_live.attribute_onset(rows, self.rule, rows[100].date, rows[110].date, **FAST)
        self.assertIn("near_blind", str(caught.exception))

    def test_the_development_path_still_refuses_a_locked_day(self):
        """`h10_apply` keeps `check_development` (development ends on 2025-12-31)."""
        with self.assertRaises(LookAheadError):
            attribution.check_development([date(2026, 9, 4)])

    def test_a_not_attributable_onset_is_reported_with_its_reason_never_dropped(self):
        flat = [SimpleNamespace(date=r.date, spread_bps=r.spread_bps, values=r.values) for r in self.rows[:111]]
        for t in range(100, 105):
            flat[t] = SimpleNamespace(date=flat[t].date, spread_bps=flat[t].spread_bps, values=dict(flat[t].values, tga=None))
        row = self.attribute(flat)
        self.assertEqual(row["status"], "not attributable")
        self.assertTrue(row["reason"])
        self.assertFalse(row["counted"])


class FlooredPlaceboTests(unittest.TestCase):
    """Finding #119, point 3: `h10-method.md` section 10, rule 3, reads the placebo with and without the 2 bp floor."""

    @classmethod
    def setUpClass(cls):
        cls.rows = make_rows()
        cls.rule = stub_rule()
        cls.row = h10_live.attribute_onset(cls.rows[:111], cls.rule, cls.rows[100].date, cls.rows[110].date, **FAST)

    def test_the_row_carries_both_readings_under_the_published_tables_names(self):
        """The unfloored reading keeps `placebo`, the name of `results/h10/development.json`; the floored one is
        `placebo_floored`, with the keys of the `floored` entries of `results/h10/placebo_floor_2bp.json`.

        Recorded mutation (directive #121): in `h10_live.attribute_onset`, `placebo_floored=h10_apply.floored_placebo_summary(...)`
        replaced by `placebo_floored=h10_apply.placebo_summary(...)`. This test then fails with AssertionError (the floored reading has no
        `excluded` key, and differs from the method's own floored summary).
        """
        development = json.loads((ROOT / "results" / "h10" / "development.json").read_text(encoding="utf-8"))
        floor = json.loads((ROOT / "results" / "h10" / "placebo_floor_2bp.json").read_text(encoding="utf-8"))
        unfloored = next(e for e in development["episodes"] if e["status"] == "attributed")["placebo"]
        floored = next(e for e in floor["episodes"] if e["status"] == "attributed")["floored"]
        self.assertEqual(set(self.row["placebo"]), set(unfloored))
        self.assertEqual(set(self.row["placebo_floored"]), set(floored))
        self.assertEqual(self.row["placebo_floored"]["windows"], self.row["placebo"]["windows"])
        self.assertLessEqual(self.row["placebo_floored"]["attributed"], self.row["placebo"]["attributed"])

    def test_the_floored_reading_is_the_methods_own_over_the_same_windows(self):
        dates = [r.date for r in self.rows]
        last = h10_live.last_public_start(self.rule, dates, 110, 100)
        visible = self.rows[: last + WINDOW_DAYS]
        series = attribution.series_from_rows(visible, DRIVERS_WITH_ON_RRP)
        onsets = attribution.cross_check_onsets(visible)
        windows = [attribution.point_attribution(series, s, drivers=DRIVERS_WITH_ON_RRP)
                   for s in attribution.placebo_starts(series, onsets, attribution.PLACEBO_WINDOWS, attribution.SEED)[100]]
        explained = self.row["explained_share"]
        self.assertEqual(self.row["placebo"], h10_apply.placebo_summary(windows, explained))
        self.assertEqual(self.row["placebo_floored"], h10_apply.floored_placebo_summary(windows, explained))
        self.assertGreater(self.row["placebo_floored"]["excluded"], 0)


class StampTests(unittest.TestCase):
    """Finding #119, point 2: the row names the inputs it was computed from, not only the constants."""

    @classmethod
    def setUpClass(cls):
        cls.rows = make_rows()
        cls.rule = stub_rule()

    def attribute(self, rows=None, **kwargs):
        rows = self.rows[:111] if rows is None else rows
        return h10_live.attribute_onset(rows, self.rule, rows[100].date, rows[110].date, **{**FAST, **kwargs})

    def test_the_row_carries_a_sha256_of_the_rows_it_was_given(self):
        """The rows given are hashed whole (also the days between the last public day and the report, which are never read): a caller that hands a
        different panel gets a different stamp.

        Recorded mutation (directive #121): in `h10_live.attribute_onset`, `rows_sha256(rows)` replaced by
        `rows_sha256(visible)`. This test then fails with AssertionError: '66eca8c8…' != '89…' (the stamp does not cover the rows
        given).
        """
        row = self.attribute()
        self.assertEqual(row["panel_rows_sha256"], h10_live.rows_sha256(self.rows[:111]))
        self.assertRegex(row["panel_rows_sha256"], r"^[0-9a-f]{64}$")
        altered = list(self.rows[:111])
        altered[110] = SimpleNamespace(date=altered[110].date, spread_bps=altered[110].spread_bps + 1.0, values=altered[110].values)
        self.assertNotEqual(self.attribute(altered)["panel_rows_sha256"], row["panel_rows_sha256"])
        self.assertEqual(self.attribute()["panel_rows_sha256"], row["panel_rows_sha256"])

    def test_rows_that_are_not_the_pinned_published_panel_say_so(self):
        """Recorded mutation (directive #121): in `h10_live.attribute_onset`, `rows_are_published_panel` set from
        `rows_sha256(rows) == published_panel_rows_sha256()` replaced by `True`. This test then fails with AssertionError:
        True is not false (a synthetic panel is called the published one).
        """
        self.assertIs(self.attribute()["rows_are_published_panel"], False)

    def test_the_row_names_the_repo_model_commit_actually_imported(self):
        row = self.attribute()
        self.assertEqual(row["imported_parent_commit"], h10_live.imported_parent_commit())
        self.assertEqual(row["imported_parent_commit"], PARENT_COMMIT)
        self.assertIs(row["imported_parent_clean"], True)
        self.assertIs(row["parent_override"], False)

    def test_a_run_on_a_repo_model_that_is_not_at_the_pin_is_refused(self):
        """Guard: the digest names parent code at `PARENT_COMMIT`, so a run whose imported `repo_model` is another commit is
        refused (`ValueError`), unless an explicit override is passed; the override is recorded in the row.

        Recorded mutation (directive #121): in `h10_live.check_parent_at_pin`, `if commit != PARENT_COMMIT:` changed to
        `if False:`. This test then fails with AssertionError: ValueError not raised.
        """
        with mock.patch.object(h10_live, "imported_parent_commit", lambda: "1" * 40):
            with self.assertRaises(ValueError):
                self.attribute()
            row = self.attribute(allow_unpinned_parent=True)
        self.assertEqual(row["imported_parent_commit"], "1" * 40)
        self.assertIs(row["parent_override"], True)

    def test_a_repo_model_with_local_changes_is_refused(self):
        """Guard: a checkout at the pin with modified tracked files is not the pin.

        Recorded mutation (directive #121): in `h10_live.check_parent_at_pin`, `if not clean:` changed to `if False:`. This
        test then fails with AssertionError: ValueError not raised.
        """
        with mock.patch.object(h10_live, "imported_parent_clean", lambda: False):
            with self.assertRaises(ValueError):
                self.attribute()
            row = self.attribute(allow_unpinned_parent=True)
        self.assertIs(row["imported_parent_clean"], False)
        self.assertIs(row["parent_override"], True)

    def test_a_repo_model_that_is_not_a_git_checkout_is_refused(self):
        """Guard: an installed copy cannot name its commit, so it is not the pin.

        Recorded mutation (directive #121): in `h10_live.imported_parent_commit`, the `except (OSError, subprocess.CalledProcessError):
        return None` replaced by `return PARENT_COMMIT`. This test then fails with AssertionError: '8fd2cf8c…' is not None.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(h10_live, "parent_root", lambda: pathlib.Path(tmp)):
                self.assertIsNone(h10_live.imported_parent_commit())
                self.assertIsNone(h10_live.imported_parent_clean())
                with self.assertRaises(ValueError):
                    h10_live.check_parent_at_pin(allow_unpinned_parent=False)

    def test_the_check_is_made_before_anything_is_computed(self):
        with mock.patch.object(h10_live, "imported_parent_commit", lambda: "1" * 40):
            with mock.patch.object(attribution, "attribute", side_effect=AssertionError("computed")):
                with self.assertRaises(ValueError):
                    self.attribute()


class MethodDigestTests(unittest.TestCase):
    def test_the_digest_is_a_sha256_in_a_fixed_order_of_parts(self):
        digest = h10_live.method_digest()
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        names = [name for name, _ in h10_live.method_parts()]
        self.assertEqual(names, ["record:docs/decisions/h10-method.md", "code:src/repo_liquidity/attribution.py",
                                 "code:src/repo_liquidity/h10_apply.py", "code:src/repo_liquidity/h10_live.py",
                                 f"parent@{PARENT_COMMIT}:src/repo_model/onset.py",
                                 f"parent@{PARENT_COMMIT}:src/repo_model/pressure.py",
                                 f"parent@{PARENT_COMMIT}:src/repo_model/asof.py",
                                 f"parent@{PARENT_COMMIT}:src/repo_model/contract.py",
                                 f"parent@{PARENT_COMMIT}:src/repo_model/metrics.py", "constants"])
        self.assertEqual(digest, h10_live.method_digest())

    def test_a_decided_constant_moves_the_digest(self):
        before = h10_live.method_digest()
        with mock.patch.object(attribution, "BASELINE_DAYS", attribution.BASELINE_DAYS + 1):
            self.assertNotEqual(h10_live.method_digest(), before)
        with mock.patch.object(h10_apply, "REPORT_DAYS", 11):
            self.assertNotEqual(h10_live.method_digest(), before)
        with mock.patch.object(h10_live, "ON_RRP_DEPLETION_BREAK_BN", 101.0):
            self.assertNotEqual(h10_live.method_digest(), before)
        self.assertEqual(h10_live.method_digest(), before)

    def test_a_changed_code_file_or_record_moves_the_digest(self):
        before = h10_live.method_digest()
        tmp = pathlib.Path(self.id() + ".tmp")
        try:
            tmp.write_text("changed", encoding="utf-8")
            files = tuple(h10_live.METHOD_FILES)
            for i in range(len(files)):
                with self.subTest(part=files[i][0]):
                    with mock.patch.object(h10_live, "METHOD_FILES", files[:i] + ((files[i][0], tmp),) + files[i + 1:]):
                        self.assertNotEqual(h10_live.method_digest(), before)
        finally:
            tmp.unlink()

    def test_the_live_code_is_a_part_of_the_digest(self):
        """Finding #119, point 4: the module that cuts the rows at the report instant, splits the regimes and sets `counted`
        decides a live result, so it is in the digest.

        Recorded mutation (directive #121): in `h10_live.METHOD_FILES`, the entry `("code:src/repo_liquidity/h10_live.py", ...)`
        deleted. This test then fails with AssertionError: 'code:src/repo_liquidity/h10_live.py' not found in the part names.
        """
        names = [name for name, _ in h10_live.method_parts()]
        self.assertIn("code:src/repo_liquidity/h10_live.py", names)
        own = dict(h10_live.method_parts())["code:src/repo_liquidity/h10_live.py"]
        self.assertEqual(own, pathlib.Path(h10_live.__file__).read_bytes())

    def test_each_parent_file_moves_the_digest_and_is_named_by_the_pin(self):
        """Finding #119, point 4: the parent code the result depends on is in the digest, named by the pinned commit and the
        file read: the onset rule (`onset.py`), the pressure onsets it is cross-checked with (`pressure.py`), the as-of rule
        `InformationRule` (`asof.py`), `ON_RRP_DEPLETION_BREAK_BN` (`contract.py`) and the stationary bootstrap (`metrics.py`).

        Recorded mutations (directive #121), each making this test fail with AssertionError (the digest does not move, in the
        subTest of that file): in `h10_live.method_parts`, the generator over `PARENT_METHOD_FILES` given
        `if relative != "src/repo_model/onset.py"`; likewise for "src/repo_model/pressure.py", "src/repo_model/asof.py",
        "src/repo_model/contract.py" and "src/repo_model/metrics.py".
        And for the pin: in `h10_live.method_parts`, the part name `f"parent@{PARENT_COMMIT}:{relative}"` changed to
        `f"parent:{relative}"`; the second half of this test then fails with AssertionError (a changed pin gives the same digest).
        """
        before = h10_live.method_digest()
        self.assertEqual(len(h10_live.PARENT_METHOD_FILES), 5)
        for relative in h10_live.PARENT_METHOD_FILES:
            with self.subTest(file=relative):
                with tempfile.TemporaryDirectory() as tmp:
                    copy = pathlib.Path(tmp)
                    for other in h10_live.PARENT_METHOD_FILES:
                        (copy / other).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(h10_live.parent_root() / other, copy / other)
                    self.assertEqual(self.digest_with_parent(copy), before)
                    with open(copy / relative, "ab") as handle:
                        handle.write(b"\n# changed\n")
                    self.assertNotEqual(self.digest_with_parent(copy), before)
        with mock.patch.object(h10_live, "PARENT_COMMIT", "0" * 40):
            self.assertNotEqual(h10_live.method_digest(), before)

    @staticmethod
    def digest_with_parent(root):
        with mock.patch.object(h10_live, "parent_root", lambda: root):
            return h10_live.method_digest()

    def test_the_record_part_is_the_sha256_of_the_record_file(self):
        self.assertEqual(h10_live.record_sha256(), hashlib.sha256(RECORD.read_bytes()).hexdigest())

    def test_pr_78s_digest_was_the_record_alone_and_the_record_has_since_been_amended(self):
        """The digest published in PR #78 (`cae658c6…f126`) is the sha256 of the method record file alone, as it stood after
        H10 step 2. The record was amended afterwards (section 10, the 2 bp placebo floor, PR #88), so today's record
        digest differs, and `method_digest` (record, code and constants together) is a different quantity by construction.
        Where the git history has both commits, the test reproduces #78's number from the older record.
        """
        self.assertNotEqual(h10_live.record_sha256(), PUBLISHED_IN_78)
        self.assertNotEqual(h10_live.method_digest(), PUBLISHED_IN_78)
        shown = []
        for commit in (RECORD_COMMIT_OF_78, RECORD_AMENDED_BY_88):
            run = subprocess.run(["git", "show", f"{commit}:docs/decisions/h10-method.md"], cwd=ROOT, capture_output=True)
            if run.returncode != 0:
                self.skipTest("the git history does not hold the record's earlier versions")
            shown.append(hashlib.sha256(run.stdout).hexdigest())
        self.assertEqual(shown[0], PUBLISHED_IN_78)
        self.assertNotEqual(shown[1], PUBLISHED_IN_78)

    def test_the_row_carries_the_digest_and_the_parent_pin(self):
        row = h10_live.attribute_onset(make_rows()[:111], stub_rule(), date(2025, 1, 1) + timedelta(days=100),
                                       date(2025, 1, 1) + timedelta(days=110), **FAST)
        self.assertEqual(row["method_digest"], h10_live.method_digest())


class PanelTests(unittest.TestCase):
    """The real rule on the tracked panel, to the development end (no real onset after 2026-09-03 is read)."""

    @classmethod
    def setUpClass(cls):
        cls.rows, _ = h10_apply.load_development()
        cls.onsets = attribution.cross_check_onsets(cls.rows)

    def test_a_development_onset_is_attributed_at_its_report_day_under_the_real_rule(self):
        start = self.onsets[3]
        with h10_apply.real_rule() as rule:
            row = h10_live.attribute_onset(self.rows[: start + 11], rule, self.rows[start].date, self.rows[start + 10].date, **FAST)
        self.assertIn(row["status"], ("attributed", "not attributable"))
        self.assertEqual(row["onset"], self.rows[start].date.isoformat())
        self.assertEqual(row["regime"] in ("depleted", "abundant"), True)

    def test_the_rows_are_called_the_published_panel_only_when_they_are_the_whole_of_it(self):
        """The rows handed in end on the report day (the look-ahead guard), so they are the whole published panel only when the
        report day is its last day. The stamp compares the rows with the whole panel; it is never a prefix match."""
        start = self.onsets[3]
        rows = self.rows[: start + 11]
        with h10_apply.real_rule() as rule:
            row = h10_live.attribute_onset(rows, rule, rows[start].date, rows[start + 10].date, **FAST)
            self.assertIs(row["rows_are_published_panel"], False)
            self.assertEqual(row["panel_rows_sha256"], h10_live.rows_sha256(rows))
            with mock.patch.object(h10_live, "published_panel_rows_sha256", return_value=h10_live.rows_sha256(rows)):
                row = h10_live.attribute_onset(rows, rule, rows[start].date, rows[start + 10].date, **FAST)
            self.assertIs(row["rows_are_published_panel"], True)
        self.assertEqual(h10_live.published_panel_rows_sha256(), h10_live.rows_sha256(self.rows))

    def test_a_report_the_real_rule_has_not_yet_seen_the_window_in_is_leakage(self):
        start = self.onsets[3]
        with h10_apply.real_rule() as rule:
            with self.assertRaises(LookAheadError):
                h10_live.attribute_onset(self.rows[: start + 2], rule, self.rows[start].date, self.rows[start + 1].date, **FAST)


if __name__ == "__main__":
    unittest.main()
