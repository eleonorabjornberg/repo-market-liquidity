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
import re
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


def asset_for(entry, **override):
    """What the release API lists for a manifest entry that is stored correctly."""
    asset = {"name": entry["file"], "size": entry["size"], "digest": "sha256:" + entry["sha256"]}
    asset.update(override)
    return asset


class ReleaseStorageTests(unittest.TestCase):
    """Every manifest entry must exist as a release asset with the same SHA-256 and size (#99, finding #94)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.manifest = self.root / "manifest.json"
        self.zips = self.root / "zips"
        self.data = {"2026_06_30": zipish("june"), "2026_03_31": zipish("march")}
        archive_cdr.archive(FakeSource(**self.data), self.manifest, self.zips, T1)
        self.entries = json.loads(self.manifest.read_text())["entries"]

    def manifest_dict(self):
        return json.loads(self.manifest.read_text())

    def test_a_fully_stored_manifest_has_no_gaps(self):
        assets = [asset_for(e) for e in self.entries]
        self.assertEqual(archive_cdr.release_gaps(self.manifest_dict(), assets), [])

    def test_an_entry_missing_from_the_release_is_a_gap(self):
        """Recorded mutation: in `release_gaps`, `if asset is None:` replaced by `if False:` makes this test fail with
        `TypeError: 'NoneType' object is not subscriptable` (the missing asset is looked up as if it existed)."""
        assets = [asset_for(e) for e in self.entries[1:]]
        gaps = archive_cdr.release_gaps(self.manifest_dict(), assets)
        self.assertEqual(len(gaps), 1)
        self.assertIn(self.entries[0]["file"], gaps[0])

    def test_an_asset_with_another_size_or_hash_is_a_gap(self):
        """Recorded mutation: in `release_gaps`, `asset["size"] != entry["size"]` replaced by `False` makes the size half of
        this test fail with `AssertionError: 0 != 1`."""
        first = self.entries[0]
        wrong_size = [asset_for(first, size=first["size"] + 1), asset_for(self.entries[1])]
        wrong_hash = [asset_for(first, digest="sha256:" + "0" * 64), asset_for(self.entries[1])]
        self.assertEqual(len(archive_cdr.release_gaps(self.manifest_dict(), wrong_size)), 1)
        self.assertEqual(len(archive_cdr.release_gaps(self.manifest_dict(), wrong_hash)), 1)

    def test_an_asset_without_a_digest_is_a_gap(self):
        assets = [asset_for(e, digest=None) for e in self.entries]
        self.assertEqual(len(archive_cdr.release_gaps(self.manifest_dict(), assets)), 2)

    def test_an_entry_marked_not_stored_is_not_a_gap_and_is_never_deleted(self):
        manifest = self.manifest_dict()
        manifest["entries"][0]["status"] = "not_stored"
        assets = [asset_for(self.entries[1])]
        self.assertEqual(archive_cdr.release_gaps(manifest, assets), [])
        self.assertEqual(len(manifest["entries"]), 2)

    def test_a_hash_in_the_manifest_but_missing_from_the_release_is_uploaded_not_skipped(self):
        """Recorded mutation: in `uploads_needed`, `if asset is not None:` replaced by `if True:` makes this test fail with
        `TypeError: 'NoneType' object is not subscriptable` (a missing asset is treated as stored and never uploaded)."""
        assets = [asset_for(self.entries[1])]
        todo = archive_cdr.uploads_needed(self.manifest_dict(), assets, self.zips)
        self.assertEqual(todo, [self.entries[0]["file"]])

    def test_nothing_is_uploaded_when_the_release_holds_everything(self):
        assets = [asset_for(e) for e in self.entries]
        self.assertEqual(archive_cdr.uploads_needed(self.manifest_dict(), assets, self.zips), [])

    def test_a_missing_asset_whose_bytes_are_gone_raises(self):
        (self.zips / self.entries[0]["file"]).unlink()
        with self.assertRaises(ValueError):
            archive_cdr.uploads_needed(self.manifest_dict(), [asset_for(self.entries[1])], self.zips)

    def test_a_local_zip_whose_bytes_are_not_its_name_is_not_uploaded(self):
        (self.zips / self.entries[0]["file"]).write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            archive_cdr.uploads_needed(self.manifest_dict(), [asset_for(self.entries[1])], self.zips)

    def test_an_asset_of_the_right_name_but_wrong_bytes_is_never_clobbered(self):
        assets = [asset_for(self.entries[0], digest="sha256:" + "0" * 64), asset_for(self.entries[1])]
        with self.assertRaises(ValueError):
            archive_cdr.uploads_needed(self.manifest_dict(), assets, self.zips)


class ReconcileTests(unittest.TestCase):
    """The one-off reconciliation of the manifest with the release (#99): adopt stored zips, mark lost ones, never delete."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.manifest = Path(self._tmp.name) / "manifest.json"
        archive_cdr.archive(FakeSource(**{"2026_06_30": zipish("june")}), self.manifest, Path(self._tmp.name) / "z", T1)
        self.lost = json.loads(self.manifest.read_text())["entries"][0]["sha256"]
        self.adopted = {"quarter": "2026-06-30", "url": archive_cdr.URL, "file": "2026-06-30-" + "a" * 64 + ".zip",
                        "sha256": "a" * 64, "size": 7, "first_retrieved_utc": "2026-10-16T11:23:43Z",
                        "last_checked_utc": "2026-10-16T11:23:43Z", "note": "retrieval time = upload time (run 1)"}
        self.record = {"adopted": [self.adopted], "not_stored": [self.lost]}

    def reconciled(self):
        manifest = json.loads(self.manifest.read_text())
        archive_cdr.reconcile(manifest, self.record)
        return manifest

    def test_adopted_entries_are_added_and_lost_ones_are_marked_not_deleted(self):
        entries = self.reconciled()["entries"]
        self.assertEqual(len(entries), 2)
        by_sha = {e["sha256"]: e for e in entries}
        self.assertEqual(by_sha[self.lost]["status"], "not_stored")
        self.assertEqual(by_sha["a" * 64]["note"], "retrieval time = upload time (run 1)")
        self.assertNotIn("status", by_sha["a" * 64])

    def test_reconciling_twice_changes_nothing(self):
        once = self.reconciled()
        archive_cdr.reconcile(once, self.record)
        self.assertEqual(once, self.reconciled())

    def test_a_not_stored_hash_that_is_not_in_the_manifest_is_refused(self):
        self.record["not_stored"] = ["b" * 64]
        with self.assertRaises(ValueError):
            self.reconciled()

    def test_a_not_stored_entry_stays_not_stored_when_the_portal_serves_other_bytes_later(self):
        manifest = self.reconciled()
        self.manifest.write_text(json.dumps(manifest))
        archive_cdr.archive(FakeSource(**{"2026_06_30": zipish("june v2")}), self.manifest, Path(self._tmp.name) / "z", T2)
        entries = json.loads(self.manifest.read_text())["entries"]
        self.assertEqual({e["sha256"]: e.get("status") for e in entries if e["sha256"] == self.lost}, {self.lost: "not_stored"})
        self.assertEqual(len(entries), 3)


class TrackedReconciliationTests(unittest.TestCase):
    def test_the_tracked_manifest_has_been_reconciled(self):
        manifest = json.loads((ROOT / "archive/cdr/manifest.json").read_text())
        record = json.loads((ROOT / "archive/cdr/reconciliation.json").read_text())
        before = json.dumps(manifest, sort_keys=True)
        archive_cdr.reconcile(manifest, record)
        self.assertEqual(json.dumps(manifest, sort_keys=True), before)
        by_sha = {e["sha256"]: e for e in manifest["entries"]}
        for sha in record["not_stored"]:
            self.assertEqual(by_sha[sha]["status"], "not_stored")
        for entry in record["adopted"]:
            self.assertIn("run 38893471133", by_sha[entry["sha256"]]["note"])


class WorkflowRefTests(unittest.TestCase):
    def test_the_workflow_names_the_branch_by_its_full_ref_and_the_release_by_a_tag_that_cannot_clash(self):
        text = (ROOT / ".github/workflows/cdr-archive.yml").read_text()
        self.assertIn("refs/heads/cdr-archive", text)
        self.assertNotRegex(text, r"origin cdr-archive\b")
        self.assertNotRegex(text, r"release (create|upload) cdr-archive\b")
        self.assertIn("cdr-archive-assets", text)

    def test_the_stray_tag_is_deleted_only_after_the_release_is_retagged(self):
        text = (ROOT / ".github/workflows/cdr-archive.yml").read_text()
        self.assertLess(text.index('gh release edit cdr-archive --tag'), text.index("--delete refs/tags/cdr-archive"))

    def test_every_piped_step_runs_with_pipefail(self):
        """A step that pipes `archive_cdr.py` into `tee` must fail when the script does (#111, finding #109).

        GitHub's default `run` shell is `bash -e {0}`, which has no `pipefail`, so `python3 ... | tee ...` exits with
        `tee`'s status and a failed download goes green with nothing retrieved. `shell: bash` (set once under
        `defaults.run`) makes GitHub use `bash --noprofile --norc -eo pipefail {0}`; no step may override it.

        Recorded mutation: deleting the `defaults:` block (the three lines `defaults:`, `  run:`, `    shell: bash`)
        from cdr-archive.yml. The failing test raised AssertionError (no `defaults.run.shell: bash` found), and the
        pipe-count check below shows the workflow does pipe.
        """
        text = (ROOT / ".github/workflows/cdr-archive.yml").read_text()
        self.assertRegex(text, r"(?m)^defaults:\n  run:\n    shell: bash$")
        self.assertEqual(re.findall(r"(?m)^\s+shell:.*$", text), ["    shell: bash"])
        self.assertGreaterEqual(len(re.findall(r"\| tee ", text)), 2)

    def test_the_readme_names_the_release_by_its_current_tag(self):
        text = (ROOT / "archive/cdr/README.md").read_text()
        self.assertNotRegex(text, r"release `cdr-archive`")
        self.assertIn("`cdr-archive-assets`", text)


if __name__ == "__main__":
    unittest.main()
