"""The digest-named snapshots of the three FOMC series (#25; `docs/decisions/snapshots.md`, a draft).

Each series is published at `snapshots/<series>/manifest.json` (a stable path) and `snapshots/<series>/<sha256>.csv`
(named by its digest). The manifest carries the digest, the parent pin and panel digest, and the commit of this
repository the snapshot was built from. CI rebuilds each snapshot from the tracked rate tables and their saved pages
and checks it reproduces the tracked bytes and digest.
"""

import hashlib
import json
import pathlib
import tempfile
import unittest

from repo_liquidity import PANEL_SHA256, PARENT_COMMIT, snapshots

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TrackedSnapshotTests(unittest.TestCase):
    def test_every_series_has_a_manifest_and_a_digest_named_file(self):
        for series in snapshots.SERIES:
            manifest = snapshots.load_manifest(series)
            self.assertEqual(manifest["series"], series)
            path = ROOT / manifest["path"]
            self.assertEqual(path.name, manifest["sha256"] + ".csv")
            self.assertEqual(path.parent, ROOT / "snapshots" / series)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest["sha256"])

    def test_every_snapshot_names_the_parent_and_this_repositorys_commit(self):
        for series in snapshots.SERIES:
            manifest = snapshots.load_manifest(series)
            self.assertEqual(manifest["parent_commit"], PARENT_COMMIT)
            self.assertEqual(manifest["parent_panel_sha256"], PANEL_SHA256)
            self.assertRegex(manifest["repo_commit"], r"^[0-9a-f]{40}$")

    def test_a_snapshot_rebuilds_to_its_tracked_digest(self):
        """CI check: the snapshot is a function of the tracked rate table and its saved pages.

        Recorded mutation (13 October 2026): in `tests/fixtures/snapshots/fomc_notes/srf_rate.csv`, the rate of the
        2021-07-28 row changed from 0.25 to 0.30 and its manifest digest refreshed. This test then fails with
        AssertionError: the rebuilt digest differs from the tracked manifest's, for `srf_rate`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            for series in snapshots.SERIES:
                tracked = snapshots.load_manifest(series)
                rebuilt = snapshots.build(series, pathlib.Path(tmp), repo_commit=tracked["repo_commit"])
                self.assertEqual(rebuilt["sha256"], tracked["sha256"], series)
                self.assertEqual(rebuilt, tracked, series)

    def test_the_manifest_describes_the_series(self):
        manifest = snapshots.load_manifest("on_rrp_rate")
        self.assertEqual(manifest["rows"], 32)
        self.assertEqual(manifest["last_announced"], "2026-09-16T14:00")
        self.assertEqual(manifest["last_effective"], "2026-09-17")
        self.assertEqual(len(manifest["source_pages"]), manifest["rows"])


class ReadTests(unittest.TestCase):
    def test_reading_by_digest_returns_the_rows(self):
        manifest = snapshots.load_manifest("srf_rate")
        rows = snapshots.read("srf_rate", sha256=manifest["sha256"])
        self.assertEqual(rows[0]["announcement_date"], "2021-07-28")
        self.assertEqual(len(rows), manifest["rows"])

    def test_a_digest_that_is_not_the_published_one_is_refused(self):
        with self.assertRaises(ValueError):
            snapshots.read("srf_rate", sha256="0" * 64)

    def test_an_edited_snapshot_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            manifest = snapshots.build("srf_rate", out, repo_commit="a" * 40)
            path = out / manifest["path"]
            path.write_bytes(path.read_bytes().replace(b",0.25,", b",0.30,"))
            with self.assertRaises(ValueError):
                snapshots.read("srf_rate", root=out)

    def test_an_unknown_series_is_refused(self):
        with self.assertRaises(ValueError):
            snapshots.load_manifest("iorb")

    def test_a_repo_commit_that_is_not_a_full_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                snapshots.build("srf_rate", pathlib.Path(tmp), repo_commit="HEAD")


class ManifestFormatTests(unittest.TestCase):
    def test_the_manifest_is_stable_json(self):
        for series in snapshots.SERIES:
            text = (ROOT / "snapshots" / series / "manifest.json").read_text(encoding="utf-8")
            manifest = json.loads(text)
            self.assertEqual(text, json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
