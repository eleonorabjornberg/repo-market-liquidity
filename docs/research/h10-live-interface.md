# H10 prospective confirmation: the live entry point (directive #87, finding #81)

**Serves H10, prospective confirmation (plan, H10 "Prospective confirmation"; milestone M3).** This is an interface note, not
a decision record. It decides nothing. It registers nothing, runs no prospective attribution, and reads no real onset after
2026-09-03. Eleonora's ruling on finding #81 (14 October 2026) is that the model repo's live-record job runs the attribution
at the pin, and that this repository publishes the function and its digest. The split of
[repo-market-model#643](https://github.com/eleonorabjornberg/repo-market-model/issues/643) stands: the model repo owns the
live record, and **this repository runs no schedule and writes no log.**

## The entry point

```python
from repo_liquidity import h10_apply, h10_live

rows, manifest = h10_apply.load_development()          # or the model repo's own rows, as of the report day
with h10_apply.real_rule() as rule:                     # the parent's InformationRule over the spread and the five drivers
    row = h10_live.attribute_onset(rows, rule, onset_date, report_date)
```

`h10_live.attribute_onset(panel_rows, rule, onset_date, report_date, *, draws=10_000, null_draws=1_000, allow_unpinned_parent=False) -> dict`

| | |
|---|---|
| **Inputs** | `panel_rows`: the parent's `DailyObservation` rows in date order (`repo_model.data.load_daily_panel`). `rule`: the parent's `InformationRule` over `spread_bps` and the five drivers, at the decision instant, 18:00 (`h10_apply.DECISION_TIME`, one line; `h10_apply.real_rule`). `onset_date`: a day the parent's onset rule flags. `report_date`: the panel day the episode is reported on. `draws` and `null_draws` are the method's values; a caller does not change them. `allow_unpinned_parent` is the explicit override of the pin check below; the row records it. |
| **What is read** | Only what was public at the decision instant of `report_date` (`h10-method.md` section 6). The window's spread and drivers are checked with `attribution.check_window_public`. The fitting sample, the placebo windows and the selection null use only the windows already public then; rows after the last public day are cut off before any of them is built and are never read. |
| **Output** | One JSON-able row in the columns of the development table (`results/h10/development.json`, one entry of `episodes`), plus `method_digest`, `parent_commit`, `parent_panel_sha256`, `last_day_read`, the floored placebo reading and the stamp (below). An onset that cannot be attributed (an input missing, no rise in the spread, a singular fit) is returned as `"not attributable"` with its `reason`, never dropped; in the outcome rule it stays in the denominator as a miss. |
| **Raises** | `LookAheadError`: a day of the rows is in a locked tier of the parent's lockbox, or an input of the onset's window was not public at the report instant. `ValueError`: the onset or report date is not a day of the rows; the report is before the onset, or **more than 10 panel days after it** (plan, Q7); the day is not an onset under the parent's rule (`onset_flags`, cross-checked with `pressure.onsets`); the imported `repo_model` is not a clean checkout of `PARENT_COMMIT` and no override is passed. |

**The two placebo readings.** `h10-method.md` section 10, rule 3 (PR #88), requires both. `placebo` is the unfloored reading
under the name `results/h10/development.json` uses; `placebo_floored` is the reading over the placebo windows whose spread rise
is at least 2 bp, with the keys of the `floored` entries of `results/h10/placebo_floor_2bp.json` (`windows`, `excluded`,
`attributed`, `median_explained`, `share_at_or_above`). Both come from the same placebo windows.

**The stamp** names what the row was computed from (finding #119, point 2), beside the constants the digest covers:

| Column | Meaning |
|---|---|
| `panel_rows_sha256` | sha256 of the `panel_rows` as given (`h10_live.rows_sha256`: date, spread and values of every row, sorted compact JSON, one line per row). It covers rows after the report day too, which are never read, so it moves with them; the method's columns do not. |
| `rows_are_published_panel` | `True` only when that sha256 equals the one of the pinned published panel to the development end (`h10_live.published_panel_rows_sha256`, rebuilt from the tracked fixtures and refused if it is not the manifest's). A live panel that has more days than the published one is `False`: the row says it is not the pinned published panel. |
| `imported_parent_commit`, `imported_parent_clean` | The commit of the checkout `repo_model` is imported from and whether its tracked files are unmodified, read with git when the row is made. |
| `parent_override` | `True` if the run was made with `allow_unpinned_parent=True`. |

The entry point raises `ValueError`, before anything is computed, when the imported `repo_model` is not at `PARENT_COMMIT`, has
modified tracked files, or is not a git checkout, unless the override is passed.

The counts the row carries (`under_bar`, `beats_null`, `counted`) are those of the development table: the residual bar of
section 5, the selection null of section 9 and both together. The row is an input to a report; whether and how it is
published is the model repo's live record's, and a registration is Eleonora's attested act.

## The method digest

`h10_live.method_digest()` is one sha256 over the frozen method, hashed in this fixed order, each part as
`name NUL length NUL bytes`:

1. `record:docs/decisions/h10-method.md` (the decision record, sections 1 to 10),
2. `code:src/repo_liquidity/attribution.py`,
3. `code:src/repo_liquidity/h10_apply.py`,
4. `code:src/repo_liquidity/h10_live.py` (the as-of cut, the regime split and `counted`; new in #121),
5. the parent files the result depends on, each named `parent@<PARENT_COMMIT>:<path>` and read from the imported `repo_model`
   tree (new in #121): `src/repo_model/onset.py` (the onset rule), `pressure.py` (the onsets it is cross-checked with),
   `asof.py` (`InformationRule`), `contract.py` (`ON_RRP_DEPLETION_BREAK_BN`) and `metrics.py` (the stationary bootstrap),
6. `constants`: the decided values (baseline and window days, placebo windows and floor, bootstrap block, draws, seed, level,
   residual bar, majority, null draws and quantile, the five drivers, report days, decision time, and the ON RRP depletion
   break) as sorted compact JSON.

The parent's lockbox is a guard that refuses a run; it decides no result and is not a part. Because the parent parts are named
by the pin, moving the pin changes the digest even if the files were identical.

`h10_live.method_parts()` lists the parts and `h10_live.record_sha256()` is the first part's own sha256. At this commit (the digest before #121 was `081a8cab…2b93`; it covered three files and the constants, and is superseded):

| | |
|---|---|
| `method_digest()` | `cc7bab6ea31ef51c839b17b237a8b92bd12afa60c191fe91f15d33286a1249b1` |
| `record_sha256()` (the record alone) | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` |

**This is not the number PR #78 published, and why.** PR #78's page and log entry gave `cae658c6…f126` as the "method record
sha256". That was the sha256 of the record file alone, taken before section 10 (the 2 bp placebo floor, PR #88) amended the
record. The record as it stood at `9a32493` hashes to `cae658c6…f126`; at `9fee94f` (PR #88) it hashes to `642fe092…a9`. So
the record part moved when the amendment merged (as directive #87 expected), and `method_digest()` is a different quantity
besides, because it also covers the code and the constants. `tests/test_h10_live.py` reproduces #78's number from the record
as it stood at `9a32493` wherever the git history holds that commit. The method was not changed to make anything match.

A change to any part changes the digest, so a digest read from a record names exactly the method that produced
it. A later amendment to the record, the code or a decided value gives a new digest; the model repo reads the digest of the
commit it calls.

## How the model repo calls it

The model repo's live-record job calls `attribute_onset` at **this repository's commit** (a pin it holds, as this repository
holds the parent's pin) and stores the row beside the digest the row carries. This repository keeps no log, runs no
schedule and does not write to the model repo. The pin and the panel digest in the row are the parent's, as this repository
reads them (`repo_liquidity.PARENT_COMMIT`, `PANEL_SHA256`).
