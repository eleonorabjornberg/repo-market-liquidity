"""The dispersion- and volume-based liquidity hypothesis, step 1 (#205): its inputs and two data guards.

`docs/research/dispersion-volume-hypothesis.md` is the draft page for Eleonora; the hypothesis carries a provisional
label and she names it. Nothing is fitted, scored or estimated here. This module holds:

* `INPUTS`, the inputs the hypothesis may read, each by the name of its declared feature (`repo_liquidity.declaration`),
  with its family and role. Every one is read through the parent's `asof.InformationRule`, which applies the lag its
  source declares. One input is primary (Eleonora's ruling of 9 November 2026: both families are inputs and one is
  primary; the page gives the reason and marks it as a question for her).
* the 2027-06-30 measurement break (`docs/decisions/data-meaning.md`, answer 11): mandatory clearing of Treasury repo
  changes what SOFR's volume and dispersion measure. Draft default: no input affected is read across the break until she
  declares a re-based series (`check_not_across_break`).
* the one input with a first usable day (`check_usable`): the OFR's DVP volume.

Standard library only, apart from the parent.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, NamedTuple, Tuple

from repo_liquidity import indicators


class Input(NamedTuple):
    #: The declared feature (`declaration.FIELDS`), which is also the panel column where the panel builds one.
    name: str
    #: "dispersion" (a width of a rate distribution, in basis points) or "volume" (a repo volume, in USD).
    family: str
    #: "primary" (exactly one), "secondary" or "context".
    role: str


INPUTS: Tuple[Input, ...] = (
    # Primary: the interquartile width of SOFR. It leaves out the 1st and 99th percentiles, which the data-meaning
    # record reads as a noisy specials proxy on the collateral axis (answer 8), kept apart from cash scarcity.
    Input("sofr_p75_p25_bp", "dispersion", "primary"),
    Input("sofr_p99_p1_bp", "dispersion", "secondary"),
    Input("sofr_volume", "volume", "secondary"),
    Input("bgcr_volume", "volume", "secondary"),
    # Off in every published declaration of the parent; switched on here for development only. The OFR keeps no
    # vintages and the volume is its final figure, so it is not a first print (page, section 3).
    Input("ofr_dvp_volume", "volume", "context"),
)

#: The OFR began publishing its repo data in real time on 2020-09-09; values dated before were filled in afterwards
#: (`ofr_stfm_repo.release_lag.note`, parent `metadata/sources.json` at the pin; `repo_model.dvp_segment`).
FIRST_USABLE: Dict[str, date] = {"ofr_dvp_volume": date(2020, 9, 9)}

#: Mandatory clearing of Treasury repo (`docs/decisions/data-meaning.md`, answer 11; `indicators.MEASUREMENT_BREAKS`).
BREAK = date.fromisoformat(next(iter(indicators.MEASUREMENT_BREAKS)))
#: The register's columns, then the two volumes this step adds. Whether BGCR's volume is affected is a data-meaning
#: question the page marks for her; until she rules, it is treated as broken, and so is the OFR's DVP volume, whose
#: segment is the one mandatory clearing moves.
BREAK_COLUMNS = frozenset(indicators.MEASUREMENT_BREAKS[BREAK.isoformat()]) | {"bgcr_volume", "ofr_dvp_volume"}


def check_not_across_break(column: str, first: date, last: date) -> None:
    """Refuse a window of `column` that holds days on both sides of the break.

    The break day is the first day under the new meaning, so a window from `first` to `last` (inclusive) straddles it
    when `first` is before it and `last` is on or after it.

    Raises:
        ValueError: if the window runs backwards, or `column` is one the break affects and the window straddles it.
    """
    if last < first:
        raise ValueError(f"{column}: the window runs backwards ({first} to {last})")
    if column in BREAK_COLUMNS and first < BREAK <= last:
        raise ValueError(f"{column}: the window {first} to {last} reads across the {BREAK} measurement break; "
                         f"no re-based series is declared")


def check_usable(column: str, day: date) -> None:
    """Refuse a value dated before the column's first usable day.

    Raises:
        LookAheadError: if `day` is before `FIRST_USABLE[column]`: the value was filled in after the day, so it was not
            public on it.
    """
    from repo_model.splits import LookAheadError

    first = FIRST_USABLE.get(column)
    if first is not None and day < first:
        raise LookAheadError(f"{column} dated {day} was filled in after the day; its first usable day is {first}")
