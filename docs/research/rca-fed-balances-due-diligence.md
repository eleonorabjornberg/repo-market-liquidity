# Group reserves (#43): due diligence on the quarterly anchor

**Status (updated 14 October 2026 by the fix run on Eleonora's rulings; the sections below are the first run's text, kept as
written, and section 7 says what changed).** Step 1 found that the anchor Nicholas's answer 17(b) asks for can be read for
domestic banks from the CDR bulk files, that the FFIEC 002 for foreign-related institutions cannot be read from any source
this environment reaches, and that the domestic items cover about 54% to 67% of H.4.1 reserve balances. Eleonora has since
ruled (section 7): the foreign group's weekly level is the H.8 foreign-related cash assets, labelled an approximation, and no
FFIEC 002 is read. The anchor overlay and the weekly series are now built (`repo_liquidity.rca`,
`repo_liquidity.group_reserves`); section 7 reports what they show. Hypothesis and step: H7m, groundwork G4 (candidate C).
No score.

Answer 17 is recorded in `docs/decisions/data-meaning.md`; answer 16(d) as amended by Eleonora's ruling of 13 October
2026 (PR #44) sets how a Call Report figure is dated. Read with both.

## 1. The items

- **Domestic banks, Call Report (FFIEC 031/041) Schedule RC-A, "Balances due from Federal Reserve Banks".** In the CDR
  bulk file of the Call Report (`Call Schedule RCA`) the item is `RCFD0090` (consolidated) and `RCON0090` (domestic
  offices), USD thousands; the file's own description is "BALANCES WITH F. R. BKS (COML BK BOOK)". It is the item
  answer 17(b) names. **Not checked against the current FFIEC 031/041 instructions** (his caveat): www.ffiec.gov, where
  they are published, is refused by the environment's proxy (section 5). The mnemonic and the label are read from the
  file, not from the instructions.
- **Who carries it.** Every filer has a row in `Call Schedule RCA`, but the item is filled for a minority:

  | quarter-end | file as of | filers | carrying item 0090 | sum, $bn | 25 largest by total assets: carrying, sum $bn |
  |---|---|---|---|---|---|
  | 2018-03-31 | 2025-06-15 | 5,656 | 1,258 | 1,199.2 | 25, 931.5 |
  | 2020-12-31 | 2024-11-15 | 5,049 | 948 | 2,078.1 | 25, 1,543.6 |
  | 2023-06-30 | 2026-09-15 | 4,696 | 902 | 1,791.4 | 25, 1,436.1 |
  | 2025-12-31 | 2026-09-15 | 4,393 | 830 | 1,605.7 | 25, 1,212.3 |
  | 2026-06-30 | 2026-09-15 | 4,296 | 806 | 1,631.7 | 25, 1,268.5 |

  A filer without the item reports balances due from depository institutions in Schedule RC items 1.a and 1.b
  (`RCON0081`, `RCON0071`), which do not separate the Federal Reserve Banks. Why the schedule is filled for some filers
  only is **not established** here (the instructions are unreachable); the data show the pattern, not the rule.
- **Foreign branches and agencies, FFIEC 002.** The directive names "the corresponding item of the FFIEC 002".
  **It is not in the CDR bulk files**: the portal's products are "Call Reports -- Single Period", the four-period
  balance-sheet series, and four UBPR products, and the Call Report zip has no FFIEC 002 schedule. The FFIEC 002 is
  published through the FFIEC's National Information Center pages on www.ffiec.gov, which this environment refuses
  (section 5). So **no FFIEC 002 figure, and no FFIEC 002 first-filing time, was read** ("if the FFIEC 002 files carry
  first-filing times after all, say so": this is not known, because the files could not be reached).

## 2. How far the item reaches H.4.1 reserves

`scripts/diagnostics/ffiec_rca_diligence.py` sets the sum of item 0090 beside the weekly H.4.1 reserve balances
(`WRESBAL`, the parent's ALFRED snapshot of 12 September 2026, a week average, millions of dollars) for the week ending
nearest the quarter-end:

| quarter-end | WRESBAL week | WRESBAL, $bn | item 0090 sum as a share of it |
|---|---|---|---|
| 2018-03-31 | 2018-03-28 | 2,113.3 | 57% |
| 2020-12-31 | 2020-12-30 | 3,122.2 | 67% |
| 2023-06-30 | 2023-06-28 | 3,171.6 | 56% |
| 2025-12-31 | 2025-12-31 | 2,957.4 | 54% |
| 2026-06-30 | 2026-07-01 | 2,967.0 | 55% |

The rest, 33% to 46%, is balances that the domestic Call Report item does not show: foreign-related institutions' (the
FFIEC 002 filers, not read), and any domestic filer that does not carry the item, and other depositories (credit unions
file with the NCUA, not in these files). **The split of that remainder among those parts is not established here.**
A quarter-end Call Report balance and a week-average H.4.1 level are not the same quantity, and the weeks differ by up to
three days; the shares are an order of magnitude, not a reconciliation.

## 3. Aggregation to the three H.8 groups

- **Large domestic and small domestic.** The H.8 groups are the 25 largest domestically chartered commercial banks and
  the rest (answer 17(c): "the top 25 by domestic assets", reassessed at each benchmark). The Call Report files carry
  each filer's total assets (`RCFD2170`/`RCON2170`) but not the Board's list, and the Board's panel is assessed against
  the Call Reports at each benchmark. The diagnostic uses the 25 largest filers by consolidated total assets as a
  stand-in: for every quarter above all 25 carry the item. **That list is not the Board's panel**, and the files do not
  show which filers are commercial banks as against the savings institutions the H.8 excludes. Matching the groups
  exactly needs the Board's panel list per benchmark, which may be in the H.8 release notes behind
  `docs/research/h8-group-breaks.json`; it was not read for this step.
- **Foreign-related institutions.** Anchored by the FFIEC 002, not read (section 1). Without it the three groups cannot be
  anchored and the "other depository institutions" residual of answer 17(b) cannot be separated from the foreign group:
  the scaling would put all of the 33% to 46% above in one residual.

## 4. When a figure is public, and revisions

Eleonora's ruling of 13 October 2026 on PR #44, Q1: use the latest-filed Call Report figures as a labelled input, each
available only from its **latest-update time**. The diagnostic reads that time ("Last Date/Time Submission Updated On",
`Call Bulk POR`) for the filers that carry item 0090:

| quarter-end | median days from quarter-end | max | updated more than 45 days after |
|---|---|---|---|
| 2018-03-31 | 30 | 1,595 | 389 of 1,258 |
| 2020-12-31 | 29 | 1,251 | 295 of 948 |
| 2023-06-30 | 33 | 1,092 | 385 of 902 |
| 2025-12-31 | 30 | 254 | 156 of 830 |
| 2026-06-30 | 29 | 73 | 37 of 806 |

So a typical filer's latest update falls about a month after quarter-end, but a third to nearly a half of those for the
older quarters were last updated after any filing deadline. Under the ruling an anchor for such a filer is unavailable
from its quarter-end until that update, and the figure read is the amended one. Every file here is rebuilt from the
repository's current content (the "as of" dates above), so revisions are not visible: the file carries only the latest
value. The scheduled archive (#46, PR #49) keeps first prints from now on. **The posting lag between a submission and
its public availability is not recorded** and is not assumed.

## 5. What could not be read

- **www.ffiec.gov** (the FFIEC 002 data, and the form instructions): refused by the proxy.
  `curl -sS https://www.ffiec.gov/npw/FinancialReport/DataDownload` returned `curl: (56) CONNECT tunnel failed, response 403`
  on 14 October 2026. No other route was tried (nothing is worked around). `cdr.ffiec.gov` is reachable.
- The current FFIEC 031/041 and 002 instructions, and the Board's large-bank panel list.

## 6. Why the anchor and the weekly series are not built here

Both need a foreign-related anchor and a group mapping that this step could not establish (sections 1 and 3). Building
the domestic half alone would put 33% to 46% of reserves in an unexplained residual and publish a series whose caveat is
larger than its content. Under `CLAUDE.md` ("step by step", "judgement calls are hers") the choices are Eleonora's; they
are asked in the pull request.

## Checksums of the files read

```
a9be30d444f7a2dd4d43db96d2a8bc56eb8deac28387617b7bcb46482742f87c  FFIEC CDR Call Bulk All Schedules 03312018.zip
4b4228ca49d1a6e92210cbbc2d6eab43ff447a7201726c1a905967072096e061  FFIEC CDR Call Bulk All Schedules 12312020.zip
49c6c8e6f5a7df28f102b25d8ca4e61616fb89eefba595e98c179b5cbd5800f0  FFIEC CDR Call Bulk All Schedules 06302023.zip
66d9881a82c4e7391acfe7b75fa2ada5c6fcbd8fb8325a71025b50fd62db6097  FFIEC CDR Call Bulk All Schedules 12312025.zip
0a2d59ce16b5a5b756765e00364d525855019ac657e0398c96323aebfa1679fe  FFIEC CDR Call Bulk All Schedules 06302026.zip
```

The zips are not tracked. A later fetch of the same quarter gives a later "as of" date and possibly other values; that is
the finding of PR #44.

## How to reproduce

Fetch the quarters from the bulk page (product "Call Reports -- Single Period", format "Tab Delimited"), save the zips
in one directory, then:

```
python3 -I scripts/diagnostics/ffiec_rca_diligence.py DIRECTORY --reserves \
  <parent>/tests/fixtures/snapshots/alfred-wresbal/WRESBAL_2026-09-12.csv
```

## 7. Update, 14 October 2026: the rulings and what the build shows

**Rulings** (recorded as row 18 of `docs/decisions/data-meaning.md`, drafted for her to merge):

- Q1 (16:12 UTC): www.ffiec.gov allowed. The fix run found it moot: www.ffiec.gov passes the proxy but FFIEC itself answers
  `curl -sS https://www.ffiec.gov/npw/FinancialReport/DataDownload` with HTTP 403 and a page titled "CAPTCHA Error | FFIEC" (a bot
  block on their side; nothing was worked around). The current form instructions therefore remain unchecked.
- Q2: no domestic-only series. Q3: top 25 by domestic assets, labelled an approximation, the Board's list where found.
- 19:13 UTC, option (a): the H.8 foreign-related institutions' cash assets (weekly first prints) are the foreign group's level,
  labelled an approximation; no FFIEC 002 for now (a hand-downloaded one may come later as a sensitivity check).

**What was built.** `repo_liquidity.rca` reads RC-A item 0090 from the 34 stored quarters (2018-03-31 to 2026-06-30) into
two groups (the 25 filers with the largest total assets; every other carrying filer), each a latest-filed sum available from
the day after its slowest member's latest update (`declarations/ffiec_call_rca.json`, snapshot `snapshots/rca_anchor/`).
`repo_liquidity.group_reserves` does **not** read the anchor (her ruling of 14 October 2026, option (i), comment 6178605509):
each of the three groups is the H.8 group's cash assets, first print, unanchored and labelled an approximation, and the
residual "other depository institutions" is H.4.1 reserves less the three. The anchor stays as a published input for a
later, anchored version.

**What it shows (generated tables: `docs/research/rca-anchor-coverage.md`, `docs/research/group-reserves-coverage.md`).**

1. **The anchor is very stale in real time.** Under the amended answer 16(d) a figure is available only from its latest-update
   time, and a group's sum from its slowest member's. For the large group the extract's figures became available 189 to 1,714
   days after quarter-end (the quarters not withheld; 1,358 days for 2018Q1, 1,714 for 2018Q2); for the small group 972 to
   1,596. The share of the large group's balance whose own latest update fell within 45 days of quarter-end is 2% to 39% for
   the quarters to 2024 (36% to 79% for the small group), so a partial-sum reading would have undercounted badly (the
   diagnostic table in the coverage record; no model reads it).
2. **Twelve of 68 group-quarters are withheld**, because a member was last updated after the parent's development end
   (2026-09-10 and 2026-09-11, a batch of resubmissions): the small group for 2024Q1 to 2026Q2 (ten quarters) and the large
   group for 2026Q1 and 2026Q2.
3. **No week has a row.** Of 452 H.8 weeks, 241 have no anchor public for both domestic groups (the first pair is public on
   2022-08-13), and the other 211 stand on an anchor whose week lies before an H.8 break week, so the move is refused
   (`h8.difference`'s rule).
4. **The approximations are coherent where they can be computed.** With the break refusal switched off (a diagnostic, never a
   series) the 211 weeks from 2022-08-10 give a residual "other depository institutions" of about 150 to 480 billion dollars with
   one negative week, so the three groups do not overshoot reserves.

**Why this is a question for her, not a code choice.** Three readings are open and each changes what is available: (i) how a
group's sum becomes public (slowest member, as built; a completeness threshold; or filer-by-filer carry-forward);
(ii) how a weekly move is split when the anchor and the H.8 disagree in sign, and whether a ratio across a break may be
adjusted; (iii) whether the anchor may be a labelled retrospective input outside the information set for the measurement claim
H7m. They are asked in PR #50. Until she rules, the weekly series is published as its builder, its tests and its coverage
record, with no row, and no snapshot of it is published.
