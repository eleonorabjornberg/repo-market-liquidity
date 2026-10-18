# Research plan: H7 measurement and H10 attribution

**Decided by Eleonora, 12 October 2026** ([her decision, Q1–Q7](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/20#issuecomment-6131178133)),
on the plan drafted in [#20](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/20) by the liquidity
orchestrator, with the corrections and rulings posted below it. Committed by #28. The firm rules for measurement claims
are [`docs/decisions/measurement-protocol.md`](../decisions/measurement-protocol.md) v1, decided with this plan.

Order (Eleonora, 12 Oct): *"I want the same academic rigor applied to liquidity: a plan, firm rules and milestones and
goalposts."*

Scope, from her decision on eleonorabjornberg/repo-market-model#643: this repo owns **H7's estimator** (deployable
liquidity and the scarcity state, as a slow variable) and **H10** (attributing pressure episodes to drivers). The model
repo owns the scorer, the eleonorabjornberg/repo-market-model#640 protocol, the lockbox, the live record, H1–H6, H8, H9
and **H7's nested forecast test**. This repo reads the model repo at a pinned commit and panel digest, publishes
estimates as snapshots named by digest, and scores no forecast itself.

**This repo ingests its own inputs** (rulings of 12 Oct 2026 on #20, relayed by the model orchestrator: "The split is
supposed to save time, let liquidity do it." and "Delete duplicates, favor the model, let liquidity ingest its own
data."): the H.8 bank groups, the ON RRP offering rate, the SRF rate, the FOMC runoff caps, and SLR headroom once
Nicholas names a source. The model repo does not ingest them; if it ever needs one, it reads this repo's published
snapshot by digest. Where a module here duplicated the model repo's, it is deleted in favour of the model repo's
(`docs/decisions/deleted-duplicates.md`).

## The decisions (Eleonora, 12 October 2026)

- **Q1.** The plan (H7m, H7f's interface, H10) and `measurement-protocol.md` v1 are approved, with P1–P6 as proposed.
- **Q2 (a).** The parent's exit criterion stays a deliverable inside H7m: stability and sharpness are goalposts, and the
  distribution account is required for registration but decides nothing.
- **Q3.** H7f may start once H7m registers, without waiting for H7m's verdict.
- **Q4.** The model repo logs the registered H7m estimate (its prospective logging, eleonorabjornberg/repo-market-model#640
  §12.2, from this repo's snapshot pinned by digest). This repo runs no log of its own.
- **Q5.** This repo adopts eleonorabjornberg/repo-market-model#640's tiers: development to 2026-09-03; confirmation only
  after registration. They replace this repo's own development end of 2025-12-31. There is one lockbox, the model
  repo's: near-blind 2026-01-01 to 2026-09-03 (opened 2026-10-05), blind from 2026-09-04 (unopened). No day from
  2026-09-04 on may be used in development.
- **Q6.** H10 declares its window (baseline and length) in its own method record. Its episode source is the model
  repo's `onset.onset_flags`, with `pressure.onsets` at +5 bp as a cross-check.
- **Q7.** H10's method is a leave-episode-out regression with Shapley shares. A prospective episode is reported within
  10 business days of its onset.
- **Q8** (requests to the model repo) was settled by her ruling that this repo ingests those series itself. It is
  replaced by three directives, in this order: #25 L1 (the rates and caps as declared inputs at the new pin, with the
  snapshot convention), #26 L2 (the H.8 bank groups), #27 L3 (SLR headroom, after Nicholas answers question 16).

## Every hypothesis follows one sequence

The sequence is the one in the eleonorabjornberg/repo-market-model#638 manuals:
1. question;
2. groundwork;
3. development (never a verdict);
4. registration (her attested action);
5. prospective confirmation;
6. verdict: supported, killed, inconclusive or not testable.

The kill criterion and the milestones are set below, before any step runs. A step is never reopened without a log
entry saying why. A new directive names its hypothesis and step. Work that serves no step goes to the auditor's
`avenue` list.

## The research log

There is one log: `docs/research/log.md` in the model repo (eleonorabjornberg/repo-market-model#638). This repo writes
`[H7]` and `[H10]` entries there that link its own PRs. It keeps no log of its own. The format is the one on
[#20](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/20#issuecomment-6128124017), passed to
eleonorabjornberg/repo-market-model#638 as the shared one:

````
### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#NN
- Directive: eleonorabjornberg/repo-market-liquidity#MM
- Step: H7m development 1 (estimand and estimator)
- Tier: development | confirmation
- Pins: model <sha>, panel digest <digest>, snapshot <digest or "none">
- Tried: <one line>; variant count <n>
- Result: <headline with its interval, or "built, nothing scored">
- Against kill: <met / not met / not applicable, citing the rule's file:line>
- Next: <the step on either outcome>
````

- **The heading is machine-checked:** date (ET); one hypothesis tag from this plan (H7, H10); the step; the PR, written
  as `owner/repo#n`.
- **Figures are copied as published.** None is recomputed, and none appears without its interval.
- **A development result says so on the Tier line.** It is never written as a verdict.
- **This repo's check.** `scripts/check_log_entry.py` runs in `tests.yml` on `pull_request` and reads the PR body from
  the event payload. A PR that adds or changes `results/`, `docs/stages/`, a snapshot or a decision record must carry
  one fenced `research-log` block in the format, with a tag from {H7, H10} and the PR's own number.
- **The same check on `main`** (#100, finding #96). The `research-log-main` job in `tests.yml` runs on every push to
  `main` and checks each PR merged in that push again, from its body read over REST, at the format in force on `main`.
  A missing or invalid entry turns `main` red. A merged entry that was wrong is corrected without editing the PR, in
  `docs/research/log-corrections.md`, which the check reads instead of the body. The format has no tag for process work
  (its tags are the plan's hypotheses), so a process PR keeps the tag of the hypothesis it serves.
- **The model repo's half.** After merge, the entry is copied verbatim into the model repo's `log.md` by that repo's
  next log PR, and its `check_research_log.py` validates the heading there. Each day, this repo's orchestrator checks
  that every merged result PR here has its entry in the model repo's log, and raises any gap through the model
  orchestrator.

---

## H7. Reserve scarcity can be tracked

H7 asks two questions. Each has its own owner and rule.

| | **H7m, measurement (this repo)** | **H7f, forecast (model repo)** |
|---|---|---|
| Question | Is an as-of estimate of deployable liquidity stable across refits, with a usable interval, and does it carry information about stress beyond the reserves ratio and the scarcity state? | Does that estimate improve H5's primary score as an input, prospectively? |
| Rule | `docs/decisions/measurement-protocol.md` | eleonorabjornberg/repo-market-model#640 §9, nested test |
| This repo's part | All of it | Supplies the registered estimator as a snapshot named by digest. Scores nothing. |

### H7m

**Question.** On prospective days, does a registered as-of estimator of aggregate deployable liquidity meet three
goalposts, all set in advance?
- **Stable:** real-time estimates under consecutive refits agree.
- **Sharp:** its 90% interval is narrow enough to use.
- **Informative:** it separates stress days from other days better than the plain reserves ratio and the current
  scarcity state, by at least the MME.

**Target.**
- **Deployable liquidity on T:** reserves minus the desired buffer, in points of bank assets, aggregate. It is reported
  in dollars too, and by H.8 bank group where a candidate allows.
- **Read as:** the real-time estimate (the state a forecast for T reads), as of 16:00 on the panel day before T, through
  `repo_model.asof.InformationRule`. Filtered, never smoothed.
- **The scarcity state** is the parent's 0–3 state (`src/repo_model/scarcity.py:194`). H7m extends it and never builds
  a second one.
- **Stress days**, the validation events: the material-use event ($1bn or more), counted per operation on its operation
  date. It is defined in the model repo (`src/repo_model/fed_liquidity.py:13`, `:163`), from 2019-09-17.

**Benchmarks (the ones to beat).**
- **R:** the plain reserves ratio, `reserves_ratio` (`src/repo_model/scarcity.py:161`).
- **S:** the current scarcity state (`scarcity.py:194`).
- **R+S:** both together.

From step 1 on, R and S come from those two model-repo functions only. This repo's own reserves-over-assets
computations (`src/repo_liquidity/demand_curve.py:187-188`, `src/repo_liquidity/curve_feature.py:240-244`) are not used
for them.

Stage 6 *argued* both buffer candidates rank days as R does; R's own score is computed in step 5. Stage 6's statement
is prose (`docs/stages/stage-6.md:158-159`, `:165`): `scripts/stage6_ab.py:67-75` scores only the candidates. For A it
holds by construction, since a constant shift keeps the ranking; for B it is an inference. **So R and R+S are computed
in step 5,** under the protocol's §5 statistic, and are never cited from Stage 6. A candidate must beat R+S, not only R.

**Groundwork**
- G1. L0 merged: pin at current model main, the new aim, the `evaluation.md` amendment, Stage 5a retired, duplicates
  deleted.
- G2. `measurement-protocol.md` decided (attested).
- G3. eleonorabjornberg/repo-market-model#640 decided (attested). H7f and the shared bootstrap conventions follow it.
- G4. **The H.8 bank-group series** (cash and total assets for large domestic, small domestic and foreign-related
  institutions, as first prints): #26 merged. Candidate C and every candidate's distribution account need it. Whether
  H.8 group cash assets can stand in for group reserves is Nicholas's question 17 on #1.
- G5. **SLR headroom** (candidate D): #27 merged. It waits on Nicholas's question 16 on #1.
- G6. A power study for the information goalpost on development data. How many confirmation days, and how many stress
  events, detect the MME? Runs before registration.

**Development steps (never a verdict)**
1. **Estimand and as-of estimator.** This is the recreated model eleonorabjornberg/repo-market-model#644. Define
   deployable liquidity and the distance to the kink as one slow variable, with a stated reason why it differs from R.
   It gets a leakage test raising `LookAheadError`, with one recorded mutation. No score.
2. **Candidate C, bank groups** (`docs/stages/stage-6.md:61-68`), once G4 is in.
3. **Candidate D, SLR headroom** (`stage-6.md:70-79`), once G5 is in. It is otherwise recorded as not buildable, with
   the reason.
4. **The distribution account** for every candidate still in play, A included. Its eligibility has been pending this
   since Stage 6 (`stage-6.md:146-147`).
5. **Development score of the three goalposts** for each candidate, and for R and R+S, on development days, under the
   protocol's definitions. This step is reported, never a verdict.
6. **Choice of the primary candidate** by the rule fixed in the protocol (§7), with the development variant count. Up
   to two secondaries.

**Registration.** Her attested action. It freezes:
- the primary candidate, by code commit, configuration and inputs, plus up to two secondaries;
- the goalposts, the MME and the checkpoints;
- the seed;
- the variant count.

The distribution account is required for registration but decides nothing (Q2 (a)).

**Prospective confirmation.**
- **Each day:** the frozen estimator's daily estimate and interval are logged before the day's outcome is public.
- **Each refit:** every scheduled refit is logged, with its real-time path.
- **Where:** one prospective log, owned by the model repo (S3; Q4). This repo runs no log of its own.
- **When judged:** at the protocol's checkpoints.

**Verdict.** At a checkpoint:
- **Supported:** all three goalposts hold.
- **Killed:** a goalpost fails by the futility rule, or a stability breach occurs.
- **Inconclusive (continue):** neither holds yet.
- **Not testable as stated:** no candidate meets the stability and sharpness goalposts in development, so nothing can
  be registered.

**Kill criterion (set now).** Any one of the following:
- a prospective stability breach;
- a prospective median interval width over the bar;
- at a checkpoint, the upper bound of the information gain against R+S falls below the MME.

In development, "no eligible candidate after steps 2–5" ends H7m as not testable as stated. Effort then goes to H7f
with R+S alone.

**Milestones (done when)**
- M0. L0 merged (G1).
- M1. `measurement-protocol.md` merged (G2).
- M2. Step 1 merged: estimand, estimator, leakage test with its mutation.
- M3. H.8 group series available here (#26).
- M4. C scored on development.
- M5. D scored, or recorded as not buildable.
- M6. A distribution account for every candidate in play.
- M7. Power study published (G6).
- M8. Primary candidate chosen and registered (attested).
- M9–M11. Checkpoints, each with a verdict or "continue".
- M12. The registered estimator is published as a snapshot named by digest, for H7f.

**Progress markers**
- Current step (1–6).
- Candidates scored, eligible or not buildable.
- Worst real-time gap and median interval width (points of bank assets).
- Development information gain against R+S.
- Variant count.
- Prospective days, refits and stress events logged.

**Where H7m stands (12 October 2026)**
- **Current step:** groundwork. Step 1 is #22, which waits only on eleonorabjornberg/repo-market-model#626
  (eleonorabjornberg/repo-market-model#640 is closed). The inputs it needs first are #25, then #26 and #27.
- **Term repos outstanding** are not in the model repo's `fed_liquidity`; they are filed there as
  eleonorabjornberg/repo-market-model#659. Until it merges, no step here uses take-up as outstanding amounts. H7m's
  stress days do not depend on it, because the material-use events are pinned.
- **Done:** M0 (L0, #21, merged as PR #29).
- **Done when #28 merges:** M1.
- **Open:** M2–M12.

### H7f (model repo, stated here for completeness)

Owned and scored there under eleonorabjornberg/repo-market-model#640 §9: the H5 primary candidate with and without the
registered H7m estimate. Kill (eleonorabjornberg/repo-market-model#46): no gain beyond the current scarcity state.

This repo's only part is M12. H7f does not have to wait for H7m's verdict, only for its registration (Q3).

**Where H7f stands (12 October 2026):** waiting on H7m's registration (M8) and the published estimator (M12). Open.

---

## H10. Pressure episodes can be attributed to drivers (descriptive)

**Question.** For each pressure episode in the model repo's onset list, what share of the rise in SOFR − IORB is
accounted for by each of five components? The method is declared and frozen before it is applied.
- **The components:** Treasury settlement, TGA, reserves, quarter-end, and a residual.
- **Is the residual small enough** for the drivers to be named?

**Target.** The rise in SOFR − IORB in bp, first published, over each episode's window, against its pre-onset baseline.

**The episode list is the model repo's, cited and never redefined** (Q6).
- **The episode source:** `onset.onset_flags`, the onset group's module (`src/repo_model/onset.py:153`), with
  `ONSET_THRESHOLD_BP` = 5 (`:53`) and `ONSET_CALM_DAYS` = 5 (`:55`).
- **The cross-check:** `pressure.onsets` at `tau` = +5 bp (`src/repo_model/pressure.py:78`, `:286`), which must agree.
  There an onset is a scored day above `tau`, with no event on the `ONSET_QUIET_DAYS` = 5 panel days before it.
- **The threshold:** whole basis points, strictly greater (`src/repo_model/data.py:63`).
- **What is not defined:** an onset fixes the episode's start only, and no episode-end rule exists in the model repo.
  The window (the baseline days before, and the length after) is part of H10's declared method (Q6).

All lines are at 6c09789.

**Benchmark (the one to beat).** The same method with reserves as the only driver (R alone). Two figures are reported
beside it:
- **the drivers' explained share above R alone;**
- **a placebo:** the same decomposition on matched non-episode windows of the same length and day type. It tells
  whether the drivers explain episodes more than they explain ordinary weeks.

**Groundwork**
- G1. L0 merged.
- G2. The settlement, TGA, reserves and calendar columns, read at the pin through the parent's panel. All exist there.
- G3. The method record decided (step 1).

**Development steps**
1. **Declare the method** as a decision record for her, before anything is applied. The record fixes:
   - the window;
   - the decomposition;
   - the fitting sample;
   - the outcome rule.

   The method (Q7): a regression of the spread change on driver changes. It is fitted with each episode left out (so
   that no episode explains itself), with Shapley shares for the components and an interval from the stationary
   bootstrap. It is frozen before it is applied.
2. **Apply it** to every development onset, once, at a pin.
3. **Publish the table:** one row per episode, its shares with intervals, the residual share, the reserves-only
   benchmark and the placebo.

**Registration.** The frozen method, by commit and digest, is her attested action. After it, the method does not
change. A changed method is a new declaration with a new date.

**Prospective confirmation.** Each new onset after registration is attributed with the frozen fit and reported within
10 business days of its onset (Q7). This checks out of sample whether the named drivers still carry the episodes. It is
reported, never a forecast claim.

**Verdict.** None in eleonorabjornberg/repo-market-model#640's sense (§9: descriptive). The outcome rule is set now:
- **"Drivers named":** the residual share is under 50% in more than half the development episodes.
- **"Residual dominates":** otherwise. That is eleonorabjornberg/repo-market-model#46's kill. H5–H9 then get no driver
  list from H10.
- **Prospective episodes:** reported against that rule, labelled as prospective.

**Milestones**
- M0. L0 merged.
- M1. Method record merged (attested).
- M2. Development table published.
- M3. First prospective episode attributed.

**Progress markers**
- Episodes covered.
- Median residual share with its interval.
- Explained share above reserves-only.
- Placebo gap.
- Prospective episodes attributed.

**Where H10 stands (12 October 2026)**
- **Current step:** 1, declare the method (#23). Its only prerequisite, L0, has merged.
- **Done:** M0 (L0, #21, merged as PR #29).
- **Open:** M1–M3.

---

## The parent's exit criterion

The parent's Phase 3 exit criterion is "stable posterior intervals for aggregate effective liquidity, with a clear
account of their sensitivity to the bank-level distribution of reserves" (quoted in this repo's `PLAN.md:12-14`, at
a1685ac). Eleonora made it Phase 3's verdict on 7 Oct (`docs/decisions/evaluation.md:88-112`, at a1685ac).

**It stays a deliverable inside H7m (Q2 (a)).** H7m's stability and sharpness goalposts cover its first half, and step 4
(the distribution account) its second. The distribution account is required for registration but decides nothing.

## Prior work (development evidence only, never a verdict)

All lines are at a1685ac.

| Stage | Result | Where |
|---|---|---|
| 2, the demand curve | The bend was not shown stable under the decided rule. A post-hoc test showed a 2025 upward shift; the two bends mark different features. | `docs/decisions/stage-2-bend.md:7-12` (rule), `:22` (post-hoc); `docs/HANDOFF.md:26-32` |
| 3, the latent buffer | Not shown. Not identified (full-window and walk-forward fits settle apart); ON RRP dominates; worst refit gap about 4 points against 0.5. | `docs/stages/stage-3.md:34`; `docs/HANDOFF.md:36-62` |
| 3b, the buffer on a fixed curve | Benchmark shown (+3.3 points full-window, [2.8, 3.7]); stability not shown. | `docs/HANDOFF.md:78-114`; `docs/stages/stage-3b.md:76` |
| 3c, the real-time buffer | Not shown: it moved by up to 4.2 points between refits. | `PLAN.md:144-146`; `docs/stages/stage-4.md:8` |
| 4, the curve as a gbm feature | Not shown: +0.0038 bp CRPS, 90% [−0.0070, +0.0146]. | `docs/stages/stage-4.md:208-232` |
| 5a, a daily log | Built; the schedule was never on. Retired (S3). | `docs/stages/stage-5a.md:21-22`; `.github/workflows/live-log.yml:15-19` |
| 6, candidates A and B | A: stable, 2.7-point median width, eligibility pending the distribution account. B: not eligible (4.0-point gap). Stage 6 argued both rank days as R does; R's own score was never computed (step 5 computes it). | `docs/stages/stage-6.md:86-94` (eligibility), `:100-107` (choice rule), `:142-149` (table), `:167-173` (reading) |

**What the prior work says about the design:**
- **Re-estimation fails stability.** Any model that learns the 2025 shift by re-estimation fails a 0.5-point bar
  (`stage-6.md:168-170`).
- **Only C and D can tell a buffer from R.** They are the candidates whose buffers move with observed data
  (`stage-6.md:171-173`).

That is why the information goalpost is set against R+S, and why C and D come before any further work on A or B.
