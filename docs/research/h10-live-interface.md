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

`h10_live.attribute_onset(panel_rows, rule, onset_date, report_date, *, draws=10_000, null_draws=1_000) -> dict`

| | |
|---|---|
| **Inputs** | `panel_rows`: the parent's `DailyObservation` rows in date order (`repo_model.data.load_daily_panel`). `rule`: the parent's `InformationRule` over `spread_bps` and the five drivers, at the 16:00 decision instant (`h10_apply.real_rule`). `onset_date`: a day the parent's onset rule flags. `report_date`: the panel day the episode is reported on. `draws` and `null_draws` are the method's values; a caller does not change them. |
| **What is read** | Only what was public at the decision instant of `report_date` (`h10-method.md` section 6). The window's spread and drivers are checked with `attribution.check_window_public`. The fitting sample, the placebo windows and the selection null use only the windows already public then; rows after the last public day are cut off before any of them is built and are never read. |
| **Output** | One JSON-able row in the columns of the development table (`results/h10/development.json`, one entry of `episodes`), plus `method_digest`, `parent_commit`, `parent_panel_sha256` and `last_day_read`. An onset that cannot be attributed (an input missing, no rise in the spread, a singular fit) is returned as `"not attributable"` with its `reason`, never dropped; in the outcome rule it stays in the denominator as a miss. |
| **Raises** | `LookAheadError`: a day of the rows is in a locked tier of the parent's lockbox, or an input of the onset's window was not public at the report instant. `ValueError`: the onset or report date is not a day of the rows; the report is before the onset, or **more than 10 panel days after it** (plan, Q7); the day is not an onset under the parent's rule (`onset_flags`, cross-checked with `pressure.onsets`). |

The counts the row carries (`under_bar`, `beats_null`, `counted`) are those of the development table: the residual bar of
section 5, the selection null of section 9 and both together. The row is an input to a report; whether and how it is
published is the model repo's live record's, and a registration is Eleonora's attested act.

## The method digest

`h10_live.method_digest()` is one sha256 over the frozen method, hashed in this fixed order, each part as
`name NUL length NUL bytes`:

1. `record:docs/decisions/h10-method.md` (the decision record, sections 1 to 10),
2. `code:src/repo_liquidity/attribution.py`,
3. `code:src/repo_liquidity/h10_apply.py`,
4. `constants`: the decided values (baseline and window days, placebo windows and floor, bootstrap block, draws, seed, level,
   residual bar, majority, null draws and quantile, the five drivers, report days, decision time) as sorted compact JSON.

`h10_live.method_parts()` lists the parts and `h10_live.record_sha256()` is the first part's own sha256. At this commit:

| | |
|---|---|
| `method_digest()` | `081a8cab4bea848b387d16f52cbd7b748a54c0b6a4935cb4802ac9aa0ea52b93` |
| `record_sha256()` (the record alone) | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` |

**This is not the number PR #78 published, and why.** PR #78's page and log entry gave `cae658c6…f126` as the "method record
sha256". That was the sha256 of the record file alone, taken before section 10 (the 2 bp placebo floor, PR #88) amended the
record. The record as it stood at `9a32493` hashes to `cae658c6…f126`; at `9fee94f` (PR #88) it hashes to `642fe092…a9`. So
the record part moved when the amendment merged (as directive #87 expected), and `method_digest()` is a different quantity
besides, because it also covers the code and the constants. `tests/test_h10_live.py` reproduces #78's number from the record
as it stood at `9a32493` wherever the git history holds that commit. The method was not changed to make anything match.

A change to any of the four parts changes the digest, so a digest read from a record names exactly the method that produced
it. A later amendment to the record, the code or a decided value gives a new digest; the model repo reads the digest of the
commit it calls.

## How the model repo calls it

The model repo's live-record job calls `attribute_onset` at **this repository's commit** (a pin it holds, as this repository
holds the parent's pin) and stores the row beside the digest the row carries. This repository keeps no log, runs no
schedule and does not write to the model repo. The pin and the panel digest in the row are the parent's, as this repository
reads them (`repo_liquidity.PARENT_COMMIT`, `PANEL_SHA256`).
