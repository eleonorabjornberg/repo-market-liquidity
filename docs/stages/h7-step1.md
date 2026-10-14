# H7m, development step 1: the estimand and the as-of estimator

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 1 of the plan
(`docs/research/plan.md`). Directive #22, recreating eleonorabjornberg/repo-market-model#644.

**Development, never a verdict. Nothing is scored here:** no AUROC, no CRPS, no comparison with R, and no real
real-time path is run. Scoring is step 5, under `docs/decisions/measurement-protocol.md`. This document is written
before the code (`src/repo_liquidity/h7_estimator.py`) and the code is held to it.

## 1. The estimand

**The quantity.** Deployable liquidity on day T, `D_T = R_T − k_T`:

- `R_T` is the parent's reserves ratio, `repo_model.scarcity.reserves_ratio`, of the reserve balances and the bank
  total assets that were public at T's decision instant. It is never recomputed here (plan, amendment 1).
- `k_T` is the **kink** of the reserve demand curve, the satiation level: the reserves ratio below which the spread
  rises. It is the desired buffer, in the same units. It is a *slow variable*: it changes only at a refit.

`D_T` is both of the directive's quantities: reserves minus the desired buffer, and the signed distance to the
kink. A negative value is a reserve ratio below the kink.

**Unit.** A share of bank assets; reported in points of bank assets (`100 × D`), and in dollars as `D` times the bank
total assets that were public at T's decision (`dollars`). Each estimate carries a 90% interval in the same units.

**Decision instant.** 16:00 on the panel day before T, through `repo_model.asof.InformationRule`, with the parent's
reads and guards unchanged. Each leg of the ratio is read at its own latest public row.

*14 October 2026 (directive #58, finding #53):* the sentence above was not yet true of the code. The estimator built each
information set but did not call the parent's `rule.check`, and it carried a copy of the parent's date extension. It now
calls `rule.check(dates, info)` on every set it reads (so `LookAheadError` and `StaleReadError` can be raised from
`asof_days`) and imports `satiation._extended` from the parent at the pin. The estimate path on the development panel
(days to 2025-12-31) is byte-identical before and after.

**Real-time reading, filtered and never smoothed.** The estimate for T uses the refit in force at T's decision. A
refit with cutoff `c` is fitted on the training pairs whose scored day is on or before `c`, each pair being the ratio
public at that day's own decision and that day's SOFR − IORB spread in basis points. It serves the days from the
second business day after `c` (the lag Stage 3c uses, `docs/stages/stage-3c.md:28`) to the day the next refit
serves from. No later row enters any refit.

**The kink.** The parent's fitted level (`repo_model.satiation.fit_level`, declared in #587 and used by #626's kinked
elasticity): `spread = a + b × max(0, k − ratio)`, `b ≥ 0`, `k` on the parent's grid (0.080 to 0.200 in steps of
0.0025), least squares, at least 250 pairs. It is imported, never copied; its constants are the parent's. With too
few pairs, or no candidate with a non-negative slope, the parent returns the fixed 0.12. That refit is marked
**not fitted**, carries no interval, and is reported as such, never as an estimate (protocol §11).

**The interval.** A stationary bootstrap of the kink over the refit's training pairs (the parent's
`metrics.stationary_bootstrap_indices`): mean block 10, the parent's seed (`scarcity.BOOTSTRAP_SEED`), the 5th and 95th
percentiles of the refit kink, subtracted from the day's ratio. The number of draws is a parameter; the tests use few,
and a real path (step 5) uses the protocol's.

**The scarcity state.** The parent's 0 to 3 state (`scarcity.reserve_scarcity_state`), read through the parent's
own-leg states (`scarcity.own_leg_states`). It is carried beside the estimate and never rebuilt (plan, amendment 1).

## 2. Why it differs from R

`R` ranks days by reserves alone. `D_T = R_T − k_T` ranks them by reserves *relative to the kink in force*. The two
orders differ exactly when the kink moves between refits: when a day before a refit and a day after it have ratios
`R_a < R_b` but `R_a − k_a > R_b − k_b`, which needs `k_b − k_a > R_b − R_a`.

This is testable and is tested on a constructed input in which the kink steps up (`tests/test_h7_estimator.py`):
`D` is not `R` plus a constant, and a pair of days exists that `R` and `D` rank in opposite orders. If the kink never
moved, `D` would be `R` minus a constant and ranking-equivalent to R. That is Stage 6's finding for candidates A and
B (`docs/stages/stage-6.md:156-159`, `:165`), and the reason this estimator is not claimed to beat R. It is the
reason it *can*: it changes the order only where the evidence moves the kink. Whether it does on real days, and
whether any such difference is informative, is step 5's question, with R and R+S computed under protocol §5.

## 3. What the code exposes

- `asof_days`: the scored days with their as-of ratio, spread and state, through the parent's as-of reads. It refuses a
  day in a locked tier of the parent's lockbox (`lockbox.require_unlocked`).
- `training_pairs` and `refit`: one refit's kink, interval and record. `training_pairs` refuses a pair after the cutoff.
- `real_time_path`: every refit's real-time path over its served days, with the gap to the previous refit on each day
  both serve. **Computed, not scored.** Step 5 reads goalpost 1 (protocol §3: every gap under 0.5 points) from it.
- `check_no_future`: refuses a refit whose kink differs from the same refit rebuilt from the rows cut at its cutoff.

## 4. Out of scope, and what is not claimed

- No score, no comparison with R or S. The path is run on synthetic and tracked-fixture inputs only; **no real
  episode and no real figure is produced**.
- No new input, no new package (the parent's functions, the standard library).
- The kink is one candidate for the buffer. Candidates C (bank groups) and D (SLR headroom) are later steps.
- Whether the fitted kink is *identified* on real data is not shown here: Stages 2 to 3c found it was not stable, and
  step 5 measures it.
