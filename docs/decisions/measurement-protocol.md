# Decision: measurement protocol, v1

**Decided by Eleonora, 12 October 2026 ([her comment](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/20#issuecomment-6131178133)). In force once this record merges.**

This is how a measurement claim, which has no outcome of its own, is judged. It is shaped like eleonorabjornberg/repo-market-model#640 and defers to it wherever both apply. Proposed values are marked P1–P6.

## 0. What it decides
- **It governs H7m.** The stability, sharpness and information claims for an as-of estimate of deployable liquidity.
- **The same evidence rules bind H10's prospective episodes** (§11).
- **The verdicts** are eleonorabjornberg/repo-market-model#640's four: supported, killed, inconclusive (continuing), not testable as stated.
- **No forecast claim is judged here.** H7f is judged in the model repo under eleonorabjornberg/repo-market-model#640.

## 1. Which data can be evidence
- **The tiers are eleonorabjornberg/repo-market-model#640 §1's**, with the model repo's lockbox:
  - development to 2026-09-03;
  - an unused tier up to registration;
  - confirmation after it.
- **Development data never gives a verdict.** Stages 2–6, and every development score under this record, are development evidence, however they come out.
- **Confirmation is prospective only:**
  - the registered estimator's daily estimate and interval, produced at the decision instant and committed with hash and timestamp before that day's outcome is public;
  - each scheduled refit's real-time path, committed when it is made.

## 2. The quantity and its benchmarks
- **Estimate.** Aggregate deployable liquidity on T, in points of bank assets, as of 16:00 on the panel day before T. It is read through `repo_model.asof`, filtered or real-time only. Each estimate carries a 90% interval.
- **R.** The reserves ratio (`repo_model/scarcity.py:161`).
- **S.** The scarcity state (`scarcity.py:194`).
- **Stress event on T.** The model repo's material-use event (`repo_model/fed_liquidity.py:163`). Both are cited at the model pin and never redefined here.

## 3. Goalpost 1, stability (P1)
- **The gap.** On every served day, the real-time estimate under refit k and under refit k − 1 differs by less than **0.5 points of bank assets**. This is Stage 3c's bar (`docs/stages/stage-3c.md:30`) and Stage 6's (`docs/stages/stage-6.md:86-87`).
- **It is a requirement, not a statistic.** One prospective breach kills H7m.
- **Why keep the bar unchanged:** it was set before Stage 6, and changing it after Stage 6's result would be a change motivated by a result (§12). It also rewards what H7 needs: a buffer that moves with observed data, not with re-estimation (`stage-6.md:167-173`).

## 4. Goalpost 2, sharpness (P2)
The median width of the daily 90% interval is under **3 points of bank assets**. That is the width of the parent's 11–14% sensitivity range (`stage-6.md:88-89`). It is judged on every confirmation day logged so far.

## 5. Goalpost 3, information beyond R and S (P3)
- **The statistic.** The scarcity-state-stratified AUROC of the estimate, ranked low to high, minus that of R, for separating stress days from other days. Each stratum's AUROC is computed within one S level, and the strata are pooled by event-weighted mean. No model is fitted, so it cannot learn from the confirmation days. Holding S fixed is what makes it a test against R+S together.
- **MME.** **0.05 AUROC points.** Stage 6's A and B differed from each other by 0.004 (`stage-6.md:148`). The power study (§9) checks that 0.05 is detectable. If it is not, the study reports what is, and Eleonora sets the MME once, before registration.
- **Reported, not deciding:**
  - unstratified AUROC against R;
  - the 2021-on (standing-facility) split (`stage-6.md:104-105`);
  - the splits at the clearing mandates (`docs/decisions/evaluation.md:44-56`).

## 6. The test (P4), aligned with eleonorabjornberg/repo-market-model#640 §5
- **Bootstrap.** A stationary bootstrap over days (event indicator, estimate, R and S resampled together), with mean block length 10 business days and 10,000 draws.
- **Seed.** Fixed at registration.
- **Interval.** One-sided 95%.

## 7. Choice and registration
- **Eligibility in development.** Goalposts 1 and 2 hold on the development walk-forward, and the distribution account (§8) exists.
- **Choice.** The eligible candidate with the highest development §5 statistic is primary. Within 0.02, the narrower median interval wins. This is Stage 6's rule (`stage-6.md:100-107`), re-based on R+S. Up to two secondaries.
- **Registration** is Eleonora's attested action. It freezes:
  - code, configuration, inputs and refit schedule, by hash;
  - the parent pin and panel digest;
  - P1–P6 and the seed;
  - the development variant count.

  Nothing about a registered candidate changes after that. A changed candidate is a new registration with a new start date.

## 8. The account of the bank distribution (the parent's exit criterion)
- **The alternatives.** Aggregate deployable liquidity is also reported under declared alternatives for how reserves spread across the three H.8 groups:
  - as observed;
  - all held by large domestic banks;
  - in proportion to group assets.

  These are `stage-6.md:90-94`. Candidates that model groups report it group by group too.
- **Required, never decisive.** It is required for eligibility and logged prospectively beside the aggregate. Its size decides nothing, unless Eleonora makes the exit criterion its own hypothesis (plan, Q2).

## 9. Effect size and timing (P5)
- **Checkpoints.** 60, 125 and 250 confirmation days.
- **Spending.** The one-sided α of 0.05 for goalpost 3 is spent across them by Lan–DeMets O'Brien–Fleming, as eleonorabjornberg/repo-market-model#640 §6.
- **The verdict at a checkpoint:**
  - **Supported:** goalposts 1 and 2 have held on every logged day and refit, and the lower bound of the §5 statistic is above 0 with the point at or above the MME. At least **10 stress events** must have been logged; the power study may raise that number before registration.
  - **Killed:** a goalpost 1 or 2 failure, or the upper bound of the §5 statistic below the MME.
  - **Inconclusive:** otherwise. Still inconclusive at 250 days means "not shown".
- **Power study.** Run on development data before the first registration. It gives the days and events needed to detect the MME.

## 10. Multiplicity
- **The goalposts.** All three must hold (an intersection–union test), so no correction is applied across them.
- **Candidates.** Holm across the primary and the secondaries on goalpost 3. No correction for the primary alone.
- **The variant count** is published with every registration. It starts from Stages 2–6, counted from their records.

## 11. Missing data (P6)
- **A missing daily estimate** counts against the estimate: R takes its place for §5, so it cannot gain, and the day is counted. For §4 the day is counted as over the bar.
- **A scheduled refit** that is missing, or that does not converge, is a goalpost 1 breach. There is no silent fallback, as in Stage 4's rule (`PLAN.md:235-237`).
- **More than 5% missing days** voids the registration.
- **A day with a stale input** refused by a staleness guard is missing, not imputed.
- **The outcome** is the first published value.
- **For H10,** an episode whose inputs are missing is reported as not attributable, never dropped.

## 12. Change control
- **This record becomes** `docs/decisions/measurement-protocol.md` v1, merged by Eleonora (attested).
- **It changes only on** eleonorabjornberg/repo-market-model#640 §13's two kinds of evidence:
  - (a) a synthetic or analytic demonstration that it misjudges estimators of known quality;
  - (b) a reproduced error in its data or code.
- **Each change** needs the auditor's confirmation and Eleonora's attested action.
- **No change may be motivated by a candidate's result.**
- **A change applies only to confirmation days logged after it.** Verdicts reached stand under the version they were reached with.

## 13. Must exist before the first registration
1. The goalpost module, tested on synthetic estimators of known quality:
   - a stable and sharp one;
   - a jumpy one;
   - a wide one;
   - R itself, which must score 0 on §5;
   - one with planted information beyond R.
2. The prospective logging hook in the model repo (plan, Q4).
3. The power study (§9).
4. The auditor's check that 1–3 match this text.

## 14. Amendment (19 October 2026): section 2's cite of the stress event

**Status: a draft for Eleonora's review (directive #124; finding #75, point 1). In force once she merges it.** It is a
correction of a reproduced error under section 12(b). It changes no rule, threshold or definition, and section 2 above is left
as written.

- **Superseded cite:** `repo_model/fed_liquidity.py:163`, in section 2's "Stress event on T". At the pin (`8fd2cf8`) that line
  is the closing brace of a mapping, not the event. The parent defines no event column there.
- **Where the event is defined.** The meaning is `docs/decisions/data-meaning.md` answer 14: a day with Fed repo operations
  accepted of `fed_repo_accepted >= 1.0` (USD billions), term repos counted as an amount outstanding over their term. This
  repository states the rule in one place, `repo_liquidity.goalposts.is_material_use` (`MATERIAL_USE_BN = 1.0`). Section 2 is
  read with that cite in place of the superseded one.
- **Labels now run through 2026-09-03** (the development end), since PR #107 (directive #105; finding #75, point 2).
- **What it does not do.** It does not change what the event is, the $1bn bar, the benchmarks, the goalposts or any score. The
  cites to `scarcity.py:161` and `scarcity.py:194` are unchanged and still resolve.
- **A guard against the next stale cite:** `tests/test_protocol_cites.py` checks that every `file.py:line` cite of the parent in
  this record opens a `def` or `class` at the pin, and that the event's replacement exists.
