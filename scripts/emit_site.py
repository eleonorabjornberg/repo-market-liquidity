#!/usr/bin/env python3
"""Emit the results site: site/index.html (directive #170; the pattern is the model repo's `scripts/emit_visual.py`).

The published face of Phase 3: what the data show, H10's development table and registration, H7m's two
development records, and where each hypothesis stands. Nothing on the page is typed:

* Every figure is read from a published record on main through one reader, `Records.figure`, which refuses a figure no
  record carries. The records are `results/h10/` (development, the two ON RRP sensitivities and the 2 bp placebo
  floor), `results/h7/kink.json`, `results/h7/calendar-clean.json` and `docs/research/h7-refit-schedule.json`.
* The three findings in "What the data show" are computed by the functions below from the parent's published panel,
  rebuilt from the parent's tracked fixtures at the pin and refused unless its SHA-256 is the published digest
  (`load_panel`), and from this repository's SRF-rate snapshot, refused unless its bytes match its manifest.
* Every pin and hash is read from the code or the record that defines it: `repo_liquidity.PARENT_COMMIT`,
  `repo_liquidity.PANEL_SHA256`, the panel manifest, `h10_live.method_digest()`, and the re-registration page.
* The template (`site/template.html`) carries no figure: `typed_numbers` finds any digit in its text, and the tests
  fail on one. A placeholder left unfilled is an error, and so is a value the template does not use.
* The status table is read from `docs/research/plan.md` (each hypothesis's development steps) and from the records'
  own metadata (which step has a record on main). GitHub is not read at build time.
* Development evidence is labelled as such beside each figure. No verdict is shown: confirmation is prospective only.

The page is built on main and never committed (#928 in the model repo): it is gitignored, the pages job builds it
(`--stamp`), the tests build their own copy, and `scripts/check_built_outputs.py` refuses a pull request that carries it.

Standard library only, plus this repository's own `src/` and the parent at the pin.

    python3 scripts/emit_site.py            # writes site/index.html
    python3 scripts/emit_site.py --check    # writes nothing; fails if the page does not build, is stale, or is tracked
    python3 scripts/emit_site.py --stamp    # as the first, stamped with the latest input commit (the pages job)
"""
import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import repo_liquidity  # noqa: E402

TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "index.html"

#: The model repo's site, linked from this page. The link back is a model-repo change.
PARENT_SITE = "https://eleonorabjornberg.github.io/repo-market-model/"
REPO_URL = "https://github.com/eleonorabjornberg/repo-market-liquidity"
PARENT_URL = "https://github.com/eleonorabjornberg/repo-market-model"

#: Eleonora's registration of H10 at the new pin: her own comment on #23 (not an app post), naming this repository's
#: commit. Pointers only; the digest and the pin come from the code and the re-registration page.
REGISTRATION_COMMIT = "783848316995d4f2d425abea0c6bd0be3e157c26"
REGISTRATION_COMMENT = "https://github.com/eleonorabjornberg/repo-market-liquidity/issues/23#issuecomment-6353434164"
RE_REGISTRATION_PAGE = "docs/research/h10-reregistration.md"

#: The five-lens review's Lens A, row A5 (model repo, PR #958), fixed to the commit that added it. It is after this
#: repository's parent pin, so it is cited by link and not read through the pin. A reviewer's reading, not a decision.
REVIEW_COMMIT = "6225bdbe58fc72aeaf83064b52121c790fbb2759"
REVIEW_PATH = "docs/reviews/2026-10-19-five-lens/lens-A-repo-trader.md"
REVIEW_QUOTE = "the ceiling leaks on snapshot dates and holds otherwise"

#: The windows of the three findings (Eleonora's request of 23 October 2026, #170).
ABUNDANCE_YEARS = (2021, 2023)
SCARCITY_YEARS = (2022, 2025)
#: SOFR minus IORB, in basis points, at which SOFR sat in the abundant years.
FLOOR_BP = Decimal(-10)

#: Which record carries each development step of a hypothesis (the status table). A step with no entry has no record.
STEP_RECORDS = {
    "H7m": {1: "results/h7/kink.json", 2: "results/h7/calendar-clean.json"},
    "H10": {1: "docs/decisions/h10-method.md", 2: "results/h10/development.json", 3: "results/h10/development.json"},
}
#: A step the records say was not built, with the record and keys that say so.
STEP_NOT_BUILT = {("H7m", 3): ("results/h7/calendar-clean.json", "not_run", "D")}
#: The plan's section for each hypothesis: the heading that opens it and the heading that ends it.
PLAN_SECTIONS = {"H7m": ("### H7m", "### H7f"), "H10": ("## H10.", "## The parent's exit criterion")}


class FigureError(ValueError):
    """A figure no published record carries (or a record that is missing)."""


class Records:
    """The one reader of published records. It refuses a figure no record carries and remembers what it read."""

    def __init__(self, root=ROOT):
        self.root = Path(root)
        self._read = {}

    def _bytes(self, relative):
        path = self.root / relative
        if not path.is_file():
            raise FigureError("record %s does not exist" % relative)
        data = path.read_bytes()
        self._read[relative] = hashlib.sha256(data).hexdigest()
        return data

    def text(self, relative):
        return self._bytes(relative).decode("utf-8")

    def figure(self, relative, *keys):
        """The value at `keys` in the JSON record `relative`; FigureError if the record does not carry it."""
        node = json.loads(self.text(relative))
        for key in keys:
            try:
                node = node[key]
            except (KeyError, IndexError, TypeError):
                raise FigureError("%s carries no figure at %s" % (relative, " / ".join(map(str, keys)))) from None
        return node

    def inputs(self):
        """(path, sha256) of every record read so far, in path order."""
        return sorted(self._read.items())


# --------------------------------------------------------------------------------------------- the panel and the findings


def load_panel(workdir=None, expected_sha=None):
    """The parent's published panel, rebuilt from its tracked fixtures at the pin, as a list of CSV rows (strings).

    Raises:
        ValueError: if the rebuilt panel's SHA-256 is not the published digest (`repo_liquidity.PANEL_SHA256`).
    """
    expected_sha = repo_liquidity.PANEL_SHA256 if expected_sha is None else expected_sha
    root = repo_liquidity.parent_root()
    manifest = json.loads((root / "metadata" / "funding_panel_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        output = Path(tmp) / "funding_panel.csv"
        subprocess.run(
            [sys.executable, "-B", "-m", "repo_model.cli", "build",
             "--raw-root", "tests/fixtures/snapshots/funding_inputs", "--registry", "metadata/sources.json",
             "--build-cutoff", manifest["build_cutoff"], "--decision-time", manifest["decision_time"],
             "--output", str(output)],
            cwd=root, check=True, capture_output=True, text=True)
        data = output.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha:
        raise ValueError("the rebuilt panel is %s, not the published %s" % (digest, expected_sha))
    return list(csv.DictReader(data.decode("utf-8").splitlines()))


def spread_bp(row):
    """SOFR minus IORB in basis points, exactly (decimal arithmetic on the panel's strings)."""
    return (Decimal(row["sofr"]) - Decimal(row["iorb"])) * 100


def _years(rows, first, last):
    """The rows of each year from `first` to `last`; ValueError if a year has none."""
    out = {}
    for year in range(first, last + 1):
        chosen = [r for r in rows if r["date"][:4] == str(year)]
        if not chosen:
            raise ValueError("the panel has no rows in %d" % year)
        out[year] = chosen
    return out


def _mean(values):
    values = list(values)
    return sum(values, Decimal(0)) / len(values)


def finding_abundance(rows, first_year, last_year):
    """Finding 1: how many days SOFR sat at `FLOOR_BP` below IORB, and how many days it did not move, in the years given.

    A day "did not move" when its spread equals the previous panel row's. Reserves are the panel's `reserve_balances`
    ($bn); the peak and the trough are the window's highest and lowest, with their dates.
    """
    by_year = _years(rows, first_year, last_year)
    window = [r for y in by_year.values() for r in y]
    index = {id(r): i for i, r in enumerate(rows)}
    at_floor = sum(1 for r in window if spread_bp(r) == FLOOR_BP)
    comparisons = [(r, rows[index[id(r)] - 1]) for r in window if index[id(r)] > 0]
    unchanged = sum(1 for r, previous in comparisons if spread_bp(r) == spread_bp(previous))
    peak = max(window, key=lambda r: Decimal(r["reserve_balances"]))
    trough = min(window, key=lambda r: Decimal(r["reserve_balances"]))
    return {
        "days": len(window),
        "share_at_floor": Decimal(at_floor) / len(window),
        "comparisons": len(comparisons),
        "share_unchanged": Decimal(unchanged) / len(comparisons),
        "reserves_max": {"bn": Decimal(peak["reserve_balances"]), "date": peak["date"]},
        "reserves_min": {"bn": Decimal(trough["reserve_balances"]), "date": trough["date"]},
        "years": [{"year": y, "days": len(r), "share_at_floor": Decimal(sum(1 for x in r if spread_bp(x) == FLOOR_BP))
                   / len(r), "reserves_mean_bn": _mean(Decimal(x["reserve_balances"]) for x in r)}
                  for y, r in by_year.items()],
    }


def finding_scarcity(rows, first_year, last_year):
    """Finding 2: the yearly mean of SOFR minus IORB (bp) over each year's panel days, with the year's mean reserves."""
    by_year = _years(rows, first_year, last_year)
    return {"years": [{"year": y, "days": len(r), "mean_bp": _mean(spread_bp(x) for x in r),
                       "reserves_mean_bn": _mean(Decimal(x["reserve_balances"]) for x in r)}
                      for y, r in by_year.items()]}


def finding_ceiling(rows, srf_rates, first_day, last_day):
    """Finding 3: SOFR against the SRF rate in force, on quarter-end days and on all other days.

    `srf_rates` is (effective date, rate in percent) pairs. The rate in force on a day is the latest one effective on or
    before it; a day before the first has no rate and is not counted. The quarter-end days are the panel's own
    `quarter_end` flag. Per class: the days, the days with SOFR above the rate, and the largest SOFR minus rate (bp).
    """
    srf_rates = sorted(srf_rates)
    classes = {"quarter_end": [], "other": []}
    for row in rows:
        if not first_day <= row["date"] <= last_day:
            continue
        in_force = [rate for effective, rate in srf_rates if effective <= row["date"]]
        if not in_force:
            continue
        margin = (Decimal(row["sofr"]) - in_force[-1]) * 100
        classes["quarter_end" if row["quarter_end"] == "1" else "other"].append((row, margin))
    if not classes["quarter_end"] and not classes["other"]:
        raise ValueError("no SRF rate is in force on any panel day from %s to %s" % (first_day, last_day))
    out = {}
    for name, days in classes.items():
        if not days:
            raise ValueError("no %s days from %s to %s" % (name, first_day, last_day))
        row, margin = max(days, key=lambda pair: pair[1])
        out[name] = {"days": len(days), "above": sum(1 for _, m in days if m > 0),
                     "above_days": [(r["date"], m) for r, m in days if m > 0],
                     "largest": {"date": row["date"], "margin_bp": margin, "spread_bp": spread_bp(row)}}
    return out


def load_srf_rates(records):
    """The SRF-rate snapshot's (effective date, rate) pairs, refused unless its bytes are the manifest's."""
    manifest = json.loads(records.text("snapshots/srf_rate/manifest.json"))
    data = records.text(manifest["path"])
    if hashlib.sha256(data.encode("utf-8")).hexdigest() != manifest["sha256"]:
        raise ValueError("snapshots/srf_rate: the file is not the one its manifest names")
    return [(r["effective_date"], Decimal(r["rate_percent"])) for r in csv.DictReader(data.splitlines())]


# ------------------------------------------------------------------------------------------------- the registration


def registration_record_text():
    return (ROOT / RE_REGISTRATION_PAGE).read_text(encoding="utf-8")


def registration(record_text=None):
    """H10's registration as the re-registration page and the code state it; ValueError if they disagree.

    The page's digest is the one Eleonora registered (her comment names the same). The code's is
    `h10_live.method_digest()` computed now, so a change to a frozen part turns this red.
    """
    from repo_liquidity import h10_live

    text = registration_record_text() if record_text is None else record_text
    digest = re.search(r"\| method_digest\(\) at the new pin \| `([0-9a-f]{64})` \|", text)
    record_sha = re.search(r"\| record_sha256\(\) \| `([0-9a-f]{64})` \|", text)
    parent = re.search(r"\| Parent commit \| `[0-9a-f]{40}` \| `([0-9a-f]{40})` \|", text)
    if not (digest and record_sha and parent):
        raise ValueError("%s no longer states the digest, the method record and the parent pin" % RE_REGISTRATION_PAGE)
    found = {"digest": digest.group(1), "code_digest": h10_live.method_digest(), "record_sha256": record_sha.group(1),
             "code_record_sha256": h10_live.record_sha256(), "parent": parent.group(1)}
    if found["digest"] != found["code_digest"]:
        raise ValueError("the registered method digest %s is not the code's %s" % (found["digest"], found["code_digest"]))
    if found["record_sha256"] != found["code_record_sha256"]:
        raise ValueError("the registered method record %s is not the code's %s"
                         % (found["record_sha256"], found["code_record_sha256"]))
    if found["parent"] != repo_liquidity.PARENT_COMMIT:
        raise ValueError("the re-registration page names parent %s, the code pins %s"
                         % (found["parent"], repo_liquidity.PARENT_COMMIT))
    found["commit"] = REGISTRATION_COMMIT
    return found


# ------------------------------------------------------------------------------------------------------- formatting


def esc(value):
    return html.escape(str(value), quote=True)


def num(value, places=1):
    """A number with a true minus sign; infinity and None are named, not printed."""
    if value is None:
        return "none"
    value = Decimal(str(value)) if not isinstance(value, Decimal) else value
    if not value.is_finite():
        return "not identified"
    text = "{:.{p}f}".format(value, p=places)
    return text.replace("-", "−")


def pct(value, places=0):
    return num(Decimal(str(value)) * 100, places) + "%"


def interval(pair, fmt=pct):
    return "%s to %s" % (fmt(pair[0]), fmt(pair[1]))


def tn(bn):
    return num(Decimal(bn) / 1000, 2)


def table(headers, body, caption=None):
    head = "".join("<th>%s</th>" % esc(h) for h in headers)
    rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in row) for row in body)
    cap = "<caption>%s</caption>" % esc(caption) if caption else ""
    return '<div class="scroll"><table>%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (cap, head, rows)


def code(text):
    return "<code>%s</code>" % esc(text)


def link(url, label):
    return '<a href="%s">%s</a>' % (esc(url), esc(label))


def short(sha):
    return sha[:8] + "…" + sha[-4:]


# ---------------------------------------------------------------------------------------------------------- sections


def section_findings(rows, records):
    first, last = ABUNDANCE_YEARS
    one = finding_abundance(rows, first, last)
    y0, y1 = SCARCITY_YEARS
    two = finding_scarcity(rows, y0, y1)
    floor_date = records.figure("docs/research/h7-refit-schedule.json", "entry_dates", "C", "episode:%d" % y1)
    episode_floor = records.figure("docs/research/h7-refit-schedule.json", "episode_floor")
    window_end = records.figure("results/h7/kink.json", "window_end")
    srf = load_srf_rates(records)
    three = finding_ceiling(rows, srf, srf[0][0], window_end)
    out = {}
    out["f1_lead"] = esc(
        "From %d to %d SOFR sat exactly %s bp below IORB on %s of the %d panel days and did not move from the previous day on "
        "%s. Reserve balances ran from %s tn on %s down to %s tn on %s."
        % (first, last, num(-FLOOR_BP, 0), pct(one["share_at_floor"]), one["days"], pct(one["share_unchanged"]),
           tn(one["reserves_max"]["bn"]), one["reserves_max"]["date"], tn(one["reserves_min"]["bn"]),
           one["reserves_min"]["date"]))
    out["f1_table"] = table(
        ["Year", "Panel days", "Days at the floor", "Mean reserves ($ tn)"],
        [[str(y["year"]), str(y["days"]), pct(y["share_at_floor"]), tn(y["reserves_mean_bn"])] for y in one["years"]],
        "Finding one, by year: the spread against reserves")
    out["f2_lead"] = esc(
        "The yearly mean of SOFR minus IORB went %s bp. The record of refit dates (%s) has C's %d episode reach its "
        "floor of %d scarce days on %s."
        % (" to ".join(num(y["mean_bp"], 1) for y in two["years"]), "docs/research/h7-refit-schedule.json", y1,
           episode_floor, floor_date))
    out["f2_table"] = table(
        ["Year", "Panel days", "Mean SOFR minus IORB (bp)", "Mean reserves ($ tn)"],
        [[str(y["year"]), str(y["days"]), num(y["mean_bp"], 1), tn(y["reserves_mean_bn"])] for y in two["years"]],
        "Finding two, by year: the spread against reserves")
    qe, other = three["quarter_end"], three["other"]
    out["f3_lead"] = esc(
        "With the SRF rate in force (%s to %s), SOFR was above it on %d of %d quarter-end days and on %d of %d other days. "
        "The largest margin on a quarter-end day was %s bp on %s (SOFR minus IORB that day: %s bp); on other days it was "
        "%s bp on %s."
        % (srf[0][0], window_end, qe["above"], qe["days"], other["above"], other["days"],
           num(qe["largest"]["margin_bp"], 0), qe["largest"]["date"], num(qe["largest"]["spread_bp"], 0),
           num(other["largest"]["margin_bp"], 0), other["largest"]["date"]))
    out["f3_table"] = table(
        ["Day type", "Days", "Days SOFR above the SRF rate", "Largest SOFR minus SRF rate (bp)", "On"],
        [["Quarter-end (the panel's flag)", str(qe["days"]), str(qe["above"]), num(qe["largest"]["margin_bp"], 0),
          qe["largest"]["date"]],
         ["Every other day", str(other["days"]), str(other["above"]), num(other["largest"]["margin_bp"], 0),
          other["largest"]["date"]]],
        "Finding three: SOFR against the SRF rate in force")
    listed = sorted([(d, m, "quarter-end") for d, m in qe["above_days"]] + [(d, m, "other") for d, m in other["above_days"]])
    out["f3_days"] = table(["Day", "Day type", "SOFR minus SRF rate (bp)"],
                           [[d, kind, num(m, 0)] for d, m, kind in listed], "Every day SOFR was above the SRF rate in force")
    review_url = "%s/blob/%s/%s" % (PARENT_URL, REVIEW_COMMIT, REVIEW_PATH)
    out["f3_reading"] = ('The five-lens review’s Lens A (row A5) reads it as "%s". That is the reviewer’s '
                         "reading, not a decision record: %s, fixed to commit %s."
                         % (esc(REVIEW_QUOTE), link(review_url, "the review"), code(REVIEW_COMMIT[:8])))
    return out


def section_h10(records, reg):
    development = "results/h10/development.json"
    summary = records.figure(development, "summary")
    tier = records.figure(development, "tier")
    out = {"h10_tier": esc(tier), "h10_not_a_verdict": esc(records.figure(development, "not_a_verdict"))}

    def group(label, node):
        return [label, str(node["episodes"]), "%d (%s)" % (node["under_bar"], interval(node["intervals"]["under_bar"])),
                "%d (%s)" % (node["beats_null"], interval(node["intervals"]["beats_null"])),
                "%d (%s)" % (node["counted"], interval(node["intervals"]["counted"]))]

    splits = summary["splits"]
    body = [group("All development onsets", summary),
            group("ON RRP depleted", splits["regime"]["depleted"]), group("ON RRP abundant", splits["regime"]["abundant"]),
            group("Quarter-end onsets", splits["day_type"]["quarter-end"]), group("Other onsets", splits["day_type"]["other"])]
    out["h10_outcome"] = esc("%s (the rule on the share of episodes counted: %s; on the residual bar alone: %s)"
                             % (summary["outcome"], summary["outcome"], summary["under_bar_outcome"]))
    out["h10_groups"] = table(
        ["Group", "Episodes", "Under the residual bar", "Beats the null", "Both (counted)"], body,
        "H10 development onsets: episodes with the residual under the bar and beating the selection-aware null (Wilson 90% intervals)")
    markers = summary["markers"]
    labels = (("median_residual_share", "Median residual share"),
              ("median_explained_above_reserves", "Median explained share above reserves alone"),
              ("median_placebo_gap", "Median placebo gap (episode less its placebo windows)"))
    out["h10_markers"] = table(
        ["Progress marker", "Median", "90% interval on the median", "Episodes"],
        [[label, num(markers[key]["median"], 2), interval(markers[key]["interval"], lambda v: num(v, 2)),
          str(markers[key]["n"])] for key, label in labels],
        "H10 progress markers")
    sens = []
    for label, path in (("The decided driver set", development),
                        ("ON RRP as an interaction with the depleted regime", "results/h10/sensitivity_onrrp_interaction.json"),
                        ("ON RRP as two regime-specific terms", "results/h10/sensitivity_onrrp_regimes.json")):
        node = records.figure(path, "summary")
        sens.append([label, str(node["episodes"]), str(node["counted"]), node["outcome"], code(path)])
    out["h10_sensitivity"] = table(["Specification", "Episodes", "Counted", "Outcome", "Record"], sens,
                                   "H10 sensitivities, reported only: the decided driver set and the outcome do not change")
    placebo = "results/h10/placebo_floor_2bp.json"
    readings = records.figure(placebo, "readings")
    out["h10_placebo"] = table(
        ["Placebo windows", "Windows attributed", "Median placebo gap", "90% interval"],
        [["Without a rise floor", str(readings["unfloored"]["attributed_windows"]),
          num(readings["unfloored"]["median_placebo_gap"]["median"], 2),
          interval(readings["unfloored"]["median_placebo_gap"]["interval"], lambda v: num(v, 2))],
         ["With the placebo rise floor", str(readings["floored"]["attributed_windows"]),
          num(readings["floored"]["median_placebo_gap"]["median"], 2),
          interval(readings["floored"]["median_placebo_gap"]["interval"], lambda v: num(v, 2))]],
        "H10 placebo comparison: the rise floor on placebo windows")
    out["h10_registration"] = (
        "<dl><dt>Registered by</dt><dd>%s (her own comment, not an app post)</dd>"
        "<dt>This repository at</dt><dd>%s</dd><dt>Method digest</dt><dd>%s</dd>"
        "<dt>Method record</dt><dd>%s, SHA-256 %s</dd><dt>Parent</dt><dd>%s</dd><dt>Phase 3 panel</dt><dd>version %s, SHA-256 %s</dd></dl>"
        % (link(REGISTRATION_COMMENT, "Eleonora, on #23"),
           link("%s/commit/%s" % (REPO_URL, reg["commit"]), reg["commit"][:7]), code(reg["digest"]),
           code("docs/decisions/h10-method.md"), code(short(reg["record_sha256"])), code(repo_liquidity.PARENT_COMMIT[:7]),
           esc(records.figure("metadata/phase3_panel_v4_manifest.json", "version")),
           code(records.figure("metadata/phase3_panel_v4_manifest.json", "sha256"))))
    return out


def _goalpost(held):
    return "holds" if held else "does not hold"


def section_h7(records):
    kink = "results/h7/kink.json"
    common = records.figure(kink, "summaries", "B", "common_served_days")
    limit_gap = common["goalpost_1"]["limit"]
    limit_width = common["goalpost_2"]["limit"]
    comparison = records.figure(kink, "comparison")
    first = comparison[sorted(comparison)[0]]
    body = [["Baseline B", "0", num(first["baseline_worst_gap_points"], 2), "-", num(first["baseline_median_width_points"], 2),
             "-"]]
    for name in sorted(comparison):
        node = comparison[name]
        body.append([name, str(node["not_fitted_refits"]), num(node["worst_gap_points"], 2),
                     _goalpost(node["goalpost_1_holds"]), num(node["median_width_points"], 2),
                     _goalpost(node["goalpost_2_holds"])])
    out = {"h7_tier": esc(records.figure(kink, "tier")),
           "h7_kink_days": esc(records.figure(kink, "same_served_days")),
           "h7_kink_limits": esc("%s points for the worst gap between consecutive refits, %s points for the median width of the 90%% interval"
                                 % (num(limit_gap, 1), num(limit_width, 1))),
           "h7_kink_table": table(
               ["Estimator", "Refits not fitted", "Worst refit gap (points)", "Goalpost one", "Median 90% width (points)",
                "Goalpost two"], body, "A's kink record, on the days every estimator serves"),
           "h7_kink_superseded": esc("%s Superseded record: %s."
                                     % (records.figure(kink, "superseded", "reason"),
                                        short(records.figure(kink, "superseded", "sha256"))))}
    clean = "results/h7/calendar-clean.json"
    comparison = records.figure(clean, "comparison")
    body = []
    for name in sorted(comparison):
        node = comparison[name]
        status = node["refit_status"]
        body.append([name, ", ".join("%s %d" % (k, status[k]) for k in sorted(status)),
                     esc(node["goalpost_1_reading"]), _goalpost(node["goalpost_2_holds"]),
                     num(node["median_width_points"], 2), num(node["baseline_median_width_points"], 2)])
    not_run = records.figure(clean, "not_run", "D")
    if records.figure(clean, "tier") != records.figure(kink, "tier"):
        raise ValueError("the two H7m records are not at the same tier")
    out.update({
        "h7_clean_table": table(
            ["Variant", "Refits", "Goalpost one", "Goalpost two", "Median 90% width (points)", "Candidate C's width (points)"],
            body, "C's calendar-clean record: which variants serve days and which are not identified"),
        "h7_clean_d": esc("Candidate D: %s." % not_run)})
    return out


def plan_steps(plan_text, hypothesis):
    """(number, title) of the development steps the plan lists for `hypothesis` (`PLAN_SECTIONS`)."""
    start, end = PLAN_SECTIONS[hypothesis]
    begin = plan_text.find("\n" + start)
    stop = plan_text.find("\n" + end, begin + 1)
    if begin < 0 or stop < 0:
        raise ValueError("docs/research/plan.md no longer has the section %s" % hypothesis)
    section = plan_text[begin:stop]
    marker = section.find("**Development steps")
    if marker < 0:
        raise ValueError("docs/research/plan.md lists no development steps for %s" % hypothesis)
    steps = []
    for line in section[marker:].split("\n")[1:]:
        match = re.match(r"^(\d+)\. \*\*(.+?)\*\*", line)
        if match:
            steps.append((int(match.group(1)), match.group(2).rstrip(".:")))
        elif line.startswith("**"):
            break
    if not steps:
        raise ValueError("docs/research/plan.md lists no numbered development steps for %s" % hypothesis)
    return steps


def section_status(records):
    plan = records.text("docs/research/plan.md")
    body = []
    for hypothesis, records_by_step in STEP_RECORDS.items():
        steps = plan_steps(plan, hypothesis)
        recorded = set(records_by_step) | {n for (h, n) in STEP_NOT_BUILT if h == hypothesis}
        current = next((n for n, _ in steps if n not in recorded), None)
        for number, title in steps:
            path = records_by_step.get(number)
            if (hypothesis, number) in STEP_NOT_BUILT:
                state = esc(records.figure(*STEP_NOT_BUILT[(hypothesis, number)]))
            elif path is None:
                state = "no record on main" + (" (current step)" if number == current else "")
            elif path.endswith(".json"):
                state = "%s, %s, %s" % (code(path), esc(records.figure(path, "directive")),
                                        esc(records.figure(path, "tier")))
            else:
                records.text(path)
                state = "%s (decision record)" % code(path)
            body.append([hypothesis, str(number), esc(title), state])
    return {"status_table": table(["Hypothesis", "Step", "Plan step", "Record on main"], body,
                                  "Each hypothesis's development steps (docs/research/plan.md) and the record that carries each")}


# --------------------------------------------------------------------------------------------------- template and page


def typed_numbers(template_text):
    """Every figure typed into the template's text: digits left once markup, style, scripts, placeholders and hypothesis
    names (H7, H10, H7m) are removed."""
    text = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", template_text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]*>", " ", text)
    text = re.sub(r"\{\{[^}]*\}\}", " ", text)
    text = re.sub(r"\bH\d+[a-z]?\b", " ", text)
    return re.findall(r"\d+(?:[.,]\d+)*", text)


def render(template_text, values):
    """Fill `{{name}}` placeholders. An unfilled placeholder and an unused value are both errors."""
    names = set(re.findall(r"\{\{([a-z0-9_]+)\}\}", template_text))
    missing = sorted(names - set(values))
    unused = sorted(set(values) - names)
    if missing:
        raise ValueError("placeholders left unfilled: %s" % ", ".join(missing))
    if unused:
        raise ValueError("values the template does not use: %s" % ", ".join(unused))
    return re.sub(r"\{\{([a-z0-9_]+)\}\}", lambda m: values[m.group(1)], template_text)


def build(rows, stamp=None, records=None):
    """The page, as a string, from the panel rows and the records. Deterministic for fixed inputs and `stamp`."""
    records = Records() if records is None else records
    typed = typed_numbers(TEMPLATE.read_text(encoding="utf-8"))
    if typed:
        raise ValueError("site/template.html carries typed numbers: %s" % ", ".join(typed))
    reg = registration()
    values = {}
    values.update(section_findings(rows, records))
    values.update(section_h10(records, reg))
    values.update(section_h7(records))
    values.update(section_status(records))
    manifest = "metadata/phase3_panel_v4_manifest.json"
    values.update({
        "parent_commit": code(repo_liquidity.PARENT_COMMIT),
        "parent_panel": code(repo_liquidity.PANEL_SHA256),
        "phase3_panel": code(records.figure(manifest, "sha256")),
        "phase3_panel_version": esc(records.figure(manifest, "version")),
        "parent_site": esc(PARENT_SITE),
        "repo_url": esc(REPO_URL),
        "stamp": esc(stamp or "not stamped (a local or test build)"),
    })
    values["inputs"] = "".join("<li>%s <span class=\"hash\">%s</span></li>" % (code(path), esc(digest[:12]))
                               for path, digest in records.inputs())
    return render(TEMPLATE.read_text(encoding="utf-8"), values)


def latest_input_commit(paths):
    """The latest commit that changed one of `paths` (needs history), as 'short-sha date'; ValueError on a shallow clone."""
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True, text=True)
    if shallow.stdout.strip() == "true":
        raise ValueError("--stamp reads git history, and this is a shallow clone")
    out = subprocess.run(["git", "log", "-1", "--format=%h %cs", "--", *paths], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.strip()
    if not out:
        raise ValueError("no commit has changed an input yet")
    return out


def check(rows, output=OUTPUT):
    """Problems with the page: it does not build, it is not what the inputs build (stale), or a built file is tracked."""
    problems = []
    try:
        page = build(rows)
    except ValueError as error:
        return ["the page does not build: %s" % error]
    output = Path(output)
    if output.exists() and output.read_text(encoding="utf-8") != page:
        problems.append("%s is stale: it is not what the inputs build; rebuild it with scripts/emit_site.py" % output.name)
    tracked = subprocess.run(["git", "ls-files", "site/index.html"], cwd=ROOT, capture_output=True, text=True).stdout
    if tracked.strip():
        problems.append("site/index.html is tracked; it is built on main and never committed")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="write nothing; fail on a build error, a stale page or a tracked built file")
    parser.add_argument("--stamp", action="store_true", help="stamp the page with the latest commit that changed an input")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args(argv)
    rows = load_panel()
    if args.check:
        problems = check(rows, output=Path(args.output))
        for problem in problems:
            print(problem)
        if not problems:
            print("site: builds from the records, nothing stale or tracked")
        return 1 if problems else 0
    records = Records()
    stamp = None
    if args.stamp:
        build(rows, records=records)
        stamp = latest_input_commit([path for path, _ in records.inputs()] + ["site/template.html", "scripts/emit_site.py"])
        records = Records()
    page = build(rows, stamp=stamp, records=records)
    Path(args.output).write_text(page, encoding="utf-8")
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
