# A dispersion- or volume-based liquidity hypothesis, step 1: the hypothesis, its inputs and its prior-work check

**Draft for Eleonora's review (#205); in force only once she merges it.** It is a planning decision: the merge is hers.
Written 9 November 2026 at base `b4737219c8d443041bbc406cc97dfb584cbbcc2d`. **Step 1 only.** Nothing is fitted, scored or
estimated here, and no panel was built for it. Step 2 is written only after this step is reviewed. Under the 2 November
freeze nothing is adopted.

**Ruling it follows.** Eleonora, 9 November 2026 (relayed by the orchestrating session; the choice "do all four" on
[#24](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/24#issuecomment-6731242692), then her answer from the
decision docket on #205): judge it under `docs/decisions/measurement-protocol.md` v1 with **no protocol change**; it carries a
**provisional name**; dispersion and volume are **both inputs and one is primary**, step 1 naming which and why.

**Hypothesis and step:** the hypothesis below, provisionally labelled **HX**, step 1 (the hypothesis, its inputs and its
prior-work check). Development tier: groundwork. The research-log tag is `H7` because this repository's check accepts only H7 and
H10 (`scripts/check_log_entry.py`, `TAGS`); that, and the label, are marked question (ii) in the pull request.

## 1. Question

On prospective days, does the dispersion of the overnight secured rate distribution, or the volume traded, locate **aggregate
deployable liquidity** (the protocol's quantity, in points of bank assets) well enough to meet the three goalposts of
`measurement-protocol.md` v1, all set in advance?

- **Stable:** real-time estimates under consecutive refits agree (v1 §3: under 0.5 points of bank assets).
- **Sharp:** the daily 90% interval is narrow enough (v1 §4: median width under 3 points).
- **Informative:** it separates stress days from other days better than the reserves ratio and the scarcity state together,
  by at least the MME (v1 §5: 0.05 AUROC points, stratified by S).

The mechanism it asks about: as reserves fall toward the point where banks stop treating them as abundant, the **spread of
trades around the rate** widens before, or differently from, the **level** of the rate. H7m read only levels (section 5).

## 2. Estimand, and how it relates to points of bank assets

**The estimand is the protocol's own** (`measurement-protocol.md:23-27`, §2): aggregate deployable liquidity on T, in points of
bank assets, as of 16:00 on the panel day before T, read through `repo_model.asof.InformationRule`, filtered and never smoothed,
with a 90% interval; judged against R (`scarcity.py:161`) and S (`scarcity.py:194`) of the model repository, cited and never
redefined. The benchmarks are those of H7m: R, S and R+S (`plan.md:125-130`).

**The primary measure itself is not in points of bank assets.** It is in basis points (dispersion) or USD (volume). That is
why it is an **input to an estimator**, not the estimand: a candidate would read a dispersion or volume series and return a
point-of-bank-assets estimate. The page does not say how; that is step 2, and nothing about the form of the estimator is
decided here. Two consequences, stated plainly:

1. **Goalposts 1 and 2 are in points of bank assets,** so only an estimator that returns points can be tested under v1 as
   written. This is why the draft holds the estimand to the protocol's and does not propose a different one.
2. **If she wants the dispersion or volume measure judged as a stress indicator in its own units** (an estimand that is not in
   points of bank assets), v1 does not cover it, and a protocol change goes through §12 as written (see question (i), option 2).
   §12 allows a change only on a synthetic demonstration or a reproduced error, never on a candidate's result
   (`measurement-protocol.md:92-99`), so such a change could not be drafted from this hypothesis's motivation alone.

**A prior that bears on step 2** (`stage-6.md:167-173`; plan "Prior work"): any model that learns a shift by re-estimation fails
the 0.5-point stability bar on the refit where it learns it, and in H7m family A fails goalpost 1 while family C's is unreadable on development data (section 6).
A candidate here must say in its declaration how its estimate moves with observed data without a refit moving it by more than
the bar. The draft does not claim one exists.

## 3. Inputs and their availability declarations

Each input is an overlay under D1 (`docs/decisions/input-declarations.md`): **declared in this repository, read through
`repo_model.asof.InformationRule`, checked by the parent's validators**. All five are **fields of sources the parent already
declares**, and the overlay refuses an id the parent declares (`declaration.merge`), so no new file is added under
`declarations/`: the inputs are switched on in `src/repo_liquidity/declaration.py`, as Stage 1b switched on `sofr_p1`, `sofr_p99`
and `effr`. The parent is not changed. The release lags are the parent's (`metadata/sources.json` at the pin
`2032de4a7d7802289bc5a78dfc02599752bc7c5c`).

| Input (declared feature) | Family, role | Source and field | Declared lag | Status here |
|---|---|---|---|---|
| `sofr_p75_p25_bp` | dispersion, **primary** | `nyfed_sofr` `SOFR_p75`, `SOFR_p25` | 1 business day, 15:00 ET | Panel column since version 3 (`indicators.py:26`); switched on already |
| `sofr_p99_p1_bp` | dispersion, secondary | `nyfed_sofr` `SOFR_p99`, `SOFR_p1` | 1 business day, 15:00 ET | Panel column since version 3 (`indicators.py:27`); switched on already |
| `sofr_volume` | volume, secondary | `nyfed_sofr` `SOFR_volume` | 1 business day, 15:00 ET | The parent's own feature (`contract.py:277`); no change |
| `bgcr_volume` | volume, secondary | `nyfed_bgcr` `BGCR_volume` | 1 business day, 15:00 ET | **Switched on by this step** |
| `ofr_dvp_volume` | volume, context | `ofr_stfm_repo` `REPO-DVP_TV_OO-F` | 2 business days, 16:00 ET | **Switched on by this step**; off in every published declaration of the parent |

Each is tested by `tests/test_dispersion_volume.py`: a read one row later than the declared lag allows raises `LookAheadError`,
a read one row earlier raises `StaleReadError`, and the module's two data guards are tested. Every test carries its recorded
mutation in its docstring.

**The primary measure is `sofr_p75_p25_bp`, SOFR's interquartile width. Reasons:**

1. **It measures cash scarcity, not collateral scarcity.** The data-meaning record puts SOFR's 1st percentile among "acceptable
   but noisy" specials proxies and keeps collateral scarcity on its own axis, apart from cash scarcity (`data-meaning.md`,
   answer 8, `:19`). The 1st percentile enters the p99-p1 range; the interquartile range does not use it. The hypothesis is about
   the cash side.
2. **It is in the family the record starts with:** "percentile dispersion" is first-wave pricing (answer 7, `:18`). Volume
   belongs to the second wave, "dealer intermediation and cash supply and demand".
3. **It has no trend to remove.** A width in basis points compares across years; a repo volume in USD grows with the market and
   needs a normalisation that is itself a choice (`sofr_volume` over `bgcr_volume` is the cleared-DVP share that the model
   repository's `dvp_segment.py` already forms for the forecast side).

The cost, to be checked in step 2 and not assumed away: the percentiles are published to the basis point, so the interquartile
width takes few distinct values. If it carries too little resolution to locate anything, that is a step 2 finding.
**Volume is secondary** and may be promoted only by her (question (iii)). **`ofr_dvp_volume` is context only,** because the OFR
keeps no vintages and the series is its final figure (`sources.json`, `ofr_stfm_repo.availability_provenance`): the 2-day lag
is a conservative declaration, not a first print, so it cannot be primary or enter a registration without a first-print
archive. Values dated before 2020-09-09 were filled in after the OFR began publishing in real time, so
`dispersion_volume.check_usable` refuses them with `LookAheadError`.

**Not used.** The DTCC GCF Repo Index (model repository `src/repo_model/gcf_index.py`) is a forward capture begun in autumn 2026
(its file holds one year of rows, and the capture records only from the day it began); the registry at the pin carries no
declaration for it, and its own declaration was not traced. It is not a development series, so it is not an input of this
development hypothesis. The model repository's decision instant is 18:00
ET since 29 October 2026; this repository reads the parent at the pin, whose instant is 16:00 (`decision_time=time(16, 0)`), and
the draft follows the pin. Moving the pin is a separate reviewed change (`docs/decisions/dependencies.md`).

### The 2027-06-30 break

Mandatory clearing of Treasury repo makes uncleared bilateral repo enter SOFR from 2027-06-30: **a measurement break in SOFR's
volume and dispersion** (`data-meaning.md`, answer 11, `:22`; `indicators.MEASUREMENT_BREAKS`, `indicators.py:46-50`).

**Draft default: no input is read across the break until she declares a re-based series.** `dispersion_volume.check_not_across_break`
refuses, with `ValueError`, a window that has days on both sides (the break day is the first day under the new meaning).

| Series | Treatment across 2027-06-30 |
|---|---|
| `sofr_p75_p25_bp`, `sofr_p99_p1_bp`, `sofr_volume` | In the register's list. Not read across the break. |
| `bgcr_volume` | **Not in the register.** BGCR is tri-party and GCF repo, which uncleared bilateral repo does not enter, so it may be unaffected; whether it is a data-meaning question for her. Until she rules it is **treated as broken** (the conservative reading). |
| `ofr_dvp_volume` | Not in the register. The OFR's DVP segment is the one mandatory clearing moves, so it is **treated as broken**. |

Development ends 2026-09-03 and the lockbox covers later days, so no development read meets the break; it matters for
confirmation and for any series a registration would freeze.

## 4. What would confirm it and what kills it

**Set now, before any step runs. Nothing is added to the protocol:** the goalposts, the MME, the bootstrap, the checkpoints and
the kill rule are v1's (`measurement-protocol.md` §3 to §9, and plan "H7m: Kill criterion").

- **Supported** at a checkpoint: all three goalposts hold (v1 §9, with the 10-event floor).
- **Killed:** a prospective stability breach, a prospective median interval width over 3 points, or at a checkpoint the upper
  bound of the information gain against R+S below the MME.
- **Not testable as stated** (development): no candidate meets goalposts 1 and 2 on the development walk-forward, so nothing can
  be registered. This is how H7m ended (`h7m-verdict.md:5`).
- **Judged against** R, S and R+S, from the model repository's two functions only (plan, H7m "Benchmarks").
- **Missing data** are v1's §11: more than 5% missing days voids a registration, and a stale day is missing, not imputed.

**Calendar first** (Eleonora, 20 October 2026). Dispersion moves on quarter-ends, month-ends, tax dates and Treasury settlements.
Any candidate reads the calendar at the target day, and where it fits on days it trains on the calendar-clean set
(`docs/stages/h7-calendar-clean.md`, section 2 (a)). That is a constraint on step 2, recorded here and not designed here.

**Milestones (done when).**

| | Done when |
|---|---|
| M0 | This page and its inputs, guards and leakage and staleness tests are merged (step 1), with her answers to questions (i) to (iii). |
| M1 | Step 2 merged: the estimand's as-of estimator over the primary measure, with a leakage test and its mutation. No score. |
| M2 | The candidates are declared, with their variant count, before any is run. |
| M3 | A power study on development data says whether 0.05 AUROC points is detectable with these inputs (as G6 did for H7m). |
| M4 | Development score of the three goalposts for each candidate, and for R and R+S. Reported, never a verdict. |
| M5 | The primary candidate is chosen by v1 §7 and registered (her attested action). |
| M6 | Checkpoints at 60, 125 and 250 confirmation days. |

M1's estimator is declared in `docs/research/dispersion-estimator.md` (step 2, #210). M2's candidate set is declared in
`docs/research/dispersion-candidates.md` (step 3, #214): W1 alone by default, which adds nothing to the count below.

**The variant count** (v1 §10) is carried, not reset. From the records: **12 estimators in play, 10 of them variants** (A's B and
six variants, C and four variants); D and its four variants were declared and dropped under #142 and are listed, not counted in
play; the count "from Stages 2 to 6's records" is stated by no record (`docs/research/h7-step5.md`, "The variant count"). **This step
adds none:** it declares inputs, not estimators. Step 2 (#210) adds one, W1, so the count in play is 13, 11 of them variants. Every estimator step 2 or M2 declares adds to the count, a not-scorable one included
(the default of `docs/stages/h7-step5.md` section 6, Q4).

## 5. How it differs from what was tried

| Tried | What it was | How this differs |
|---|---|---|
| **H7m candidate A** (the kink, B and V1 to V6) | A kink in a corridor position against reserves; left sides **SOFR − IORB** or **EFFR − IORB** (`h7-kink.md:105-112`; `plan.md:157-158`) | A level. The left side here is a **width** of the distribution of trades, or a volume. No level of any rate is read as the primary. |
| **C, bank groups** (CV1 to CV4) | The same left sides, by H.8 group (`h7-calendar-clean.md:139-144`) | Aggregate, not by group. Groups are not an input here. |
| **D, SLR headroom** | A buffer from a regulatory constraint; declared and dropped under #142 | A market-side reading, not a constraint-side one. |
| **H9, richer targets** (model repository) | `sofr_dispersion_bps` and `bgcr_dispersion_bps` are **forecast targets**, scored by CRPS against persistence and climatology (`docs/research/hypotheses/H9.md:8`, `:27`) | Here dispersion is an **observed input** read at the decision instant, and the question is about a **state**, not a forecast. Nothing is forecast and nothing is scored by the model's CRPS. |
| **#1175** (model repository) | H5's candidate scaled by SOFR's in-panel dispersion; development, no verdict (`docs/research/sofr-dispersion-1175-result.md`) | A scale on a forecast, to shorten misses. Not a liquidity measure. |
| **Cleared-DVP share** (model repository, #187) | `(SOFR volume − BGCR volume) / SOFR volume`, a forecast-side feature (`src/repo_model/dvp_segment.py`) | A candidate here may use the same two volumes, but as a scarcity reading judged under v1, not as a feature of a spread forecast. |

**Overlap to be said plainly.** Section 2 makes this hypothesis a new **left side** for a device H7m already used: the V-series
varied the left side among two levels, and this is a third kind. Under the refocus rule of 22 October 2026 ("fix the known
failures, and stop patching failed models with variants", #24) that is a reason to ask whether it is more than another variant.
The draft's answer is that it changes the **observable**, not a fitting detail, and that her order of 9 November asks for it. The
question is hers.

## 6. The prior-work check, at this PR's base

**Not tried before as a liquidity or scarcity measure.** At base `b4737219c8d443041bbc406cc97dfb584cbbcc2d`, these paths were
searched for `p99`, `p75`, `dispersion`, `volume`, `tri-party` and `GCF`, with **no hit**:
`docs/stages/h7*`, `docs/stages/h7m-verdict.md`, `docs/stages/phase3-exit.md`, `docs/stages/stage-6.md`, `docs/research/h7*`,
`src/repo_liquidity/h7*` and `archive/h7*`. The model repository's `docs/research/plan.md` (main at
`a14a354a79ebf08558e502686b46ed74572c3abb`) has dispersion only under H9 (`:107`), none under H7 or H7f.

**H7m's outcome** (`h7m-verdict.md:5`, ruled 26 October; `phase3-exit.md:49`, ruled 28 October): **not testable as stated.** H7m is
closed and Phase 3's exit criterion is not met on development.

- B and V1 to V6 fail goalpost 1 (the worst real-time gap against 0.5 points: 2.00 to 8.75, `h7m-verdict.md:33-39`).
- C fails goalpost 2: a median width of 3.46 against 3.0 (`:40`).
- CV3's goalpost 1 is unreadable; CV1, CV2 and CV4 are not scorable, with 69 of 70 refits not identified.
- D was not run (dropped under #142).

**H7f** (R+S in the model repository; `plan.md:193-194`, `:241`) has no dispersion or volume content on the model's main; the
nested test of #1526 (open) is not on main.

**Data meaning that binds it** (`docs/decisions/data-meaning.md`): row 7 (`:18`) percentile dispersion is first-wave pricing; row 8
(`:19`) DVP − BGCR and SOFR's 1st percentile are noisy specials proxies; row 11 (`:22`) mandatory clearing on 2027-06-30 is a break
in SOFR's volume and dispersion.

**Brought up to date at the base:** the pin is still `2032de4`, the parent panel digest is unchanged
(`4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999`), the Phase 3 panel is version 5, and the pin's `sources.json`
carries `BGCR_volume` under `nyfed_bgcr` and `REPO-DVP_TV_OO-F` under `ofr_stfm_repo`.

## 7. What this step does not do

- No estimator, no fit, no score, no panel: the guards are tested on the declaration and the panel's dates only.
- No protocol change, no change to the parent, its pin, its panel, `sources_phase3.json` or any record.
- It does not choose between the primary measure's alternatives for good: question (iii) is hers.
- It does not settle whether BGCR's volume is affected by the break (a data-meaning question), and it does not name the hypothesis.
