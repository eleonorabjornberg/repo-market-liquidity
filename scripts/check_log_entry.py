"""Check a pull request's research-log entry (#20, second comment; `docs/research/plan.md`).

A pull request that adds or changes `results/`, `docs/stages/`, a snapshot or a decision record must carry one fenced
block headed `research-log`, in the format of repo-market-model's `scripts/check_research_log.py` (finding #80,
directive #83), which validates the block once it is copied into that repository's `docs/research/log.md`:

    ### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#NN
    - Directive: ...
    - Step: ...
    - Tier: development | confirmation
    - Pins: ...
    - Tried: ...
    - Result: ...
    - Against kill: ...
    - Next: ...

The heading reads `step N` (N from 1 to 6) or, for groundwork, `groundwork G<n>` (`### 2026-10-12 [H10] groundwork
G3 · owner/repo#NN`); the Directive line names an issue (`#N`); every field is `- Name: value` with a space after the
colon. The rules are the model repo's, copied, not its code. This check is stricter in three ways, so that an entry
that passes here passes there verbatim: the fields come in this order with no extra line, the tag is one from this
repository's plan (H7, H10), and the heading cites this pull request's own number. The body is read from the
`pull_request` event payload (`$GITHUB_EVENT_PATH`), so no API call is made. The changed paths are read from git, as
the difference between the merge commit and its first parent, or from `--changed-files`.

On the push to main the same rule is applied to every pull request merged in the push (#100, finding #96): a pull request
can merge although its check last ran before the rules changed, and the merge commit's job was skipped. The merged
pull requests are found through the commits of the push, and each body and its changed paths are read over REST with the
workflow token. A missing or invalid entry makes the job, and so main, red. A merged entry that was wrong is corrected
without editing the pull request: `docs/research/log-corrections.md` holds a block under `## Corrects the entry of #N
(<link to the finding>)`, and the check reads it instead of the body.

Usage (CI): python3 scripts/check_log_entry.py --event "$GITHUB_EVENT_PATH" --repo "$GITHUB_REPOSITORY"
            python3 scripts/check_log_entry.py --push-event "$GITHUB_EVENT_PATH" --repo "$GITHUB_REPOSITORY" [--pulls 76,84]
"""

import argparse
import datetime as dt
import json
import re
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

#: The hypotheses of this repository's plan (`docs/research/plan.md`).
TAGS = ("H7", "H10")
TIERS = ("development", "confirmation")
FIELDS = ("Directive", "Step", "Tier", "Pins", "Tried", "Result", "Against kill", "Next")
STEPS = range(1, 7)
INFO = "research-log"

STEP_FORMAT = "### YYYY-MM-DD [H#] step N · owner/repo#n"
GROUNDWORK_FORMAT = "### YYYY-MM-DD [H#] groundwork G<n> · owner/repo#n"
HEADING = re.compile(r"^### (?P<date>\d{4}-\d{2}-\d{2}) \[(?P<tag>H\d+)\] "
                     r"(?:step (?P<step>\d+)|groundwork (?P<groundwork>G[1-9]\d*)) · "
                     r"(?P<repo>[\w.-]+/[\w.-]+)#(?P<number>\d+)$")
CORRECTIONS = Path(__file__).resolve().parents[1] / "docs" / "research" / "log-corrections.md"
CORRECTS = re.compile(r"^## Corrects the entry of #(?P<number>\d+) \((?P<link>https://github\.com/\S+/issues/\d+)\)\s*$")
FENCE = re.compile(r"^(`{3,}|~{3,})\s*(?P<info>[^`\s]*)\s*$")


def needs_entry(paths):
    """Whether any changed path is under `results/` or `docs/stages/`, a snapshot or a decision record."""
    for path in paths:
        parts = Path(path).parts
        if parts[:1] == ("results",) or parts[:2] in (("docs", "stages"), ("docs", "decisions")):
            return True
        if any(part.startswith("snapshot") for part in parts[:-1]):
            return True
    return False


def research_log_blocks(text):
    """The fenced `research-log` blocks of `text`, as lists of lines; None for one that is never closed."""
    blocks, lines, current, fence = [], (text or "").splitlines(), None, None
    for line in lines:
        match = FENCE.match(line.strip())
        if fence is None:
            if match:
                fence = match.group(1)
                current = [] if match.group("info") == INFO else None
        elif match and match.group("info") == "" and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
            if current is not None:
                blocks.append(current)
            fence, current = None, None
        elif current is not None:
            current.append(line.rstrip())
    if fence is not None and current is not None:
        blocks.append(None)
    return blocks


def check_entry(lines, number, repo):
    """The format errors of one entry."""
    errors = []
    lines = [line for line in lines if line.strip()]
    if not lines:
        return ["the research-log block is empty"]
    heading = HEADING.match(lines[0].strip())
    if not heading:
        errors.append(f"the heading {lines[0]!r} is not '{STEP_FORMAT}' or '{GROUNDWORK_FORMAT}'")
    else:
        try:
            dt.date.fromisoformat(heading["date"])
        except ValueError:
            errors.append(f"the heading's date {heading['date']!r} is not a date written YYYY-MM-DD")
        if heading["step"] is not None and int(heading["step"]) not in STEPS:
            errors.append(f"the heading's step {heading['step']} is not 1 to 6")
        if heading["tag"] not in TAGS:
            errors.append(f"the tag [{heading['tag']}] is not in the plan ({', '.join(TAGS)})")
        cited = f"{heading['repo']}#{heading['number']}"
        if cited != f"{repo}#{number}":
            errors.append(f"the heading cites {cited}, not this pull request, {repo}#{number}")
    fields = lines[1:]
    for index, name in enumerate(FIELDS):
        if index >= len(fields):
            errors.append(f"the field '- {name}:' is missing")
            continue
        prefix = f"- {name}:"
        if not fields[index].startswith(prefix) or fields[index][len(prefix):len(prefix) + 1] not in ("", " "):
            errors.append(f"line {index + 2} should be the field '- {name}: ' (a space after the colon), "
                          f"not {fields[index]!r}")
            continue
        value = fields[index][len(prefix):].strip()
        if not value:
            errors.append(f"the field '{name}' is empty")
        elif name == "Tier" and value not in TIERS:
            errors.append(f"the Tier {value!r} is not one of {', '.join(TIERS)}")
        elif name == "Directive" and not re.search(r"#\d+", value):
            errors.append("the Directive line names no issue (#N)")
    for extra in fields[len(FIELDS):]:
        errors.append(f"unexpected line after '- Next:': {extra!r}")
    return errors


def check_body(body, number, repo):
    """The errors of a pull request body: it must carry exactly one well-formed research-log block."""
    blocks = research_log_blocks(body)
    if not blocks:
        return [f"no fenced {INFO} block in the pull request body"]
    if len(blocks) > 1:
        return [f"{len(blocks)} fenced {INFO} blocks in the pull request body; exactly one is allowed"]
    if blocks[0] is None:
        return [f"the {INFO} block is not closed"]
    return check_entry(blocks[0], number, repo)


def run(pull_request, repo, changed):
    """The errors for a pull request (the event's `pull_request` object) with these changed paths."""
    if not needs_entry(changed):
        return []
    return check_body(pull_request.get("body") or "", pull_request["number"], repo)


def parse_corrections(text):
    """{pull request number: the lines of its corrected entry} from `log-corrections.md`.

    Each `## Corrects the entry of #N (<link to the finding>)` section carries exactly one `research-log` block, and a
    pull request is corrected once. A section that breaks this raises ValueError."""
    sections, current = {}, None
    for line in (text or "").splitlines():
        if line.startswith("## "):
            match = CORRECTS.match(line)
            if not match:
                raise ValueError(f"{line!r} is not '## Corrects the entry of #N (https://github.com/<repo>/issues/M)'")
            number = int(match["number"])
            if number in sections:
                raise ValueError(f"#{number} is corrected twice")
            current = sections[number] = []
        elif current is not None:
            current.append(line)
    corrections = {}
    for number, lines in sections.items():
        blocks = research_log_blocks("\n".join(lines))
        if len(blocks) != 1 or blocks[0] is None:
            raise ValueError(f"the correction of #{number} needs exactly one closed {INFO} block, not {len(blocks)}")
        corrections[number] = blocks[0]
    return corrections


def check_merged(pull_request, repo, changed, corrections):
    """The errors of a merged pull request: its body's entry, or the correction that stands in for it."""
    if not needs_entry(changed):
        return []
    number = pull_request["number"]
    if number in corrections:
        return [f"correction of #{number}: {e}" for e in check_entry(corrections[number], number, repo)]
    return check_body(pull_request.get("body") or "", number, repo)


def merged_pull_requests(event, repo, fetch):
    """The pull requests whose merge commit is one of the commits of this push, oldest first."""
    after, before = event["after"], event.get("before") or ""
    if before.strip("0"):
        shas = [c["sha"] for c in fetch(f"repos/{repo}/compare/{before}...{after}").get("commits", [])]
    else:
        shas = [after]
    found = []
    for sha in shas or [after]:
        for pull in fetch(f"repos/{repo}/commits/{sha}/pulls?per_page=100"):
            if pull.get("merge_commit_sha") == sha and pull.get("merged_at") and pull["number"] not in [
                    p["number"] for p in found]:
                found.append(pull)
    return found


def pull_request_files(repo, number, fetch):
    """The paths a pull request changed, read page by page."""
    paths, page = [], 1
    while True:
        files = fetch(f"repos/{repo}/pulls/{number}/files?per_page=100&page={page}")
        paths += [f["filename"] for f in files]
        if len(files) < 100:
            return paths
        page += 1


def check_pulls(pulls, repo, fetch, corrections):
    errors = []
    for pull in pulls:
        for error in check_merged(pull, repo, pull_request_files(repo, pull["number"], fetch), corrections):
            errors.append(f"#{pull['number']}: {error}")
    return errors


def run_push(event, repo, fetch, corrections):
    """The errors of every pull request merged in this push."""
    return check_pulls(merged_pull_requests(event, repo, fetch), repo, fetch, corrections)


def run_numbers(numbers, repo, fetch, corrections):
    """The errors of these merged pull requests, whatever push they came in."""
    pulls = []
    for number in numbers:
        pull = fetch(f"repos/{repo}/pulls/{number}")
        if not pull.get("merged_at"):
            raise ValueError(f"#{number} is not merged")
        pulls.append(pull)
    return check_pulls(pulls, repo, fetch, corrections)


def github(path):
    """GET https://api.github.com/<path> with the workflow token (GH_TOKEN)."""
    request = urllib.request.Request("https://api.github.com/" + path, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def changed_from_git():
    """The paths the merge commit changes against its first parent (the base branch)."""
    out = subprocess.run(["git", "diff", "--name-only", "HEAD^1", "HEAD"], check=True, capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line]


def main(argv=None, fetch=github):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", help="the pull_request event payload ($GITHUB_EVENT_PATH)")
    parser.add_argument("--push-event", help="the push event payload: check every pull request merged in the push")
    parser.add_argument("--pulls", help="comma-separated merged pull request numbers to check as well (with --push-event)")
    parser.add_argument("--corrections", default=str(CORRECTIONS), help="the corrections file")
    parser.add_argument("--repo", required=True, help="owner/repo ($GITHUB_REPOSITORY)")
    parser.add_argument("--changed-files", help="a file listing the changed paths, one per line (default: from git)")
    args = parser.parse_args(argv)
    if bool(args.event) == bool(args.push_event):
        parser.error("give exactly one of --event and --push-event")
    if args.push_event:
        path = Path(args.corrections)
        corrections = parse_corrections(path.read_text(encoding="utf-8")) if path.exists() else {}
        push = json.loads(Path(args.push_event).read_text(encoding="utf-8"))
        errors = run_push(push, args.repo, fetch, corrections) if push.get("after") else []
        numbers = [int(n) for n in (args.pulls or "").replace(" ", "").split(",") if n]
        errors += run_numbers(numbers, args.repo, fetch, corrections)
        for error in errors:
            print(f"research-log: {error}", file=sys.stderr)
        if not errors:
            print("research-log: every pull request merged in the push has a valid entry or needs none")
        return 1 if errors else 0
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    if not isinstance(event.get("pull_request"), dict):
        raise ValueError(f"{args.event} is not a pull_request event payload")
    if args.changed_files:
        changed = [line.strip() for line in Path(args.changed_files).read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    else:
        changed = changed_from_git()
    errors = run(event["pull_request"], args.repo, changed)
    for error in errors:
        print(f"research-log: {error}", file=sys.stderr)
    if not errors:
        print("research-log: " + ("entry well formed" if needs_entry(changed) else "no entry needed"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
