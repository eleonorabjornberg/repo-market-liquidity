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
    """The corrections file in the tree: #76's entry, corrected, passes the model repo's format."""

    def test_the_tracked_correction_of_76_passes(self):
        text = (ROOT / "docs" / "research" / "log-corrections.md").read_text(encoding="utf-8")
        corrections = check_log_entry.parse_corrections(text)
        self.assertEqual(sorted(corrections), [76])
        self.assertEqual(check_log_entry.check_entry(corrections[76], 76, REPO), [])
        self.assertIn("/issues/96", text)

    def test_it_changes_only_the_field_name_of_76s_merged_entry(self):
        text = (ROOT / "docs" / "research" / "log-corrections.md").read_text(encoding="utf-8")
        merged = [l.replace("- Against kill:", "- Against the goalpost or kill:") for l in
                  check_log_entry.parse_corrections(text)[76]]
        self.assertEqual(merged[7], "- Against the goalpost or kill: not applicable (no candidate scored); "
                         "docs/decisions/measurement-protocol.md §5 and §9 unchanged")


if __name__ == "__main__":
    unittest.main()
