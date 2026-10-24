# The announced balance-sheet pace (#125, avenue #56; H7 groundwork)

**Status: groundwork for H7. An input, not a result.** Nothing is wired into an estimator, a score or the panel, and
no figure is published. Eleonora merges: it publishes a snapshot and carries a data-meaning question.

## Why

`runoff_caps` is the only balance-sheet-pace input so far. It reads (0, 0) from 1 August 2019 and again from
1 December 2025, so H7 would see a flat balance sheet in both periods. In fact the Fed was adding reserves: it bought
Treasury bills from 15 October 2019, bought assets at scale from March 2020 to March 2022, and from 12 December 2025
bought bills to keep reserves ample.

## Definition

One row per announcement of a runoff cap or of purchases (`tests/fixtures/snapshots/fomc_notes/announced_pace.csv`,
built by `scripts/build_announced_pace.py` from `runoff_caps.csv` and `announced_purchases.csv`, never edited by hand):

- the Treasury and MBS runoff caps in force;
- the announced monthly net purchases of Treasury securities and of agency MBS, in $bn;
- the signed pace, caps minus purchases, in $bn a month. Positive drains the balance sheet, negative grows it.

A row is public at its announcement instant and effective from its effective date; values hold between announcements and
are never revised. A reader uses the parent's scheduled-availability rule: the row announced at or before the decision
instant and effective on or before the day, the newest of them.

## What enters, and what does not

- **Enters:** reserve management purchases and net asset purchases, as announced ("approximately", "at least").
- **Does not enter:** reinvestment of principal payments, which holds reserves constant. This includes the reinvestment of
  agency paydowns into Treasury bills since December 2025 (the Dec 2025 note's last directive line), so MBS paydowns above
  the MBS cap that are reinvested in Treasuries enter at 0. **Decided by Eleonora, 19 October 2026** ([ruling on #130](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/130#issuecomment-6278307470)): MBS reinvestment counts as 0 (reserve-neutral) in the signed pace.
- **Unquantified:** a row where no monthly amount was announced has empty purchases and signed pace, and a reader gets
  `None`. These are the March 2020 plan (at least $500 billion and $200 billion "over coming months", then "in the amounts
  needed") and the days from 12 to 15 January 2026, after the first schedule of December 2025 (about $40 billion for
  12 December 2025 to about 12 January 2026) and before the January amount was public.
- **The monthly reserve management purchases after December 2025** are the amounts the Desk's operational-details page states
  for each monthly period (**decided by Eleonora, 21 October 2026**, [ruling on #156](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/156#issuecomment-6318942760);
  built in #158). Each is public from its publication instant and effective from the period's start. The page states
  no publication time. The Desk publishes the amounts "on or around the ninth business day of each month" (its 10 December 2025
  statement), which is before every period starts, so a period is taken as published at the end of the last business day before
  it starts (a day late at worst, never early). `rmp_schedule.csv` records each period's amounts, that instant, the schedule
  PDF's creation time as evidence (a PDF created after its period began was re-created with the results and is no evidence), the
  saved page's fetch hash and the values' content hash. The page is a living page saved on 23 October 2026: it holds each period's
  amounts as they stand then, and an earlier edit of a past row would not show. Periods announced after the development end are
  not entered.

## Dates and times

- A Board statement is read at the minute it states. A Desk statement states no time, so its row is read from 23:59 on its
  date (the conservative direction).
- A date the page does not state is a convention, named in `effective_basis`: mid-November and mid-December 2021 (the 15th),
  the end of net purchases in early March 2022 (the 14th, the day the next monthly period would have begun), 24 March 2020
  (the day after the "no limit" statement, because the table needs an effective date after the announcement day) and the end of
  the first December 2025 schedule (12 January 2026).

## Sources

Each purchase row quotes the phrases that state its amounts and dates from its saved page, and
`tests/test_announced_pace.py` checks each phrase against the page. Pages are saved under
`tests/fixtures/snapshots/fomc_notes/pages/`; their SHA-256 are in `snapshots/announced_pace/manifest.json`. Statements that keep
the pace and add no row (checked, 19 October 2026): the Desk statements of 12 and 13 March 2020 ($60 billion a month for the
period from 13 March), 16 September 2020 and 16 December 2020 ($80 billion and $40 billion a month). The FOMC's
17 June 2026 note changes "increase" to "when appropriate, increase"; it states no amount and adds no row.
