# Decision: how Phase 3 is judged

**Status: decided by Eleonora, 5 October 2026. In force once this record merges.** Every rule below is hers; nothing is a proposal any more.
No Phase 3 result is computed except under this record.

Ruling (Eleonora, 5 October 2026, on repo-market-model#233, question 4): "Yes, let's do that."

## Evidence sets

1. **Development:** as-of walk-forward on parent panel days up to 2025-12-31, on the parent's fold grid and guards.
2. **Confirmatory:** the parent's live record, from its first logged day (October 2026). This is the only data that is
   unseen once the parent's final test (#151) opens 2026.
3. **Not evidence:** 2026-01-01 to the day before the live record's first file. After #151 it has been seen. It may be
   shown descriptively, labelled as seen, and is never used to claim anything for Phase 3.

## Phase 3 freezes its own forecasts

Ruling (Eleonora, 5 October 2026; relayed by the orchestrating session): "Done, that sounds good."

- The parent's live record logs only the parent's published model and its baselines. A Phase 3 forecast made later for
  a logged day is made after that day's outcome exists, so it is not blind.
- **Once the Stage 3 model is frozen, Phase 3 logs its own forecast every business day, before the outcome**, to an
  append-only record in this repository, as the parent's live record does.
- **Only days logged that way are confirmatory evidence.** Live-record days before the freeze are treated like
  2026-01-01 onwards: shown if useful, labelled as seen, never used to claim anything.

## The comparison, the pass rule and the scoring dates

Ruling (Eleonora, 5 October 2026; relayed by the orchestrating session), accepting the primary comparison, the pass
rule, the scoring dates and the secondary Brier result as drafted below: "deal".

- **The primary metric is CRPS** (Eleonora, 5 October 2026; relayed by the orchestrating session: "Let's use crps"). Every day
  informs it, where a pressure-day Brier score rests on rare days, and it is the metric of the live record's primary
  result.
- **The primary comparison.** The parent's published predictive distribution of the spread, one day ahead,
  with and without the latent state, paired by day, CRPS; as-of persistence reported beside it, as in the live record.
  The pressure probability (P(spread > +5 bp), Brier, against calendar climatology and the persistence-logistic model)
  is reported as a secondary result and is not part of the pass rule.
- **The pass rule.** As the parent's final test: mean paired CRPS gain above 0 and its 90%
  stationary-bootstrap lower bound above 0; labels "shown better", "not shown", "shown worse".
- **Splits.** By regime and by pressure-day type, as the parent requires. A pooled figure alone is not a result.
- **Scoring dates on the live record.** As the parent's live record, 2027-04-01 and then each 1 October.

## Amendment: reform splits (reported only)

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), accepting `PLAN.md` D5 (the reform splits).

The confirmatory evidence crosses mandatory Treasury clearing: cash transactions from 2026-12-31 and repo transactions
from 2027-06-30, the latter between the scoring dates 2027-04-01 and 2027-10-01 (`reform-dates.md`).

- The confirmatory CRPS result is also reported split before and after each of those two dates, with the same interval
  method as the pooled result.
- **These splits are reported only.** They never decide the verdict. The primary comparison and the pass rule are
  unchanged.
- A split with too few days on one side is reported with its estimate and interval and labelled as such, never
  dropped.

## Amendment: what replaces the latent state (draft for Eleonora)

**Status: a draft for Eleonora's review. It is in force only once she merges it.** Until then the rules above stand
unamended.

Ruling (Eleonora, 7 October 2026; relayed by the orchestrating session), choosing option A, curve (a), one feature and
the freeze whatever development shows, from the questions put to her after Stage 3c. Stage 3c was not shown (#12),
so under `PLAN.md` ("After Stage 3b", point 4) the latent buffer is set aside and Stage 2's curve becomes the Stage 4
model.

The record above says "with and without the latent state" and "once the Stage 3 model is frozen". Read them as follows:

- **What replaces the latent state: the curve-implied spread.** At each refit, Stage 2's broken stick (corridor
  position against the reserves ratio, `demand_curve.fit_broken_stick`) is fitted as of that refit's cutoff, on
  training rows only. Its implied corridor position at the reserves ratio known at T's decision instant is converted
  to an implied SOFR − IORB in basis points, using the IORB and ON RRP rates in force on T as they were announced by
  then. That one number is the added feature.
- **The primary comparison** is the parent's published predictive distribution with and without that one feature.
  Everything else in the parent's declaration is unchanged, including the nested conformal PID. It is paired by day,
  scored by CRPS at h = 1, with as-of persistence beside it. The pass rule, the splits, the secondary Brier result and
  the scoring dates are unchanged.
- **The freeze.** "Once the Stage 3 model is frozen" reads "once the Stage 4 declaration is frozen". The declaration is
  frozen by checksum after the development walk-forward has been scored, **whatever its verdict**. Phase 3's own daily
  log starts from that freeze (Stage 5a), so that the confirmatory record is as long as it can be by 2027-04-01.
- **Both arms are logged.** Phase 3's daily log records, each business day before the outcome, the forecasts with and
  without the feature, both from the frozen declaration (Eleonora, 7 October 2026). The confirmatory pairing rests on
  that log alone.
- **One feature only.** The Stage 1b indicators, the MBS flow and the take-up events are not part of this comparison.
  Any of them is a separate comparison, written and frozen before it is scored.
