"""The weekly group-reserves series: H.4.1 reserves split into bank groups by H.8 cash-asset shares (#43, G4 for H7m).

Candidate C (#41) needs reserves by bank group. Nicholas's answer 17(b) gave an anchored method (quarterly Call Report
balances moved by the H.8). Eleonora's rulings of 14 October 2026 on PR #50 replace the anchor: option (a) for the
foreign-related group and option (i) for the domestic split (unanchored, an approximation; "do not anchor on latest-filed
RC-A, because that would break rule 16(d)"), and then her middle option for the domestic split. Nothing is scored.

- **Other depository institutions, set first.** Thrifts and credit unions hold reserves that the H.4.1 counts and the H.8
  does not. Their reserves are a labelled fixed share of the week's H.4.1 reserve balances (`WRESBAL`):
  `OTHER_SHARE`. The share is a constant, not estimated week by week, so the residual is positive in every week and is never
  clipped. Where the value comes from is in `OTHER_SHARE_SOURCE`.
- **The rest, split by cash shares.** The remaining reserves, `(1 - OTHER_SHARE)` of the week's total, are split across the
  large domestic, small domestic and foreign-related groups in proportion to each group's H.8 cash assets, first print
  (`h8_large_domestic_cash_assets`, `h8_small_domestic_cash_assets`, `h8_foreign_related_cash_assets`). The shares are
  shares, not levels: cash assets are not reserves (they include vault cash, cash items in process of collection and balances
  due from other depository institutions), so the split is labelled an approximation (`domestic_basis`, `foreign_basis`).
  The four pieces sum to reserves in every week.
- **As of.** A week's row is public from the later of the H.8 first print's release (16:15 New York) and the reserves'
  declared availability (the parent's `fred_macro_latest_vintage` `WRESBAL` lag). Both inputs are first prints, so a row is
  never revised. The share is a constant fixed in this module, so it adds no vintage.
- **Breaks.** The H.8 restates the large and small panels at the break weeks of `docs/research/h8-group-moves.json`,
  moving them in opposite directions. A share of cash is not a ratio across weeks, so a break is not a refusal; the week
  carries `h8_break_week` so a reader knows that the split across it is on different panels.
- **What is not built.** The RC-A anchor (`repo_liquidity.rca`) is not read here. Under rule 16(d) as amended it is public
  years late. When the CDR archive (#49) holds first prints, the Call Report total can replace the fixed share (the
  ruling's step 2, a later directive that records the switch date and both versions).

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

#: The labelled fixed share of H.4.1 reserves held by other depository institutions (thrifts and credit unions).
OTHER_SHARE = 0.086
OTHER_SHARE_SOURCE = (
    "Median of the residual 'other depository institutions' divided by H.4.1 reserves over the 211 H.8 weeks from "
    "2022-08-10 to 2026-08-19 on which the retired anchored build (latest-filed Call Report RC-A item 0090, moved by the "
    "H.8 and with the break refusal switched off) could be computed: median 0.0862, range -0.009 to 0.163 (docs/research/"
    "rca-fed-balances-due-diligence.md, section 7). A full-sample constant from latest-filed data, so a retrospective "
    "calibration, not point-in-time; the value is rounded to 0.086 and is Eleonora's to confirm or replace.")

#: What `OTHER_SHARE` is (her ruling of 15 October 2026, condition 1): a full-sample constant from latest-filed data.
OTHER_SHARE_BASIS = "retrospective_calibration_not_point_in_time"
#: The range of the share's computable weeks (condition 2): the group levels are also reported at each end, next to the main
#: series. At the low end the residual is a small negative share of reserves, which is part of what the range shows.
SENSITIVITY_SHARES = (-0.009, 0.163)
USE_NOTE = ("Nothing scored or registered uses this series (her ruling of 15 October 2026, condition 3). The Call Report switch "
            "(step 2 of her ruling of 14 October 2026, once the CDR archive #49 has first prints) replaces the fixed share first.")

_GROUPS = ("large_domestic", "small_domestic", "foreign_related")
_SENSITIVITY_COLUMNS = tuple(f"{group}_share_{end}_bn" for end in ("low", "high") for group in _GROUPS)
COLUMNS: Tuple[str, ...] = (
    "week_ending", "public_at", "reserves_bn", "large_domestic_bn", "small_domestic_bn", "foreign_related_bn", "other_bn",
    "other_share", "other_share_basis") + _SENSITIVITY_COLUMNS + ("h8_break_week", "domestic_basis", "foreign_basis")
DOMESTIC_BASIS = "h8_cash_assets_approximation"
FOREIGN_BASIS = "h8_cash_assets_approximation"
REFUSALS = ("reserves_missing", "no_cash_assets")
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
    #: The three group levels at `SENSITIVITY_SHARES[0]` and `[1]` (the range of the share's computable weeks).
    sens_low: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    sens_high: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def other_negative(self) -> bool:
        return self.other_bn < 0


def _public_at(item: h8.FirstPrint, reserve_at: datetime) -> datetime:
    return max(h8.available_at(item.release_date), reserve_at)


def _check_share(share: float) -> None:
    if not 0.0 <= share < 1.0:
        raise ValueError(f"the other-depository share must be in [0, 1), not {share}")


def _check_sensitivity(share: float) -> None:
    if not -1.0 < share < 1.0:
        raise ValueError(f"the sensitivity share must be in (-1, 1), not {share}")


def _split(reserve_bn: float, cash: Sequence[float], share: float) -> List[float]:
    """The three group levels: reserves less the residual, in proportion to the H.8 cash assets (`cash`)."""
    rest = reserve_bn * (1.0 - share)
    total = sum(cash)
    return [round(rest * value / total, 6) for value in cash]


def build(*, prints: Sequence[h8.FirstPrint], reserves: Mapping[date, Tuple[float, datetime]],
          breaks: Mapping[date, str], other_share: float = OTHER_SHARE) -> Tuple[List[Row], List[dict]]:
    """The weekly series and the listed holes, from the inputs only.

    Args:
        prints: the H.8 group first prints (`h8.load_extract`).
        reserves: week ending -> (H.4.1 reserve balances in billions, the instant that value is public).
        breaks: the H.8 break weeks (`h8.break_flags`).
        other_share: the fixed share of reserves held by other depository institutions.

    Raises:
        ValueError: if an instant has no time zone, or the share is not in [0, 1).
    """
    _check_share(other_share)
    for sens in SENSITIVITY_SHARES:
        _check_sensitivity(sens)
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
        cash = [float(item.values[field]) for _, field in _LEVEL_FIELDS]
        if sum(cash) <= 0 or min(cash) < 0:
            holes.append({"week_ending": week.isoformat(), "reason": "no_cash_assets",
                          "detail": "the H.8 cash assets of the three groups are not all non-negative with a positive sum"})
            continue
        levels = dict(zip((name for name, _ in _LEVEL_FIELDS), _split(reserve_bn, cash, other_share)))
        other = round(reserve_bn - sum(levels.values()), 6)
        low, high = (tuple(_split(reserve_bn, cash, sens)) for sens in SENSITIVITY_SHARES)
        rows.append(Row(week_ending=week, public_at=_public_at(item, reserve_at), reserves_bn=reserve_bn, other_bn=other,
                        h8_break_week=week in breaks, sens_low=low, sens_high=high, **levels))
    return rows, holes


def verify(rows: Iterable[Row], prints: Sequence[h8.FirstPrint], reserves: Mapping[date, Tuple[float, datetime]]) -> None:
    """Refuse a row that is public before its inputs are, or whose levels are not the cash shares of the rest of reserves.

    Raises:
        ValueError: if a row's week is not in the H.8 extract or the reserves, or a level or the residual is not what the
            inputs give (the residual is reserves less the three levels).
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
        reserve_bn = reserves[row.week_ending][0]
        cash = [float(item.values[field]) for _, field in _LEVEL_FIELDS]
        for (name, _), want in zip(_LEVEL_FIELDS, _split(reserve_bn, cash, OTHER_SHARE)):
            if getattr(row, name) != want:
                raise ValueError(f"the week ending {row.week_ending}: {name} {getattr(row, name)} is not the H.8 cash share "
                                 f"of the rest of reserves ({want})")
        for sens, got in zip(SENSITIVITY_SHARES, (row.sens_low, row.sens_high)):
            if tuple(got) != tuple(_split(reserve_bn, cash, sens)):
                raise ValueError(f"the week ending {row.week_ending}: the levels at the share {sens} are not the H.8 cash "
                                 f"shares of the rest of reserves ({_split(reserve_bn, cash, sens)})")
        expected = round(reserve_bn - row.large_domestic_bn - row.small_domestic_bn - row.foreign_related_bn, 6)
        if row.other_bn != expected or row.reserves_bn != reserve_bn:
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
                         _fmt(row.other_bn), _fmt(OTHER_SHARE), OTHER_SHARE_BASIS,
                         *(_fmt(v) for v in row.sens_low), *(_fmt(v) for v in row.sens_high),
                         str(row.h8_break_week).lower(), DOMESTIC_BASIS, FOREIGN_BASIS))
    return buffer.getvalue().encode("utf-8")


def load_extract(path: Path) -> List[Row]:
    """The tracked extract, checked against its manifest and against its own derived columns.

    Raises:
        ValueError: if the bytes do not match the manifest, the columns are not `COLUMNS`, a week is listed twice, a basis
            label is not the declared one, or a stored derived column (the residual, the share) is not what the stored
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
                  other_bn=float(item["other_bn"]), h8_break_week=item["h8_break_week"] == "true",
                  sens_low=tuple(float(item[f"{g}_share_low_bn"]) for g in _GROUPS),
                  sens_high=tuple(float(item[f"{g}_share_high_bn"]) for g in _GROUPS))
        if row.week_ending in seen:
            raise ValueError(f"{path.name}: the week ending {row.week_ending} is listed twice")
        seen.add(row.week_ending)
        for column, want in (("domestic_basis", DOMESTIC_BASIS), ("foreign_basis", FOREIGN_BASIS),
                             ("other_share_basis", OTHER_SHARE_BASIS)):
            if item[column] != want:
                raise ValueError(f"{path.name}: {row.week_ending} is labelled {item[column]!r}, not {want!r}")
        expected = round(row.reserves_bn - row.large_domestic_bn - row.small_domestic_bn - row.foreign_related_bn, 6)
        for column, want in (("other_bn", _fmt(expected)), ("other_share", _fmt(OTHER_SHARE))):
            if item[column] != want:
                raise ValueError(f"{path.name}: {row.week_ending} stores {column} {item[column]!r}, the levels give {want!r}")
        rows.append(row)
    return rows


def _sensitivity(rows: Sequence[Row]) -> Dict:
    """For each end of the range: the share, and the median of each group's level beside the main series' median."""
    def med(values):
        return round(statistics.median(values), 3) if values else None

    out: Dict = {"main": {"share": OTHER_SHARE, "rows": len(rows),
                          **{f"{g}_median_bn": med([getattr(r, f"{g}_bn") for r in rows]) for g in _GROUPS}}}
    for end, share in zip(("low", "high"), SENSITIVITY_SHARES):
        attr = f"sens_{end}"
        out[end] = {"share": share, "rows": len(rows),
                    "residual_median_bn": med([share * r.reserves_bn for r in rows]),
                    **{f"{g}_median_bn": med([getattr(r, attr)[i] for r in rows]) for i, g in enumerate(_GROUPS)}}
    return out


def coverage(rows: Sequence[Row], holes: Sequence[dict], prints: Sequence[h8.FirstPrint]) -> Dict:
    """Every hole by week and reason, the counts, and the spread of the residual."""
    counts: Dict[str, int] = {}
    for item in holes:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    by_year: Dict[str, int] = {}
    for row in rows:
        by_year[str(row.week_ending.year)] = by_year.get(str(row.week_ending.year), 0) + 1
    others = sorted(r.other_bn for r in rows)
    cash = {p.week_ending: sum(float(p.values[f]) for _, f in _LEVEL_FIELDS) for p in prints}
    levels_negative = sum(1 for r in rows if r.reserves_bn - cash[r.week_ending] < 0)
    return {"weeks": len(prints), "rows": len(rows), "reasons": dict(sorted(counts.items())), "holes": list(holes),
            "first_week": rows[0].week_ending.isoformat() if rows else None,
            "last_week": rows[-1].week_ending.isoformat() if rows else None,
            "first_public_at": min(r.public_at for r in rows).isoformat() if rows else None,
            "rows_by_year": dict(sorted(by_year.items())),
            "break_weeks": sum(1 for r in rows if r.h8_break_week),
            "other_negative_weeks": sum(1 for r in rows if r.other_negative),
            "levels_reading_negative_weeks": levels_negative,
            "other_share": OTHER_SHARE, "other_share_source": OTHER_SHARE_SOURCE, "other_share_basis": OTHER_SHARE_BASIS,
            "sensitivity_shares": list(SENSITIVITY_SHARES), "sensitivity": _sensitivity(rows),
            "other_bn": ({"min": others[0], "median": statistics.median(others), "max": others[-1]} if others else None)}
