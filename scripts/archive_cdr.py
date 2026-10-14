#!/usr/bin/env python3
"""Archive the FFIEC CDR "Call Reports -- Single Period" bulk files, with the time each was retrieved (#46).

    python3 -I scripts/archive_cdr.py --manifest archive/cdr/manifest.json --zips /path/to/zips [--quarters 2]

The CDR rebuilds every quarter's bulk file from its current content, so a first-filed figure cannot be recovered later
(`docs/research/slr-headroom-due-diligence.md`). This script downloads the latest `--quarters` quarter-ends listed on the
portal's bulk page (the form is a three-step ASP.NET post-back: choose the tab-delimited format, read the quarter-end list,
post the download) and keeps what it was served:

- a zip is stored as `<quarter-end>-<sha256>.zip` under `--zips` and is never overwritten (a stored file whose bytes are not
  its name raises `ValueError`);
- `manifest.json` gets, per distinct SHA-256 of a quarter, one entry: quarter, URL, file name, SHA-256, size,
  `first_retrieved_utc` and `last_checked_utc`. An unchanged file moves only `last_checked_utc`; a new SHA-256 is a new
  entry, and earlier entries are never rewritten otherwise.

A file is available from its `first_retrieved_utc`, never earlier (`archive/cdr/README.md`). Needs network access to
cdr.ffiec.gov. Standard library only. Nothing is scored.
"""

import argparse
import hashlib
import html
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
PRODUCT = "Call Reports -- Single Period"
FORMAT = "Tab Delimited"
FIELD = "ctl00$MainContentHolder$"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "archive/cdr/manifest.json"
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def hidden_fields(page):
    """The page's hidden form fields (`__VIEWSTATE` and its companions), unescaped."""
    fields = {k: html.unescape(v) for k, v in re.findall(r'<input type="hidden" name="(\w+)" id="\w+" value="([^"]*)"', page)}
    if "__VIEWSTATE" not in fields:
        raise ValueError("the page has no __VIEWSTATE: the portal did not return its form")
    return fields


def parse_quarters(page):
    """The quarter-ends in the dates list as (date, form value), newest first."""
    select = re.search(r"<select[^>]*DatesDropDownList.*?</select>", page, re.S)
    options = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*(\d\d)/(\d\d)/(\d{4})', select.group(0)) if select else []
    if not options:
        raise ValueError("the page lists no quarter-ends (the portal may be reporting technical difficulties)")
    return sorted(((date(int(y), int(m), int(d)), value) for value, m, d, y in options), reverse=True)


def check_zip(data, filename, quarter_end):
    """Refuse a response that is not a zip, or is named for another quarter-end."""
    if not data.startswith(b"PK"):
        raise ValueError(f"the download for {quarter_end} is not a zip")
    if f"{quarter_end:%m%d%Y}" not in filename:
        raise ValueError(f"the download for {quarter_end} is named {filename!r}")


class Portal:
    """One session on the CDR bulk page."""

    def __init__(self):
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self._opener.addheaders = [("User-Agent", "repo-market-liquidity (research)")]
        self._values = {}
        self._page = None

    def _open(self, fields=None):
        data = urllib.parse.urlencode(fields).encode() if fields is not None else None
        return self._opener.open(urllib.request.Request(URL, data=data), timeout=120)

    def _list(self):
        if self._page is None:
            first = self._open().read().decode("utf-8", "replace")
            fields = hidden_fields(first)
            fields.update({"__EVENTTARGET": FIELD + "TSVRadioButton", "__EVENTARGUMENT": "",
                           FIELD + "FormatType": "TSVRadioButton", FIELD + "ListBox1": "ReportingSeriesSinglePeriod"})
            self._page = self._open(fields).read().decode("utf-8", "replace")
            self._values = dict(parse_quarters(self._page))
        return self._page

    def quarters(self, count):
        self._list()
        return sorted(self._values, reverse=True)[:count]

    def download(self, quarter_end):
        fields = hidden_fields(self._list())
        fields.update({FIELD + "FormatType": "TSVRadioButton", FIELD + "ListBox1": "ReportingSeriesSinglePeriod",
                       FIELD + "DatesDropDownList": self._values[quarter_end],
                       FIELD + "TabStrip1$Download_0": "Download"})
        with self._open(fields) as response:
            disposition = response.headers.get("Content-Disposition", "")
            data = response.read()
        name = re.search(r'filename="?([^";]+)', disposition)
        return (name.group(1) if name else ""), data


def _load(manifest_path):
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    return {"source": URL, "product": PRODUCT, "format": FORMAT, "entries": []}


def archive(source, manifest_path, zips_dir, now, quarters=2):
    """Download the latest `quarters` quarter-ends from `source` and record them. Returns the new entries."""
    if now.tzinfo is None:
        raise ValueError("the retrieval time must be timezone-aware")
    stamp = now.astimezone(timezone.utc).strftime(STAMP)
    manifest, new = _load(manifest_path), []
    zips_dir.mkdir(parents=True, exist_ok=True)
    for quarter_end in source.quarters(quarters):
        filename, data = source.download(quarter_end)
        check_zip(data, filename, quarter_end)
        digest = hashlib.sha256(data).hexdigest()
        stored = zips_dir / f"{quarter_end.isoformat()}-{digest}.zip"
        if stored.exists():
            if hashlib.sha256(stored.read_bytes()).hexdigest() != digest:
                raise ValueError(f"{stored.name} is already stored with other bytes; it is never overwritten")
        else:
            stored.write_bytes(data)
        latest = [e for e in manifest["entries"] if e["quarter"] == quarter_end.isoformat()]
        if latest and latest[-1]["sha256"] == digest:
            latest[-1]["last_checked_utc"] = stamp
            continue
        entry = {"quarter": quarter_end.isoformat(), "url": URL, "file": stored.name, "download_name": filename,
                 "sha256": digest, "size": len(data), "first_retrieved_utc": stamp, "last_checked_utc": stamp}
        manifest["entries"].append(entry)
        new.append(entry)
    manifest["entries"].sort(key=lambda e: (e["quarter"], e["first_retrieved_utc"]))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--zips", type=Path, required=True, help="where the zips are stored (not tracked)")
    parser.add_argument("--quarters", type=int, default=2)
    args = parser.parse_args(argv)
    new = archive(Portal(), args.manifest, args.zips, datetime.now(timezone.utc), quarters=args.quarters)
    for entry in new:
        print(f"new: {entry['quarter']} {entry['sha256']} {entry['size']} bytes retrieved {entry['first_retrieved_utc']}")
    if not new:
        print("no new bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
