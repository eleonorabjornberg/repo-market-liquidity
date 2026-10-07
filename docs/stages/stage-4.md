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

   The broken stick has Stage 2's form and grid. It is pooled over every training day, with no episodes and no
   regimes. **Its slope is constrained to b ≥ 0** (Eleonora, 7 October 2026): at each grid point a negative
   least-squares slope is floored at 0 before that point's fit is compared. A new function does this.
   `demand_curve.fit_broken_stick` is not changed, so Stage 2's record still reproduces.
2. **Read it at the forecast day.** For each row the gbm sees, training or scored, take the reserves ratio known at
   that row's decision instant, r, and compute p̂ = a + b · max(k − r, 0).
3. **Convert it to basis points of SOFR − IORB:** implied = 100 · (p̂ − 1) · (IORB − ON RRP rate). Both rates are
   those in force on the forecast day, as announced by its decision instant. These are the scheduled `iorb` and
   `on_rrp_rate` columns of the Phase 3 panel, never `scheduled.rate_in_force`, which is for realized outcomes only.
   Converting puts the feature in the outcome's units, so a corridor whose width the Fed moved (25, 10 and 15 bp) is
   carried into the feature rather than left for the gbm to learn.
4. **No silent fallback** (Eleonora, 7 October 2026: "diagnose and remedy"). A refit's curve fails if the fit raises
   `ValueError`, or if the constrained fit lands on b = 0, a flat curve that carries no reserves signal. A failed
   curve is never replaced by a default. It stops the run, as set out under "The curve pass".

### The curve pass, before anything is scored

Before any gbm is fitted, the curve alone is fitted at every refit cutoff of the fold grid. No gbm runs and no
forecast is scored. The pass reports each refit's bend, intercept and slope.

- **If every refit's curve is fitted with b > 0,** the run goes ahead.
- **If any refit fails,** the run stops there. The pull request diagnoses each failure: which refit, its training
  window, how many of its days were on the scarce side, and why the fit failed. It proposes a remedy, which goes to
  Eleonora. The remedy is written into this plan as a labelled amendment, merged by her, **before anything is scored**.
- This means a remedy, if one is needed, is chosen after the curve fits are seen but before any comparison is.
  The amendment says so.

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

- the curve at every refit (bend, intercept, slope), from the curve pass;
- the bend's path across refits beside Stage 2's two episode bends;
- the Brier result;
- the as-of persistence comparisons.

## After the run

- **The freeze.** Once Eleonora has reviewed the run, the declaration is frozen by checksum, as the parent freezes its
  final test, whatever the verdict. The declaration covers the wrapper, the curve's form, grid and slope constraint, any remedy from the curve pass, the
  published fitter's arguments, the panel version, the parent pin and the package pins.
- **Stage 5a, Phase 3's own daily log,** is written as its own directive after the freeze, on GitHub Actions (the place
  recommended earlier). **It logs both arms' forecasts each business day,** with and without the feature, both from the
  frozen declaration (Eleonora, 7 October 2026). The confirmatory pairing then rests on Phase 3's own log, not on the
  parent's live record.
- **Scoring dates** are unchanged: 2027-04-01, then each 1 October. The confirmatory record counts only days logged
  after the freeze.

## Build order, once this plan is merged

Each step is its own commit, with tests written first.

1. The `ml` extra in `pyproject.toml`, pinned exactly with what the install resolves, and CI installing it. The
   transitive pins are recorded in `docs/decisions/dependencies.md`.
2. The curve-implied feature (`src/repo_liquidity/curve_feature.py`): the constrained fit on training rows, the read
   at the forecast day and the conversion. A failed curve raises rather than falling back. It gets the leakage tests
   with their mutations.
3. The curve pass (`scripts/stage4_curve_pass.py`). It fits the curve at every refit cutoff and scores nothing. If any
   refit fails, the work stops here for the diagnosis and Eleonora's remedy.
4. The wrapper fitter and its declaration, and a test that the parent's guard refuses an undeclared read.
5. The run script (`scripts/stage4_compare.py`), which first checks the reproduction in must-show 1, then scores.
6. The record (`results/stage4/`, outside `docs/runs/`), with full provenance. It is not published until Eleonora says so.

## Amendment: the curve pass's remedy (7 October 2026)

**Status: a draft for Eleonora's review. It is in force only once she merges it.** Nothing is scored before then.

**This amendment is written after the curve fits were seen, and before any comparison.** The plan's "The curve pass"
allows a remedy only on those terms, and asks that it say so.

**What the curve pass found** (`results/stage4/curve_pass.json`, from commit `ec7716a` with a clean tree):

- 89 of 90 refits fit with a slope above 0.
- **One fails:** the refit with cutoff 2018-07-27, which serves the 21 scored days from 2018-07-31.
  - Its sample is 72 days, every one with the reserves ratio between 11.5% and 12.9%.
  - The constrained fit lands on a slope of 0, at a bend of 11.5%. The unconstrained Stage 2 fit has slope −38.9, at
    a bend of 11.75%.
- **Why it fails:** in the window's first four months the ratio moves within 1.4 points. The corridor's moves there
  are calendar spikes: 2018-06-29 (a quarter-end, position 1.85) and the first days of July. They are not a reserves
  response. The 22 days below the would-be bend are calm July days, with a mean position of 0.87 against 0.885 above
  it. Dropping month-ends and quarter-ends does not rescue the fit. The curve is not identified on this sample.
- **Reported, not judged:**
  - The first refit fits (cutoff 2018-06-27, 51 days, bend 12.3%), but on the same narrow sample.
  - From the refit of June 2021 to that of October 2022, the bend sits at 17% to 19%, with the intercept near 0.
  - In the refits of November and December 2021 the intercept is slightly below 0.

**The remedy (Eleonora, 7 October 2026, choosing the recommended option): carry the last fitted curve.**

- A refit whose curve fails (`CurveFailure`) uses the curve of the latest earlier refit whose own curve was fitted.
  It is still as of that refit: the carried curve was fitted on days at or before an earlier cutoff, and a guard
  refuses one fitted later (`LookAheadError`, with a recorded mutation).
- Every published origin stays in the comparison, so must-show 1 and the pairing are unchanged.
- **The run still stops if a refit fails with no earlier fitted curve to carry.** On today's panel that does not
  happen: the first refit fits.
- On today's panel the remedy touches one refit block (cutoff 2018-07-27), which uses the first refit's curve. The
  record lists, for every refit, the curve it used and where a curve was carried from.

**Two corrections the build exposed, also for Eleonora's review.** Neither changes what the feature means.

1. **IORB in the conversion.** The plan says the conversion uses "the scheduled `iorb` and `on_rrp_rate` columns of the
   Phase 3 panel". `on_rrp_rate` is scheduled, but the panel's `iorb` is not: it is the realized rate, a constituent
   of the target, read at the anchor (two panel days before T). Around a rate change it would give the old rate. The
   build therefore adds a scheduled column, `iorb_in_force`: the IORB in force on T, read at T's decision instant. It
   comes from the parent's own table of implementation notes, keyed on the announcement, as `on_rrp_rate` is.
   - It is declared in `metadata/sources_stage4.json` and checked by the parent's validators. It is added in memory,
     so panel versions 1 to 3 and their manifests do not change.
   - It equals the panel's realized `iorb` on every day of the window but 2020-03-16. That day's cut was announced on
     Sunday 15 March, after Friday's 16:00 decision. A test records this.
2. **The declared features.** The plan lists `sofr` and `iorb` among model B's added declared features. Both are
   constituents of the target, `spread_bps`, which every model already declares and reads. The curve's labels are read
   from them. Model B therefore declares the published nine plus `bank_total_assets`, `on_rrp_rate` and
   `iorb_in_force`. Its `features_read` reports `spread_bps` for the labels, so the parent's
   `_check_fitter_stayed_inside` covers everything the curve reads.

## Result (7 October 2026): not shown

Scored once under the plan and its amendment, development evidence only, to 2025-12-31. Records:
`results/stage4/comparison.json` (primary), `results/stage4/brier.json` (secondary) and
`results/stage4/curve_pass.json`. The Brier record was scored at commit `eaee930`. The primary was first scored at `c07d681`, then re-scored after the exceedance code landed, at `7e89020`; the two runs agree origin by origin. `7e89020` differs from `eaee930` only by the Brier record, so both scored records stand on the same code. Each carries its commit, a clean tree, the parent pin and both panel digests. No
record is published.

**Must-show 1, the baseline arm reproduces the published record: held.** On every published origin, model A's scored
days and per-origin CRPS equal the parent's published gbm, with a largest gap of 0 bp. In the secondary run, model A's
Brier equals the published exceedance record's at +5 and +10 bp, also with a gap of 0. (The record reports +20 and
+50 bp event by event, with no pooled Brier to compare.)

**Must-show 2, no look-ahead by test: held.** Each guard raises `LookAheadError` and has a recorded mutation that kills
it:
- the scheduled IORB is keyed on the announcement;
- the curve is fitted only on days at or before the refit's cutoff;
- the feature's inputs are read as of the row's decision instant;
- a curve input left out of the declaration is refused, on both the CRPS path and the exceedance path;
- a carried curve fitted after the cutoff is refused.

**Must-show 3, the development verdict: not shown.** The curve is not shown to help.

| | Mean paired CRPS gain (A − B), bp | 90% interval |
|---|---|---|
| Pooled | +0.0038 | [−0.0070, +0.0146] |

The gain is model A's CRPS minus model B's; positive means the curve helped. Pooled CRPS is 1.6592 bp for A and 1.6554
bp for B, over the published origins. The interval is the 90% stationary bootstrap (block 2, 2000 replications).

By regime and by pressure-day type (`baseline.add_comparison_splits`):

| Split | Days | Mean gain, bp | 90% interval |
|---|---|---|---|
| 2018–19 | 375 | +0.0073 | [−0.0266, +0.0442] |
| 2020 | 251 | +0.0288 | [+0.0014, +0.0572] |
| 2021–23 | 748 | −0.0012 | [−0.0152, +0.0119] |
| 2024 | 250 | +0.0010 | [−0.0202, +0.0205] |
| 2025 (to 31 December) | 249 | −0.0090 | [−0.0406, +0.0211] |
| Quarter-end | 31 | −0.0242 | [−0.1812, +0.1284] |
| Month-end | 158 | −0.0022 | [−0.0478, +0.0390] |
| Tax date | 89 | +0.0080 | [−0.0501, +0.0628] |
| Ordinary | 1595 | +0.0047 | [−0.0055, +0.0158] |

Only the 2020 regime's interval lies above 0. It is one split of many, and the pass rule is the pooled figure.
2025, where the curve's shift should matter most, is slightly negative.

**Beside it, as-of persistence** (persistence's CRPS minus the arm's, from the published persistence losses on the same
origins): A +0.4268 bp [+0.1862, +0.7443]; B +0.4306 bp [+0.1861, +0.7395]. Both arms beat persistence by the same
margin. This bootstrap's seed is derived from the Phase 3 panel, so A's interval differs slightly from the published
[+0.1855, +0.7369]; the mean is the same.

**Secondary, P(spread > +5 bp), Brier (not part of the pass rule):**
- Brier is 0.049612 for A and 0.049571 for B. A minus B is +0.000041, 90% interval [−0.000752, +0.000817]: not shown.
- Both arms beat calendar climatology (0.071413) and the persistence-logistic model (0.056329), with intervals above 0.
- By day type, tax dates are worse with the curve: −0.00495 [−0.00971, −0.00096], over 89 days.
- At +50 bp, B is slightly worse: −0.000033 [−0.000065, −0.000009].

**Reported, not judged:**
- The curve at every refit is in the record. One refit carried a curve: the one at cutoff 2018-07-27 used the curve from
  2018-06-27, as the amendment says.
- The bend moves with the sample:
  - near 11.5% to 12.3% through 2018 and 2019, with 10.35% at the year-end refit of January 2019;
  - near 9% to 10.5% from October 2019 into May 2021;
  - near 16.5% to 18.5%, with the intercept near 0, from June 2021 to October 2022;
  - near 14.6% at the end of 2022, near 13.5% from 2023 to July 2025, and near 14.5% from August 2025.

  This is the instability Stage 3 met in another form.

**What this means for the next step.** Under Eleonora's ruling of 7 October 2026, the freeze and Stage 5a's daily log
go ahead whatever the verdict, once she has reviewed this run. A "not shown" development verdict with a near-zero
point estimate means the confirmatory log is likely to show little. Whether to freeze this declaration as planned, or
to reconsider first, is her decision.

## Not in Stage 4

- No change to the parent, its published model, its pre-registration, its live record or its records.
- No other features.
- No tuning of the gbm, the curve's form or its grid.
- No 2026 data.
- No publish.
- No freeze before Eleonora has reviewed the run.
