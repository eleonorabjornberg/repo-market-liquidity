#!/usr/bin/env python3
"""Stage 5a: Phase 3's daily log (`docs/stages/stage-5a.md`).

    PYTHONPATH=src python3 scripts/stage5a_log.py run --date YYYY-MM-DD --out-dir ../live-log [--dry-run]

One run logs one decision day D: both arms' forecasts for the next decision day, made at 16:00 New York on D from what
was public then, with the frozen Stage 4 declaration. In order, and each refusal raises before anything is fetched:

1. D is after the development window, is a decision day (the parent's holiday table) and has no record yet; the rate
   tables cover every scheduled FOMC statement made by D's decision (the FOMC guard); the declaration's checksum is the
   one pinned in `docs/decisions/stage-4-freeze.md`. Outside `--dry-run`, it is past 16:00 New York on D.
2. Fetch, by the parent's own fetchers: SOFR, FRED macro, Treasury bill rates, Treasury auctions; and the H.8 releases
   after the tracked first-print extract, cut by the parent's own `extract_h8_first_prints.py`.
3. Build the columns the declaration reads (`live.build_rows`), extend the panel with placeholders through the target
   (the parent's `extend_panel`), add the two scheduled rates, and check no forecast reads a placeholder's unknown
   cell.
4. Forecast every arm (`live.forecast`) and write `live/D.json` once. `--dry-run` writes under `dry-run/` instead,
   and its record says so; a dry run is never confirmatory.
"""

import argparse
import json
import platform
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from repo_liquidity import PARENT_COMMIT, curve_feature, live, parent_root, scheduled

ROOT = Path(__file__).resolve().parents[1]
EASTERN = ZoneInfo("America/New_York")
RECORD_VERSION = 1


def _git(*argv):
    return subprocess.run(["git", *argv], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _freeze():
    import importlib.util

    spec = importlib.util.spec_from_file_location("stage4_freeze", ROOT / "scripts" / "stage4_freeze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_checksum() -> str:
    import re

    text = (ROOT / "docs" / "decisions" / "stage-4-freeze.md").read_text(encoding="utf-8")
    found = re.findall(r"^- \*\*Declaration checksum:\*\* `([^`]+)`", text, re.MULTILINE)
    if len(found) != 1:
        raise ValueError("the freeze record must pin exactly one declaration checksum")
    return found[0]


def refuse(day: date, out_dir: Path, *, dry_run: bool, module) -> datetime:
    """Step 1. Returns D's decision instant (naive New York wall clock).

    Raises:
        ValueError: on any refusal, naming it.
    """
    live.require_loggable(day)
    if not module.is_decision_day(day):
        raise SystemExit(0)
    if not dry_run and live.record_path(out_dir, day).exists():
        raise ValueError(f"{day} already has a record")
    decision = datetime.combine(day, live.DECISION_TIME)
    live.require_tables_cover(decision, live.table_coverage())
    checksum = _freeze().checksum()
    if checksum != pinned_checksum():
        raise ValueError(f"the declaration's checksum {checksum} is not the frozen {pinned_checksum()}")
    if not dry_run:
        now = datetime.now(EASTERN)
        if now.date() != day or now.time() < live.DECISION_TIME:
            raise ValueError(f"a run for {day} is made on {day} after 16:00 New York, not at {now}")
    return decision


def fetch(raw: Path, day: date, module) -> list:
    """Step 2. The parent's fetches into `raw`; the H.8 releases after the tracked extract, cut into `raw/h8_live`.

    Returns the raw roots the build reads: the fetched sources, the tracked H.8 extract, and the new one.
    """
    module.fetch(raw, day)
    tracked = parent_root() / "tests" / "fixtures" / "snapshots" / "h8_inputs"
    extract = (tracked / "frb_h8" / "h8_total_assets_first_print.csv").read_text(encoding="utf-8").splitlines()
    start = date.fromisoformat(extract[-1].split(",")[2]) + timedelta(days=1)
    pages = raw.parent / "h8_pages"
    subprocess.run([sys.executable, "-m", "repo_model.cli", "fetch", "h8", "--start", start.isoformat(),
                    "--end", day.isoformat(), "--output-root", str(pages)], check=True, capture_output=True)
    new = raw.parent / "h8_live" / "frb_h8"
    new.mkdir(parents=True)
    subprocess.run([sys.executable, str(parent_root() / "scripts" / "extract_h8_first_prints.py"),
                    "--raw-root", str(pages), "--output", str(new), "--start", start.isoformat(),
                    "--end", day.isoformat()], check=True, capture_output=True, cwd=parent_root())
    live.require_h8_seam(tracked / "frb_h8" / "h8_total_assets_first_print.csv",
                         new / "h8_total_assets_first_print.csv")
    return [raw, tracked, new.parent]


def run(args) -> int:
    if args.raw_root and not args.dry_run:
        raise ValueError("--raw-root reads saved snapshots instead of fetching; only a dry run may use it")
    module = live.parent_live()
    day = args.date
    out_dir = Path(args.out_dir)
    started = datetime.now(timezone.utc)
    with curve_feature.stage4_declaration():
        decision = refuse(day, out_dir, dry_run=args.dry_run, module=module)
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            roots = list(args.raw_root) if args.raw_root else fetch(raw, day, module)
            rows, pit_path, snapshots = live.build_rows(roots, datetime.now(timezone.utc), Path(tmp))
            real = [row for row in rows if row.date < day]
            extended, targets = module.extend_panel(real, day, 1, pit_path)
            extended = live.with_scheduled_rates(extended)
            live.require_forecast_reads(extended, len(real) - 1, module=module)
            result = live.forecast(extended, module=module)
    record = {
        "record_version": RECORD_VERSION,
        "decision_day": day.isoformat(),
        "decision_instant": decision.isoformat(),
        "target_date": targets[0].isoformat(),
        "code": {"sha": _git("rev-parse", "HEAD"), "parent_commit": PARENT_COMMIT,
                 "declaration_checksum": pinned_checksum()},
        "packages": live.package_versions(),
        "inputs": {"snapshots": snapshots, "rate_tables": live.rate_table_state(),
                   "panel_last_real_date": real[-1].date.isoformat()},
        "distributions": result["distributions"],
        "probabilities": result["probabilities"],
        "curve": result["curve"],
        "run": {"started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
                "workflow_run": args.workflow_run, "python": platform.python_version()},
    }
    if args.dry_run:
        record["dry_run"] = True
        written = live.write_record(out_dir / "dry-run", day, record)
    else:
        written = live.write_record(out_dir, day, record)
    print(json.dumps({"path": str(written.path), "sha256": written.sha256}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--date", type=date.fromisoformat, required=True)
    run_parser.add_argument("--out-dir", required=True)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--raw-root", type=Path, action="append",
                            help="read these snapshot roots instead of fetching (dry runs and tests only)")
    run_parser.add_argument("--workflow-run", default=None)
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
