"""H10's second declaration, step 2 (#209): the nine-driver development attribution, run in pieces, beside the registered method.

The full run (512 subsets on each of 10,000 bootstrap draws, 31 episodes, a 1,000-draw null) is a run for Eleonora's Mac. These
tests run the same code path on every development episode with a handful of draws, labelled a smoke run: they show that the pieces,
the assembly, the guards and the rendering work, and prove nothing about the figures.
"""

import hashlib
import json
import pathlib
import shutil
import tempfile
import unittest
from datetime import date
from unittest import mock

from repo_model.splits import LookAheadError

from repo_liquidity import attribution, h10_apply, h10_apply_2 as h2, h10_drivers_2 as d2, h10_live, h10_registration

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTERED_RECORD_SHA256 = "21fa38197d75822024a121106510a6b340cb842ddd2cbf5c643226e34b8dd8af"
SMOKE_DRAWS, SMOKE_NULL_DRAWS = 20, 2


class LabelTests(unittest.TestCase):
    def test_every_driver_has_an_axis_and_fails_is_the_collateral_one(self):
        self.assertEqual(set(h2.DRIVER_LABELS), set(d2.DRIVERS_2))
        self.assertEqual(h2.DRIVER_LABELS["pd_fails_deliver_ust"], "collateral")
        self.assertEqual([n for n, axis in h2.DRIVER_LABELS.items() if axis == "collateral"], ["pd_fails_deliver_ust"])
        for name, axis in h2.DRIVER_LABELS.items():
            if name != "pd_fails_deliver_ust":
                self.assertIn(axis, ("cash-side", "calendar"), name)
        self.assertEqual(h2.label("pd_fails_deliver_ust"), "pd_fails_deliver_ust (collateral)")

    def test_the_driver_set_is_the_nine_in_one_fit(self):
        self.assertEqual(len(d2.DRIVERS_2), 9)
        self.assertEqual(h2.run_settings(10_000, 1_000, smoke=False)["drivers"], list(d2.DRIVERS_2))
        self.assertEqual(h2.run_settings(10_000, 1_000, smoke=False)["report_days"], 11)


class RegisteredMethodUntouchedTests(unittest.TestCase):
    def test_the_registered_digest_and_record_are_unchanged(self):
        self.assertEqual(h10_live.method_digest(), h10_registration.REGISTERED_DIGEST)
        self.assertTrue(h10_registration.REGISTERED_DIGEST.startswith("54b5f151"))
        self.assertTrue(h10_registration.REGISTERED_DIGEST.endswith("8770"))
        self.assertEqual(hashlib.sha256(h10_apply.RECORD.read_bytes()).hexdigest(), REGISTERED_RECORD_SHA256)
        covered = {name for name, _ in h10_live.METHOD_FILES}
        self.assertFalse([n for n in covered if "apply_2" in n or "pd_fails" in n or "panel_v6" in n])
        self.assertEqual(h10_apply.REPORT_DAYS, 10)
        self.assertEqual(h10_apply.PANEL_VERSION, 5)


class SmokeRunTests(unittest.TestCase):
    """A smoke run over every development episode, at 20 bootstrap draws and 2 null draws."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name) / "pieces"
        cls.report = h2.run_pieces(cls.out, draws=SMOKE_DRAWS, null_draws=SMOKE_NULL_DRAWS, smoke=True)
        cls.registered = json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))
        cls.record = h2.build_record(cls.out, allow_smoke=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_piece_per_episode_and_one_for_the_null(self):
        names = sorted(p.name for p in self.out.glob("*.json"))
        self.assertEqual(len(names), len(self.registered["episodes"]) + 1)
        self.assertIn("null.json", names)
        for episode in self.registered["episodes"]:
            self.assertIn(f"episode-{episode['onset']}.json", names)
        self.assertEqual(sorted(self.report["written"]), names)

    def test_a_rerun_skips_what_finished_and_a_lost_piece_costs_only_itself(self):
        lost = self.out / h2.piece_name(self.registered["episodes"][3]["onset"])
        copy = pathlib.Path(self.tmp.name) / "copy"
        shutil.copytree(self.out, copy)
        (copy / lost.name).unlink()
        again = h2.run_pieces(copy, draws=SMOKE_DRAWS, null_draws=SMOKE_NULL_DRAWS, smoke=True)
        self.assertEqual(again["written"], [lost.name])
        self.assertEqual(len(again["skipped_existing"]), len(self.registered["episodes"]))

    def test_a_piece_run_with_other_settings_is_not_skipped(self):
        piece = json.loads((self.out / "null.json").read_text(encoding="utf-8"))
        self.assertTrue(h2._same_run(piece, piece["settings"], piece["panel_sha256"]))
        self.assertFalse(h2._same_run(piece, {**piece["settings"], "draws": 10_000}, piece["panel_sha256"]))
        self.assertFalse(h2._same_run(piece, piece["settings"], "0" * 64))

    def test_the_record_is_labelled_a_smoke_run_and_a_smoke_run_is_never_a_record(self):
        self.assertTrue(self.record["smoke"])
        with self.assertRaises(ValueError) as caught:
            h2.build_record(self.out)
        self.assertIn("smoke", str(caught.exception))

    def test_every_episode_of_the_registered_record_is_in_the_table_attributed_or_not(self):
        self.assertEqual([e["onset"] for e in self.record["episodes"]], [e["onset"] for e in self.registered["episodes"]])
        self.assertEqual(self.record["summary"]["episodes"], len(self.registered["episodes"]))
        for entry in self.record["episodes"]:
            self.assertIn(entry["status"], ("attributed", "not attributable"))
            if entry["status"] == "attributed":
                self.assertEqual(set(entry["shares"]), set(d2.DRIVERS_2))
                for name in d2.DRIVERS_2:
                    share = entry["shares"][name]
                    self.assertLessEqual(share["low"], share["high"])
                self.assertIn("placebo", entry)
                self.assertIn("placebo_floored", entry)
                self.assertLessEqual(entry["placebo_floored"]["attributed"], entry["placebo"]["attributed"])
                self.assertEqual(entry["placebo_floored"]["windows"], entry["placebo"]["windows"])
            else:
                self.assertTrue(entry["reason"])
        self.assertEqual(len(self.record["not_attributable"]), self.record["summary"]["not_attributable"])

    def test_the_shapley_shares_and_the_residual_add_to_one(self):
        for entry in self.record["episodes"]:
            if entry["status"] == "attributed":
                total = sum(s["point"] for s in entry["shares"].values()) + entry["residual"]["point"]
                self.assertAlmostEqual(total, 1.0, places=9, msg=entry["onset"])

    def test_the_report_day_is_eleven_panel_days_after_the_onset(self):
        rows, dates, *_ = h2.load_inputs()
        for entry in self.record["episodes"]:
            self.assertEqual(entry["report_day"], dates[entry["index"] + 11].isoformat())

    def test_the_five_drivers_refitted_here_reproduce_the_registered_record(self):
        """The comparison is like for like: the registered five on panel version 6 give the published residual shares. Recorded
        mutation (11 November 2026): in `h10_apply_2.check_reproduces_registered`, `if worst > REPRODUCTION_TOLERANCE:`
        changed to `if False:`, and the registered record's residual of the first episode moved by 0.01 in the copy the
        test passes. `test_a_comparison_that_is_not_like_for_like_is_refused` failed with AssertionError (ValueError not
        raised)."""
        self.assertLess(self.record["comparison"]["five_driver_reproduction_max_abs_difference"], h2.REPRODUCTION_TOLERANCE)
        self.assertEqual(self.record["comparison"]["registered_record"]["sha256"], REGISTERED_RECORD_SHA256)

    def test_a_comparison_that_is_not_like_for_like_is_refused(self):
        moved = json.loads(json.dumps(self.registered))
        first = next(e for e in moved["episodes"] if e["status"] == "attributed")
        first["residual"]["point"] += 0.01
        with self.assertRaises(ValueError):
            h2.check_reproduces_registered(self.record["episodes"], moved)
        short = {**self.registered, "episodes": self.registered["episodes"][:-1]}
        with self.assertRaises(ValueError):
            h2.check_reproduces_registered(self.record["episodes"], short)

    def test_the_paired_comparison_has_the_splits_and_intervals(self):
        paired = self.record["comparison"]["paired_residual"]
        self.assertEqual(paired["all"]["episodes"], len(paired["episodes"]))
        self.assertEqual(paired["regime"]["depleted"]["episodes"] + paired["regime"]["abundant"]["episodes"], paired["all"]["episodes"])
        self.assertEqual(paired["day_type"]["quarter-end"]["episodes"] + paired["day_type"]["other"]["episodes"], paired["all"]["episodes"])
        interval = paired["all"]["median_paired_difference_nine_less_five"]["interval"]
        self.assertLessEqual(interval[0], interval[1])
        five = self.record["comparison"]["registered_record"]["summary"]
        self.assertEqual(five["not_attributable"], 0)
        self.assertEqual(five["under_bar"], paired["all"]["under_bar_five"])

    def test_no_episode_meets_the_2027_break_and_the_record_says_so(self):
        rows, dates, series, raw_on_rrp, onsets, placebo, manifest = h2.load_inputs()
        self.assertEqual(h2.meets_break(dates, onsets), 0)
        self.assertEqual(self.record["report_window"]["development_episodes_meeting_the_break"], 0)
        self.assertEqual(self.record["report_window"]["report_days"], 11)
        self.assertIn("not tested on development data", self.record["report_window"]["statement"])
        self.assertLess(dates[-1], d2.BREAK_DATE)

    def test_no_day_after_the_development_end_is_read(self):
        from repo_liquidity import development

        self.assertLessEqual(date.fromisoformat(self.record["last_report_day_read"]), development.development_end())

    def test_the_new_inputs_are_not_public_a_day_early(self):
        """The nine drivers go through the parent's as-of rule at the report day. Fails are public 11 panel days after an onset,
        so a report at 10 is a look-ahead on them: the registered method's own guard (`attribution.check_window_public`) raises
        `LookAheadError` on the nine-driver rule, which is why this declaration reports at 11."""
        rows, dates, series, raw_on_rrp, onsets, placebo, manifest = h2.load_inputs()
        with d2.rule_2() as rule:
            with self.assertRaises(LookAheadError):
                attribution.check_window_public(rule, dates, onsets[10], onsets[10] + 10)
            attribution.check_window_public(rule, dates, onsets[10], onsets[10] + 11)

    def test_the_page_shows_fails_as_collateral_and_the_registered_table_unchanged(self):
        page = h2.render_markdown(self.record, self.registered)
        self.assertIn("pd_fails_deliver_ust (collateral)", page)
        self.assertNotIn("| pd_fails_deliver_ust |", page)
        self.assertIn("collateral driver", page)
        self.assertIn(h10_apply.table_markdown(self.registered), page)
        self.assertIn(h10_apply.summary_markdown(self.registered), page)
        self.assertIn("not a verdict", page)
        self.assertIn(h2.comparison_markdown(self.record), page)
        for name in d2.DRIVERS_2:
            self.assertIn(h2.label(name), page)


class AssemblyGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name) / "pieces"
        h2.run_pieces(cls.out, draws=SMOKE_DRAWS, null_draws=SMOKE_NULL_DRAWS, smoke=True, limit=2)
        cls.registered = json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_lost_piece_is_named_and_no_record_is_assembled(self):
        with self.assertRaises(ValueError) as caught:
            h2.build_record(self.out, allow_smoke=True)
        self.assertIn("piece(s) missing", str(caught.exception))
        self.assertIn(h2.piece_name(self.registered["episodes"][5]["onset"]), str(caught.exception))
        self.assertEqual(len(h2.missing_pieces(self.out, [e["onset"] for e in self.registered["episodes"]])),
                         len(self.registered["episodes"]) - 2)

    def test_pieces_of_two_commits_are_not_assembled(self):
        """Recorded mutation (11 November 2026): in `h10_apply_2.build_record`, the commit comparison
        `if piece["provenance"]["repo_commit"] != first["provenance"]["repo_commit"]:` changed to `if False:`. This test failed
        with KeyError: 'registered_five' (the assembly went on to read the mixed pieces)."""
        directory = pathlib.Path(self.tmp.name) / "mixed"
        shutil.copytree(self.out, directory)
        for onset in [e["onset"] for e in self.registered["episodes"]]:
            path = directory / h2.piece_name(onset)
            if not path.exists():
                piece = json.loads((self.out / "null.json").read_text(encoding="utf-8"))
                piece.update(piece="episode", episode={"onset": onset})
                path.write_text(json.dumps(piece), encoding="utf-8")
        other = json.loads((directory / h2.piece_name(self.registered["episodes"][0]["onset"])).read_text(encoding="utf-8"))
        other["provenance"]["repo_commit"] = "0" * 40
        (directory / h2.piece_name(self.registered["episodes"][0]["onset"])).write_text(json.dumps(other), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            h2.build_record(directory, allow_smoke=True)
        self.assertIn("another commit", str(caught.exception))

    def test_a_full_run_is_refused_from_a_modified_tree(self):
        """Recorded mutation (11 November 2026): in `h10_apply_2.run_pieces`, `if not smoke and require_clean and
        prov["tree_modified"]:` changed to `if False:`. This test failed with RuntimeError ("a full run must not start", from the patched
        `load_inputs`: the run went on past the refused point)."""
        prov = {"repo_commit": "a" * 40, "tree_modified": True, "python": "3.11", "platform": "x"}
        # `load_inputs` is patched so that a guard that stopped refusing could never start a full run in a test.
        with mock.patch.object(h2, "provenance", return_value=prov), \
                mock.patch.object(h2, "load_inputs", side_effect=RuntimeError("a full run must not start")):
            with self.assertRaises(ValueError):
                h2.run_pieces(pathlib.Path(self.tmp.name) / "full", smoke=False)
            self.assertFalse((pathlib.Path(self.tmp.name) / "full").exists())

    def test_a_smoke_run_does_not_write_where_the_record_is_assembled_from(self):
        with self.assertRaises(ValueError):
            h2.run_pieces(h2.PIECES_DIR, smoke=True)

    def test_the_assembly_refuses_if_the_registered_digest_moved(self):
        """Recorded mutation (11 November 2026): in `h10_apply_2.build_record`, the digest comparison changed to `if False:`
        with `h10_live.method_digest` patched to return another digest. This test failed with AssertionError ("digest
        moved" not in the message: the assembly went on to the missing-piece refusal)."""
        with mock.patch.object(h10_live, "method_digest", return_value="0" * 64):
            with self.assertRaises(ValueError) as caught:
                h2.build_record(self.out, allow_smoke=True)
        self.assertIn("digest moved", str(caught.exception))


class TrackedRecordTests(unittest.TestCase):
    """Once the Mac run has come back, the record and the page it renders to are tracked; until then neither exists."""

    def test_the_tracked_page_is_what_the_tracked_record_renders_to(self):
        if not h2.RECORD.is_file():
            self.skipTest("the Mac run has not come back: results/h10/development_2.json is not tracked yet")
        self.assertEqual(h2.PAGE.read_text(encoding="utf-8"), h2.render_tracked())

    def test_the_tracked_record_is_a_full_clean_run_of_the_registered_settings(self):
        if not h2.RECORD.is_file():
            self.skipTest("the Mac run has not come back: results/h10/development_2.json is not tracked yet")
        record = json.loads(h2.RECORD.read_text(encoding="utf-8"))
        self.assertFalse(record["smoke"])
        self.assertFalse(record["provenance"]["tree_modified"])
        self.assertEqual(record["settings"]["draws"], attribution.DRAWS)
        self.assertEqual(record["settings"]["null_draws"], attribution.NULL_DRAWS)
        self.assertEqual(record["settings"]["drivers"], list(d2.DRIVERS_2))
        self.assertEqual(record["registered_method_digest"], h10_registration.REGISTERED_DIGEST)
        self.assertEqual(record["tier"], "development")
        self.assertEqual(record["panel"]["sha256"], json.loads((ROOT / "metadata/phase3_panel_v6_manifest.json").read_text())["sha256"])


if __name__ == "__main__":
    unittest.main()
