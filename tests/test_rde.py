"""The NY Fed's reserve demand elasticity, an external check on H7m goalposts 1 and 3 (#132).

The parser is tested on small synthetic workbooks; the tracked extract, its declaration and the guards are tested on the
real extract cut by `scripts/extract_rde.py` from the stored workbook. The check is reported and never deciding, and no
test scores anything.
"""

import hashlib
import io
import json
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, development, rde

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "rde"
EXTRACT = DIRECTORY / rde.EXTRACT_NAME
HISTORY = DIRECTORY / rde.HISTORY_NAME
NEW_YORK = rde.NEW_YORK
EXCEL_ZERO = date(1899, 12, 30)


def workbook(estimates, cover="Updated on October 5 for release on October 15", header=rde.HEADER, raw=None):
    """A workbook with the two sheets and the shared strings the parser reads.

    `estimates`: (date, [five values]) pairs; `raw` replaces a row's text values by name when given.
    """
    strings = []

    def shared(text):
        if text not in strings:
            strings.append(text)
        return strings.index(text)

    def cell(ref, value, string=False):
        return (f'<c r="{ref}" t="s"><v>{shared(value)}</v></c>' if string else f'<c r="{ref}"><v>{value}</v></c>')

    rows = ["<row r=\"1\">" + "".join(cell(f"{'ABCDEF'[i]}1", text, True) for i, text in enumerate(header)) + "</row>"]
    for number, (day, values) in enumerate(estimates, start=2):
        texts = [str((day - EXCEL_ZERO).days)] + [str(v) for v in values]
        rows.append(f'<row r="{number}">' + "".join(cell(f"{'ABCDEF'[i]}{number}", text) for i, text in enumerate(texts)) + "</row>")
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = f'<worksheet xmlns="{main}"><sheetData>' + "".join(rows) + "</sheetData></worksheet>"
    cover_sheet = (f'<worksheet xmlns="{main}"><sheetData><row r="1">{cell("A1", cover, True)}</row></sheetData></worksheet>')
    shared_xml = f'<sst xmlns="{main}">' + "".join(f"<si><t>{text}</t></si>" for text in strings) + "</sst>"
    book = (f'<workbook xmlns="{main}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{rde.COVER}" sheetId="2" r:id="rId1"/><sheet name="{rde.SHEET}" sheetId="1" r:id="rId2"/>'
            f'</sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
            '</Relationships>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", book)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/sharedStrings.xml", shared_xml)
        archive.writestr("xl/worksheets/sheet1.xml", cover_sheet)
        archive.writestr("xl/worksheets/sheet2.xml", sheet)
    return buffer.getvalue()


LAST = date(2026, 10, 5)
VALUES = ["-0.37141199999999996", "-0.73244500000000001", "2.5121999999999998E-2", "-0.55650100000000002", "-0.179512"]


class ScheduleTests(unittest.TestCase):
    def test_the_third_thursday(self):
        self.assertEqual(rde.third_thursday(2024, 10), date(2024, 10, 17))
        self.assertEqual(rde.third_thursday(2026, 10), date(2026, 10, 15))
        self.assertEqual(rde.third_thursday(2025, 1), date(2025, 1, 16))
        self.assertEqual(rde.third_thursday(2026, 1), date(2026, 1, 15))  # the month starts on a Thursday

    def test_availability_is_at_noon_new_york_time(self):
        """The launch press release says "around 10:00 A.M."; availability is declared at 12:00, the conservative reading."""
        self.assertEqual(rde.RELEASE_TIME, time(12, 0))
        self.assertEqual(rde.release_for(date(2026, 8, 6)), datetime(2026, 8, 20, 12, 0, tzinfo=NEW_YORK))

    def test_nothing_is_public_before_the_launch(self):
        """Leakage guard: an estimate dated before the product existed is read from the launch and no earlier.

        Recorded mutation (20 October 2026): in `rde.release_for`, the starting month
        `max((estimate_date.year, estimate_date.month), (LAUNCH_DATE.year, LAUNCH_DATE.month))` replaced by
        `(estimate_date.year, estimate_date.month)`. This test then fails with `ValueError: the parent's FOMC calendar holds no
        scheduled meeting public at 2010-02-18 12:00:00`: the 2010 estimate is sent to the release after its own date, where
        the parent's calendar shows no meeting yet (re-recorded 22 October 2026 for #162; the guard that refused it was the
        saved page's calendar-years check).
        """
        self.assertEqual(rde.release_for(date(2010, 1, 20)), rde.LAUNCH)
        self.assertEqual(rde.release_for(date(2024, 10, 2)), rde.LAUNCH)
        self.assertEqual(rde.LAUNCH, datetime(2024, 10, 17, 12, 0, tzinfo=NEW_YORK))

    def test_an_estimate_is_public_at_the_first_release_whose_data_is_as_of_its_date_or_later(self):
        """Leakage guard (the ruling of 19 October 2026, change 4): the launch release carried data as of Friday 11
        October 2024, the stored one as of 5 October 2026 (its cover sheet); an estimate is not read from an earlier release.

        Recorded mutation (20 October 2026): in `rde.release_for`, the comparison `as_of_date(year, month) < estimate_date`
        replaced by `as_of_date(year, month) < estimate_date - timedelta(days=1)`. This test then fails with
        `AssertionError: datetime.date(2024, 10, 17) != datetime.date(2024, 11, 21)`: the estimate dated the day after
        the launch release's as-of date is read at the launch.
        """
        self.assertEqual(rde.release_for(date(2024, 10, 11)).date(), date(2024, 10, 17))
        self.assertEqual(rde.release_for(date(2024, 10, 12)).date(), date(2024, 11, 21))
        self.assertEqual(rde.release_for(date(2026, 10, 5)).date(), date(2026, 10, 15))
        self.assertEqual(rde.release_for(date(2026, 10, 6)).date(), date(2026, 11, 19))

    def test_a_release_with_no_recorded_as_of_date_is_assumed_ten_days_earlier_than_its_release(self):
        """The one declared conservative lag: the larger of the two recorded gaps (6 days at the launch, 10 in October 2026)."""
        self.assertEqual(rde.UNRECORDED_AS_OF_LAG_DAYS, 10)
        self.assertEqual(rde.as_of_date(2026, 8), date(2026, 8, 20) - timedelta(days=10))
        self.assertEqual(rde.release_for(date(2026, 8, 10)).date(), date(2026, 8, 20))
        self.assertEqual(rde.release_for(date(2026, 8, 11)).date(), date(2026, 9, 18))  # 17 September is in the blackout
        self.assertEqual(rde.release_for(date(2025, 12, 10)).date(), date(2026, 1, 15))  # across the year end

    def test_the_recorded_as_of_dates_are_the_sourced_ones(self):
        self.assertEqual(rde.AS_OF_RECORDED, {date(2024, 10, 17): date(2024, 10, 11), date(2026, 10, 15): date(2026, 10, 5)})

    def test_the_release_is_never_before_the_estimate_date(self):
        day = date(2024, 10, 9)
        while day < date(2027, 1, 1):
            self.assertGreater(rde.release_for(day).date(), day)
            day += timedelta(days=1)


class BlackoutTests(unittest.TestCase):
    """The FOMC blackout (the launch press release of 17 October 2024; the ruling of 19 October 2026, change 2)."""

    #: #136's table: the third Thursday read as the release before the fallback, and the first business day after the blackout.
    MOVED = {date(2024, 12, 19): date(2024, 12, 20), date(2025, 3, 20): date(2025, 3, 21),
             date(2025, 6, 19): date(2025, 6, 20), date(2025, 9, 18): date(2025, 9, 19),
             date(2026, 3, 19): date(2026, 3, 20),
             date(2026, 6, 18): date(2026, 6, 22)}  # Friday 19 June 2026 is Juneteenth: the next business day is the Monday

    def test_the_meetings_are_read_from_the_parents_calendar_and_not_from_the_saved_board_page(self):
        """Her #140 ruling (20 October 2026): the blackout is placed from the parent's FOMC calendar (`repo_liquidity.fomc`).

        `rde` holds no reader of the saved Board page; the page stays a cross-check in `tests/test_fomc.py`.
        """
        self.assertFalse(hasattr(rde, "fomc_meetings"))
        self.assertFalse(hasattr(rde, "live"))
        source = (ROOT / "src" / "repo_liquidity" / "rde.py").read_text(encoding="utf-8")
        self.assertNotIn("CALENDAR_PAGE", source.split('"""', 2)[2])  # outside the module docstring
        self.assertNotIn("gzip", source)
        meetings = rde.blackout_meetings(datetime(2026, 8, 20, 12, 0))
        self.assertIn((date(2024, 12, 17), date(2024, 12, 18)), meetings)
        self.assertIn((date(2024, 4, 30), date(2024, 5, 1)), meetings)  # across a month end
        self.assertIn((date(2026, 6, 16), date(2026, 6, 17)), meetings)
        self.assertNotIn(date(2025, 8, 22), [first for first, _ in meetings])  # a notation vote is not a meeting
        self.assertEqual(sum(first.year == 2025 for first, _ in meetings), 8)
        from repo_liquidity import fomc
        self.assertEqual(set(meetings), {(m.start, m.end) for m in fomc.meetings_at(datetime(2026, 8, 20, 12, 0))
                                         if m.kind == "scheduled"})

    def test_a_meeting_not_public_at_the_release_does_not_move_it(self):
        """Leakage guard (her #140 ruling): the blackout is placed only from meetings the parent's calendar shows as public
        at the instant the release is due (12:00 on the third Thursday), and a meeting cancelled by then is not one.

        A synthetic meeting on 25-26 August 2026 has its blackout from 15 to 27 August, which holds the third Thursday
        (20 August 2026). Announced after noon on the 20th, it must not move that release; announced earlier, it moves it
        to Friday 28 August; announced earlier and cancelled before noon on the 20th, it does not move it.

        Recorded mutation (22 October 2026): in `rde.blackout_meetings`, `fomc.meetings_at(as_of, calendar)` replaced by
        `fomc.load() if calendar is None else calendar` (every meeting of the calendar, whenever it became public). This
        test then fails with `AssertionError: datetime.date(2026, 8, 28) != datetime.date(2026, 8, 20)`: the late-announced
        meeting moves the release.
        """
        from repo_model.fomc_calendar import Meeting

        def meeting(public_at, cancelled_at=None, kind="scheduled"):
            return Meeting("synthetic-2026-08-25", kind, date(2026, 8, 25), date(2026, 8, 26), public_at, cancelled_at,
                           "https://example.invalid/")

        after = Meeting("scheduled-2027-01-26", "scheduled", date(2027, 1, 26), date(2027, 1, 27),
                        datetime(2024, 8, 9, 13, 30), None, "https://example.invalid/")  # keeps the calendar reaching on
        nominal = date(2026, 8, 20)
        self.assertEqual(rde.release_day(2026, 8, [meeting(datetime(2026, 8, 20, 13, 0)), after]), nominal)
        self.assertEqual(rde.release_day(2026, 8, [meeting(datetime(2026, 8, 1, 9, 0)), after]), date(2026, 8, 28))
        self.assertEqual(rde.release_day(2026, 8, [meeting(datetime(2026, 8, 1, 9, 0), datetime(2026, 8, 19, 9, 0)), after]),
                         nominal)
        # An unscheduled meeting carries no blackout rule here (the Board page the check compares with lists none).
        self.assertEqual(rde.release_day(2026, 8, [meeting(datetime(2026, 8, 1, 9, 0), kind="unscheduled"), after]), nominal)

    def test_the_blackout_runs_from_the_second_saturday_before_the_meeting_through_the_day_after_it(self):
        self.assertEqual(rde.blackout(date(2025, 3, 18), date(2025, 3, 19)), (date(2025, 3, 8), date(2025, 3, 20)))
        self.assertEqual(rde.blackout(date(2024, 12, 17), date(2024, 12, 18)), (date(2024, 12, 7), date(2024, 12, 19)))
        self.assertEqual(rde.blackout(date(2024, 4, 30), date(2024, 5, 1)), (date(2024, 4, 20), date(2024, 5, 2)))
        self.assertEqual(rde.blackout(date(2025, 3, 18), date(2025, 3, 19))[0].weekday(), 5)  # a Saturday

    def test_a_third_thursday_inside_a_blackout_moves_to_the_first_business_day_after_it(self):
        """Leakage guard: the six releases of finding #136 are not read on their third Thursday, 16:00 included.

        Recorded mutation (20 October 2026): in `rde.release_day`, the shifted day `next_business_day(end, 1)` replaced by
        the nominal third Thursday `nominal`. This test then fails with `AssertionError: LookAheadError not raised` for the
        read at 16:00 on Thursday 19 December 2024 (the estimate dated 2024-12-04 is returned before its release).
        """
        values = (Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1"))
        estimate = rde.Row(date(2024, 12, 4), "latest_release:2026-10-15", *values, "0" * 64)
        with self.assertRaises(LookAheadError):
            rde.read([estimate], estimate.estimate_date, datetime(2024, 12, 19, 16, 0, tzinfo=NEW_YORK))
        self.assertEqual(rde.read([estimate], estimate.estimate_date, datetime(2024, 12, 20, 16, 0, tzinfo=NEW_YORK)), estimate)
        for nominal, moved in self.MOVED.items():
            self.assertEqual(rde.nominal_release_day(nominal.year, nominal.month), nominal)
            self.assertEqual(rde.release_day(nominal.year, nominal.month), moved)

    def test_no_other_release_from_the_launch_to_august_2026_moves(self):
        """The six of #136, to the last release of the table (20 August 2026); September 2026's moves too (below)."""
        moved = {}
        for year, month in [(2024, m) for m in (10, 11, 12)] + [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 9)]:
            nominal = rde.nominal_release_day(year, month)
            if rde.release_day(year, month) != nominal:
                moved[nominal] = rde.release_day(year, month)
        self.assertEqual(moved, self.MOVED)
        self.assertEqual(rde.release_day(2026, 9), date(2026, 9, 18))  # inside the blackout of the 15-16 September meeting

    def test_a_release_the_parents_calendar_does_not_reach_is_refused_not_read_as_unmoved(self):
        """The calendar reaches the 25-26 January 2028 meeting; a release after it could hide a blackout."""
        self.assertEqual(rde.release_day(2028, 1), date(2028, 1, 28))  # inside the blackout of the 25-26 January meeting
        with self.assertRaises(ValueError):
            rde.release_day(2028, 3)
        with self.assertRaises(ValueError):
            rde.release_for(date(2028, 2, 20))

    def test_the_release_time_and_the_source_are_stated(self):
        entry = declaration.registry()[rde.SOURCE_ID]
        note = entry["availability_provenance"]["note"]
        self.assertIn("around 10:00 A.M. Eastern Time on the third Thursday of each month", note)
        self.assertIn("first business day following a Federal Open Market Committee blackout period", note)
        self.assertTrue("https://www.newyorkfed.org/newsevents/news/research/2024/20241017" in entry["availability_provenance"]["publication"])
        self.assertNotIn("not a time the Fed states", note)
        self.assertNotIn("10 days (the gap on the cover sheet)", note)


class ParseTests(unittest.TestCase):
    def estimates(self):
        return [(date(2026, 9, 28), VALUES), (LAST, VALUES)]

    def test_the_values_and_the_cover_sheet_are_read(self):
        estimates, cover = rde.parse_workbook(workbook(self.estimates()))
        self.assertEqual([day for day, _ in estimates], [date(2026, 9, 28), LAST])
        self.assertEqual(estimates[1][1], (Decimal("-0.371412"), Decimal("-0.732445"), Decimal("0.025122"),
                                           Decimal("-0.556501"), Decimal("-0.179512")))
        self.assertEqual(cover, {"update_date": LAST, "release_date": date(2026, 10, 15)})

    def test_a_value_with_more_than_six_places_is_refused_not_rounded(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook([(LAST, ["-0.3714123", *VALUES[1:]])]))

    def test_a_different_header_is_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook(self.estimates(), header=("Date", "Median", *rde.HEADER[2:])))

    def test_dates_that_do_not_increase_are_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook([(LAST, VALUES), (date(2026, 9, 28), VALUES)]))

    def test_a_missing_value_is_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook([(LAST, VALUES[:4])]))

    def test_a_cover_sheet_that_does_not_fit_the_last_estimate_is_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook(self.estimates(), cover="Updated on October 6 for release on October 16"))

    def test_a_release_that_is_not_the_third_thursday_is_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(workbook(self.estimates(), cover="Updated on October 5 for release on October 16"))

    def test_a_file_that_is_not_a_workbook_is_refused(self):
        with self.assertRaises(ValueError):
            rde.parse_workbook(b"not an xlsx")

    def test_a_row_carries_the_release_it_was_read_from(self):
        rows, _ = rde.rows_from_workbook(workbook(self.estimates()))
        self.assertEqual({row.vintage for row in rows}, {"latest_release:2026-10-15"})
        self.assertEqual(len({row.fetch_sha256 for row in rows}), 1)

    def test_the_sign_and_the_interval_are_derived_from_the_values(self):
        rows, _ = rde.rows_from_workbook(workbook(self.estimates()))
        self.assertEqual(rows[0].sign, "negative")
        self.assertFalse(rows[0].interval_excludes_zero_95)  # the 95% interval is [-0.73, 0.03]
        wholly_below = rde.Row(LAST, "latest_release:2026-10-15", *(Decimal(v) for v in ("-1", "-2", "-0.1", "-1.5", "-0.5")), "0" * 64)
        self.assertTrue(wholly_below.interval_excludes_zero_95)
        self.assertEqual(rde.Row(LAST, "v", *(Decimal(v) for v in ("0", "-1", "1", "-0.5", "0.5")), "0" * 64).sign, "zero")


class BackHistoryTests(unittest.TestCase):
    def test_the_table_starts_at_the_estimate_the_launch_release_headlined(self):
        """The launch release carried data as of Friday 11 October 2024 (its press release): its headline is the latest
        estimate dated on or before that day, and the estimates up to it are read at the launch."""
        days = [date(2024, 9, 25), date(2024, 10, 2), date(2024, 10, 9), date(2024, 10, 12), date(2024, 10, 17)]
        self.assertEqual(rde.launch_headline(days), date(2024, 10, 9))
        self.assertEqual(rde.launch_headline(days[:2] + days[3:]), date(2024, 10, 2))
        self.assertEqual(rde.release_for(date(2024, 10, 9)), rde.LAUNCH)
        self.assertEqual(rde.release_for(date(2024, 10, 11)), rde.LAUNCH)
        self.assertGreater(rde.release_for(date(2024, 10, 12)), rde.LAUNCH)

    def test_the_rows_before_the_headline_are_the_back_history(self):
        make = lambda day: rde.Row(day, "latest_release:2026-10-15", *(Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1")), "0" * 64)
        rows = [make(date(2024, 9, 25)), make(date(2024, 10, 2)), make(date(2024, 10, 9)), make(date(2024, 10, 16))]
        table, back = rde.split_back_history(rows)
        self.assertEqual([r.estimate_date for r in table], [date(2024, 10, 9), date(2024, 10, 16)])
        self.assertEqual([r.estimate_date for r in back], [date(2024, 9, 25), date(2024, 10, 2)])

    def test_a_workbook_with_no_estimate_as_of_the_launch_is_refused(self):
        with self.assertRaises(ValueError):
            rde.launch_headline([date(2024, 10, 12), date(2024, 10, 17)])


class HistoryTests(unittest.TestCase):
    """The estimates before the launch, published apart from the table (the ruling of 19 October 2026, change 5)."""

    @classmethod
    def setUpClass(cls):
        cls.table = rde.load_extract(EXTRACT)
        cls.history = rde.load_history(HISTORY)
        cls.captures = json.loads((DIRECTORY / rde.CAPTURES_NAME).read_text(encoding="utf-8"))

    def test_the_history_is_every_estimate_before_the_table(self):
        latest = self.captures["captures"][-1]
        rows, _ = rde.rows_from_workbook((DIRECTORY / latest["file"]).read_bytes())
        _, back = rde.split_back_history(rows)
        self.assertEqual([row.estimate_date for row in self.history], [row.estimate_date for row in back])
        self.assertEqual(self.history[0].estimate_date, date(2010, 1, 20))
        self.assertLess(self.history[-1].estimate_date, self.table[0].estimate_date)
        self.assertGreater(len(self.history), 600)

    def test_every_history_row_carries_the_label_and_no_availability(self):
        self.assertEqual(rde.HISTORY_LABEL, "history, not public before 2024-10-17")
        self.assertNotIn("available_from", rde.HISTORY_COLUMNS)
        for line in HISTORY.read_text(encoding="utf-8").splitlines()[1:]:
            self.assertIn(rde.HISTORY_LABEL, line)

    def test_the_declaration_does_not_read_the_history(self):
        """No declared field is a history field, and the history's estimates are not in the table."""
        for path in (ROOT / "declarations").glob("*.json"):
            for entry in json.loads(path.read_text(encoding="utf-8")).values():
                self.assertFalse(any("history" in field for field in entry["fields"]), path.name)
        self.assertFalse({row.estimate_date for row in self.history} & {row.estimate_date for row in self.table})
        self.assertEqual(set(declaration.registry()[rde.SOURCE_ID]["fields"]), set(rde.FIELDS))

    def test_an_edited_history_is_refused(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copy(HISTORY, tmp / HISTORY.name)
        shutil.copy(DIRECTORY / (HISTORY.name + ".manifest.json"), tmp / (HISTORY.name + ".manifest.json"))
        with (tmp / HISTORY.name).open("a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaises(ValueError):
            rde.load_history(tmp / HISTORY.name)


class WithholdTests(unittest.TestCase):
    def row(self, day):
        return rde.Row(day, "latest_release:2026-10-15", *(Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1")), "0" * 64)

    def test_an_estimate_released_on_a_locked_day_is_withheld_and_listed(self):
        """Leakage guard: nothing past the parent's development end is read.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.withhold_locked`, the test
        `development.is_locked(row.available_from.date())` replaced by `False`. This test then fails: the estimate
        released on the first locked day is kept and `holes` is empty (`AssertionError: Lists differ`).
        """
        # With the development end at 2026-09-03: the release of 20 August is inside it, the one of 18 September is not.
        inside, outside = self.row(date(2026, 8, 6)), self.row(date(2026, 8, 13))
        self.assertEqual((inside.available_from.date(), outside.available_from.date()),
                         (date(2026, 8, 20), date(2026, 9, 18)))  # 17 September is inside the blackout of the 15-16 meeting
        self.assertTrue(development.is_locked(outside.available_from.date()))
        self.assertFalse(development.is_locked(inside.available_from.date()))
        kept, holes = rde.withhold_locked([inside, outside])
        self.assertEqual(kept, [inside])
        self.assertEqual([h["reason"] for h in holes], ["released_after_development_end"])
        self.assertEqual(holes[0]["estimate_date"], outside.estimate_date.isoformat())


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rde.load_extract(EXTRACT)
        cls.captures = json.loads((DIRECTORY / rde.CAPTURES_NAME).read_text(encoding="utf-8"))

    def test_the_table_runs_from_the_launch_to_the_development_end(self):
        self.assertEqual(min(row.available_from for row in self.rows), rde.LAUNCH)
        self.assertEqual(self.rows[0].estimate_date, date(2024, 10, 9))  # the estimate the launch release headlined
        self.assertLessEqual(max(row.available_from for row in self.rows).date(), development.development_end())
        last = self.rows[-1]
        self.assertEqual(last.available_from, rde.release_for(last.estimate_date))

    def test_the_estimates_increase_in_date_and_are_never_listed_twice(self):
        days = [row.estimate_date for row in self.rows]
        self.assertEqual(days, sorted(set(days)))

    def test_no_row_is_read_from_a_day_the_lockbox_holds(self):
        for row in self.rows:
            self.assertFalse(development.is_locked(row.available_from.date()), row.estimate_date)

    def test_every_row_names_the_stored_workbook_it_was_read_from(self):
        stored = {item["sha256"]: item for item in self.captures["captures"]}
        for row in self.rows:
            self.assertIn(row.fetch_sha256, stored)
            self.assertEqual(row.vintage, f"latest_release:{stored[row.fetch_sha256]['release_date']}")

    def test_the_extract_is_what_the_stored_workbook_gives(self):
        latest = self.captures["captures"][-1]
        payload = (DIRECTORY / latest["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), latest["sha256"])
        rows, _ = rde.rows_from_workbook(payload)
        table, back_history = rde.split_back_history(rows)
        kept, held = rde.withhold_locked(table)
        self.assertEqual(kept, self.rows)
        self.assertEqual(rde.write_extract(kept), EXTRACT.read_bytes())

    def test_a_stored_workbook_is_named_by_its_digest_and_release(self):
        for item in self.captures["captures"]:
            self.assertEqual(item["file"], f"rde-{item['release_date']}-{item['sha256']}.xlsx")

    def test_the_sign_changes_are_listed_with_their_dates(self):
        changes = rde.sign_changes(self.rows)
        self.assertTrue(changes)
        self.assertEqual(changes[0], {"estimate_date": "2025-10-03", "from": "negative", "to": "positive",
                                      "read_from": "2025-10-16T12:00:00-04:00"})
        for before, now in zip(self.rows, self.rows[1:]):
            self.assertEqual(before.sign != now.sign, any(c["estimate_date"] == now.estimate_date.isoformat() for c in changes))

    def test_the_coverage_record_agrees_with_the_extract(self):
        record = json.loads((DIRECTORY / rde.COVERAGE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(record["rows"], len(self.rows))
        self.assertEqual(record["sign_changes"], rde.sign_changes(self.rows))
        self.assertEqual(record["significance_changes"], rde.significance_changes(self.rows))
        self.assertEqual(record["worst_case_lag_days"], rde.worst_case_lag_days(self.rows))
        self.assertEqual(record["estimates_in_workbook"],
                         len(self.rows) + record["withheld"] + record["back_history"]["estimates"])
        self.assertEqual(record["back_history"]["last"], "2024-10-02")

    def copy(self, edit):
        """A copy of the extract with `edit` applied to its text, the manifest refreshed to match."""
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        path = tmp / EXTRACT.name
        data = edit(EXTRACT.read_text(encoding="utf-8")).encode("utf-8")
        path.write_bytes(data)
        manifest = json.loads((DIRECTORY / (EXTRACT.name + ".manifest.json")).read_text(encoding="utf-8"))
        manifest["sha256"] = hashlib.sha256(data).hexdigest()
        path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_an_edited_extract_is_refused(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copy(EXTRACT, tmp / EXTRACT.name)
        shutil.copy(DIRECTORY / (EXTRACT.name + ".manifest.json"), tmp / (EXTRACT.name + ".manifest.json"))
        with (tmp / EXTRACT.name).open("a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaises(ValueError):
            rde.load_extract(tmp / EXTRACT.name)

    def test_a_row_not_labelled_with_a_release_is_refused(self):
        path = self.copy(lambda text: text.replace("latest_release:2026-10-15", "first_print", 1))
        with self.assertRaises(ValueError):
            rde.load_extract(path)

    def test_a_stored_availability_that_the_rule_does_not_give_is_refused(self):
        path = self.copy(lambda text: text.replace("2024-10-17T12:00:00-04:00", "2010-02-18T12:00:00-05:00", 1))
        with self.assertRaises(ValueError):
            rde.load_extract(path)

    def test_a_stored_content_hash_that_the_values_do_not_give_is_refused(self):
        first = self.rows[0]
        path = self.copy(lambda text: text.replace(f"{first.elasticity_p50:.6f}", "-9.000000", 1))
        with self.assertRaises(ValueError):
            rde.load_extract(path)

    def test_a_row_released_in_the_blind_tier_is_refused(self):
        """Leakage guard: the loader refuses an extract that holds an estimate released on a locked day.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.load_extract`, the `LookAheadError` branch
        `if development.is_locked(row.available_from.date()): raise ...` replaced by `if False:`. This test then fails
        with `AssertionError: LookAheadError not raised` (the row is returned).
        """
        end = development.development_end()
        day = rde.release_for(end + timedelta(days=1)).date() - timedelta(days=rde.UNRECORDED_AS_OF_LAG_DAYS)
        locked = rde.Row(day, "latest_release:2026-10-15", *(Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1")),
                         self.rows[0].fetch_sha256)
        line = ",".join((day.isoformat(), locked.vintage, locked.available_from.isoformat(),
                         *(f"{v:.6f}" for v in locked.values), locked.sign, "false", locked.fetch_sha256, locked.content_sha256))
        path = self.copy(lambda text: text + line + "\n")
        with self.assertRaises(LookAheadError):
            rde.load_extract(path)


class DeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rde.load_extract(EXTRACT)
        cls.entry = declaration.registry()[rde.SOURCE_ID]

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_the_declared_fields_are_the_five_rde_fields(self):
        self.assertEqual(tuple(self.entry["fields"]), rde.FIELDS)
        self.assertEqual(set(self.entry["field_frequencies"]), set(rde.FIELDS))
        for field in rde.FIELDS:
            self.assertEqual(declaration.FIELDS[field], ((rde.SOURCE_ID, field),))

    def test_the_declaration_says_it_is_an_external_check_and_the_figures_are_the_latest_release(self):
        text = json.dumps(self.entry)
        self.assertIn("EXTERNAL CHECK", text)
        self.assertIn("never deciding", text)
        self.assertIn("LATEST-RELEASE", text)
        self.assertIn("2024-10-17", json.dumps(self.entry["availability_provenance"]).replace("17 October 2024", "2024-10-17"))

    def test_the_declared_time_is_noon_new_york_time(self):
        self.assertEqual(self.entry["release_lag"]["available_time"], "12:00")
        self.assertEqual(self.entry["release_lag"]["timezone"], "America/New_York")

    def test_no_estimate_is_available_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every estimate in the extract.

        Recorded mutation (20 October 2026): in `declarations/nyfed_rde.json`, `nyfed_rde.release_lag.days` changed
        from 44 to 30. This test then fails with LookAheadError: the estimate of 2024-10-17 is
        available from 2024-11-21 12:00:00-05:00, after its declared availability 2024-11-16 12:00:00-05:00.
        """
        rde.check_declared_lag(self.entry, self.rows)

    def test_an_estimate_later_than_declared_is_refused(self):
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], days=1)
        with self.assertRaises(LookAheadError):
            rde.check_declared_lag(entry, self.rows)

    def test_a_lag_longer_than_the_slowest_estimate_is_stale(self):
        """Staleness guard: the declared lag is the measured worst case and not above it.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.check_declared_lag`, the branch
        `if int(lag["days"]) > worst: raise StaleReadError(...)` replaced by `if False:`. This test then fails with
        `AssertionError: StaleReadError not raised`. (A declaration changed from 44 to 60 days is caught by
        `test_the_worst_case_lag_is_the_declared_one`: `AssertionError: 44 != 60`.)
        """
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], days=60)
        with self.assertRaises(StaleReadError):
            rde.check_declared_lag(entry, self.rows)

    def test_the_declaration_is_record_date_calendar_days(self):
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], basis="snapshot_retrieved_at")
        with self.assertRaises(ValueError):
            rde.check_declared_lag(entry, self.rows)

    def test_the_worst_case_lag_is_the_declared_one(self):
        self.assertEqual(rde.worst_case_lag_days(self.rows), self.entry["release_lag"]["days"])


class ReadGuardTests(unittest.TestCase):
    """The exact, row-by-row reader. The panel-level guard under the parent's `InformationRule` is in test_guards.py."""

    @classmethod
    def setUpClass(cls):
        cls.rows = rde.load_extract(EXTRACT)
        cls.old, cls.new = cls.rows[-8], cls.rows[-1]
        assert cls.old.available_from < cls.new.available_from

    def test_an_estimate_is_read_from_the_instant_it_is_available(self):
        self.assertEqual(rde.read(self.rows, self.new.estimate_date, self.new.available_from), self.new)

    def test_a_read_before_the_release_is_look_ahead(self):
        """Leakage guard: an estimate read before its release raises LookAheadError.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.read`, the branch
        `if row.available_from > at: raise LookAheadError(...)` replaced by `if False:`. This test then fails with
        `AssertionError: LookAheadError not raised` (the estimate is returned).
        """
        with self.assertRaises(LookAheadError):
            rde.read(self.rows, self.new.estimate_date, self.new.available_from - timedelta(seconds=1))

    def test_a_read_of_an_older_estimate_than_the_latest_public_is_stale(self):
        """Staleness guard: once a later estimate is public, an earlier one is stale.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.read`, the branch
        `if latest is not None and latest.estimate_date > estimate_date: raise StaleReadError(...)` replaced by
        `if False:`. This test then fails with `AssertionError: StaleReadError not raised`.
        """
        with self.assertRaises(StaleReadError):
            rde.read(self.rows, self.old.estimate_date, self.new.available_from)

    def test_the_latest_public_estimate_is_the_one_whose_release_has_passed(self):
        before = self.rows[0].available_from - timedelta(seconds=1)
        self.assertIsNone(rde.latest_public(self.rows, before))
        self.assertEqual(rde.latest_public(self.rows, self.new.available_from), self.new)

    def test_a_decision_instant_without_a_time_zone_is_refused(self):
        with self.assertRaises(ValueError):
            rde.read(self.rows, self.new.estimate_date, datetime(2026, 9, 1, 16, 0))

    def test_an_estimate_not_in_the_extract_is_refused(self):
        with self.assertRaises(ValueError):
            rde.read(self.rows, date(2026, 8, 7), self.new.available_from)

    def test_the_observations_are_public_from_the_release_not_before(self):
        observations = rde.observations(self.rows, "rde_elasticity", source_sha="0" * 64)
        self.assertEqual(len(observations), len(self.rows))
        for observation, row in zip(observations, self.rows):
            self.assertEqual((observation.series_id, observation.ref_date, observation.available_at, observation.value),
                             ("rde_elasticity", row.estimate_date, row.available_from, float(row.elasticity_p50)))
        upper = rde.observations(self.rows, "rde_upper_95", source_sha="0" * 64)
        self.assertEqual(upper[-1].value, float(self.new.elasticity_p97_5))

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(ValueError):
            rde.observations(self.rows, "rde_median", source_sha="0" * 64)


if __name__ == "__main__":
    unittest.main()
