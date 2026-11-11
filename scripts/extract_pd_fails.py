#!/usr/bin/env python3
"""Cut the primary dealers' fails extract from the parent's tracked Primary Dealer Statistics export (#209).

    PYTHONPATH=src python3 scripts/extract_pd_fails.py           # write the extract and its manifest
    PYTHONPATH=src python3 scripts/extract_pd_fails.py --check   # exit 1 if the tracked files are not what the cut gives

The export is the parent's `nyfed_fr2004` snapshot at the pin (`repo_liquidity.pd_fails.PARENT_EXPORT`). The extract keeps the
`PDFTD-UST` and `PDFTR-UST` lines byte for byte, less each week published on a day the parent's lockbox holds
(`repo_liquidity.pd_fails`). Nothing is fetched.
"""

import argparse
import csv
import hashlib
import io
import json
import sys

from repo_liquidity import PARENT_COMMIT, development, parent_root, pd_fails


def build():
    export_path = parent_root() / pd_fails.PARENT_EXPORT
    export = export_path.read_bytes()
    parent_manifest = json.loads(export_path.with_name(export_path.name + ".manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(export).hexdigest() != parent_manifest["sha256"]:
        raise ValueError(f"{export_path.name} is not the bytes its manifest names")
    data, withheld = pd_fails.cut_extract(export)
    series = {}
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        item = series.setdefault(row["Time Series"], {"first": row["As Of Date"], "last": row["As Of Date"], "rows": 0})
        item["first"], item["last"] = min(item["first"], row["As Of Date"]), max(item["last"], row["As Of Date"])
        item["rows"] += 1
    manifest = {
        "export_path": pd_fails.PARENT_EXPORT,
        "export_sha256": parent_manifest["sha256"],
        "export_byte_count": parent_manifest["byte_count"],
        "export_retrieved_at": parent_manifest["retrieved_at"],
        "url": pd_fails.URL,
        "parent_commit": PARENT_COMMIT,
        "extract_sha256": hashlib.sha256(data).hexdigest(),
        "extract_byte_count": len(data),
        "kept": "the lines of PDFTD-UST and PDFTR-UST, copied byte for byte, less every week published on a day the parent's "
                "lockbox holds",
        "development_end": development.development_end().isoformat(),
        "withheld_weeks": [day.isoformat() for day in withheld],
        "series": series,
    }
    return data, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data, manifest = build()
    if args.check:
        same = pd_fails.EXTRACT.read_bytes() == data and pd_fails.MANIFEST.read_bytes() == manifest
        print("pd_fails extract: ok" if same else "pd_fails extract is stale: run scripts/extract_pd_fails.py")
        return 0 if same else 1
    pd_fails.DIR.mkdir(parents=True, exist_ok=True)
    pd_fails.EXTRACT.write_bytes(data)
    pd_fails.MANIFEST.write_bytes(manifest)
    print(f"wrote {pd_fails.EXTRACT} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
