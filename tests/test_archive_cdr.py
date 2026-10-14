"""The scheduled CDR bulk-file archive (`scripts/archive_cdr.py`, #46; groundwork G5 for H7m, candidate D).

The FFIEC CDR rebuilds each quarter's "Call Reports -- Single Period" bulk file from its current content, so a first-filed
figure is not recoverable later (`docs/research/slr-headroom-due-diligence.md`, PR #44). The archive keeps what the portal
served, when. These tests use a saved copy of the portal's page after the tab-delimited format is chosen
(`fixtures/cdr/bulk_page_tsv_selected.html.gz`) and fake zip bytes; nothing here touches the network.
"""

import gzip
import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("archive_cdr", ROOT / "scripts" / "archive_cdr.py")
archive_cdr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive_cdr)

PAGE = gzip.decompress((ROOT / "tests/fixtures/cdr/bulk_page_tsv_selected.html.gz").read_bytes()).decode("utf-8")
T1 = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)
Q2, Q1 = date(2026, 6, 30), date(2026, 3, 31)


class FakeSource:
    """What the portal serves: bytes per quarter-end, changeable between runs."""

    def __init__(self, **served):
        self.served = {date.fromisoformat(k.replace("_", "-")): v for k, v in served.items()}

    def quarters(self, count):
        return sorted(self.served, reverse=True)[:count]

    def download(self, quarter_end):
        return f"FFIEC CDR Call Bulk All Schedules {quarter_end:%m%d%Y}.zip", self.served[quarter_end]


def zipish(tag):
    return b"PK\x03\x04" + tag.encode()


class ParsePageTests(unittest.TestCase):
    def test_quarter_ends_are_read_newest_first_with_their_form_values(self):
        listing = archive_cdr.parse_quarters(PAGE)
        self.assertEqual(listing[0], (date(2026, 6, 30), "152"))
        self.assertEqual(listing[1], (date(2026, 3, 31), "151"))
        self.assertEqual([d for d, _ in listing], sorted((d for d, _ in listing), reverse=True))

    def test_a_page_without_the_dates_list_is_refused(self):
        with self.assertRaises(ValueError):
            archive_cdr.parse_quarters("<html>The system is currently experiencing technical difficulties.</html>")

    def test_hidden_fields_carry_the_view_state(self):
        fields = archive_cdr.hidden_fields(PAGE)
        self.assertIn("__VIEWSTATE", fields)
        self.assertIn("__VIEWSTATEGENERATOR", fields)

    def test_a_download_that_is_not_a_zip_is_refused(self):
        with self.assertRaises(ValueError):
            archive_cdr.check_zip(b"<html>error</html>", "FFIEC CDR Call Bulk All Schedules 06302026.zip", Q2)

    def test_a_download_named_for_another_quarter_is_refused(self):
        with self.assertRaises(ValueError):
            archive_cdr.check_zip(zipish("x"), "FFIEC CDR Call Bulk All Schedules 03312026.zip", Q2)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.manifest = self.root / "manifest.json"
        self.zips = self.root / "zips"

    def run_archive(self, source, now, quarters=2):
        return archive_cdr.archive(source, self.manifest, self.zips, now, quarters=quarters)

    def entries(self):
        return json.loads(self.manifest.read_text())["entries"]

    def test_first_run_records_time_hash_size_and_quarter_for_each_download(self):
        a, b = zipish("june"), zipish("march")
        self.run_archive(FakeSource(**{"2026_06_30": a, "2026_03_31": b}), T1)
        by_quarter = {e["quarter"]: e for e in self.entries()}
        self.assertEqual(set(by_quarter), {"2026-06-30", "2026-03-31"})
        june = by_quarter["2026-06-30"]
        self.assertEqual(june["sha256"], hashlib.sha256(a).hexdigest())
        self.assertEqual(june["size"], len(a))
        self.assertEqual(june["first_retrieved_utc"], "2026-10-14T06:00:00Z")
        self.assertEqual(june["last_checked_utc"], "2026-10-14T06:00:00Z")
        self.assertEqual((self.zips / june["file"]).read_bytes(), a)

    def test_an_unchanged_file_records_only_the_check_time(self):
        source = FakeSource(**{"2026_06_30": zipish("june")})
        self.run_archive(source, T1)
        before = self.entries()
        self.run_archive(source, T2)
        after = self.entries()
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["last_checked_utc"], "2026-10-15T06:00:00Z")
        for key in ("quarter", "sha256", "size", "file", "url", "first_retrieved_utc"):
            self.assertEqual(after[0][key], before[0][key])

    def test_a_changed_file_is_a_new_entry_and_the_old_bytes_stay(self):
        old, new = zipish("june v1"), zipish("june v2")
        self.run_archive(FakeSource(**{"2026_06_30": old}), T1)
        self.run_archive(FakeSource(**{"2026_06_30": new}), T2)
        entries = self.entries()
        self.assertEqual([e["sha256"] for e in entries], [hashlib.sha256(old).hexdigest(), hashlib.sha256(new).hexdigest()])
        self.assertEqual(entries[0]["first_retrieved_utc"], "2026-10-14T06:00:00Z")
        self.assertEqual(entries[0]["last_checked_utc"], "2026-10-14T06:00:00Z")
        self.assertEqual(entries[1]["first_retrieved_utc"], "2026-10-15T06:00:00Z")
        self.assertEqual((self.zips / entries[0]["file"]).read_bytes(), old)
        self.assertEqual((self.zips / entries[1]["file"]).read_bytes(), new)

    def test_a_file_that_returns_to_an_earlier_hash_is_not_a_duplicate_of_the_earlier_entry(self):
        a, b = zipish("a"), zipish("b")
        for source, when in ((a, T1), (b, T2), (a, datetime(2026, 10, 16, 6, tzinfo=timezone.utc))):
            self.run_archive(FakeSource(**{"2026_06_30": source}), when)
        self.assertEqual(len(self.entries()), 3)

    def test_a_stored_zip_is_never_overwritten(self):
        """Recorded mutation: in `archive`, `if hashlib.sha256(stored.read_bytes()).hexdigest() != digest:` replaced by
        `if False:` makes this test fail with `AssertionError: ValueError not raised`."""
        data = zipish("june")
        self.run_archive(FakeSource(**{"2026_06_30": data}), T1)
        stored = self.zips / self.entries()[0]["file"]
        stored.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.run_archive(FakeSource(**{"2026_06_30": data}), T2)
        self.assertEqual(stored.read_bytes(), b"tampered")

    def test_a_new_quarter_end_in_the_listing_is_archived_beside_the_old(self):
        self.run_archive(FakeSource(**{"2026_06_30": zipish("june")}), T1)
        source = FakeSource(**{"2026_06_30": zipish("june"), "2026_09_30": zipish("sept")})
        self.run_archive(source, T2)
        self.assertEqual([e["quarter"] for e in self.entries()], ["2026-06-30", "2026-09-30"])

    def test_only_the_requested_number_of_latest_quarters_is_fetched(self):
        source = FakeSource(**{"2026_06_30": zipish("j"), "2026_03_31": zipish("m"), "2025_12_31": zipish("d")})
        self.run_archive(source, T1, quarters=2)
        self.assertEqual({e["quarter"] for e in self.entries()}, {"2026-06-30", "2026-03-31"})

    def test_a_naive_time_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_archive(FakeSource(**{"2026_06_30": zipish("j")}), datetime(2026, 10, 14, 6))

    def test_the_manifest_is_the_same_bytes_on_a_rerun_apart_from_the_check_time(self):
        source = FakeSource(**{"2026_06_30": zipish("june")})
        self.run_archive(source, T1)
        first = self.manifest.read_text()
        self.run_archive(source, T1)
        self.assertEqual(self.manifest.read_text(), first)


class TrackedManifestTests(unittest.TestCase):
    def test_the_tracked_manifest_is_well_formed(self):
        manifest = json.loads((ROOT / "archive/cdr/manifest.json").read_text())
        self.assertIn("cdr.ffiec.gov", manifest["source"])
        for entry in manifest["entries"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(entry["first_retrieved_utc"].endswith("Z"))
            self.assertLessEqual(entry["first_retrieved_utc"], entry["last_checked_utc"])


if __name__ == "__main__":
    unittest.main()
