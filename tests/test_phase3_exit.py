"""Phase 3's exit record (directive #198): `docs/stages/phase3-exit.md`.

A decision-level record of Eleonora's ruling of 28 October 2026 (option (a)): Phase 3's exit criterion is not met on
development and H7m is closed. Nothing is scored and no figure changes. Written before the page; the first run failed
because the page did not exist.

What is checked: the page is labelled as drafted for her; it quotes the criterion from `evaluation.md:88-112` as the file
has it; it cites `results/h7/verdict.json` by that file's current sha256; it carries `verdict.json`'s `not_claimed`
sentence; it states the outcome, and what continues; it holds none of the six forbidden phrases and no test count; the
plan points to it and keeps its earlier text; `evaluation.md` is not edited here.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "stages" / "phase3-exit.md"
VERDICT = ROOT / "results" / "h7" / "verdict.json"
EVALUATION = ROOT / "docs" / "decisions" / "evaluation.md"
PLAN = ROOT / "docs" / "research" / "plan.md"
FORBIDDEN = ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record")
LABEL = "drafted for Eleonora; in force once she merges it"


def _text():
    return PAGE.read_text(encoding="utf-8")


class Phase3ExitRecordTests(unittest.TestCase):
    def test_the_page_opens_with_its_label(self):
        self.assertIn(LABEL, "\n".join(_text().splitlines()[:6]))

    def test_the_page_cites_the_verdict_record_by_its_current_sha256(self):
        """Mutation recorded (29 October 2026): the last hex digit of the digest on the page changed from 0 to 1; this
        failed with AssertionError ('7c753f0f...51d0' not found in the page)."""
        digest = hashlib.sha256(VERDICT.read_bytes()).hexdigest()
        self.assertIn("results/h7/verdict.json", _text())
        self.assertIn(digest, _text())
        shas = re.findall(r"results/h7/verdict\.json`?\s*\(`?([0-9a-f]{64})", _text())
        self.assertEqual(shas, [digest])

    def test_the_criterion_is_quoted_from_evaluation_md_as_the_file_has_it(self):
        lines = EVALUATION.read_text(encoding="utf-8").splitlines()[87:112]
        quoted = [ln for ln in lines if ln.strip()]
        self.assertIn("evaluation.md:88-112", _text())
        page = _text()
        for needle in ("Phase 3's verdict is the parent's exit criterion",
                       "stable posterior intervals for aggregate deployable liquidity",
                       "with a clear account of their sensitivity to how reserves are distributed across banks"):
            self.assertIn(needle, page)
            self.assertTrue(any(needle in ln for ln in quoted), needle)

    def test_her_ruling_and_the_outcome_are_stated(self):
        page = _text()
        for needle in ("28 October 2026", "option (a)", "not met on development", "H7m is closed"):
            self.assertIn(needle, page)

    def test_what_continues_and_what_is_not_claimed(self):
        page = _text()
        not_claimed = json.loads(VERDICT.read_text(encoding="utf-8"))["not_claimed"]
        self.assertIn(not_claimed, page)
        for needle in ("H7f", "R+S", "plan.md:193-194", "H10", "22 October 2026"):
            self.assertIn(needle, page)

    def test_no_forbidden_phrase_and_no_test_count(self):
        text = _text().lower().replace("-", " ")
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, text)
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import check_log_entry
        self.assertIsNone(check_log_entry.COUNT_CLAIM.search(_text()))

    def test_the_plan_points_to_the_record_and_keeps_its_earlier_text(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertIn("**Where H7m stands (12 October 2026)**", plan)
        self.assertIn("- **Open:** M2–M12.", plan)
        self.assertIn("closed (stage verdict, PR #191; Phase 3 exit not met, this PR)", plan)
        tail = plan.split("## The parent's exit criterion", 1)[1].split("## Prior work", 1)[0]
        self.assertIn("docs/stages/phase3-exit.md", tail)

    def test_evaluation_md_is_not_edited_here(self):
        out = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", "docs/decisions/evaluation.md", "docs/runs", "results"],
                             cwd=ROOT, capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("no origin/main to compare with")
        self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
