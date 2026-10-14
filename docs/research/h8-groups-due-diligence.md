# H.8 bank-group first prints: due diligence (#26)

**Serves:** groundwork G4 for H7m (`docs/research/plan.md`, #20): an input this repository owns. Nothing is scored.
**Status:** a record of what was checked, with the numbers it rests on. It decides nothing; data meaning is Nicholas
Beroud's and every judgement call below is marked as a question.

Reproduce every figure here with the commands in `scripts/extract_h8_groups.py` and
`scripts/diagnostics/h8_groups_diligence.py` (the archive pages are fetched with the parent's own
`repo_model.ingest.fetch_frb_h8_archive` into a raw root outside the tree; each page's SHA-256 is in
`tests/fixtures/snapshots/h8_groups/h8_group_first_print.releases.json`).

## What is read

Six lines, not seasonally adjusted, billions of dollars, week ending Wednesday, from the tables the release titles:

| Group | Table | Lines |
|---|---|---|
| Large domestically chartered commercial banks | 7 | `Cash assets`, `Total assets` |
| Small domestically chartered commercial banks | 9 | `Cash assets`, `Total assets` |
| Foreign-related institutions | 11 | `Cash assets`, `Total assets` |

The seasonally adjusted twins (tables 6, 8 and 10) have the same titles and are told apart by the unit line. Before the
2020s layout a table runs over two pages and its lines sit on either; the parser reads each line by its label from the
tables that carry the title and refuses a page with other than exactly one of each. Both layouts and the monthly columns
that precede the four week columns are covered by tests on two saved pages (`tests/fixtures/h8_pages/`).

## 1. The release time

- The Board releases the H.8 on Fridays at 4:15 p.m. Eastern, on the Thursday before a Friday holiday (the parent's
  `frb_h8` provenance quotes the release-date page). 4:15 p.m. is after the 16:00 decision instant, so a week printed
  on a Friday is read from the next business day.
- The pages state the date in every layout. 51 of the 452 pages read, from 25 September 2020 to 2 July 2026, also state
  "For release at 4:15 p.m. Eastern Time"; none states another time, and the extract refuses a page that does.
- Two exceptions, both the parent's: the page archived as `20201221/` states Friday 18 December 2020 (the later date is
  taken), and the index lists 2022-11-11 (Veterans Day) while the archive serves that release as `20221110/`.

## 2. The lag from the as-of week to publication

A week ending Wednesday is first printed in the release of the second Friday after it:

| Calendar days | Weeks |
|---|---|
| 8 (Thursday release before a Friday holiday) | 9 |
| 9 | 439 |
| 12 (a Monday release: 21 and 28 December 2020, 21 June 2021, 29 December 2025) | 4 |

452 weeks, 2017-12-27 to 2026-08-19. The declaration (`frb_h8_groups.release_lag`) is 12 days at 16:15, the measured
maximum and not above it, as the parent's `frb_h8` is. `h8.check_declared_lag` refuses a declaration shorter than any
release (`LookAheadError`) or longer than the slowest (`StaleReadError`).

## 3. Revisions

**A week is printed in four consecutive releases** (the first print and three more), and the later prints differ. Over
the 452 weeks, comparing the first print with the same week in the last release that carries it:

| Line | Weeks restated | Largest change ($bn) | Mean change when restated ($bn) |
|---|---|---|---|
| Large domestic, cash assets | 265 | 32.5 | 3.7 |
| Large domestic, total assets | 307 | 168.5 | 20.5 |
| Small domestic, cash assets | 430 | 39.1 | 3.8 |
| Small domestic, total assets | 440 | 149.7 | 14.6 |
| Foreign-related, cash assets | 207 | 43.7 | 7.6 |
| Foreign-related, total assets | 221 | 42.1 | 7.6 |

One or more of the six lines is restated in 451 of the 452 weeks. As a share of the first print, small domestic cash
assets move by a median 0.18% and 3.8% at the 95th percentile (largest 8.0%); large domestic cash assets 0.01% and
1.1% (largest 2.9%); foreign-related 0.00% and 1.8% (largest 5.5%). **Reading the latest vintage would therefore move
the group series, which is why only first prints are read** (answer 17(c)); a first print is never replaced by a
later one, and `h8.check_first_prints` refuses an extract that reads a week from any release but the earliest that
carries it.

**Reclassifications between the large and small groups are visible in these pages.** In 13 releases, one earlier week's
large and small total assets are restated by at least $50bn each, in opposite directions and by nearly the same amount
(for example the release of 2025-05-30 moves the week of 2025-04-30 by +143.5 for large and −143.7 for small):
2019-05-31, 2019-12-20, 2021-10-01, 2021-10-22, 2022-04-15, 2022-10-14, 2023-02-17, 2023-03-24, 2023-05-12, 2023-06-09,
2023-06-30, 2025-05-30 and 2026-02-13. The notes archive does not date them (section 5). Restatements of earlier
quarters' levels at a benchmark are not visible here: a page carries four weekly columns and some monthly ones, so
only the weeks inside the four-release window can be compared. **Question for Nicholas:** are these the large-bank panel
reassessments his answer 17(c) names, and which of them are the replacements on a merger?

## 4. Where first prints are recovered

- The release-date index lists 456 releases from 5 January 2018 to 25 September 2026. All 456 archived pages were
  fetched and all parse to the six lines; none was refused. The 452 on or before 3 September 2026 are read.
- A first print is recovered for every week from 2017-12-27 (first printed on 2018-01-05) to 2026-08-19 (first printed
  on 2026-08-28), with no hole. The first week is before the measurement panel's first date (2018-04-03), so every row of
  the panel sees the earlier weeks as they were public.
- **Refusals: none.** Nothing falls back to a later vintage. A week first printed after 3 September 2026 is not read
  (the lockbox's blind tier starts the next day): the releases of 4, 11, 18 and 25 September 2026 are not read.

## 5. Breaks

`docs/research/h8-group-breaks.json` records every note of the Board's "Notes on Data" page (`h8notes.htm`, retrieved
13 October 2026, saved gzipped with its SHA-256) as an as-of Wednesday from 2018-02-07 to 2026-07-01, with its text
verbatim: 43 events. By the opening of the note: 16 thrift conversions (10 alone, 6 with a nonbank acquisition), 7
acquisitions of nonbank assets, 9 divestitures to nonbanks, 9 reporting reclassifications (5 of domestically chartered
banks, 4 of foreign-related institutions) and 2 changes of accounting standard (ASU 2016-02 leases on 2019-04-03, ASU
2016-13 credit losses on 2020-05-06). The notes name "domestically chartered commercial banks" or "foreign-related
institutions"; **none splits large from small**. One note, as of 2026-09-30, is after the panel's last date and is not
recorded.

**What the notes do not carry, so what is not declared** (the record says so under `not_in_the_notes`):

- **The large-bank panel reassessments and replacements** of answer 17(c): no note dates one. Section 3 lists the
  releases that restate a week between the groups, which is evidence of them, not a declaration.
- **The 2023 failures and acquisitions.** The notes of 2023-03-22 and 2023-03-29 each record domestically chartered
  banks divesting $87 billion in assets to nonbank institutions (securities and loans); no note names Silicon Valley
  Bank, Signature Bank or First Republic, or a group, and none is dated for First Republic. They are recorded as stated.
  **Question for Nicholas:** which weeks are the three institutions' moves between groups, and from what source?

### 5a. The moves between the large and small groups, read against the notes (#47)

`docs/research/h8-group-moves.json` records the 13 releases of section 3 and the 2023 failures. Each release's archived
page and its predecessor's were read on 14 October 2026, with the notes of the Notes on Data page: **none of the 13 moves
has a cause stated by a note, so all 13 are `unexplained`; none of the four 2023 items (Silicon Valley Bank, Signature
Bank, their acquisitions, First Republic) is named by a note or dated to a week, so all four are `unexplained`.** Each
move is a structural break in the group input, flagged in the `h8_groups` snapshot (column `break_ids`) at the week its
release first printed: the first week of the first-print series on the new basis. Two corrections to section 3 follow
from the reading: the release of 2023-03-24 moves two weeks (2023-02-22 and 2023-03-01) by -50.1 on the large group and
+72.5 and +80.6 on the small, which is not "nearly the same amount"; and the dating of a restatement by the first
print is the latest the basis can have changed, not the week it did. `h8.difference` refuses a difference that spans a
flagged week.

## 6. Cash assets are not reserves

Recorded from Nicholas's answer 17 (`docs/decisions/data-meaning.md`): H.8 cash assets include vault cash, cash items in
process of collection and balances due from other depository institutions as well as balances at the Fed. They stand in
for reserves for large domestic banks and foreign-related institutions, and **overstate small domestic banks'
reserves**; the groups must not be summed naively, because balances due from other depository institutions are another
bank's liability. Build both series either way; **no candidate uses cash assets as reserves until a derived series
names this caveat**, and the registry's `limitation` carries it.

## 7. The scaling and the quarterly anchor: not built here

Answer 17(b) asks for the weekly group shares scaled to sum to H.4.1 reserve balances with a residual "other depository
institutions" group, anchored quarterly to "balances due from Federal Reserve Banks" (Call Report Schedule RC-A; the
FFIEC 002 for foreign branches), with weekly H.8 moves interpolating between quarters as of each first release.

- **The quarterly anchor is a new source** (the Call Report and FFIEC 002, retrievable first-filed data), too large for
  this pull request. It is for its own directive.
- **The weekly scaling is not built either, and the reason is not size.** Without the anchor nothing fixes the residual
  group: H.8 covers commercial banks only and the three groups' cash assets sum to the commercial banks' total, so the
  scale factor that makes the shares sum to reserves leaves "other depository institutions" undefined (zero, or the
  difference between reserves and an estimate of commercial banks' reserves that only the anchor supplies). Choosing
  one would be settling a data-meaning question in code. **It is queued with the anchor.**

## 8. What a page digest is

The `release_sha256` of each row is the SHA-256 of the bytes fetched, as the parent's `frb_h8` extract records it. It
**identifies the fetch behind a row, not the release's content**, the finding of #40 for the H.4.1 pages: the archive
injects per-request tokens. Two fetches of `releases/h8/20250103/` seconds apart are the same length (672,021 bytes) and
differ in 25 bytes, the `data-injected="worker-…"` value on the stylesheet link and the challenge script at the end of
the page. The values do not differ: the parser reads only the table cells, and every week's three total-assets lines
sum to the parent's separately fetched first print within 0.1. The remedy for #40 (hash the page without the injected
elements, or hash the extracted lines) is hers to choose and applies here and to the parent's H.8 extract alike; nothing
was changed for it.

## What was not checked

- **Report and line references against the current form instructions** (Nicholas's caveat). This pull request declares
  H.8 table lines as the release prints them (lines 29 and 33 in the 2025 layout), not FR 2644 item numbers, and does not
  declare any Call Report or FFIEC 002 item; that check belongs to the anchor directive.
- **The H.8 definition of cash assets by group in older vintages** (whether the line's content changed since 2018 beyond
  what the notes say) beyond the 13 group restatements in section 3.
- **Whether weekly cash assets of the three groups sum to the commercial banks' cash assets** the way total assets do:
  the parent holds only the all-banks total assets, so only that was cross-checked (every week within 0.1, from the same
  release).
