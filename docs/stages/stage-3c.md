# Stage 3c directive: stability on the real-time buffer

**Written 6 October 2026, after Stage 3b (#9) and before any Stage 3c computation.** Eleonora decided on 6 October 2026
(`PLAN.md`, "After Stage 3b"): Stage 3c judges stability on the buffer a forecast actually reads, not on revisions to
earlier history; it is judged once; and if it fails, the latent buffer is set aside and Stage 2's curve becomes the
Stage 4 model. On the same day she chose this test from the options put to her, and to keep Stage 3b's model unchanged.

**This directive is written after Stage 3b's results were seen, and it changes a must-show.** Stage 3b's stability
test compared consecutive refits on every earlier date, and failed. Almost every breach was a refit re-drawing the
2018 to 2020 buffer, which no forecast reads (`docs/stages/stage-3b.md`, `results/stage3b/anchored.json`). The test
below has not been computed on any data before this directive was committed.

## The model: Stage 3b's, unchanged

- **The same model** as `docs/stages/stage-3b.md` with both amendments: `src/repo_liquidity/anchored.py`.
  - The corridor head is on Stage 2's fixed 2018 to March 2020 curve.
  - SOFR dispersion sits beside it, with calendar terms in both heads.
  - The buffer is kept between 0 and 30%.
  - It drifts, and may jump at the five reform dates of the development window.
  - Every fit runs from the same set of starting points, and the best is kept.
- **The same data:** panel version 1, the panel Stage 3b read. The columns added in versions 2 and 3 are not used.
- **The same walk-forward:** the first refit on 2020-03-13, then one every 21 observation days to 2025-12-31.
- **The new inputs are not used:** the MBS flow and the take-up events. They go to Stage 4 as forecast inputs.

## What Stage 3c must show

1. **Stability of the real-time buffer.** For every day T served by a refit k after the first, a forecast for T reads
   the filtered buffer at the observation day two before T (`latent.forecast_state`). The test compares that
   buffer under refit k's parameters with the same buffer under refit k − 1's parameters. Both are filtered (never
   smoothed) on the observations through that day. **Every gap must be under 0.5 points** of the reserves ratio.
   - A day T is served by refit k when T falls after refit k's cutoff and on or before the next refit's cutoff.
   - The days the first refit serves have no earlier refit, so they are not compared.
2. **The like-for-like benchmark, as in Stage 3b.** The walk-forward buffer's 2025 mean, minus its 2018 to
   13 March 2020 mean, must be positive with a 90% interval above 0. The interval combines the filter's own state
   variances, taken as perfectly correlated within each period.
   - **Known before writing:** the model and data are unchanged, so this is the same computation as Stage 3b's.
     It is expected to reproduce +7.6 points [2.9, 12.3].
   - Its 2018 to 2020 level comes from the first refit, which did not converge. The full-window shift (+3.3 points
     [2.8, 3.7]) is reported beside it, with the three caveats `docs/stages/stage-3b.md` attaches to it.
3. **Reported, not judged:**
   - the old test (consecutive refits on every earlier date), for comparison with Stage 3b;
   - the largest real-time gaps, with their days and refits.

If 1 or 2 fails, the pull request says so plainly, nothing is frozen, and Stage 2's curve becomes the Stage 4 model.
If both hold, the model is frozen by checksum, and Stage 5a's daily log can start once Eleonora merges. Stage 3c is
judged once: whatever it shows, no further amendment.

## Not in Stage 3c

Nothing is scored (that is Stage 4) and nothing is published. The Stage 3 and 3b records are not edited.
