# H7m, development step 5: the three goalposts, scored on development days for every estimator in play, and for R, S and R+S

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 5 of the plan
(`docs/research/plan.md`, "Development steps", item 5). Directive #178. It follows step 4 (`docs/stages/h7-step4.md`, PR #174) and
precedes step 6, the choice of a primary candidate, which is not made here.

**It gives no verdict.** Development evidence is never a verdict (protocol section 1). Nothing here is a registration, a
prospective result or a choice. A reading is reported with its interval and its split; whether it "passes" is not said. This
document is written before the code (`src/repo_liquidity/h7_step5.py`) and the code is held to it.

**Under her direction of 22 October ("refocus": fix the known failures, stop patching failed models with variants).** There is no
new variant, no re-specification and no new refit schedule. Every estimator scored is one already declared and recorded on main:

| Family | Estimators | Record |
|---|---|---|
| A | B, V1 to V6 | `results/h7/kink.json` (restated by #168) |
| C | C, CV1 to CV4 | `results/h7/calendar-clean.json` (#150) |
| the account | the daily estimate and 90% interval of each of the above | `results/h7/distribution-account.json` (#174) |

Nothing is re-fitted. An estimator that serves no scored day is reported "not scorable", with its reason from the records, and is
never re-fitted (CV1, CV2 and CV4 are not identified at 69 of 70 refits, and serve no day). D and its variants were dropped
under #142 (#148) and are not run.

## 1. The protocol's definitions, quoted

All of this is `docs/decisions/measurement-protocol.md` v1, in force, with the two rulings of 15 October 2026 recorded by #92
(`docs/stages/h7-g6.md`, Q2) and the amendment of section 2 (section 14, #124).

**Goalpost 1, stability (section 3).** "On every served day, the real-time estimate under refit k and under refit k − 1 differs by
less than **0.5 points of bank assets**. [...] It is a requirement, not a statistic. One prospective breach kills H7m."

**Goalpost 2, sharpness (section 4).** "The median width of the daily 90% interval is under **3 points of bank assets**." A
missing day counts as over the bar (section 11).

**Goalpost 3, information beyond R and S (section 5).** "The scarcity-state-stratified AUROC of the estimate, ranked low to high,
minus that of R, for separating stress days from other days. Each stratum's AUROC is computed within one S level, and the strata
are pooled by event-weighted mean. No model is fitted, so it cannot learn from the confirmation days. Holding S fixed is what
makes it a test against R+S together."

**The MME and the event floor (section 5, section 9; her ruling of 15 October on G6, Q2, recorded by #92).** The MME is **0.05
AUROC points**; the event floor is **10 stress events**. Both are kept: `goalposts.MME`, `goalposts.EVENT_FLOOR`.

**Missing data (section 11).** "A missing daily estimate counts against the estimate: R takes its place for section 5, so it
cannot gain, and the day is counted. For section 4 the day is counted as over the bar." More than 5% missing days voids a
registration; that is a registration rule and is reported here as a share, not applied.

**The stress-day definition (section 2, amended by section 14).** A stress event on T is the parent's material-use event: a day
with Fed repo operations accepted of `fed_repo_accepted >= 1.0` (USD billions), term repos counted as an amount outstanding over
their term (`docs/decisions/data-meaning.md`, answer 14; `goalposts.is_material_use`, `MATERIAL_USE_BN = 1.0`). The label is read
from the parent at the pin through `fed_liquidity.assemble`, from 2019-09-17 (`goalposts.EVENTS_FROM`), counted per operation on its
operation date. The label is an outcome and is never an input to any estimate.

**The bootstrap convention.** Protocol section 6, aligned with eleonorabjornberg/repo-market-model#640 section 5 (the parent's
`repo_model.scoring_protocol`): a stationary bootstrap over days, event indicator, estimate, R and S resampled together, mean block
length **10** business days (`scoring_protocol.BLOCK_LENGTH`), **10,000** draws (`scoring_protocol.DRAWS`), bounds read one-sided at
95%. The parent's forecast interval is studentized by a Newey-West standard error; section 6 of this repository's protocol, the
power study (G6) and `goalposts.information_test` use the percentile bound of the AUROC difference. See marked question Q1.

## 2. What is read, and from where

- **R and S** are read only from the parent: `scarcity.reserves_ratio` and `scarcity.reserve_scarcity_state`, evaluated on what
  `repo_model.asof.InformationRule` serves at each decision instant, through `h7_estimator.asof_days` under
  `declaration.phase3_declaration()` and `scarcity.measurement_declaration()` (as every earlier step reads them). This repository's own
  reserves-over-assets code (`demand_curve.py:187-188`, `curve_feature.py:240-244`) is not used (plan, H7m "Benchmarks").
- **The estimates** are each estimator's daily record in `results/h7/distribution-account.json` (`as_observed` aggregate, `lower`,
  `upper`, in points of bank assets rounded to four places), converted to shares (`/ 100`) so that they sit on R's scale when R takes
  a missing day's place. For A the record's values equal `100 * (R - k)` of the refit in force; the run checks it (to the rounding),
  which also checks the run's R against the account's. A is A as defined (`R - k`); A through the group machinery is step 4's marked
  reading and is not an estimator declared by a record, so it is not scored.
- **The window** is the days the records serve: from the first served day (2020-03-17) to 2025-12-31, the fits' own window
  (marked question Q5). Every scored day has an event label, a ratio and a state; any that has not is dropped and counted. No day
  after 2025-12-31 is read, and the parent's lockbox refuses a locked day at every read.
- **Goalpost 1 for A** is read as A's restated record has it (`results/h7/kink.json`, `summaries`, `all_served_days.goalpost_1`):
  the worst gap in points and its day, the days compared and the missing refits. That record cannot recompute the count of
  breaching days without a re-run (#166), and this step does not re-run it.
- **Goalpost 1 for C** is "unreadable on development data, read prospectively" (her option 6, 22 October). It is never computed
  here and never read as a pass or a fail.

## 3. What is computed

**Goalpost 2.** Per estimator, from the daily 90% interval (`upper - lower`, in points): the median width on the window with a
missing day counted as over the bar (section 4 with section 11), against the bar of 3 points; and beside it the median over the
days the estimator serves (the form A's record gives, `kink.json` `goalpost_2`). Each is checked against the tracked record's own
median. Split as in section 4 below.

**Goalpost 3.** Per estimator that serves at least one window day, the information gain, in AUROC points, with its bootstrap
interval, against each of the three benchmarks, "ranked low to high" (an event expected to sit low; ties count half;
`deployable.auc`):

| Against | The statistic | Days |
|---|---|---|
| R | AUROC(estimate) minus AUROC(R), over all days (unstratified; protocol section 5, "reported") | the window; a missing day takes R's value (section 11) |
| R+S | the section 5 statistic: within each S level AUROC(estimate) minus AUROC(R), pooled by events (the deciding statistic) | the window; a missing day takes R's value |
| S | AUROC(estimate) minus AUROC(-S), over all days (S ranked so that a higher state is the lower score; marked question Q2) | the days the estimator serves |

**The benchmarks' own scores**, on the same window days: R, AUROC over all days; S, AUROC of -S over all days; R+S, the
stratified AUROC of R within S levels pooled by events (section 5 fits no model, so within a level R+S ranks as R does). They
are computed here and never cited from Stage 6 (plan, "Benchmarks"). R's gain against R, and R+S's against R+S, are 0 by
construction.

**The interval.** The 5th and 95th percentiles of the statistic on 10,000 stationary-bootstrap resamples (mean block 10), which are
the one-sided 95% lower bound (section 6) and the one-sided 95% upper bound (the "killed" bound, `goalposts.FUTILITY_LEVEL = 0.05`),
read together as a two-sided 90% interval. No look is spent (no Lan-DeMets level): development is not a checkpoint. Each interval
is placed against the MME of 0.05 in words only: "below the MME" (upper bound under it), "at or above the MME" (lower bound at
or over it) or "straddles the MME". It is never called a pass or a fail. The seed is `20261024` plus the position of the subset in
the split list; the same resamples serve every estimator on the same days.

## 4. Splits

Every pooled figure sits beside its splits; a pooled figure alone is not a result. Each split is bootstrapped on its own days in
date order.

- **By regime:** the parent's declared regimes (`metadata/evaluation_splits.json`, `SplitDeclaration.regime`): 2020, 2021-23, 2024,
  2025-26 (only 2025 is in the window), as the parent requires for a development figure.
- **By pressure-day type:** the parent's `SplitDeclaration.reporting_day_type` of the scored day's own row: quarter-end, month-end,
  tax date, ordinary.
- **2021 on** (the standing-facility split, protocol section 5, "reported, not deciding"). The clearing-mandate splits fall after the
  development end and have no day.

A split with fewer than the event floor of 10 events is reported with its estimate and interval and labelled "under the event
floor", never dropped. A split in which a gain has no usable stratum (no event, or no other day) reports that stratum as dropped.

## 5. The variant count

The count of estimators declared to date, which step 6 uses, is reported from the records and not decided: A's B and the six
declared variants V1 to V6 (7 estimators, `kink.json` `variant_count` 6 added), C and CV1 to CV4 (5 estimators, `calendar-clean.json`
`variant_count_added` 4), 12 estimators in play, 10 of them variants. D and its four variants were declared and dropped
(#142); they are listed and not counted among those in play. The count "from Stages 2 to 6's records" (protocol section 10) is stated
by no record and is not counted here. How a not-scorable estimator counts is Q4.

## 6. Marked questions (for Eleonora; nothing is settled in code, the default stands until she rules)

1. **Q1. Studentization.** The parent's interval studentizes by a Newey-West standard error; this repository's section 6, its power
   study and `goalposts.information_test` use the percentile bound of the AUROC difference, and no standard error for a
   stratified AUROC difference is defined. *Default:* the percentile bound, as G6 used it. A studentized AUROC statistic would be a
   new statistic and is not built.
2. **Q2. The gain against S alone.** Section 5 defines the statistic against R and, by stratifying, against R+S; "against S" alone
   is not defined. *Default:* AUROC(estimate) minus AUROC(-S) on the days the estimator serves, S ranked high-state-is-stress, ties
   half, no stand-in for a missing day (a single vector cannot mix the estimate's scale with S's).
3. **Q3. Goalpost 2 for an estimator that serves only part of the window.** Section 4 with section 11 counts a missing day as over
   the bar; A's record gives the median over the served days. *Default:* both are reported side by side; neither is read as the
   goalpost.
4. **Q4. The variant count and a not-scorable estimator.** *Default:* every estimator declared and run counts, a not-scorable one
   included (it was tried), reported as 12 in play and 10 variants, with the Stages 2 to 6 number absent.
5. **Q5. The window.** The directive says development days; the records serve no day after 2025-12-31 (no refit serves a 2026
   day), so 2026-01-01 to 2026-09-03 is not scored. *Default:* as is (the same reading as step 4, Q3).

## 7. Tests and guards

Tests first (`tests/test_h7_step5.py`, `tests/test_h7_step5_record.py`). One new guard raises `LookAheadError`: a day an estimate is
read for must lie at least `SERVING_LAG` business days after the cutoff of the refit that made it, re-checked from the account's own
`cutoff` column (the mutation is recorded in the test's docstring). A window day that is locked or after 2025-12-31 is refused
(`goalposts.labelled_days`, `lockbox.require_unlocked`).

## 8. The record and the run

`scripts/h7_step5.py` writes `results/h7/step5-scores.json` and prints `docs/research/h7-step5.md` from it (`--render`;
`--render --check` exits 1 if the page is stale). Neither is edited by hand. The record is in `repo_liquidity.records.OWN_CHECK`
with `tests/test_h7_step5_record.py`. `--timing` times the bootstrap on a synthetic window of the real size, before anything is
scored. The run is under the two-hour line, so it runs in the cloud:

    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py --timing
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py
    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_step5.py --render --check
