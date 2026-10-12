# Decision: duplicates of repo-market-model, deleted in its favour

**Status: a draft for Eleonora's review. It is in force once she merges it** (L0, #21).

Ruling (Eleonora, 12 October 2026, on
[repo-market-model#643](https://github.com/eleonorabjornberg/repo-market-model/issues/643#issuecomment-6130179990)):
"the liquidity repo ingests its own data, and duplicates are deleted in favour of this repo." "This repo" is
repo-market-model, where she wrote it. The relayed form on #21 is "Delete duplicates, favor the model, let liquidity
ingest its own data."

## What was deleted, and its successor

Each successor is read from the parent checkout at the pin (`PARENT_COMMIT`), never copied here.

| Deleted | Successor in repo-market-model |
|---|---|
| `src/repo_liquidity/fed_repo.py` (the 2019 to 2021 temporary repo operations, the combined take-up, its facility code, the material-use event) | `repo_model.fed_liquidity`, over the source `nyfed_repo_ops` (`metadata/sources_measurement.json`) |
| `tests/test_fed_repo.py`, and `fed_repo`'s two lag guards in `tests/test_guards.py` | the parent's own tests of `fed_liquidity` and `ingest._nyfed_repo_ops_rows` |
| `tests/fixtures/snapshots/nyfed_temp_repo/` (three saved searches, 2019-09-17 to 2021-07-28, with manifests) | `tests/fixtures/snapshots/repo_ops_inputs/nyfed_repo_ops/` (calendar years 2018 to 2025) |
| `scripts/fetch_temp_repo.py` (fetched those searches) | the parent's `fetch` of `nyfed_repo_ops` |
| `scheduled.py`'s IORB part: `IORB_RATE_TABLE`, `IORB_COLUMN`, `load_iorb_rates`, `iorb_in_force_values` | `repo_model.announced_iorb` (`load_announcements`); `curve_feature.iorb_in_force_values` reads it by `scheduled`'s rule |
| `tests/fixtures/snapshots/fomc_notes/iorb_rate.csv` and its manifest | `tests/fixtures/snapshots/fed-iorb-announcements/iorb_changes.csv` |
| `tests/fixtures/snapshots/fomc_notes/pages/monetary20190501a1.htm.gz`, the one saved page only the IORB table cited | the parent's `fed-iorb-announcements/pages/` |

`tests/test_deleted_duplicates.py` checks that the files are gone and that nothing under `src/`, `scripts/` or `tests/`
imports `fed_repo` or reads `scheduled`'s deleted names (an AST walk).

## What was kept, and is owned here

- **`h41.py`:** H.4.1 Treasury and MBS holdings, first prints. The parent's `h41_release.py` only dates FRED series by
  release, so it is not a duplicate.
- **`scheduled.py`'s ON RRP offering rate, standing repo facility rate and FOMC runoff caps,** with their tables under
  `tests/fixtures/snapshots/fomc_notes/`. The parent has no counterpart. They are not frozen.

## What the deletion changes

- **The IORB in force is unchanged.** The two tables had the same 31 notes, with the same announcement instants,
  effective dates and rates, through the note of 16 September 2026 (the test deleted with this repository's table
  checked it row for row). On every panel date, 2018-04-03 to 2026-09-03, the in-force rate read from the parent's
  table equals the one read from the deleted table.
- **The Fed repo take-up is not the same measurement.** The differences are written up for Eleonora and Nicholas in
  `docs/decisions/data-meaning.md`, "Note for Eleonora and Nicholas: the deleted `fed_repo` against the parent's
  `fed_liquidity`". Nothing here keeps a local copy to close them.
- **Panel versions 2 and 3** carried `fed_repo`'s columns. Their manifests stay as records, verified at the commit and
  parent pin they were made from (`scripts/verify_records.py`); `panel.build` no longer builds them. Version 1 does not
  read `fed_repo` and still builds, to the recorded bytes, at the new pin.
- **The Stage 4 freeze** hashes the deleted table and names, and the old pin. It is verified at its commit; at head it
  refuses with a `ValueError` that says so. Stage 5a, which forecast with it, was retired before it started.
