"""Phase 3 panel version 6: the columns derived on each row for H10's second declaration (#209, step 2).

`docs/decisions/h10-method-2.md` section 1. Version 6 is version 5's build at the same pin with the second declaration's inputs
added (`repo_liquidity.panel`); this module holds what is computed on a row from the row's own values:

- `sofr_p99_p1_bp`, `100 x (SOFR_p99 - SOFR_p1)` in bp (`indicators.SPREADS`);
- `fed_repo_material_use`, the 2019 to 2021 term repo event of data-meaning row 14, from the parent's repo operation results
  (`repo_model.fed_liquidity`, `nyfed_repo_ops`: the New York Fed's repo operation results, declared 16:00 on the next business
  day, as `nyfed_temp_repo` is). It is 1 on an operation date whose accepted amount, overnight and term alike, is $1bn or more.
  Before the facility's first day (2019-09-17) no Fed repo was offered, so it is 0. From 2019-09-17 to 2021-07-28 a date
  with no operation is missing, never zero (the Desk operated every business day, and nothing says nothing was demanded); from
  the standing facility's first day (2021-07-29) a date with no operation is zero, as the parent reads it;
- `facility_material_use`, the facility event: `h10_drivers_2.facility_event(srf_take_up, fed_repo_material_use)` on each row,
  with the standing facility's take-up a structural zero before it existed (the panel carries no `srf_take_up` before 2021-07-29,
  831 rows, so that the term repo operations alone decide a day of 2019 to 2021).

Each column is read, under the parent's as-of rule, at the declarations of its source fields (`declaration.FIELDS`); a column
derived on a row from values of the same row is public when the latest of its inputs is. Standard library only.
"""

from __future__ import annotations

from datetime import date
from typing import List, Mapping, Optional, Sequence

from repo_model.ingest import REPO_FACILITY_START

from repo_liquidity import h10_drivers_2, indicators, scheduled

#: The standing facility's first day: no `srf_take_up` before it, and no standing-facility use.
SRF_INCEPTION = scheduled.SRF_INCEPTION
FIRST_REPO_OPERATION = REPO_FACILITY_START
#: Material use, USD bn (data-meaning rows 13 and 14), the same threshold as the standing facility's.
MATERIAL_USE_BN = h10_drivers_2.SRF_MATERIAL_BN
ADDED_DERIVED = ("sofr_p99_p1_bp", "fed_repo_material_use", "facility_material_use")


def fed_repo_material_use(day: date, accepted: Mapping[date, float]) -> Optional[float]:
    """The term repo event on `day`: 1.0 if the Desk accepted `MATERIAL_USE_BN` or more on it, else 0.0, else missing.

    `accepted` is the amount accepted per operation date, USD bn, overnight and term alike (`fed_liquidity`, series
    `repo_accepted`). A day before `FIRST_REPO_OPERATION` is 0.0 whatever `accepted` holds (the six operations of $64-66 million
    before it are tests); from `FIRST_REPO_OPERATION` to the day before `SRF_INCEPTION` a day with no operation is None; from
    `SRF_INCEPTION` it is 0.0."""
    if day < FIRST_REPO_OPERATION:
        return 0.0
    value = accepted.get(day)
    if value is None:
        return 0.0 if day >= SRF_INCEPTION else None
    return 1.0 if value >= MATERIAL_USE_BN else 0.0


def facility_for_row(day: date, row: Mapping[str, Optional[float]]) -> Optional[float]:
    """The facility event on one row (`h10_drivers_2.facility_event`), with the standing facility's take-up a structural zero
    before `SRF_INCEPTION`. After it a missing `srf_take_up` is not read as zero."""
    standing = row.get("srf_take_up")
    if standing is None and day < SRF_INCEPTION:
        standing = 0.0
    return h10_drivers_2.facility_event(standing, row.get("fed_repo_material_use"))


def with_v6_columns(observations: Sequence, accepted: Mapping[date, float]) -> List:
    """Each row with `ADDED_DERIVED` added.

    Raises:
        ValueError: a row already carries one of them.
    """
    from repo_model.data import DailyObservation

    out = []
    for row in observations:
        clash = [column for column in ADDED_DERIVED if column in row.values]
        if clash:
            raise ValueError(f"{row.date} already carries {clash}")
        values = dict(row.values)
        values["sofr_p99_p1_bp"] = indicators._bp(values.get("sofr_p99"), values.get("sofr_p1"))
        values["fed_repo_material_use"] = fed_repo_material_use(row.date, accepted)
        values["facility_material_use"] = facility_for_row(row.date, values)
        out.append(DailyObservation(row.date, values))
    return out
