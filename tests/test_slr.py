"""SLR headroom of the nine G-SIB depository subsidiaries, latest-filed figures (#63, H7m groundwork G5).

The parser is tested on small synthetic bulk zips; the tracked extract, its declaration and the guards are tested on the
real extract cut by `scripts/extract_slr.py` from the 34 stored quarters. No test scores anything.
"""

import csv
import io
import json
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta

from repo_model.asof import StaleReadError
from repo_model.splits import LookAheadError

from repo_liquidity import declaration, development, slr

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "slr_headroom"
EXTRACT = DIRECTORY / slr.EXTRACT_NAME
JPM, STATE_STREET, STATE_STREET_TRUST_NA = 852218, 35301, 93619
NEW_YORK = slr.NEW_YORK


def bulk_zip(banks, as_of="2026-01-15T04:30:03"):
    """A bulk zip with the two files the parser reads. `banks`: IDRSSD -> (update, {item column: value})."""
    por = ["IDRSSD\tName\tLast Date/Time Submission Updated On", "ID\tname\tlast"]
    columns = ["RCFA8274", "RCFAH015", "RCFAH036", "RCOA8274", "RCOAH015", "RCOAH036"]
    rcri = ["IDRSSD\t" + "\t".join(columns), "ID\t" + "\t".join("d" for _ in columns)]
    for idrssd, (update, items) in banks.items():
        por.append(f"{idrssd}\tbank\t{update}")
        rcri.append(f"{idrssd}\t" + "\t".join(items.get(column, "") for column in columns))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Readme.txt", f"data from Call Reports as of {as_of}\n")
        archive.writestr("FFIEC CDR Call Bulk POR 03312021.txt", "\n".join(por) + "\n")
        archive.writestr("FFIEC CDR Call Schedule RCRI 03312021.txt", "\n".join(rcri) + "\n")
    return buffer.getvalue()


class ParseTests(unittest.TestCase):
    QUARTER = date(2021, 3, 31)

    def parse(self, banks):
        return slr.parse_quarter(bulk_zip(banks), self.QUARTER)

    def test_a_bank_is_read_from_the_consolidated_column_and_the_ratio_is_computed(self):
        rows, holes, as_of = self.parse({JPM: ("2021-05-05T12:00:00", {
            "RCFA8274": "60", "RCFAH015": "1000", "RCFAH036": "6.0000%", "RCOA8274": "1", "RCOAH015": "1000"})})
        self.assertEqual(as_of, "2026-01-15T04:30:03")
        self.assertEqual([(r.column_form, r.slr_pct, r.headroom_pp, r.reported_slr_pct) for r in rows],
                         [("RCFA", 6.0, 0.0, 6.0)])
        self.assertEqual({h["reason"] for h in holes}, {"not_a_filer"})  # the other eight banks are not in the file

    def test_the_domestic_offices_column_is_the_fallback(self):
        rows, _, _ = self.parse({JPM: ("2021-05-05T12:00:00", {"RCOA8274": "70", "RCOAH015": "1000"})})
        self.assertEqual([(r.column_form, r.slr_pct, r.reported_slr_pct) for r in rows], [("RCOA", 7.0, None)])

    def test_a_blank_item_is_a_hole_and_not_a_guess(self):
        rows, holes, _ = self.parse({JPM: ("2021-05-05T12:00:00", {"RCFA8274": "60"})})
        self.assertEqual(rows, [])
        blank = [h for h in holes if h["reason"] == "item_blank"]
        self.assertEqual([h["idrssd"] for h in blank], [JPM])
        self.assertIn("H015", blank[0]["detail"])

    def test_tier_1_capital_above_the_exposure_is_refused(self):
        rows, holes, _ = self.parse({STATE_STREET: ("2021-05-05T12:00:00", {"RCFA8274": "36100", "RCFAH015": "35799"})})
        self.assertEqual(rows, [])
        self.assertEqual([h["reason"] for h in holes if h["idrssd"] == STATE_STREET], ["tier1_exceeds_exposure"])

    def test_a_file_that_is_not_a_zip_is_refused(self):
        with self.assertRaises(ValueError):
            slr.parse_quarter(b"<html>technical difficulties</html>", self.QUARTER)

    def test_the_requirement_is_set_only_before_april_2026(self):
        make = lambda q: slr.Row(q, JPM, "bank", datetime(2026, 5, 1), "RCFA", 70, 1000, None, "0" * 64)
        self.assertEqual(make(date(2026, 3, 31)).headroom_pp, 1.0)
        self.assertIsNone(make(date(2026, 6, 30)).headroom_pp)
        self.assertEqual(make(date(2026, 6, 30)).slr_pct, 7.0)
        self.assertIsNone(make(date(2017, 12, 31)).headroom_pp)

    def test_the_exclusion_window_quarters_are_flagged_unknown(self):
        make = lambda q: slr.Row(q, JPM, "bank", datetime(2021, 5, 1), "RCFA", 70, 1000, None, "0" * 64)
        flagged = [q for q in (date(2020, 3, 31), *slr.EXCLUSION_QUARTERS, date(2021, 6, 30)) if make(q).exclusion_status]
        self.assertEqual(flagged, list(slr.EXCLUSION_QUARTERS))


class WithholdTests(unittest.TestCase):
    def row(self, update):
        return slr.Row(date(2025, 12, 31), JPM, "bank", update, "RCFA", 70, 1000, None, "0" * 64)

    def test_a_figure_last_updated_on_a_locked_day_is_withheld_and_listed(self):
        """Leakage guard: nothing past the parent's development end is read.

        Recorded mutation (14 October 2026): in `repo_liquidity.slr.withhold_locked`, the test
        `development.is_locked(row.latest_update.date())` replaced by `False`. This test then fails: the row updated
        on the first locked day is kept and `holes` is empty (`AssertionError: Lists differ`).
        """
        end = development.development_end()
        inside = self.row(datetime.combine(end, datetime.min.time()) + timedelta(hours=9))
        outside = self.row(datetime.combine(end + timedelta(days=1), datetime.min.time()) + timedelta(hours=9))
        kept, holes = slr.withhold_locked([inside, outside])
        self.assertEqual(kept, [inside])
        self.assertEqual([h["reason"] for h in holes], ["updated_after_development_end"])


class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = slr.load_extract(EXTRACT)
        cls.coverage = json.loads((DIRECTORY / slr.COVERAGE_NAME).read_text(encoding="utf-8"))
        cls.sources = json.loads((DIRECTORY / slr.SOURCES_NAME).read_text(encoding="utf-8"))

    def test_every_bank_quarter_is_a_row_or_a_listed_refusal(self):
        quarters = len(self.coverage["quarters"])
        refused = {(h["quarter_end"], h["idrssd"]) for h in self.coverage["holes"] if not h["row_kept"]}
        kept = {(r.quarter_end.isoformat(), r.idrssd) for r in self.rows}
        self.assertEqual(quarters, 34)
        self.assertEqual(len(kept) + len(refused), quarters * len(slr.BANKS))
        self.assertFalse(kept & refused)

    def test_the_quarters_run_from_2018_03_31_to_2026_06_30(self):
        self.assertEqual(self.coverage["quarters"][0], "2018-03-31")
        self.assertEqual(self.coverage["quarters"][-1], "2026-06-30")
        self.assertEqual({r.quarter_end for r in self.rows} - {date.fromisoformat(q) for q in self.coverage["quarters"]},
                         set())

    def test_every_row_is_labelled_latest_filed_and_available_only_after_its_update(self):
        with EXTRACT.open(encoding="utf-8") as handle:
            stored = list(csv.DictReader(handle))
        self.assertEqual({row["vintage"] for row in stored}, {"latest_filed"})
        for row in self.rows:
            self.assertGreater(row.available_from, row.latest_update.replace(tzinfo=NEW_YORK))

    def test_no_row_is_read_from_a_day_the_lockbox_holds(self):
        self.assertTrue(all(not development.is_locked(r.latest_update.date()) for r in self.rows))
        self.assertEqual([(h["quarter_end"], h["idrssd"]) for h in self.coverage["holes"]
                          if h["reason"] == "updated_after_development_end"],
                         # The bulk files of 15 October 2026 carry amendments that Citibank (476810) and Goldman Sachs
                         # Bank USA (2182786) filed from 29 September to 9 October; the files of 14 October did not yet.
                         [("2025-06-30", 476810), ("2025-09-30", 476810), ("2025-09-30", 2182786),
                          ("2025-12-31", 476810), ("2025-12-31", 2182786), ("2026-03-31", 476810),
                          ("2026-03-31", 1456501), ("2026-03-31", 2182786), ("2026-06-30", 476810),
                          ("2026-06-30", 1456501), ("2026-06-30", 2182786)])

    def test_the_computed_ratio_agrees_with_the_one_the_banks_reported(self):
        self.assertFalse([h for h in self.coverage["holes"] if h["reason"] == "ratio_differs_from_reported"])
        self.assertTrue(all(r.reported_slr_pct is not None for r in self.rows))

    def test_the_headroom_is_blank_from_the_quarter_the_requirement_is_not_set(self):
        for row in self.rows:
            self.assertEqual(row.headroom_pp is None, row.quarter_end >= date(2026, 4, 1), (row.quarter_end, row.idrssd))
        self.assertEqual(sum(1 for h in self.coverage["holes"] if h["reason"] == "requirement_not_set"),
                         sum(1 for r in self.rows if r.quarter_end >= date(2026, 4, 1)))

    def test_every_row_in_the_exclusion_window_is_flagged_and_listed(self):
        flagged = [r for r in self.rows if r.exclusion_status]
        self.assertTrue(flagged)
        listed = {(h["quarter_end"], h["idrssd"]) for h in self.coverage["holes"] if h["reason"] == "exclusion_status_unknown"}
        self.assertEqual({(r.quarter_end.isoformat(), r.idrssd) for r in flagged}, listed)

    def test_the_sources_are_the_34_stored_zips_by_digest(self):
        self.assertEqual(len(self.sources["zips"]), 34)
        self.assertEqual({r.source_zip_sha256 for r in self.rows} - {z["sha256"] for z in self.sources["zips"]}, set())
        for item in self.sources["zips"]:
            self.assertEqual(item["file"], f"{item['quarter_end']}-{item['sha256']}.zip")

    def test_no_aggregate_across_banks_is_published(self):
        self.assertEqual(slr.EXTRACT_COLUMNS.count("institution"), 1)
        self.assertEqual({r.idrssd for r in self.rows} - set(slr.BANKS), set())

    def temp_copy(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        for name in (slr.EXTRACT_NAME, slr.EXTRACT_NAME + ".manifest.json"):
            shutil.copy(DIRECTORY / name, tmp / name)
        return tmp / slr.EXTRACT_NAME

    def rewrite(self, path, edit):
        """Rewrite the copy with `edit(rows)` applied and its manifest digest updated (so only the content is wrong)."""
        import hashlib

        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        edit(rows)
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=slr.EXTRACT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        data = buffer.getvalue().encode("utf-8")
        path.write_bytes(data)
        manifest = path.with_name(path.name + ".manifest.json")
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["sha256"] = hashlib.sha256(data).hexdigest()
        manifest.write_text(json.dumps(record), encoding="utf-8")

    def test_an_edited_extract_is_refused(self):
        path = self.temp_copy()
        path.write_bytes(path.read_bytes().replace(b"latest_filed", b"first_filed", 1))
        with self.assertRaises(ValueError):
            slr.load_extract(path)

    def test_a_row_not_labelled_latest_filed_is_refused(self):
        path = self.temp_copy()
        self.rewrite(path, lambda rows: rows[0].update(vintage="first_filed"))
        with self.assertRaises(ValueError):
            slr.load_extract(path)

    def test_a_stored_ratio_that_the_figures_do_not_give_is_refused(self):
        path = self.temp_copy()
        self.rewrite(path, lambda rows: rows[0].update(slr_pct="9.9999"))
        with self.assertRaises(ValueError):
            slr.load_extract(path)

    def test_a_row_last_updated_in_the_blind_tier_is_refused(self):
        """Leakage guard: the loader refuses an extract that holds a figure updated on a day the lockbox holds.

        Recorded mutation (14 October 2026): in `repo_liquidity.slr.load_extract`, the `LookAheadError` branch
        `if development.is_locked(row.latest_update.date()):` replaced by `if False:`. This test then fails with
        `AssertionError: LookAheadError not raised`.
        """
        path = self.temp_copy()
        late = (development.development_end() + timedelta(days=1)).isoformat()

        def edit(rows):
            rows[0].update(latest_update=late + "T09:00:00",
                           available_from=(date.fromisoformat(late) + timedelta(days=1)).isoformat() + "T00:00:00-04:00")

        self.rewrite(path, edit)
        with self.assertRaises(LookAheadError):
            slr.load_extract(path)


class DeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = slr.load_extract(EXTRACT)
        cls.entry = declaration.registry()[slr.SOURCE_ID]

    def test_the_overlay_passes_the_parents_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_the_declared_fields_are_the_four_slr_fields(self):
        self.assertEqual(tuple(self.entry["fields"]), slr.FIELDS)
        self.assertEqual(set(self.entry["field_frequencies"]), set(slr.FIELDS))
        for field in slr.FIELDS:
            self.assertEqual(declaration.FIELDS[field], ((slr.SOURCE_ID, field),))

    def test_the_declaration_says_the_figures_are_latest_filed(self):
        text = json.dumps(self.entry)
        self.assertIn("LATEST-FILED", text)
        self.assertIn("not first prints", text)

    def test_no_figure_is_available_after_its_declared_availability(self):
        """Leakage guard: the declared lag covers every figure in the extract.

        Recorded mutation (14 October 2026): in `declarations/ffiec_call_slr.json`, `ffiec_call_slr.release_lag.days`
        changed from 1714 to 1700. This test then fails with LookAheadError: Bank of America, N.A. 2018-06-30 is
        available from 2023-03-10, after its declared availability 2023-02-24.
        """
        slr.check_declared_lag(self.entry, self.rows)

    def test_a_figure_later_than_declared_is_refused(self):
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], days=1)
        with self.assertRaises(LookAheadError):
            slr.check_declared_lag(entry, self.rows)

    def test_a_lag_longer_than_the_slowest_figure_is_stale(self):
        """Staleness guard: the declared lag is the measured worst case and not above it.

        Recorded mutation (14 October 2026): in `declarations/ffiec_call_slr.json`, `ffiec_call_slr.release_lag.days`
        changed from 1714 to 1800. This test then fails with StaleReadError: the declared lag of 1800 days is longer
        than the 1714 days the slowest figure in the extract took.
        """
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], days=1800)
        with self.assertRaises(StaleReadError):
            slr.check_declared_lag(entry, self.rows)

    def test_the_declaration_is_record_date_calendar_days(self):
        entry = dict(self.entry)
        entry["release_lag"] = dict(entry["release_lag"], basis="snapshot_retrieved_at")
        with self.assertRaises(ValueError):
            slr.check_declared_lag(entry, self.rows)

    def test_the_worst_case_lag_is_the_declared_one(self):
        self.assertEqual(slr.worst_case_lag_days(self.rows), self.entry["release_lag"]["days"])


class ReadGuardTests(unittest.TestCase):
    """The exact, row-by-row reader. The panel-level guard under the parent's `InformationRule` is in test_guards.py."""

    @classmethod
    def setUpClass(cls):
        cls.rows = slr.load_extract(EXTRACT)
        by_bank = [r for r in cls.rows if r.idrssd == JPM]
        cls.first, cls.second = sorted(by_bank, key=lambda r: r.quarter_end)[:2]

    def at(self, row, offset=timedelta(0)):
        return row.available_from + offset

    def test_a_figure_is_read_from_the_instant_it_is_available(self):
        row = slr.read(self.rows, JPM, self.first.quarter_end, self.at(self.first))
        self.assertEqual(row, self.first)

    def test_a_read_before_the_latest_update_is_look_ahead(self):
        """Leakage guard: a figure read before its latest-update time raises LookAheadError.

        Recorded mutation (14 October 2026): in `repo_liquidity.slr.read`, the branch
        `if row.available_from > at: raise LookAheadError(...)` replaced by `if False:`. This test then fails with
        `AssertionError: LookAheadError not raised` (the figure is returned).
        """
        with self.assertRaises(LookAheadError):
            slr.read(self.rows, JPM, self.first.quarter_end, self.at(self.first, -timedelta(seconds=1)))

    def test_a_read_of_an_older_quarter_than_the_latest_public_is_stale(self):
        """Staleness guard: once a later quarter is public, an earlier one is stale.

        Recorded mutation (14 October 2026): in `repo_liquidity.slr.read`, the branch
        `if latest is not None and latest.quarter_end > quarter_end: raise StaleReadError(...)` replaced by `if False:`.
        This test then fails with `AssertionError: StaleReadError not raised`.
        """
        later = max(self.first.available_from, self.second.available_from)
        with self.assertRaises(StaleReadError):
            slr.read(self.rows, JPM, self.first.quarter_end, later)

    def test_the_latest_public_quarter_is_the_one_whose_update_has_passed(self):
        before = min(self.first.available_from, self.second.available_from) - timedelta(seconds=1)
        self.assertIsNone(slr.latest_public(self.rows, JPM, before))
        for row in (self.first, self.second):
            public = [r for r in self.rows if r.idrssd == JPM and r.available_from <= row.available_from]
            self.assertEqual(slr.latest_public(self.rows, JPM, row.available_from).quarter_end,
                             max(r.quarter_end for r in public))

    def test_a_decision_instant_without_a_time_zone_is_refused(self):
        with self.assertRaises(ValueError):
            slr.read(self.rows, JPM, self.first.quarter_end, datetime(2030, 1, 1))

    def test_a_quarter_not_in_the_extract_is_refused(self):
        with self.assertRaises(ValueError):
            slr.read(self.rows, JPM, date(2018, 4, 1), self.at(self.first))

    def test_the_observations_are_public_from_the_update_not_before(self):
        observations = slr.observations(self.rows, "slr_ratio", source_sha="0" * 64)
        self.assertEqual(len(observations), sum(1 for r in self.rows if r.measure == slr.MAIN))
        by_key = {(o.series_id, o.ref_date): o for o in observations}
        item = by_key[(f"slr_ratio:{JPM}", self.first.quarter_end)]
        self.assertEqual(item.available_at, self.first.available_from)
        self.assertEqual(item.value, self.first.slr_pct)

    def test_a_headroom_observation_is_not_made_for_a_quarter_with_no_requirement(self):
        observations = slr.observations(self.rows, "slr_headroom", source_sha="0" * 64)
        self.assertEqual(len(observations), sum(1 for r in self.rows if r.headroom_pp is not None and r.measure == slr.MAIN))

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(ValueError):
            slr.observations(self.rows, "h8_large_domestic_cash_assets", source_sha="0" * 64)


def synthetic_table():
    """A requirement table that is not the real one: 5.0 in 2019, nothing in 2020, 4.0 from 2021 on."""
    return (slr.RequirementPeriod(date(2019, 1, 1), date(2020, 1, 1), 5.0, "synthetic A"),
            slr.RequirementPeriod(date(2020, 1, 1), date(2021, 1, 1), None, "synthetic: bank-specific"),
            slr.RequirementPeriod(date(2021, 1, 1), None, 4.0, "synthetic B"))


class RequirementTableTests(unittest.TestCase):
    """The headroom reads the requirement in force on the quarter-end from a table (#71, Q1).

    Recorded mutation (the table is read, not a constant): in `slr.requirement_for`, replace the lookup loop's
    `return period.requirement_pct` with `return 6.0`; `test_the_requirement_follows_the_periods_of_the_table` fails
    with AssertionError (5.0 != 6.0).
    """

    def test_the_requirement_follows_the_periods_of_the_table(self):
        table = synthetic_table()
        self.assertEqual(slr.requirement_for(date(2019, 6, 30), table), 5.0)
        self.assertEqual(slr.requirement_for(date(2021, 3, 31), table), 4.0)
        self.assertEqual(slr.requirement_for(date(2030, 12, 31), table), 4.0)

    def test_a_period_with_no_value_and_a_date_with_no_period_stay_blank(self):
        table = synthetic_table()
        self.assertIsNone(slr.requirement_for(date(2020, 6, 30), table))
        self.assertIsNone(slr.requirement_for(date(2018, 12, 31), table))
        self.assertIsNone(slr.headroom_for(7.0, date(2020, 6, 30), table))
        self.assertEqual(slr.headroom_for(7.0, date(2019, 6, 30), table), 2.0)

    def test_the_period_starts_on_its_first_day_and_ends_before_its_end_day(self):
        table = synthetic_table()
        self.assertIsNone(slr.requirement_for(date(2018, 12, 31), table))
        self.assertEqual(slr.requirement_for(date(2019, 1, 1), table), 5.0)
        self.assertIsNone(slr.requirement_for(date(2020, 1, 1), table))
        self.assertEqual(slr.requirement_for(date(2021, 1, 1), table), 4.0)

    def test_a_row_reads_the_table_in_force(self):
        row = slr.Row(date(2019, 6, 30), JPM, "bank", datetime(2019, 8, 1), "RCFA", 70, 1000, None, "0" * 64)
        self.assertEqual(row.headroom_pp, 1.0)
        original = slr.REQUIREMENT_TABLE
        slr.REQUIREMENT_TABLE = synthetic_table()
        try:
            self.assertEqual(row.requirement_pct, 5.0)
            self.assertEqual(row.headroom_pp, 2.0)
        finally:
            slr.REQUIREMENT_TABLE = original

    def test_overlapping_or_unordered_periods_are_refused(self):
        a = slr.RequirementPeriod(date(2019, 1, 1), date(2021, 1, 1), 5.0, "a")
        b = slr.RequirementPeriod(date(2020, 1, 1), None, 4.0, "b")
        with self.assertRaises(ValueError):
            slr.requirement_for(date(2020, 6, 30), (a, b))
        with self.assertRaises(ValueError):
            slr.requirement_for(date(2020, 6, 30), (b, a))

    def test_the_real_table_is_the_draft_record_and_nothing_else(self):
        text = (ROOT / "docs" / "decisions" / "slr-requirement.md").read_text(encoding="utf-8")
        self.assertIn("DRAFT", text)
        self.assertEqual([(p.start.isoformat(), p.end.isoformat() if p.end else None, p.requirement_pct)
                          for p in slr.REQUIREMENT_TABLE],
                         [("2018-01-01", "2026-04-01", 6.0), ("2026-04-01", None, None)])
        for period in slr.REQUIREMENT_TABLE:
            self.assertIn(period.start.isoformat(), text)
            self.assertIn(period.citation, text)


class StateStreetTests(unittest.TestCase):
    """State Street is the G-SIB bank (IDRSSD 35301) and is in the main measure (Eleonora, 15 October 2026).

    PR #67 read IDRSSD 93619, State Street Bank and Trust Company, N.A.: a non-depository trust subsidiary of about $65
    million whose tier 1 capital is close to its total exposure, so its ratio was near 100%. The bank of the G-SIB is
    State Street Bank and Trust Company, IDRSSD 35301. With the right bank there is nothing to keep apart, so her ruling
    on #69 (Q2, 14 October 2026) is replaced: State Street is in the main measure.

    Recorded mutations. (1) Put IDRSSD 93619 back in `slr.BANKS` in place of 35301: `test_state_street_is_the_g_sib_bank`
    fails with AssertionError. (2) Set `slr.SENSITIVITY_BANKS` back to `(35301,)`: `setUpClass` fails with ValueError from
    `load_extract` (the stored `measure` `main` is not what the figures give).
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = slr.load_extract(EXTRACT)

    def test_state_street_is_the_g_sib_bank(self):
        self.assertIn(STATE_STREET, slr.BANKS)
        self.assertNotIn(STATE_STREET_TRUST_NA, slr.BANKS)
        self.assertEqual(slr.BANKS[STATE_STREET], "State Street Bank and Trust Company")

    def test_state_street_is_in_the_main_measure(self):
        ours = [r for r in self.rows if r.idrssd == STATE_STREET]
        self.assertTrue(ours)
        self.assertEqual({r.measure for r in ours}, {slr.MAIN})
        for field in ("slr_tier1_capital", "slr_total_leverage_exposure", "slr_ratio"):
            series = {o.series_id for o in slr.observations(self.rows, field, source_sha="0" * 64)}
            self.assertIn(f"{field}:{STATE_STREET}", series, field)

    def test_there_is_no_sensitivity_series(self):
        self.assertEqual([r for r in self.rows if r.measure != slr.MAIN], [])
        for field in slr.FIELDS:
            self.assertEqual(slr.sensitivity_observations(self.rows, field, source_sha="0" * 64), [])

    def test_every_kept_ratio_is_a_bank_ratio(self):
        """A G-SIB bank's ratio is a few percent; the trust company's was near 100%. 20% is far above any bank's."""
        for row in self.rows:
            self.assertLess(row.slr_pct, 20.0, (row.institution, row.quarter_end))

    def test_a_row_labelled_sensitivity_is_refused(self):
        path = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, path)
        for name in (slr.EXTRACT_NAME, slr.EXTRACT_NAME + ".manifest.json"):
            shutil.copy(DIRECTORY / name, path / name)
        target = path / slr.EXTRACT_NAME
        data = target.read_bytes().replace(b",main,", b",sensitivity_state_street,", 1)
        self.assertNotEqual(data, target.read_bytes())
        target.write_bytes(data)
        import hashlib
        manifest = path / (slr.EXTRACT_NAME + ".manifest.json")
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["sha256"] = hashlib.sha256(data).hexdigest()
        manifest.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(ValueError):
            slr.load_extract(target)


if __name__ == "__main__":
    unittest.main()
