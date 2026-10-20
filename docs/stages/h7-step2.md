# H7m, development step 2: candidate C, the buffer set by H.8 bank group

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 2 of the plan
(`docs/research/plan.md`). Directive #41. It follows step 1 (`docs/stages/h7-step1.md`, PR #35), whose estimand and as-of
machinery it reuses, and builds candidate C of `docs/stages/stage-6.md:61-68`.

**Development, never a verdict. Nothing is scored here:** no AUROC, no CRPS, no stability or width figure, no comparison
with R or S, and no real real-time path is run or published. Scoring is step 5, under
`docs/decisions/measurement-protocol.md`. This document is written before the code (`src/repo_liquidity/h7_candidate_c.py`)
and the code is held to it.

## 1. The candidate

**The buffer** is set group by group, as a share of each group's own assets: one share `s_g` for each of the three H.8 groups
`g` (large domestic, small domestic, foreign-related). A group's buffer is `s_g × A_g`, where `A_g` is the group's total assets.

**Aggregate deployable liquidity** on a day is

    D_C = ( sum over g of max(Res_g - s_g × A_g, 0) ) / sum over g of A_g

- `Res_g` is the group's reserves, from the weekly group-reserves series of #43 (`repo_liquidity.group_reserves`): H.4.1 reserve
  balances less a fixed share for other depository institutions, split by the H.8 groups' cash-asset shares. It is an
  approximation (data-meaning row 18).
- `A_g` is the group's H.8 total assets, first print, of the same week.
- **Unit.** A share of bank assets, reported in points (`100 × D_C`), as step 1's `D = R - k` is. The denominator is the three
  groups' assets, which sum to the parent's all-banks first print within 0.1 for every week (`declarations/h8_groups.json`).
  Reserves of other depository institutions are not in `D_C`: they are not held by these groups.
- A group below its own buffer contributes 0, not a negative number: a bank short of its buffer does not take liquidity from
  one above it. This is the clip that makes C a function of the composition, not only of the total.

**What it adds over step 1.** Step 1's `D = R - k_T` subtracts one number, the kink, from the all-banks ratio. C builds the
quantity from three groups' own reserves and assets, each moving week by week.

## 2. Why C can move with observed data where A and B could not

Stage 6's results (`stage-6.md`, "Results so far"): A's real-time buffer is a constant between refits, so its estimate is
the reserves ratio minus a constant and ranks days exactly as R does; B's buffer moves only when a refit learns a shift, and is
nearly flat otherwise. Each is, between refits, R plus a constant.

C is not. Its buffer for each group is a fixed share of that group's **current** assets, and its supply is that group's
**current** reserves, both read week by week. Two days with the same aggregate reserves and the same bank assets can have
different `D_C` if the reserves sit in different groups, or if a group's assets differ, because of the clip and because each
group has its own share. Aggregate reserves can be flat while `D_C` falls (reserves move from a group with room above its
buffer to one with none). This is tested on a constructed input (must-show 3 below). Whether it moves *informatively* on
real days is step 5's question; nothing here claims it.

**The caveat C carries (answer 17(a), named as the directive requires).** Cash assets overstate small domestic banks'
reserves: vault cash and balances at correspondent banks are a much larger share of them. The group-reserves series splits
reserves by cash-asset **shares**, unanchored, so the small group's reserves are an overstated approximation and C's small-group
buffer share absorbs part of that overstatement when it is fitted. The three group levels, and so `D_C`, are approximations
for the same reason. The fixed share of other depository institutions (0.086) is a retrospective calibration, not
point-in-time (row 18(d)); **no scored or registered figure uses the group series** (her ruling of 15 October 2026,
condition 3), and C does not score anything. The quarterly Call Report anchor (`repo_liquidity.rca`) was **not** built into the
weekly series (rule 16(d)); C does not read it.

## 3. The fit

The shares are fitted so that `D_C`, through Stage 2's curve form, best explains the corridor position in the scarce episodes,
as of each refit's cutoff, on training rows only.

- **Curve form (Stage 2, `demand_curve.fit_broken_stick`).** Corridor position = a + b × max(k - D_C, 0), `b >= 0`, with the
  kink `k` on a grid in the units of `D_C` (`KINK_GRID`: 0.05 to 8 points of bank assets in steps of 0.05 points). Corridor
  position is Stage 2's: SOFR's place between the ON RRP rate (0) and IORB (1), with the rate in force that day. The kink is a
  nuisance location of the curve; it is reported in the record and is **not** part of the estimate (the estimate is `D_C`, the
  liquidity above the group buffers).
- **Scarce episodes (Stage 2's revised test, as Stage 6's A applies it).** An episode counts at a cutoff when it has at least 60
  training days with the all-banks ratio below 13%. The two episodes are Stage 2's: 2018 to 2020-03-13, and calendar 2025
  (`demand_curve.EPISODES`). The fit uses **all days** of every counted episode up to the cutoff, pooled. With no counted episode the
  refit is **not fitted**, serves no estimate and carries no interval; there is no fallback to a fixed share.
- **Search.** The shares search a grid (`SHARE_GRID`: 0 to 30% of a group's assets in steps of 1%), by coordinate descent from
  three fixed starts, least squares, ties to the smaller share. The refit records whether the three starts agree. **Whether the
  shares are identified is not shown here** (Stages 2 to 3c found the kink was not stable; a common shift of all three shares
  is close to a shift of the curve's kink); step 5 measures it.
- **A refit with a negative slope is rejected** for that share vector, as the parent's `fit_level` rejects it.

**Refits and serving** are step 1's: the refit with cutoff `c` fits on days scored on or before `c` and serves from the second
business day after `c` (`SERVING_LAG`) to the day the next refit serves from. Filtered, never smoothed.

**The interval.** A stationary bootstrap of the **shares** over the refit's training days (step 1's block length 10, level 0.90
and seed constants, the parent's `metrics.stationary_bootstrap_indices`): each draw refits the shares and the curve, searching from the refit's own shares only (one start, not three); a day's
interval is the 5th and 95th percentiles of that day's `D_C` over the draws, widened to hold the point estimate. The number of
draws is a parameter; the tests use few and a real path (step 5) uses the protocol's.

## 4. Inputs, and how they are read

- **The panel days, ratio, spread and scarcity state** are step 1's (`h7_estimator.asof_days`): the parent's
  `InformationRule`, with its leakage and staleness checks, and the lockbox. Unchanged.
- **The group weeks** are read as they were public at each scored day's decision instant, `InformationRule.decision_instant`:
  the **latest** week whose `public_at` is on or before it. A week is public from the later of its H.8 release (16:15 New York)
  and its reserves' declared availability, both first prints; a week is never revised. `group_reserves.verify` is run on the
  tracked extract at load. Leakage (a week public after the instant) is `LookAheadError`; staleness (a later week was public)
  is `StaleReadError`, both raised by `check_reads`.
- **Break flags (Eleonora's Q18 ruling, #47).** An H.8 break week (`h8_break_week`) is a structural break: the group panels
  were restated, so the shares of one side are not the shares of the other. C does not refuse a break week and does not adjust
  across it. It **flags**: each refit lists the break weeks in its training sample, and each path lists the served days that read
  a break week (`break_days`). **Nothing may be scored across a break unadjusted** (step 5's rule); this step scores nothing.
- **No new input.** The group series is #43's, the H.8 totals are #26's, R and S are the parent's.
- **Pin.** The parent pin (8fd2cf8) already carries the `fit_level` tie fix (#747, merged in repo-market-model #749), which the
  directive required before candidate C is fitted; no pin bump is needed or made. C does not call `fit_level`: its curve is the
  repository's Stage 2 broken stick, whose ties go to the smaller kink.

## 5. What the code exposes

- `deployable`, `group_contributions`: `D_C` and each group's term, for a week and a share vector.
- `sample_c`: the scored days with their as-of group week, corridor position, ratio, state and the decision instant.
- `fit_shares`, `refit_c`: one refit's shares, curve, interval draws and record.
- `real_time_path`: every refit's real-time path over its served days, with the gap to the previous refit on each day both
  serve and a daily interval, through the same shape as step 1's `real_time_path`. **Computed, not scored.**
- `distribution`: aggregate deployable liquidity under the protocol's three declared alternatives (§8): as observed; all reserves
  held by large domestic banks; in proportion to group assets. Implemented and unit-tested; **no figures published** (step 4 uses it).
- `check_reads`, `check_no_future`: the leakage and staleness guards.

## 6. Out of scope, and what is not claimed

- No score, no AUROC, no stability or width figure; the path is run on synthetic and tracked-fixture inputs only in tests.
- No new input beyond #26's and #43's; no new package (the standard library and the parent).
- Candidate D (SLR headroom) is a later step.
- The group series is not published as a snapshot by this step (#43's marked question (ii) stays hers).
- **Marked question for Eleonora (not settled in code).** Her condition 3 of 15 October 2026 says nothing scored or registered
  uses the group series, and `tests/test_group_reserves.py` pins that no module but the builder imports it. Candidate C
  imports it to be built, and scores nothing. This step amends that test to allow exactly one reader, `h7_candidate_c.py`, and
  leaves the manifest's use note unchanged. If she reads condition 3 as also barring an unscored estimator from reading the
  series, the amendment is hers to refuse.
