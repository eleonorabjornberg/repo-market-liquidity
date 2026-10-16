"""#101 (finding #97): the H.8 group extract names its page digest `fetch_sha256` and carries a `content_sha256`.

#89 gave the H.4.1 extracts the same treatment and left the H.8 group extract with `release_sha256`, a name that claims
the digest identifies the release when it identifies one fetch (finding #40). Here the column is relabelled, values
byte-for-byte, and a `content_sha256` is added per row: the hash of the values its release first printed, in the canonical
form of `repo_liquidity.contenthash` (`h8.release_content_hashes`, the function #89 wrote).

The old digests below are those of the files on main before this change. Rebuilding the old bytes from the new files (drop
the new column, restore the old name) and getting the old digest back is the proof that no extracted value moved.
"""

import csv
import hashlib
import io
import json
import pathlib
import tempfile
import unittest

from repo_liquidity import h8, snapshots

ROOT = pathlib.Path(__file__).resolve().parents[1]
H8_DIR = ROOT / "tests" / "fixtures" / "snapshots" / "h8_groups"
EXTRACT = H8_DIR / h8.EXTRACT_NAME

#: The files on main before #101: the tracked extract and the published `h8_groups` snapshot.
OLD_EXTRACT = "1069af546ca0c5d3d69190b680dbc617557d3bbac0798f6a1e12d155f9f1f7f9"
OLD_SNAPSHOT = "326466ae847af5c5be0a462d0a71e6d4022fc792816a1c7f57ad1a9e8ee022fe"


def old_bytes(data: bytes) -> bytes:
    """The pre-#101 bytes: `content_sha256` dropped, `fetch_sha256` named `release_sha256` again."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"), newline="")))
    drop = rows[0].index("content_sha256")
    rows[0][rows[0].index("fetch_sha256")] = "release_sha256"
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(row[:drop] + row[drop + 1:])
    return buffer.getvalue().encode("utf-8")


class ColumnTests(unittest.TestCase):
    def test_the_extract_columns_end_with_the_fetch_hash_and_the_content_hash(self):
        self.assertEqual(h8.EXTRACT_COLUMNS[-2:], ("fetch_sha256", "content_sha256"))
        self.assertNotIn("release_sha256", h8.EXTRACT_COLUMNS)
        self.assertEqual(h8.SNAPSHOT_COLUMNS, h8.EXTRACT_COLUMNS + ("break_ids",))

    def test_the_tracked_extract_has_those_columns(self):
        with EXTRACT.open(encoding="utf-8", newline="") as handle:
            self.assertEqual(tuple(csv.reader(handle).__next__()), h8.EXTRACT_COLUMNS)

    def test_the_manifest_columns_match_the_published_file(self):
        manifest = snapshots.load_manifest("h8_groups")
        path = ROOT / manifest["path"]
        header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
        self.assertEqual(manifest["columns"], header)
        self.assertEqual(header, list(h8.SNAPSHOT_COLUMNS))


class NoValueMovedTests(unittest.TestCase):
    def test_the_old_extract_is_recovered_digest_for_digest(self):
        self.assertEqual(hashlib.sha256(old_bytes(EXTRACT.read_bytes())).hexdigest(), OLD_EXTRACT)

    def test_the_old_snapshot_is_recovered_digest_for_digest_and_kept(self):
        manifest = snapshots.load_manifest("h8_groups")
        new = (ROOT / manifest["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(old_bytes(new)).hexdigest(), OLD_SNAPSHOT)
        old = ROOT / "snapshots" / "h8_groups" / f"{OLD_SNAPSHOT}.csv"
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), OLD_SNAPSHOT)
        self.assertNotEqual(manifest["sha256"], OLD_SNAPSHOT)

    def test_the_superseded_note_names_the_old_and_the_new_digest(self):
        note = (ROOT / "snapshots" / "SUPERSEDED.md").read_text(encoding="utf-8")
        self.assertIn(OLD_SNAPSHOT, note)
        self.assertIn(snapshots.load_manifest("h8_groups")["sha256"], note)


class ContentHashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prints = h8.load_extract(EXTRACT)
        cls.rows = list(csv.DictReader(EXTRACT.open(encoding="utf-8", newline="")))

    def test_every_row_carries_the_content_hash_of_its_release(self):
        derived = h8.release_content_hashes(self.prints)
        self.assertEqual(len(self.rows), len(self.prints))
        for row in self.rows:
            self.assertEqual(row["content_sha256"], derived[row["release_date"]], row["week_ending"])

    def test_the_content_hash_rederives_from_the_extract_alone_and_matches_the_releases_record(self):
        record = json.loads((H8_DIR / h8.RELEASES_NAME).read_text(encoding="utf-8"))
        listed = {r["release_date"]: r["content_sha256"] for r in record["releases"]}
        for row in self.rows:
            self.assertEqual(row["content_sha256"], listed[row["release_date"]])

    def test_the_writer_writes_the_tracked_bytes(self):
        self.assertEqual(h8.write_extract(self.prints), EXTRACT.read_bytes())

    def test_the_loader_refuses_a_content_hash_that_is_not_the_hash_of_the_values(self):
        """Data guard: a row whose `content_sha256` is not the hash of its release's values is refused.

        Recorded mutation (16 October 2026): in `src/repo_liquidity/h8.py`, `load_extract`'s check
        `if recorded != derived[item.release_date.isoformat()]:` replaced by `if False:` (the content hash read and never compared). This test then fails
        with AssertionError: ValueError not raised.
        """
        text = EXTRACT.read_text(encoding="utf-8").splitlines(keepends=True)
        fields = text[3].rstrip("\n").split(",")
        fields[-1] = "0" * 64
        text[3] = ",".join(fields) + "\n"
        data = "".join(text).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / EXTRACT.name
            out.write_bytes(data)
            out.with_name(out.name + ".manifest.json").write_text(json.dumps({"sha256": hashlib.sha256(data).hexdigest()}))
            with self.assertRaises(ValueError) as caught:
                h8.load_extract(out)
        self.assertIn("content_sha256", str(caught.exception))

    def test_one_changed_value_changes_the_content_hash_written(self):
        import dataclasses

        first = self.prints[0]
        values = dict(first.values)
        values[h8.FIELDS[0]] += 0.1
        changed = [dataclasses.replace(first, values=values)] + list(self.prints[1:])
        before = list(csv.DictReader(io.StringIO(h8.write_extract(self.prints).decode("utf-8"))))
        after = list(csv.DictReader(io.StringIO(h8.write_extract(changed).decode("utf-8"))))
        self.assertNotEqual(before[0]["content_sha256"], after[0]["content_sha256"])
        self.assertEqual([r["content_sha256"] for r in before[1:]], [r["content_sha256"] for r in after[1:]])


if __name__ == "__main__":
    unittest.main()
