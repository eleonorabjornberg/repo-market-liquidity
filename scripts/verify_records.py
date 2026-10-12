#!/usr/bin/env python3
"""Verify the development records at the commit and parent pin they were made from (L0, #21, option (a)).

    python3 scripts/verify_records.py --workdir records-check

1. Checks that this tree's record files are the recorded bytes (`repo_liquidity.records.RECORD_FILES`).
2. Checks out this repository at `RECORD_COMMIT` into `<workdir>/liquidity`, and checks that its record files are the
   same bytes, so what is verified there is what is tracked here.
3. Checks out the parent at `RECORD_PIN` into `<workdir>/parent`, installs both into `<workdir>/venv` as the record
   commit's own CI did (`.github/workflows/tests.yml` there), and runs that commit's full suite in one process: every
   record test, the panel rebuilds and the Stage 4 freeze, at the pin of the day.

Exits non-zero on the first failure. Needs git and network access to GitHub; CI runs it as the `records` job.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_liquidity import records  # noqa: E402

LIQUIDITY_URL = "https://github.com/eleonorabjornberg/repo-market-liquidity"
PARENT_URL = "https://github.com/eleonorabjornberg/repo-market-model"
#: The packages the record commit's CI installed, at the same pins.
PACKAGES = ("statsmodels==0.14.6", "numpy==2.4.6", "scipy==1.17.1", "pandas==3.0.6", "patsy==1.0.3",
            "python-dateutil==2.9.0.post0", "six==1.17.0", "packaging==26.3", "scikit-learn==1.9.1",
            "joblib==1.6.0", "threadpoolctl==3.7.0", "narwhals==2.26.0")


def run(*args, **kwargs):
    print("+", " ".join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def checkout(url: str, commit: str, directory: Path) -> None:
    """A clean checkout of `commit` alone (as CI checks out its own commit)."""
    run("git", "init", "-q", directory)
    run("git", "-C", directory, "fetch", "-q", "--depth", "1", url, commit)
    run("git", "-C", directory, "checkout", "-q", "FETCH_HEAD")
    head = subprocess.run(["git", "-C", str(directory), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    if head != commit:
        raise SystemExit(f"{directory} is at {head}, not {commit}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workdir", type=Path, required=True, help="an empty or missing directory to work in")
    parser.add_argument("--liquidity-url", default=LIQUIDITY_URL)
    parser.add_argument("--parent-url", default=PARENT_URL)
    args = parser.parse_args()

    changed = records.changed(ROOT)
    if changed:
        print(f"record files changed in this tree: {changed}", file=sys.stderr)
        return 1
    workdir = args.workdir.resolve()
    if workdir.exists() and any(workdir.iterdir()):
        print(f"{workdir} is not empty", file=sys.stderr)
        return 1
    liquidity, parent, venv = workdir / "liquidity", workdir / "parent", workdir / "venv"
    checkout(args.liquidity_url, records.RECORD_COMMIT, liquidity)
    changed = records.changed(liquidity)
    if changed:
        print(f"the record commit's files differ from the recorded bytes: {changed}", file=sys.stderr)
        return 1
    pinned = (liquidity / "src" / "repo_liquidity" / "__init__.py").read_text(encoding="utf-8")
    if f'PARENT_COMMIT = "{records.RECORD_PIN}"' not in pinned:
        print(f"the record commit is not pinned to {records.RECORD_PIN}", file=sys.stderr)
        return 1
    checkout(args.parent_url, records.RECORD_PIN, parent)
    run(sys.executable, "-m", "venv", venv)
    pip = venv / "bin" / "pip"
    run(pip, "install", "-q", "-e", parent)
    run(pip, "install", "-q", "--no-deps", "-e", liquidity)
    run(pip, "install", "-q", *PACKAGES)
    print(f"running the suite of {records.RECORD_COMMIT} at parent {records.RECORD_PIN}", flush=True)
    result = subprocess.run([str(venv / "bin" / "python"), "-B", "-m", "unittest", "discover", "-s", "tests"],
                            cwd=liquidity, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
