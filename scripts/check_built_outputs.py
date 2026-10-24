#!/usr/bin/env python3
"""Refuse a change that carries a file that is built on main (#170, as the model repo's #928).

`site/index.html` is generated from the tree's records and tracked files by the pages job on main
(`scripts/emit_site.py`), and the tests build their own copy. It is gitignored; a pull request changes the inputs (the
records, `site/template.html`, the scripts) and nothing else. This check fails when git tracks the built page, or, with
`--base`, when the change since the merge base adds or edits it (deleting a tracked copy is the cure, so it is allowed).

    python3 scripts/check_built_outputs.py
    python3 scripts/check_built_outputs.py --base REF [--head REF]

Standard library only.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The built paths; a trailing slash is a directory.
BUILT = ("site/index.html",)
INPUTS = ("the records, site/template.html and the scripts (`python3 scripts/emit_site.py` builds the page locally; "
          "it stays untracked)")


def built(path):
    """True when `path` is one of the built outputs."""
    return any(path == b or (b.endswith("/") and path.startswith(b)) for b in BUILT)


def errors(paths):
    """One error for every path that is a built output."""
    return ["%s is built on main (#170), not committed: change its inputs instead, %s" % (path, INPUTS)
            for path in sorted(set(paths)) if built(path)]


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)
    paths = _git("ls-files").split("\n")
    if args.base:
        merge_base = _git("merge-base", args.base, args.head).strip()
        paths += _git("diff", "--name-only", "--diff-filter=AMR", merge_base, args.head).split("\n")
    found = errors(p for p in paths if p)
    for error in found:
        print(error)
    if not found:
        print("built outputs: none tracked or changed")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
