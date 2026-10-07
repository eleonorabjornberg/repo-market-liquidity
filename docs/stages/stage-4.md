# Stage 4 plan: Stage 2's curve as one feature of the published distribution

**Written 7 October 2026, after Stage 3c (#12) and before anything in Stage 4 is built, fitted or scored.** Nothing
below is computed until Eleonora has merged this plan and the evaluation amendment that comes with it.

## Why Stage 4 looks like this

- Stage 3c was not shown: the real-time buffer moved by up to 4.2 points between refits (`results/stage3c/realtime.json`).
  Under Eleonora's decision of 6 October 2026 (`PLAN.md`, "After Stage 3b", point 4), the latent buffer is set aside
  and **Stage 2's curve becomes the Stage 4 model**. The curve is the corridor position,
  (SOFR − ON RRP rate) / (IORB − ON RRP rate), against the reserves ratio, as a broken stick
  (`src/repo_liquidity/demand_curve.py`, `results/stage2/demand_curve.json`).
- On 7 October 2026 Eleonora ruled on the four questions put to her. Each ruling took the recommended option:
  1. **How the curve enters: a curve-implied feature (option A).** It is one added regressor of the published gbm, and
     everything else in the parent's declaration stays the same.
  2. **Which curve: refit as of each refit (a),** so the 2025 shift is learned only once the data shows it.
  3. **Scope: one feature only.** The Stage 1b indicators, the MBS flow and the take-up events each get their own
     comparison later, written and frozen before it is scored. **The ml dependency is approved:** numpy 2.4.6 and
     scikit-learn 1.9.1, pinned exactly (`docs/decisions/dependencies.md`).
  4. **The freeze:** score the development walk-forward, then freeze the declaration by checksum and start Phase 3's
     own daily log (Stage 5a), **whatever the development verdict**.
- `docs/decisions/evaluation.md` said "with and without the latent state" and "once the Stage 3 model is frozen". This
  pull request drafts the amendment that names the replacement. **It is in force only once Eleonora merges it.**

The kept descriptive finding is unchanged and is not used as an input: the banks' buffer rose about 3.3 points
between 2018–Mar 2020 and 2025. It carries three caveats: it needs drift, it rose in late 2022 rather than on a reform
date, and it vanishes at `s = 0.002` (`docs/stages/stage-3b.md`).

## The feature: the curve-implied spread

At each refit k, with training cutoff c_k (the parent's fold grid):

1. **Fit the curve on training rows only.** Each training day t ≤ c_k contributes:
   - the reserves ratio known at t's decision instant, `reserve_balances / bank_total_assets` read through the parent's
     `asof.InformationRule` under Phase 3's declaration, as `demand_curve.sample` reads it;
   - t's realized corridor position, built with the ON RRP rate in force on t (`demand_curve.corridor_position`).

   The broken stick is `demand_curve.fit_broken_stick`, on Stage 2's grid, unchanged. It is pooled over every
   training day, with no episodes and no regimes.
2. **Read it at the forecast day.** For each row the gbm sees, training or scored, take the reserves ratio known at
   that row's decision instant, r, and compute p̂ = a + b · max(k − r, 0).
3. **Convert it to basis points of SOFR − IORB:** implied = 100 · (p̂ − 1) · (IORB − ON RRP rate). Both rates are
   those in force on the forecast day, as announced by its decision instant. These are the scheduled `iorb` and
   `on_rrp_rate` columns of the Phase 3 panel, never `scheduled.rate_in_force`, which is for realized outcomes only.
   Converting puts the feature in the outcome's units, so a corridor whose width the Fed moved (25, 10 and 15 bp) is
   carried into the feature rather than left for the gbm to learn.
4. **The fallback, fixed now.** If `fit_broken_stick` raises `ValueError` on a refit's training rows, that refit uses
   the flat curve: p̂ is the training rows' mean corridor position. Each such refit is counted and listed. The slope is
   not constrained: a refit with b ≤ 0 is used as fitted, and it is listed.

The curve's parameters are fixed within a refit block, as the gbm's are. No row's feature uses a curve fitted on any
day after that block's cutoff.

### How it reaches the gbm

The feature is a model output, not a panel column, so it enters through a wrapper fitter. This is the design
`PLAN.md` already set out for the latent state:

- The wrapper receives the fold's training frame and fits the curve on it. It adds `curve_implied_spread_bp` to every
  row it hands on, then calls the published fitter (`ml.fit_gradient_boosted_quantiles`) with the published nine
  regressors plus `curve_implied_spread_bp`. Every other argument is copied from the published declaration
  (`docs/runs/compare_persistence_vs_gbm_conformal_pid_nested_funding_crps.json` in the parent, read at the pin). The
  nested conformal PID and its selection grid are unchanged.
- **Its declared features** are the published nine plus every column the curve reads: `bank_total_assets`, `sofr`,
  `iorb` and `on_rrp_rate`. The parent's `baseline._check_fitter_stayed_inside` therefore covers them, and the as-of
  rule reads and guards them.
- The parent is not changed. Everything is called at the pin, as `PLAN.md` ("What the parent provides") sets out.

## The comparison

As `docs/decisions/evaluation.md`, with the amendment:

- **Primary:** `baseline.paired_model_comparison`, with model A the published gbm and model B the same gbm plus the
  feature. It is one run on the parent's fold grid: minimum history 61, refit every 21, decision 16:00, to 2025-12-31.
  CRPS at h = 1 on SOFR − IORB, paired by day. The interval is the 90% stationary bootstrap with 2000 replications and
  block length 2, as the parent's final test.
- **The verdict:** the parent's `crps_verdict` (`scripts/final_test_preregistration.py`). Mean paired gain above 0
  with its 90% lower bound above 0 is "shown better"; an upper bound below 0 is "shown worse"; anything else is
  "not shown".
- **Beside it:** as-of persistence against each arm, with the same pairing.
- **Splits:** by regime and by pressure-day type (`baseline.add_comparison_splits`). A pooled figure alone is not a
  result. The reform dates are reported as splits only.
- **Secondary:** Brier on P(spread > +5 bp) at h = 1, with and without the feature
  (`baseline.rolling_exceedance_backtest`), against calendar climatology and the persistence-logistic model. It is not
  part of the pass rule.
- **The panel:** version 3 (`scripts/build_panel.py --version 3`), rebuilt to its manifest digest before the run. The
  curve reads only columns that version 1 already had.
- **Development only.** Every scored day is on or before 2025-12-31. The parent's lockbox holds 2026, and nothing here
  reads it.

## What Stage 4 must show

Fixed before anything is built. The pull request that reports the run says plainly which of these held.

1. **The baseline arm reproduces the published record.** Model A's scored origins and per-origin CRPS must equal the
   `per_origin` list of the parent's published comparison record, read at the pin, to 1e-9 bp. If they do not, the
   run stops there, no verdict is reported, and the mismatch is the result. A gain measured against a baseline that
   is not the published one is not the comparison evaluation.md fixes.
   One known way it could fail: if model B's added declared columns (H.8 bank assets above all) change which origins
   both arms are scored on, model A no longer covers the published origins. This check catches that.
2. **No look-ahead, by test.** Each new guard raises `LookAheadError` and has one recorded mutation that kills it, in
   its test's docstring:
   - the curve is fitted only on rows at or before the refit's cutoff;
   - the reserves ratio, IORB and ON RRP rate in the feature are read as of the forecast day's decision instant;
   - the wrapper's declared features cover every column it reads, through the parent's own guard.
3. **The development verdict,** labelled under the pass rule and split as above. **The curve is shown to help only if
   it is "shown better".** Under Eleonora's ruling, the label does not decide whether Stage 5a starts.

**Reported, not judged:**

- the curve at every refit (bend, intercept, slope), with the refits that fell back or had b ≤ 0;
- the bend's path across refits beside Stage 2's two episode bends;
- the Brier result;
- the as-of persistence comparisons.

## After the run

- **The freeze.** Once Eleonora has reviewed the run, the declaration is frozen by checksum, as the parent freezes its
  final test, whatever the verdict. The declaration covers the wrapper, the curve's form, grid and fallback, the
  published fitter's arguments, the panel version, the parent pin and the package pins.
- **Stage 5a, Phase 3's own daily log,** is written as its own directive after the freeze, on GitHub Actions (the place
  recommended earlier). One point is put to Eleonora in that directive, not settled here: whether the log records both
  arms' forecasts each day, so that the confirmatory pairing does not lean on the parent's live record.
- **Scoring dates** are unchanged: 2027-04-01, then each 1 October. The confirmatory record counts only days logged
  after the freeze.

## Build order, once this plan is merged

Each step is its own commit, with tests written first.

1. The `ml` extra in `pyproject.toml`, pinned exactly with what the install resolves, and CI installing it. The
   transitive pins are recorded in `docs/decisions/dependencies.md`.
2. The curve-implied feature (`src/repo_liquidity/curve_feature.py`): the fit on training rows, the read at the
   forecast day, the conversion and the fallback. It gets the leakage tests with their mutations.
3. The wrapper fitter and its declaration, and a test that the parent's guard refuses an undeclared read.
4. The run script (`scripts/stage4_compare.py`), which first checks the reproduction in must-show 1, then scores.
5. The record (`results/stage4/`, outside `docs/runs/`), with full provenance. It is not published until Eleonora says so.

## Not in Stage 4

- No change to the parent, its published model, its pre-registration, its live record or its records.
- No other features.
- No tuning of the gbm, the curve's form or its grid.
- No 2026 data.
- No publish.
- No freeze before Eleonora has reviewed the run.
