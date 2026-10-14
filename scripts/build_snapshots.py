#!/usr/bin/env python3
"""Build the digest-named snapshots of the FOMC series (#25; `docs/decisions/snapshots.md`, a draft).

    PYTHONPATH=src python3 scripts/build_snapshots.py            # write snapshots/<series>/, from a clean tree
    PYTHONPATH=src python3 scripts/build_snapshots.py --check    # rebuild into a temporary directory and compare

A build records the commit it ran at, so it refuses a tree with uncommitted changes outside `snapshots/`. Commit the
tables first; the snapshot and its manifest are committed in the next commit. Standard library only.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from repo_liquidity import snapshots


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=snapshots.ROOT, check=True, capture_output=True, text=True).stdout


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="rebuild and compare with the tracked manifests")
    parser.add_argument("--series", action="append", choices=sorted(snapshots.SERIES),
                        help="build only this series (repeatable); a build of a series rewrites its manifest at this commit")
    args = parser.parse_args(argv)
    chosen = args.series or list(snapshots.SERIES)
    if args.check:
        bad = []
        with tempfile.TemporaryDirectory() as tmp:
            for series in chosen:
                tracked = snapshots.load_manifest(series)
                rebuilt = snapshots.build(series, Path(tmp), repo_commit=tracked["repo_commit"])
                if rebuilt != tracked:
                    bad.append(series)
        print("snapshots rebuild to their tracked manifests" if not bad else f"stale: {bad}")
        return 1 if bad else 0
    dirty = [line for line in _git("status", "--porcelain").splitlines() if not line[3:].startswith("snapshots/")]
    if dirty:
        print("refusing to build from a tree with uncommitted changes:\n" + "\n".join(dirty), file=sys.stderr)
        return 1
    commit = _git("rev-parse", "HEAD").strip()
    for series in chosen:
        manifest = snapshots.build(series, repo_commit=commit)
        last = manifest.get("last_announced") or f"last week {manifest['last_week']}"
        print(f"{series}: {manifest['sha256']} ({manifest['rows']} rows, {last})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
