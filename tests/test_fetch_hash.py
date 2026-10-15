"""#89 (finding #40): a fetch hash identifies a fetch, a content hash identifies the extracted values.

The archive injects per-request tokens into every page, so the SHA-256 of a saved page differs between two fetches of
one release (finding #40; PR #51, section 8, found the same for the H.8 pages). Each extract therefore carries two
hashes per release: `fetch_sha256` (the old `page_sha256`, relabelled, values byte-for-byte) and `content_sha256`, the
SHA-256 of the release's extracted values in the canonical form of `repo_liquidity.contenthash`.

The old digests below are those of the files on main before this change. Rebuilding the old bytes from the new files
(drop the new column, restore the old name) and getting the old digest back is the proof that no extracted value moved.
"""

import csv
import hashlib
import io
import json
import pathlib
import shutil
import tempfile
import unittest
from decimal import Decimal

from repo_liquidity import contenthash, h41, h8, snapshots

ROOT = pathlib.Path(__file__).resolve().parents[1]
H41_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h41"
H8_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups"

#: The files on main before #89: extract name -> the SHA-256 of its bytes.
OLD_H41 = {
    "h41_treasury_first_print.csv": "01ae1de42e72a210d6d90fcf293b574167e2ceed3b477f48ea0a51b451454433",
    "h41_mbs_first_print.csv": "b9a48241fbddd0130fb4210cf59c700ca912b5d4e008ffdec14735631dffc993",
    "h41_agency_first_print.csv": "6c5a387ab7f674316a7ef1b0644ec9ed8d349250dbb1167b2e334cd547a3fc1b",
}
OLD_H8_RELEASES = "54a2043667b0cdd95db7e3982c969f7e17fe9723a34161d34a0e9bc87715f448"
OLD_AGENCY_SNAPSHOT = "71921036e67a2f4b028caa072d773190b1be0bdeebf7e176ada37ba252fd602e"

NOTE = ("fetch_sha256 identifies the fetch, not the release (finding #40); content_sha256 identifies the extracted "
        "values")


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _old_bytes(path, drop, rename):
    """The file as it was: the new column dropped, the old column name restored."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        keep = [i for i, name in enumerate(header) if name != drop]
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow([rename.get(header[i], header[i]) for i in keep])
        for row in reader:
            writer.writerow([row[i] for i in keep])
    return out.getvalue().encode("utf-8")


class CanonicalFormTests(unittest.TestCase):
    COLUMNS = ("week", "level", "share")
    PLACES = {"level": 0, "share": 1}

    def test_the_form_is_fixed(self):
        rows = [("2018-01-10", "7", "1.2"), ("2018-01-03", "-5", "2.0")]
        self.assertEqual(contenthash.canonical(self.COLUMNS, rows, self.PLACES),
                         b"week,level,share\n2018-01-03,-5,2.0\n2018-01-10,7,1.2\n")

    def test_a_value_with_more_places_than_the_form_fixes_is_refused_not_rounded(self):
        with self.assertRaises(ValueError):
            contenthash.canonical(self.COLUMNS, [("d", "1", "1.25")], self.PLACES)

    def test_rows_are_sorted_so_the_order_does_not_matter(self):
        a = [("2018-01-03", "1", "1.0"), ("2018-01-10", "2", "2.0")]
        self.assertEqual(contenthash.content_sha256(self.COLUMNS, a, self.PLACES),
                         contenthash.content_sha256(self.COLUMNS, list(reversed(a)), self.PLACES))

    def test_the_same_number_written_two_ways_is_one_value(self):
        a = contenthash.content_sha256(self.COLUMNS, [("d", "1500", "2.0")], self.PLACES)
        b = contenthash.content_sha256(self.COLUMNS, [("d", "1500.0", "2.00")], self.PLACES)
        c = contenthash.content_sha256(self.COLUMNS, [("d", 1500, Decimal("2"))], self.PLACES)
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_one_changed_value_changes_the_hash(self):
        base = contenthash.content_sha256(self.COLUMNS, [("d", "1500", "2.0")], self.PLACES)
        self.assertNotEqual(base, contenthash.content_sha256(self.COLUMNS, [("d", "1501", "2.0")], self.PLACES))
        self.assertNotEqual(base, contenthash.content_sha256(self.COLUMNS, [("d", "1500", "2.1")], self.PLACES))
        self.assertNotEqual(base, contenthash.content_sha256(self.COLUMNS, [("e", "1500", "2.0")], self.PLACES))

    def test_a_value_with_a_separator_or_newline_is_refused(self):
        for bad in ("a,b", "a\nb", "a\rb"):
            with self.assertRaises(ValueError):
                contenthash.canonical(self.COLUMNS, [(bad, "1", "1.0")], self.PLACES)

    def test_a_row_of_the_wrong_width_is_refused(self):
        with self.assertRaises(ValueError):
            contenthash.canonical(self.COLUMNS, [("d", "1")], self.PLACES)


class H41ExtractTests(unittest.TestCase):
    def test_the_column_is_relabelled_and_the_content_hash_added(self):
        for name in OLD_H41:
            with (H41_DIR / name).open(encoding="utf-8") as handle:
                header = next(csv.reader(handle))
            self.assertEqual(header, list(h41.EXTRACT_COLUMNS), name)
            self.assertIn("fetch_sha256", header)
            self.assertNotIn("page_sha256", header)
            self.assertEqual(header[-1], "content_sha256")

    def test_no_extracted_value_moved(self):
        """Dropping `content_sha256` and restoring the name `page_sha256` gives the old bytes back, digest for digest;
        so every other column, `fetch_sha256` included, is byte-for-byte the old one."""
        for name, old in OLD_H41.items():
            data = _old_bytes(H41_DIR / name, "content_sha256", {"fetch_sha256": "page_sha256"})
            self.assertEqual(hashlib.sha256(data).hexdigest(), old, name)

    def test_each_content_hash_rederives_from_the_extract_alone(self):
        for name in OLD_H41:
            for row in _rows(H41_DIR / name):
                self.assertEqual(row["content_sha256"], h41.row_content_sha256(row), (name, row["week_ended"]))

    def test_one_changed_value_changes_the_content_hash(self):
        row = _rows(H41_DIR / "h41_treasury_first_print.csv")[0]
        for column in ("week_average_musd", "change_from_prior_week_musd", "wednesday_level_musd"):
            changed = dict(row, **{column: str(int(row[column]) + 1)})
            self.assertNotEqual(h41.row_content_sha256(changed), row["content_sha256"], column)
        self.assertNotEqual(h41.row_content_sha256(dict(row, week_ended="2017-12-20")), row["content_sha256"])

    def test_the_fetch_hash_and_url_are_not_part_of_the_content(self):
        """The same values fetched twice are the same content, whatever the page's tokens made its digest."""
        row = _rows(H41_DIR / "h41_treasury_first_print.csv")[0]
        again = dict(row, fetch_sha256="0" * 64, url="https://example.invalid/")
        self.assertEqual(h41.row_content_sha256(again), row["content_sha256"])

    def test_a_stored_content_hash_that_does_not_match_its_values_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / "treasury.csv"
            shutil.copy(H41_DIR / "h41_treasury_first_print.csv", copy)
            lines = copy.read_text(encoding="utf-8").splitlines()
            fields = lines[1].split(",")
            fields[4] = str(int(fields[4]) + 1)  # a value changed, the stored hash not
            lines[1] = ",".join(fields)
            copy.write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest = {"path": copy.name, "sha256": hashlib.sha256(copy.read_bytes()).hexdigest(), "source": "x"}
            copy.with_name(copy.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "content_sha256"):
                h41.load_extract(copy)

    def test_the_writer_writes_the_new_names(self):
        row = ("2018-01-03", "2018-01-04", "https://www.federalreserve.gov/releases/h41/20180104/", "a" * 64,
               2452495, -1729, 2448208)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "x.csv"
            h41.write_extract([row], path)
            written = _rows(path)[0]
        self.assertEqual(written["fetch_sha256"], "a" * 64)
        self.assertEqual(written["content_sha256"], h41.row_content_sha256(written))
        self.assertNotIn("page_sha256", written)


class H8ReleasesRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = H8_DIR / h8.RELEASES_NAME
        cls.record = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.prints = h8.load_extract(H8_DIR / h8.EXTRACT_NAME)

    def test_the_record_is_relabelled_and_no_other_field_moved(self):
        """Dropping `content_sha256` and restoring `sha256` gives the old file back, digest for digest."""
        old = json.loads(json.dumps(self.record))
        old["index"]["sha256"] = old["index"].pop("fetch_sha256")
        for release in old["releases"]:
            release["sha256"] = release.pop("fetch_sha256")
            del release["content_sha256"]
        data = (json.dumps(old, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(data).hexdigest(), OLD_H8_RELEASES)

    def test_no_record_still_calls_a_fetch_hash_a_sha256(self):
        self.assertNotIn("sha256", self.record["index"])
        for release in self.record["releases"]:
            self.assertNotIn("sha256", release)
            self.assertRegex(release["fetch_sha256"], r"^[0-9a-f]{64}$")

    def test_each_release_content_hash_rederives_from_the_extract_alone(self):
        hashes = h8.release_content_hashes(self.prints)
        self.assertEqual(len(hashes), len(self.record["releases"]))
        for release in self.record["releases"]:
            self.assertEqual(release["content_sha256"], hashes[release["release_date"]], release["release_date"])

    def test_one_changed_value_changes_the_release_content_hash(self):
        import dataclasses

        first = self.prints[0]
        values = dict(first.values)
        field = h8.FIELDS[0]
        values[field] = values[field] + 0.1
        changed = [dataclasses.replace(first, values=values)] + list(self.prints[1:])
        before, after = h8.release_content_hashes(self.prints), h8.release_content_hashes(changed)
        self.assertNotEqual(before[first.release_date.isoformat()], after[first.release_date.isoformat()])
        self.assertEqual({k: v for k, v in before.items() if k != first.release_date.isoformat()},
                         {k: v for k, v in after.items() if k != first.release_date.isoformat()})

    def test_the_extract_script_writes_the_new_names(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("extract_h8_groups", ROOT / "scripts" / "extract_h8_groups.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("fetch_sha256", module.RELEASE_KEYS)
        self.assertIn("content_sha256", module.RELEASE_KEYS)
        self.assertNotIn("sha256", module.RELEASE_KEYS)


class SnapshotTests(unittest.TestCase):
    def test_the_agency_securities_snapshot_is_relabelled_and_no_value_moved(self):
        manifest = snapshots.load_manifest("agency_securities")
        self.assertIn("fetch_sha256", manifest["columns"])
        self.assertIn("content_sha256", manifest["columns"])
        self.assertNotIn("page_sha256", manifest["columns"])
        path = ROOT / manifest["path"]
        data = _old_bytes(path, "content_sha256", {"fetch_sha256": "page_sha256"})
        self.assertEqual(hashlib.sha256(data).hexdigest(), OLD_AGENCY_SNAPSHOT)

    def test_the_agency_securities_content_hash_rederives_from_the_snapshot_alone(self):
        for row in snapshots.read("agency_securities"):
            self.assertEqual(row["content_sha256"], snapshots.agency_row_content_sha256(row), row["week_ended"])

    def test_the_affected_manifests_carry_the_note(self):
        for series in ("agency_securities", "h8_groups"):
            self.assertEqual(snapshots.load_manifest(series)["hash_note"], NOTE, series)

    def test_the_h8_manifest_lists_the_content_hash_of_each_release(self):
        manifest = snapshots.load_manifest("h8_groups")
        record = json.loads((H8_DIR / h8.RELEASES_NAME).read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_content_sha256"],
                         {r["release_date"]: r["content_sha256"] for r in record["releases"]})
        self.assertEqual(manifest["source_pages"], {r["release_date"]: r["fetch_sha256"] for r in record["releases"]})

    def test_a_stale_content_hash_in_the_h8_record_is_refused_by_the_build(self):
        """Recorded mutation is not required (a data guard); the case is: the record's content hash of one release
        changed, and the build refuses with ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            table = pathlib.Path(tmp) / h8.EXTRACT_NAME
            for name in (h8.EXTRACT_NAME, h8.EXTRACT_NAME + ".manifest.json", h8.RELEASES_NAME):
                shutil.copy(H8_DIR / name, table.with_name(name))
            record_path = table.with_name(h8.RELEASES_NAME)
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["releases"][0]["content_sha256"] = "0" * 64
            record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "content_sha256"):
                snapshots._build_weekly("h8_groups", table, pathlib.Path(tmp) / "out", "a" * 40)

    def test_the_superseded_agency_digest_stays_published_with_a_note(self):
        old = ROOT / "snapshots" / "agency_securities" / f"{OLD_AGENCY_SNAPSHOT}.csv"
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), OLD_AGENCY_SNAPSHOT)
        note = (ROOT / "snapshots" / "SUPERSEDED.md").read_text(encoding="utf-8")
        self.assertIn(OLD_AGENCY_SNAPSHOT, note)
        self.assertIn(snapshots.load_manifest("agency_securities")["sha256"], note)
        self.assertIn("page_sha256", note)


if __name__ == "__main__":
    unittest.main()
