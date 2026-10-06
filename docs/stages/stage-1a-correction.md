# Stage 1a correction: plan

**Written 6 October 2026, before anything is built.** Eleonora agreed it on 6 October 2026, after Nicholas Beroud
answered questions 1 to 13 (`docs/decisions/data-meaning.md`). It corrects Stage 1a (#6) where he corrected the
preliminary answers. It is built only after Stage 3b (#9) is reviewed.

## What it adds

1. **The realized weekly change in the Fed's MBS holdings (his answer 1).**
   - Read from the same archived H.4.1 releases as the Treasury change. Table 1 carries a "Mortgage-backed
     securities" row in the same layout (checked on the 2018 and 2025 pages in `tests/fixtures/h41_pages/`).
   - The tracked extract kept only the Treasury row, so the releases are fetched again from federalreserve.gov
     (reachable from the cloud).
   - A new column, `soma_mbs_weekly_change` ($bn), under a new overlay source `frb_h41_mbs` with the same record-date
     declaration as `frb_h41_treasury`. Its worst-case lag is measured from the release dates.
   - The Treasury extract and its digest are not changed.
   - Agency debt is left out: it has been small since 2019. Whether it should be included is Nicholas's call.
2. **The Fed's 2019 to 2021 repo operations as take-up from a different facility (his answer 5).**
   - Read from the NY Fed's repo operation results (`markets.newyorkfed.org/api/rp/results`, the API the parent's
     `nyfed_srf` snapshots come from, reachable from the cloud).
   - A check today found daily operations from 2019-09-17, overnight and term, through 2020 (with zero take-up late in
     2020) into 2021. In May 2019 there were two small operations, which were tests.
   - New columns:
     - `fed_repo_take_up` ($bn): a structural 0.0 before 2019-09-17; the temporary operations from 2019-09-17 to
       2021-07-28; the standing facility from 2021-07-29;
     - `fed_repo_facility`: none, temporary or standing.
   - Availability is the parent's `nyfed_srf` declaration: the next weekday at 16:00.
   - `srf_take_up` keeps Stage 1a's treatment (missing before 2021-07-29), so Stage 2 and 3b reproduce.
   - **A question for Nicholas before it is built:** do the temporary operations' **term** repos count as take-up?
     The parent counts only overnight operations for the standing facility. This plan counts overnight only and reports
     term beside it.
3. **The standing facility's material-use event (his answer 13).**
   - `srf_material_use`: 1 on a day with standing-facility take-up of $1bn or more, else 0, from 2021-07-29. The
     threshold was fixed by Nicholas in advance.
   - The parent already drops the Desk's small-value exercises. The event ignores the remaining small trades by
     construction.
   - An outcome the model explains, not an input.
4. **The distance to the ceiling stays missing before 2021-07-29** (his answer 5), as Stage 1a built it.

## What it must show

1. Every new input passes the parent's guards, and each new guard has one recorded mutation that kills it.
2. The parent's published panel still rebuilds to its digest, and Stage 1a's columns are unchanged apart from the
   additions. The new manifest lists every change.
3. Coverage from 2018-04-03, with every hole and refusal listed, and the structural zero, the temporary facility and
   the standing facility shown in their own date ranges.
4. Stage 2's record and Stage 3b's record still regenerate unchanged (they read none of the new columns).
5. No scores and no figures.

## Not in it

Stage 1b's indicators (`docs/stages/stage-1b.md`), the bank-size split, and any model change. Using the new columns in
a model is a later directive's decision.
