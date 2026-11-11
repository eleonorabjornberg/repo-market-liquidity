# HX step 2: the as-of estimator W1 over SOFR's interquartile width (milestone M1)

**Draft for Eleonora's review (#210); in force only once she merges it.** The form below involves a choice, so it carries three
marked questions (section 6). Written 11 November 2026. **Nothing is fitted to judge it and nothing is scored.** No goalpost is
read, no R, S or R+S comparison is made, no day after 2026-09-03 is read, and no locked tier is touched.

**Hypothesis and step:** HX (provisional label; log tag `H7`), step 2, milestone M1 of `docs/research/dispersion-volume-hypothesis.md`
(section 4): "the estimand's as-of estimator over the primary measure, with a leakage test and its mutation. No score."
Ruling it follows: Eleonora, 10 November 2026 (relayed; PR #207): protocol v1, the bank-asset estimand, the width as an input,
**`sofr_p75_p25_bp` primary**, BGCR and OFR DVP volume treated as broken at 2027-06-30 until she rules.

## 1. The form, declared before anything is fitted

**W1 is H7m candidate A's kink with one change of observable.** Everything is the parent's or H7m's, by import:

| Part | W1 | Where it comes from |
|---|---|---|
| Estimand | Aggregate deployable liquidity on T, in points of bank assets: the reserves ratio public at T's decision instant, less the kink in force, times 100 | Protocol v1 section 2; `h7_estimator.points`; R is the parent's `scarcity.reserves_ratio`, read through `asof.InformationRule` |
| **Left side** | **The target day's `sofr_p75_p25_bp`, in basis points** | **The one change.** A uses SOFR - IORB; `dispersion_volume.INPUTS` makes the width primary |
| Kink | The `k` on the parent's grid minimising squared error of `width = a + b * max(0, k - ratio)`, `b >= 0` | The parent's `satiation.fit_level`, unchanged; its tie rule (#747) is inherited, so a refit whose kink is not identified serves no estimate and has no fallback |
| Interval | 90%, stationary bootstrap, mean block 10, the parent's seed | `h7_estimator.refit` |
| Days it fits on | Calendar-clean days only: those where the parent's `settlement_day`, `quarter_end_window` and `turn_days.turn_label` all say no | `h7_clean.clean_days` rules, `h7-calendar-clean.md` section 2(a); the constraint of the hypothesis page (section 4) |
| Refits | Scheduled as H7m's (`docs/research/h7-refit-schedule.md`); a refit at cutoff `c` serves from the second business day after `c` | `h7_estimator.SERVING_LAG` |
| Filtering | Filtered, never smoothed; a refit that does not fit serves no estimate | Protocol v1 section 2 |

The width is a **training label** (a day on or before the cutoff), not an input read at a decision instant. The code is
`src/repo_liquidity/dispersion_estimator.py`.

**Why the estimate is in points.** The kink is a level of the reserves ratio, so the estimate is a distance in ratio, whatever
the left side's units. The width only decides where the kink is. That is how a basis-point measure becomes an estimate in points
of bank assets (the hypothesis page, section 2).

**The variant count (protocol v1 section 10).** W1 is one estimator. The count in play rises from 12 to 13, 11 of them variants
(section 4 of the hypothesis page, updated in this PR). No other estimator is declared here.

## 2. How it meets the prior on stability, said plainly

The page records a prior (`stage-6.md:167-173`): a model that learns a shift by re-estimation fails the 0.5-point stability bar
on the refit where it learns it. **W1 does learn by re-estimation, so it may fail goalpost 1.** It has no device that keeps a
refit from moving the kink by more than the bar, and this page does not claim one. The bar is unchanged (v1 section 3). Whether
the width's kink is steadier than the spread's is what M4 would show, and it is development evidence, never a verdict. Question
(ii) below asks whether she wants a slow-update rule declared first.

## 3. The calendar constraint

W1 trains on calendar-clean days, as the hypothesis page requires, and every calendar flag is read at the scored day through the
parent's rule (`h7_clean.read_flags`, which refuses a calendar read at any other row). The width on quarter-ends, month-ends,
tax dates and Treasury settlements is not learned. A dropped day is still served, by the refit in force.

## 4. Guards, and the tests that kill them (`tests/test_dispersion_estimator.py`)

| Guard | Raises | Test, with its recorded mutation in the docstring |
|---|---|---|
| A refit fits on days on or before its cutoff only | `LookAheadError` | `TrainingTests` (mutation 3) |
| A refit serves only once the width of its last training day is public (one business day, 15:00 ET) | `LookAheadError` | `AvailabilityTests` (mutations 1 and 2) |
| The kink carried between refits is the one in force: an older one is stale, a later one is look-ahead | `StaleReadError`, `LookAheadError` | `CarryForwardTests` (mutation 4) |
| Calendar days are left out of the fit | `ValueError` for a flag that is a hole | `TrainingTests` (mutation 5) |
| No window runs across the 2027-06-30 break | `ValueError` | `TrainingTests`, through `dispersion_volume.check_not_across_break` |
| No locked day is read | `LookAheadError` | `ResolutionTests`, through the parent's `lockbox.require_unlocked` |

The estimator's mechanics are tested on constructed inputs (a planted kink is recovered; planted calendar spikes move the kink when
they are left in and do not when they are left out). No real-data fit is made.

## 5. The resolution check (descriptive; a fact, not a score)

The percentiles print to the basis point, so the width takes few distinct values. Over the development panel (2018-04-04 to
2026-09-03, `docs/research/hx-resolution.json`, written by `python3 scripts/hx_resolution.py`; the width is computed by
`indicators.with_indicators`, since the version 5 panel carries the percentiles and not the width):

| Days | Days with a width | Distinct values | Range, bp | Most common value | Its share |
|---|---|---|---|---|---|
| All development days | 2,101 | 27 | 0 to 85 | 8 bp | 17.5% |
| Calendar-clean days (what W1 fits on) | 1,524 | 17 | 0 to 24 | 8 bp | 17.5% |

The clean set drops 578 of the 2,101 days (a little over a quarter), and with them the whole tail of the width above 24 bp.

**A step 2 finding, stated without a verdict:** on the days W1 fits on, the width takes 17 values and no value holds more than
17.5% of the days, so it is coarse but not degenerate. Whether it locates a kink is not read here: that needs a fit, and
none is made. The cost to watch is the one the hypothesis page names: ties in a coarse left side make more refits "not
identified", which serve no estimate. M3's power study is where that would show.

## 6. Marked questions for Eleonora (nothing is settled in code)

**(i) The form.**
1. **W1 as declared: candidate A's kink with the width as left side, fitted on calendar-clean days (the draft).** **Default
   if unanswered by the next 5 pm batch.** It changes the observable and nothing else.
2. A different form (for example no kink and a direct map from the width to points). It would be a new declaration, with its own
   variant count, and a new directive.
3. Both W1 and a second form, declared together before either is run (variant count 14).

**(ii) Stability.** W1 may fail goalpost 1 on the refit where it learns a shift (section 2).
1. **Proceed; M3 and M4 show it (the draft).** **Default.**
2. Declare a slow-update rule first (a refit may move the kink by at most a stated step, or the kink is re-fitted only on a stated
   trigger), as a new directive before M2. That is a design she would choose; it is not drawn here.

**(iii) Where the training days start.** H7m's A variants left out the 25 bp corridor regime (pairs before 2018-06-13; `h7-kink.md` section 7(i)). Whether the interquartile width is tied
to that regime is not known, and this page does not claim it is not.
1. **Every development day from 2018-04-04 (the draft).** **Default.**
2. Days after 2018-06-13, as A.

## 7. What this step does not do

- No fit on real data, no score, no goalpost, no comparison with R, S or R+S, and no refit path on the panel.
- No protocol change; no change to the parent, its pin, its panel, `sources_phase3.json` or any record.
- It does not rule on whether BGCR's volume is affected by the break, and it declares no estimator over a volume.
- Whether the width has the resolution to locate anything is left to M3, with the fact above.
