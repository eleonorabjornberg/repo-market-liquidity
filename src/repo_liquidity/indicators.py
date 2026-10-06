"""Stage 1b's first-wave indicators: pricing and the Fed's facilities (`docs/stages/stage-1b.md`).

Nicholas Beroud's answer 7 (`docs/decisions/data-meaning.md`): start narrow, with pricing (SOFR - IORB, TGCR and BGCR,
percentile dispersion, SOFR - EFFR) and the Fed's facilities (ON RRP, the standing facility, SOMA flows, the TGA).
Answer 12 adds TGCR - ON RRP rate as the ON RRP reading, with take-up kept only as the parent's buffer flag (#232).

Each indicator is computed on a panel row from that row's own values, which refer to the row's date; the parent's
`asof.InformationRule` applies each input's publication lag when a row is read. The two rates the spreads are
measured against (the ON RRP rate and the standing facility's rate) are read by effective date, and only from a
publication out by the close of the row's day (`rate_known_by_close`). Rates in percent; spreads in basis points.
Standard library only, apart from the parent.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from repo_liquidity import scheduled

#: Each indicator, the panel columns it reads, and how. Order is the panel's.
SPREADS: Tuple[Tuple[str, str, str], ...] = (
    ("sofr_minus_iorb_bp", "sofr", "iorb"),
    ("tgcr_minus_sofr_bp", "tgcr", "sofr"),
    ("bgcr_minus_sofr_bp", "bgcr", "sofr"),
    ("sofr_p75_p25_bp", "sofr_p75", "sofr_p25"),
    ("sofr_p99_p1_bp", "sofr_p99", "sofr_p1"),
    # The specials proxy of answer 8, kept on its own (collateral) axis.
    ("sofr_p1_minus_bgcr_bp", "sofr_p1", "bgcr"),
    ("sofr_minus_effr_bp", "sofr", "effr"),
)
FLOOR_SPREAD = ("tgcr_minus_on_rrp_bp", "tgcr")
CEILING_SPREAD = ("sofr_minus_srf_bp", "sofr")
COLUMNS: Tuple[str, ...] = tuple(name for name, _, _ in SPREADS) + (
    FLOOR_SPREAD[0], CEILING_SPREAD[0], "on_rrp_buffer_gone", "soma_weekly_change_total", "tga_change_bn")
#: The panel columns each indicator reads, for the availability declaration (`repo_liquidity.declaration`).
INPUTS: Dict[str, Tuple[str, ...]] = {
    **{name: (a, b) for name, a, b in SPREADS},
    FLOOR_SPREAD[0]: ("tgcr",),
    CEILING_SPREAD[0]: ("sofr",),
    "on_rrp_buffer_gone": ("on_rrp",),
    "soma_weekly_change_total": ("soma_treasury_weekly_change", "soma_mbs_weekly_change"),
    "tga_change_bn": ("tga",),
}
#: Answer 11: mandatory clearing of Treasury repo makes uncleared bilateral repo enter SOFR, so SOFR volume and
#: dispersion change meaning. Every column built on SOFR's distribution carries the break into the live filter.
MEASUREMENT_BREAKS = {
    "2027-06-30": ("sofr_volume", "sofr_p25", "sofr_p75", "sofr_p1", "sofr_p99", "sofr_p75_p25_bp",
                   "sofr_p99_p1_bp", "sofr_p1_minus_bgcr_bp"),
}
#: The day's close: a rate announced by then is public for that day's spread.
CLOSE = time(23, 59, 59)


def rate_known_by_close(rows: Sequence[scheduled.Publication], day: date) -> Optional[float]:
    """The rate in force on `day` by effective date, from a publication out by the close of `day`.

    Raises:
        LookAheadError: if the publication in force on `day` was announced after that day's close.
    """
    from repo_model.splits import LookAheadError

    row = max((r for r in rows if r.effective <= day), key=lambda r: r.effective, default=None)
    if row is None:
        return None
    close = datetime.combine(day, CLOSE, tzinfo=row.announced_at.tzinfo)
    if row.announced_at > close:
        raise LookAheadError(f"the rate in force on {day} was announced at {row.announced_at}, after that day's close")
    return row.values[0]


def _bp(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else round(100.0 * (a - b), 6)


def with_indicators(observations, *, floors: Sequence[scheduled.Publication] = None,
                    ceilings: Sequence[scheduled.Publication] = None) -> List:
    """Each row with `COLUMNS` added.

    Raises:
        ValueError: if a row already carries one of `COLUMNS`.
    """
    from repo_model.data import DailyObservation
    from repo_model.scarcity import buffer_level

    floors = scheduled.load_on_rrp_rates() if floors is None else floors
    ceilings = scheduled.load_srf_rates() if ceilings is None else ceilings
    out, previous = [], None
    for row in observations:
        values = row.values
        clash = sorted(set(COLUMNS) & {k for k, v in values.items()})
        if clash:
            raise ValueError(f"{row.date} already carries {clash}")
        added: Dict[str, Optional[float]] = {name: _bp(values.get(a), values.get(b)) for name, a, b in SPREADS}
        added[FLOOR_SPREAD[0]] = _bp(values.get(FLOOR_SPREAD[1]), rate_known_by_close(floors, row.date))
        ceiling = rate_known_by_close(ceilings, row.date) if row.date >= scheduled.SRF_INCEPTION else None
        added[CEILING_SPREAD[0]] = _bp(values.get(CEILING_SPREAD[1]), ceiling)
        on_rrp = values.get("on_rrp")
        added["on_rrp_buffer_gone"] = None if on_rrp is None else float(buffer_level(on_rrp))
        treasury, mbs = values.get("soma_treasury_weekly_change"), values.get("soma_mbs_weekly_change")
        added["soma_weekly_change_total"] = None if treasury is None or mbs is None else round(treasury + mbs, 6)
        tga, last = values.get("tga"), None if previous is None else previous.values.get("tga")
        added["tga_change_bn"] = None if tga is None or last is None else round(tga - last, 6)
        out.append(DailyObservation(date=row.date, values={**values, **added}))
        previous = row
    return out
