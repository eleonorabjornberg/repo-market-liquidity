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
from datetime import date, datetime, timedelta
from decimal import Decimal

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, development, rde

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "rde"
EXTRACT = DIRECTORY / rde.EXTRACT_NAME
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

    def test_a_release_is_at_ten_new_york_time(self):
        self.assertEqual(rde.release_for(date(2026, 8, 6)), datetime(2026, 8, 20, 10, 0, tzinfo=NEW_YORK))

    def test_nothing_is_public_before_the_launch(self):
        """Leakage guard: an estimate dated before the product existed is read from the launch and no earlier.

        Recorded mutation (19 October 2026): in `rde.release_for`, `max(..., LAUNCH)` replaced by its first argument.
        This test then fails with `AssertionError: datetime.datetime(2010, 2, 18, 10, 0, ...) != datetime.datetime(2024,
        10, 17, 10, 0, ...)`: the 2010 estimate is read at the third Thursday after its own date.
        """
        self.assertEqual(rde.release_for(date(2010, 1, 20)), rde.LAUNCH)
        self.assertEqual(rde.release_for(date(2024, 10, 2)), rde.LAUNCH)
        self.assertEqual(rde.LAUNCH, datetime(2024, 10, 17, 10, 0, tzinfo=NEW_YORK))

    def test_an_estimate_waits_for_the_first_release_at_least_ten_days_after_its_date(self):
        """Leakage guard: the stored release shows 5 October for release on 15 October; no estimate is read sooner.

        Recorded mutation (19 October 2026): in `rde.UPDATE_TO_RELEASE_DAYS`, 10 changed to 0. This test then fails
        with `AssertionError: datetime.date(2026, 8, 20) != datetime.date(2026, 9, 17)`
        for the estimate dated 2026-08-20, which would be read at the release on its own date.
        """
        self.assertEqual(rde.release_for(date(2026, 8, 10)).date(), date(2026, 8, 20))
        self.assertEqual(rde.release_for(date(2026, 8, 11)).date(), date(2026, 9, 17))
        self.assertEqual(rde.release_for(date(2026, 8, 20)).date(), date(2026, 9, 17))
        self.assertEqual(rde.release_for(date(2026, 12, 10)).date(), date(2027, 1, 21))  # across the year end

    def test_the_release_is_never_before_the_estimate_date(self):
        day = date(2024, 10, 9)
        while day < date(2027, 1, 1):
            self.assertGreaterEqual(rde.release_for(day).date(), day + timedelta(days=rde.UPDATE_TO_RELEASE_DAYS))
            day += timedelta(days=1)


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
        days = [date(2024, 9, 25), date(2024, 10, 2), date(2024, 10, 7), date(2024, 10, 9), date(2024, 10, 17)]
        self.assertEqual(rde.launch_headline(days), date(2024, 10, 7))  # ten days before the launch: read at the launch
        self.assertEqual(rde.launch_headline(days[:2] + days[3:]), date(2024, 10, 2))
        self.assertEqual(rde.release_for(date(2024, 10, 7)), rde.LAUNCH)
        self.assertGreater(rde.release_for(date(2024, 10, 8)), rde.LAUNCH)

    def test_the_rows_before_the_headline_are_the_back_history(self):
        make = lambda day: rde.Row(day, "latest_release:2026-10-15", *(Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1")), "0" * 64)
        rows = [make(date(2024, 9, 25)), make(date(2024, 10, 2)), make(date(2024, 10, 9))]
        table, back = rde.split_back_history(rows)
        self.assertEqual([r.estimate_date for r in table], [date(2024, 10, 2), date(2024, 10, 9)])
        self.assertEqual([r.estimate_date for r in back], [date(2024, 9, 25)])

    def test_a_workbook_with_no_estimate_ten_days_before_the_launch_is_refused(self):
        with self.assertRaises(ValueError):
            rde.launch_headline([date(2024, 10, 9), date(2024, 10, 17)])


class WithholdTests(unittest.TestCase):
    def row(self, day):
        return rde.Row(day, "latest_release:2026-10-15", *(Decimal(v) for v in ("-0.1", "-0.5", "0.3", "-0.3", "0.1")), "0" * 64)

    def test_an_estimate_released_on_a_locked_day_is_withheld_and_listed(self):
        """Leakage guard: nothing past the parent's development end is read.

        Recorded mutation (19 October 2026): in `repo_liquidity.rde.withhold_locked`, the test
        `development.is_locked(row.available_from.date())` replaced by `False`. This test then fails: the estimate
        released on the first locked day is kept and `holes` is empty (`AssertionError: Lists differ`).
        """
        # With the development end at 2026-09-03: the release of 20 August is inside it, the one of 17 September is not.
        inside, outside = self.row(date(2026, 8, 6)), self.row(date(2026, 8, 13))
        self.assertEqual((inside.available_from.date(), outside.available_from.date()),
                         (date(2026, 8, 20), date(2026, 9, 17)))
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
        self.assertEqual(self.rows[0].estimate_date, date(2024, 10, 2))  # the estimate the launch release headlined
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
                                      "read_from": "2025-10-16T10:00:00-04:00"})
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
        self.assertEqual(record["back_history"]["last"], "2024-09-20")

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
        path = self.copy(lambda text: text.replace("2024-10-17T10:00:00-04:00", "2010-02-18T10:00:00-05:00", 1))
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
        day = rde.release_for(end + timedelta(days=1)).date() - timedelta(days=rde.UPDATE_TO_RELEASE_DAYS)
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

    def test_the_declared_time_is_ten_new_york_time(self):
        self.assertEqual(self.entry["release_lag"]["available_time"], "10:00")
        self.assertEqual(self.entry["release_lag"]["timezone"], "America/New_York")

    def test_no_estimate_is_available_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every estimate in the extract.

        Recorded mutation (19 October 2026): in `declarations/nyfed_rde.json`, `nyfed_rde.release_lag.days` changed
        from 44 to 30. This test then fails with LookAheadError: the estimate of 2024-10-09 is
        available from 2024-11-21 10:00:00-05:00, after its declared availability 2024-11-08 10:00:00-05:00.
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
