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

## Stages

### Stage 1: data, as of 4 pm

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

- **Where the new declarations and parsers live is Eleonora's decision (D1).** Proposed: here, as a registry overlay
  validated by the parent's own validators (`contract.validate_release_lag`, `asof.validate_scheduled_availability`,
  `registry.check_availability_provenance`), with Phase 3's parsers and tracked snapshots. The alternative is the
  parent, switched off; but under the parent's publish rule any change to its `src/`, `metadata/` or
  `tests/fixtures/snapshots/` makes records scored before it unpublishable, so a change during the final test would
  stale that test's records.
- **Each new input** gets an availability declaration, a leakage test (`LookAheadError`) and a staleness test
  (`StaleReadError`), each with one recorded mutation that kills it.
- **The measurement panel** is built by the parent's build over the parent's fixture snapshots plus Phase 3's own. Its
  manifest (digest, columns, holes, refusals) is generated output, never hand-edited, and a test rebuilds it to its
  digest.
- **Fetching** runs on the Mac, which has the network. Snapshots are committed as fixtures, so CI rebuilds with none.
- *Must show:* every input passes the parent's guards and each new guard's mutation is killed; coverage from
  2018-04-03 to 2025-12-31 with every hole and refusal listed, and late-starting inputs shown with the treatment
  Nicholas chose.
- *Waits on:* Nicholas's answers (issue #1) and D1. No scores, no figures.

### Stage 2: the reserve demand curve (descriptive)

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
- *Must show:* a bend whose location is stable enough across regimes to be worth modelling. The threshold is
  Eleonora's (D2). Proposed: every regime with enough days on the scarce side has a 90% kink interval overlapping the
  pooled interval, and the pooled interval is narrower than the 11–14% range of the parent's sensitivity variants.
  If it is not shown, Stage 3 is reconsidered before it is designed.

### Stage 3: the latent model

**Not designed until Stage 2 has been reviewed.** Its expected form:

- **State:** deployable liquidity, reserves minus a latent desired buffer. Known flows move reserves (TGA changes,
  settlement drains, QT runoff, ON RRP shifts); the buffer moves slowly.
- **Observed through:** the spread via the Stage 2 curve, SOFR dispersion, volume, ON RRP take-up and facility take-up.
- **Estimated by** a Kalman filter if the Stage 2 curve allows a linear-Gaussian form, otherwise a non-linear filter.
- **Two leakage rules for filters:** a forecast uses filtered estimates only, never smoothed ones; and parameters are
  fitted on the training prefix at each refit (`asof.refit_blocks`).
- **Packages are Eleonora's decision (D3).** Proposed: start with a filter written on numpy, which the parent's `ml`
  extra already pins, so no new package is needed; a state-space or probabilistic-programming library only if the
  design requires it, recorded in `docs/decisions/dependencies.md` first.
- *Must show:* filtered intervals stable across refits, and a stated sensitivity of the state to the form of the
  Stage 2 curve.
- **The freeze:** at the end of Stage 3 the model is frozen by a declaration checksum, as the parent freezes its final
  test, and the daily frozen log starts (Stage 5).

### Stage 4: evaluation

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

### Stage 5: confirmatory log and monitoring

- **The frozen daily log,** from the Stage 3 freeze: a GitHub Actions workflow here, after 4 pm New York time on each
  business day, appending to a protected branch, reusing the parent's live-record helpers (`scripts/live_record.py`:
  `extend_panel`, `require_reads_on_real_rows`, `is_decision_day`, `write_record`) with its own record schema. Scored
  on the dates in `evaluation.md`.
- **Monitoring:** the filtered state beside the parent's live record, published from here, never written into the
  parent's frozen daily file.

## Across all stages

- **Provenance.** Every Phase 3 record carries this repository's commit and whether its tree was modified, the parent
  pin, the parent panel digest and the Phase 3 panel digest.
- **Publishing.** A draft rule for this repository is in
  [`docs/decisions/drafts/publish-rule.md`](docs/decisions/drafts/publish-rule.md), for Eleonora's decision (D4).
- **Reproducibility.** Figures of record are computed on Python 3.11 with the parent's pinned numpy and scikit-learn.
  Development may run on the Mac; a published figure is reproduced in CI before it is published.

## Decisions for Eleonora

- **D1.** Where Phase 3's new inputs are declared and parsed: here, as an overlay (proposed), or in the parent.
- **D2.** Stage 2's "stable enough" threshold: the proposal above, or another.
- **D3.** Stage 3's numerics: a numpy filter with no new package (proposed), or a library now.
- **D4.** The publish rule for this repository (draft).

## Open questions for Nicholas Beroud (data meaning, issue #1)

Under the parent's `PLAN.md`, the choice of data and its meaning rests with Nicholas. Before Stage 1 is written:

1. Which QE/QT measure: the level of the Fed's holdings, its weekly change, the announced runoff caps, or a combination?
2. Are standing repo facility usage and H.8 bank assets the right proxies for the facility outside option and bank
   balance-sheet size?
3. Do the announced runoff caps count as a scheduled input (known in advance, like a settlement), and from their
   announcement date or their effective date?
4. ON RRP from the NY Fed's operation results, as the parent's measurement runs use?
5. Facility usage before 2021-07-29, when the facility did not exist: a structural zero, or missing?
6. A bank-size split for the concentration sensitivity, since H.8 total assets has none?

His evidence pack (parent branch `advisor/evidence-pack`, and his comment on parent PR #219) points to the ON RRP buffer
and a QT restart as the levers.
