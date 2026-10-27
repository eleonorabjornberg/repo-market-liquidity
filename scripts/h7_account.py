#!/usr/bin/env python3
"""H7m, development step 4: the account of the bank distribution for A and C (`docs/stages/h7-step4.md`, directive #144).

    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_account.py [--replications 2000] [--workers 1]
        [--output results/h7/distribution-account.json] [--page docs/research/h7-distribution-account.md]
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_account.py --withdraw [--output ...] [--page ...]
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_account.py --render [--check]

Reports aggregate deployable liquidity under the three declared alternatives of protocol section 8, per served day, for the
current C and its calendar-clean variants (`results/h7/calendar-clean.json`) and for A and its variants (`results/h7/kink.json`),
and writes `results/h7/distribution-account.json` and the Markdown printed from it. Neither is ever edited by hand. It decides
and scores nothing; the tier is "development".

* Rows, days and group weeks are the earlier runs': panel version 4 from the tracked fixtures (digest checked) to
  `demand_curve.LAST_DAY`, every scored day read through the parent's rule, which refuses a locked day.
* Both tracked records must carry this tree's parent pin, panel digest and window, or the run stops.
* C and CV3 serve days: their refits (two distinct fits each) are re-run with the run's settings so that the bootstrap draws exist,
  and compared with the tracked record's shares. CV1, CV2 and CV4 are not identified at any stride refit and serve no day: their
  accounts come from the record's own fitted flags, and the final refit (which serves no window day) needs no draws.
* A's kinks, intervals and fitted flags are read from the kink record, not re-fitted.
* The reading "A through the group machinery" is withdrawn (#182, ruling of 26 October 2026, #186): a run builds no such row, and
  `--withdraw` restates the superseded record without them, re-running nothing.
* The served-day counts of every estimator are compared with the tracked records' own.
"""

import argparse
import hashlib
import json
import sys
import time as clock
from datetime import date, time
from pathlib import Path

from repo_model import measurement_fields, scarcity
from repo_model.asof import InformationRule

from repo_liquidity import demand_curve
from repo_liquidity import h7_account as account
from repo_liquidity import h7_candidate_c as c
from repo_liquidity import h7_clean as h
from repo_liquidity import h7_kink as k

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "h7" / "distribution-account.json"
PAGE = ROOT / "docs" / "research" / "h7-distribution-account.md"
CLEAN = ROOT / "results" / "h7" / "calendar-clean.json"
KINK = ROOT / "results" / "h7" / "kink.json"
FIRST_CUTOFF = date(2020, 3, 13)
#: The estimators that are re-run for their draws; the others come from the record (they serve no day).
RERUN = ("C", "CV3")
D_NOT_REPORTED = "not reported (D dropped under #142)"
READING = ("A through step 2's group machinery, with A's single kink read as every group's buffer share (shares = (k, k, k)), is a "
           "marked reading (docs/stages/h7-step4.md section 2). It is reported beside A as defined, never in its place.")
#: The record this one replaces, as 4c37e36 published it (#144, PR #174), kept under `archive/`; the reading is withdrawn (#182, #186).
SUPERSEDED_SHA256 = "5b8ee596d16ccf6277f7174e109746c342bbfad270d10cfd9071fa9a8ebd20e8"
SUPERSEDED_REASON = ("the rows of \"A through the group machinery\" are withdrawn for the base mismatch (#182): they subtracted A's kink, "
                     "fitted on the all-banks ratio R, from group reserves over group assets. Every other row and field is "
                     "copied as it was, nothing is re-fitted (Eleonora's ruling on repo-market-liquidity#182, 26 October 2026, "
                     "directive #186). The superseded record is kept as it was in archive/h7-distribution-account-5b8ee596/.")
ARCHIVE = ROOT / "archive" / "h7-distribution-account-5b8ee596" / "distribution-account.json"
A_AS_DEFINED = ("A as defined is R - k. It has no per-group term, so no redistribution of the same reserves over the groups changes "
                "it: all three alternatives give the same figure.")
SOURCES = {"calendar_clean": CLEAN, "kink": KINK}


def _rule():
    return InformationRule(measurement_fields.load_registry(), scarcity.LEGS, decision_time=time(16, 0), horizon=1)


def _calendar_days(key):
    """Whether the estimator trains on calendar-clean days (`clean`), or on every day and so is provisional under "Calendar first"."""
    clean = {v.id for v in h.VARIANTS if v.days == "clean"} | {v.id for v in k.VARIANTS if v.clean}
    return "clean" if key.split("_")[-1] in clean else "all (provisional: trained on calendar days)"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_pins(pins, records):
    """Both tracked records were made at this tree's parent pin, panel and window."""
    for name, record in records.items():
        theirs = record["pins"]
        for key in ("parent_commit", "panel_version", "panel_sha256", "effr_series_sha256", "rows", "first_day", "last_day"):
            if theirs[key] != pins[key]:
                raise ValueError(f"the {name} record has {key} {theirs[key]!r}, but this run has {pins[key]!r}")
        if record["window_end"] != demand_curve.LAST_DAY.isoformat():
            raise ValueError(f"the {name} record's window ends {record['window_end']}, not {demand_curve.LAST_DAY}")


def _refit_from_record(row):
    """A refit rebuilt from the record's row alone: shares and fitted flag, no bootstrap draws (used only where the refit serves
    no day)."""
    shares = tuple(row["parameters"]) if row["fitted"] else None
    return c.RefitC(date.fromisoformat(row["cutoff"]), shares, bool(row["fitted"]), row["kink"], row["intercept"], row["slope"],
                    row["objective_or_sse"], row["training_days"], tuple(row["episodes"]), row["starts_agree"], (), (), {})


def _check_served(name, built, expected_served, expected_missing=None):
    summary = account.summarise(built)
    if summary["served_days"] != expected_served:
        raise ValueError(f"{name} serves {summary['served_days']} days, the tracked record says {expected_served}")
    if expected_missing is not None and summary["missing_days"] != expected_missing:
        raise ValueError(f"{name} misses {summary['missing_days']} days, the tracked record says {expected_missing}")


def build(args):
    clean = json.loads(CLEAN.read_text(encoding="utf-8"))
    kink = json.loads(KINK.read_text(encoding="utf-8"))
    rows, pins = h.build_rows()
    _check_pins(pins, {"calendar-clean": clean, "kink": kink})
    rows = [row for row in rows if row.date <= demand_curve.LAST_DAY]
    weeks = c.tracked_weeks()
    with scarcity.measurement_declaration():
        days = c.sample_c(rows, _rule(), weeks)
    day_set = {d.day for d in days}
    c_cutoffs = [date.fromisoformat(x) for x in clean["cutoffs"]]
    a_cutoffs = [date.fromisoformat(x) for x in kink["cutoffs"]]
    for cut in c_cutoffs + a_cutoffs:
        if cut not in day_set:
            raise ValueError(f"the record's refit cutoff {cut} is not a scored day of this run")

    accounts, checks = {}, {"c_refits_match_record": [], "served_days_match_record": []}
    # -- C and its calendar-clean variants ---------------------------------------------------------------------------------
    flags = series = None
    for name, entry in clean["estimators"].items():
        recorded = entry["refits"]
        summary = entry["summary"]
        if name in RERUN:
            started = clock.time()
            if name == "C":
                paths = h.baseline_path_c(days, c_cutoffs, replications=args.replications)
            else:
                if flags is None:
                    flags, series = h.read_flags(h.with_quarter_end_window(rows), h.flag_rule(), h.parent_turn_label()), h.left_sides(rows)
                spec = next(v for v in h.VARIANTS if v.id == name)
                paths = h.path_c(days, c_cutoffs, flags, spec.left, series, replications=args.replications, workers=args.workers,
                                 clean=spec.days == "clean", objective=spec.objective)
            refits = [p.refit for p in paths]
            account.check_against_record(refits, recorded)
            checks["c_refits_match_record"].append(name)
            print(f"{name}: refits re-run and equal to the record ({clock.time() - started:.0f} s)", flush=True)
        else:
            refits = [_refit_from_record(row) for row in recorded]
        built = account.account_c(name, days, c_cutoffs, refits)
        _check_served(name, built, summary["served_days"], summary["missing_days"] if name in RERUN else None)
        checks["served_days_match_record"].append(name)
        accounts[name] = ("C", built)
    # -- A and its variants --------------------------------------------------------------------------------------------------
    for name, entry in kink["estimators"].items():
        refits = account.a_refits_from_record(entry["refits"])
        if [r.cutoff for r in refits] != a_cutoffs:
            raise ValueError(f"{name}'s refits are not the kink record's cutoffs")
        own = account.account_a_own(name, days, a_cutoffs, refits)
        recorded = kink["summaries"][name]["all_served_days"]
        _check_served(f"A {name}", own, recorded["served_days"])
        checks["served_days_match_record"].append(f"A_{name}")
        accounts[f"A_{name}"] = ("A as defined", own)

    estimators = {}
    for key, (kind, built) in accounts.items():
        estimators[key] = {"view": kind, "calendar_days": _calendar_days(key),
                           "summary": account.summarise(built), "daily": account.daily(built)}
    served = sorted({day for _kind, b in accounts.values() for day in (s.day for s in b.served)})
    return {
        "note": "Generated by scripts/h7_account.py; never edited by hand.",
        "tier": "development", "directive": "repo-market-liquidity#144", "stage": "docs/stages/h7-step4.md",
        "decides_nothing": "The account's size decides nothing (docs/decisions/measurement-protocol.md section 8).",
        "alternatives": list(account.ALTERNATIVES), "groups": list(c.GROUPS), "unit": "points of bank assets",
        "pins": pins, "window_end": rows[-1].date.isoformat(), "first_served_day": served[0].isoformat(),
        "last_served_day": served[-1].isoformat(),
        "settings": {"replications": args.replications, "seed": c.SEED, "level": c.LEVEL, "serving_lag": account.SERVING_LAG,
                     "first_cutoff": FIRST_CUTOFF.isoformat(), "c_refits": len(c_cutoffs), "a_refits": len(a_cutoffs)},
        "sources": {name: {"path": str(path.relative_to(ROOT)), "sha256": _sha(path)} for name, path in SOURCES.items()},
        "checks": checks,
        "readings": {"a_as_defined": A_AS_DEFINED, "a_through_groups": READING},
        "withdrawn": account.withdrawal_entry([f"Ag_{name}" for name in kink["estimators"]]),
        "superseded": {"sha256": SUPERSEDED_SHA256, "reason": SUPERSEDED_REASON},
        "not_reported": {name: D_NOT_REPORTED for name in ("D",) + tuple("D" + v.id[1:] for v in h.VARIANTS)},
        "estimators": estimators,
    }


# -- the page ---------------------------------------------------------------------------------------------------------------


def _fmt(value, places=2):
    return "n/a" if value is None else f"{value:.{places}f}"


def _reading_lines(record):
    """The paragraph on the second reading: a marked reading, or, once withdrawn, the label, the reason and the superseded record."""
    if "withdrawn" not in record:
        return [f"**Marked reading, for Eleonora.** {record['readings']['a_through_groups']}"]
    return [f"**{record['withdrawn']['label']}.** The reading \"A through the group machinery\" is no longer reported: "
            f"{record['withdrawn']['reason']}", "",
            f"This record replaces the one with sha256 `{record['superseded']['sha256']}`: {record['superseded']['reason']}"]


def markdown(record):
    """The Markdown printed from the record. Never edited by hand."""
    pins = record["pins"]
    lines = ["# H7m: the account of the bank distribution for A and C (development)", "",
             "Generated from `results/h7/distribution-account.json` by `scripts/h7_account.py --render`; never edited by hand.",
             f"Tier: **{record['tier']}**. Development evidence, not a verdict. {record['decides_nothing']} "
             f"Stage document: `{record['stage']}`.", "",
             f"Panel version {pins['panel_version']} `{pins['panel_sha256']}`; parent `{pins['parent_commit']}`; days served "
             f"{record['first_served_day']} to {record['last_served_day']} (window ends {record['window_end']}); "
             f"{record['settings']['replications']} bootstrap draws for C's intervals. Unit: {record['unit']}. Sources: "
             + ", ".join(f"`{s['path']}` (`{s['sha256'][:12]}`)" for s in record["sources"].values()) + ".", "",
             "The three alternatives for how the same reserves spread over the three H.8 groups: `as_observed`, "
             "`all_large_domestic`, `proportional_to_assets` (protocol section 8). Each keeps the week's total reserves.", "",
             f"**A as defined.** {record['readings']['a_as_defined']}", "",
             *_reading_lines(record), "",
             "## Days served", "",
             "| Estimator | View | Calendar days | Served | Missing | Break-week days |", "|---|---|---|---|---|---|"]
    for name, e in record["estimators"].items():
        s = e["summary"]
        reasons = "; ".join(f"{k}: {v}" for k, v in s["missing_reasons"].items())
        lines.append(f"| {name} | {e['view']} | {e['calendar_days']} | {s['served_days']} | {s['missing_days']}"
                     + (f" ({reasons})" if reasons else "") + f" | {s['break_week_days']} |")
    lines += ["", "An estimator that serves no day has an empty account, and is listed.", "",
              "## Aggregate deployable liquidity under each alternative", "",
              "Points of bank assets over the served days. Interval: the median width of the 90% interval, where the estimator has one.", "",
              "| Estimator | Alternative | Days | Median | Min | Max | Median 90% width | Days at zero | Median difference from as observed |",
              "|---|---|---|---|---|---|---|---|---|"]
    for name, e in record["estimators"].items():
        for alt, row in e["summary"]["alternatives"].items():
            lines.append(f"| {name} | {alt} | {row['days']} | {_fmt(row['median_points'])} | {_fmt(row['min_points'])} | "
                         f"{_fmt(row['max_points'])} | {_fmt(row['median_width_points'])} | {row['days_at_zero']} | "
                         f"{_fmt(row['median_difference_points'])} |")
    grouped = {n: e for n, e in record["estimators"].items() if any("groups" in r for r in e["summary"]["alternatives"].values())}
    lines += ["", "## Group by group", "",
              "Each group's reserves above its own buffer, as points of the groups' total assets (they sum to the aggregate). "
              "Median over the served days, and the days on which the group's term is zero.", "",
              "| Estimator | Alternative | " + " | ".join(f"{g} median" for g in record["groups"]) + " | "
              + " | ".join(f"{g} days at zero" for g in record["groups"]) + " |",
              "|---|---|" + "---|" * (2 * len(record["groups"]))]
    for name, e in grouped.items():
        for alt, row in e["summary"]["alternatives"].items():
            g = row["groups"]
            lines.append(f"| {name} | {alt} | " + " | ".join(_fmt(g[x]["median_points"]) for x in record["groups"]) + " | "
                         + " | ".join(str(g[x]["days_at_zero"]) for x in record["groups"]) + " |")
    lines += ["", "## Median aggregate by calendar year", "",
              "| Estimator | Year | Days | " + " | ".join(record["alternatives"]) + " |", "|---|---|---|" + "---|" * len(record["alternatives"])]
    for name, e in record["estimators"].items():
        for year, row in e["summary"]["by_year"].items():
            lines.append(f"| {name} | {year} | {row['days']} | "
                         + " | ".join(_fmt(row["median_points"][alt]) for alt in record["alternatives"]) + " |")
    lines += ["", "## Checks the run made", "",
              f"- Refits re-run and equal to the tracked calendar-clean record: {', '.join(record['checks']['c_refits_match_record'])}.",
              f"- Served-day counts equal to the tracked records': {', '.join(record['checks']['served_days_match_record'])}.", "",
              "## Not reported", ""]
    for name, reason in record["not_reported"].items():
        lines.append(f"- {name}: {reason}.")
    lines.append("")
    return "\n".join(lines)


def withdraw(output):
    """Rewrite `output` without the rows of the withdrawn reading (`account.withdraw_group_reading`); only the superseded record."""
    raw = output.read_bytes()
    if _sha(output) != SUPERSEDED_SHA256:
        print(f"{output} is not the record with sha256 {SUPERSEDED_SHA256}: nothing withdrawn", file=sys.stderr)
        return 1
    record = account.withdraw_group_reading(json.loads(raw), superseded=SUPERSEDED_SHA256, reason=SUPERSEDED_REASON)
    output.write_text(account.dump_record(record), encoding="utf-8")
    print(f"withdrew the group reading from {output}; now render the page")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replications", type=int, default=demand_curve.REPLICATIONS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--page", type=Path, default=PAGE)
    parser.add_argument("--withdraw", action="store_true",
                        help="withdraw the group reading from the superseded record (#186); runs nothing, refuses any other record")
    parser.add_argument("--render", action="store_true", help="print the page from the record; run nothing")
    parser.add_argument("--check", action="store_true", help="with --render: write nothing, exit 1 if the page is stale")
    args = parser.parse_args(argv)
    if args.withdraw:
        return withdraw(args.output)
    if args.render:
        text = markdown(json.loads(args.output.read_text(encoding="utf-8")))
        if args.check:
            if not args.page.is_file() or args.page.read_text(encoding="utf-8") != text:
                print(f"{args.page} is stale: run scripts/h7_account.py --render", file=sys.stderr)
                return 1
            print("h7 distribution-account page: ok")
            return 0
        args.page.write_text(text, encoding="utf-8")
        print(f"wrote {args.page}")
        return 0
    record = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(account.dump_record(record), encoding="utf-8")
    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(markdown(json.loads(args.output.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {args.output} and {args.page}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
