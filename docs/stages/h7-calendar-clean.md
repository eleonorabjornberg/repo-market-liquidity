# H7m, declared development variants of candidates C and D: calendar-clean training days, a least-absolute-deviation fit, and EFFR − IORB as an alternative left side

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development, steps 2 (candidate C,
`docs/stages/h7-step2.md`) and 3 (candidate D, `docs/stages/h7-step3.md`). Directive #145. It applies Eleonora's standing rule
of 20 October 2026, "Calendar first" (relayed by the model orchestrator): a repo-market model that does not read calendar days
at the target day is wrong, and any result from it is provisional until it is re-run. The specification follows Lens B of
eleonorabjornberg/repo-market-model#958. The variants are **declared next to the current C and D**, not in place of them.

**This is a declaration. Nothing is computed, scored or run here, and no figure appears.** No code is written for it. The run
that follows is a separate directive, written after this document has been reviewed (`CLAUDE.md`, step by step), and it
implements what is below with no further choice, apart from the marked questions in section 7. Development, never a verdict
(`docs/decisions/measurement-protocol.md` §1).

## 1. Why

Neither C nor D leaves calendar days out of the days it fits on.

- **C.** `h7_candidate_c.training_days` (`src/repo_liquidity/h7_candidate_c.py`, function `training_days`) keeps every day, up to
  the cutoff, of each counted episode that has a group week and a corridor position. Nothing is dropped for being a quarter-end,
  a month-end, a tax day or a coupon-settlement day.
- **D.** `h7_candidate_d` fits the large group's buffer (level and slope on headroom) and the small and foreign-related shares
  jointly, over the same kind of days (those that also have a headroom). It uses no calendar exclusion either.

So 2019-09-17 and the quarter-ends help set both fits. The fit is least squares in the corridor position
(`demand_curve.fit_broken_stick`, `h7-step2.md` section 3), which weights a spike far above an ordinary day. The kink variants
of candidate A (`docs/stages/h7-kink.md`, PR #135) already carry this change for A; this document does the same for C and D, and
it is not a claim that either is the cause of anything. Whether a variant helps is what the later run measures.

## 2. The specification

The **baseline** for each of C and D is the current estimator, unchanged (every day of a counted episode with its inputs, least
squares, corridor position on the left). It is not a new variant. Every variant is compared with its own baseline.

### (a) The exclusion set: calendar-clean training days

A **training day** is as in `h7-step2.md` section 3 and, for D, `h7-step3.md` section 3. A day T is **dropped** from the days a
refit fits on, and from the days its bootstrap resamples, when T satisfies either of:

- `settlement_day` = 1, the parent's composed feature at the pin (`contract.COMPOSED_FEATURES`, `asof.COMPOSERS`;
  `repo_model.asof._settlement_day`): `quarter_end`, or `tax_date`, or `days_to_month_end ≤ SETTLEMENT_DAY_MONTH_END_DAYS`
  (2 calendar days up to and including the month's last day), or `treasury_settlement_coupons > 0`;
- `quarter_end_window` = 1, the parent's opt-in column (`data.quarter_end_window`: the quarter's last business day and the
  `data.QUARTER_END_WINDOW_BUSINESS_DAYS` = 2 business days either side).

That covers Lens B's four classes: quarter-end windows (the second clause), month-end (the `days_to_month_end` clause), tax days
(`tax_date`) and coupon-settlement days (`treasury_settlement_coupons`). Both flags are read from the parent's functions at the
pin (8fd2cf8), at the day's own decision instant. Nothing is re-implemented here.

**One exclusion set for A, C and D.** These are exactly `h7-kink.md` section 2(a)'s two clauses, so that the three candidates
share a set. No difference is declared.

What changes and what does not:

- **Only which days enter the fit changes.** The group weeks, the headroom, the ratio, the corridor position and the as-of reads
  are untouched. The training-day rules of `h7-step2.md` (a group week and a corridor position; D also a headroom) still apply,
  and the calendar clause is applied on top.
- **(Amended by section 10: the episode floor is read on all days, not on the clean days.)** ~~The counted-episode rule is taken over the clean days.~~ An episode counts at a cutoff when it has at least 60 *clean*
  training days with the all-banks ratio below 13% (D's precedent, `h7-step3.md` section 3, which takes the 60 over the days
  that have a headroom). A refit with no counted episode is **not fitted**, serves no estimate and is reported; there is no
  fallback to the baseline's fit or to a fixed share.
- **A dropped day is still served.** The estimate on a quarter-end or any dropped day is the estimate of the refit in force, as
  for any other day (serving and the two-business-day lag are unchanged). Dropping a day removes it from what a fit learns
  from; it does not remove it from what is scored.
- **The bootstrap** resamples the refit's clean training days only (block length 10, level 0.90, the parent's seed constants,
  one start per draw, as `h7-step2.md` section 3).

*Marked reading for Eleonora (same as `h7-kink.md`):* "month-end ±2 business days" is read as the parent's own month-end clause,
the last two calendar days up to the month's last day. The parent has no column for the first days of the next month, and adding
one here would re-implement the calendar. If the days after month-end must be dropped too, that needs a parent column, hers to
order. This document does not build one.

### (b) A least-absolute-deviation objective

In C's share fit, and so in D's four-parameter fit, the objective changes from least squares to the **sum of absolute
deviations** between the corridor position (or, in (c), the alternative left side) and Stage 2's curve
`a + b × max(k − D, 0)`, `b ≥ 0`, with `k` on the existing `KINK_GRID`.

- **Why this loss.** It has no tuning constant, so nothing is chosen after seeing data, and it is the loss the A variants of
  `h7-kink.md` section 2(b) use. A Huber loss, or any loss with a threshold, would need a constant; that is a marked question
  (section 7), not a choice made here.
- **The inner fit.** For a given share vector (C) or parameter vector (D), and for each `k` on the grid, the fit of `a` and
  `b ≥ 0` is the exact least-absolute-deviation line in `(max(k − D, 0), left)`; the curve takes the `k` with the least
  objective. The solver is the run's choice within `docs/decisions/dependencies.md`, with two conditions: it returns the exact
  optimum (to a relative 1e-9), and a test checks it against brute force over all two-point vertices (and the `b = 0` boundary)
  on small constructed cases. A `k` with no spread in `max(k − D, 0)` is skipped, as `fit_broken_stick` does.
- **The outer search is unchanged:** the coordinate descent over the same grids from the same three fixed starts
  (`SHARE_GRID` for the shares and for D's level; D's slope grid as in `h7-step3.md`), with the objective in (b). A negative
  slope is rejected for that parameter vector, as now.
- **The interval** is the same stationary bootstrap of the parameters, each draw refitted under the variant's objective, one
  start (the refit's own parameters); a day's interval is the 5th and 95th percentiles of that day's estimate over the draws,
  widened to hold the point estimate.

#### The tie rule (finding #54)

A least-absolute-deviation objective is piecewise linear, so exact ties are more likely than under squares, and #54's jumps
(a choice among points that fit alike changing between refits) must not return. The rule, for every variant:

1. **Tied** means within `KINK_TIE_RTOL` (relative 1e-9, the parent's constant at the pin, `satiation`) of the least objective.
2. **The kink** `k` is a nuisance location of the curve and is not part of the estimate (`h7-step2.md` section 3). Among tied
   kinks the **smaller** wins, as in the baseline. It cannot move the estimate.
3. **The shares (C) and D's parameters** decide the estimate. At the end of a refit, the fitted vector from each of the three
   starts is compared. If two of them have objectives within the tolerance and differ by **more than one grid step in any
   parameter**, the refit is **not fitted**, reported as "not identified" with the span of the tied parameters, and serves no
   estimate and no interval. It is never replaced by a picked vector. If the tied vectors differ by at most one grid step, the
   lower objective wins, then the smaller parameter vector in the order the parameters are listed (ties to the smaller value,
   as in the baseline).
4. **Along a descent,** a coordinate's tied values are resolved to the smaller value, as in the baseline, and the final point is
   tested as in (3).

The later run must show, before any real data, a constructed case in which two share vectors fit alike (the estimate would jump
between refits) giving "not identified" under every variant, and a planted optimum recovered exactly.

*Marked question (section 7, Q3):* point 3 extends the A variants' "not identified" rule (which acts on grid points of one
parameter) to the multi-parameter fits of C and D, where the baseline's three-start agreement is only recorded
(`h7-step2.md` section 3: "records whether the three starts agree"). This is the reading that keeps #54 from returning; it is
hers to confirm.

### (c) EFFR − IORB as an alternative left side

A variant may fit on the **EFFR − IORB spread** (`effr_minus_iorb_bp`, parent `contract.py:410`, in whole basis points, the
parent's note there: EFFR is a slower gauge of how ample reserves are) in place of the corridor position. It is a **separate
variant**, never pooled with the corridor-position variant.

- **Read literally:** the left side is `effr_minus_iorb_bp` of the scored day, as of its decision instant, in basis points,
  *not* rescaled to the corridor. The slope `b ≥ 0` and the intercept `a` are then in basis points; neither enters the estimate
  (the estimate is `D`, the liquidity above the buffers). The kink grid, in the units of `D`, is unchanged.
- **Consequences, stated so the run does not choose:** (i) the left side does not adjust for the width of the corridor, which
  the corridor position does; (ii) EFFR is published in whole basis points, so the objective has many exact ties and the tie rule
  above will bind more often. Both are properties of this left side, to be reported by the run, not worked around.

*Marked question (section 7, Q2):* the corridor-position left side is normalised (SOFR between the ON RRP rate and IORB). An
EFFR version normalised the same way, `(EFFR − ON RRP rate) / (IORB − ON RRP rate)`, is the natural like-for-like variant. It is
**not declared here**, because the directive names `effr_minus_iorb_bp` and a normalised version would be a second left side.

## 3. The variants and their count

Under protocol §7 and §10, each specification run is one development variant. This declaration runs four:

| # | Candidate | Days | Objective | Left side |
|---|---|---|---|---|
| CV1 | C | calendar-clean | absolute deviation | corridor position |
| CV2 | C | calendar-clean | absolute deviation | `effr_minus_iorb_bp` |
| DV1 | D | calendar-clean | absolute deviation | corridor position |
| DV2 | D | calendar-clean | absolute deviation | `effr_minus_iorb_bp` |

**The variant count this declaration adds is 4.** It is added to the count counted from Stages 2 to 6's records (protocol §10)
and to the variants `h7-kink.md` declares (6); nothing is stated here about that earlier number. No other specification is run:
in particular (a) alone and (b) alone are not run, so a difference from the baseline is the effect of the two changes together
and cannot be attributed to either (marked question Q4). A fifth variant would be a new declaration, and a changed table after
the run has seen data is a change motivated by a result (protocol §12).

## 4. D under finding #142

D serves no estimate on a day that reads no headroom (`h7-step3.md` sections 2 and 3). Finding #142 (`needs-eleonora`): with the
latest-filed vintage, no complete quarter of the nine banks is public before 2021-12-18, so D cannot be fitted on the first
episode, and Stage 6's out-of-sample test has nothing to fit on. **Eleonora has not ruled on #142 at the time of writing.**
Until she does, the clean variants **inherit D's behaviour unchanged**:

- DV1 and DV2 serve no estimate on a day with no headroom, and a refit counts an episode only on clean days that have a headroom;
- a refit with no counted episode is not fitted and is reported; there is no fallback to C's fit, to the baseline or to a fixed
  share;
- dropping the calendar days can only make the count of such refits larger, never smaller. The run reports it per variant.

This does not settle #142. If she rules on #142 before the run directive is written, the run follows her ruling; this section is
then amended in the run's PR by quoting it. Marked question Q5 restates it.

## 5. The first experiment, for the later run

H7m steps 1 to 5 under `docs/decisions/measurement-protocol.md`, for each baseline and each variant (C, CV1, CV2, D, DV1, DV2),
on the development walk-forward with the same refit dates, the same bootstrap (mean block 10, the parent's seed, the same number
of draws) and the same days:

- **Goalpost 1 (protocol §3):** the worst gap between a refit and the one before it, on every served day, against 0.5 points of
  bank assets.
- **Goalpost 2 (protocol §4):** the median width of the 90% interval, against 3 points.
- Each variant is compared with its own baseline on both. The count of refits that are **not fitted** or **not identified** is
  reported beside them, per variant, because a variant that is not fitted cannot breach a gap.
- Both goalposts are **development evidence, never a verdict**. Every figure carries the Tier "development", and none is
  compared on a locked day (the parent's `docs/decisions/lockbox.md`; the run reads through `lockbox.require_unlocked`, as step 1
  does). Goalpost 3 is not read here.
- The variants are not chosen by this document: whether any becomes a candidate is the choice rule of protocol §7.

## 6. What it does not change

- The protocol, the MME, the goalposts, and R and S as the deciding benchmarks (protocol §5).
- The parent, in every file. The variants are implemented in this repository only; the parent is imported, never edited and never
  copied.
- The estimand: still `D = R − buffer` in points of bank assets, the same interval construction, the same as-of rule, the same
  serving lag.
- The current C and D, which stay as the baselines.
- Candidate A's kink variants (`h7-kink.md`), whose run waits on Eleonora's ruling on #137.
- No new input beyond those declared: the calendar flags are the parent's, EFFR and IORB are the parent's panel, the group weeks
  and headroom are the existing snapshots. No new package.

## 7. Marked questions for Eleonora (none is settled in code)

- **Q1. Month-end.** Is the parent's two-calendar-day month-end clause the intended "month-end ±2 business days"? If not, a parent
  column for the days after month-end is hers to order (section 2(a)).
- **Q2. EFFR left side.** Raw `effr_minus_iorb_bp` in basis points, as the directive names it, or a corridor-normalised EFFR
  position (section 2(c))?
- **Q3. Not identified.** Does the "not identified" rule of the A variants extend to the three-start agreement of C and D
  (section 2(b), point 3)?
- **Q4. Attribution.** The four variants change days and loss together; (a) alone and (b) alone are not run, so no difference can
  be attributed to either. Add them (two more variants per candidate, 4 more in all), or accept the combined effect?
- **Q5. D and #142.** The clean variants of D inherit "no estimate without a headroom" until she rules on #142 (section 4).
- **Q6. Loss constant.** Least absolute deviation has no constant; a Huber loss needs one. Is the absolute-deviation loss accepted?

## 8. What the run that follows must contain

Tests first. For every part of section 2, a test written and watched failing: the exclusion flags against the parent's own
columns on a constructed week (each of the four classes, and a day that is none); the counted-episode rule on clean days; the
exact absolute-deviation solver against brute force; the tie rule and the "not identified" construction under all four variants.
A **leakage test with one recorded mutation** (`CLAUDE.md`) for the calendar read: a flag read for the cutoff day, or any day
other than T at T's decision instant, must raise `LookAheadError`, and the mutated line and the exception the failing test raised
are recorded in the test's docstring. The run keeps long computation to the Mac if it is expected to take over about two hours
(each refit now solves a linear-programming fit per grid point and per bootstrap draw).

## 9. Amendment of 21 October 2026: the rulings on Q1–Q6, applied before any fit

This section is added to the run's pull request (#147, PR #150) and quotes the ruling comment
(<https://github.com/eleonorabjornberg/repo-market-liquidity/issues/147#issuecomment-6297287738>; Q4 is Eleonora's own answer,
Q1–Q3, Q5 and Q6 are the orchestrating session's decisions she asked for, each checked against the five-lens review,
repo-market-model#958). Where this section and sections 2 to 7 differ, this section decides. Nothing has been fitted on real
days, so protocol §12 is not touched. The answers to the marked questions of section 7 are:

- **Q1, month-end.** "No, the parent's two-calendar-day clause is not enough." Decision, quoted: "add a third clause to the
  exclusion set: `repo_model.turn_days.turn_label(T)` is not `None` (declared by `metadata/turn_day_labels_959.json`; model #959,
  merged in #975). It covers every month's last business day and the first business day after it; the quarter-end and year-end
  turns overlap the existing quarter-end window. It is read from the parent, never re-implemented, at the target day's own
  decision instant, and the leakage test of §8 covers it." The exclusion set of section 2(a) is therefore three clauses:
  `settlement_day` = 1, `quarter_end_window` = 1, or `turn_label(T)` is not `None`. The label exists only after the pin of this
  document (8fd2cf8), so **the fit on real days waits for the pin move (#149)**; the tests, the solver and the constructed cases
  go ahead. The set stays shared with A: `h7-kink.md`'s set gains the same clause before A's clean run.
- **Q2, EFFR left side.** "Corridor-normalised for C and D, `(EFFR − ON RRP rate) / (IORB − ON RRP rate)`. It replaces raw
  `effr_minus_iorb_bp` in CV2 and DV2; it is not added beside it." Section 2(c) is read accordingly: the left side of CV2 is that
  position, built as the corridor position is (`demand_curve.corridor_position`, with EFFR in place of SOFR and the ON RRP rate
  in force that day). The ties from EFFR's whole-basis-point prints remain and are reported.
- **Q3, not identified.** "Yes." The rule of section 2(b) point 3 extends to the three-start agreement of C and D, and a refit
  that is not identified serves nothing and is counted beside the goalposts (section 5).
- **Q4, attribution (hers).** "Yes, add the separating variants." Per candidate, both on the corridor position:
  **CV3** is (a) only, calendar-clean days with least squares; **CV4** is (b) only, all days with absolute deviation. The table
  of section 3 is CV1 to CV4 for C (and DV1 to DV4 for D, below). CV3 is a least-squares fit on the clean days; it takes the
  baseline's kink search and its rejection of a negative slope, and the tie rule of section 2(b) for the starts, because the
  declaration says that rule holds "for every variant". CV4 fits all of the baseline's days.
- **Q5, D and #142.** "Settled by her #142 ruling (b): try the vintage rule (#148), and drop D if it cannot be obtained." D was
  dropped (#153). D and DV1 to DV4 are therefore "not run (D dropped under #142)" and **do not count as run variants**. The
  code for D's variants stays in the tree, tested, and the run does not call it. Section 4 is no longer a run-time behaviour.
- **Q6, loss.** "Yes, least absolute deviation. It is Lens B §4.2(2) verbatim, and it has no constant to choose after seeing
  data."

**Added for reporting only, nothing changed** (the ruling's last paragraph): the run reports the Politis–White block length of
each refit's training residuals beside goalpost 2, because a block of 10 that is too short would make the 90% interval too
narrow (Lens C measured about 108 days post-2020 for the model's score series). The bootstrap stays as declared (mean block 10,
section 2(a)). "Whether a longer block is needed is her call, on that figure."

## 10. Amendment of 21 October 2026: the episode floor is read on all days (option (a)), before any fit

Quoting Eleonora's ruling, relayed by the orchestrating session on PR #150
(<https://github.com/eleonorabjornberg/repo-market-liquidity/pull/150#issuecomment-6326672451>): "option (a) on the episode
floor. Whether an episode counts is decided on all days, under the declared rule of at least 60 scarce days, the same for every
variant. The fit then uses that episode's calendar-clean days only. 2025 therefore counts for every variant (77 scarce days),
and the clean variants fit on its 55 clean days."

Where this section and section 2(a) ("The counted-episode rule is taken over the clean days") or section 9 differ, this section
decides:

- **Eligibility is read on all days, the same as the baseline.** An episode counts at a cutoff when it has at least 60 days with
  the all-banks ratio below 13% among the days that have a group week and a left side, dropped or not. The rule is the same for
  every variant (CV1 to CV4) and for the baseline.
- **The clean variants (CV1 to CV3) fit on the counted episodes' clean days.** The dropped days of a counted episode leave the fit
  and the bootstrap; they do not decide whether the episode counts. CV4 fits every day of a counted episode, as before.
- A refit with no counted episode is not fitted, as before. The training sample size of each variant at each refit is reported.

Nothing has been fitted on real days, so protocol §12 is not touched.

