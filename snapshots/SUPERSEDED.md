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

## 16 October 2026: the `h8_groups` snapshot re-cut with `fetch_sha256` and `content_sha256` (#101, finding #97)

#89 relabelled the H.4.1 page digest as a fetch hash and left the H.8 group extract with `release_sha256`, a name that
says the digest identifies the release when it identifies one fetch (finding #40). The snapshot's `release_sha256` column
is relabelled `fetch_sha256`, byte-for-byte the same values, and a `content_sha256` column is added: the SHA-256 of the
values the row's release first printed, in the canonical form of `repo_liquidity.contenthash` (`h8.release_content_hashes`;
it re-derives from the snapshot alone, and equals the `content_sha256` of the releases record). No extracted value moved:
dropping the new column and restoring the old name gives the superseded file back, digest for digest
(`tests/test_h8_fetch_hash.py`).

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `h8_groups` | `326466ae847af5c5be0a462d0a71e6d4022fc792816a1c7f57ad1a9e8ee022fe` | `f1ff8d72ec62346948798a8cfef8c0c537e72642fae55432e4fd5aaff8530302` | 452 to 452 |

A reader that pinned the superseded digest still finds its bytes, with the column named `release_sha256`. A reader that
moves to the current digest finds `fetch_sha256` in its place and one more column, `content_sha256`, before `break_ids`.

## 15 October 2026: the `slr_headroom` snapshot re-cut with State Street's bank (IDRSSD 35301)

The extract read State Street at IDRSSD 93619, State Street Bank and Trust Company, N.A.: a non-depository trust
subsidiary of about $65 million, whose tier 1 capital is close to its exposure. That is why its ratio was near 100% and
22 of its quarters were refused (`tier1_exceeds_exposure`). The bank of the G-SIB is State Street Bank and Trust Company,
IDRSSD 35301. Eleonora put it in the main measure (15 October 2026), replacing her decision on #69 (Q2), which was made on
the trust subsidiary's figures. The `measure` column is now `main` for every row.

The extract is re-cut from the bulk files retrieved on 15 October 2026, because the zips of 14 October are not kept here.
The portal had rebuilt 14 of the 34 quarter files since then (2023-03-31 to 2026-06-30). Every figure kept in both files
is unchanged. Nine bank-quarters of Citibank (476810) and Goldman Sachs Bank USA (2182786), 2025-06-30 to 2026-06-30, now
carry amendments filed from 29 September to 9 October 2026, days the parent's lockbox holds, so they are withheld
(`updated_after_development_end`). Rows: 277 less State Street's 7 and the 9 withheld, plus State Street's 34, is 295.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `slr_headroom` | `09c138ad385424b8ba9d705e258ac254cd0ab6ee5e93e7ba199276440ba4de27` | `013b647e6c4257a2e95e5cd939d8572dd7d006fc2cf8dfcef782d7439d83d9d9` | 277 to 295 |

A reader that pinned the superseded digest still finds its bytes. They should move to the current digest: the old file's
`sensitivity_state_street` rows are the trust subsidiary's, not State Street's.

## 19 October 2026: the `slr_headroom` snapshot re-cut with nine restored filings (#123, finding #120)

Nine bank-quarters of Citibank (476810) and Goldman Sachs Bank USA (2182786), 2025-06-30 to 2026-06-30, were withheld
because the bulk files now carry amendments filed from 29 September to 9 October 2026, days the parent's lockbox holds.
Eleonora ruled on finding #120 (19 October 2026) that the filings made before 2026-09-04 "stand as the latest filed as of
the development end". The nine rows are read from the superseded snapshot `09c138ad385424b8ba9d705e258ac254cd0ab6ee5e93e7ba199276440ba4de27`,
each with its own `available_from` and source hash as stored there, and the new column `restored_from` names that
snapshot. Their source zips are lost (finding #94). The snapshot's other 295 rows have the same values as in the file they
replace; only the new, blank `restored_from` column is added. Rows: 295 plus 9, is 304.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `slr_headroom` | `013b647e6c4257a2e95e5cd939d8572dd7d006fc2cf8dfcef782d7439d83d9d9` | `4e9f87b518b3106ec5dc7d709f19e7f365e499c969fa5cb7ba9201e66f37e817` | 295 to 304 |

A reader that pinned the superseded digest still finds its bytes. A reader that moves to the current digest finds nine more
rows and the `restored_from` column; the 295 earlier rows are unchanged.

## 20 October 2026: the `rde` snapshot re-cut for Eleonora's ruling of 19 October (#139, finding #136)

PR #134 merged before her ruling on the reserve demand elasticity. The re-cut applies it: availability at 12:00 New York time, a
third Thursday inside an FOMC blackout moved to the first business day after it (six releases of the table, and 17 September
2026), an estimate public at the first release whose data is as of its date or later, and the table starting at the estimate
the launch release headlined (2024-10-09, one row later than before). The 634 earlier estimates are published apart as
`history-<digest>.csv`, labelled "history, not public before 2024-10-17", outside the declaration.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `rde` | `6edafdc786e9b99d8e43f540a52083ed843a086a43209d3df3bfd207023d9e80` | `bc6f395a61b5b83c7fce36de3623e3e05f807f1f30cce5731c7d2743a81c85f2` | 80 to 79 |

A reader that pinned the superseded digest still finds its bytes; they read estimates up to a day before their release and must
move to the current digest.

## 23 October 2026: the `announced_pace` snapshot extended with the Desk's monthly reserve management purchases (#158, G7)

Eleonora's ruling of 21 October 2026 on #156 (option (a)): the monthly amounts on the Desk's operational-details page are read, each
as of its publication instant and from its period's start. The table gains eight rows, for the periods starting 15 January to
14 August 2026 (announced from 14 January to 13 August), so the pace reads a signed value from 16 January 2026 to the development end where
it read `None`. The published bytes of the 23 earlier rows are unchanged. The `source_inputs` of the manifest now also name
`rmp_schedule.csv`, which holds the page's fetch hash and the values' content hash. Two notes that called MBS reinvestment at 0 "marked
question Q1" now cite her ruling of 19 October 2026; the table does not carry them.

| Series | Superseded digest (file kept) | Current digest | Rows |
|---|---|---|---|
| `announced_pace` | `b542577ce0a3aa051503b6606de4be6c7fa3d35222abc97218a67c48ca62b6ab` | `8036fe9b1dc25cfd34126e2c35e4e7885bdb6b5fa74cd516ac37265596209ab6` | 23 to 31 |

A reader that pinned the superseded digest still finds its bytes; it reads `None` from 12 January 2026 and must move to the current
digest for the monthly amounts.
