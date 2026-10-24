"""The announced balance-sheet pace: the runoff caps less the announced purchases (#125, avenue #56; H7 groundwork).

`runoff_caps` is the maximum pace at which holdings may run off. It reads (0, 0) from 1 August 2019 and again from
1 December 2025, so it shows a flat balance sheet there, while the Fed was adding reserves by buying securities. This
module joins the caps with the purchases the Fed announced, one row per announcement:

- the Treasury and MBS runoff caps in force (from `runoff_caps.csv`, never entered by hand);
- the announced monthly net purchases of Treasury securities and of agency MBS, in $bn (`announced_purchases.csv`,
  each row read from a saved federalreserve.gov or newyorkfed.org page);
- the signed pace, caps minus purchases, in $bn a month: positive means the balance sheet drains, negative that it grows.

Values hold between announcements and are never revised. A row is read at a decision instant only if it was announced at
or before it and is effective on or before the day (the parent's scheduled-availability rule, as for `scheduled`).

**What enters the purchases.** Reserve management and net asset purchases enter; reinvestment of principal payments
does not, because it holds reserves constant. MBS paydowns above the MBS cap that the Fed reinvests in Treasuries
therefore enter at 0 (decided by Eleonora, 19 October 2026, ruling on #130).

**The monthly amounts after December 2025** are the reserve management purchases the Desk's operational-details page
states for each monthly period (#158; Eleonora's ruling of 21 October 2026 on #156). Each is read as of its publication
instant and from the period's start; `rmp_schedule.csv` keeps the page's fetch hash and the values' content hash, and
`load_rmp_schedule` checks them. The page states no publication time: a period is taken as published at the end of the last
business day before it starts, and never before the schedule PDF that states it was created.

**Where no monthly amount was announced** the row is `unquantified` and its purchases and signed pace are empty: the
March 2020 plan ("at least $500 billion ... over coming months", then "in the amounts needed"), and the days from 12 January
2026 until the January 2026 amount was public (16 January). A reader gets `None` for the signed pace there, never a
carried-forward amount.

Nothing is wired into an estimator, a score or the panel: H7 steps consume it later. Standard library only.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from repo_liquidity import contenthash, scheduled

PACE_TABLE = scheduled.NOTES / "announced_pace.csv"
PURCHASES_TABLE = scheduled.NOTES / "announced_purchases.csv"
#: The monthly reserve management purchase amounts of the Desk's operational-details page, with the page's fetch hash and
#: the values' content hash (#158; `scripts/extract_rmp.py`).
RMP_TABLE = scheduled.NOTES / "rmp_schedule.csv"
RMP_CONTENT_COLUMNS = ("period_start", "period_end", "rmp_bn", "reinvestment_bn")
RMP_PLACES = {"rmp_bn": 3, "reinvestment_bn": 3}
_RMP_KINDS = ("statement", "pdf_created_before_start", "pdf_recreated_after_start")

PACE_COLUMNS = ("announcement_date", "announcement_time", "timezone", "effective_date", "treasury_cap_bn", "mbs_cap_bn",
                "treasury_purchases_bn", "mbs_purchases_bn", "signed_pace_bn", "status", "effective_basis", "source_url",
                "page")
QUANTIFIED = "quantified"
UNQUANTIFIED = "unquantified"
#: The Board's statements are under this address; the saved page of a cap row names its file.
_BOARD = "https://www.federalreserve.gov/newsevents/pressreleases/"


class Purchase(NamedTuple):
    """One announcement of purchases (a row of `announced_purchases.csv`)."""

    announced_at: datetime
    effective: date
    basis: str
    status: str
    purchases: Optional[Tuple[float, float]]
    amount_phrases: Tuple[str, ...]
    date_phrase: str
    note: str
    source_url: str
    page: str
    also_page: str


class RmpPeriod(NamedTuple):
    """One monthly operation period of the Desk's operational-details page (a row of `rmp_schedule.csv`)."""

    start: date
    end: date
    rmp_bn: float
    reinvestment_bn: float
    announced_at: datetime
    basis: str
    evidence_kind: str
    evidence_url: str
    evidence_created: Optional[datetime]
    evidence_sha256: str
    page: str
    fetch_sha256: str
    content_sha256: str


class Pace(NamedTuple):
    """One row of `announced_pace.csv`: the state in force from `effective`, announced at `announced_at`."""

    announced_at: datetime
    effective: date
    caps: Tuple[float, float]
    purchases: Optional[Tuple[float, float]]
    signed: Optional[float]
    status: str
    basis: str
    source_url: str
    page: str


def _moment(row: dict) -> datetime:
    if row["timezone"] != "America/New_York":
        raise ValueError(f"timezone {row['timezone']!r}")
    return datetime.combine(date.fromisoformat(row["announcement_date"]), time.fromisoformat(row["announcement_time"]))


def _amount(text: str) -> Optional[float]:
    return None if text == "" else float(text)


def load_purchases() -> List[Purchase]:
    """The announced purchases, in file order.

    Raises:
        ValueError: if the table does not match its manifest, a row is unquantified with an amount or quantified without
            one, or a row takes effect on or before its announcement day.
    """
    out = []
    for row in scheduled._verified_rows(PURCHASES_TABLE):
        announced, effective = _moment(row), date.fromisoformat(row["effective_date"])
        if effective <= announced.date():
            raise ValueError(f"{PURCHASES_TABLE.name}: effective {effective} is not after its announcement {announced}")
        amounts = (_amount(row["treasury_purchases_bn"]), _amount(row["mbs_purchases_bn"]))
        if row["status"] == QUANTIFIED and None in amounts:
            raise ValueError(f"{PURCHASES_TABLE.name}: the quantified row of {effective} has no amount")
        if row["status"] == UNQUANTIFIED and amounts != (None, None):
            raise ValueError(f"{PURCHASES_TABLE.name}: the unquantified row of {effective} carries an amount")
        if row["status"] not in (QUANTIFIED, UNQUANTIFIED):
            raise ValueError(f"{PURCHASES_TABLE.name}: status {row['status']!r}")
        out.append(Purchase(announced, effective, row["effective_basis"], row["status"],
                            None if row["status"] == UNQUANTIFIED else amounts,
                            tuple(p.strip() for p in row["amount_phrase"].split("||") if p.strip()), row["date_phrase"],
                            row["note"], row["source_url"], row["page"], row["also_page"]))
    return out


def load_rmp_schedule(path: Path = RMP_TABLE) -> List[RmpPeriod]:
    """The monthly reserve management purchase periods, in file order (#158).

    Each amount is public from its publication instant, which the page does not state: a Desk statement's own day, or
    the end of the last business day before the period starts (the Desk publishes "on or around the ninth business
    day"). The schedule PDF's creation time is kept beside it, and a publication instant before that is refused.

    Raises:
        ValueError: if the table does not match its manifest, a row's content hash does not give its values, its fetch
            hash is not the saved page's, a period does not start after its announcement day, or its evidence is
            labelled inconsistently with its dates.
        LookAheadError: if a period is published before the schedule that states it was created.
    """
    from repo_model.splits import LookAheadError

    out = []
    for row in scheduled._verified_rows(path):
        announced = _moment({"timezone": row["timezone"], "announcement_date": row["announcement_date"],
                             "announcement_time": row["announcement_time"]})
        start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
        if start <= announced.date() or end < start:
            raise ValueError(f"{path.name}: the period {start} to {end} is not after its announcement {announced}")
        content = contenthash.content_sha256(RMP_CONTENT_COLUMNS, [[row[c] for c in RMP_CONTENT_COLUMNS]], RMP_PLACES)
        if content != row["content_sha256"]:
            raise ValueError(f"{path.name}: {start} stores content_sha256 {row['content_sha256']!r}, the values give "
                             f"{content!r}")
        saved = scheduled.NOTES / "pages" / row["page"]
        if not saved.exists() or hashlib.sha256(saved.read_bytes()).hexdigest() != row["fetch_sha256"]:
            raise ValueError(f"{path.name}: {start} names a fetch_sha256 that is not the saved page {row['page']}")
        kind = row["evidence_kind"]
        if kind not in _RMP_KINDS:
            raise ValueError(f"{path.name}: evidence_kind {kind!r}")
        created = None
        if kind != "statement":
            created = datetime.fromisoformat(row["evidence_created_utc"].replace("Z", "+00:00"))
            made = created.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
            if (kind == "pdf_created_before_start") != (made.date() < start):
                raise ValueError(f"{path.name}: {start} is labelled {kind} but its schedule was made {made}")
            if kind == "pdf_created_before_start" and announced < made:
                raise LookAheadError(f"the period starting {start} is published {announced}, before its schedule was "
                                     f"created {made}")
        out.append(RmpPeriod(start, end, float(row["rmp_bn"]), float(row["reinvestment_bn"]), announced, row["basis"], kind,
                             row["evidence_url"], created, row["evidence_sha256"], row["page"], row["fetch_sha256"],
                             row["content_sha256"]))
    return out


def _signed(caps: Tuple[float, float], purchases: Optional[Tuple[float, float]]) -> Optional[float]:
    if purchases is None:
        return None
    return float(Decimal(str(caps[0])) + Decimal(str(caps[1])) - Decimal(str(purchases[0])) - Decimal(str(purchases[1])))


def build_rows(caps: Sequence[scheduled.Publication], purchases: Sequence[Purchase]) -> List[Pace]:
    """One row per announcement of a cap or a purchase, in the order they take effect.

    Each row carries the caps and the purchases in force from its effective date. Before the first purchase announcement
    the purchases are 0 (only reinvestment, which holds reserves constant).

    Raises:
        ValueError: if a purchase takes effect before the first cap, or a row would carry a cap or a purchase
            announced after the row itself (the row would then be read before all of what it states was public).
    """
    events = [(c.effective, c.announced_at, "cap", c) for c in caps] + \
             [(p.effective, p.announced_at, "purchase", p) for p in purchases]
    events.sort(key=lambda event: (event[0], event[1], event[2]))
    cap_event = purchase_event = None
    rows: List[Pace] = []
    for effective, announced, kind, event in events:
        if kind == "cap":
            cap_event = event
        else:
            purchase_event = event
        if cap_event is None:
            raise ValueError(f"the purchase effective {effective} takes effect before the first cap")
        held = (0.0, 0.0) if purchase_event is None else purchase_event.purchases
        latest = max(cap_event.announced_at, announced if purchase_event is None else purchase_event.announced_at)
        if latest > announced:
            raise ValueError(f"the row announced {announced} would carry a value announced at {latest}")
        status = QUANTIFIED if purchase_event is None else purchase_event.status
        if kind == "cap":
            basis, url, page = "stated", _BOARD + event.page.removesuffix(".gz"), event.page
        else:
            basis, url, page = event.basis, event.source_url, event.page
        rows.append(Pace(announced, effective, cap_event.values, held, _signed(cap_event.values, held), status, basis,
                         url, page))
    return rows


def _number(value: Optional[float]) -> str:
    return "" if value is None else format(Decimal(str(value)).normalize(), "f")


def table_bytes(rows: Sequence[Pace]) -> bytes:
    """The bytes of `announced_pace.csv` for `rows`."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(PACE_COLUMNS)
    for row in rows:
        purchases = row.purchases if row.status == QUANTIFIED else (None, None)
        writer.writerow([row.announced_at.date().isoformat(), row.announced_at.strftime("%H:%M"), "America/New_York",
                         row.effective.isoformat(), _number(row.caps[0]), _number(row.caps[1]), _number(purchases[0]),
                         _number(purchases[1]), _number(row.signed), row.status, row.basis, row.source_url, row.page])
    return out.getvalue().encode("utf-8")


def build_table_bytes() -> bytes:
    """The table as rebuilt from `runoff_caps.csv` and `announced_purchases.csv`."""
    return table_bytes(build_rows(scheduled.load_runoff_caps(), load_purchases()))


def load_announced_pace() -> List[Pace]:
    """The published table, as `Pace` rows.

    Raises:
        ValueError: if the table does not match its manifest or an effective date is not after its announcement day.
    """
    out = []
    for row in scheduled._verified_rows(PACE_TABLE):
        announced, effective = _moment(row), date.fromisoformat(row["effective_date"])
        if effective <= announced.date():
            raise ValueError(f"{PACE_TABLE.name}: effective {effective} is not after its announcement {announced}")
        caps = (float(row["treasury_cap_bn"]), float(row["mbs_cap_bn"]))
        quantified = row["status"] == QUANTIFIED
        purchases = (float(row["treasury_purchases_bn"]), float(row["mbs_purchases_bn"])) if quantified else None
        signed = float(row["signed_pace_bn"]) if quantified else None
        out.append(Pace(announced, effective, caps, purchases, signed, row["status"], row["effective_basis"],
                        row["source_url"], row["page"]))
    return out


def _in_force(rows: Sequence[Pace], instant: datetime, day: date) -> Optional[Pace]:
    """The latest row announced at or before `instant` and effective on or before `day`."""
    known = [row for row in rows if row.announced_at <= instant and row.effective <= day]
    if not known:
        return None
    return max(known, key=lambda row: (row.effective, row.announced_at))


def check_read(rows: Sequence[Pace], instant: datetime, day: date, *, used: Optional[Pace]) -> None:
    """Refuse a read of `used` for `day` at the decision `instant` that the information-set rule does not allow.

    Raises:
        LookAheadError: if `used` was announced after `instant`.
        StaleReadError: if a row announced at or before `instant` and effective on or before `day` is newer than `used`
            (or `used` is None while one exists).
    """
    from repo_model.asof import StaleReadError
    from repo_model.splits import LookAheadError

    if used is not None and used.announced_at > instant:
        raise LookAheadError(f"the pace announced {used.announced_at} is read at {instant}, before it was public")
    admissible = [row for row in rows if row.announced_at <= instant and row.effective <= day]
    if admissible:
        newest = max(admissible, key=lambda row: (row.effective, row.announced_at))
        if used is None or (used.effective, used.announced_at) < (newest.effective, newest.announced_at):
            raise StaleReadError(f"the pace effective {None if used is None else used.effective} is read on {day}, "
                                 f"after the pace effective {newest.effective} was announced")


def read(rows: Sequence[Pace], instant: datetime, day: date) -> Optional[Pace]:
    """The pace in force on `day` as public at `instant`, checked by `check_read`; None before the first cap.

    Raises:
        LookAheadError, StaleReadError: from `check_read`, if the selection broke the information-set rule.
    """
    used = _in_force(rows, instant, day)
    check_read(rows, instant, day, used=used)
    return used


def pace_values(dates: Sequence[date], *, decision_time: time, rows: Optional[Sequence[Pace]] = None) -> List[Optional[Pace]]:
    """The pace in force on each date, read at that date's decision instant (the panel day before, at `decision_time`).

    The first date has no earlier panel day and reads None, as the other scheduled inputs do.
    """
    rows = load_announced_pace() if rows is None else rows
    moment = decision_time.replace(tzinfo=None)
    out: List[Optional[Pace]] = [None]
    for index in range(1, len(dates)):
        out.append(read(rows, datetime.combine(dates[index - 1], moment), dates[index]))
    return out
