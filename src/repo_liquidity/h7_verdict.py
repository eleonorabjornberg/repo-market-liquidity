"""H7m stage verdict (directive #187): the plan's rule applied to step 5's development scores, under Eleonora's ruling of 26 October 2026.

Pure functions over the tracked records. Nothing is scored, fitted or typed: every figure in the verdict record is a figure a
tracked record carries, read through `read_figure`, which refuses a source or a path that no record has and anything that is not
a single value. `check_figures` re-reads every figure of a verdict record against the records, and `untyped_numbers` finds a
number that is not one. Stdlib only.

The rule (`docs/research/plan.md:185-186`, `:193-194`; eligibility `docs/decisions/measurement-protocol.md:51`, section 7): a
candidate is eligible when goalposts 1 and 2 hold on the development walk-forward and the distribution account exists. With no
eligible candidate, H7m is "not testable as stated". The ruling covers that case only, so `verdict` refuses any other.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

NOT_TESTABLE = "not testable as stated"
GOALPOST_ONE_A = "as in A's restated record (results/h7/kink.json)"
GOALPOST_ONE_C = "unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6)"

#: The tracked records the verdict reads, by the name a figure cites.
RECORD_PATHS = {
    "step5": "results/h7/step5-scores.json",
    "kink": "results/h7/kink.json",
    "calendar_clean": "results/h7/calendar-clean.json",
    "distribution_account": "results/h7/distribution-account.json",
}
#: The rule's text, quoted from the files by line (first, last).
QUOTES = (
    ("docs/research/plan.md", 185, 186),
    ("docs/research/plan.md", 193, 194),
    ("docs/decisions/measurement-protocol.md", 51, 51),
)
A_IDS = ("B", "V1", "V2", "V3", "V4", "V5", "V6")
C_IDS = ("C", "CV1", "CV2", "CV3", "CV4")
RULING = {
    "date": "2026-10-26",
    "by": "Eleonora",
    "on": "repo-market-liquidity#181",
    "option": "(a)",
    "wording": "yep",
    "relayed_by": "the model orchestrator",
}
POOLED = "all: all"
BESIDE_NOTE = "reported as development evidence; not the reason for the verdict"
OUT_OF_SCOPE = (
    "The record states the rule's result and nothing more. It makes no claim about whether scarcity can be measured, and says nothing "
    "about the outcome of H7f."
)
H7F_NOTE = (
    "H7f is the model repository's. This is stated as the plan's consequence, not an action here."
)


# --- the reader --------------------------------------------------------------------------------------------------------------

def read_figure(records: Mapping[str, Mapping], source: str, path: Sequence[str]):
    """The single value at `path` in the record named `source`; ValueError for a source or path no record carries, or a branch."""
    if source not in records:
        raise ValueError(f"no record named {source!r}")
    node = records[source]
    for step in path:
        if not isinstance(node, Mapping) or step not in node:
            raise ValueError(f"record {source!r} carries nothing at {'.'.join(map(str, path))!r}")
        node = node[step]
    if isinstance(node, (Mapping, list)) or node is None:
        raise ValueError(f"record {source!r} at {'.'.join(map(str, path))!r} is not a single value")
    return node


def figure(records: Mapping[str, Mapping], source: str, path: Sequence[str]) -> Dict[str, object]:
    """A figure of the verdict record: its value, read from a record, with where it was read."""
    return {"value": read_figure(records, source, path), "source": source, "path": list(path)}


def _is_figure(node) -> bool:
    return isinstance(node, Mapping) and "value" in node


def check_figures(record, records: Mapping[str, Mapping]) -> List[str]:
    """The errors of a verdict record's figures: one that lacks its source or path, or that is not what the record carries."""
    errors: List[str] = []

    def walk(node, trail):
        if _is_figure(node):
            if set(node) != {"value", "source", "path"}:
                errors.append(f"{trail}: a figure without its source and path")
                return
            try:
                read = read_figure(records, node["source"], node["path"])
            except ValueError as err:
                errors.append(f"{trail}: {err}")
                return
            if read != node["value"]:
                errors.append(f"{trail}: {node['value']!r} is not what {node['source']} carries ({read!r})")
        elif isinstance(node, Mapping):
            for key, child in node.items():
                walk(child, f"{trail}.{key}" if trail else str(key))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{trail}[{i}]")

    walk(record, "")
    return errors


def untyped_numbers(record) -> List[str]:
    """Where a number stands in the record outside a figure (the line numbers of a quote excepted)."""
    found: List[str] = []

    def walk(node, trail):
        if _is_figure(node):
            return
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key == "lines":
                    continue
                walk(child, f"{trail}.{key}" if trail else str(key))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{trail}[{i}]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            found.append(trail)

    walk(record, "")
    return found


def load_records(root: Path) -> Dict[str, Mapping]:
    return {name: json.loads((root / path).read_text(encoding="utf-8")) for name, path in RECORD_PATHS.items()}


def source_digests(root: Path) -> Dict[str, Dict[str, str]]:
    return {name: {"path": path, "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest()}
            for name, path in RECORD_PATHS.items()}


# --- the rule ----------------------------------------------------------------------------------------------------------------

def derive(step5: Mapping, kink: Optional[Mapping] = None) -> Dict[str, Dict[str, object]]:
    """Each estimator's status under the rule, from step 5's record (and, when given, A's restated kink record).

    Eligible: goalposts 1 and 2 both hold. A goalpost that fails is reported before one that cannot be read, and goalpost 1 before
    goalpost 2. The distribution account must also carry the estimator (`check_account`)."""
    width_limit = step5["settings"]["width_limit_points"]
    out: Dict[str, Dict[str, object]] = {}
    for name, e in step5["estimators"].items():
        if e["status"] != "scored":
            out[name] = {"status": "not scorable", "reason": e["reason"], "eligible": False,
                         "goalpost_1": None, "goalpost_2_holds": None}
            continue
        g1 = e["goalpost_1"]
        if "recorded" in g1:
            recorded = g1["recorded"]
            if kink is not None:
                restated = kink["summaries"][name]["all_served_days"]["goalpost_1"]
                if restated != recorded:
                    raise ValueError(f"{name}: step 5's goalpost 1 is not the kink record's")
            g1_state = "holds" if recorded["holds"] else "fails"
        elif g1.get("reading") == GOALPOST_ONE_C:
            g1_state = "unreadable"
        else:
            raise ValueError(f"{name}: goalpost 1 has a reading the rule does not know: {g1!r}")
        width = e["goalpost_2"][POOLED]
        g2_holds = width["median_points"] < width_limit
        if (width["position"] == "under the bar") != g2_holds:
            raise ValueError(f"{name}: the record's position {width['position']!r} disagrees with its median")
        if g1_state == "fails":
            status = "ineligible: goalpost 1 does not hold"
            reason = ("goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at "
                      "or above the limit")
        elif not g2_holds:
            status = "ineligible: goalpost 2 does not hold"
            reason = "goalpost 2 does not hold: the median width of the daily 90% interval is not under the bar"
        elif g1_state == "unreadable":
            status = "ineligible: goalpost 1 is unreadable on development data"
            reason = ("goalpost 2 holds; goalpost 1 is unreadable on development data (her option 6 of 22 October), so it cannot "
                      "be shown to hold and the candidate is not eligible")
        else:
            status, reason = "eligible", "goalposts 1 and 2 hold on the development walk-forward"
        out[name] = {"status": status, "reason": reason, "eligible": status == "eligible", "goalpost_1": g1_state,
                     "goalpost_2_holds": g2_holds}
    return out


def check_account(derived: Mapping[str, Mapping], account: Mapping, step5: Mapping) -> None:
    """Eligibility also needs the distribution account (section 7): an eligible estimator the account lacks is refused."""
    for name, row in derived.items():
        if row["eligible"] and step5["estimators"][name]["account_key"] not in account["estimators"]:
            row["eligible"] = False
            row["status"] = "ineligible: no distribution account"
            row["reason"] = "the distribution account does not carry it"


def verdict(derived: Mapping[str, Mapping]) -> str:
    """The rule's result. The ruling covers the case of no eligible candidate only; any other raises ValueError."""
    eligible = sorted(n for n, row in derived.items() if row["eligible"])
    if eligible:
        raise ValueError(f"eligible candidates exist ({', '.join(eligible)}): the ruling of 26 October does not cover this")
    return NOT_TESTABLE


# --- the record --------------------------------------------------------------------------------------------------------------

def _quotes(root: Path) -> List[Dict[str, object]]:
    out = []
    for file, first, last in QUOTES:
        lines = (root / file).read_text(encoding="utf-8").splitlines()
        out.append({"file": file, "lines": [first, last], "text": "\n".join(lines[first - 1:last])})
    return out


def build(root: Path) -> Dict[str, object]:
    records = load_records(root)
    step5 = records["step5"]
    derived = derive(step5, kink=records["kink"])
    check_account(derived, records["distribution_account"], step5)
    result = verdict(derived)
    estimators: Dict[str, Dict[str, object]] = {}
    for name in A_IDS + C_IDS:
        d = derived[name]
        e: Dict[str, object] = {"family": step5["estimators"][name]["family"], "status": d["status"], "reason": d["reason"],
                                "eligible": d["eligible"]}
        base = ["estimators", name]
        if d["status"] != "not scorable":
            g1 = step5["estimators"][name]["goalpost_1"]
            if "recorded" in g1:
                r = base + ["goalpost_1", "recorded"]
                e["goalpost_1"] = {"reading": g1["reading"], "holds": read_figure(records, "step5", r + ["holds"]),
                                   "worst_gap_points": figure(records, "step5", r + ["worst", "gap"]),
                                   "worst_day": read_figure(records, "step5", r + ["worst", "day"]),
                                   "limit_points": figure(records, "step5", r + ["limit"])}
            else:
                e["goalpost_1"] = {"reading": g1["reading"]}
            g2 = base + ["goalpost_2", POOLED]
            e["goalpost_2"] = {"median_points": figure(records, "step5", g2 + ["median_points"]),
                               "limit_points": figure(records, "step5", g2 + ["limit_points"]),
                               "holds": d["goalpost_2_holds"]}
        estimators[name] = e
    beside = {}
    for name in A_IDS + C_IDS:
        if derived[name]["status"] == "not scorable":
            continue
        g3 = ["estimators", name, "goalpost_3"]
        beside[name] = {"vs_rs_point": figure(records, "step5", g3 + ["vs_rs", POOLED, "point"]),
                        "vs_rs_position": read_figure(records, "step5", g3 + ["vs_rs", POOLED, "position"]),
                        "vs_s_point": figure(records, "step5", g3 + ["vs_s", POOLED, "point"])}
    mme = figure(records, "step5", ["settings", "mme"])
    quotes = _quotes(root)
    return {
        "directive": "repo-market-liquidity#187",
        "hypothesis": "H7",
        "question": "H7m",
        "stage": "docs/stages/h7m-verdict.md",
        "tier": "development",
        "verdict": result,
        "eligible": [],
        "rule": {
            "result": "no candidate is eligible after steps 2 to 5",
            "eligibility": "goalposts 1 and 2 hold on the development walk-forward, and the distribution account exists",
            "quotes": quotes,
        },
        "ruling": dict(RULING),
        "plan_consequence": {"quote": "Effort then goes to H7f with R+S alone.", "source": "docs/research/plan.md:193-194",
                             "note": H7F_NOTE},
        "estimators": estimators,
        "beside": beside,
        "beside_note": BESIDE_NOTE,
        "mme": mme,
        "not_claimed": OUT_OF_SCOPE,
        "sources": source_digests(root),
        "note": "Generated by scripts/h7_verdict.py; never edited by hand.",
    }


# --- the page ----------------------------------------------------------------------------------------------------------------

def _num(fig, digits: int, signed: bool = False) -> str:
    value = fig["value"]
    return f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"


def markdown(record: Mapping) -> str:
    out: List[str] = []
    w = out.append
    w("# H7m stage verdict: not testable as stated")
    w("")
    w("**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, the verdict after development steps 2 to 5 "
      "(`docs/research/plan.md`). Directive #187. Development tier. It is hers to review and merge (a stage verdict).")
    w("")
    w(f"**Verdict: {record['verdict']}.** No candidate is eligible after steps 2 to 5. This page states the rule's result and "
      "nothing more. Printed from `results/h7/verdict.json`; every figure below is a figure a tracked record carries.")
    w("")
    w("## 1. The rule, quoted")
    w("")
    for q in record["rule"]["quotes"]:
        first, last = q["lines"]
        where = f"{q['file']}:{first}" if first == last else f"{q['file']}:{first}-{last}"
        w(f"`{where}`")
        w("")
        for line in q["text"].splitlines():
            w(f"> {line}")
        w("")
    w("## 2. Her ruling")
    w("")
    r = record["ruling"]
    w(f"Eleonora, {r['date']}, on #181: option {r['option']}, \"{r['wording']}\", relayed by {r['relayed_by']}. No candidate is "
      "eligible after steps 2 to 5, so H7m is not testable as stated, by the two plan lines above. Eligibility follows "
      "`docs/decisions/measurement-protocol.md:51` (section 7).")
    w("")
    w("## 3. Each estimator's status")
    w("")
    w("Read from `results/h7/step5-scores.json` (step 5, PR #181) and `results/h7/kink.json` (PR #168). Widths and gaps are in "
      "points of bank assets; the bar is on width and the limit is on the gap.")
    w("")
    w("| Estimator | Status | Worst gap (limit) | Median width (bar) | Reason |")
    w("|---|---|---|---|---|")
    for name in A_IDS + C_IDS:
        e = record["estimators"][name]
        g1, g2 = e.get("goalpost_1"), e.get("goalpost_2")
        gap = "-"
        if g1 and "worst_gap_points" in g1:
            gap = f"{_num(g1['worst_gap_points'], 2)} ({_num(g1['limit_points'], 1)})"
        elif g1:
            gap = "unreadable on development data"
        width = "-" if not g2 else f"{_num(g2['median_points'], 2)} ({_num(g2['limit_points'], 1)})"
        w(f"| {name} | {e['status']} | {gap} | {width} | {e['reason']} |")
    w("")
    w("Family A is B and V1 to V6; family C is C and CV1 to CV4. Goalpost 1 for C and its variants is unreadable on development "
      "data under her option 6 of 22 October, which is neither a pass nor a fail; for CV3, whose width is under the bar, that "
      "leaves it not eligible.")
    w("")
    w("## 4. Beside the rule, not as the reason")
    w("")
    w(f"Step 5's goalpost 3, pooled, in AUROC points against the MME of {_num(record['mme'], 2)}. {record['beside_note'].capitalize()}.")
    w("")
    w("| Estimator | Gain against R+S | Position | Gain against S alone |")
    w("|---|---|---|---|")
    for name in A_IDS + C_IDS:
        if name not in record["beside"]:
            continue
        row = record["beside"][name]
        w(f"| {name} | {_num(row['vs_rs_point'], 3, True)} | {row['vs_rs_position']} | {_num(row['vs_s_point'], 3, True)} |")
    w("")
    w("No interval against R+S lies at or above the MME, and every gain against S alone is negative.")
    w("")
    w("## 5. The plan's consequence")
    w("")
    c = record["plan_consequence"]
    w(f"`{c['source']}`: \"{c['quote']}\" {c['note']}")
    w("")
    w("## 6. What this does not say")
    w("")
    w(record["not_claimed"])
    w("")
    w("## 7. Records read")
    w("")
    for name in RECORD_PATHS:
        s = record["sources"][name]
        w(f"- `{s['path']}` (`{s['sha256']}`)")
    w("")
    w("Regenerate with `python3 -B scripts/h7_verdict.py` (`--check` exits 1 if the record or this page is stale). Neither is "
      "edited by hand. The record is listed in `repo_liquidity.records.OWN_CHECK` with `tests/test_h7_verdict.py`.")
    w("")
    return "\n".join(out)
