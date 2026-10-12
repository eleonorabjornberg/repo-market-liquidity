"""Check a pull request's research-log entry (#20, second comment; `docs/research/plan.md`).

A pull request that adds or changes `results/`, `docs/stages/`, a snapshot or a decision record must carry one fenced
block headed `research-log`, in the shared format of repo-market-model#638:

    ### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#NN
    - Directive: ...
    - Step: ...
    - Tier: development | confirmation
    - Pins: ...
    - Tried: ...
    - Result: ...
    - Against the goalpost or kill: ...
    - Next: ...

with a tag from this repository's plan (H7, H10) and the pull request's own number. The body is read from the
`pull_request` event payload (`$GITHUB_EVENT_PATH`), so no API call is made. The changed paths are read from git, as
the difference between the merge commit and its first parent, or from `--changed-files`.

Usage (CI): python3 scripts/check_log_entry.py --event "$GITHUB_EVENT_PATH" --repo "$GITHUB_REPOSITORY"
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

#: The hypotheses of this repository's plan (`docs/research/plan.md`).
TAGS = ("H7", "H10")
TIERS = ("development", "confirmation")
FIELDS = ("Directive", "Step", "Tier", "Pins", "Tried", "Result", "Against the goalpost or kill", "Next")
INFO = "research-log"

HEADING = re.compile(r"^### (?P<date>\S+) \[(?P<tag>[^\]]+)\] (?P<step>\S.*?) · "
                     r"(?P<repo>[\w.-]+/[\w.-]+)#(?P<number>\d+)$")
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
        errors.append(f"the heading {lines[0]!r} is not '### YYYY-MM-DD [TAG] <step> · owner/repo#n'")
    else:
        try:
            dt.date.fromisoformat(heading["date"])
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", heading["date"]):
                raise ValueError
        except ValueError:
            errors.append(f"the heading's date {heading['date']!r} is not a date written YYYY-MM-DD")
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
        if not fields[index].startswith(prefix):
            errors.append(f"line {index + 2} should be the field '- {name}:', not {fields[index]!r}")
            continue
        value = fields[index][len(prefix):].strip()
        if not value:
            errors.append(f"the field '{name}' is empty")
        elif name == "Tier" and value not in TIERS:
            errors.append(f"the Tier {value!r} is not one of {', '.join(TIERS)}")
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


def changed_from_git():
    """The paths the merge commit changes against its first parent (the base branch)."""
    out = subprocess.run(["git", "diff", "--name-only", "HEAD^1", "HEAD"], check=True, capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, help="the event payload ($GITHUB_EVENT_PATH)")
    parser.add_argument("--repo", required=True, help="owner/repo ($GITHUB_REPOSITORY)")
    parser.add_argument("--changed-files", help="a file listing the changed paths, one per line (default: from git)")
    args = parser.parse_args(argv)
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
