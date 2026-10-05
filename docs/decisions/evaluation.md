# Decision: how Phase 3 is judged

**DRAFT for Eleonora's review. Not in force until she merges it. No Phase 3 result is computed before it is merged.**

Ruling (Eleonora, 5 October 2026, on repo-market-model#233, question 4): "Yes, let's do that."

## Evidence sets

1. **Development:** as-of walk-forward on parent panel days up to 2025-12-31, on the parent's fold grid and guards.
2. **Confirmatory:** the parent's live record, from its first logged day (October 2026). This is the only data that is
   unseen once the parent's final test (#151) opens 2026.
3. **Not evidence:** 2026-01-01 to the day before the live record's first file. After #151 it has been seen. It may be
   shown descriptively, labelled as seen, and is never used to claim anything for Phase 3.

## To be fixed here before anything is scored (Eleonora's decision)

- **The primary comparison.** Proposed: the parent's published pressure probability (P(spread > +5 bp), one day ahead)
  with and without the latent state, paired, Brier score; benchmarks as the parent's (calendar climatology and the
  persistence-logistic model).
- **The pass rule.** Proposed, as the parent's final test: mean paired gain above 0 and its 90% stationary-bootstrap
  lower bound above 0; labels "shown better", "not shown", "shown worse".
- **Splits.** By regime and by pressure-day type, as the parent requires. A pooled figure alone is not a result.
- **Scoring dates on the live record.** Proposed: as the parent's live record, 2027-04-01 and then each 1 October.
