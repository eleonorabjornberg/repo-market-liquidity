# Superseded snapshot files

A published snapshot file is never edited or deleted (`docs/decisions/snapshots.md`). When a series is re-cut, the old
file stays under its own digest and its manifest is replaced; this note says what replaced it and why.

## 14 October 2026: the FOMC row of 2026-09-16 left out (#59, finding #55)

The `on_rrp_rate` and `srf_rate` snapshots published the FOMC row announced on 2026-09-16, which is in the blind tier
of the model repo's lockbox (`docs/decisions/lockbox.md`: every day after 2026-09-03). Other modules of this repository
already refuse that tier. The snapshots are now cut from the tracked rate tables without any row the lockbox holds
(`snapshots.build` reads the parent's lockbox on each build). The tracked tables keep every row.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `on_rrp_rate` | `fa35581f43d90ccf1318d78d3b7583bb5541a6fa0f7e52dbb5cf503b49c9686a` | `30e9296afbb34a110449d100148aca442ce23778cab6206db4f7796d4124e2ab` | 32 to 31 |
| `srf_rate` | `d4ded3b02729838430e50ca4034e21e93e8338958e0f808a5dcd87ccf9455606` | `a1182d32530038de4dbeb40fed3b8e733e012bf1cb4e52f430e08a0ae0bfa252` | 19 to 18 |

A reader that pinned a superseded digest still finds its bytes. They should move to the current digest: the old file
carries a blind-tier row and must not be used in a comparison. The other series' digests did not move; their manifests
gained `source_table_sha256` and `locked_rows_omitted` (empty) and were rebuilt at the commit of this change.

## 14 October 2026: the `slr_headroom` snapshot re-cut with a `measure` column (#71)

Eleonora's decision on #69 (14 October 2026, Q2) puts State Street Bank and Trust Company outside the main measure, as a
labelled sensitivity in the same snapshot. The extract gained a `measure` column (`main`, or `sensitivity_state_street`) and
the headroom now reads the requirement table of `docs/decisions/slr-requirement.md` (a draft until she merges it). No figure
moved: the 277 rows, their ratios, requirements and headroom are those of the file they replace; only the new column and the
two manifest notes are added.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `slr_headroom` | `998c5aa153689d76520e9901f82e7813eeffc1709ab4030735d4855cc9ea31f0` | `09c138ad385424b8ba9d705e258ac254cd0ab6ee5e93e7ba199276440ba4de27` | 277 to 277 |

A reader that pinned the superseded digest still finds its bytes. A reader of the main measure moves to the current digest
and filters on `measure == main`; the old file has no such column and holds State Street in the main series.

## 15 October 2026: the `agency_securities` snapshot re-cut with `fetch_sha256` and `content_sha256` (#89, finding #40)

The H.4.1 saved-page SHA-256 changes on every fetch (the archive injects per-request tokens), so it identifies a fetch,
not the release. The snapshot's `page_sha256` column is relabelled `fetch_sha256`, byte-for-byte the same values, and a
`content_sha256` column is added: the SHA-256 of the row's extracted values in the canonical form of
`repo_liquidity.contenthash` (it re-derives from the snapshot alone). No extracted value moved: dropping the new column
and restoring the old name gives the superseded file back, digest for digest (`tests/test_fetch_hash.py`). The `h8_groups`
snapshot's bytes are unchanged (its digest is the same); only its manifest gained the same note and the content hash of
each release (`source_content_sha256`).

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `agency_securities` | `71921036e67a2f4b028caa072d773190b1be0bdeebf7e176ada37ba252fd602e` | `9a5c4eafb04e85d4676c97bfc94a047ee6a7ad384345f977fff30d3f01681e58` | 454 to 454 |

A reader that pinned the superseded digest still finds its bytes, with the column named `page_sha256`. A reader that
moves to the current digest finds `fetch_sha256` in its place and one more column, `content_sha256`.
