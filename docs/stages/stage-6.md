# Stage 6 plan: a deployable-liquidity model, judged by the parent's exit criterion

**Written 7 October 2026, before anything in Stage 6 is built or fitted.** Nothing below is computed until Eleonora
has merged this plan and the evaluation amendment that comes with it. Each candidate is then built in its own pull
request, which she reviews before the next starts.

## Why Stage 6

- Stage 4 used Stage 2's curve as one extra input to the parent's published forecast. It was not shown to help, and in
  substance it is the parent's own model: the curve is a function of reserves, which the parent already reads. Phase 3
  still has no deployable-liquidity model, which is its goal (`PLAN.md`).
- **Eleonora's rulings of 7 October 2026:**
  1. **Phase 3 is judged by the parent's exit criterion:** stable posterior intervals for aggregate deployable
     liquidity, with a clear account of their sensitivity to how reserves are distributed across banks. Forecast gain
     is reported beside it and decides nothing. This changes `docs/decisions/evaluation.md`; the amendment is drafted
     in this pull request.
  2. **Try every candidate and use the best one.** The rule that picks it is fixed below, before any candidate is
     fitted.
  3. **Anchor the buffer with the supplementary leverage ratio.** Banks report leverage headroom every quarter, whether
     reserves are scarce or not. Spreads reveal the buffer only in the two scarce episodes (2018 to 13 March 2020, and
     2025), which is where every latent model so far broke. Nicholas rated the end of the SLR exclusion (2021-03-31)
     the reform most material to the buffer (`docs/decisions/data-meaning.md`, answer 11). Its data meaning is
     question 16 on issue #1, asked 7 October 2026.
- Stage 5a, the daily log of the frozen Stage 4 forecast, goes on unchanged. It answers the forecast question; Stage 6
  answers the measurement one.

## The quantity

**Deployable liquidity on day T** is reserves minus the buffer banks want to keep, in dollars, for the aggregate and,
where a candidate can, for each H.8 bank group:
- large domestically chartered banks;
- small domestically chartered banks;
- foreign-related institutions (Nicholas, answer 6).

Every input is read as of 16:00 on the panel day before T, through the parent's `asof.InformationRule`. Each candidate
gives the buffer and a 90% interval for it, so deployable liquidity has one too. Only filtered or real-time estimates
are used, never smoothed ones.

## The candidates

The development window is the as-of walk-forward to 2025-12-31 on the parent's fold grid (first refit on 2020-03-13
where a candidate needs the first scarce episode, then every 21 observation days). 2026 is not evidence.

**A. The curve's bend.**
- The buffer is the bend of Stage 2's corridor-position curve times bank assets.
- The bend is fitted only on scarce-episode days, as Stage 2's revised test does: an episode counts with at least 60
  days below 13% of bank assets.
- One break is allowed between the episodes. Its date is chosen by least squares from 2020-03-16 to 2024-12-31, and it
  is fitted only once the second episode counts. Until then, the real-time bend is the first episode's.
- The interval comes from the stationary bootstrap of the bend (10-day mean block, 2000 replications, as Stage 2).

**B. The latent buffer, identified differently.**
- Stage 3b's state-space model, with three changes, each fixed now:
  - the buffer does not drift: it moves only at the declared reform dates (`reform-dates.md`), or at one estimated
    break if the reform-date fit is worse by the likelihood;
  - ON RRP take-up is not a measurement: the gap TGCR − ON RRP rate takes its place, as Nicholas answered (answer 12);
  - several fresh starts at every refit (Stage 3b's amendment).
- The interval is the filter's own.
- Known before writing: Stage 3b's no-drift variant fit much worse and showed no shift.

**C. Bank groups.**
- The buffer is set group by group, as a share of each group's own assets: one share for each of the three H.8 groups.
- Aggregate deployable liquidity is the sum over groups of max(group cash assets − group buffer, 0).
- The shares are fitted so that aggregate deployable liquidity, through Stage 2's curve form, best explains the
  corridor position in the scarce episodes.
- The interval comes from the stationary bootstrap.
- **Needs first:** the H.8 group series (cash assets and total assets for each group, first prints). They are declared
  and built as Stage 1's inputs were: an availability declaration, a leakage test and a recorded mutation.

**D. SLR headroom.**
- For the SLR-bound group, the buffer is a level plus a slope times a declared transform of leverage headroom in
  dollars, Tier 1 capital ÷ required ratio − total leverage exposure. The level and slope are estimated from the
  corridor position in the scarce episodes. Headroom carries the buffer between them.
- The other groups are as in C.
- The interval comes from the stationary bootstrap.
- **Needs first:** Nicholas's answer to question 16 (source, level, which banks, timing, the 2020–21 exclusion, and
  foreign-related institutions), then a first-print availability declaration.
- **Its own out-of-sample test, reported beside the ranking:** fitted on the first episode only, does it predict the
  2025 bend inside the 2025 bend's 90% interval from Stage 2? This is the test of whether leverage explains the shift.

## What a candidate must show to be eligible (the exit criterion)

Fixed now, for every candidate alike. Computed on the development window, on each refit's real-time estimate (Stage
3c's definition: the state a forecast for T reads).

1. **Stable.** On every served day, aggregate deployable liquidity under refit k and under refit k − 1 differs by less
   than 0.5 points of bank assets (Stage 3c's bar).
2. **Intervals.** A 90% interval for aggregate deployable liquidity on every day, with a median width under 3 points of
   bank assets. That is the width of the parent's 11–14% sensitivity range, which was Stage 2's sharpness bar.
3. **An account of the distribution.**
   - Aggregate deployable liquidity is also reported under declared alternatives for how reserves spread across the
     three H.8 groups: as observed; all held by large domestic banks; and in proportion to group assets.
   - C and D report it group by group as well.
   - This must exist for a candidate to be eligible. Its size decides nothing.

## How the best one is chosen

Fixed now. Among the eligible candidates:

1. **Validity against stress, the deciding score.** How well real-time deployable liquidity, taken low to high,
   separates the declared material-use days (`fed_repo_material_use`, Nicholas's answers 13 and 14) from other days.
   It is the area under the ROC curve, on days from 2019-09-17, when such an event can first occur. The highest wins.
   - **Nicholas's caveat (answer 14):** in 2019–20 the Fed set its repo operations' sizes, partly to cover year-end,
     so material use then reflects the Fed's design as well as demand. The score is therefore also reported for 2021
     on, the standing-facility era. That split is reported only.
2. **Ties:** within 0.02 of each other, the narrower median interval wins.
3. **If no candidate is eligible,** Stage 6 is not shown. Every candidate is reported, and nothing is chosen.

**Reported, not deciding:**
- each eligible candidate's deployable liquidity as one extra input to the parent's published forecast, through
  Stage 4's machinery (the CRPS gain, paired by day);
- D's out-of-sample shift test;
- the full real-time paths, with their intervals.

**Forking paths, stated plainly.** Choosing the best of four on one development window flatters the winner. The chosen
model's claim therefore rests on development evidence only, until:
- it is frozen and its daily deployable liquidity is logged, as Stage 5a logs the forecast;
- and the next scarce episode, or the scoring dates of `evaluation.md`, test it.

## Order

1. **A and B** first: their data are in hand. Each is its own pull request with its eligibility result.
2. **C** after the H.8 group inputs are declared and built.
3. **D** after Nicholas answers question 16, and its inputs are declared and built.
4. **The choice:** once all four are scored, or are each recorded as not buildable with the reason.

Every step is reviewed by Eleonora before the next starts.

## Not in Stage 6

- No change to the parent.
- No change to the frozen Stage 4 declaration or to the Stage 5a log.
- No 2026 data.
- No publishing.
- No candidate fitted before this plan and the evaluation amendment are merged.
