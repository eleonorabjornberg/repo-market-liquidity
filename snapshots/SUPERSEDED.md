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
