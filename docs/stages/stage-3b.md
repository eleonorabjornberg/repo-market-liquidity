# Stage 3b directive: the buffer on a fixed curve

**Written 6 October 2026, before any Stage 3b model was fitted.** Eleonora chose it on 6 October 2026 from
`docs/stages/stage-3-diagnosis.md`: "1 with 3, then 2 as a sensitivity, with 4 put to Nicholas". Stage 3
(`docs/stages/stage-3.md`, #8) was not shown. The diagnosis found the buffer could not be identified apart from the
curve's slope and intercept. It also found that ON RRP and facility take-up measure other things, and that the drift
absorbed calendar noise.

## The model

- **State:** the desired buffer `B_t` in units of the reserves ratio, as in Stage 3. It is carried as
  `z_t`, with `B_t = 0.30 * logistic(z_t)`, so the buffer stays between 0 and 30% of bank assets.
- **Transition:** `z_t = z_{t-1} + eta_t`, with `eta_t ~ N(0, q)` each business day and variance `q + j` on a reform
  date. The dates are the same as Stage 3's: 2021-03-31, 2021-07-29, 2023-03-12, 2023-07-12 and 2023-12-13.
- **Scarcity:** `g_t = s * log(1 + exp((B_t - x_t) / s))`, with `s = 0.005`, as in Stage 3.
- **Two observation heads,** each `y = a + b * g_t + c_type + e`, with `e ~ N(0, r)`:
  1. **The corridor position, on a fixed curve.** Its `a` and `b` are not estimated. They are the intercept and slope
     of Stage 2's broken-stick fit on 2018 to 13 March 2020 (`results/stage2/demand_curve.json`, `revised_test`,
     episode "2018 to March 2020": intercept 1.057938, slope 133.2055 per unit). Stage 2's hinge `max(kink - x, 0)` is
     the limit of `g` as `s` goes to 0, so `B` is the curve's kink. Only `r` and the calendar terms are estimated.
  2. **SOFR dispersion** (75th minus 25th percentile, bp), with `a`, `b` and `r` estimated.
- **Calendar terms (option 3):** each head has an additive term for the day's pressure-day type, by the parent's
  declaration (`metadata/evaluation_splits.json`, read with `evaluation_splits.load_split_declaration`): quarter-end,
  month-end (two calendar days or fewer before it, as declared there) or tax date, with ordinary days at 0. That
  declaration is provisional in the parent; Stage 3b uses it as it stands at the pin. A day's type is calendar
  knowledge, public in advance.
- **ON RRP and facility take-up (option 4)** are not in the state. Their monthly medians are reported beside the
  buffer. How they should be measured before they can re-enter is put to Nicholas on issue #1.
- **Estimation:** an extended Kalman filter, linearized in `z`. The parameters are `q`, `j`, the initial buffer, the
  corridor's `r`, the dispersion head's `a`, `b` and `r`, and the calendar terms. They are fitted by maximum
  likelihood with statsmodels, as in Stage 3. Bounds: drift standard deviation at most 0.03 in `z` (about 0.2 points
  of the ratio per day near a 10% buffer), and jump standard deviation at most 0.75 in `z` (about 5 points).

## Information

- **The fixed curve uses data to 2020-03-13**, so no refit may be dated earlier. A guard refuses a refit whose cutoff
  precedes the curve's last day (`LookAheadError`).
- **The walk-forward:** the first refit is at 2020-03-13, then one every 21 business days to 2025-12-31.
- **The first refit's filter covers 2018 to 13 March 2020,** so that period is in-sample by construction and is also
  the curve's training window. Every later day is filtered with parameters fitted before it.
- **The forecast for day T** uses the filter through T − 2, filtered and never smoothed, as in Stage 3. The parent's
  lockbox holds 2026.

## What Stage 3b must show (unchanged from Stage 3)

1. **Stability.** For every date both refits cover, the filtered buffer from one walk-forward refit and the next
   differs by less than **0.5 points** of the reserves ratio.
2. **The like-for-like benchmark.** The mean filtered buffer over 2025 minus its mean over 2018 to 13 March 2020 is
   positive, with a 90% interval above 0. The interval combines the filter's own state variances, mapped from `z` to
   `B`, taken as perfectly correlated within each period, and stated in the record.
3. **Reported beside them, full window, not judged:**
   - `s = 0.002` and `s = 0.01`;
   - jumps only at the legal breaks (2021-03-31, 2023-03-12);
   - **option 2:** drift held at 0, so the buffer moves only at reform dates;
   - no calendar terms, to show what option 3 does.

If 1 or 2 fails, the pull request says so plainly and nothing is frozen. If both hold, the model is frozen by checksum,
and Stage 5a's daily log can start once Eleonora merges.

## Known limits, stated before the fit

- The fixed curve's flat level (1.06) is 2018 to 2019's. In 2021 to 2022 the corridor position sat near 0 at the floor.
  The corridor head cannot fit those days, and they show up as a large corridor `r`. The dispersion head carries the
  buffer there.
- Stage 2's 2025 curve is flatter (slope 60). On a fixed 2018 curve, part of any shift may be a change in shape, not
  in position.
- The benchmark interval ignores parameter uncertainty, as in Stage 3.

## Not in Stage 3b

Nothing is scored (that is Stage 4) and nothing is published. No Stage 1b input is used. The merged Stage 3 record is
not edited.

## Amendment, 6 October 2026: fresh starts at every refit (written after the first run)

**This amendment was written after Stage 3b's first run had been seen** (#9): benchmark shown, stability not shown.
Eleonora chose it on 6 October 2026 from the options in that pull request.

**What the first run found.** Almost every stability breach came from one refit transition (2022-10-19 to 2022-11-18).
Before it, 28 of 32 refits did not converge. Each was warm-started from the previous refit, so the chain stayed in a
local optimum with an initial buffer near 4%. From 2022-11-18, every refit converged near 9.4%.

**The change: procedure only.** Every fit, including the walk-forward refits, the full-window fit and each sensitivity,
is run from several starting points, and the one with the highest likelihood is kept. The starting points are:

- the previous refit's answer (for the walk-forward), or the full-window fit's answer (for a sensitivity);
- the data-scaled start;
- the data-scaled start with the initial buffer set to each of 5%, 9%, 13% and 17%.

The record lists each refit's likelihood from every start, and which start won.

**Unchanged:** the model, the fixed curve, the jump dates, both must-shows, and the 0.5-point bar.

**What is carried forward (Eleonora, 6 October 2026).** The full-window shift is the headline result, with three caveats
stated wherever it is quoted:

1. it appears only when the buffer may drift between reform dates (with drift held at 0 there is no shift, though that
   fit is much worse);
2. the rise came in late 2022, as reserves fell back toward the buffer, not on a reform date, so no single reform can be
   credited with it;
3. at the sharpest kink scale (`s = 0.002`) it disappears.

**One added sensitivity, reported and not judged:** jumps also allowed at 2025-12-11, the standing repo facility's move
to a fixed rate (added to `docs/decisions/reform-dates.md` on 6 October 2026).

## Amendment 2, 6 October 2026: Nicholas's answers (written after the first run, before the second)

Nicholas Beroud answered the data questions on 6 October 2026 (`docs/decisions/data-meaning.md`). Eleonora asked for
two of his answers to be built into Stage 3b. The model, the main jump dates and both must-shows are unchanged. Two
sensitivities are added, each reported and not judged.

**1. TGCR minus the ON RRP rate (his answer 12): the corridor read from TGCR.** The diagnosis
(`scripts/diagnostics/tgcr_gap.py`) found that this gap repeats the corridor head:

- TGCR − ON RRP = (SOFR − ON RRP) + (TGCR − SOFR), and TGCR − SOFR is nearly constant (median −2bp, 5th to 95th
  percentile −4 to 0bp);
- the gap's daily changes correlate 0.99 with the corridor position's;
- as a separate head, the filter would read the same news twice as if it were independent, and its intervals would be
  too narrow.

So it is built as the same corridor head read from TGCR instead of SOFR: (TGCR − ON RRP rate) / (IORB − ON RRP rate).
It sits on its own fixed curve, fitted by Stage 2's broken-stick method (`demand_curve.fit_broken_stick`) on the same
days (2018 to 13 March 2020). As a check of the method, the same fit on the SOFR corridor must reproduce Stage 2's
recorded curve.

**2. The SLR exclusion ending (his answer 11): jumps only at 2021-03-31,** the reform he rates most material to the
desired buffer. The existing legal-breaks sensitivity (2021-03-31 and 2023-03-12) stays.

**Also recorded, for the live filter:** mandatory clearing of Treasury repo (2027-06-30) is a measurement break in SOFR
volume and dispersion (his answer 11). The dispersion head is re-estimated after it, never read across it. This is
declared now and applies when the live filter reaches that date.
