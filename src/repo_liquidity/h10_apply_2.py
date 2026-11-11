"""H10's second declaration, step 2: the nine-driver development attribution (#209; `docs/decisions/h10-method-2.md`).

The method is the registered one (`docs/decisions/h10-method.md`, `attribution`, `h10_apply`) with the second declaration's
nine drivers (`h10_drivers_2.DRIVERS_2`) in one fit, read from Phase 3 panel version 6, reported at 11 panel days
(`h10_drivers_2.REPORT_DAYS_2`) with the 30 June 2027 break applied (`h10_drivers_2.attribute_2`). It runs **beside** the
registered method and edits none of it: this module imports `attribution`, `h10_apply` and `h10_drivers_2` and changes none, is not
in `h10_live.METHOD_FILES`, and the assembly refuses to run unless `h10_live.method_digest()` is still the registered digest.

**Development evidence, never a verdict** (`docs/decisions/measurement-protocol.md` section 1). Nothing here is registered, adopted
or scored on a locked day; the rows are the panel's to the parent's development end.

**A long run in independent pieces** (the long-run skill). 512 subsets on each of 10,000 bootstrap draws, for 31 episodes, and a
1,000-draw selection null: hours on one core. The run is split into one file per episode and one for the null
(`run_pieces`); a piece that exists with the same settings is skipped, so a lost piece costs only itself, and `assemble` scores only
the pieces that exist and writes the record only when every piece does. Every piece stamps the commit it ran at and whether the
tree was modified; the record is assembled only from pieces of one clean commit (publish rule: nothing that decides a figure
changes between the pieces and the record).

Standard library only.
"""

from __future__ import annotations

import json
import multiprocessing
import platform
import statistics
import subprocess
from datetime import date
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, attribution, h10_apply, h10_drivers_2 as d2, h10_live, h10_registration
from repo_liquidity.attribution import SEED

ROOT = Path(__file__).resolve().parents[2]
#: The version of the panel the second declaration reads (`panel.MANIFESTS[6]`).
PANEL_VERSION_2 = 6
RECORD = ROOT / "results" / "h10" / "development_2.json"
PIECES_DIR = ROOT / "results" / "h10" / "method2"
#: A smoke run writes here, which no record is assembled from, and which is not tracked.
SMOKE_DIR = ROOT / "results" / "h10" / "method2_smoke"
PAGE = ROOT / "docs" / "research" / "h10-method2-development-table.md"
DIRECTIVE = "eleonorabjornberg/repo-market-liquidity#209"
#: A residual share is compared with the registered record's to this tolerance (the five-driver reproduction check).
REPRODUCTION_TOLERANCE = 1e-9

#: How each driver is shown (`docs/decisions/h10-method-2.md` section 1, "Labelling"; data-meaning row 8): fails to deliver is a
#: **collateral** driver, kept on its own axis; every other driver is a cash-side or a calendar one. The share of fails is not read
#: as cash scarcity.
CALENDAR = "calendar"
CASH_SIDE = "cash-side"
COLLATERAL = "collateral"
DRIVER_LABELS: Mapping[str, str] = {
    "treasury_settlement": CALENDAR, "tga": CASH_SIDE, "reserve_balances": CASH_SIDE, "quarter_end": CALENDAR,
    "on_rrp": CASH_SIDE, "facility_material_use": CASH_SIDE, "sofr_volume": CASH_SIDE, "sofr_p99_p1_bp": CASH_SIDE,
    d2.FAILS: COLLATERAL,
}
REGISTERED_FIVE = attribution.DRIVERS_WITH_ON_RRP


def label(name: str) -> str:
    """The driver's name with its axis, for every table and page that shows it."""
    return f"{name} ({DRIVER_LABELS[name]})"


# --------------------------------------------------------------------------- provenance and settings


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True, text=True).stdout


def provenance(ignore: Sequence[str] = ("results/h10/method2", "results/h10/method2_smoke")) -> dict:
    """This repository's commit and whether its tree was modified (the publish rule), and where it ran. A path under `ignore`
    (the pieces themselves) does not count as a modification."""
    dirty = [line for line in _git("status", "--porcelain").splitlines()
             if not any(line[3:].startswith(prefix) for prefix in ignore)]
    return {"repo_commit": _git("rev-parse", "HEAD").strip(), "tree_modified": bool(dirty),
            "python": platform.python_version(), "platform": platform.platform()}


def run_settings(draws: int, null_draws: int, *, smoke: bool) -> dict:
    """What a piece was run with. Pieces with different settings are never assembled together."""
    return {
        "drivers": list(d2.DRIVERS_2), "baseline_days": attribution.BASELINE_DAYS, "window_days": attribution.WINDOW_DAYS,
        "seed": SEED, "draws": draws, "null_draws": null_draws, "level": attribution.LEVEL,
        "block_length": attribution.BLOCK_LENGTH, "placebo_windows": attribution.PLACEBO_WINDOWS,
        "placebo_rise_floor_bp": attribution.PLACEBO_RISE_FLOOR_BP, "null_quantile": attribution.NULL_QUANTILE,
        "report_days": d2.REPORT_DAYS_2, "decision_time": h10_apply.DECISION_TIME.isoformat(),
        "residual_bar": attribution.RESIDUAL_BAR, "break_date": d2.BREAK_DATE.isoformat(), "smoke": smoke,
    }


# --------------------------------------------------------------------------- one episode, and the null


def five_driver_point(series, start: int) -> dict:
    """The registered method's five drivers' point attribution of the same window on the same series, for the comparison."""
    result = attribution.point_attribution(series, start, drivers=REGISTERED_FIVE)
    return {"status": result.status, "reason": result.reason, "residual_share": result.residual_share,
            "explained_share": result.explained_share}


def episode_entry(series, dates: Sequence[date], rule, start: int, *, draws: int, placebo_windows: Sequence[int],
                  raw_on_rrp: Sequence[float], drivers: Sequence[str] = d2.DRIVERS_2) -> dict:
    """One episode under the second declaration: its attribution through `attribute_2` (the break, the 11-day report window and
    the parent's as-of rule), the benchmark, and the placebo read unfloored and floored at 2 bp. A window that is not attributable is
    returned with its reason, never dropped; one not public at the report day raises `LookAheadError`."""
    from repo_model.contract import ON_RRP_DEPLETION_BREAK_BN

    result = d2.attribute_2(series, start, dates=dates, rule=rule, drivers=drivers, draws=draws, seed=SEED)
    report = start + d2.REPORT_DAYS_2
    entry = {
        "onset": dates[start].isoformat(), "index": start,
        "report_day": dates[report].isoformat() if report < len(dates) else None,
        "status": result.status, "reason": result.reason, "rise_bp": result.rise_bp,
        "regime": "depleted" if raw_on_rrp[start] < ON_RRP_DEPLETION_BREAK_BN else "abundant",
        "quarter_end": bool(series["quarter_end"][start]), "on_rrp_at_onset": raw_on_rrp[start],
        "registered_five": five_driver_point(series, start),
    }
    if result.status != "attributed":
        return entry
    placebo = [attribution.point_attribution(series, s, drivers=drivers) for s in placebo_windows]
    entry.update(
        shares={name: {"point": result.shares[name], "low": result.intervals[name][0], "high": result.intervals[name][1]}
                for name in drivers},
        fixed_shares=dict(result.fixed_shares),
        residual={"point": result.residual_share, "low": result.residual_interval[0], "high": result.residual_interval[1]},
        explained_share=result.explained_share,
        explained_above_reserves=attribution.explained_above_reserves(series, start, drivers),
        placebo=h10_apply.placebo_summary(placebo, result.explained_share),
        placebo_floored=h10_apply.floored_placebo_summary(placebo, result.explained_share),
        unusable_draws=result.unusable_draws,
    )
    return entry


def null_entry(series, *, null_draws: int, drivers: Sequence[str] = d2.DRIVERS_2) -> dict:
    """The selection null (N1, as in the registered method) over the nine drivers: its bar and its percentiles."""
    null = attribution.selection_null(series, drivers, draws=null_draws, seed=SEED)
    ranked = list(null.explained)
    return {"construction": "N1: the driver-free spread, resampled by the stationary bootstrap, picked with the parent's onset rule",
            "statistic": "explained share", "quantile": null.quantile, "bar": null.bar, "draws": null.draws,
            "episodes": null.episodes,
            "explained_percentiles": {str(q): attribution._percentile(ranked, q) for q in (0.5, 0.9, 0.95, 0.99)}}


# --------------------------------------------------------------------------- the pieces

_STATE: dict = {}


def piece_name(onset: Optional[str]) -> str:
    return "null.json" if onset is None else f"episode-{onset}.json"


def _write(path: Path, piece: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(piece, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _same_run(piece: dict, settings: dict, panel_sha256: str) -> bool:
    return piece.get("settings") == settings and piece.get("panel_sha256") == panel_sha256


def _work(start: Optional[int]) -> str:
    """One piece, in a worker: an episode (by row index), or the null (None). Returns the piece's file name."""
    s = _STATE
    if start is None:
        body = {"piece": "null", "null": null_entry(s["series"], null_draws=s["settings"]["null_draws"])}
        name = piece_name(None)
    else:
        with d2.rule_2() as rule:
            entry = episode_entry(s["series"], s["dates"], rule, start, draws=s["settings"]["draws"],
                                  placebo_windows=s["placebo"][start], raw_on_rrp=s["raw_on_rrp"])
        body = {"piece": "episode", "episode": entry}
        name = piece_name(entry["onset"])
    _write(s["out"] / name, {**body, "settings": s["settings"], "panel_sha256": s["panel_sha256"],
                              "provenance": s["provenance"]})
    return name


def load_inputs(version: int = PANEL_VERSION_2):
    """The panel rows to the development end, the series of the nine drivers (the break masked), the onsets and the placebo
    windows, and the panel's manifest. The onsets and the placebo windows are the registered record's own, from the same rule."""
    rows, manifest = h10_apply.load_development(version)
    dates = [row.date for row in rows]
    series = attribution.series_from_rows(rows, d2.DRIVERS_2)
    raw_on_rrp = list(series[attribution.ON_RRP])
    series = d2.mask_across_break(series, dates)
    onsets = attribution.cross_check_onsets(rows)
    placebo = attribution.placebo_starts(series, onsets, attribution.PLACEBO_WINDOWS, SEED)
    return rows, dates, series, raw_on_rrp, onsets, placebo, manifest


def run_pieces(out: Path, *, draws: int = attribution.DRAWS, null_draws: int = attribution.NULL_DRAWS, workers: int = 1,
               limit: Optional[int] = None, smoke: bool = False, require_clean: bool = True) -> dict:
    """Run every piece that does not exist under `out` with these settings, and return what was done.

    `limit` keeps the first `limit` episodes (a smoke run; it also skips the null unless `null_draws` is positive). A full run
    (`smoke` false) refuses a tree with uncommitted changes outside the pieces, so that a piece names a commit it was run at.

    Raises:
        ValueError: a full run with a modified tree, or a smoke run at the full settings' directory.
    """
    prov = provenance()
    if not smoke and require_clean and prov["tree_modified"]:
        raise ValueError("a full run is made from a clean tree: commit first, so that its pieces name the commit they ran at")
    if smoke and out.resolve() == PIECES_DIR.resolve():
        raise ValueError("a smoke run does not write to the directory the record is assembled from")
    rows, dates, series, raw_on_rrp, onsets, placebo, manifest = load_inputs()
    settings = run_settings(draws, null_draws, smoke=smoke)
    chosen = onsets if limit is None else onsets[:limit]
    wanted: List[Optional[int]] = list(chosen) + ([None] if null_draws > 0 else [])
    done, todo = [], []
    for start in wanted:
        path = out / piece_name(None if start is None else dates[start].isoformat())
        if path.is_file() and _same_run(json.loads(path.read_text(encoding="utf-8")), settings, manifest["sha256"]):
            done.append(path.name)
        else:
            todo.append(start)
    _STATE.update(series=series, dates=dates, placebo=placebo, raw_on_rrp=raw_on_rrp, settings=settings, out=out,
                  panel_sha256=manifest["sha256"], provenance=prov)
    try:
        if workers > 1 and todo:
            with multiprocessing.get_context("fork").Pool(workers) as pool:
                written = list(pool.imap_unordered(_work, todo, chunksize=1))
        else:
            written = [_work(start) for start in todo]
    finally:
        _STATE.clear()
    return {"skipped_existing": sorted(done), "written": sorted(written), "panel_sha256": manifest["sha256"],
            "episodes": len(onsets), "provenance": prov}


# --------------------------------------------------------------------------- scoring the pieces that exist


def read_pieces(directory: Path) -> Dict[str, dict]:
    """Every piece file under `directory`, by file name."""
    return {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))}


def missing_pieces(directory: Path, onsets: Sequence[str]) -> List[str]:
    """The piece files an assembly needs and `directory` lacks."""
    have = set(read_pieces(directory)) if directory.is_dir() else set()
    return [name for name in [piece_name(None)] + [piece_name(o) for o in onsets] if name not in have]


def _paired(entries: Sequence[dict], registered_by_onset: Mapping[str, dict]) -> dict:
    """The residual share under nine drivers against the registered five, episode by episode, with intervals."""
    attributed = [e for e in entries if e["status"] == "attributed"]
    rows = []
    for e in attributed:
        five = registered_by_onset[e["onset"]]
        if five["status"] != "attributed":
            continue
        rows.append({"onset": e["onset"], "regime": e["regime"], "quarter_end": e["quarter_end"],
                     "residual_nine": e["residual"]["point"], "residual_five": five["residual"]["point"]})

    def block(sub: Sequence[dict]) -> dict:
        diffs = [r["residual_nine"] - r["residual_five"] for r in sub]
        n = len(sub)
        return {
            "episodes": n,
            "median_residual_nine": h10_apply.median_interval([r["residual_nine"] for r in sub]),
            "median_residual_five": h10_apply.median_interval([r["residual_five"] for r in sub]),
            "median_paired_difference_nine_less_five": h10_apply.median_interval(diffs),
            "nine_lower_than_five": sum(1 for d in diffs if d < 0),
            "under_bar_nine": sum(1 for r in sub if abs(r["residual_nine"]) < attribution.RESIDUAL_BAR),
            "under_bar_five": sum(1 for r in sub if abs(r["residual_five"]) < attribution.RESIDUAL_BAR),
            "intervals": None if n == 0 else {
                "under_bar_nine": h10_apply.wilson(sum(1 for r in sub if abs(r["residual_nine"]) < attribution.RESIDUAL_BAR), n),
                "under_bar_five": h10_apply.wilson(sum(1 for r in sub if abs(r["residual_five"]) < attribution.RESIDUAL_BAR), n)},
        }

    return {
        "note": ("Paired by episode: the same 31 windows, the registered five drivers' residual share (the published development "
                 "record, unchanged) against the nine drivers' (this record). Intervals are the method's: a distribution-free "
                 "90% interval on a median, a Wilson 90% interval on a count of episodes, which treat the episodes as independent "
                 "and so are, if anything, too narrow."),
        "all": block(rows),
        "regime": {name: block([r for r in rows if r["regime"] == name]) for name in h10_apply.REGIMES},
        "day_type": {"quarter-end": block([r for r in rows if r["quarter_end"]]),
                     "other": block([r for r in rows if not r["quarter_end"]])},
        "episodes": rows,
    }


def check_reproduces_registered(entries: Sequence[dict], registered: dict) -> float:
    """The five drivers' point residual of each episode, recomputed on panel version 6, equals the registered record's.

    Returns the largest absolute difference.

    Raises:
        ValueError: the episodes are not the registered record's, or a residual differs by more than `REPRODUCTION_TOLERANCE`
            (the comparison would not be like for like).
    """
    if [e["onset"] for e in entries] != [e["onset"] for e in registered["episodes"]]:
        raise ValueError("the episodes are not the registered development record's")
    worst = 0.0
    for e, r in zip(entries, registered["episodes"]):
        five = e["registered_five"]
        if five["status"] != r["status"]:
            raise ValueError(f"{e['onset']}: the five drivers read {five['status']!r} here, {r['status']!r} in the registered record")
        if r["status"] == "attributed":
            worst = max(worst, abs(five["residual_share"] - r["residual"]["point"]))
    if worst > REPRODUCTION_TOLERANCE:
        raise ValueError(f"the five drivers' residual shares differ from the registered record's by {worst}")
    return worst


def build_record(directory: Path, *, registered_path: Path = h10_apply.RECORD, allow_smoke: bool = False) -> dict:
    """The development record of the second declaration, from the pieces under `directory`.

    Scores only pieces that exist and refuses to write a record unless they are all there, from one run (the same settings, panel,
    commit, a clean tree) and the registered method is untouched.

    Raises:
        ValueError: a piece is missing; the pieces are of different runs, commits or panels, or of a modified tree; the run is a
            smoke run (unless `allow_smoke`); the registered method's digest moved; or the comparison is not like for like.
    """
    if h10_live.method_digest() != h10_registration.REGISTERED_DIGEST:
        raise ValueError("the registered method's digest moved; this declaration runs beside it, never in place of it")
    registered = json.loads(registered_path.read_text(encoding="utf-8"))
    onsets = [e["onset"] for e in registered["episodes"]]
    absent = missing_pieces(directory, onsets)
    if absent:
        raise ValueError(f"{len(absent)} piece(s) missing, no record is assembled: {', '.join(absent)}")
    pieces = read_pieces(directory)
    first = pieces[piece_name(None)]
    for name, piece in pieces.items():
        if piece["settings"] != first["settings"] or piece["panel_sha256"] != first["panel_sha256"]:
            raise ValueError(f"{name} was run with other settings or on another panel than null.json")
        if piece["provenance"]["repo_commit"] != first["provenance"]["repo_commit"]:
            raise ValueError(f"{name} ran at another commit than null.json")
    settings = first["settings"]
    if settings["smoke"] and not allow_smoke:
        raise ValueError("these pieces are a smoke run; it shows that the code path works and is never a record")
    if first["provenance"]["tree_modified"] and not settings["smoke"]:
        raise ValueError("the pieces were run from a modified tree")
    entries = [pieces[piece_name(o)]["episode"] for o in onsets]
    null = first["null"]
    worst = check_reproduces_registered(entries, registered)
    for entry in entries:
        attributed = entry["status"] == "attributed"
        entry["under_bar"] = attributed and abs(entry["residual"]["point"]) < attribution.RESIDUAL_BAR
        entry["beats_null"] = attributed and entry["explained_share"] > null["bar"]
        entry["counted"] = entry["under_bar"] and entry["beats_null"]
    registered_by_onset = {e["onset"]: e for e in registered["episodes"]}
    last_day = max(date.fromisoformat(e["report_day"]) for e in entries if e["report_day"])
    return {
        "record": "H10 second declaration, step 2: the nine-driver development attribution, beside the registered method",
        "directive": DIRECTIVE,
        "tier": "development",
        "smoke": settings["smoke"],
        "not_a_verdict": "Development evidence only (measurement-protocol.md section 1; repo-market-model#640). It confirms nothing, "
                         "adopts nothing and registers nothing.",
        "declaration": "docs/decisions/h10-method-2.md",
        "parent_commit": PARENT_COMMIT,
        "parent_panel_sha256": PANEL_SHA256,
        "registered_method_digest": h10_registration.REGISTERED_DIGEST,
        "panel": {"version": PANEL_VERSION_2, "sha256": first["panel_sha256"]},
        "provenance": first["provenance"],
        "last_report_day_read": last_day.isoformat(),
        "settings": settings,
        "driver_labels": dict(DRIVER_LABELS),
        "null": null,
        "summary": h10_apply.summarise(entries),
        "comparison": {
            "registered_record": {"path": "results/h10/development.json",
                                  "sha256": _sha256(registered_path),
                                  "panel_version": registered["panel"]["version"],
                                  "summary": {k: registered["summary"][k] for k in ("episodes", "under_bar", "beats_null", "counted",
                                                                                   "not_attributable", "outcome")}},
            "five_driver_reproduction_max_abs_difference": worst,
            "paired_residual": _paired(entries, registered_by_onset),
        },
        "not_attributable": [{"onset": e["onset"], "reason": e["reason"],
                              "registered_status": registered_by_onset[e["onset"]]["status"]}
                             for e in entries if e["status"] != "attributed"],
        "report_window": {
            "report_days": d2.REPORT_DAYS_2, "registered_report_days": h10_apply.REPORT_DAYS,
            "break_date": d2.BREAK_DATE.isoformat(),
            "development_episodes_meeting_the_break": 0,
            "statement": (f"No development episode meets the {d2.BREAK_DATE.isoformat()} break: development ends at the parent's "
                          f"development end, long before it, so `sofr_volume` and `sofr_p99_p1_bp` are read on every episode and "
                          f"the break's refusal (`h10_drivers_2.break_refusal`) applies to none. The 11-panel-day report window is a "
                          f"property of this declaration (docs/decisions/h10-method-2.md section 5, fails public 11 panel days "
                          f"after an onset); it is not tested on development data."),
        },
        "episodes": entries,
    }


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def meets_break(dates: Sequence[date], onsets: Sequence[int]) -> int:
    """How many of `onsets` have a window that touches the 30 June 2027 break (none, on development data)."""
    return sum(1 for start in onsets if d2.touches_break(dates, start))


# --------------------------------------------------------------------------- rendering


def _cell(share: dict) -> str:
    return f"{share['point']:.3f} [{share['low']:.3f}, {share['high']:.3f}]"


def table_markdown(record: dict) -> str:
    """The per-episode table of the nine drivers, rendered from the record alone. Every driver is shown with its axis, and fails
    to deliver as a collateral driver (data-meaning row 8)."""
    names = list(record["settings"]["drivers"])
    head = (["Onset", "Rise (bp)", "Regime", "Quarter-end"] + [label(n) for n in names]
            + ["Residual", "Explained", "Above reserves alone", "Placebo ≥ episode (unfloored)", "Placebo ≥ episode (floored, 2 bp)",
               "Under bar", "Beats null"])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for e in record["episodes"]:
        base = [e["onset"], "" if e["rise_bp"] is None else f"{e['rise_bp']:.2f}", e["regime"], "yes" if e["quarter_end"] else "no"]
        if e["status"] != "attributed":
            lines.append("| " + " | ".join(base + [f"not attributable: {e['reason']}"] + [""] * (len(head) - len(base) - 1)) + " |")
            continue

        def placebo(block: dict) -> str:
            value = block["share_at_or_above"]
            return "n/a" if value is None else f"{value:.2f} of {block['attributed']}"

        row = base + [_cell(e["shares"][n]) for n in names] + [
            _cell(e["residual"]), f"{e['explained_share']:.3f}",
            "" if e["explained_above_reserves"] is None else f"{e['explained_above_reserves']:.3f}",
            placebo(e["placebo"]), placebo(e["placebo_floored"]), "yes" if e["under_bar"] else "no",
            "yes" if e["beats_null"] else "no"]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def _median_cell(block: dict) -> str:
    low, high = block["interval"]
    return f"{block['median']:.2f} ({low:.2f} to {high:.2f})"


def _count_cell(count: int, total: int, interval) -> str:
    return f"{count} of {total}" if interval is None else f"{count} of {total} ({interval[0]:.0%} to {interval[1]:.0%})"


def comparison_markdown(record: dict) -> str:
    """The residual share under nine drivers against five, paired by episode, with the splits, rendered from the record alone."""
    paired = record["comparison"]["paired_residual"]
    head = ("| Group | Episodes | Median residual, five drivers | Median residual, nine drivers | Median paired difference (nine less five) "
            "| Nine lower than five | Under the bar, five | Under the bar, nine |\n|---|---|---|---|---|---|---|---|")
    groups = [("All development onsets", paired["all"])]
    groups += [(f"ON RRP {name}", paired["regime"][name]) for name in h10_apply.REGIMES]
    groups += [("Quarter-end onsets" if name == "quarter-end" else "Other onsets", paired["day_type"][name]) for name in h10_apply.DAY_TYPES]
    rows = []
    for name, b in groups:
        if b["episodes"] == 0:
            rows.append(f"| {name} | 0 | | | | | | |")
            continue
        iv = b["intervals"]
        rows.append("| " + " | ".join([
            name, str(b["episodes"]), _median_cell(b["median_residual_five"]), _median_cell(b["median_residual_nine"]),
            _median_cell(b["median_paired_difference_nine_less_five"]), f"{b['nine_lower_than_five']} of {b['episodes']}",
            _count_cell(b["under_bar_five"], b["episodes"], iv["under_bar_five"]),
            _count_cell(b["under_bar_nine"], b["episodes"], iv["under_bar_nine"])]) + " |")
    return head + "\n" + "\n".join(rows) + "\n"


def render_markdown(record: dict, registered: dict) -> str:
    """The development page of the second declaration, rendered from its record and the registered record, which is shown
    unchanged beside it. Nothing is transcribed by hand."""
    s = record["summary"]
    c = record["comparison"]
    nine_lower = c["paired_residual"]["all"]
    prov = record["provenance"]
    lines = [
        "# H10, second declaration, step 2: the nine-driver development attribution",
        "",
        f"<!-- generated: scripts/emit_h10_method2_table.py from results/h10/development_2.json and results/h10/development.json; never hand-edited -->",
        "",
        "**Serves:** H10's second declaration (`docs/decisions/h10-method-2.md`), step 2, development. Directive #209. It runs **beside** "
        "the registered H10 method and never in place of it. **Development evidence, not a verdict** "
        "(`docs/decisions/measurement-protocol.md` section 1): under the 2 November freeze nothing is adopted, and nothing is registered.",
        "",
        "## Header",
        "",
        f"- **Parent pin:** `{record['parent_commit']}`; the parent's published panel digest `{record['parent_panel_sha256']}`.",
        f"- **Panel:** version {record['panel']['version']}, digest `{record['panel']['sha256']}`.",
        f"- **Seeds and draws:** seed {record['settings']['seed']}; {record['settings']['draws']} bootstrap draws per episode; the selection-aware "
        f"null {record['settings']['null_draws']} draws at the {record['settings']['null_quantile']:.0%} quantile (bar {record['null']['bar']:.3f}); "
        f"{record['settings']['placebo_windows']} placebo windows per episode, read unfloored and floored at {record['settings']['placebo_rise_floor_bp']:g} bp.",
        f"- **Report window:** {record['settings']['report_days']} panel days (the registered method's is {record['report_window']['registered_report_days']}).",
        f"- **Run:** repository commit `{prov['repo_commit']}`, tree modified: {'yes' if prov['tree_modified'] else 'no'}; Python {prov['python']}.",
        f"- **The registered method's digest** is unchanged: `{record['registered_method_digest']}`.",
        f"- **The registered record, read byte for byte:** `results/h10/development.json`, sha256 `{c['registered_record']['sha256']}`.",
        "",
        "## What the nine-driver table shows",
        "",
        f"Over the {s['episodes']} development onsets: {s['under_bar']} under the residual bar, {s['beats_null']} beating the null, "
        f"{s['counted']} both, with {s['not_attributable']} not attributable. The registered five drivers gave "
        f"{c['registered_record']['summary']['under_bar']} under the bar, {c['registered_record']['summary']['beats_null']} beating the null, "
        f"{c['registered_record']['summary']['counted']} both. Under the plan's rule the nine-driver table reads **{s['outcome']}** "
        f"(the registered five: **{c['registered_record']['summary']['outcome']}**). This describes the development table. It is not a verdict.",
        "",
        h10_apply.summary_markdown(record),
        "",
        "Progress markers (each over the attributed episodes, with a distribution-free 90% interval on the median):",
        "",
        f"- median residual share: {_median_cell(s['markers']['median_residual_share'])}, n = {s['markers']['median_residual_share']['n']};",
        f"- explained share above reserves alone: {_median_cell(s['markers']['median_explained_above_reserves'])}, n = {s['markers']['median_explained_above_reserves']['n']};",
        f"- placebo gap, the episode's explained share less its placebo windows' median: {_median_cell(s['markers']['median_placebo_gap'])}, n = {s['markers']['median_placebo_gap']['n']}.",
        "",
        "## The residual share under nine drivers against five",
        "",
        "The registered record's \"residual dominates\" (`docs/stages/h10-step2.md`) is the motivation for the nine. Paired by episode, "
        f"the nine drivers' residual share is lower than the five's in {nine_lower['nine_lower_than_five']} of {nine_lower['episodes']} episodes.",
        "",
        comparison_markdown(record),
        c["paired_residual"]["note"],
        "",
        f"The five drivers, refitted here on panel version {record['panel']['version']}, give the registered record's residual shares to "
        f"{c['five_driver_reproduction_max_abs_difference']:.1e} (largest absolute difference), so the comparison is like for like.",
        "",
        "## The episodes that are not attributable",
        "",
    ]
    if record["not_attributable"]:
        lines += ["| Onset | Reason | Registered method |", "|---|---|---|"]
        lines += [f"| {n['onset']} | {n['reason']} | {n['registered_status']} |" for n in record["not_attributable"]]
    else:
        lines.append("None: every development episode is attributed under the nine drivers.")
    lines += [
        "",
        "## Report window and the 30 June 2027 break",
        "",
        record["report_window"]["statement"],
        "",
        "## One row per episode, nine drivers",
        "",
        "Each driver is shown with its axis. **`pd_fails_deliver_ust` is a collateral driver** (data-meaning row 8): its share is not read as "
        "cash scarcity. Each Shapley share has its 90% interval first, the point share after it. \"Above reserves alone\" is the "
        "drivers' explained share less that of reserves alone. \"Placebo ≥ episode\" is the share of the episode's placebo windows "
        "(same length and day type, touching no episode) whose explained share is at least the episode's, with the number of attributable "
        "placebo windows, read unfloored and with windows whose rise is under 2 bp excluded.",
        "",
        table_markdown(record),
        "## The registered method's development table, unchanged",
        "",
        "Rendered from `results/h10/development.json`, which this step does not touch (five drivers, panel version "
        f"{registered['panel']['version']}).",
        "",
        h10_apply.summary_markdown(registered),
        "",
        h10_apply.table_markdown(registered),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_tracked() -> str:
    """The page for the tracked records."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    registered = json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))
    return render_markdown(record, registered)
