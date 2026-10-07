# Handoff: where Phase 3 stands

**Written 6 October 2026, at the end of the session that built Stages 1a to 3; updated 7 October 2026 with the Stage 4 plan.** This file is a working note for the
next session, not a decision record. Where it disagrees with `docs/decisions/`, `CLAUDE.md`, `PLAN.md` or a stage
directive, those win and this file is stale. Update it at the end of each session.

## Stages

| Stage | State | Where |
|---|---|---|
| Setup: pin, CI, plan, decisions | Merged | `README.md`, `PLAN.md`, `CLAUDE.md`, `docs/decisions/`, `tests/test_parent_pin.py` |
| 1a: the inputs already ruled on | Merged (#6) | `metadata/sources_phase3.json`, `src/repo_liquidity/{declaration,h41,scheduled,panel}.py`, `metadata/phase3_panel_manifest.json` |
| 1b: the indicator families (questions 7 to 10) | First wave merged (#11); later waves not started | `PLAN.md`, Stage 1 |
| 2: the reserve demand curve | Merged (#7) | `src/repo_liquidity/demand_curve.py`, `results/stage2/`, `docs/decisions/stage-2-bend.md` |
| 3: the latent buffer | Merged (#8): **not shown** | `docs/stages/stage-3.md`, `src/repo_liquidity/latent.py`, `scripts/stage3_latent.py`, `results/stage3/latent.json` |
| 3b: the buffer on a fixed curve | Merged (#9): **benchmark shown, stability not shown** | `docs/stages/stage-3b.md`, `src/repo_liquidity/anchored.py`, `scripts/stage3b_anchored.py`, `results/stage3b/anchored.json` |
| 1a correction: MBS, 2019–21 repo operations, material use | Merged (#10) | `docs/stages/stage-1a-correction.md`, `src/repo_liquidity/fed_repo.py`, `metadata/phase3_panel_v2_manifest.json` (panel version 2; version 1 is unchanged) |
| 1b, first wave: pricing and the Fed's facilities | Merged (#11) | `docs/stages/stage-1b.md`, `src/repo_liquidity/indicators.py`, `metadata/phase3_panel_v3_manifest.json` (panel version 3; versions 1 and 2 unchanged) |
| 3c: Stage 3b's model, stability on the real-time buffer | Merged (#12): **not shown** (judged once). Stage 2's curve becomes the Stage 4 model | `docs/stages/stage-3c.md`, `scripts/stage3c_realtime.py`, `results/stage3c/realtime.json` |
| 4: Stage 2's curve as one feature of the published gbm | **Scored once, in review: not shown.** Model A reproduces the published record exactly; the mean CRPS gain is +0.0038 bp [−0.0070, +0.0146]; the Brier at +5 bp is not shown either. The freeze and Stage 5a wait on Eleonora's review | `docs/stages/stage-4.md` (Result), `results/stage4/` |
| 5a: Phase 3's own daily log | Not started. Starts from the Stage 4 freeze, whatever the development verdict | `PLAN.md`, Stage 5 |

## Stage 2, in one paragraph

The decided rule (`stage-2-bend.md`) did **not** show a stable bend: only 2018 to 2019 had enough scarce days, and its
bend (11.6%) sat outside the pooled bend's interval (14.5%). The diagnosis: the flat part of the curve is set by the
administered floor (the IORB minus ON RRP corridor moved from 25 to 10 to 15 bp), not by calendar effects. Eleonora
chose a revised, post-hoc test: measure from the floor (the corridor position), compare the two scarce episodes, and
require 60 scarce days. Under it the shift is shown: the 2025 bend sits about 4 points above the 2018 to March 2020
bend, and at the same reserves ratio SOFR sat higher in the corridor in 2025. The caveat is that the two bends mark
different features of the curve. Full numbers are in `results/stage2/demand_curve.json`.

## Stage 3: what the run showed

The directive (`docs/stages/stage-3.md`, written before any fit) was run as specified. **Neither must-show held, so the
model is not frozen.**

1. **Stability: not shown.** The worst gap between consecutive refits is about 4 points of the ratio (on 2021-08-26,
   just after the standing repo facility starts, between the refits of 2021-09-15 and 2021-10-15), against a limit of
   0.5. The median gap is small (about 0.05 points), so the failures sit at a few dates.
2. **The benchmark: not shown.** The walk-forward buffer averages about 2.4% in 2018 to March 2020 and about −1.4% in
   2025, so the difference is negative with a 90% interval below 0. The sign is the opposite of Stage 2's.

What the diagnosis found (reported, not tuned):

- **The model is not identified on these data.** The full-window fit and the walk-forward refits settle at different
  optima: the full-window buffer is about 10.5% in both periods, while the walk-forward buffer is near zero or negative.
  The last refits see almost the same data as the full-window fit, so the gap is mostly where the optimizer lands
  (warm-started from the previous refit, against a fresh start), not what each fit sees.
- **The ON RRP head dominates.** It has the smallest noise, so the buffer follows ON RRP take-up (`D = x - B`), which
  swings by orders of magnitude for reasons other than the buffer (money-fund allocation, bill supply).
- **The drift variance sits at its upper bound** (0.2 points a day) and the jump variance is near zero: the filter
  moves the buffer daily rather than at reform dates.
- **The buffer's path is not bounded below 0.** Only the initial buffer is bounded. The walk-forward buffer falls from
  about 5 to 7% in 2018 to 2021 to below 0 from 2022 on, as ON RRP take-up surges, and stays there through 2025.
- **The corridor head alone** (a labelled diagnostic, not the directive's model) gives a buffer near 17.8% in both
  periods: no shift.
- **Sensitivities** (`s = 0.002`, `s = 0.01`, jumps only at the legal breaks), fitted on the full window, give no upward
  shift between the two periods either.

Two refits did not report convergence. The record counts them and keeps their paths.

**The diagnosis that followed is `docs/stages/stage-3-diagnosis.md`**, which supersedes the options listed below.

**What to do next is Eleonora's call.** Options to put to her, none of them started:

- drop or down-weight the ON RRP head, or let it read a share rather than a level;
- fix the drift variance (or bound it much lower) so that the buffer moves mainly at reform dates;
- bound the state, not only its start, for example by filtering a transformed buffer;
- fit once on a training window and hold the parameters fixed in the walk-forward, so that stability measures the filter
  rather than the optimizer;
- accept that the latent buffer is not identified here, and carry Stage 2's descriptive shift into Stage 4 as a
  simpler model.

Any of these changes the directive, so it needs a new directive written before the fit is rerun.

## Stage 3b: what the run showed

Eleonora chose option 1 with 3 from the diagnosis, with 2 as a sensitivity and 4 put to Nicholas (questions 12 and 13
on issue #1). The directive is `docs/stages/stage-3b.md`, written before the fit.

- **Benchmark: shown.** On the walk-forward path the 2025 buffer is 7.6 points above 2018 to March 2020, 90% interval
  [2.9, 12.3]. On the full-window fit it is 3.3 points above, [2.8, 3.7]: about 9% then, 12 to 13% in 2025.
- **Stability: not shown.** Almost every breach comes from one refit transition, 2022-10-19 to 2022-11-18. Before it,
  28 of 32 refits did not converge, and the warm-started chain sat at an initial buffer near 4%. From 2022-11-18 on,
  every refit converges near 9.4%, and only a few days breach the bar. The walk-forward's 2018 to 2020 level (about
  5%) comes from that stuck chain, which is why its shift is larger than the full window's.
- **What the shift rests on:**
  - With drift held at 0 (option 2), there is no shift, but that fit is much worse (log-likelihood −8130 against
    −7333).
  - At `s = 0.002` there is no shift either; at `s = 0.01` there is (+3.2 points).
  - The rise comes in late 2022, as reserves fell back toward the buffer, not at a reform date.
  - From 2020 to 2022 reserves were plentiful and the buffer cannot be seen: its standard deviation grows to about 5
    points.
  - The drift sits at its bound in every fit.
- **Possible next steps, Eleonora's call:**
  - refit from several fresh starts at each refit rather than warm-starting, so that the chain cannot stay stuck;
  - or start the walk-forward once the fit is identified, and state why;
  - either one changes the directive before any rerun.

## Decided after Stage 3b (Eleonora, 6 October 2026)

Stage 3b closes as not shown, with no third amendment. Next: the Stage 1a correction, Stage 1b's first wave, then Stage
3c (stability on the real-time buffer, judged once), with Stage 2's curve as the fallback. The full list is in `PLAN.md`,
Stage 1.

After the multi-start amendment:
- 64 of 69 refits converge;
- the full-window shift is +3.3 points [2.8, 3.7];
- the remaining stability breaches come from the refits of April 2020 to April 2021, which re-draw the 2018 to 2020
  buffer, plus a few weeks in late 2022.
- the shift holds with the corridor read from TGCR (+3.3 [2.9, 3.7]) and with jumps only at the SLR end (+3.3); it
  vanishes only with drift held at 0 and at `s = 0.002`.

## Waiting on others

- **Nicholas (issue #1) answered questions 1 to 13 on 6 October 2026** (question 14 answered too; question 15, agency debt, is open), recorded in `docs/decisions/data-meaning.md`, which also lists the work it creates (Stage 1a corrections, Stage 1b's first wave). Questions 1 to 5 have Eleonora's preliminary rulings
  (`docs/decisions/data-meaning-preliminary.md`). Stage 1b waits on questions 7 to 10.
- **Eleonora, two possible reform dates found while building, not yet in `reform-dates.md`:** the standing repo
  facility moved to a fixed rate and dropped its aggregate limit on 2025-12-10, and reserve-management bill purchases
  resumed in December 2025. Adding either is a new row with its own announcement date.
- **Eleonora's laptop:** her main checkout's `.venv` was on Python 3.9.6; the rebuild on 3.11 was given to her, and
  whether she ran it is not known. The runner-notes skill path fix was given as text for her to apply.

## Setup facts a new session needs

- **The parent pin** is `71ab387e5557cc9ecefb12d1b2bf21d086571388`, in `src/repo_liquidity/__init__.py` and
  `pyproject.toml`. The parent is installed editable from a clean checkout at the pin, because it reads `metadata/`
  relative to its own source tree. The parent's panel digest is `4ddc3882…8999`.
- **The Phase 3 panel** is built by `python3 scripts/build_panel.py` (`--check` verifies it) from tracked fixtures, with
  no network. Its manifest is generated, never hand-edited.
- **Stage 3 needs the `state-space` extra** (statsmodels and its exact pins, in `pyproject.toml` and
  `docs/decisions/dependencies.md`). The walk-forward takes about a quarter of an hour, so CI checks the tracked record's
  consistency (`tests/test_stage3_record.py`), not its regeneration. Regenerate it with
  `PYTHONPATH=src python3 scripts/stage3_latent.py`.
- **Network from the cloud:** federalreserve.gov, the NY Fed and FRED graph are reachable. ALFRED and the FRED API are
  blocked.
- **The lockbox holds 2026.** Development evidence ends on 2025-12-31.
- **Her laptop layout:** `~/Desktop/Projects/Portfolio/RM Model/` holds `repo-market-model`, `repo-market-liquidity` and
  `rml-parent` (the read-only parent at the pin). Python is Homebrew 3.11. Give her commands without `#` comments: zsh
  reads an apostrophe in a comment as an open quote.

## Rules that are easy to forget

- Every stage's PR is labelled `needs-eleonora` and merged by her. Delegated review does not merge here.
- Each stage states what it must show before anything is fitted, and is written only after the previous stage is
  reviewed.
- Nothing is published until she says so (`publish-rule.md`, amended); no session opens a publish PR on its own.
- Never touch the parent's code, records or queue. New inputs are declared here as an overlay.
- A new guard gets one recorded mutation in its test's docstring. Run the full suite in one process.
- Every GitHub comment ends with the Claude Code footer.
