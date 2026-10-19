"""H7m, groundwork G6, third record: the study's script (`scripts/g6_power_study.py --third`, `docs/stages/h7-g6.md` §11).

Synthetic days only. **No part of the study is run on the real days in this tree** (`needs-mac`, Eleonora's standing rule of
19 October 2026): the study runs on her Mac, and these tests check the plumbing -- the declared seeds, the cells, the three
processes, the two tests, the readings and the tables -- on a made-up world with the same shape.

**Recorded mutation** (CLAUDE.md), 19 October 2026, in a disposable copy of the tree, CPython 3.11, the parent at the pin
(8fd2cf8), applied by `sed` and confirmed by `grep`, the module run against the copy, the copy discarded: the seed base
`THIRD_SEED = 2026101900` in `scripts/g6_power_study.py` replaced by `THIRD_SEED = 20261014` (the second record's base, so
the "fresh seeds" rule is broken): `test_the_seeds_are_fresh_and_disjoint_from_every_earlier_record` failed with
`AssertionError: 20261014 != 2026101900`.

Written first, and watched failing: before the script had `run_third` this module failed on
`AttributeError: module 'g6_power_study' has no attribute 'run_third'`.
"""

import importlib.util
import json
import random
import unittest
from datetime import date, timedelta
from pathlib import Path

from repo_liquidity import goalposts as gp

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("g6_power_study", ROOT / "scripts" / "g6_power_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _world(n=420, seed=5, start=date(2025, 1, 2)):
    """Business days from `start`: a ratio, a sticky 0-3 state, a calendar and calendar-tied events related to the ratio."""
    rng = random.Random(seed)
    days, calendar, state = [], {}, 1.0
    day = start
    while len(days) < n:
        if day.weekday() < 5:
            i = len(days)
            if rng.random() < 0.1:
                state = float(rng.randrange(4))
            flags = gp.Calendar(int(day.day in (15, 16, 17)), int(day.day >= 28), int(i % 63 == 62), int(i == 200))
            ratio = rng.gauss(0.0, 1.0)
            p = 0.04 + 0.25 * (flags.quarter_end or flags.coupon_end) + 0.1 * (ratio < -0.8)
            days.append(gp.LabelledDay(day, int(rng.random() < p), ratio, state))
            calendar[day] = flags
        day += timedelta(days=1)
    return days, calendar


SMALL = dict(grid=(0.0, 0.05, 0.10), lengths=(150, 300), baseline=150, replicates=5, reference=40, floor_series=40,
             floor_days=120, draws=300, workers=1)


class DeclarationTests(unittest.TestCase):
    def test_the_seeds_are_fresh_and_disjoint_from_every_earlier_record(self):
        """Earlier records seed from 20261014 plus an index below 300,000; the third's ranges must not meet them."""
        script = _script()
        self.assertEqual(script.THIRD_SEED, 2026101900)
        self.assertGreater(script.THIRD_SEED, 20261014 + 300000)
        earlier = set()
        for base in (20261014, 20261014 + 100000, 20261014 + 200000):
            earlier |= set(range(base, base + 2000))
        earlier |= set(range(20261014, 20261014 + 30000))
        ours = set()
        for offset, count in ((0, 400), (100000, 2000), (200000, 200)):
            ours |= set(range(script.THIRD_SEED + offset, script.THIRD_SEED + offset + count))
        self.assertFalse(earlier & ours)

    def test_it_holds_what_section_11_declares(self):
        script = _script()
        self.assertEqual(script.THIRD_LENGTHS, (250, 500, 750))
        self.assertEqual(script.THIRD_PROCESSES, ("independent", "two_state", "calendar"))
        self.assertEqual(script.THIRD_TESTS, ("section5", "calendar_strata"))
        self.assertEqual((script.THIRD_REPLICATES, script.THIRD_REFERENCE, script.THIRD_FLOOR_SERIES,
                          script.THIRD_FLOOR_DAYS), (400, 200, 2000, 1000))
        self.assertEqual(script.THIRD_LOOK, 2)
        self.assertEqual(script.GRID, (0.0, 0.02, 0.035, 0.05, 0.065, 0.08, 0.10, 0.125, 0.15))
        text = (ROOT / "docs" / "stages" / "h7-g6.md").read_text(encoding="utf-8")
        for needle in ("## 11.", "2026101900", "calendar-tied", "500 and 750", "calendar-stratified", "ridge", "Q7"):
            self.assertIn(needle, text)

    def test_the_study_is_never_smoke_run_on_the_real_days(self):
        with self.assertRaises(SystemExit):
            _script().main(["--third", "--smoke"])


class WindowTests(unittest.TestCase):
    def test_the_baseline_is_the_first_days_from_2025_and_the_longer_windows_the_last_days(self):
        script = _script()
        days, _ = _world(900, start=date(2024, 1, 2))
        first = script.third_days(days, 250)
        self.assertEqual(len(first), 250)
        self.assertEqual(first[0].day, next(d.day for d in days if d.day >= date(2025, 1, 1)))
        for length in (500, 750):
            last = script.third_days(days, length)
            self.assertEqual((len(last), last[-1].day), (length, days[-1].day))

    def test_too_few_days_is_a_data_error(self):
        script = _script()
        days, _ = _world(200)
        with self.assertRaises(ValueError):
            script.third_days(days, 250)
        with self.assertRaises(ValueError):
            script.third_days(days, 500)


class RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _script()
        cls.days, cls.calendar = _world()
        cls.record = cls.script.run_third(cls.days, cls.calendar, **SMALL)

    def test_it_declares_its_seeds_options_and_pins(self):
        declared = self.record["declaration"]
        self.assertEqual(declared["seed"], 2026101900)
        self.assertEqual(declared["lengths"], [150, 300])
        self.assertEqual(declared["tests"], ["section5", "calendar_strata"])
        self.assertEqual(declared["draws"], 300)
        self.assertEqual(declared["mme"], gp.MME)
        self.assertEqual(declared["nominal_level"], gp.nominal_level(2))
        self.assertIn("No candidate is scored", self.record["what"])

    def test_every_process_has_its_fit_floor_study_and_every_length_a_cell(self):
        self.assertEqual(list(self.record["processes"]), ["independent", "two_state", "calendar"])
        for name, entry in self.record["processes"].items():
            self.assertEqual(list(entry["cells"]), ["150", "300"], name)
            self.assertEqual(entry["days_to_the_event_floor"]["series"], 40)

    def test_the_fits_are_the_declared_ones(self):
        fits = {name: entry["fit"] for name, entry in self.record["processes"].items()}
        fitted = [d for d in self.days if d.day >= date(2025, 1, 1)]
        event = [d.event for d in fitted]
        self.assertAlmostEqual(fits["independent"]["share"], sum(event) / len(event))
        two = gp.fit_event_process(event)
        self.assertEqual((fits["two_state"]["start"], fits["two_state"]["stay"]), (two.start, two.stay))
        calendar = gp.fit_calendar_process(event, [self.calendar[d.day] for d in fitted])
        self.assertEqual(fits["calendar"]["coefficients"], list(calendar.coefficients))
        self.assertEqual(fits["calendar"]["ridge"], gp.RIDGE)
        self.assertEqual(sorted(fits["calendar"]["implied_probabilities"]), ["previous_event", "previous_quiet"])

    def test_a_cell_holds_both_tests_at_every_gain_with_the_readings_and_counts(self):
        cell = self.record["processes"]["calendar"]["cells"]["150"]
        self.assertEqual(cell["replicates"], 5)
        self.assertEqual(cell["planting"]["reference_series"], 40)
        for test in ("section5", "calendar_strata"):
            gains = cell["tests"][test]["gains"]
            self.assertEqual(list(gains), ["0.0", "0.05", "0.1"])
            for row in gains.values():
                self.assertEqual(row["all_replicates"]["replicates"], 5)
                self.assertEqual(row["replicates_at_the_floor"]["replicates"], cell["replicates_at_the_event_floor"])
                self.assertLessEqual(row["all_replicates"]["supported"], 5)

    def test_every_share_is_its_count_over_its_replicates_with_a_wilson_interval(self):
        for entry in self.record["processes"].values():
            for cell in entry["cells"].values():
                for test in cell["tests"].values():
                    for row in test["gains"].values():
                        for key in ("all_replicates", "replicates_at_the_floor"):
                            r = row[key]
                            if not r["replicates"]:
                                self.assertIsNone(r["share"])
                                continue
                            self.assertAlmostEqual(r["share"], r["supported"] / r["replicates"])
                            low, high = gp.wilson(r["supported"], r["replicates"])
                            self.assertEqual(r["interval"], [low, high])

    def test_the_longer_window_is_the_last_days_and_the_baseline_the_first_from_2025(self):
        cells = self.record["processes"]["two_state"]["cells"]
        self.assertEqual(cells["150"]["first_day"], self.days[0].day.isoformat())
        self.assertEqual(cells["300"]["last_day"], self.days[-1].day.isoformat())
        self.assertEqual(cells["150"]["days"], 150)
        self.assertEqual(cells["300"]["days"], 300)

    def test_the_planting_met_the_declared_tolerance_where_it_could(self):
        for entry in self.record["processes"].values():
            for cell in entry["cells"].values():
                for target, shift in cell["planting"]["shift_in_sigma"].items():
                    if float(target) == 0.0:
                        continue  # the null plants nothing; its "miss" is the tie-breaking noise
                    miss = cell["planting"]["mean_gain_on_the_reference_series"][target]["miss"]
                    self.assertLessEqual(abs(miss), gp.CALIBRATION_TOLERANCE + 1e-12)
                self.assertEqual(cell["planting"]["shift_in_sigma"]["0.0"], 0.0)

    def test_the_run_is_deterministic(self):
        again = self.script.run_third(self.days, self.calendar, **SMALL)
        for record in (self.record, again):
            record.pop("seconds")
        self.assertEqual(json.dumps(self.record, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_without_a_calendar_the_stratified_test_is_the_section5_test(self):
        """Every day in calendar class 0: the strata are the scarcity state's, and the two tests must agree draw for draw."""
        plain = {d: gp.Calendar(0, 0, 0, 0) for d in self.calendar}
        record = self.script.run_third(self.days, plain, **{**SMALL, "lengths": (150,), "baseline": 150},
                                       processes=("two_state",))
        cell = record["processes"]["two_state"]["cells"]["150"]["tests"]
        self.assertEqual(cell["section5"]["gains"], cell["calendar_strata"]["gains"])

    def test_the_processes_run_one_at_a_time(self):
        record = self.script.run_third(self.days, self.calendar, **SMALL, processes=("independent",))
        self.assertEqual(list(record["processes"]), ["independent"])
        self.assertEqual(record["processes"]["independent"]["cells"]["150"]["tests"]["section5"],
                         self.record["processes"]["independent"]["cells"]["150"]["tests"]["section5"])

    def test_a_day_without_its_calendar_row_is_a_data_error(self):
        missing = dict(self.calendar)
        del missing[self.days[-1].day]
        with self.assertRaises(ValueError):
            self.script.run_third(self.days, missing, **SMALL)


class AssembleAndTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _script()
        cls.days, cls.calendar = _world()
        cls.parts = {name: cls.script.run_third(cls.days, cls.calendar, **SMALL, processes=(name,))
                     for name in cls.script.THIRD_PROCESSES}
        cls.whole = cls.script.run_third(cls.days, cls.calendar, **SMALL)

    def test_the_parts_assemble_into_the_whole(self):
        assembled = self.script.assemble_third(list(self.parts.values()))
        for record in (assembled, self.whole):
            record.pop("seconds", None)
        self.assertEqual(json.dumps(assembled, sort_keys=True), json.dumps(self.whole, sort_keys=True))

    def test_a_missing_process_or_parts_made_at_different_pins_are_refused(self):
        with self.assertRaises(ValueError):
            self.script.assemble_third([self.parts["independent"], self.parts["two_state"]])
        other = json.loads(json.dumps(self.parts["calendar"]))
        other["pins"]["parent"] = "0" * 40
        with self.assertRaises(ValueError):
            self.script.assemble_third([self.parts["independent"], self.parts["two_state"], other])

    def test_the_tables_print_every_cell_and_its_counts(self):
        text = self.script.tables_third(self.whole)
        for name in self.script.THIRD_PROCESSES:
            self.assertIn(name, text)
        self.assertIn("150 days", text)
        self.assertIn("300 days", text)
        self.assertIn("section5", text)
        self.assertIn("calendar_strata", text)
        self.assertIn("(size)", text)
        self.assertEqual(text, self.script.tables_third(json.loads(json.dumps(self.whole))))


if __name__ == "__main__":
    unittest.main()
