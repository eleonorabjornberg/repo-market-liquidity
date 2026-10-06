# Stage 3 diagnosis: why the latent buffer failed, and the options

**Written 6 October 2026, after Stage 3 (#8) was merged as not shown.** This is a diagnosis for Eleonora to choose from,
not a decision and not a directive. Every number here is from a diagnostic fit on the full development window (to
2025-12-31). None of them is a Stage 3 result, and none is scored. The scripts are in `scripts/diagnostics/`
(`stage3_heads.py`, `stage3_experiments.py`, `stage3_anchor.py`).

## What went wrong

**1. The buffer and the curve's slope cannot be told apart (the main cause).** The model reads the buffer through the
smooth kink `b * s * log(1 + exp((B - x) / s))`.
- **Far on the plentiful side** (x well above B), this is about `b * s * exp((B - x) / s)`. Only `log b + B / s` is
  identified, so a larger slope with a lower buffer fits the same.
- **Far on the scarce side,** it is about `b * (B - x)`. Here B trades off against the intercept a.

The buffer is pinned only by days near the kink, and most days are not near it. The fits show it:
- From four starting values the full-window fit lands at three different optima.
- The scarcity slopes run to 5,000, and in one fit to about 10^11, which turns the kink into a step.
- **The full-window fit in the merged record (log-likelihood −9146) is one of these local optima.** Another start
  reaches −7814 on the same data. The record is not edited; this note corrects how it is read.

**2. ON RRP take-up measures money-fund cash, not the buffer.** Median ON RRP was about $2bn in 2018 to 2019,
$2,100bn in 2022, and $98bn in 2025. The reserves ratio barely changed across those years. Read through
`D = x - B`, a fall of the buffer must absorb the 2022 to 2023 surge:
- with every head in, and the buffer held constant between reform dates, it falls from about 37% before 2020 to about
  −3% in 2023;
- without the ON RRP head, no fit goes below 0.

**3. Facility take-up is mostly operational noise.** About 400 days show take-up, but the median is $3 million. Only
about 30 days exceed $1bn, nearly all from September 2025 on. The fit gives this head the smallest noise, so these
near-zeros pull the buffer hardest. The worst stability gap (2021-08-26) sits just after the head enters.

**4. The drift sits at its upper bound in every fit.** The measures move with month-ends, quarter-ends and settlement
dates, and the model treats their noise as independent from day to day. The buffer therefore moves daily to absorb
calendar spikes, rather than at reform dates.

**5. Nothing keeps the buffer above 0.** Only its starting value is bounded.

## What the experiments show

The table is ordered from the directive's model to the most constrained one. P1 is 2018 to March 2020, and P2 is
2025. The shift is P2 minus P1.

| Fit | Buffer P1 | Buffer P2 | Shift | Note |
|---|---|---|---|---|
| Directive model, best optimum found | 8.3% | 7.0% | −1.3 | slopes about 5,000 |
| Without ON RRP | 8.4% | 8.0% | −0.4 | slopes about 4,000 |
| Corridor and dispersion only | 9.9% | 13.2% | +3.3 | jump variance at its bound |
| Corridor and dispersion, buffer moves only at reform dates | 18.9% | 19.6% | +0.7 | buffer above x throughout, so it trades off against a |
| **Corridor curve fixed from Stage 2's 2018 to 2020 fit, plus dispersion** | 9.1% | 12.4% | **+3.3 [2.9, 3.7]** | slope and intercept not estimated |
| Corridor curve fixed from Stage 2's 2018 to 2020 fit, corridor alone | 8.8% | 7.3% | −1.5 | the 2021 to 2022 floor regime sits below the curve's flat level |
| Curve fitted by this model on 2018 to 2020, then held fixed | about 1% | about 1% | about 0 | the slope explodes inside the training window too |

The 90% intervals use the filter's own variances, as the directive does. They are narrow because they ignore parameter
uncertainty.

A cheap stability check refits from scratch at the pair of dates where Stage 3 failed. For corridor plus dispersion,
the gap at 2021-09-15 against 2021-10-15 is 0.24 points, inside the 0.5 bar; the directive's model gave 11 points
here when refitted from scratch (the walk-forward's warm starts gave 4 points). Two years apart (2023-12-29 against 2025-12-31) the gap is 4.8 points. That is not the directive's test, but
it says stability is not yet assured.

## The options

1. **Fix the curve from Stage 2 and estimate only the buffer.** Take the corridor head's intercept and slope from
   Stage 2's broken-stick fit on 2018 to March 2020 (intercept 1.06, slope 133 per unit). The buffer is then the
   horizontal position of a known curve, which this closes off as a source of non-identification. SOFR dispersion
   stays in with free coefficients. This is the only fit above that shows a positive shift with an interval above 0
   without exploding slopes.
   - It inherits Stage 2's caveat: the 2025 curve is flatter (slope 60), so part of the shift may be a change in
     shape, not in position.
   - Anchoring on the 2025 curve instead would use the benchmark period to build the measuring stick, so the 2018 to
     2020 fit is the only clean anchor.
2. **Let the buffer move only at reform dates.** Drift is set to about 0, so the buffer is a step function with steps at
   the declared dates. This is easier to explain and closer to "shifts at the laws", but alone it is not identified: it
   puts the buffer above x everywhere. It needs option 1's fixed curve to work.
3. **Model the calendar noise.** Add the parent's month-end, quarter-end and settlement-date effects to each head, or
   filter weekly averages instead of days. Either stops the buffer absorbing calendar spikes, and pairs with 1 or 2.
   Untested.
4. **Re-measure ON RRP and the facility before using them (Nicholas's call, Stage 1b).** For ON RRP, use take-up as a
   share of money-fund assets, or the ON RRP rate's position against market repo, rather than its level. For the
   facility, read material use (for example above $1bn) as an event rather than log take-up. Until then both stay out
   of the state and are reported beside it.
5. **Shelve the latent model.** Carry Stage 2's same-ratio comparison into Stage 4 as the model: the corridor position
   at a given ratio, indexed by period. It is the simplest option and needs no filter, but it gives no daily buffer.

**Recommendation: 1 with 3, then 2 as a sensitivity, with 4 put to Nicholas.** That means corridor (fixed Stage 2
curve) plus dispersion, calendar effects in the noise, drift plus jumps at reform dates, and the state kept above 0.
The must-shows stay as the directive set them: stability within 0.5 points through the walk-forward, and the
benchmark interval above 0. Fewer free parameters make the stability bar easier to meet honestly.

Whichever option is chosen is written as a new directive (`docs/stages/stage-3b.md`) before any fit.
