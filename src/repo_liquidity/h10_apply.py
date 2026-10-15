"""H10 step 2: the declared method applied to every development onset (`docs/stages/h10-step2.md`).

The method is `docs/decisions/h10-method.md` (sections 1 to 9, Eleonora's values of 13 and 14 October 2026) and the code
is `repo_liquidity.attribution`; nothing about the method is decided here. This module reads the parent's panel at the
pin, takes the episode list from the parent's onset rule (cross-checked with its second source), attributes each episode
through the real-data entry point (`attribution.attribute`, which checks the window against the parent's as-of rule at
the report day), and assembles the development record `results/h10/development.json`.

**Development evidence, never a verdict** (`docs/decisions/measurement-protocol.md` section 1; eleonorabjornberg/
repo-market-model#640): the record says what the development table shows and nothing more. No day after the parent's
development end is read; the lockbox is the parent's. Standard library only.
"""

from __future__ import annotations

import hashlib
import math
import multiprocessing
import statistics
import tempfile
from contextlib import contextmanager
from datetime import date, time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, attribution, declaration, development, panel
from repo_liquidity.attribution import Attribution, DRIVERS_WITH_ON_RRP, SEED, SPREAD

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "results" / "h10" / "development.json"
#: H10 step 3 (#77): the same application with ON RRP entering as `on_rrp x 1(on_rrp < break)` (her answer 5 on #69).
SENSITIVITY_RECORD = ROOT / "results" / "h10" / "sensitivity_onrrp_interaction.json"
#: H10 step 3 (#86, finding #79): ON RRP as two regime-specific terms; supersedes the interaction sensitivity above.
REGIMES_RECORD = ROOT / "results" / "h10" / "sensitivity_onrrp_regimes.json"
PLACEBO_FLOOR_RECORD = ROOT / "results" / "h10" / "placebo_floor_2bp.json"
STAGE_DOC = ROOT / "docs" / "stages" / "h10-step2.md"
#: The panel the application reads: version 1, the published columns plus the built ON RRP take-up, to the development end.
PANEL_VERSION = 1
#: An episode is reported within 10 business days of its onset (the plan, Q7; the record, section 3). The report instant is
#: that panel day's decision instant, 16:00, and the window's inputs must be public by then.
REPORT_DAYS = 10
DECISION_TIME = time(16, 0)
#: The interval on a count of episodes: Wilson's score interval at the method's 90% level, treating the episodes as
#: independent (they cluster at quarter-ends, so it is optimistic; stated in the stage document).
INTERVAL_LEVEL = attribution.LEVEL
REGIMES = ("depleted", "abundant")
DAY_TYPES = ("quarter-end", "other")
COUNTS = ("under_bar", "beats_null", "counted")


# --------------------------------------------------------------------------- counts and their intervals


def wilson(successes: int, total: int, level: float = INTERVAL_LEVEL) -> List[float]:
    """Wilson's score interval for a proportion.

    Raises:
        ValueError: `total` is not positive, or `successes` is outside 0..total.
    """
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError(f"no interval for {successes} of {total}")
    z = _normal_quantile(1 - (1 - level) / 2)
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [0.0 if successes == 0 else max(0.0, centre - half), 1.0 if successes == total else min(1.0, centre + half)]


def _normal_quantile(q: float) -> float:
    from statistics import NormalDist

    return NormalDist().inv_cdf(q)


def median_interval(values: Sequence[float], level: float = INTERVAL_LEVEL) -> dict:
    """The median of `values` with the distribution-free (sign-test) interval from two order statistics: the widest
    ranks whose lower tail, under Binomial(n, 1/2), is at most half of 1 - level. Fewer than six values give the range."""
    ranked = sorted(values)
    n = len(ranked)
    if n == 0:
        return {"n": 0, "median": None, "interval": None}
    tail, lower = 0.0, 1
    for k in range(n + 1):
        tail += math.comb(n, k) / 2 ** n  # P(X <= k)
        if tail > (1 - level) / 2:
            break
        lower = k + 1  # P(X <= lower - 1) is within the tail
    upper = n + 1 - lower
    return {"n": n, "median": statistics.median(ranked), "interval": [ranked[lower - 1], ranked[upper - 1]]}


def _markers(entries: Sequence[dict]) -> dict:
    """The plan's progress markers (H10): the median residual share, the explained share above reserves alone, and the
    placebo gap (the episode's explained share less its placebo windows' median), each over the attributed episodes."""
    attributed = [e for e in entries if e["status"] == "attributed"]
    return {
        "median_residual_share": median_interval([e["residual"]["point"] for e in attributed]),
        "median_explained_above_reserves": median_interval(
            [e["explained_above_reserves"] for e in attributed if e["explained_above_reserves"] is not None]),
        "median_placebo_gap": median_interval(
            [e["explained_share"] - e["placebo"]["median_explained"] for e in attributed
             if e["placebo"]["median_explained"] is not None]),
    }


def _group(entries: Sequence[dict]) -> dict:
    total = len(entries)
    out = {"episodes": total, **{key: sum(1 for e in entries if e[key]) for key in COUNTS},
           "not_attributable": sum(1 for e in entries if e["status"] != "attributed")}
    out["intervals"] = None if total == 0 else {key: wilson(out[key], total) for key in COUNTS}
    return out


def _outcome(count: int, total: int) -> str:
    return "drivers named" if total and count / total > attribution.MAJORITY else "residual dominates"


def summarise(entries: Sequence[dict]) -> dict:
    """The outcome rule's counts over every episode (a not-attributable one is a miss), with a Wilson interval on each,
    and the two splits, each group with its own count (the plan's benchmark rule)."""
    total = len(entries)
    out = _group(entries)
    out["fraction"] = out["counted"] / total if total else 0.0
    out["outcome"] = _outcome(out["counted"], total)
    out["under_bar_outcome"] = _outcome(out["under_bar"], total)
    out["markers"] = _markers(entries)
    out["splits"] = {
        "regime": {name: _group([e for e in entries if e["regime"] == name]) for name in REGIMES},
        "day_type": {
            "quarter-end": _group([e for e in entries if e["quarter_end"]]),
            "other": _group([e for e in entries if not e["quarter_end"]]),
        },
    }
    return out


def placebo_summary(results: Sequence[Attribution], episode_explained: Optional[float]) -> dict:
    """The same decomposition on windows that touch no episode: how many were attributable, their median explained
    share, and the share of them that explain at least as much as the episode does."""
    shares = [r.explained_share for r in results if r.status == "attributed"]
    return {
        "windows": len(results),
        "attributed": len(shares),
        "median_explained": statistics.median(shares) if shares else None,
        "share_at_or_above": (
            sum(1 for s in shares if s >= episode_explained) / len(shares)
            if shares and episode_explained is not None else None
        ),
    }


def floored_placebo_summary(results: Sequence[Attribution], episode_explained: Optional[float],
                            floor: float = attribution.PLACEBO_RISE_FLOOR_BP) -> dict:
    """`placebo_summary` over the windows whose spread rise is at least `floor` bp (section 10 of the method record).

    A window below the floor is excluded, not refused, and `excluded` counts it: every window with a rise under the
    floor, a zero or negative rise included. A window with an input missing has no rise to compare and is counted as
    not attributable, as in the unfloored reading."""
    excluded = sum(1 for r in results if r.rise_bp is not None and r.rise_bp < floor)
    kept = [r for r in results if r.status == "attributed" and r.rise_bp >= floor]
    return {**placebo_summary(kept, episode_explained), "windows": len(results), "excluded": excluded}


def as_attribution(entry: dict) -> Attribution:
    """The `Attribution` an episode entry of the record stands for (only the fields the outcome rule reads)."""
    residual = entry.get("residual")
    return Attribution(
        entry.get("index", 0), entry["status"], entry.get("reason"), rise_bp=entry.get("rise_bp"),
        residual_share=None if residual is None else residual["point"], explained_share=entry.get("explained_share"),
    )


# --------------------------------------------------------------------------- the panel, the rule, one episode


def load_development():
    """The panel rows to the development end and the panel's manifest. Rebuilds version 1 from the tracked fixtures and
    refuses if it does not give the manifest's digest.

    Raises:
        ValueError: the rebuilt panel is not the manifest's.
        LookAheadError: a row is on a day the parent's lockbox holds.
    """
    from repo_model.data import load_daily_panel

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "phase3_panel.csv"
        manifest = panel.build(path, version=PANEL_VERSION)
        recorded = panel.load_manifest(PANEL_VERSION)
        if manifest["sha256"] != recorded["sha256"]:
            raise ValueError(f"panel version {PANEL_VERSION} rebuilt to {manifest['sha256']}, not its manifest's {recorded['sha256']}")
        end = development.development_end()
        rows = [row for row in load_daily_panel(path) if end is None or row.date <= end]
    dates = [row.date for row in rows]
    attribution.check_development(dates)
    return rows, manifest


@contextmanager
def real_rule():
    """The parent's as-of rule over the spread and the five drivers, under Phase 3's declaration (ON RRP take-up from the
    New York Fed's operation results), at the 16:00 decision instant."""
    from repo_model.asof import InformationRule

    with declaration.phase3_declaration():
        yield InformationRule(declaration.registry(), list(DRIVERS_WITH_ON_RRP), decision_time=DECISION_TIME)


def interaction_series(series: attribution.Series, break_bn: float) -> Dict[str, list]:
    """A copy of `series` whose ON RRP column is `on_rrp x 1(on_rrp < break_bn)`: take-up counts only while it is below
    the break (the parent's `ON_RRP_DEPLETION_BREAK_BN`, strictly), and is zero above it. A missing day stays missing.
    Every other column is copied unchanged and the input is not modified."""
    out = {name: list(values) for name, values in series.items()}
    out[attribution.ON_RRP] = [None if v is None else (v if v < break_bn else 0.0) for v in series[attribution.ON_RRP]]
    return out


def report_index(start: int, count: int) -> int:
    """The panel day on which an episode starting at `start` is reported: `REPORT_DAYS` panel days later.

    Raises:
        ValueError: that day is not in the sample of `count` panel days.
    """
    index = start + REPORT_DAYS
    if index >= count:
        raise ValueError("the report day is past the last development day")
    return index


def attribute_episode(series, dates, rule, start: int, *, draws: int = attribution.DRAWS, seed: int = SEED,
                      drivers: Sequence[str] = DRIVERS_WITH_ON_RRP) -> Attribution:
    """One episode through the real-data entry point. An episode whose report day is past the sample is "not
    attributable" with that reason (never dropped); a window not public at the report day raises `LookAheadError`."""
    try:
        report = report_index(start, len(dates))
    except ValueError:
        return Attribution(start, "not attributable", "the report day (10 panel days after the onset) is past the last development day")
    return attribution.attribute(series, start, rule=rule, dates=dates, report_index=report, drivers=drivers, draws=draws, seed=seed)


# --------------------------------------------------------------------------- the whole application

_STATE: dict = {}


def _share(point, interval) -> dict:
    return {"point": point, "low": interval[0], "high": interval[1]}


def _work(start: int) -> dict:
    """One episode, in a worker: its attribution, the benchmark and the placebo comparison."""
    series, dates, rule, draws, placebo_windows = (_STATE[k] for k in ("series", "dates", "rule", "draws", "placebo"))
    raw_on_rrp = _STATE["raw_on_rrp"]
    drivers = _STATE["drivers"]
    result = attribute_episode(series, dates, rule, start, draws=draws, drivers=drivers)
    entry = {
        "onset": dates[start].isoformat(), "index": start,
        "report_day": dates[start + REPORT_DAYS].isoformat() if start + REPORT_DAYS < len(dates) else None,
        "status": result.status, "reason": result.reason, "rise_bp": result.rise_bp,
        "regime": "depleted" if raw_on_rrp[start] < _STATE["break"] else "abundant",
        "quarter_end": bool(series["quarter_end"][start]), "on_rrp_at_onset": raw_on_rrp[start],
    }
    if result.status != "attributed":
        return entry
    placebo = [attribution.point_attribution(series, s, drivers=drivers) for s in placebo_windows[start]]
    entry.update(
        shares={name: _share(result.shares[name], result.intervals[name]) for name in drivers},
        fixed_shares=dict(result.fixed_shares),
        residual=_share(result.residual_share, result.residual_interval),
        explained_share=result.explained_share,
        explained_above_reserves=attribution.explained_above_reserves(series, start, drivers),
        placebo=placebo_summary(placebo, result.explained_share),
        unusable_draws=result.unusable_draws,
    )
    return entry


def build_record(rows, manifest, *, draws: int = attribution.DRAWS, null_draws: int = attribution.NULL_DRAWS,
                 workers: int = 1, interaction: bool = False, regimes: bool = False) -> dict:
    """The development record: every onset attributed, missed or not attributable, the null, the counts and the splits.

    With `interaction` the ON RRP driver is `on_rrp x 1(on_rrp < break)` instead of its window change, everywhere (the
    fit, the Shapley shares, the placebo, the benchmark and the null), and the record is marked as a sensitivity. The regime
    and `on_rrp_at_onset` are always read from the plain take-up, so the two records' episodes are comparable.

    With `regimes` the ON RRP driver is two drivers, `window change x 1(depleted)` and `window change x 1(abundant)`, the
    window's regime fixed by its baseline mean ON RRP (`attribution.window_change`); the series is the plain one.

    Raises:
        ValueError: both `interaction` and `regimes` are set."""
    from repo_model.contract import ON_RRP_DEPLETION_BREAK_BN

    if interaction and regimes:
        raise ValueError("a sensitivity is either the interaction or the regime terms, not both")
    drivers = attribution.DRIVERS_REGIME_TERMS if regimes else DRIVERS_WITH_ON_RRP
    dates = [row.date for row in rows]
    series = attribution.series_from_rows(rows, DRIVERS_WITH_ON_RRP)
    raw_on_rrp = list(series[attribution.ON_RRP])
    if interaction:
        series = interaction_series(series, ON_RRP_DEPLETION_BREAK_BN)
    onsets = attribution.cross_check_onsets(rows)
    placebo = attribution.placebo_starts(series, onsets, attribution.PLACEBO_WINDOWS, SEED)
    null = attribution.selection_null(series, drivers, draws=null_draws, seed=SEED)
    with real_rule() as rule:
        _STATE.update(series=series, dates=dates, rule=rule, draws=draws, placebo=placebo, raw_on_rrp=raw_on_rrp, drivers=drivers,
                      **{"break": ON_RRP_DEPLETION_BREAK_BN})
        try:
            if workers > 1:
                with multiprocessing.get_context("fork").Pool(workers) as pool:
                    entries = pool.map(_work, onsets, chunksize=1)
            else:
                entries = [_work(start) for start in onsets]
        finally:
            _STATE.clear()
    for entry in entries:
        attributed = entry["status"] == "attributed"
        entry["under_bar"] = attributed and abs(entry["residual"]["point"]) < attribution.RESIDUAL_BAR
        entry["beats_null"] = attributed and entry["explained_share"] > null.bar
        entry["counted"] = entry["under_bar"] and entry["beats_null"]
    ranked = list(null.explained)
    out = {
        "record": ("H10 step 3: sensitivity, ON RRP entering as two regime-specific terms" if regimes else
                   "H10 step 3: sensitivity, ON RRP entering as an interaction with the depleted regime" if interaction
                   else "H10 step 2: the declared method applied to the development onsets"),
        "directive": ("eleonorabjornberg/repo-market-liquidity#86" if regimes else
                      "eleonorabjornberg/repo-market-liquidity#77" if interaction else "eleonorabjornberg/repo-market-liquidity#70"),
        "tier": "development",
        "not_a_verdict": "Development evidence only (measurement-protocol.md section 1; repo-market-model#640). It confirms nothing.",
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "panel": {"version": PANEL_VERSION, "sha256": manifest["sha256"], "rows": len(rows),
                  "first": dates[0].isoformat(), "last": dates[-1].isoformat()},
        "last_day_read": dates[-1].isoformat(),
        "episode_source": {"onsets": "repo_model.onset.onset_flags", "cross_check": "held",
                           "cross_checked_with": "repo_model.pressure.onsets at +5 bp"},
        "settings": {
            "drivers": list(drivers), "baseline_days": attribution.BASELINE_DAYS,
            "window_days": attribution.WINDOW_DAYS, "seed": SEED, "draws": draws, "level": attribution.LEVEL,
            "block_length": attribution.BLOCK_LENGTH, "placebo_windows": attribution.PLACEBO_WINDOWS,
            "null_draws": null_draws, "null_quantile": null.quantile, "report_days": REPORT_DAYS,
            "decision_time": DECISION_TIME.isoformat(), "residual_bar": attribution.RESIDUAL_BAR,
            "regime_break_bn": ON_RRP_DEPLETION_BREAK_BN, "count_interval": f"Wilson, {INTERVAL_LEVEL:.0%}",
        },
        "null": {
            "construction": "N1: the driver-free spread, resampled by the stationary bootstrap, picked with the parent's onset rule",
            "statistic": "explained share", "quantile": null.quantile, "bar": null.bar, "draws": null.draws,
            "episodes": null.episodes,
            "explained_percentiles": {str(q): attribution._percentile(ranked, q) for q in (0.5, 0.9, 0.95, 0.99)},
        },
        "summary": summarise(entries),
        "episodes": entries,
    }
    if interaction:
        out["sensitivity"] = {
            "on_rrp_term": f"on_rrp x 1(on_rrp < {ON_RRP_DEPLETION_BREAK_BN} bn)", "regime_break_bn": ON_RRP_DEPLETION_BREAK_BN,
            "replaces": "the ON RRP window change", "reported_only": "the decided driver set and the published outcome do not change",
        }
    if regimes:
        out["sensitivity"] = {
            "on_rrp_terms": [f"on_rrp window change x 1(baseline mean on_rrp < {ON_RRP_DEPLETION_BREAK_BN} bn)",
                             f"on_rrp window change x 1(baseline mean on_rrp >= {ON_RRP_DEPLETION_BREAK_BN} bn)"],
            "regime_break_bn": ON_RRP_DEPLETION_BREAK_BN, "regime_of_a_window": "its baseline mean ON RRP",
            "replaces": "the ON RRP window change", "supersedes": "results/h10/sensitivity_onrrp_interaction.json",
            "reported_only": "the decided driver set and the published outcome do not change",
        }
    return out


# --------------------------------------------------------------------------- rendering


def _cell(share: dict) -> str:
    return f"{share['point']:.3f} [{share['low']:.3f}, {share['high']:.3f}]"


def table_markdown(record: dict) -> str:
    """The per-episode tables, rendered from the record alone: intervals lead, the point share after them."""
    names = list(DRIVERS_WITH_ON_RRP)
    head = ["Onset", "Rise (bp)", "Regime", "Quarter-end"] + names + ["Residual", "Explained", "Above reserves alone",
                                                                          "Placebo ≥ episode", "Under bar", "Beats null"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    fixed = ["| Onset | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for e in record["episodes"]:
        base = [e["onset"], "" if e["rise_bp"] is None else f"{e['rise_bp']:.2f}", e["regime"], "yes" if e["quarter_end"] else "no"]
        if e["status"] != "attributed":
            note = f"not attributable: {e['reason']}"
            lines.append("| " + " | ".join(base + [note] + [""] * (len(head) - len(base) - 1)) + " |")
            fixed.append(f"| {e['onset']} | " + " | ".join([note] + [""] * (len(names) - 1)) + " |")
            continue
        placebo = e["placebo"]["share_at_or_above"]
        row = base + [_cell(e["shares"][n]) for n in names] + [
            _cell(e["residual"]), f"{e['explained_share']:.3f}",
            "" if e["explained_above_reserves"] is None else f"{e['explained_above_reserves']:.3f}",
            "n/a" if placebo is None else f"{placebo:.2f} of {e['placebo']['attributed']}",
            "yes" if e["under_bar"] else "no", "yes" if e["beats_null"] else "no"]
        lines.append("| " + " | ".join(row) + " |")
        fixed.append(f"| {e['onset']} | " + " | ".join(f"{e['fixed_shares'][n]:.3f}" for n in names) + " |")
    return ("\n".join(lines) + "\n\nFixed-coefficient shares, beside the Shapley shares above (reported only; no outcome rule reads them):\n\n"
            + "\n".join(fixed) + "\n")


def _count_row(label: str, group: dict) -> str:
    cells = [label, str(group["episodes"])]
    for key in COUNTS:
        if group["intervals"] is None:
            cells.append(str(group[key]))
        else:
            low, high = group["intervals"][key]
            cells.append(f"{group[key]} ({low:.0%} to {high:.0%})")
    cells.append(str(group["not_attributable"]))
    return "| " + " | ".join(cells) + " |"


def summary_markdown(record: dict) -> str:
    """The outcome rule's counts and the two splits, rendered from the record alone."""
    s = record["summary"]
    head = ("| Group | Episodes | Under the residual bar | Beats the null | Both (counted) | Not attributable |\n"
            "|---|---|---|---|---|---|")
    rows = [_count_row("All development onsets", s)]
    for name in REGIMES:
        rows.append(_count_row(f"ON RRP {name}", s["splits"]["regime"][name]))
    for name in DAY_TYPES:
        rows.append(_count_row("Quarter-end onsets" if name == "quarter-end" else "Other onsets", s["splits"]["day_type"][name]))
    return head + "\n" + "\n".join(rows) + "\n"


# --------------------------------------------------------------------------- the 2 bp placebo floor (#85)


def placebo_floor_record(rows, development_record: dict, manifest: dict) -> dict:
    """The placebo comparison with and without the 2 bp floor, as a new development record. Re-runs only the placebo, at
    the published record's pin, seeds and episodes; nothing else is re-fitted, and the published record is not touched.

    Raises:
        ValueError: the placebo rebuilt without the floor is not the published record's.
    """
    dates = [row.date for row in rows]
    series = attribution.series_from_rows(rows, DRIVERS_WITH_ON_RRP)
    onsets = attribution.cross_check_onsets(rows)
    if [dates[i].isoformat() for i in onsets] != [e["onset"] for e in development_record["episodes"]]:
        raise ValueError("the onsets are not the published record's")
    placebo = attribution.placebo_starts(series, onsets, attribution.PLACEBO_WINDOWS, SEED)
    episodes = []
    for start, published in zip(onsets, development_record["episodes"]):
        entry = {"onset": published["onset"], "status": published["status"]}
        if published["status"] == "attributed":
            windows = [attribution.point_attribution(series, s, drivers=DRIVERS_WITH_ON_RRP) for s in placebo[start]]
            entry["explained_share"] = published["explained_share"]
            entry["unfloored"] = placebo_summary(windows, published["explained_share"])
            if entry["unfloored"] != published["placebo"]:
                raise ValueError(f"the placebo of {published['onset']} does not reproduce the published record's")
            entry["floored"] = floored_placebo_summary(windows, published["explained_share"])
        episodes.append(entry)
    attributed = [e for e in episodes if e["status"] == "attributed"]

    def gap(name):
        return median_interval([e["explained_share"] - e[name]["median_explained"] for e in attributed
                                if e[name]["median_explained"] is not None])

    settings = development_record["settings"]
    return {
        "record": "H10 step 3 amendment: the placebo comparison with and without a 2 bp placebo rise floor",
        "directive": "eleonorabjornberg/repo-market-liquidity#85",
        "tier": "development",
        "not_a_verdict": "Development evidence only (measurement-protocol.md section 1; repo-market-model#640). It confirms nothing.",
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "panel": development_record["panel"],
        "last_day_read": dates[-1].isoformat(),
        "source_record": {"path": "results/h10/development.json", "sha256": hashlib.sha256(RECORD.read_bytes()).hexdigest()},
        "settings": {**{k: settings[k] for k in ("seed", "placebo_windows", "baseline_days", "window_days", "drivers")},
                     "placebo_rise_floor_bp": attribution.PLACEBO_RISE_FLOOR_BP},
        "readings": {
            "unfloored": {"windows": sum(e["unfloored"]["windows"] for e in attributed),
                          "attributed_windows": sum(e["unfloored"]["attributed"] for e in attributed),
                          "median_placebo_gap": gap("unfloored")},
            "floored": {"windows": sum(e["floored"]["windows"] for e in attributed),
                        "windows_excluded": sum(e["floored"]["excluded"] for e in attributed),
                        "attributed_windows": sum(e["floored"]["attributed"] for e in attributed),
                        "median_placebo_gap": gap("floored")},
        },
        "episodes": episodes,
    }
