# H7m, the run of the calendar-clean variants of C and D: what the code does and the readings it took

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development steps 2 (candidate C) and 3 (candidate
D). Directive #147. It implements, with no choice of its own, the declaration in `docs/stages/h7-calendar-clean.md` (merged with
#146). **Development, never a verdict** (`docs/decisions/measurement-protocol.md` §1): no locked day, no goalpost 3, nothing
scored against the stress events.

Code: `src/repo_liquidity/h7_clean.py`. Tests: `tests/test_h7_clean.py`. Run: `scripts/h7_calendar_clean.py`, which writes
`results/h7/calendar-clean.json` and prints `docs/research/h7-calendar-clean.md` from it (`--render` prints it again from the tracked record). The record is generated output and is never
edited by hand.

## The command

```
PYTHONPATH=src:<repo-market-model at 8fd2cf8c72e7d5c6e81c509651b684b690054a6f>/src \
  python3 -B scripts/h7_calendar_clean.py --replications 2000 --workers 8
```

`--workers` only spreads the bootstrap draws over processes; the draws and the record do not depend on it. A variant's work is
kept in `results/h7/calendar-clean.parts/<variant>.json` (not tracked) when it finishes, and a rerun reuses it. `--variants`
runs some of `C,D,CV1,CV2,DV1,DV2`; `--limit-refits N` runs the first N refits.

## What is implemented, by section of the declaration

- **2(a), the exclusion set.** `h7_clean.read_flags` reads the parent's `settlement_day` and `quarter_end_window` for every
  scored day through `repo_model.asof.InformationRule` (the composed feature is formed by the parent's own composer), at the day's
  own decision instant. `quarter_end_window` is the parent's opt-in column, a function of the date alone
  (`data.quarter_end_window`), added to the rows with `with_quarter_end_window`. A flag read for any row but the scored one is a
  `LookAheadError` (`check_flag_reads`), and a day's flags must be that day's own (`clean_days`). The counted-episode rule is taken
  over the clean days, a dropped day is still served, and the bootstrap resamples the clean days only.
- **2(b), the objective and the tie rule.** `lad_curve` is the exact least-absolute-deviation line `a + b × max(k − D, 0)`,
  `b ≥ 0`, for every kink on `KINK_GRID` at once. Tied kinks go to the smaller. `descend` is the baselines' coordinate search; a
  value replaces the current one only when its objective is lower by more than `KINK_TIE_RTOL`. `combine_starts` compares the
  three starts at the end: tied and more than one grid step apart in any parameter is "not identified" (no estimate, no picked
  vector); otherwise the lower objective, then the smaller vector.
- **2(c), the left side.** `effr_minus_iorb_bp` is the parent's property of the scored row, in whole basis points, not rescaled.
- **3, the variants.** CV1, CV2, DV1, DV2; four added.
- **4, D under #142.** A day with no headroom is not a training day and is not served; the clean variants of D inherit it.
- **5, the comparison.** `summarise` reads goalpost 1 and goalpost 2 for each estimator; the baselines are the current C and D.

## Readings this implementation took (none changes what the declaration says; Eleonora may overrule any)

1. **The refit dates and the window.** The first refit is at 2020-03-13, then every 21 observation days, as Stages 3c and 6, on
   the rows to `demand_curve.LAST_DAY` (2025-12-31), as Stage 6's refits ran. The declaration says "the same refit dates" without
   naming them. The near-blind 2026 days are ordinary history since the lockbox amendment of 5 October 2026 and are not used.
2. **The number of draws.** 2000, the count Stage 2 and Stage 6 use for the bend's interval (`demand_curve.REPLICATIONS`). The
   declaration says "the same number of draws" without a number.
3. **The slope bound and the rule that rejects a negative slope.** The fit enforces `b ≥ 0`, as section 2(b) says, so a fit
   cannot have a negative slope and "a negative slope is rejected" cannot bind; a flat curve (`b = 0`) is accepted, as the
   baselines accept `slope = 0`.
4. **A day whose flags cannot be read.** The parent's rule cannot form an information set for the panel's second row
   (2018-04-04: too little history for the target's lag), so its flags are not read. It cannot be certified clean and leaves the
   fit. It is one day, listed in the record (`unread_flag_days`). A flag that is a hole in any other day is a `ValueError`.
5. **The solver.** A golden-section search over the slope of the profiled objective (convex, piecewise linear), to a relative
   1e-10 of the objective, checked against brute force over every two-point vertex and the `b = 0` boundary. The objective, not
   the sum of squares, is stored in the refit's `sse` field and the record calls it `objective_or_sse`.
6. **One refit per distinct training sample.** A refit is a function of its sample alone (the bootstrap seed is fixed), so
   cutoffs that fit on the same days share one refit. `baseline_path_c` and `baseline_path_d` do the same for the current C and D
   and are tested equal to their modules' `real_time_path`.
7. **The leakage check.** `check_no_future` rebuilds each cutoff's training sample (days, what each read, flags, left side) from
   the panel cut at that row and compares it with the full panel's. A refit depends on the panel only through that sample.

## A fact the declaration's counting rule produces (reported, not decided)

On the tracked panel, with the parent's two flags, the 2025 episode has 77 scarce days (ratio below 13%) and 55 once the
calendar days are dropped. The counting rule needs 60 clean scarce days, so under the declaration the 2025 episode never counts
for a clean variant, and DV1 and DV2 (which have headroom only from 2021-12-21) have no counted episode at any refit. CV1 and CV2
fit on the first episode alone at every refit. Whether that is what is wanted is Eleonora's: a lower count for clean days, or a
count taken on the baseline's days, would be a change to the declaration. The run reports it as it is
(`episode_counts` in the record).
