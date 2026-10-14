"""The weekly group-reserves series: H.8 group cash assets set against H.4.1 reserves (#43, G4 for H7m).

Candidate C (#41) needs reserves by bank group. Nicholas's answer 17(b) gave an anchored method (quarterly Call Report
balances moved by the H.8). Eleonora's rulings of 14 October 2026 on PR #50 replace the anchor: option (a) for the
foreign-related group and option (i) for the domestic split ("use the H.8 group cash shares for the domestic split as well,
unanchored and labelled as an approximation ... Do not anchor on latest-filed RC-A, because that would break rule 16(d)").
Nothing is scored.

- **Large and small domestic groups, and the foreign-related group.** Each level is the H.8 group's cash assets, first
  print, in billions of dollars: `h8_large_domestic_cash_assets`, `h8_small_domestic_cash_assets`,
  `h8_foreign_related_cash_assets`. Cash assets are not reserves alone (they include vault cash, cash items in process of
  collection and balances due from other depository institutions), so every level is labelled an approximation
  (`domestic_basis`, `foreign_basis`).
- **Other depository institutions.** The residual: H.4.1 reserve balances (`WRESBAL`) less the three groups. It is not
  clipped: a negative residual means the three approximations together exceed reserves, and the row is flagged
  (`other_negative`), never adjusted.
- **As of.** A week's row is public from the later of the H.8 first print's release (16:15 New York) and the reserves'
  declared availability (the parent's `fred_macro_latest_vintage` `WRESBAL` lag). Both inputs are first prints, so a row is
  never revised.
- **Breaks.** The H.8 restates the large and small panels at the break weeks of `docs/research/h8-group-moves.json`, moving
  them in opposite directions. A level is a first print and not a ratio, so a break is not a refusal; the week carries
  `h8_break_week` so a reader knows that levels across it are on different panels.
- **What is not built.** The RC-A anchor (`repo_liquidity.rca`) is not read here. Under rule 16(d) as amended it is public
  years late, and the ruling says not to anchor on latest-filed figures. When the CDR archive (#49) holds first prints, an
  anchored version can be a later directive.

Standard library only (the parent's `repo_model` is imported for the as-of declaration and the exception classes).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from repo_liquidity import development, h8, parent_root

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "tests" / "fixtures" / "snapshots" / "group_reserves"
EXTRACT_NAME = "group_reserves_weekly.csv"
COVERAGE_NAME = "group_reserves_weekly.coverage.json"
H8_EXTRACT = ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups" / h8.EXTRACT_NAME
#: The parent's tracked ALFRED vintage of `WRESBAL` (millions of dollars, the units rescale of 2026-09-12 recorded in the
#: parent's `fred_macro_latest_vintage` declaration). The registry says the series is never revised.
RESERVES_RELATIVE = Path("tests") / "fixtures" / "snapshots" / "alfred-wresbal" / "WRESBAL_2026-09-12.csv"
RESERVES_SOURCE, RESERVES_FIELD = "fred_macro_latest_vintage", "WRESBAL"

COLUMNS: Tuple[str, ...] = (
    "week_ending", "public_at", "reserves_bn", "large_domestic_bn", "small_domestic_bn", "foreign_related_bn", "other_bn",
    "other_negative", "h8_break_week", "domestic_basis", "foreign_basis")
DOMESTIC_BASIS = "h8_cash_assets_approximation"
FOREIGN_BASIS = "h8_cash_assets_approximation"
REFUSALS = ("reserves_missing",)
_LEVEL_FIELDS = (("large_domestic_bn", "h8_large_domestic_cash_assets"), ("small_domestic_bn", "h8_small_domestic_cash_assets"),
                 ("foreign_related_bn", "h8_foreign_related_cash_assets"))


@dataclass(frozen=True)
class Row:
    """One H.8 week's four group levels (billions of dollars) and the instant they are public."""

    week_ending: date
    public_at: datetime
    reserves_bn: float
    large_domestic_bn: float
    small_domestic_bn: float
    foreign_related_bn: float
    other_bn: float
    h8_break_week: bool = False

    @property
    def other_negative(self) -> bool:
        return self.other_bn < 0


def _public_at(item: h8.FirstPrint, reserve_at: datetime) -> datetime:
    return max(h8.available_at(item.release_date), reserve_at)


def build(*, prints: Sequence[h8.FirstPrint], reserves: Mapping[date, Tuple[float, datetime]],
          breaks: Mapping[date, str]) -> Tuple[List[Row], List[dict]]:
    """The weekly series and the listed holes, from the inputs only.

    Args:
        prints: the H.8 group first prints (`h8.load_extract`).
        reserves: week ending -> (H.4.1 reserve balances in billions, the instant that value is public).
        breaks: the H.8 break weeks (`h8.break_flags`).

    Raises:
        ValueError: if an instant has no time zone.
    """
    rows: List[Row] = []
    holes: List[dict] = []
    for item in sorted(prints, key=lambda p: p.week_ending):
        week = item.week_ending
        if week not in reserves:
            holes.append({"week_ending": week.isoformat(), "reason": "reserves_missing",
                          "detail": "no H.4.1 reserve balances for the week"})
            continue
        reserve_bn, reserve_at = reserves[week]
        if reserve_at.tzinfo is None:
            raise ValueError(f"the reserves of the week ending {week} are dated without a time zone")
        levels = {name: float(item.values[field]) for name, field in _LEVEL_FIELDS}
        other = round(reserve_bn - sum(levels.values()), 6)
        rows.append(Row(week_ending=week, public_at=_public_at(item, reserve_at), reserves_bn=reserve_bn, other_bn=other,
                        h8_break_week=week in breaks, **levels))
    return rows, holes


def verify(rows: Iterable[Row], prints: Sequence[h8.FirstPrint], reserves: Mapping[date, Tuple[float, datetime]]) -> None:
    """Refuse a row that is public before its inputs are, or whose levels are not the first prints.

    Raises:
        ValueError: if a row's week is not in the H.8 extract or the reserves, or a level or the residual is not what the
            inputs give.
        LookAheadError: if a row's `public_at` is earlier than the later of its H.8 release and its reserves' availability.
    """
    from repo_model.splits import LookAheadError

    by_week = {item.week_ending: item for item in prints}
    for row in rows:
        if row.week_ending not in by_week or row.week_ending not in reserves:
            raise ValueError(f"the week ending {row.week_ending} is not in the H.8 extract and the reserves")
        item = by_week[row.week_ending]
        ready = _public_at(item, reserves[row.week_ending][1])
        if row.public_at < ready:
            raise LookAheadError(f"the week ending {row.week_ending} is public at {row.public_at}, before its inputs are "
                                 f"({ready})")
        for name, field in _LEVEL_FIELDS:
            if getattr(row, name) != float(item.values[field]):
                raise ValueError(f"the week ending {row.week_ending}: {name} {getattr(row, name)} is not the H.8 first "
                                 f"print {item.values[field]}")
        expected = round(reserves[row.week_ending][0] - row.large_domestic_bn - row.small_domestic_bn
                         - row.foreign_related_bn, 6)
        if row.other_bn != expected or row.reserves_bn != reserves[row.week_ending][0]:
            raise ValueError(f"the week ending {row.week_ending}: the reserves or the residual are not what the inputs give")


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
    """The keyword inputs of `build`, read from tracked files only. The H.8 weeks are checked on load."""
    prints = h8.load_extract(H8_EXTRACT)
    reserves = load_reserves()
    end = development.development_end()
    reserves = {w: v for w, v in reserves.items() if end is None or not development.is_locked(v[1].date())}
    return {"prints": prints, "reserves": reserves, "breaks": h8.break_flags(h8.load_moves())}


def source_digests() -> Dict[str, str]:
    """The SHA-256 of each tracked input file the series is computed from."""
    files = {"h8_groups": H8_EXTRACT, "h8_group_moves": h8.MOVES_PATH, "wresbal": parent_root() / RESERVES_RELATIVE}
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
                         _fmt(row.large_domestic_bn), _fmt(row.small_domestic_bn), _fmt(row.foreign_related_bn),
                         _fmt(row.other_bn), str(row.other_negative).lower(), str(row.h8_break_week).lower(),
                         DOMESTIC_BASIS, FOREIGN_BASIS))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against its own derived columns.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `COLUMNS`, a week is listed twice, a basis
            label is not the declared one, or a stored derived column (the residual, its flag) is not what the stored
            levels give.
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
                  reserves_bn=float(item["reserves_bn"]), large_domestic_bn=float(item["large_domestic_bn"]),
                  small_domestic_bn=float(item["small_domestic_bn"]), foreign_related_bn=float(item["foreign_related_bn"]),
                  other_bn=float(item["other_bn"]), h8_break_week=item["h8_break_week"] == "true")
        if row.week_ending in seen:
            raise ValueError(f"{path.name}: the week ending {row.week_ending} is listed twice")
        seen.add(row.week_ending)
        for column, want in (("domestic_basis", DOMESTIC_BASIS), ("foreign_basis", FOREIGN_BASIS)):
            if item[column] != want:
                raise ValueError(f"{path.name}: {row.week_ending} is labelled {item[column]!r}, not {want!r}")
        expected = round(row.reserves_bn - row.large_domestic_bn - row.small_domestic_bn - row.foreign_related_bn, 6)
        for column, want in (("other_bn", _fmt(expected)), ("other_negative", str(expected < 0).lower())):
            if item[column] != want:
                raise ValueError(f"{path.name}: {row.week_ending} stores {column} {item[column]!r}, the levels give {want!r}")
        rows.append(row)
    return rows


def coverage(rows: Sequence[Row], holes: Sequence[dict], prints: Sequence[h8.FirstPrint]) -> Dict:
    """Every hole by week and reason, the counts, and the spread of the residual."""
    counts: Dict[str, int] = {}
    for item in holes:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    by_year: Dict[str, int] = {}
    for row in rows:
        by_year[str(row.week_ending.year)] = by_year.get(str(row.week_ending.year), 0) + 1
    others = sorted(r.other_bn for r in rows)
    return {"weeks": len(prints), "rows": len(rows), "reasons": dict(sorted(counts.items())), "holes": list(holes),
            "first_week": rows[0].week_ending.isoformat() if rows else None,
            "last_week": rows[-1].week_ending.isoformat() if rows else None,
            "first_public_at": min(r.public_at for r in rows).isoformat() if rows else None,
            "rows_by_year": dict(sorted(by_year.items())),
            "break_weeks": sum(1 for r in rows if r.h8_break_week),
            "other_negative_weeks": sum(1 for r in rows if r.other_negative),
            "other_bn": ({"min": others[0], "median": statistics.median(others), "max": others[-1]} if others else None)}
