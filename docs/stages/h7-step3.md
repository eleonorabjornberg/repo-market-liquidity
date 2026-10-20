# H7m, development step 3: candidate D, the buffer of the SLR-bound group set by leverage headroom

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 3 of the plan
(`docs/research/plan.md`). Directive #138. It follows step 2 (`docs/stages/h7-step2.md`, PR #127), whose estimand, interfaces
and machinery it reuses, and builds candidate D of `docs/stages/stage-6.md:70-79`.

**Development, never a verdict. Built, nothing scored:** no AUROC, no CRPS, no stability or width figure, no comparison with R,
S or C, and no real real-time path or out-of-sample result is run or published. Scoring is step 5, under
`docs/decisions/measurement-protocol.md`. This document is written before the code (`src/repo_liquidity/h7_candidate_d.py`) and
the code is held to it.

## 1. The candidate

**Aggregate deployable liquidity** is step 2's:

    D_D = ( sum over g of max(Res_g - s_g,t × A_g, 0) ) / sum over g of A_g

with the same weekly group reserves `Res_g` (approximation, data-meaning row 18) and H.8 total assets `A_g` (first prints), the
same unit (a share of bank assets, reported in points by `100 × D_D`), and the same clip at zero per group. **What D changes is
one group's buffer share.**

**The SLR-bound group is the large domestic group** (H.8 large domestically chartered commercial banks). It is the group the
nine G-SIB depository subsidiaries of data-meaning row 16 belong to; the headroom of those nine, read at the main bank of each
G-SIB (row 16(c) as amended, with its known limitation: not every G-SIB depository subsidiary, Chase Bank USA, N.A. is not
read), stands for the group's. The small domestic and foreign-related groups are **as in C**: each has one share of its own
assets, fixed within a refit. Foreign-related institutions have no SLR anchor (row 16(f)); D gives them none.

**The large group's buffer** on day T is a level plus a slope times the headroom transform, kept inside the shares' range:

    s_large,t = clip( level + slope × h_t , 0 , 0.30 )

**The headroom transform (named before any fit).** `h_t = H_t / A_large,t`, where

- `H_t` is the **leverage headroom in dollars** of the nine banks, in USD billions: for each bank,
  `Tier 1 capital ÷ required ratio − total leverage exposure` (`slr.Row.tier1_capital_kusd / (requirement_pct / 100) −
  total_leverage_exposure_kusd`, from thousands to billions), summed over the nine. It is the extra exposure the banks could
  take on before reaching the requirement. The requirement is the per-period table of `docs/decisions/slr-requirement.md`
  (6% for quarter-ends 2018-01-01 to 2026-03-31), as `slr.requirement_for` gives it. A quarter with no requirement (from
  2026-04-01, where the rule is bank-specific) has **no headroom**: `H_t` is None and D serves no estimate on days that read it.
  There is no fallback to an earlier quarter and none to the ratio.
- `A_large,t` is the large domestic group's H.8 total assets of the week the day reads (step 2's `GroupWeek`).
- **Unit.** `h_t` is a pure number: dollars of headroom per dollar of the group's assets, the unit of a buffer share. The
  slope is therefore a buffer share per unit of headroom share; the level is the buffer at zero headroom.
- **The sign of the slope is not imposed.** The slope grid (`SLOPE_GRID`) runs from -1.0 to 1.0 in steps of 0.1. The theory
  (less headroom, a higher effective buffer) says negative; the fit may say otherwise, and the refit's record carries the sign.

**What D adds over C.** C's large-domestic share is one number per refit. D's is a function of a quarterly, bank-reported
quantity that moves between refits: the same weekly reserves can give a different D when headroom differs. With the slope at
zero D is exactly C with the large share equal to the level (a unit test); the slope is the whole addition.

## 2. Why D is not C plus a constant

Between refits C is a function of the week's group reserves and assets alone. D also depends on the quarter's headroom, which is
unrelated to the week's reserves. Two days with identical group reserves and assets, in quarters with different headroom, have
different `D_D` whenever the slope is not zero, and the clip means the difference is not a constant offset (it is zero where
the group is below its buffer on both days). This is tested on a constructed input (must-show 3 of the directive).

**What the data allow, stated before anyone reads a result.** The SLR series is the **latest-filed** vintage
(data-meaning row 16(d), her ruling of 13 October 2026): a (bank, quarter) value is available only from its latest-update time,
which for the first quarters is a year or two after the quarter. The earliest public quarters are therefore read on days well
after they ended, and an episode can have few or no days with a complete quarter of the nine banks public. A refit counts an
episode only on days that have headroom (section 3), so **D may be unfitted for a long stretch, the first episode included**;
the refit then serves no estimate. That is a property of the input, not of this step, and it is the reason section 5's
out-of-sample test may have nothing to fit on. Step 5 reports it.

**Measured from the snapshot's `available_from` column alone (no panel day is scored, no figure is a result).** The first
quarter for which all nine banks have a row public is the one ended 2018-03-31, public from 2021-12-18; the next, ended
2018-06-30, from 2023-03-10; the quarters ended 2021-03-31 to 2024-06-30 from 2025-08-29 to 2025-10-01; the quarter ended
2024-12-31 from 2026-06-27. So **no day of the first episode (to 2020-03-13) reads any complete quarter**, and D cannot be fitted
on that episode alone in real time (the out-of-sample test of section 5 has nothing to fit). A decision on 2025-01-02 reads the
quarter ended 2020-12-31, and one on 2025-12-31 the quarter ended 2024-09-30, years old. The quarters ended 2026-03-31 and
2026-06-30 are incomplete (Morgan Stanley Bank, N.A. was amended on 2026-09-10, after the development end, and is withheld), and
2026-06-30 has no requirement in any case, so the last quarter D can read at the development end is the one ended 2025-12-31.
This follows from ruling 1 of 13 October 2026 (the latest-filed vintage) and the day-after rule, and is reported as a finding
for her (see the pull request); nothing here changes either ruling.

## 3. The fit

The parameters are fitted so that `D_D`, through Stage 2's curve form, best explains the corridor position in the scarce
episodes, as of each refit's cutoff, on training rows only. Everything of step 2's section 3 holds unchanged (the curve form,
`KINK_GRID`, the episodes, the 60-scarce-day rule, no fallback, a negative slope rejected, refits and serving lag, filtered
never smoothed), with these differences:

- The parameters are four: `level`, `slope` (the large group's buffer) and the small and foreign-related shares (`SHARE_GRID`).
  The level takes `SHARE_GRID` as well.
- **Training days** are the days of a counted episode, up to the cutoff, that have a group week, a corridor position **and a
  headroom** (a complete quarter with a requirement). The 60-scarce-day count is taken over those days.
- **Search.** A coordinate descent over the four grids from three fixed starts (`START_PARAMETERS`), least squares, ties to the
  smaller value. The refit records whether the starts agree. Whether the parameters are identified is not shown here.
- **The interval** is the stationary bootstrap of the parameters over the refit's training days, with step 1's block length 10,
  level 0.90 and seed constants (the parent's `metrics.stationary_bootstrap_indices`), one start per draw (the refit's own
  parameters). A day's interval is the 5th and 95th percentiles of that day's `D_D` over the draws, widened to hold the point
  estimate.

## 4. Inputs, and how they are read

- **Panel days, ratio, spread and scarcity state:** step 1's (`h7_estimator.asof_days`), through the parent's `InformationRule`.
  **R and S** come only from `repo_model.scarcity.reserves_ratio` and `reserve_scarcity_state` at the pin (8fd2cf8), as in step 1.
- **Group weeks (G4):** exactly as step 2 reads them (`h7_candidate_c.read_week`, `tracked_weeks`), under her condition 3 as
  ruled on 19 October 2026: reading is allowed, scoring and registration are not.
- **SLR headroom (G5):** the `slr_headroom` snapshot published by PR #128, `4e9f87b5…e37` (it supersedes `013b647e…`), loaded
  through `slr.load_extract`, which checks it against its manifest and refuses a locked row; `tracked_rows` also checks that the
  extract's digest is the snapshot manifest's. A day reads the **latest complete quarter** public at its decision instant: the
  latest quarter for which all nine banks have a row with `available_from` on or before the instant. The read's `public_at` is
  the latest `available_from` of the nine. Leakage (a read public after the instant) is `LookAheadError`; staleness (a later
  complete quarter was public) is `StaleReadError`, both raised by `check_reads`. `slr.available_at` is the start of the day
  after the latest update, New York time (her ruling on #69).
- **What it rests on, cited and not re-decided:** Nicholas's answer 16 (#1, 12 October 2026); her rulings on #115 (the Fed
  standard for the three state member banks; the Chase Bank USA limitation; PR #118) and on #120 (pre-end filings stand; PR #128).
- **The 2020-21 exclusion (row 16(e)).** Headroom is used as reported. A day that reads a quarter whose exclusion status is
  unknown (`slr.EXCLUSION_QUARTERS`) is **flagged** (`exclusion_days`), never refused and never recomputed.
- **Break flags (Q18):** as in step 2, flagged (`break_days`), never adjusted.
- **No new input** beyond G4 and G5.

## 5. What the code exposes

- `shares_at`, `deployable`, `group_contributions`: the three groups' buffer shares for a week and a headroom, `D_D` and each
  group's term.
- `read_headroom`, `sample_d`: the headroom read for an instant, and the scored days with their as-of group week and headroom.
- `fit_parameters`, `refit_d`: one refit's parameters, curve, interval draws and record.
- `real_time_path`: every refit's real-time path over its served days, with the gap to the previous refit and a daily interval,
  through the same shape as steps 1 and 2. **Computed, not scored.**
- `distribution`: aggregate deployable liquidity under the protocol's three declared alternatives (§8), group by group, with each
  day's own buffer shares. Implemented and unit-tested; **no figures published**.
- `out_of_sample_2025`: Stage 6's own test for D, **machinery only**. D is fitted on the first episode alone; on the 2025
  days it reads, `D_D` is regressed on the all-banks ratio by least squares (`D = a + b × ratio`, `b > 0`), and the predicted bend
  is the ratio at which `D_D` equals the first episode's fitted kink, `(kink - a) / b`. It predicts the bend if that ratio is
  inside Stage 2's 90% interval for the 2025 bend, `[0.131, 0.1365]` (`results/stage2/demand_curve.json`, `revised_test`,
  episode 2025), read by `stage2_bend_interval`. The regression is a declared reading of "predict the bend": it is not Stage 6's
  wording, which says only "predict the 2025 bend inside the 2025 bend's 90% interval"; if she reads it otherwise it is hers to
  change before step 5. Unit-tested on constructed data; **not run on real days**.
- `check_reads`, `check_no_future`: the leakage and staleness guards.

## 6. Out of scope, and what is not claimed

- No score, no AUROC, no stability or width figure, no out-of-sample result.
- No new input beyond G4 and G5; no new package (the standard library and the parent).
- The re-specified kink (PR #135; finding #137) is a separate line. D uses step 1's kink as it is on main (Stage 2's curve form).
- The group series is not published as a snapshot by this step (marked question (ii) of #43 stays hers).
- **Marked question for Eleonora (not settled in code):** D reads the group-reserves series through candidate C's module
  (`h7_candidate_c.tracked_weeks`), so the one-reader rule of `tests/test_group_reserves.py` is unchanged: D imports only C. If she
  reads her condition 3 as also barring a second estimator from reaching the series that way, the dependency is hers to refuse.
