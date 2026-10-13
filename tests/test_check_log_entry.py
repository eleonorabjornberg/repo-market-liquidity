"""The research-log check (`scripts/check_log_entry.py`), one test per failure mode.

The format is the one decided on #20 (its second comment, adopted by Eleonora on 12 October 2026 with the plan) and
passed to repo-market-model#638 as the shared one. A pull request that adds or changes `results/`, `docs/stages/`, a
snapshot or a decision record must carry one fenced `research-log` block in that format, with a tag from {H7, H10} and
the pull request's own number. The check reads the body from the `pull_request` event payload, so it needs no API call.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_log_entry", ROOT / "scripts" / "check_log_entry.py")
check_log_entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_log_entry)

REPO = "eleonorabjornberg/repo-market-liquidity"
NUMBER = 40

ENTRY_LINES = [
    "### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#40",
    "- Directive: eleonorabjornberg/repo-market-liquidity#22",
    "- Step: H7m development 1 (estimand and estimator)",
    "- Tier: development",
    "- Pins: model 490f23d, panel digest abc123, snapshot none",
    "- Tried: one estimator; variant count 1",
    "- Result: built, nothing scored",
    "- Against the goalpost or kill: not applicable",
    "- Next: step 2",
]


def body(lines=ENTRY_LINES, info="research-log", before="Summary.\n\n", after="\n\nMore text.\n"):
    return before + "```" + info + "\n" + "\n".join(lines) + "\n```" + after


def replaced(index, line):
    lines = list(ENTRY_LINES)
    lines[index] = line
    return lines


def errors(text, number=NUMBER, repo=REPO):
    return check_log_entry.check_body(text, number=number, repo=repo)


class TriggerTests(unittest.TestCase):
    def test_paths_that_need_an_entry(self):
        for path in ("results/stage6/table.csv", "docs/stages/stage-7.md", "docs/decisions/measurement-protocol.md",
                     "tests/fixtures/snapshots/fomc_notes/onrrp_rate.csv", "snapshots/abc123/estimate.parquet"):
            with self.subTest(path=path):
                self.assertTrue(check_log_entry.needs_entry([path]))

    def test_paths_that_do_not(self):
        self.assertFalse(check_log_entry.needs_entry(
            ["src/repo_liquidity/panel.py", "README.md", "docs/research/plan.md", "docs/HANDOFF.md", "docs/stagesx.md"]))

    def test_a_pull_request_that_needs_no_entry_passes_without_one(self):
        self.assertEqual(check_log_entry.run({"number": NUMBER, "body": None}, REPO, ["src/x.py"]), [])

    def test_a_pull_request_that_needs_an_entry_fails_without_one(self):
        self.assertNotEqual(check_log_entry.run({"number": NUMBER, "body": None}, REPO, ["results/a.csv"]), [])


class EntryTests(unittest.TestCase):
    def test_a_well_formed_entry_passes(self):
        self.assertEqual(errors(body()), [])

    def test_the_heading_step_is_free_text(self):
        self.assertEqual(errors(body(replaced(0, "### 2026-10-12 [H10] groundwork G3 · " + REPO + "#40"))), [])

    def test_missing_block(self):
        self.assertTrue(any("no fenced research-log block" in e for e in errors("Just a summary.")))

    def test_a_block_with_another_info_string_does_not_count(self):
        self.assertTrue(any("no fenced research-log block" in e for e in errors(body(info="text"))))

    def test_more_than_one_block(self):
        self.assertTrue(any("2 fenced research-log blocks" in e for e in errors(body() + body())))

    def test_unterminated_block(self):
        text = "```research-log\n" + "\n".join(ENTRY_LINES) + "\n"
        self.assertTrue(any("not closed" in e for e in errors(text)))

    def test_malformed_heading(self):
        self.assertTrue(any("heading" in e for e in errors(body(replaced(0, "## 2026-10-14 H7 step 1")))))

    def test_impossible_date(self):
        self.assertTrue(any("date" in e for e in errors(body(replaced(0, "### 2026-02-30 [H7] step 1 · " + REPO + "#40")))))

    def test_tag_not_in_the_plan(self):
        found = errors(body(replaced(0, "### 2026-10-14 [H5] step 1 · " + REPO + "#40")))
        self.assertTrue(any("tag" in e and "H5" in e for e in found))

    def test_another_pull_request_number(self):
        found = errors(body(replaced(0, "### 2026-10-14 [H7] step 1 · " + REPO + "#39")))
        self.assertTrue(any("#39" in e and "#40" in e for e in found))

    def test_another_repository(self):
        found = errors(body(replaced(0, "### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-model#40")))
        self.assertTrue(any("repo-market-model#40" in e for e in found))

    def test_missing_field(self):
        lines = [line for line in ENTRY_LINES if not line.startswith("- Pins:")]
        self.assertTrue(any("Pins" in e for e in errors(body(lines))))

    def test_fields_out_of_order(self):
        lines = list(ENTRY_LINES)
        lines[1], lines[2] = lines[2], lines[1]
        self.assertTrue(any("Directive" in e for e in errors(body(lines))))

    def test_empty_field(self):
        self.assertTrue(any("Result" in e and "empty" in e for e in errors(body(replaced(6, "- Result:")))))

    def test_extra_line(self):
        self.assertTrue(any("unexpected" in e for e in errors(body(ENTRY_LINES + ["- Verdict: supported"]))))

    def test_tier_not_development_or_confirmation(self):
        self.assertTrue(any("Tier" in e for e in errors(body(replaced(3, "- Tier: lockbox")))))


class EventTests(unittest.TestCase):
    def test_main_reads_the_event_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            changed = Path(tmp) / "changed.txt"
            changed.write_text("docs/decisions/measurement-protocol.md\n", encoding="utf-8")
            event.write_text(json.dumps({"pull_request": {"number": NUMBER, "body": body()}}), encoding="utf-8")
            argv = ["--event", str(event), "--repo", REPO, "--changed-files", str(changed)]
            self.assertEqual(check_log_entry.main(argv), 0)
            event.write_text(json.dumps({"pull_request": {"number": NUMBER + 1, "body": body()}}), encoding="utf-8")
            self.assertEqual(check_log_entry.main(argv), 1)

    def test_an_event_without_a_pull_request_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"push": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                check_log_entry.main(["--event", str(event), "--repo", REPO, "--changed-files", str(event)])


if __name__ == "__main__":
    unittest.main()
