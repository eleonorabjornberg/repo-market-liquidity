"""The research-log check on the push to main (`scripts/check_log_entry.py`, directive #100, finding #96).

A pull request can merge without its research-log entry ever being checked at the format in force on main (PR #76
did: its check last ran before PR #84 changed the rules, and the merge commit's job was skipped). So the check also
runs on `push` to main: for every pull request merged in that push it reads the pull request's body over REST and
applies the same rule as on the pull request, and a missing or invalid entry turns main red. A pull request whose entry
was wrong when it merged is corrected without editing it, by a block in `docs/research/log-corrections.md`, which the
check reads instead of the body.

The REST calls are replaced by a fake `fetch(path)` here; nothing in these tests uses the network.

Recorded mutation (the guard: a merged pull request that needs an entry is refused without a valid one): in
`check_merged`, replacing the last line `return check_body(...)` by `return []` makes `test_a_merged_pull_request_with_a_bad_entry_is_refused`
fail with `AssertionError: [] is not true` (seven tests fail). Applied and killed when the tests were written.
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
ISSUE = "https://github.com/eleonorabjornberg/repo-market-liquidity/issues/96"


def entry(number, against="Against kill"):
    return [
        f"### 2026-10-14 [H7] groundwork G6 · {REPO}#{number}",
        "- Directive: eleonorabjornberg/repo-market-liquidity#74",
        "- Step: a step",
        "- Tier: development",
        "- Pins: model 53e61af",
        "- Tried: something",
        "- Result: something",
        f"- {against}: not applicable",
        "- Next: step 2",
    ]


def body(number, **kwargs):
    return "Summary.\n\n```research-log\n" + "\n".join(entry(number, **kwargs)) + "\n```\n"


def corrections_text(number=76, lines=None):
    lines = entry(number) if lines is None else lines
    return (f"# Corrections\n\n## Corrects the entry of #{number} ({ISSUE})\n\nWhy.\n\n```research-log\n"
            + "\n".join(lines) + "\n```\n")


class FakeGitHub:
    """A fake `fetch(path)` over a few pull requests: {number: (merge sha, body, [changed paths])}."""

    def __init__(self, pulls):
        self.pulls, self.calls = pulls, []

    def __call__(self, path):
        self.calls.append(path)
        for number, (sha, text, files) in self.pulls.items():
            if path.startswith(f"repos/{REPO}/commits/{sha}/pulls"):
                return [{"number": number, "merge_commit_sha": sha, "merged_at": "2026-10-15T00:00:00Z", "body": text}]
            if path.startswith(f"repos/{REPO}/pulls/{number}/files"):
                return [{"filename": name} for name in files] if "page=1" in path else []
            if path == f"repos/{REPO}/pulls/{number}":
                return {"number": number, "merge_commit_sha": sha, "merged_at": "2026-10-15T00:00:00Z", "body": text}
        if path.startswith(f"repos/{REPO}/compare/"):
            return {"commits": [{"sha": sha} for sha, _, _ in self.pulls.values()]}
        return []


class CorrectionTests(unittest.TestCase):
    def test_a_correction_is_found_by_the_number_it_corrects(self):
        found = check_log_entry.parse_corrections(corrections_text(76))
        self.assertEqual(sorted(found), [76])
        self.assertEqual(found[76][0], entry(76)[0])

    def test_no_corrections(self):
        self.assertEqual(check_log_entry.parse_corrections("# Corrections\n\nNone yet.\n"), {})

    def test_a_correction_without_a_link_to_its_finding_is_refused(self):
        text = corrections_text(76).replace(f" ({ISSUE})", "")
        with self.assertRaises(ValueError):
            check_log_entry.parse_corrections(text)

    def test_a_correction_with_two_blocks_or_none_is_refused(self):
        text = corrections_text(76)
        with self.assertRaises(ValueError):
            check_log_entry.parse_corrections(text + "\n```research-log\n" + "\n".join(entry(76)) + "\n```\n")
        with self.assertRaises(ValueError):
            check_log_entry.parse_corrections(f"## Corrects the entry of #76 ({ISSUE})\n\nNo block.\n")

    def test_two_corrections_of_one_pull_request_are_refused(self):
        with self.assertRaises(ValueError):
            check_log_entry.parse_corrections(corrections_text(76) + corrections_text(76))

    def test_a_correction_must_itself_cite_the_pull_request_it_corrects(self):
        corrections = check_log_entry.parse_corrections(corrections_text(76, entry(77)))
        found = check_log_entry.check_merged({"number": 76, "body": body(76, against="Against the kill")}, REPO,
                                             ["results/a.csv"], corrections)
        self.assertTrue(any("#77" in e for e in found), found)


class MergedPullRequestTests(unittest.TestCase):
    def test_a_merged_pull_request_with_a_bad_entry_is_refused(self):
        pull = {"number": 76, "body": body(76, against="Against the goalpost or kill")}
        self.assertTrue(check_log_entry.check_merged(pull, REPO, ["results/a.csv"], {}))

    def test_a_merged_pull_request_with_no_entry_is_refused(self):
        self.assertTrue(check_log_entry.check_merged({"number": 5, "body": "Nothing"}, REPO, ["docs/stages/x.md"], {}))

    def test_a_merged_pull_request_that_needs_none_passes(self):
        self.assertEqual(check_log_entry.check_merged({"number": 5, "body": None}, REPO, ["src/x.py"], {}), [])

    def test_a_good_entry_passes(self):
        self.assertEqual(check_log_entry.check_merged({"number": 76, "body": body(76)}, REPO, ["results/a.csv"], {}), [])

    def test_a_correction_stands_in_for_a_bad_body(self):
        pull = {"number": 76, "body": body(76, against="Against the goalpost or kill")}
        corrections = check_log_entry.parse_corrections(corrections_text(76))
        self.assertEqual(check_log_entry.check_merged(pull, REPO, ["results/a.csv"], corrections), [])

    def test_a_correction_does_not_excuse_another_pull_request(self):
        corrections = check_log_entry.parse_corrections(corrections_text(76))
        pull = {"number": 90, "body": body(90, against="Against the goalpost or kill")}
        self.assertTrue(check_log_entry.check_merged(pull, REPO, ["results/a.csv"], corrections))

    def test_a_bad_correction_is_refused_too(self):
        corrections = check_log_entry.parse_corrections(corrections_text(76, entry(76, against="Against the kill")))
        self.assertTrue(check_log_entry.check_merged({"number": 76, "body": body(76)}, REPO, ["results/a.csv"],
                                                     corrections))


class PushTests(unittest.TestCase):
    def test_the_pull_requests_merged_in_a_push_are_found_through_the_commits_of_the_push(self):
        fetch = FakeGitHub({76: ("a" * 40, body(76), ["results/a.csv"]), 90: ("b" * 40, body(90), ["README.md"])})
        event = {"before": "0" * 39 + "1", "after": "b" * 40}
        self.assertEqual([p["number"] for p in check_log_entry.merged_pull_requests(event, REPO, fetch)], [76, 90])

    def test_a_pull_request_that_did_not_merge_this_commit_is_not_counted(self):
        def fetch(path):
            if "/pulls" in path:
                return [{"number": 3, "merge_commit_sha": "c" * 40, "merged_at": "2026-10-15T00:00:00Z", "body": ""}]
            return {"commits": [{"sha": "a" * 40}]}
        event = {"before": "0" * 39 + "1", "after": "a" * 40}
        self.assertEqual(check_log_entry.merged_pull_requests(event, REPO, fetch), [])

    def test_a_first_push_reads_the_head_commit_only(self):
        fetch = FakeGitHub({76: ("a" * 40, body(76), [])})
        event = {"before": "0" * 40, "after": "a" * 40}
        self.assertEqual([p["number"] for p in check_log_entry.merged_pull_requests(event, REPO, fetch)], [76])
        self.assertFalse(any("/compare/" in call for call in fetch.calls))

    def test_the_push_check_turns_main_red_on_a_bad_entry(self):
        fetch = FakeGitHub({76: ("a" * 40, body(76, against="Against the goalpost or kill"), ["results/a.csv"])})
        event = {"before": "0" * 40, "after": "a" * 40}
        self.assertTrue(check_log_entry.run_push(event, REPO, fetch, {}))

    def test_the_push_check_passes_once_the_correction_exists(self):
        fetch = FakeGitHub({76: ("a" * 40, body(76, against="Against the goalpost or kill"), ["results/a.csv"])})
        event = {"before": "0" * 40, "after": "a" * 40}
        self.assertTrue(check_log_entry.run_push(event, REPO, fetch, {}))
        corrections = check_log_entry.parse_corrections(corrections_text(76))
        self.assertEqual(check_log_entry.run_push(event, REPO, fetch, corrections), [])

    def test_named_pull_requests_are_checked_whatever_the_push(self):
        fetch = FakeGitHub({76: ("a" * 40, body(76, against="Against the goalpost or kill"), ["results/a.csv"])})
        self.assertTrue(check_log_entry.run_numbers([76], REPO, fetch, {}))

    def test_a_pull_request_that_is_not_merged_is_refused_by_number(self):
        def fetch(path):
            return {"number": 9, "merge_commit_sha": None, "merged_at": None, "body": ""}
        with self.assertRaises(ValueError):
            check_log_entry.run_numbers([9], REPO, fetch, {})

    def test_main_reads_the_push_event_and_the_corrections_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            event, corr = Path(tmp) / "event.json", Path(tmp) / "corr.md"
            event.write_text(json.dumps({"before": "0" * 40, "after": "a" * 40}), encoding="utf-8")
            corr.write_text("# Corrections\n", encoding="utf-8")
            fetch = FakeGitHub({76: ("a" * 40, body(76, against="Against the goalpost or kill"), ["results/a.csv"])})
            argv = ["--push-event", str(event), "--repo", REPO, "--corrections", str(corr)]
            self.assertEqual(check_log_entry.main(argv, fetch=fetch), 1)
            corr.write_text(corrections_text(76), encoding="utf-8")
            self.assertEqual(check_log_entry.main(argv, fetch=fetch), 0)


class TrackedCorrectionsTests(unittest.TestCase):
    """The corrections file in the tree: #76's entry, corrected, passes the model repo's format (among the others)."""

    def test_the_tracked_correction_of_76_passes(self):
        text = (ROOT / "docs" / "research" / "log-corrections.md").read_text(encoding="utf-8")
        corrections = check_log_entry.parse_corrections(text)
        self.assertIn(76, corrections)
        self.assertEqual(check_log_entry.check_entry(corrections[76], 76, REPO), [])
        self.assertIn("/issues/96", text)

    def test_it_changes_only_the_field_name_of_76s_merged_entry(self):
        text = (ROOT / "docs" / "research" / "log-corrections.md").read_text(encoding="utf-8")
        merged = [l.replace("- Against kill:", "- Against the goalpost or kill:") for l in
                  check_log_entry.parse_corrections(text)[76]]
        self.assertEqual(merged[7], "- Against the goalpost or kill: not applicable (no candidate scored); "
                         "docs/decisions/measurement-protocol.md §5 and §9 unchanged")



class TrackedCorrectionFormatTests(unittest.TestCase):
    """The tracked `docs/research/log-corrections.md` (directive #176, finding #175): every corrected entry passes this
    repository's format check under its own pull request number, the groundwork item of #134 is named, and the plain
    wording of #114 avoids the word the model's lay-reader page test forbids. Written before the corrections; it failed
    with `KeyError: 134` first."""

    @classmethod
    def setUpClass(cls):
        cls.corrections = check_log_entry.parse_corrections(check_log_entry.CORRECTIONS.read_text(encoding="utf-8"))

    def test_each_corrected_entry_passes_under_its_own_number(self):
        for number, lines in self.corrections.items():
            self.assertEqual(check_log_entry.check_entry(lines, number, REPO), [], number)

    def test_134_names_the_groundwork_item_and_its_own_pull_request(self):
        self.assertEqual(self.corrections[134][0],
                         "### 2026-10-19 [H7] groundwork G8 · eleonorabjornberg/repo-market-liquidity#134")

    def test_114_avoids_the_words_the_models_page_test_forbids(self):
        text = "\n".join(self.corrections[114]).lower()
        for gone in ("lockbox", "held out", "blind tier", "post hoc", "decides nothing"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, text)

    def test_no_corrected_block_carries_a_phrase_the_models_page_test_forbids(self):
        """Directive #176, the handover on #180: #114, #174, #61 and #134 are the corrected blocks the model copies."""
        for number in (114, 174, 61, 134):
            text = "\n".join(self.corrections[number]).lower().replace("-", " ")
            for gone in ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record"):
                with self.subTest(number=number, gone=gone):
                    self.assertNotIn(gone, text)

    def test_174_and_61_change_only_the_offending_clauses(self):
        """Putting the merged clauses back gives the merged body's lines (174: Result; 61: Step and the field name)."""
        r174 = self.corrections[174]
        self.assertEqual(r174[6].replace("reported only; it settles no question", "reported, decides nothing"),
                         "- Result: reported, decides nothing")
        r61 = self.corrections[61]
        step = r61[2].replace("one read of the locked days", "one lockbox read") \
                     .replace("the row for the locked final period", "the blind-tier row")
        self.assertEqual(step, "- Step: H10 step 1 and L1 inputs: one lockbox read from the parent; the attribution "
                         "entry checks the window is public; the FOMC snapshots re-cut without the blind-tier row")
        self.assertEqual(r61[7].replace("Against kill", "Against the goalpost or kill"),
                         "- Against the goalpost or kill: not applicable; nothing scored")


class LabelCorrectionTests(unittest.TestCase):
    """Directive #176, the ruling on #180 (item 1 to 3): eleven merged entries still carry the old field label
    `Against the goalpost or kill`, and #61's corrected block must lose it too. Each correction changes the label and
    nothing else, except the headings of #38 and #39 (`[H7] L6 red-main fix`, `[H7] L5 agency securities input`), which
    take `groundwork G1`. The fixtures `tests/fixtures/research_log/merged_N.txt` are the merged blocks, unedited. Written
    before the corrections; it failed with `KeyError: 32` first."""

    NUMBERS = (32, 33, 34, 35, 38, 39, 42, 48, 51, 60, 68)
    HEADINGS = {38: "### 2026-10-13 [H7] groundwork G1 · eleonorabjornberg/repo-market-liquidity#38",
                39: "### 2026-10-13 [H7] groundwork G1 · eleonorabjornberg/repo-market-liquidity#39"}

    @classmethod
    def setUpClass(cls):
        cls.corrections = check_log_entry.parse_corrections(check_log_entry.CORRECTIONS.read_text(encoding="utf-8"))
        cls.fixtures = ROOT / "tests" / "fixtures" / "research_log"

    def merged(self, number):
        return (self.fixtures / f"merged_{number}.txt").read_text(encoding="utf-8").splitlines()

    def test_each_one_passes_under_its_own_number_and_has_the_new_label(self):
        for number in self.NUMBERS + (61,):
            with self.subTest(pr=number):
                lines = self.corrections[number]
                self.assertEqual(check_log_entry.check_entry(lines, number, REPO), [])
                self.assertFalse(any("goalpost or kill" in line for line in lines))

    def test_only_the_label_differs_from_the_merged_block(self):
        for number in self.NUMBERS:
            expected = [line.replace("- Against the goalpost or kill:", "- Against kill:") for line in self.merged(number)]
            if number in self.HEADINGS:
                expected[0] = self.HEADINGS[number]
            with self.subTest(pr=number):
                self.assertEqual(self.corrections[number], expected)

    def test_no_forbidden_phrase(self):
        for number in self.NUMBERS + (61,):
            text = "\n".join(self.corrections[number]).lower().replace("-", " ")
            for gone in ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record"):
                with self.subTest(pr=number, gone=gone):
                    self.assertNotIn(gone, text)


class CountCorrectionTests(unittest.TestCase):
    """Directive #192 (model PR #1250): #185's merged entry counted tests in its Result line, which the model's
    `COUNT_CLAIM` refuses in a published document. The correction changes that line and no other; the block carries no
    numeral that counts tests. Written before the correction; it failed with `KeyError: 185` first."""

    #: The Result line and the other eight lines of #185's merged block, as merged (PR #185's body).
    MERGED = [
        "### 2026-10-26 [H7] groundwork G8 · eleonorabjornberg/repo-market-liquidity#185",
        "- Directive: #184",
        "- Step: groundwork, shared research log: the two #76 correction tests collected again, and a guard against a "
        "repeated test class name",
        "- Tier: development",
        "- Pins: parent 08ff67e27bc3d7e357491cf8e1da59793702b3fb; panel digest unchanged "
        "(4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999)",
        "- Tried: renamed the second TrackedCorrectionsTests, moved every class above the main guard, checked #76 among "
        "the corrections, added tests/test_class_names.py",
        "- Result: test_log_push collects 31 tests (29 before) and the full suite passes; nothing scored, no figure or "
        "record changed",
        "- Against kill: not applicable; nothing scored",
        "- Next: none",
    ]
    RESULT = ("- Result: test_log_push collects the two #76 correction tests again and the full suite passes; nothing "
              "scored, no figure or record changed")

    @classmethod
    def setUpClass(cls):
        text = check_log_entry.CORRECTIONS.read_text(encoding="utf-8")
        cls.text = text
        cls.corrections = check_log_entry.parse_corrections(text)

    def test_the_merged_block_is_what_the_check_refuses(self):
        self.assertTrue(any("counts tests" in e for e in check_log_entry.check_entry(self.MERGED, 185, REPO)))

    def test_185_is_corrected_and_passes_under_its_own_number(self):
        self.assertEqual(check_log_entry.check_entry(self.corrections[185], 185, REPO), [])

    def test_only_the_result_line_differs(self):
        expected = list(self.MERGED)
        expected[6] = self.RESULT
        self.assertEqual(self.corrections[185], expected)

    def test_the_section_cites_this_issue_and_says_what_changed(self):
        heading = "## Corrects the entry of #185 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/192)"
        self.assertIn(heading, self.text.splitlines())
        note = self.text.split(heading)[1].split("```research-log")[0]
        self.assertIn("test count is removed", note)

    def test_no_numeral_counts_tests_in_it(self):
        # The model's COUNT_CLAIM, via the script's copy (CountClaimTests holds the model's source and compares).
        for line in self.corrections[185]:
            self.assertIsNone(check_log_entry.COUNT_CLAIM.search(line), line)

    def test_no_forbidden_phrase(self):
        text = "\n".join(self.corrections[185]).lower().replace("-", " ")
        for gone in ("decides nothing", "post hoc", "held out", "lockbox", "blind tier", "live record"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, text)

    def test_the_push_check_reads_the_correction_in_place_of_185s_body(self):
        merged_body = "Summary.\n\n```research-log\n" + "\n".join(self.MERGED) + "\n```\n"
        files = ["tests/test_log_push.py", "docs/decisions/x.md"]
        pulls = {185: ("c" * 40, merged_body, files)}
        event = {"before": "0" * 40, "after": "c" * 40}
        self.assertEqual(len(check_log_entry.run_push(event, REPO, FakeGitHub(pulls), {})), 1)
        self.assertEqual(check_log_entry.run_push(event, REPO, FakeGitHub(pulls), self.corrections), [])


if __name__ == "__main__":
    unittest.main()
