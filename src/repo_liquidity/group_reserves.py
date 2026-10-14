"""The weekly group-reserves series: the anchor moved by H.8 group cash, set against H.4.1 reserves (#43, G4 for H7m).

Candidate C (#41) needs reserves by bank group. Nicholas's answer 17(b) gives the method: anchor the group shares on the
exact quarterly figures, move them week by week with the H.8, scale them to H.4.1 reserve balances, and keep a residual
group for institutions the H.8 does not cover. Eleonora's rulings of 14 October 2026 on PR #50 fix the inputs, and this
module builds the series as ruled. Nothing is scored.

- **Large and small domestic groups.** The latest quarterly anchor of the group public at the row's instant
  (`repo_liquidity.rca`: RC-A item 0090, the 25 largest filers by total assets standing in for the Board's panel, a
  labelled approximation), moved from the H.8 week nearest its quarter-end to the row's week by the ratio of the group's
  H.8 cash assets, both first prints: `level = anchor * cash(week) / cash(anchor week)`.
- **Foreign-related institutions.** The H.8 foreign-related institutions' cash assets, first print, labelled an
  approximation (cash assets, not reserves alone). Ruling of 14 October 2026, option (a): no FFIEC 002 is read.
- **Other depository institutions.** The residual: H.4.1 reserve balances (`WRESBAL`) less the three groups. It is not
  clipped: a negative residual means the three approximations together exceed reserves, and the row is flagged
  (`other_negative`), never adjusted. There is no separate scaling step: a group level and the residual that makes the
  four sum to reserves are the same arithmetic.
- **As of.** A week's row is public from the later of the H.8 first print's release (16:15 New York) and the reserves'
  declared availability (the parent's `fred_macro_latest_vintage` `WRESBAL` lag). The anchors are chosen at that
  instant, once, and a row is not revised when a later anchor becomes public: the series is as first computed, in the
  way the H.8 groups are first prints. A week with no public anchor for either domestic group is a listed hole.
- **Breaks.** The H.8 restates the large and small panels at the break weeks of `docs/research/h8-group-moves.json`,
  moving them in opposite directions: a ratio across one is a change of basis and not a flow. A week whose anchor week
  lies before a break week that is not after the row's week is a listed hole (`h8.difference` refuses the same).
- **The moves are one proposed reading.** How a weekly move is split when the anchor and the H.8 disagree in sign is the
  question the directive says to ask, not to settle in code; the ratio is the simplest scaling and is marked as a question
  in the pull request and in `docs/decisions/data-meaning.md`.

Standard library only (the parent's `repo_model` is imported for the as-of declaration and the exception classes).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from repo_liquidity import development, h8, parent_root, rca

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "group_reserves"
EXTRACT_NAME = "group_reserves_weekly.csv"
COVERAGE_NAME = "group_reserves_weekly.coverage.json"
H8_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups" / h8.EXTRACT_NAME
RCA_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "rca_anchor" / rca.EXTRACT_NAME
#: The parent's tracked ALFRED vintage of `WRESBAL` (millions of dollars, the units rescale of 2026-09-12 recorded in the
#: parent's `fred_macro_latest_vintage` declaration). The registry says the series is never revised.
RESERVES_RELATIVE = Path("tests") / "fixtures" / "snapshots" / "alfred-wresbal" / "WRESBAL_2026-09-12.csv"
RESERVES_SOURCE, RESERVES_FIELD = "fred_macro_latest_vintage", "WRESBAL"

COLUMNS: Tuple[str, ...] = (
    "week_ending", "public_at", "reserves_bn", "large_anchor_quarter", "large_domestic_bn", "small_anchor_quarter",
    "small_domestic_bn", "foreign_related_bn", "other_bn", "other_negative", "large_anchor_age_days",
    "small_anchor_age_days", "foreign_basis")
FOREIGN_BASIS = "h8_cash_assets_approximation"
#: A quarter-end is matched to the H.8 week that ends within this many days of it.
MATCH_DAYS = 3
REFUSALS = ("reserves_missing", "no_anchor_public", "break_between_anchor_and_week")


@dataclass(frozen=True)
class Row:
    """One H.8 week's four group levels (billions of dollars), the anchors they stand on and the instant they are public."""

    week_ending: date
    public_at: datetime
    reserves_bn: float
    large_anchor_quarter: date
    large_domestic_bn: float
    small_anchor_quarter: date
    small_domestic_bn: float
    foreign_related_bn: float
    other_bn: float

    @property
    def other_negative(self) -> bool:
        return self.other_bn < 0

    @property
    def large_anchor_age_days(self) -> int:
        return (self.week_ending - self.large_anchor_quarter).days

    @property
    def small_anchor_age_days(self) -> int:
        return (self.week_ending - self.small_anchor_quarter).days


def anchor_week(weeks: Sequence[date], quarter_end: date) -> date:
    """The H.8 week that ends nearest `quarter_end` (a tie goes to the earlier week).

    Raises:
        ValueError: if no week ends within `MATCH_DAYS` of the quarter-end.
    """
    best = min(weeks, key=lambda w: (abs((w - quarter_end).days), w), default=None)
    if best is None or abs((best - quarter_end).days) > MATCH_DAYS:
        raise ValueError(f"no H.8 week ends within {MATCH_DAYS} days of the quarter-end {quarter_end}")
    return best


def build(*, prints: Sequence[h8.FirstPrint], anchors: Sequence[rca.Row], reserves: Mapping[date, Tuple[float, datetime]],
          breaks: Mapping[date, str]) -> Tuple[List[Row], List[dict]]:
    """The weekly series and the listed holes, from the inputs only.

    Args:
        prints: the H.8 group first prints (`h8.load_extract`).
        anchors: the quarterly RC-A anchors (`rca.load_extract`).
        reserves: week ending -> (H.4.1 reserve balances in billions, the instant that value is public).
        breaks: the H.8 break weeks (`h8.break_flags`).

    Raises:
        ValueError: if an instant has no time zone, or a group's cash assets at an anchor week are not positive.
        LookAheadError: if an anchor quarter ends after the week it anchors.
    """
    from repo_model.splits import LookAheadError

    by_week = {item.week_ending: item for item in prints}
    weeks = sorted(by_week)
    rows: List[Row] = []
    holes: List[dict] = []

    def hole(week: date, reason: str, detail: str) -> None:
        holes.append({"week_ending": week.isoformat(), "reason": reason, "detail": detail})

    for week in weeks:
        item = by_week[week]
        if week not in reserves:
            hole(week, "reserves_missing", "no H.4.1 reserve balances for the week")
            continue
        reserve_bn, reserve_at = reserves[week]
        if reserve_at.tzinfo is None:
            raise ValueError(f"the reserves of the week ending {week} are dated without a time zone")
        public_at = max(h8.available_at(item.release_date), reserve_at)
        picked = {group: rca.latest_public(anchors, group, public_at) for group in rca.GROUPS}
        absent = [group for group, found in picked.items() if found is None]
        if absent:
            hole(week, "no_anchor_public", f"no quarterly anchor of {', '.join(absent)} is public at {public_at.isoformat()}")
            continue
        levels: Dict[str, float] = {}
        crossed: List[str] = []
        for group, found in picked.items():
            if found.quarter_end > week:
                raise LookAheadError(f"the {group} anchor of the quarter ended {found.quarter_end} anchors the earlier "
                                     f"week ending {week}")
            origin = anchor_week(weeks, found.quarter_end)
            if any(origin < b <= week for b in breaks):
                crossed.append(f"{group} (anchor week {origin})")
                continue
            field = f"h8_{group}_cash_assets"
            base = by_week[origin].values[field]
            if not base > 0:
                raise ValueError(f"the {group} cash assets of the week ending {origin} are {base}, not a positive base")
            levels[group] = round(found.balances_bn * item.values[field] / base, 6)
        if crossed:
            hole(week, "break_between_anchor_and_week",
                 f"an H.8 break week lies between the anchor week and the week: {', '.join(crossed)}")
            continue
        foreign = item.values["h8_foreign_related_cash_assets"]
        other = round(reserve_bn - levels["large_domestic"] - levels["small_domestic"] - foreign, 6)
        rows.append(Row(week_ending=week, public_at=public_at, reserves_bn=reserve_bn,
                        large_anchor_quarter=picked["large_domestic"].quarter_end,
                        large_domestic_bn=levels["large_domestic"],
                        small_anchor_quarter=picked["small_domestic"].quarter_end,
                        small_domestic_bn=levels["small_domestic"], foreign_related_bn=foreign, other_bn=other))
    return rows, holes


def verify(rows: Iterable[Row], anchors: Sequence[rca.Row]) -> None:
    """Refuse a row whose anchors were not public at its instant, or were not the latest then public.

    Raises:
        ValueError: if a row names an anchor quarter the extract does not hold.
        LookAheadError: if a row's anchor became available after the row's `public_at`.
        StaleReadError: if a later quarter of the group was already public at the row's `public_at`.
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    for row in rows:
        for group, quarter in (("large_domestic", row.large_anchor_quarter), ("small_domestic", row.small_anchor_quarter)):
            matches = [a for a in anchors if a.group == group and a.quarter_end == quarter]
            if not matches:
                raise ValueError(f"the week ending {row.week_ending} names the {group} anchor of {quarter}, which is not in "
                                 f"the anchor extract")
            if matches[0].available_from > row.public_at:
                raise LookAheadError(f"the week ending {row.week_ending} (public {row.public_at}) uses the {group} anchor "
                                     f"of {quarter}, available only from {matches[0].available_from}")
            latest = rca.latest_public(anchors, group, row.public_at)
            if latest is not None and latest.quarter_end > quarter:
                raise StaleReadError(f"the week ending {row.week_ending} uses the {group} anchor of {quarter} when the "
                                     f"quarter ended {latest.quarter_end} was already public at {row.public_at}")


# ---------------------------------------------------------------------------------------------------------------
# Inputs


def load_reserves(root: Optional[Path] = None) -> Dict[date, Tuple[float, datetime]]:
    """H.4.1 reserve balances in billions, by week ending, with the instant each is public.

    Read from the parent's tracked ALFRED vintage; the instant is the parent's own declared availability for the field
    (`repo_model.asof.declared_availability`), never a rule of this repository.
    """
    from repo_model import asof

    base = root or parent_root()
    registry = json.loads((base / "metadata" / "sources.json").read_text(encoding="utf-8"))
    out: Dict[date, Tuple[float, datetime]] = {}
    with (base / RESERVES_RELATIVE).open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for day, value in reader:
            if not value.strip() or value.strip() == ".":
                continue
            ref = date.fromisoformat(day)
            moment = asof.declared_availability(registry, RESERVES_SOURCE, RESERVES_FIELD, [ref], 0)
            if moment is None:
                raise ValueError("the parent no longer declares a row-relative availability for WRESBAL")
            out[ref] = (round(float(value) / 1000.0, 6), moment.replace(tzinfo=h8.NEW_YORK))
    return out


def tracked_inputs() -> dict:
    """The keyword inputs of `build`, read from tracked files only. The H.8 weeks and anchors are checked on load."""
    prints = h8.load_extract(H8_EXTRACT)
    reserves = load_reserves()
    end = development.development_end()
    reserves = {w: v for w, v in reserves.items() if end is None or not development.is_locked(v[1].date())}
    return {"prints": prints, "anchors": rca.load_extract(RCA_EXTRACT), "reserves": reserves,
            "breaks": h8.break_flags(h8.load_moves())}


def source_digests() -> Dict[str, str]:
    """The SHA-256 of each tracked input file the series is computed from."""
    files = {"h8_groups": H8_EXTRACT, "rca_anchor": RCA_EXTRACT, "h8_group_moves": h8.MOVES_PATH,
             "wresbal": parent_root() / RESERVES_RELATIVE}
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}


# ---------------------------------------------------------------------------------------------------------------
# The extract


def _fmt(value: float) -> str:
    return f"{value:.6f}"


def write_extract(rows: Iterable[Row]) -> bytes:
    """The tracked CSV: one row per week, oldest first."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in sorted(rows, key=lambda r: r.week_ending):
        writer.writerow((row.week_ending.isoformat(), row.public_at.isoformat(), _fmt(row.reserves_bn),
                         row.large_anchor_quarter.isoformat(), _fmt(row.large_domestic_bn),
                         row.small_anchor_quarter.isoformat(), _fmt(row.small_domestic_bn), _fmt(row.foreign_related_bn),
                         _fmt(row.other_bn), str(row.other_negative).lower(), row.large_anchor_age_days,
                         row.small_anchor_age_days, FOREIGN_BASIS))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against its own derived columns.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `COLUMNS`, a week is listed twice, the
            foreign basis is not `FOREIGN_BASIS`, or a stored derived column (the residual, its flag, an anchor age) is
            not what the stored levels give.
    """
    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match its manifest ({digest} != {manifest['sha256']})")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"{path.name}: columns {reader.fieldnames} are not {list(COLUMNS)}")
        stored = list(reader)
    rows: List[Row] = []
    seen = set()
    for item in stored:
        row = Row(week_ending=date.fromisoformat(item["week_ending"]), public_at=datetime.fromisoformat(item["public_at"]),
                  reserves_bn=float(item["reserves_bn"]), large_anchor_quarter=date.fromisoformat(item["large_anchor_quarter"]),
                  large_domestic_bn=float(item["large_domestic_bn"]),
                  small_anchor_quarter=date.fromisoformat(item["small_anchor_quarter"]),
                  small_domestic_bn=float(item["small_domestic_bn"]), foreign_related_bn=float(item["foreign_related_bn"]),
                  other_bn=float(item["other_bn"]))
        if row.week_ending in seen:
            raise ValueError(f"{path.name}: the week ending {row.week_ending} is listed twice")
        seen.add(row.week_ending)
        if item["foreign_basis"] != FOREIGN_BASIS:
            raise ValueError(f"{path.name}: {row.week_ending} is labelled {item['foreign_basis']!r}, not {FOREIGN_BASIS!r}")
        expected = round(row.reserves_bn - row.large_domestic_bn - row.small_domestic_bn - row.foreign_related_bn, 6)
        for column, want in (("other_bn", _fmt(expected)), ("other_negative", str(expected < 0).lower()),
                             ("large_anchor_age_days", str(row.large_anchor_age_days)),
                             ("small_anchor_age_days", str(row.small_anchor_age_days))):
            if item[column] != want:
                raise ValueError(f"{path.name}: {row.week_ending} stores {column} {item[column]!r}, the levels give {want!r}")
        rows.append(row)
    return rows


def _diagnostic(inputs: Mapping) -> Dict:
    """What `build` would give with the break refusal switched off. A diagnostic of how much the refusal costs, never a series.

    The rows it counts move a ratio across a change of basis (the H.8 restates the large and small panels at a break week),
    so they are not published and no model reads them.
    """
    rows, _ = build(prints=inputs["prints"], anchors=inputs["anchors"], reserves=inputs["reserves"], breaks={})
    others = sorted(r.other_bn for r in rows)
    return {"rows": len(rows), "first_week": rows[0].week_ending.isoformat() if rows else None,
            "last_week": rows[-1].week_ending.isoformat() if rows else None,
            "other_negative_weeks": sum(1 for r in rows if r.other_negative),
            "other_bn": ({"min": others[0], "median": statistics.median(others), "max": others[-1]} if others else None)}


def coverage(rows: Sequence[Row], holes: Sequence[dict], prints: Sequence[h8.FirstPrint],
             inputs: Optional[Mapping] = None) -> Dict:
    """Every hole by week and reason, the counts, and the age of the anchors the rows stand on.

    With `inputs` (the keyword inputs of `build`), also the diagnostic of `_diagnostic`.
    """
    counts: Dict[str, int] = {}
    for item in holes:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    by_year: Dict[str, int] = {}
    for row in rows:
        by_year[str(row.week_ending.year)] = by_year.get(str(row.week_ending.year), 0) + 1
    ages = sorted(a for row in rows for a in (row.large_anchor_age_days, row.small_anchor_age_days))
    record = {"weeks": len(prints), "rows": len(rows), "reasons": dict(sorted(counts.items())), "holes": list(holes),
              "first_week": rows[0].week_ending.isoformat() if rows else None,
              "last_week": rows[-1].week_ending.isoformat() if rows else None,
              "first_public_at": min(r.public_at for r in rows).isoformat() if rows else None,
              "rows_by_year": dict(sorted(by_year.items())),
              "other_negative_weeks": sum(1 for r in rows if r.other_negative),
                "anchor_age_days": ({"min": ages[0], "median": statistics.median(ages), "max": ages[-1]} if ages else None)}
    if inputs is not None:
        record["diagnostic_without_break_refusal"] = _diagnostic(inputs)
    return record
