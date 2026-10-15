"""H10 step 3 (#77): the published development table, rendered from the records and never hand-written.

`docs/research/h10-development-table.md` is `render_tracked()`: the step 2 record (`results/h10/development.json`), byte for
byte, with the ON RRP interaction sensitivity (`results/h10/sensitivity_onrrp_interaction.json`) beside it. Nothing is
re-fitted or re-run here; every number comes from a record. **Development evidence, never a verdict**
(`docs/decisions/measurement-protocol.md` section 1). Registration of the frozen method is Eleonora's attested action
(plan, H10, "Registration"); this page only states the method record's digest so she has it. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional

from repo_liquidity import attribution, h10_apply

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "research" / "h10-development-table.md"
METHOD = ROOT / "docs" / "decisions" / "h10-method.md"
SENSITIVITY_FLAG = "sensitivity"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_comparable(development: dict, sensitivity: dict) -> None:
    if SENSITIVITY_FLAG not in sensitivity:
        raise ValueError("the second record is not marked as a sensitivity")
    if SENSITIVITY_FLAG in development:
        raise ValueError("the published record is itself a sensitivity")
    if [e["onset"] for e in development["episodes"]] != [e["onset"] for e in sensitivity["episodes"]]:
        raise ValueError("the sensitivity's episodes are not the published record's episodes")


def _counts(summary: dict) -> str:
    return (f"{summary['under_bar']} of {summary['episodes']} ({_pct(summary['intervals']['under_bar'])}) under the residual bar, "
            f"{summary['beats_null']} of {summary['episodes']} ({_pct(summary['intervals']['beats_null'])}) beating the null, "
            f"{summary['counted']} of {summary['episodes']} ({_pct(summary['intervals']['counted'])}) both")


def _pct(interval) -> str:
    return f"{interval[0]:.0%} to {interval[1]:.0%}"


def _marker(entry: dict) -> str:
    low, high = entry["interval"]
    return f"{entry['median']:.2f} (90% interval {low:.2f} to {high:.2f}, n = {entry['n']})"


def _differing(development: dict, sensitivity: dict) -> List[str]:
    rows = []
    for a, b in zip(development["episodes"], sensitivity["episodes"]):
        if (a["under_bar"], a["beats_null"], a["counted"]) == (b["under_bar"], b["beats_null"], b["counted"]):
            continue
        yes = lambda flag: "yes" if flag else "no"
        rows.append(f"| {a['onset']} | {a['residual']['point']:.3f} | {b['residual']['point']:.3f} | "
                    f"{yes(a['under_bar'])} / {yes(b['under_bar'])} | {yes(a['beats_null'])} / {yes(b['beats_null'])} |")
    return rows


def _sensitivity_table(development: dict, sensitivity: dict) -> str:
    head = ("| Onset | Regime | ON RRP share (published) | ON RRP share (interaction) | Residual (published) | Residual (interaction) "
            "| Explained (interaction) | Under bar | Beats null |\n|---|---|---|---|---|---|---|---|---|")
    lines = [head]
    for a, b in zip(development["episodes"], sensitivity["episodes"]):
        if b["status"] != "attributed" or a["status"] != "attributed":
            lines.append(f"| {a['onset']} | {a['regime']} | not attributable | | | | | | |")
            continue
        yes = lambda flag: "yes" if flag else "no"
        lines.append(
            f"| {a['onset']} | {a['regime']} | {h10_apply._cell(a['shares']['on_rrp'])} | {h10_apply._cell(b['shares']['on_rrp'])} | "
            f"{h10_apply._cell(a['residual'])} | {h10_apply._cell(b['residual'])} | {b['explained_share']:.3f} | "
            f"{yes(b['under_bar'])} | {yes(b['beats_null'])} |")
    return "\n".join(lines) + "\n"


#: The date of the note that the interaction sensitivity is superseded (finding #79, directive #86).
SUPERSEDED_ON = "15 October 2026"


def _regime_table(development: dict, regimes: dict) -> str:
    depleted, abundant = attribution.REGIME_TERMS
    head = ("| Onset | Regime | Depleted-term share | Abundant-term share | Residual (published) | Residual (regime terms) "
            "| Explained (regime terms) | Under bar | Beats null |\n|---|---|---|---|---|---|---|---|---|")
    lines = [head]
    yes = lambda flag: "yes" if flag else "no"
    for a, b in zip(development["episodes"], regimes["episodes"]):
        if b["status"] != "attributed" or a["status"] != "attributed":
            lines.append(f"| {a['onset']} | {a['regime']} | not attributable | | | | | | |")
            continue
        lines.append(
            f"| {a['onset']} | {a['regime']} | {h10_apply._cell(b['shares'][depleted])} | {h10_apply._cell(b['shares'][abundant])} | "
            f"{h10_apply._cell(a['residual'])} | {h10_apply._cell(b['residual'])} | {b['explained_share']:.3f} | "
            f"{yes(b['under_bar'])} | {yes(b['beats_null'])} |")
    return "\n".join(lines) + "\n"


def _regime_sections(development: dict, interaction: dict, regimes: dict) -> List[str]:
    """The sensitivity with two regime-specific terms, beside the published record (`results/h10/sensitivity_onrrp_regimes.json`)."""
    _check_comparable(development, regimes)
    if [e["onset"] for e in interaction["episodes"]] != [e["onset"] for e in regimes["episodes"]]:
        raise ValueError("the regime-term sensitivity's episodes are not the interaction sensitivity's episodes")
    d, i, r = development["summary"], interaction["summary"], regimes["summary"]
    abundant = r["splits"]["regime"]["abundant"]["episodes"]
    differing = _differing(development, regimes)
    out = [
        "## Sensitivity: ON RRP as two regime-specific terms",
        "",
        "**Reported only** (finding #79; her ruling of 14 October 2026; directive #86). The method record's decided driver set is "
        "unchanged, and this sensitivity does not change the published outcome above. Each window's regime is fixed by its "
        f"**baseline** mean ON RRP against the parent's `ON_RRP_DEPLETION_BREAK_BN` ({regimes['sensitivity']['regime_break_bn']} bn); "
        "ON RRP then enters as two drivers in place of its window change, "
        f"`{regimes['sensitivity']['on_rrp_terms'][0]}` and `{regimes['sensitivity']['on_rrp_terms'][1]}`, each with its own "
        "coefficient. A window that straddles the break keeps the sign of its change. Everything else (window, bootstrap, seeds, "
        "placebo, benchmark, null, outcome rule) is as in the published record. "
        f"The record is `results/h10/sensitivity_onrrp_regimes.json`; its null bar is {regimes['null']['bar']:.3f}.",
        "",
        f"What the sensitivity shows: {_counts(r)}, against {_counts(d)} in the published record and {_counts(i)} in the superseded "
        "interaction sensitivity. Labelled sensitivity; it is not a result.",
        "",
        f"**The abundant regime has {abundant} onsets**, so its coefficient rests on the fitting sample's abundant windows, not on "
        "the onsets.",
        "",
        h10_apply.summary_markdown(regimes),
        "Progress markers under the regime terms:",
        "",
        f"- median residual share: {_marker(r['markers']['median_residual_share'])};",
        f"- explained share above reserves alone: {_marker(r['markers']['median_explained_above_reserves'])};",
        f"- placebo gap: {_marker(r['markers']['median_placebo_gap'])}.",
        "",
        "### Episodes whose outcome differs from the published record",
        "",
    ]
    if differing:
        out += ["Published / regime terms in each outcome column.", "",
                "| Onset | Residual (published) | Residual (regime terms) | Under bar | Beats null |", "|---|---|---|---|---|", *differing]
    else:
        out.append("None: every episode has the same outcome under both.")
    out += ["", "### Per episode, beside the published figures", "", _regime_table(development, regimes)]
    return out


def render(development: dict, sensitivity: dict, *, development_sha256: str, method_sha256: str,
           regimes: Optional[dict] = None) -> str:
    """The page, from the records alone.

    With `regimes` (the sensitivity with two regime-specific terms, #86) the interaction sensitivity carries a dated note
    that this record supersedes it, and the page gains a section for the new record.

    Raises:
        ValueError: the second record is not a sensitivity, or does not cover the same episodes as the first.
    """
    _check_comparable(development, sensitivity)
    d, s = development["summary"], sensitivity["summary"]
    settings, panel = development["settings"], development["panel"]
    abundant = s["splits"]["regime"]["abundant"]["episodes"]
    differing = _differing(development, sensitivity)
    out = [
        "# H10: the development table",
        "",
        "<!-- generated: scripts/emit_h10_table.py from results/h10/development.json, "
        "results/h10/sensitivity_onrrp_interaction.json" + (" and results/h10/sensitivity_onrrp_regimes.json" if regimes is not None else "")
        + "; never hand-edited -->",
        "",
        "**Serves:** H10 (pressure episodes can be attributed to drivers), development step 3 of the plan "
        "(`docs/research/plan.md`). Directives #77 and #86. **Development evidence, not a verdict** "
        "(`docs/decisions/measurement-protocol.md` section 1; eleonorabjornberg/repo-market-model#640): it confirms nothing, "
        "and there is no registration. Registering the frozen method is Eleonora's attested action.",
        "",
        "## Header",
        "",
        f"- **Parent pin:** `{development['parent_commit']}`; the parent's published panel digest `{development['parent_panel_sha256']}`.",
        f"- **Panel:** version {panel['version']}, digest `{panel['sha256']}`, {panel['rows']} rows, {panel['first']} to {panel['last']} "
        f"(the last day read: {development['last_day_read']}).",
        f"- **Seeds and draws:** seed {settings['seed']}; {settings['draws']} bootstrap draws per episode; the selection-aware null "
        f"{settings['null_draws']} draws at the {settings['null_quantile']:.0%} quantile (bar {development['null']['bar']:.3f}); "
        f"{settings['placebo_windows']} placebo windows per episode.",
        f"- **Record read, byte for byte:** `results/h10/development.json`, sha256 `{development_sha256}` "
        f"(H10 step 2, #70, PR #73). It is not re-fitted or re-run for this page.",
        f"- **The method:** `docs/decisions/h10-method.md`, sha256 `{method_sha256}`. This is the digest to register; the commit is "
        "named in the pull request.",
        "",
        "## What the development table shows",
        "",
        f"Over the {d['episodes']} development onsets: {_counts(d)}. Intervals are Wilson 90% intervals on the share of episodes and "
        "treat the episodes as independent, which they are not quite (they cluster at quarter-ends and in 2018-19), so they are, "
        "if anything, too narrow.",
        "",
        f"Under the plan's rule (\"drivers named\" needs more than half the episodes) the table reads **{d['outcome']}**; "
        f"on the residual bar alone it reads **{d['under_bar_outcome']}**. This describes the development table. It is not a verdict.",
        "",
        h10_apply.summary_markdown(development),
        "Progress markers (each over the attributed episodes, with a distribution-free 90% interval on the median):",
        "",
        f"- median residual share: {_marker(d['markers']['median_residual_share'])};",
        f"- explained share above reserves alone: {_marker(d['markers']['median_explained_above_reserves'])};",
        f"- placebo gap, the episode's explained share less its placebo windows' median: {_marker(d['markers']['median_placebo_gap'])}.",
        "",
        "## One row per episode",
        "",
        "Each driver's Shapley share has its 90% interval first, the point share after the interval. \"Above reserves alone\" is the "
        "drivers' explained share less that of reserves alone. \"Placebo ≥ episode\" is the share of the episode's placebo windows "
        "(same length and day type, touching no episode) whose explained share is at least the episode's, with the number of "
        "attributable placebo windows.",
        "",
        h10_apply.table_markdown(development),
        "## Sensitivity: ON RRP as an interaction with the depleted regime",
        "",
        *([f"**Superseded ({SUPERSEDED_ON}, finding #79).** This sensitivity took the window change of a truncated level, "
           "`v if v < 100 else 0`, which gives the regressor the wrong sign in 92 of the 128 windows that straddle the $100 bn break, "
           "and it held the abundant regime's coefficient at 0 although the method record says each regime has its own. "
           "It stands as published; the corrected sensitivity is the next section, from "
           "`results/h10/sensitivity_onrrp_regimes.json`, and supersedes it.", ""] if regimes is not None else []),
        "**Reported only** (her answer 5 on #69: \"the interaction reported later as a sensitivity\"). The method record's decided "
        "driver set is unchanged, and this sensitivity does not change the published outcome above. ON RRP enters as "
        f"`{sensitivity['sensitivity']['on_rrp_term']}`, the parent's `ON_RRP_DEPLETION_BREAK_BN`, in place of its window change; "
        "everything else (window, bootstrap, seeds, placebo, benchmark, null, outcome rule) is as in the published record. "
        f"The record is `results/h10/sensitivity_onrrp_interaction.json`; its null bar is {sensitivity['null']['bar']:.3f}.",
        "",
        f"What the sensitivity shows: {_counts(s)}, against {_counts(d)} in the published record. Labelled sensitivity; it is not a result.",
        "",
        f"**The abundant regime has {abundant} onsets**, so the interaction is estimated almost entirely from the depleted regime and "
        "its term says little about the abundant one.",
        "",
        h10_apply.summary_markdown(sensitivity),
        "Progress markers under the interaction:",
        "",
        f"- median residual share: {_marker(s['markers']['median_residual_share'])};",
        f"- explained share above reserves alone: {_marker(s['markers']['median_explained_above_reserves'])};",
        f"- placebo gap: {_marker(s['markers']['median_placebo_gap'])}.",
        "",
        "### Episodes whose outcome differs",
        "",
    ]
    if differing:
        out += ["Published / interaction in each outcome column.", "",
                "| Onset | Residual (published) | Residual (interaction) | Under bar | Beats null |", "|---|---|---|---|---|", *differing]
    else:
        out.append("None: every episode has the same outcome under both.")
    out += ["", "### Per episode, beside the published figures", "", _sensitivity_table(development, sensitivity),
            *(_regime_sections(development, sensitivity, regimes) if regimes is not None else []),
            "## What this page does not do", "",
            "It states no verdict, registers nothing, scores no forecast, publishes no figure of the model repo and changes nothing "
            "in it. Registration of the frozen method is her attested action (plan, H10, \"Registration\").", ""]
    return "\n".join(out)


def render_tracked() -> str:
    """The page for the tracked records."""
    development = json.loads(h10_apply.RECORD.read_text(encoding="utf-8"))
    sensitivity = json.loads(h10_apply.SENSITIVITY_RECORD.read_text(encoding="utf-8"))
    regimes = json.loads(h10_apply.REGIMES_RECORD.read_text(encoding="utf-8")) if h10_apply.REGIMES_RECORD.is_file() else None
    return render(development, sensitivity, development_sha256=_digest(h10_apply.RECORD), method_sha256=_digest(METHOD),
                  regimes=regimes)
