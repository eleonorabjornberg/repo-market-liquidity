"""The parent's FOMC meeting calendar, read through its point-in-time interface (directive #149; parent #1038).

Groundwork for H7 and H10 (calendar). Three things are checked:

- the pin carries the calendar (`repo_model.fomc_calendar`, parent #1038/#1045);
- `repo_liquidity.fomc` reads it only through the parent's `visible_at` and `require_public`, never re-implements it;
- the saved Board page (`tests/fixtures/snapshots/fomc_calendar/`) is a cross-check only: the parent's scheduled meetings
  and the page's agree on every meeting from 2024 to the development end.

Standard library only.
"""

import gzip
import html
import re
import unittest
from datetime import date, datetime, timedelta

from repo_liquidity import fomc, live

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
CROSS_CHECK_FROM = date(2024, 1, 1)


def board_page_meetings():
    """{(start, end)} read from the saved Board page, by an independent parse of its "YYYY FOMC Meetings" sections.

    A notation vote ("22 (notation vote)") is not a meeting; a cancelled meeting is marked, and none falls after 2020.
    """
    raw = gzip.decompress(live.CALENDAR_PAGE.read_bytes()).decode("utf-8", errors="replace")
    sections = list(re.finditer(r"(\d{4}) FOMC Meetings", raw))
    found = set()
    for index, section in enumerate(sections):
        year = int(section.group(1))
        end = sections[index + 1].start() if index + 1 < len(sections) else len(raw)
        body = raw[section.end():end]
        for month, days in re.findall(
                r'fomc-meeting__month[^>]*><strong>([^<]*)</strong></div>\s*<div class="fomc-meeting__date[^>]*>([^<]*)<',
                body):
            days = html.unescape(days).strip()
            if "notation vote" in days:
                continue
            first, last = re.match(r"(\d+)(?:-(\d+))?", days.replace("*", "")).groups()
            names = month.split("/")
            start = date(year, MONTHS.index(next(m for m in MONTHS if m.startswith(names[0]))) + 1, int(first))
            if last is None:
                finish = start
            elif len(names) == 2:
                month2 = MONTHS.index(next(m for m in MONTHS if m.startswith(names[1]))) + 1
                finish = date(year + (month2 < start.month), month2, int(last))
            else:
                finish = start.replace(day=int(last))
            found.add((start, finish))
    return found


class PinCarriesTheCalendarTests(unittest.TestCase):
    def test_the_parent_at_the_pin_has_the_meeting_calendar(self):
        """The pin is at or after parent #1038 (merged in #1045 on 2026-10-20), which adds `repo_model.fomc_calendar`.

        Written first: at the previous pin (8fd2cf8) this fails with ModuleNotFoundError.
        """
        from repo_model import fomc_calendar

        meetings = fomc_calendar.load_calendar()
        self.assertTrue(meetings)
        self.assertEqual(min(m.start for m in meetings).year, 2018)


class PointInTimeTests(unittest.TestCase):
    def test_a_meeting_is_read_only_from_the_instant_it_was_public(self):
        """`fomc.meetings_at` returns the meetings public at the instant and no other.

        The 2020-03-17 meeting was public from the 2019 schedule and cancelled on 2020-03-15 at 17:00: visible before,
        gone after. The 2019-10-04 unscheduled meeting was announced on 2019-10-11.

        Recorded mutation (20 October 2026): in `fomc.meetings_at`, the filter `if visible_at(meeting, as_of)` changed
        to `if True`. This test then fails with LookAheadError (the explicit `require_public` on a meeting announced
        after the instant), not an assertion.
        """
        before = fomc.meetings_at(datetime(2019, 10, 10, 16, 0))
        self.assertNotIn(date(2019, 10, 4), [m.start for m in before])
        after = fomc.meetings_at(datetime(2019, 10, 11, 16, 0))
        self.assertIn(date(2019, 10, 4), [m.start for m in after])
        self.assertIn(date(2020, 3, 17), [m.start for m in fomc.meetings_at(datetime(2020, 3, 13, 16, 0))])
        self.assertNotIn(date(2020, 3, 17), [m.start for m in fomc.meetings_at(datetime(2020, 3, 16, 16, 0))])

    def test_a_future_meeting_is_refused_not_filtered_silently(self):
        from repo_model.splits import LookAheadError

        meetings = fomc.load()
        late = max(meetings, key=lambda m: m.public_at)
        with self.assertRaises(LookAheadError):
            fomc.require_public(late, late.public_at - timedelta(seconds=1))
        self.assertIs(fomc.require_public(late, late.public_at), late)

    def test_an_instant_with_a_zone_is_refused(self):
        from zoneinfo import ZoneInfo

        with self.assertRaises(ValueError):
            fomc.meetings_at(datetime(2025, 1, 2, 16, 0, tzinfo=ZoneInfo("America/New_York")))

    def test_the_module_does_not_carry_a_calendar_of_its_own(self):
        """Never re-implement the calendar: `fomc` holds no meeting date."""
        source = fomc.__file__
        text = open(source, encoding="utf-8").read()
        self.assertIsNone(re.search(r"\b20[12]\d-\d\d-\d\d\b", text))
        self.assertIsNone(re.search(r"\bdate\(20[12]\d,", text))


class CrossCheckTests(unittest.TestCase):
    def test_the_saved_page_parses_to_the_meetings_it_lists(self):
        page = board_page_meetings()
        self.assertIn((date(2024, 4, 30), date(2024, 5, 1)), page)
        self.assertIn((date(2025, 12, 9), date(2025, 12, 10)), page)
        self.assertNotIn(date(2025, 8, 22), [start for start, _ in page])

    def test_the_two_calendars_agree_on_every_meeting_from_2024_to_the_development_end(self):
        """The parent's scheduled meetings and the saved Board page's, 2024-01-01 to 2025-12-31, are the same set.

        The page is a cross-check only; the parent's calendar is what is read. A meeting on one and not the other, or
        with other days, fails this test, naming it.

        Recorded mutation (20 October 2026): in `board_page_meetings`, `int(first)` changed to `int(first) + 1`. This
        test then fails with AssertionError (the sets differ, naming every 2024 and 2025 meeting).
        """
        parent = {(m.start, m.end) for m in fomc.load()
                  if m.kind == "scheduled" and m.cancelled_at is None
                  and CROSS_CHECK_FROM <= m.start <= live.LAST_DEVELOPMENT_DAY}
        page = {pair for pair in board_page_meetings()
                if CROSS_CHECK_FROM <= pair[0] <= live.LAST_DEVELOPMENT_DAY}
        self.assertEqual(len(parent), 16)
        self.assertEqual(sorted(parent ^ page), [], "meetings on one calendar only (parent ^ page)")

    def test_after_the_development_end_the_two_calendars_are_compared_too(self):
        """Informational extension of the same check to the later meetings the page lists (2026, 2027)."""
        parent = {(m.start, m.end) for m in fomc.load()
                  if m.kind == "scheduled" and m.cancelled_at is None and m.start > live.LAST_DEVELOPMENT_DAY}
        page = {pair for pair in board_page_meetings() if pair[0] > live.LAST_DEVELOPMENT_DAY}
        self.assertEqual(sorted(parent ^ page), [])

    def test_the_statement_dates_of_the_log_guard_are_the_second_days(self):
        """`live`'s statement calendar (this repository's) is the second day of each parent meeting from 2026."""
        parent = {m.end for m in fomc.load() if m.kind == "scheduled" and m.cancelled_at is None
                  and m.start >= date(2026, 1, 1)}
        ours = {s.instant.date() for s in live.load_fomc_calendar()}
        self.assertEqual(sorted(ours - parent), [])


if __name__ == "__main__":
    unittest.main()
