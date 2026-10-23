#!/usr/bin/env python3
"""Store the Desk's operational-details page and cut the monthly reserve management purchase amounts from it (#158, G7).

    # 1. Fetch with one plain request per file, as fetched (no retries that change the bytes):
    curl -sS -A "repo-market-liquidity research" -o details.html \\
        https://www.newyorkfed.org/markets/domestic-market-operations/monetary-policy-implementation/treasury-securities/treasury-securities-operational-details
    #    and each monthly schedule PDF the page links, into one directory, under its own name (HTPC_<mmdd>_<mmdd>_<yyyy>.pdf)
    PYTHONPATH=src python3 scripts/extract_rmp.py capture details.html pdfs/ --retrieved-utc 2026-10-23T17:08:02Z

    # 2. Check that the tracked files are what the stored page gives:
    PYTHONPATH=src python3 scripts/extract_rmp.py check

`capture` stores the page as `tests/fixtures/snapshots/fomc_notes/pages/treasury_operational_details_<yyyymmdd>.htm.gz`
(gzip of the bytes as fetched, no header time), writes `rmp_schedule.csv` and its manifest, and appends one row per
period to `announced_purchases.csv` (rows already there are left alone). It needs `pdfinfo` (poppler) only to read each PDF's
creation time. `check` needs neither: it rebuilds the schedule from the stored page and the evidence columns already
tracked, and compares bytes.

The page states each month's planned amounts but no publication time. The Desk publishes them "on or around the ninth
business day of each month" (its 10 December 2025 statement), which is before every period starts. A row is therefore
dated the end of the last business day before its period starts (conservative: it is read from the day after), and the
schedule PDF's own creation time is recorded beside it as evidence (a PDF created after its period began was re-created with
the results and is no evidence of the date). Nothing announced after the parent's development end is entered. Standard
library only, apart from `pdfinfo`.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from repo_liquidity import announced_pace, contenthash, development, scheduled

ROOT = Path(__file__).resolve().parents[1]
PAGES = scheduled.NOTES / "pages"
URL = ("https://www.newyorkfed.org/markets/domestic-market-operations/monetary-policy-implementation/"
       "treasury-securities/treasury-securities-operational-details")
SITE = "https://www.newyorkfed.org"
DESK_STATEMENT = "operating_policy_251210a.htm.gz"
DESK_STATEMENT_URL = "https://www.newyorkfed.org/markets/opolicy/operating_policy_251210a"
FIRST_START = date(2025, 12, 12)
NEW_YORK = ZoneInfo("America/New_York")
COLUMNS = ("period_start", "period_end", "rmp_bn", "reinvestment_bn", "announcement_date", "announcement_time", "timezone",
           "basis", "evidence_kind", "evidence_url", "evidence_created_utc", "evidence_sha256", "page", "fetch_sha256",
           "content_sha256")
PERIOD = re.compile(r"(\d{1,2}/\d{1,2}/\d{4}) - (\d{1,2}/\d{1,2}/\d{4}) (The Desk plans to conduct approximately "
                    r"\$(?P<reinv>[\d.]+) billion in reinvestment purchases (?:and an additional approximately "
                    r"\$(?P<rmp>[\d.]+) billion in reserve management purchases|and no reserve management purchases) "
                    r"over the noted monthly period)\.")


def _text(raw: bytes) -> str:
    body = re.sub(r"(?s)<(script|style).*?</\1>", "", raw.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))


def _us(text: str) -> date:
    month, day, year = (int(part) for part in text.split("/"))
    return date(year, month, day)


def _previous_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def periods(raw: bytes):
    """The periods of the page from 12 December 2025 whose publication is not past the development end, oldest first."""
    end = development.development_end()
    out = []
    for match in PERIOD.finditer(_text(raw)):
        start, last = _us(match.group(1)), _us(match.group(2))
        if start < FIRST_START:
            continue
        announced = date(2025, 12, 10) if start == FIRST_START else _previous_weekday(start)
        if end is not None and announced > end:
            continue
        out.append({"start": start, "end": last, "rmp": match.group("rmp") or "0", "reinv": match.group("reinv"),
                    "announced": announced, "sentence": match.group(3),
                    "phrase_dates": f"{match.group(1)} - {match.group(2)}"})
    out.sort(key=lambda item: item["start"])
    return out


def _pdf_href(raw: bytes, start: date, last: date) -> str:
    name = f"HTPC_{start:%m%d}_{last:%m%d}_{last.year}.pdf"
    found = re.search(r'href="([^"]*/' + re.escape(name) + r')"', raw.decode("utf-8", errors="replace"))
    if not found:
        raise ValueError(f"the page links no schedule PDF {name}")
    return found.group(1)


def _created_utc(pdf: Path) -> str:
    info = subprocess.run(["pdfinfo", "-isodates", str(pdf)], check=True, capture_output=True, text=True).stdout
    stamp = re.search(r"^CreationDate:\s*(\S+)", info, re.M).group(1)
    return datetime.fromisoformat(stamp).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _content(item) -> str:
    return contenthash.content_sha256(announced_pace.RMP_CONTENT_COLUMNS,
                                      [[item["start"].isoformat(), item["end"].isoformat(), item["rmp"], item["reinv"]]],
                                      announced_pace.RMP_PLACES)


def _row(item, page: str, fetch: str, evidence) -> list:
    kind, url, created, digest = evidence
    return [item["start"].isoformat(), item["end"].isoformat(), item["rmp"], item["reinv"], item["announced"].isoformat(),
            "23:59", "America/New_York",
            "desk_statement" if kind == "statement" else "end_of_last_business_day_before_period", kind, url, created,
            digest, page, fetch, _content(item)]


def _table(rows) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def _purchase_row(item, page: str) -> list:
    note = (f"Reserve management purchases of approximately ${item['rmp']} billion for the monthly period "
            f"{item['phrase_dates']} on the Desk's operational-details page. Reinvestment purchases (approximately "
            f"${item['reinv']} billion) are reserve-neutral and enter at 0 (Eleonora's ruling of 19 October 2026 on #130). "
            "The page states no publication time: the row is read from the end of the last business day before the period "
            "starts, the Desk publishing 'on or around the ninth business day of each month' (see rmp_schedule.csv).")
    return [item["announced"].isoformat(), "23:59", "America/New_York", item["start"].isoformat(), "stated",
            "quantified", item["rmp"], "0", item["sentence"], item["phrase_dates"], note, URL, page, ""]


def _evidence(item, raw, pdf_dir):
    """(kind, url, created UTC, sha256) of the schedule PDF, read from `pdf_dir`."""
    if item["start"] == FIRST_START:
        digest = hashlib.sha256((PAGES / DESK_STATEMENT).read_bytes()).hexdigest()
        return "statement", DESK_STATEMENT_URL, "", digest
    href = _pdf_href(raw, item["start"], item["end"])
    pdf = pdf_dir / href.rsplit("/", 1)[1]
    created = _created_utc(pdf)
    local = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(NEW_YORK).date()
    kind = "pdf_created_before_start" if local < item["start"] else "pdf_recreated_after_start"
    return kind, SITE + href, created, hashlib.sha256(pdf.read_bytes()).hexdigest()


def capture(page_file: Path, pdf_dir: Path, retrieved: str) -> int:
    raw = page_file.read_bytes()
    name = f"treasury_operational_details_{retrieved[:10].replace('-', '')}.htm.gz"
    stored = PAGES / name
    if stored.exists():
        print(f"{name} is already stored; a stored page is never overwritten", file=sys.stderr)
        return 1
    stored.write_bytes(gzip.compress(raw, mtime=0))
    fetch = hashlib.sha256(stored.read_bytes()).hexdigest()
    items = periods(raw)
    rows = [_row(item, name, fetch, _evidence(item, raw, pdf_dir)) for item in items]
    announced_pace.RMP_TABLE.write_bytes(_table(rows))
    print(f"rmp_schedule.csv: {scheduled.write_manifest(announced_pace.RMP_TABLE)} ({len(rows)} periods)")
    existing = announced_pace.PURCHASES_TABLE.read_text(encoding="utf-8")
    have = {row["effective_date"] for row in csv.DictReader(io.StringIO(existing))}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for item in items:
        if item["start"].isoformat() not in have:
            writer.writerow(_purchase_row(item, name))
    announced_pace.PURCHASES_TABLE.write_text(existing + out.getvalue(), encoding="utf-8")
    print(f"announced_purchases.csv: {scheduled.write_manifest(announced_pace.PURCHASES_TABLE)}")
    return 0


def check() -> int:
    tracked = list(csv.DictReader(announced_pace.RMP_TABLE.open(encoding="utf-8")))
    page = tracked[0]["page"]
    raw = gzip.decompress((PAGES / page).read_bytes())
    fetch = hashlib.sha256((PAGES / page).read_bytes()).hexdigest()
    by_start = {row["period_start"]: row for row in tracked}
    rows = []
    for item in periods(raw):
        old = by_start[item["start"].isoformat()]
        rows.append(_row(item, page, fetch, (old["evidence_kind"], old["evidence_url"], old["evidence_created_utc"],
                                             old["evidence_sha256"])))
    same = _table(rows) == announced_pace.RMP_TABLE.read_bytes()
    print("rmp_schedule.csv is what the stored page gives" if same else "rmp_schedule.csv is stale")
    return 0 if same else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture")
    cap.add_argument("page", type=Path)
    cap.add_argument("pdfs", type=Path)
    cap.add_argument("--retrieved-utc", required=True)
    commands.add_parser("check")
    args = parser.parse_args(argv)
    return capture(args.page, args.pdfs, args.retrieved_utc) if args.command == "capture" else check()


if __name__ == "__main__":
    sys.exit(main())
