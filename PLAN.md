# Plan: Phase 3, latent reserves and deployable liquidity

Moved from [repo-market-model#233](https://github.com/eleonorabjornberg/repo-market-model/issues/233), where Eleonora's
rulings of 5 October 2026 were made. The parent's `PLAN.md` (Phase 3) is the origin of the goal and the exit criterion.
Every statement about the parent below names a file and symbol at the pinned commit (`PARENT_COMMIT`).

## Goal

Estimate **deployable liquidity**: observed reserves minus the buffer banks want to keep, a quantity no one reports,
inferred from what the market reveals (the spread, SOFR dispersion, volume, ON RRP and facility usage, payment timing).

**Exit criterion (parent `PLAN.md`):** stable posterior intervals for aggregate effective liquidity, with a clear
account of their sensitivity to the bank-level distribution of reserves, which is not observed. Whether it is met is
Eleonora's verdict.

## How the work runs (Eleonora, 5 October 2026)

- **Staged, one stage at a time.** Each stage is its own piece of work, written only after the previous stage has been
  reviewed. No stage is started ahead of that review.
- **Every stage ends with Eleonora.** Its pull request carries `needs-eleonora`; she reviews and merges it, and decides
  whether the next stage goes ahead, changes, or stops.
- **Each stage states up front what it must show** for the next one to be worth doing, and its write-up says plainly
  whether it did.
- **Separate from the final test.** The parent's "no new model variants" rule covers its final test only. Nothing here
  changes the parent's published model, pre-registration, live record or records, and no Phase 3 work changes the
  parent at all.
- **Evidence and scoring** are fixed by [`docs/decisions/evaluation.md`](docs/decisions/evaluation.md): development
  evidence is the walk-forward to 2025-12-31; confirmatory evidence is Phase 3's own frozen daily log from the day the
  Stage 3 model is frozen; the primary metric is CRPS at h = 1.

## What the parent provides, and what it does not

Read at the pin, these facts shape the stages below.

- **Built in the published panel:** reserves (`reserve_balances`), TGA (`tga`), Treasury settlements with the Fed's
  SOMA amount accepted at auction (`treasury_settlement_soma`; this is not SOMA holdings), SOFR with its 25th and 75th
  percentiles and volume, TGCR, BGCR, IORB, and the calendar columns (`src/repo_model/data.py`,
  `metadata/funding_panel_manifest.json`).
- **ON RRP is refused in the published panel.** FRED's latest vintage cannot be priced point-in-time. The usable
  source is the NY Fed's operation results, declared and switched off (`contract.ON_RRP_OPERATION_RESULTS_FIELDS`,
  source `nyfed_on_rrp`).
- **H.8 bank assets** are declared as first prints and switched off (`contract.BANK_TOTAL_ASSETS_FIELDS`, source
  `frb_h8`, 12 calendar days at 16:15). They cover all commercial banks only: **there is no large-bank versus
  small-bank split** anywhere in the parent.
- **Standing repo facility usage** is fetched, parsed and switched off (`contract.SRF_OPERATION_RESULTS_FIELDS`, source
  `nyfed_srf`). The facility exists only from 2021-07-29 (`ingest.SRF_INCEPTION`).
- **The Fed's Treasury holdings (`TREAST`) are fetchable but not priceable.** The series is in
  `ingest.FRED_MACRO_SERIES`, but `fred_macro_latest_vintage` gives it no `field_release_lags` entry and no revision
  evidence, so a column built on it is refused.
- **The announced runoff caps exist nowhere in the parent.**
- **The reserve-scarcity indicator** (`src/repo_model/scarcity.py`) scores 0 to 3 from reserves over bank assets against
  the satiation band (`SATIATION_BAND`, 12–13%) and ON RRP against \$100bn (`ON_RRP_BUFFER_BN`). Phase 3 starts from it
  and extends it; it does not build a second one.
- **The lockbox refuses every scored day from 2026-01-01** (`metadata/lockbox.json`, `lockbox.require_unlocked`) until
  Eleonora opens the tier for the final test.
- **The parent's command line cannot select an outside model.** Phase 3 scores by calling the parent's functions
  directly (`baseline.paired_model_comparison`, `baseline.rolling_persistence_backtest`,
  `baseline.rolling_exceedance_backtest`), as the parent's own `compare` command does. The parent's records stamp the
  parent's commit, so every Phase 3 record adds its own provenance.

## Repo-liquidity indicators (Eleonora, 6 October 2026)

Deployable liquidity stays the target. The indicators below are what Stage 1 may carry and what the Stage 3 model may
observe. Which of them Stage 1 carries, and what each means, is Nicholas's call. Status is read at the pin
(`metadata/sources.json`).

**1. Pricing**

| Indicator | Status at the pin | Proposed |
|---|---|---|
| SOFR, BGCR, TGCR, with their percentiles and volumes | Declared (`nyfed_sofr`, `nyfed_bgcr`, `nyfed_tgcr`; business day + 1 at 15:00). The panel builds SOFR, its 25th and 75th percentiles and volume, TGCR and BGCR | Cross-venue spreads (SOFR − TGCR, BGCR − TGCR) and tail widths |
| General collateral versus specials | No specials rate is public. SOFR's delivery-versus-payment (DVP) part drops the low-rate tail as specials, so OFR's DVP rate minus BGCR is a partial proxy, declared and off (`ofr_stfm_repo`, `dvp_segment`, from 2020-09-09); SOFR's 1st percentile is a lower-tail proxy | These proxies, plus two public collateral-scarcity measures: the NY Fed's SOMA securities-lending results and FR 2004 settlement fails |
| Haircuts | Not in the parent; no daily public source is known | Check OFR's public releases from its bilateral repo collection; otherwise recorded as not observable |

**2. Segment distribution**

| Indicator | Status at the pin | Proposed |
|---|---|---|
| Tri-party, GCF and cleared DVP activity | Derivable from the declared TGCR, BGCR and SOFR volumes and OFR's DVP volume (`REPO-DVP_TV_OO-F`, declared, unused) | Segment volumes and shares: what mandatory repo clearing will move |
| Non-centrally cleared bilateral repo | Not declared | As for haircuts |

**3. Dealer intermediation and cash supply and demand**

| Indicator | Status at the pin | Proposed |
|---|---|---|
| Dealer balance-sheet capacity | `nyfed_fr2004` declares dealer positions only (`dealer_treasury_position` is built) | FR 2004 financing (repo and reverse repo by segment) and fails series |
| Quarter-end tightening | Built: `quarter_end`, `days_to_month_end`, and the quarter-end window split | Reused |
| Money-fund cash supply | `sec_nmfp` declares `mmf_repo_holdings` and `mmf_on_rrp`, refused in the published panel as latest vintage | Dated by filing date, so they can be priced |
| Hedge-fund demand (the basis trade) | Absent | The CFTC's Traders in Financial Futures report: leveraged funds' Treasury futures positions, weekly, Tuesday's positions released on Friday |
| GSE, foreign-bank and bank lenders | Absent | No new source: the GSE mid-month cycle is calendar, and foreign-bank quarter-end behaviour shows in the quarter-end split |

**4. Central-bank backstops**

| Indicator | Status at the pin | Proposed |
|---|---|---|
| Standing repo facility usage (the ceiling) | `nyfed_srf`, off, from 2021-07-29 | Stage 1 |
| ON RRP usage (the floor) | `nyfed_on_rrp`, off | Stage 1 |

**A design rule for Stage 3:** collateral scarcity is kept apart from cash scarcity. A security on special signals
scarce collateral, not scarce cash, so its indicators are observed separately and never read as deployable liquidity.

## Reform dates (Eleonora, 6 October 2026)

The desired buffer is partly regulatory (the parent's `PLAN.md` lists "regulatory liquidity needs"). The parent tracks
no reform, and its regimes are calendar groups, not reform dates. The confirmatory window crosses three reforms, one
of them between the two scoring dates.
[`docs/decisions/reform-dates.md`](docs/decisions/reform-dates.md) lists the dates with their sources as a
declared input, fixed before anything is scored. Uses:

- **Stage 2:** also split the curve at the 2021 and 2023 reforms, and report whether the bend moves at a reform date.
- **Stage 3:** reforms may enter as declared shifts in the buffer; decided when Stage 3 is designed.
- **Evaluation:** the confirmatory result is also reported before and after the clearing mandates, reported only and
  never deciding the verdict (amendment in [`docs/decisions/evaluation.md`](docs/decisions/evaluation.md)).

## Stages

### Stage 1: data, as of 4 pm

Stage 1 is built in two parts (Eleonora, 6 October 2026):

- **Stage 1a, the inputs already ruled on:** ON RRP, H.8 bank assets, standing repo facility usage and its rate, the
  weekly change in the Fed's Treasury holdings (H.4.1 first prints), and the announced runoff caps. Built by
  `scripts/build_panel.py` into a measurement panel whose manifest is `metadata/phase3_panel_manifest.json`.
- **Stage 1b, the indicator families (questions 7 to 10):** written once Nicholas has answered.

**Nicholas answered questions 1 to 13 on 6 October 2026** (`docs/decisions/data-meaning.md`). Two more pieces follow,
each planned before it is built (Eleonora, 6 October 2026):

- **Stage 1a correction** (`docs/stages/stage-1a-correction.md`): the realized weekly MBS change beside the Treasury
  change; the Fed's 2019 to 2021 repo operations as take-up from a different facility; a structural zero before
  2019-09-17; and the facility's material-use event ($1bn or more).
- **Stage 1b, first wave** (`docs/stages/stage-1b.md`): pricing and the Fed's facilities, as Nicholas set out.

**After Stage 3b (Eleonora, 6 October 2026):**

1. Stage 3b closes as not shown (benchmark shown, stability not shown), with no further amendment. Its full-window
   shift is kept as a descriptive finding, with its three caveats (`docs/stages/stage-3b.md`).
2. Next, in order: the Stage 1a correction, then Stage 1b's first wave, then Stage 3c.
3. **Stage 3c,** written before any fit, judges stability on each refit's real-time buffer (the state a forecast reads,
   day T − 2), not on revisions to earlier history. That change of must-show is made after Stage 3b, and the directive
   says so. It may use the new inputs (the MBS flow, the material-use event). It is judged once.
4. **If Stage 3c fails,** the latent buffer is set aside and Stage 2's curve becomes the Stage 4 model (option 5 of
   `docs/stages/stage-3-diagnosis.md`).
   **Stage 3c's result (6 October 2026, #12 in review):** not shown. The real-time buffer moved by up to 4.2 points
   between refits, in four refit blocks: April–May 2020, November–December 2020, April–May 2021 and December
   2022–January 2023. Under point 4, Stage 2's curve becomes the Stage 4 model once Eleonora merges.
5. Nicholas is asked whether the 2019 to 2021 term repos count as take-up (issue #1, question 14). The Stage 1a
   correction waits on his answer for that column only.

**Nicholas owns the MBS scenario** (the balance sheet's MBS runoff, reinvestment and the active-sales tail), as he asked
and Eleonora agreed on 6 October 2026.


**Goal:** a Phase 3 measurement panel in which every input is read only as it was public at the decision instant,
from 2018-04-03.

| Input | Where it comes from | Work |
|---|---|---|
| Reserves, TGA, settlements, SOFR percentiles and volume, TGCR, BGCR, IORB, calendar | Parent panel, built | None: read through the pin |
| ON RRP | Parent `nyfed_on_rrp`, off | Switched on in Phase 3's declaration, as the parent's `scarcity.measurement_declaration()` does |
| H.8 bank assets (first prints) | Parent `frb_h8`, off | Switched on, as above |
| Standing repo facility usage | Parent `nyfed_srf`, off | Switched on; the meaning of the days before 2021-07-29 is Nicholas's |
| Fed Treasury holdings and their weekly change (the QE/QT pace) | `TREAST`, not priceable | Revision evidence from ALFRED vintages, or H.4.1 release dating |
| Announced runoff caps | Absent | A new scheduled input from FOMC statements, with evidence per announcement, as the parent's `fed_iorb_announcements` |
| A bank-size split (for Stage 4) | Absent | Nicholas to name a source |

- **New declarations and parsers live here** (D1, [`docs/decisions/input-declarations.md`](docs/decisions/input-declarations.md)):
  a registry overlay validated by the parent's own validators (`contract.validate_release_lag`,
  `asof.validate_scheduled_availability`, `registry.check_availability_provenance`), with Phase 3's parsers and
  tracked snapshots. The parent is not changed.
- **Each new input** gets an availability declaration, a leakage test (`LookAheadError`) and a staleness test
  (`StaleReadError`), each with one recorded mutation that kills it.
- **The measurement panel** is built by the parent's build over the parent's fixture snapshots plus Phase 3's own. Its
  manifest (digest, columns, holes, refusals) is generated output, never hand-edited, and a test rebuilds it to its
  digest.
- **Fetching** runs on the Mac, which has the network. Snapshots are committed as fixtures, so CI rebuilds with none.
- *Must show:* every input passes the parent's guards and each new guard's mutation is killed; coverage from
  2018-04-03 to 2025-12-31 with every hole and refusal listed, and late-starting inputs shown with the treatment
  Nicholas chose.
- *Waits on:* Nicholas's answers (issue #1). No scores, no figures.

### Stage 2: the reserve demand curve (descriptive)

**Result (6 October 2026):** under the decided rule the bend is **not shown** stable. A diagnosis found the outcome
mixed in administered-rate floors; a revised test written after it (post-hoc, amendment in
`docs/decisions/stage-2-bend.md`) measures SOFR from the floor in two scarce episodes and is shown, but its two bends
mark different features of the curve. The like-for-like comparison, at the same reserves ratio, finds SOFR higher in
the corridor in 2025 than in 2018 to March 2020: the demand curve shifted up. All in `results/stage2/`. Stage 3
waits on Eleonora's reading.

**Goal:** a transparent first estimate of the desired buffer: where the spread starts to respond as reserves become
scarce.

- **What is described:** the spread SOFR − IORB, and its upper tail, against reserves over bank assets
  (`scarcity.reserves_ratio`), read as of 4 pm; split by the parent's regimes (`metadata/evaluation_splits.json`) and by
  ON RRP buffer present or gone.
- **How:** a binned curve, and a broken-stick fit whose kink is the bend, with a 90% stationary-bootstrap interval
  (`metrics.stationary_bootstrap_interval`). Both are standard-library only, so Stage 2 needs no package decision.
- **Compared with** the parent's satiation band and its sensitivity variants (`scarcity.SENSITIVITY_VARIANTS`).
- **Window:** 2018-04-03 to 2025-12-31 only. 2026 is held by the parent's lockbox, and describing it before the final
  test would spend the near-blind tier.
- *Must show* (D2, [`docs/decisions/stage-2-bend.md`](docs/decisions/stage-2-bend.md)): every regime with enough days on
  the scarce side has a 90% interval for the bend overlapping the pooled interval, and the pooled interval is narrower
  than the 11–14% range of the parent's sensitivity variants. If it is not shown, Stage 3 is reconsidered before it is
  designed.

### Stage 3: the latent model

**Not designed until Stage 2 has been reviewed.** Its expected form:

- **State:** deployable liquidity, reserves minus a latent desired buffer. Known flows move reserves (TGA changes,
  settlement drains, QT runoff, ON RRP shifts); the buffer moves slowly.
- **Observed through:** the spread via the Stage 2 curve, SOFR dispersion, volume, ON RRP take-up and facility take-up.
- **Estimated by** a Kalman filter if the Stage 2 curve allows a linear-Gaussian form, otherwise a non-linear filter.
- **Two leakage rules for filters:** a forecast uses filtered estimates only, never smoothed ones; and parameters are
  fitted on the training prefix at each refit (`asof.refit_blocks`).
- **Package** (D3, [`docs/decisions/dependencies.md`](docs/decisions/dependencies.md)): statsmodels 0.14.6 is approved for
  the state-space model and its estimation; it enters `pyproject.toml`, pinned with its own dependencies, when Stage 3
  first uses it.
- *Must show:* filtered intervals stable across refits, and a stated sensitivity of the state to the form of the
  Stage 2 curve.
- **The freeze:** at the end of Stage 3 the model is frozen by a declaration checksum, as the parent freezes its final
  test, and the daily frozen log starts (Stage 5).

### Stage 4: evaluation

**Planned 7 October 2026: [`docs/stages/stage-4.md`](docs/stages/stage-4.md), in review.** Stage 3c was not shown, so
Stage 2's curve is the Stage 4 model. Eleonora ruled on 7 October 2026, taking the recommended option each time:
- the curve enters as one curve-implied feature of the published gbm;
- the curve is refit as of each refit;
- one feature only, and the ml extra (numpy 2.4.6, scikit-learn 1.9.1) is approved;
- the declaration is frozen and Stage 5a's log starts after the development run, whatever its verdict.

On review of the plan (7 October 2026) she added:
- the curve's slope is constrained to b ≥ 0;
- a curve that fails at any refit stops the run for diagnosis and a remedy she rules on before anything is scored,
  with no silent fallback;
- Stage 5a logs both arms' forecasts each day.

The amendment to `evaluation.md` that names the replacement for the latent state is drafted in the same pull request.
**Stage 4's result (7 October 2026, in review): not shown.** Model A reproduced the published record exactly, and the curve-implied spread gave a mean CRPS gain of +0.0038 bp, 90% [−0.0070, +0.0146] (`docs/stages/stage-4.md`, Result). The freeze and Stage 5a follow Eleonora's review.

Where the text below says "latent state", the plan and that amendment decide once merged. The text below is the
original design, kept for the record.

Under [`docs/decisions/evaluation.md`](docs/decisions/evaluation.md):

- **Primary:** the parent's published distribution (`ml.fit_gradient_boosted_quantiles` with
  `recalibration.NestedFoldPid`, its nine features, minimum history 61, refit every 21, decision 4 pm) with and without
  the filtered latent state as one extra regressor; `baseline.paired_model_comparison` with CRPS at h = 1, to
  2025-12-31; 90% stationary-bootstrap interval, 2000 replications, block length 2; as-of persistence beside it; the
  verdict as the parent's `crps_verdict` (`scripts/final_test_preregistration.py`); split by regime and day type
  (`baseline.add_comparison_splits`).
- **Secondary:** Brier on P(spread > +5 bp) at h = 1, with and without the state, against calendar climatology and the
  persistence-logistic model. Not part of the pass rule.
- **Also reported:** the state's stability across refits, and the reserve-concentration sensitivity if a bank-size
  source is named.
- **Known design point:** the latent state is a model output, not a panel column. The candidate is a wrapper fitter
  that fits the filter on the training frame, adds the filtered state to each row, and calls the published fitter. Its
  declared features include every input the filter reads, so the parent's check that a fitter stays inside its
  declaration (`baseline._check_fitter_stayed_inside`) covers them.

### Stage 6: a deployable-liquidity model (planned 7 October 2026)

[`docs/stages/stage-6.md`](docs/stages/stage-6.md), in review: four candidates (the curve's bend, the latent buffer
identified differently, bank groups, SLR headroom), judged by the parent's exit criterion, with the best chosen by a
rule fixed before any fit. The evaluation amendment that makes the exit criterion Phase 3's verdict is drafted with it.

### Stage 5: confirmatory log and monitoring

- **Stage 5a's directive** is [`docs/stages/stage-5a.md`](docs/stages/stage-5a.md), and the freeze it starts from is
  [`docs/decisions/stage-4-freeze.md`](docs/decisions/stage-4-freeze.md) (both drafted 7 October 2026, in review).
- **The frozen daily log,** from the Stage 4 freeze (Stage 5a, its own directive): a GitHub Actions workflow here, after 4 pm New York time on each
  business day, appending to a protected branch, reusing the parent's live-record helpers (`scripts/live_record.py`:
  `extend_panel`, `require_reads_on_real_rows`, `is_decision_day`, `write_record`) with its own record schema. Scored
  on the dates in `evaluation.md`.
- **Monitoring:** the filtered state beside the parent's live record, published from here, never written into the
  parent's frozen daily file.

## Across all stages

- **Provenance.** Every Phase 3 record carries this repository's commit and whether its tree was modified, the parent
  pin, the parent panel digest and the Phase 3 panel digest.
- **Publishing.** A draft rule for this repository is in
  [`docs/decisions/publish-rule.md`](docs/decisions/publish-rule.md) (D4).
- **Reproducibility.** Figures of record are computed on Python 3.11 with the parent's pinned numpy and scikit-learn.
  Development may run on the Mac; a published figure is reproduced in CI before it is published.

## Decisions (Eleonora, 6 October 2026)

- **D1.** New inputs are declared and parsed here, as an overlay checked by the parent's validators:
  [`docs/decisions/input-declarations.md`](docs/decisions/input-declarations.md).
- **D2.** Stage 2's bar is the proposed rule: [`docs/decisions/stage-2-bend.md`](docs/decisions/stage-2-bend.md).
- **D3.** statsmodels is approved, pinned at 0.14.6: [`docs/decisions/dependencies.md`](docs/decisions/dependencies.md).
- **D4.** The publish rule, and a record is published only when Eleonora says so:
  [`docs/decisions/publish-rule.md`](docs/decisions/publish-rule.md).
- **D5.** The reform dates are a declared input ([`docs/decisions/reform-dates.md`](docs/decisions/reform-dates.md)),
  and the confirmatory result is also reported split at the clearing mandates (amendment to `evaluation.md`).

Each is in force once its record merges.

## Open questions for Nicholas Beroud (data meaning, issue #1)

Questions 1 to 3 have a preliminary ruling by Eleonora, pending Nicholas:
[`docs/decisions/data-meaning-preliminary.md`](docs/decisions/data-meaning-preliminary.md).

Under the parent's `PLAN.md`, the choice of data and its meaning rests with Nicholas. Before Stage 1 is written:

1. Which QE/QT measure: the level of the Fed's holdings, its weekly change, the announced runoff caps, or a combination?
2. Are standing repo facility usage and H.8 bank assets the right proxies for the facility outside option and bank
   balance-sheet size?
3. Do the announced runoff caps count as a scheduled input (known in advance, like a settlement), and from their
   announcement date or their effective date?
4. ON RRP from the NY Fed's operation results, as the parent's measurement runs use?
5. Facility usage before 2021-07-29, when the facility did not exist: a structural zero, or missing?
6. A bank-size split for the concentration sensitivity, since H.8 total assets has none?
7. Which of the four indicator families above should Stage 1 carry?
8. Are OFR's DVP rate minus BGCR, and SOFR's 1st percentile, acceptable proxies for specials?
9. Are the CFTC's leveraged-fund Treasury futures positions the right proxy for basis-trade demand?
10. Is there a public source for haircuts?
11. Which of the reforms in the draft reform-dates record are material to the buffer, and does mandatory repo clearing
    change what SOFR volume and dispersion measure?

His evidence pack (parent branch `advisor/evidence-pack`, and his comment on parent PR #219) points to the ON RRP buffer
and a QT restart as the levers.
