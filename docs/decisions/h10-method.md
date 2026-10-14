# Decision (DRAFT for Eleonora): H10's attribution method, v1

**Status: a draft for Eleonora to merge (H10 step 1, repo-market-liquidity#23; values set by her ruling, directive #45).
It is in force only once she merges it. The six values below are decided, by her ruling on
[#37](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/37#issuecomment-6159864877) (13 October 2026):
"i agree with your recommendations". Nothing is applied to a real episode before this record is merged (H10 step 2).**

H10 asks, for each pressure episode, what share of the rise in SOFR − IORB is accounted for by Treasury settlement, the
TGA, reserves, quarter-end and a residual (plan, H10). This record declares the method before it is applied. It is
descriptive: no verdict in the sense of eleonorabjornberg/repo-market-model#640 §9. The code is
`src/repo_liquidity/attribution.py`; its synthetic tests are `tests/test_attribution.py`.

## 0. The episode list is the model repo's

- **Source (plan, Q6; amendment on #23):** `repo_model.onset.onset_flags`, the onset group's module, at the pin. An onset
  is a day above +5 bp (whole bp, strictly greater, `data.exceeds_bp`) after five panel days at or below it.
- **Cross-check:** `repo_model.pressure.onsets` at +5 bp. `attribution.cross_check_onsets` refuses (`ValueError`) if the
  two give different days; a test asserts they agree on the tracked panel. If Eleonora picks the other source under Q6,
  the cross-check becomes the source.
- **Not defined by either:** an episode's end. This record fixes the window (section 1) and does not redefine an episode.
- **Both sources are cited at the pin**, `PARENT_COMMIT` in `src/repo_liquidity/__init__.py`, not at the commit the issue
  text cites; the issue's line numbers (`6c09789`) should be re-read at the pin when the record is reviewed.

## 1. The window (decided)

| | Decided | Why |
|---|---|---|
| **Baseline** | the mean of the **5** panel days before the onset | the onset group's own calm days (`ONSET_CALM_DAYS` = 5): all at or below +5 bp by construction |
| **Length** | the onset day and the **4** days after it, **5** panel days in all | long enough to average out the onset day's own noise, short enough that a second episode is rarely inside it |
| **Change** | the window mean minus the baseline mean, for the spread and for each driver | a level shift relative to the calm before |

Constants: `BASELINE_DAYS`, `WINDOW_DAYS`. **Decided (13 October 2026): 5 baseline days plus the onset day and 4 more,
as proposed.**

## 2. The decomposition (decided: regression with Shapley shares; the alternative is written out)

**Decided (plan, Q7; ruling of 13 October 2026).** A leave-episode-out regression of the spread change on the driver changes, with Shapley shares
and a stationary-bootstrap interval.

- **Drivers:** Treasury settlement (`treasury_settlement`, USD bn), TGA (`tga`), reserves (`reserve_balances`) and
  quarter-end (`quarter_end`, 0 or 1), all columns of the parent's panel, in that order. Each is read at the value first
  published (section 6).
- **Model:** `Δspread = Σ_j β_j Δx_j`, with **no intercept**: a window in which no driver moved predicts no rise, so
  whatever the drivers do not carry is residual and is not absorbed into a constant. Fitted by least squares.
- **Left out:** the fit for an episode uses no window that overlaps its own baseline-plus-window (windows whose start
  differs from the onset by fewer than 10 panel days), so no episode explains itself.
- **Shares:** for each subset of drivers, the model is refitted on that subset and predicts the episode's rise; the
  Shapley value of driver `j` is its average marginal contribution over all orderings (16 refits for four drivers).
  A share is its Shapley value divided by the episode's rise. The **residual share** is the rise less the full model's
  prediction, divided by the rise. Shares and residual sum to 1; a share may be negative (a driver that worked against
  the rise).
- **Interval:** the stationary bootstrap over the fitting rows (the parent's `metrics.stationary_bootstrap_indices`),
  mean block **10** panel days, **10,000** draws, seed **20261013**, each draw refitted, 90% percentile interval. The
  seed is fixed here and per episode as `seed × 1,000,003 + start`. A draw with a singular design is skipped; more than
  5% skipped refuses the interval.
- **What the synthetic tests show** (`tests/test_attribution.py`, planted shares, no real data): with no noise and no
  planted residual the residual is zero; a planted residual is recovered and does not leak into the drivers; the 90%
  interval covers the planted share at close to the nominal rate (30 seeded replications each at two noise levels, over
  the four shares and the residual; the test's floor is 0.80); with orthogonal drivers a share is exactly
  `β_j Δx_j / rise`.
- **A property Eleonora should know before choosing.** The shares come from refitted sub-models, so when drivers are
  correlated in the fitting sample, chance correlation moves a *point* share away from its planted value even with no
  noise (on one synthetic episode a share of 0.49 was estimated at 0.33). The interval, not the point, is what the test
  holds to its nominal coverage. With the drivers' coefficients held fixed (the alternative below) a share is exactly
  `β_j Δx_j / rise` and has no such shift, but then it is not a Shapley value of anything.

- **Fixed-coefficient shares (added by the ruling).** Beside each Shapley share the output reports
  `β_j · Δx_j / rise`, with β from the full model fitted on the whole fitting sample (`Attribution.fixed_shares`).
  They are reported only: they are not the method, they have no interval of their own, and no outcome rule reads them.
  Intervals lead every table; a point share is shown after its interval.

**Alternative (written out, not chosen).** Flow accounting through the Stage 2 demand curve: reserves' contribution is
the curve's slope at the baseline times the reserves change, and the other drivers enter through their effect on reserves
and on the funding need. It needs the curve's parameters, which are estimated on the same days; it is cheaper to
interpret and harder to bootstrap. It is not built.

**Decided:** the regression with Shapley shares; the alternative is not built.

## 3. The fitting sample (decided, as proposed)

- **Rows:** every development window, not only the episodes' (about the whole development sample, rather than the few
  dozen onsets): the window starting at each panel day `t` with a complete baseline and window, its spread change and its
  four driver changes. A day that is missing any of the five series for any of its ten days is not a row.
- **Why all windows:** a regression on the episodes alone has a few dozen rows for four coefficients. The episodes'
  windows are in the sample (with the episode being explained left out).
- **Tier:** development only, to 2026-09-03 (plan, Q5). `attribution.check_development` raises `LookAheadError` for a later
  date. No day from 2026-09-04 on is read.
- **For a prospective episode:** the fit uses only windows already public at the report instant (section 6), and the
  episode is reported within 10 business days of its onset (plan, Q7).

## 4. The benchmark and the placebo

- **Benchmark:** the same method with reserves as the only driver (`RESERVES_ONLY`). Reported beside every episode:
  the drivers' explained share above reserves alone (`explained_above_reserves`).
- **Placebo:** the same decomposition on windows of the same length and day type that touch no episode
  (`placebo_starts`). **Day type (decided):** the start day's quarter-end flag and whether Treasury settlement is
  positive. **20 windows per episode** (`PLACEBO_WINDOWS`; first proposed as five), drawn with a fixed seed. It tells
  whether the drivers explain episodes more than ordinary weeks. **Decided (13 October 2026):** the day type as
  proposed, and the count changed from 5 to 20.

## 5. The outcome rule (copied from the plan; not changed here)

- **"Drivers named":** the residual share is under 50% in more than half the development episodes.
- **"Residual dominates":** otherwise. That is the kill in eleonorabjornberg/repo-market-model#46; H5–H9 then get no
  driver list from H10.
- **The test of an episode** is `|residual share| < 0.5` (the absolute value, so an over-explained rise counts as a miss
  too; **decided** (13 October 2026): the plan does not say how a negative residual is read, and Eleonora rules that it
  is a miss).
- **Prospective episodes:** reported against the same rule, labelled prospective.

## 6. Missing data and the information set

- **An episode with an input missing** in its baseline or window, an incomplete window, no rise in the spread, or a
  singular fit is reported as **not attributable**, with the reason, **never dropped** (measurement protocol §11). In the
  outcome rule it stays in the denominator as a miss.
- **Inputs are read through the parent's as-of rule** (`repo_model.asof.InformationRule`). The outcome is the first
  published value. `attribution.check_window_public` raises `LookAheadError` if any input of an episode's window was
  not public at the decision instant of the report day.
- **The development application (step 2) is a retrospective table**, so the fit for one episode uses windows after it
  (that is what leaving the episode out and keeping the others means). Only the prospective report is bound to
  what was public.

## 7. What this record does not do

- It attributes no real episode and publishes no figure (step 2 does, after she merges this).
- It does not register anything; registration of the frozen method is her attested action (plan, H10).
- It does not change the plan's outcome rule, the episode list, or the model repo.

## 8. Decided (13 October 2026)

Eleonora's ruling on [#37](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/37#issuecomment-6159864877)
accepted every recommendation. The text of the record outside this section is unchanged except where the values and the
two additions below say so.

1. The window: 5 baseline days, 5 window days (section 1). As proposed.
2. Regression with Shapley shares (section 2). As proposed, **with fixed-coefficient shares `β_j · Δx_j / rise` reported
   beside each Shapley share**; they are reported only; intervals lead every table.
3. The fitting sample: all development windows with the episode's neighbourhood left out (section 3). As proposed.
4. The placebo (section 4): the day type as proposed; **20 windows per episode** instead of 5.
5. An episode counts as attributed only if `|residual share| < 0.5`; a negative residual is a miss (section 5).
6. The source of the episode list: as decided on #20 (section 0).

## 9. Amendment (Eleonora, 14 October 2026; finding #52): a selection-aware null and ON RRP as a driver

**Status: DRAFT for Eleonora (directive #62). Every value in this section is PROPOSED and is hers to set. Nothing here is
in force until she merges it, and sections 1 to 8 stand except where this section changes them.** Her ruling
([on #52](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/52)): amend this record before H10 step 2, to
add a null that allows for how episodes are selected, and to add ON RRP as a driver. This section applies no method to a
real episode, scores nothing, and publishes no figure.

**Why.** Episodes are picked by `onset.onset_flags` on the spread itself, so each episode's residual is large by
construction (finding #52: in its simulation at R² 0.49, 39% of rule-picked onsets pass the 50% residual bar, against 78%
when windows are picked on the drivers). And one pooled fit spans both ON RRP regimes, while only 2 of the 31 onsets fall in
the abundant regime, which covers half the days (finding #52; not re-derived here).

### 9a. The selection-aware null (constructions laid out; one recommended)

The test of an episode in section 5 asks only whether its residual share is under 50%. The null asks how much of a rise the
drivers would "explain" in an episode that the same rule picked from a spread they did not drive.

| | Construction | For | Against |
|---|---|---|---|
| **N1 (recommended)** | Remove the drivers' fitted effect from the daily spread, keep its level (`driver_free_spread`). Resample that series with the stationary bootstrap (block 10, as section 2). Pick onsets from each resample with the model repo's own rule (`repo_model.onset.onset_flags`). Attribute each pick against the real drivers with the method of section 2 (`selection_null`). | It is the same rule on a series with no driver effect, so the null has the selection built in. It keeps persistence, so clusters of high days survive. It reuses the model repo's rule and the section 2 shares. | The fit for a null pick does not leave that pick out, which raises the null's explained share a little: the bar is conservative. The coefficients are estimated on the same sample, so the removal is not perfect (a test shows the refitted coefficients are zero to six places on a synthetic series). |
| N2 | Apply the onset rule to the residual series of a fit on non-episode days (the directive's first example). | One deterministic series, no resampling. | One draw is not a distribution: its tail needs a resampling step anyway, and then it is N1 with a different surrogate. |
| N3 | Choose placebo windows by the drivers (the finding's 78% figure) rather than by the rule. | Shows the size of the selection effect. | It answers a different question: windows that are not episodes. It sets no bar for episodes. |

**Proposed statistic and bar (hers to set).**

- **Statistic:** the episode's **explained share** (the full model's prediction over the rise, `Attribution.explained_share`,
  which is one minus the residual share). It is the quantity that selection depresses.
- **Bar:** the **95th percentile** of the explained shares of the null's picks, pooled over draws (`NULL_QUANTILE`, 0.95).
  Alternatives: 90th (looser) or 99th (stricter). An episode **beats the null** when its explained share is above the bar.
- **Draws:** **1,000** resamples (`NULL_DRAWS`), seed **20261013** (`SEED`, as section 2). The synthetic tests use fewer.
- **Refusal:** a null in which the rule picks no attributable episode from any draw has no bar and raises `ValueError`.

**Proposed use in the outcome rule.** An episode counts as attributed only if it is **under the residual bar of section 5
and also beats the null** (`outcome_with_null`). The denominator is unchanged (every episode, a not-attributable one as a
miss), and so are the "more than half" majority and the two outcomes. The code reports the count under the bar, the count
beating the null, and the count that satisfies both, so the null's effect is visible and not folded in.

**Question for Eleonora.** Is the null a second condition on each episode (recommended), or does it replace the 50% residual
bar? Replacing it changes the plan's outcome rule (section 5 says the plan's rule is not changed here), so it is hers.

### 9b. ON RRP as a driver

- **The series (recommended):** the model repo's **ON RRP take-up**, the column `on_rrp` (the New York Fed's operation results,
  `reverse_repo_total_accepted`, which the panel's `declaration.phase3_declaration()` switches on, USD bn). It is a quantity;
  this repo's ON RRP offering rate (#25) is an administrative price that changes a few times a year, so it cannot carry an
  episode's rise, and it is not a driver here.
- **Availability:** read through the parent's `InformationRule` like the other drivers (`attribution.check_window_public`
  checks every group the rule names). On the registry's declarations the spread is published later than ON RRP, so the spread
  is the input that binds and ON RRP's own check never does; the test of ON RRP's check therefore uses a stub rule.
- **How it enters (recommended):** as the **window change**, like every other driver (section 1: window mean minus baseline
  mean), added last: `DRIVERS_WITH_ON_RRP = DRIVERS + ("on_rrp",)`. The Shapley shares then run over 2^5 = 32 refits. The
  decided `DRIVERS` is unchanged until she merges this.
- **Alternatives, not built:** (i) the **level** of ON RRP at the window; it mixes the regime into the coefficient and does not
  move with an episode. (ii) An **interaction with the regime**: `on_rrp × 1(on_rrp < ON_RRP_DEPLETION_BREAK_BN)`, with the
  parent's break at USD 100 bn (`repo_model.contract`), which gives each regime its own coefficient. It is the direct answer to
  the finding's "one fit across both regimes", but only 2 of 31 onsets are in the abundant regime, so its coefficient there
  would rest on very few episodes. Recommended only after the change has been tried. Hers to choose.
- **The pooled fit stays one fit across regimes** under the recommendation; the finding's regime point is answered by the
  driver, and the interaction is the stronger answer if she wants one.

### 9c. What the tests show, on synthetic episodes only

`tests/test_attribution.py` (classes `SelectionNullTests`, `OnRrpDriverTests`): the null rejects episodes planted with a real
driver effect; of the onsets the rule picks from a spread with no driver effect, at most 20% beat it (nominal 5%; the ratio on
the seeded series is recorded in the PR); a null with nothing selected is refused; the surrogate spread has zero refitted
coefficients; the ON RRP driver recovers a planted coefficient and a driver with no effect gets one near zero.

### 9d. Questions, each with a recommendation

1. Construction: N1 (recommended), N2 or N3?
2. Statistic: explained share (recommended)?
3. Bar: the 95th percentile of the null (recommended), the 90th or the 99th?
4. Second condition or replacement of the 50% bar? Second condition (recommended).
5. ON RRP: take-up, as a window change (recommended), a level, or a regime interaction?
6. Draws: 1,000 (recommended)?

### 9e. What this amendment does not do

It attributes no real episode, runs no null on real data, scores nothing and registers nothing; `results/`, `metadata/` and
`snapshots/` are unchanged. H10 step 2 waits for this record to be merged.
