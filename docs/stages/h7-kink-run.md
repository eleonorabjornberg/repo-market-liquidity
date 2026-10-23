# H7m, the run of A's re-specified kink: what the code does and the readings it took

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 1 (candidate A's kink). Directive #151.
It implements, with no choice of its own, the declaration in `docs/stages/h7-kink.md` (merged with #135) as amended by its section 7
(the rulings on #137 and on #147, Q1). **Development, never a verdict** (`docs/decisions/measurement-protocol.md` §1): no locked
day, no goalpost 3, nothing scored against the stress events.

Code: `src/repo_liquidity/h7_kink.py`. Tests: `tests/test_h7_kink.py`. Run: `scripts/h7_kink_run.py`, which writes
`results/h7/kink.json` and prints `docs/research/h7-kink.md` from it (`--render` prints it again from the tracked record). The record
is generated output and is never edited by hand.

## The command

```
PYTHONPATH=src:<repo-market-model at the NEW pin, #149>/src \
  python3 -B scripts/h7_kink_run.py --replications 2000 --workers 8
PYTHONPATH=src:<parent>/src python3 -B scripts/h7_kink_run.py --render --check
```

**It cannot run on real days at the current pin (8fd2cf8).** The exclusion set needs `repo_model.turn_days.turn_label`
(section 7(ii)), which the parent has only after #959. At 8fd2cf8 the script exits 2 with "not run" and reads nothing. The run
waits for #149 (the pin move). `--timing` times one refit per estimator on a synthetic window the size of the real one and reads no
real day:

```
PYTHONPATH=src:<parent>/src python3 -B scripts/h7_kink_run.py --timing
```

Timing (synthetic, 1700 days, four regimes, one core, 20 draws scaled to 2000): the baseline, V1 and V3 about 5 to 7 s per
refit; V2 and V4 (one intercept, absolute deviation) about 250 to 340 s; V5 and V6 about 160 s. About 72 refits of all seven is an
upper bound of around 20 hours of core time (early refits have fewer days), so with `--workers 8` it is well over the two hours
that send a run to the Mac (`needs-mac`).

## What is implemented, by section of the declaration

- **7(i), the training start.** `training_days` takes only pairs scored after `TRAIN_AFTER` (2018-06-13), for the baseline too, so
  every estimator compared is trained on the same window. The regimes expected become 20, 15, 10 and 15 bp (`EXPECTED_WIDTHS`).
- **2(a) with 7(ii), the exclusion set.** `read_flags` reads the parent's `settlement_day` and `quarter_end_window` for every
  scored day through `repo_model.asof.InformationRule` at the day's own decision instant (the composed feature is the parent's own
  composer); `quarter_end_window` is the parent's opt-in column, a function of the date alone. `read_turn_labels` reads
  `turn_days.turn_label(T)` for the scored day alone. `mark_clean` drops a day when either flag is 1 or the label is not `None`.
  A dropped day is still served by the refit in force. A flag read for another row, or another day's flags, is a `LookAheadError`.
- **2(b), the objective.** `lad_lines` is the exact least-absolute-deviation fit with `b >= 0` and one intercept per group (one
  group is one intercept), for every kink on the grid at once; `squares_lines` is the group-demeaned least-squares slope. The
  solver's test is brute force over every two-point vertex (one intercept) and every within-group break point (several).
- **2(c), the regimes.** `width_regimes` reads IORB (the previous row's, plus the change the parent's `announced_iorb` says was
  public by the decision instant) less the ON RRP offering rate announced by then, per scored day. `check_public` refuses a rate
  announced after the decision instant. A regime is a run of one width. `regime_table` prints the table and `check_expected` stops
  the run with a finding if it differs from the list. A refit with a regime under 50 pairs is **not fitted**, with the counts.
- **The tie rule.** `fit_kink` takes the grid points within `KINK_TIE_RTOL` of the least objective; if they span more than one grid
  step the refit is "not identified" and serves nothing. The finding-#54 construction is "not identified" under all seven
  estimators in `TieRuleTests`.
- **4 and 7(iii), the comparison.** `common_served_days` and `summarise` read goalposts 1 and 2 on the days every estimator
  serves. The record carries the clean training days per regime at each refit and `politis_white_block` of each refit's training
  residuals, beside goalpost 2 (reporting only; the bootstrap stays as declared).

## Readings this implementation took (none changes what the declaration says; Eleonora may overrule any)

Readings (3), (4) and (7) are **Eleonora's**, accepted by her on 21 October 2026 (ruling on repo-market-liquidity#154, relayed by the orchestrating session). The others stand as read until she rules.

1. **The refit dates and the window**, as the #147 run: the first refit at 2020-03-13, then every 21 observation days, on rows to
   `demand_curve.LAST_DAY` (2025-12-31). The declaration says "the same refit dates" without naming them.
2. **The number of draws:** 2000, as Stage 2 and Stage 6.
3. **Feasibility** (accepted by Eleonora, 21 October 2026). The parent skips a kink whose unconstrained least-squares slope is negative. For squares this is kept. For
   absolute deviation the slope is constrained to `b >= 0` and every kink with spread in the hinge is a candidate, so on data with no
   kink the many kinks that fit alike tie and the refit is "not identified" (the #54 case), rather than "no candidate".
4. **IORB as known at the decision instant** (accepted by Eleonora, 21 October 2026) is the previous row's `iorb` plus the announced change, not the scored row's own
   `iorb` (the value realised on that day), because the regime is read at announcement.
5. **A day with no regime** (no ON RRP rate public) leaves the regime variants only, and is counted in the record.
6. **The baseline** is the parent's `fit_level` result on the same pairs (a test checks equality); the baseline column in the
   comparison is trained from after 2018-06-13 like the variants.
7. **The kill** (accepted by Eleonora, 21 October 2026) is reported as its two clauses and not combined: the second ("the clean-day kink's interval is wider than the raw
   one's") is given per clean variant; how they read together is protocol §7's choice rule.
8. **Bootstrap draws that do not fit** (too few pairs, a regime short of 50, not identified) are left out of the interval, as the
   parent's `refit` leaves out a draw that did not fit.
9. **The leakage rebuild** (`check_no_future`) rebuilds the days from the panel cut at each cutoff and compares every day up to the
   cutoff, ratio, both left sides, regime and cleanliness. It runs inside the real run.
