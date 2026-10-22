# H7m, the run of the calendar-clean variants of C: what the code does and the readings it took

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 2 (candidate C). Directive #147.
It implements, with no choice of its own, the declaration in `docs/stages/h7-calendar-clean.md` (merged with #146) as amended
by its section 9, the rulings on Q1 to Q6. D and its variants are not run (D dropped under #142); their code stays, tested. **Development, never a verdict** (`docs/decisions/measurement-protocol.md` §1): no locked day, no goalpost 3, nothing
scored against the stress events.

Code: `src/repo_liquidity/h7_clean.py`. Tests: `tests/test_h7_clean.py`. Run: `scripts/h7_calendar_clean.py`, which writes
`results/h7/calendar-clean.json` and prints `docs/research/h7-calendar-clean.md` from it (`--render` prints it again from the tracked record). The record is generated output and is never
edited by hand.

## The command

**Runnable at the pin of 08ff67e** (`PARENT_COMMIT`, after #155). The exclusion set's third clause reads the parent's
`repo_model.turn_days.turn_label` (Q1), which exists from that pin on. The rows are measurement panel version 4 (version 1's
build at 08ff67e: the same columns, only `srf_take_up` differs, `docs/stages/panel-v4.md`); version 1 is refused at this pin.
It goes to Eleonora's Mac, from the 5 pm batch (`needs-mac`):

```
PYTHONPATH=src:<repo-market-model at 08ff67e>/src \
  python3 -B scripts/h7_calendar_clean.py --replications 2000 --workers 8
```

`--workers` only spreads the bootstrap draws over processes; the draws and the record do not depend on it. A variant's work is
kept in `results/h7/calendar-clean.parts/<variant>.json` (not tracked) when it finishes, and a rerun reuses it. `--variants`
runs some of `C,CV1,CV2,CV3,CV4`; `--limit-refits N` runs the first N refits.

## What is implemented, by section of the declaration (as amended)

- **2(a) and Q1, the exclusion set.** `h7_clean.read_flags` reads the parent's `settlement_day` and `quarter_end_window` for every
  scored day through `repo_model.asof.InformationRule` (the composed feature is formed by the parent's own composer), at the day's
  own decision instant, and the parent's `turn_days.turn_label` of the scored day (`parent_turn_label`, `read_turn`). A day is
  dropped when `settlement_day` = 1, `quarter_end_window` = 1, or the label is not `None`. `quarter_end_window` is the parent's
  opt-in column, a function of the date alone (`data.quarter_end_window`), added to the rows with `with_quarter_end_window`. A flag
  read for any row but the scored one, or a label read for any day but the scored one, is a `LookAheadError` (`check_flag_reads`,
  `read_turn`), and a day's flags must be that day's own (`clean_days`). The counted-episode rule is read on all days, as the baseline's, and the fit uses the counted episodes' clean days (declaration
  section 10, her ruling on PR #150); a dropped day is still served, and the bootstrap resamples the clean days only.
- **2(b), Q3 and Q6, the objective and the tie rule.** `lad_curve` is the exact least-absolute-deviation line
  `a + b x max(k - D, 0)`, `b >= 0`, for every kink on `KINK_GRID` at once. Tied kinks go to the smaller. `descend` is the
  baselines' coordinate search; a value replaces the current one only when its objective is lower by more than `KINK_TIE_RTOL`.
  `combine_starts` compares the three starts at the end: tied and more than one grid step apart in any parameter is "not
  identified" (no estimate, no picked vector); otherwise the lower objective, then the smaller vector. It holds for every
  variant.
- **2(c) and Q2, the left side.** CV2 fits `(EFFR - ON RRP rate) / (IORB - ON RRP rate)` (`left_sides`), the corridor position
  of `demand_curve.corridor_position` with EFFR in place of SOFR and the ON RRP rate in force that day. Raw `effr_minus_iorb_bp`
  is not offered beside it.
- **3 and Q4, the variants.** CV1 (clean days, absolute deviation, SOFR corridor), CV2 (the same on the EFFR position), CV3
  (clean days, least squares: (a) only) and CV4 (every day, absolute deviation: (b) only). Four are run.
- **Q5, D.** D and DV1 to DV4 are "not run (D dropped under #142)" and are listed so in the record. `refit_d` and `path_d` stay.
- **5, the comparison.** `summarise` reads goalpost 1 and goalpost 2 for each estimator; the baseline is the current C.
- **The block length, reporting only.** `politis_white_block` (Politis and White 2004, with Patton, Politis and White 2009) of
  each fitted refit's training residuals in time order, recorded per refit and set beside goalpost 2. It follows the paper's
  definition and agrees with `arch.bootstrap.optimal_block_length` on a fixed series (49.23 and 49.229). The bootstrap is
  unchanged, mean block 10.

## Readings this implementation took (none changes what the declaration says; Eleonora may overrule any)

1. **The refit dates and the window.** The first refit is at 2020-03-13, then every 21 observation days, as Stages 3c and 6, on
   the rows to `demand_curve.LAST_DAY` (2025-12-31), as Stage 6's refits ran, plus a final refit on 2025-12-31 (her ruling on
   finding #160, option (b); `h7-calendar-clean.md` section 11), for the baseline C and CV1 to CV4 alike. The declaration says
   "the same refit dates" without naming them. The near-blind 2026 days are ordinary history since the lockbox amendment of 5 October 2026 and are not used.
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
8. **CV3 under the tie rule.** The declaration says the tie rule holds "for every variant", and Q3 extends the "not identified" rule
   to C. CV3 is therefore the baseline's least-squares fit (its kink search and its rejection of a negative slope) on the clean
   days, with `combine_starts` on its three starts. On days nothing drops it equals the baseline's fit (a test). Whether the
   baseline's own starts should also be tested for identification is not asked here.

## A fact the counting rule produces (reported, not decided)

Counted from the tracked panel with the parent's three clauses (finding #160; no variant was fitted): the 2025 episode has 77
scarce days (ratio below 13%), the 60th on 2025-12-05. The last refit of the 21-day stride, 2025-12-02, sees 57, so 2025 counts at
no refit of the stride. Her ruling on #160, option (b), adds a final refit on 2025-12-31 (`h7-calendar-clean.md` section 11), where
it counts for every variant. The first episode alone is the sample at every earlier refit (one fit per variant, shared by the 69
refits of the stride), and the final refit is a second sample, hence a second fit per variant. The final refit serves no day in
the window. The run reports the episodes counted at each refit (`episode_counts`).
