# H7m, groundwork G6: the power study for goalpost 3 (milestone M7)

**Development evidence, never a verdict. No candidate is scored** (not A, not B, not step 1's estimator, not C): the
estimate is R plus a planted signal. The declaration (`docs/stages/h7-g6.md`) was committed before any number
(`68e35fa`). `docs/decisions/measurement-protocol.md` is unchanged. The record is `docs/research/h7m-power-study.json`
(`PYTHONPATH=src python3 scripts/g6_power_study.py`, about four minutes on four cores); the tables below are printed from
it by `--tables` and not recomputed. Pins: model 53e61af, panel (version 1) digest `acb77874…`; the parent's published
panel digest is `4ddc3882…`.

## Headline

1. **On the declared reading the MME of 0.05 AUROC points is not detectable at 250 days.** The power at 0.05 is 15% over
   all 67 windows, 41% in windows that start before 2021, and 6% in 2021–24. No grid gain reaches 80% on that reading.
2. **The binding constraint is the event floor, not the days.** The 1,570 scored days hold 221 material-use events: 190
   in 2019–20, 1 in 2021–24 and 30 in 2025. Only 13 of the 67 250-day windows hold the 10 events §9 requires. From a
   start in 2021–24 the median wait for 10 events was 696 scored days, and from a start in 2025, 87.
3. **Among the windows that reach the floor, 250 days detect 0.05 about three times in four and 0.065 at 80%.** (10 of 13
   windows at 0.05, 11 of 13 at 0.065. These windows overlap heavily: the effective count is far smaller, and the
   intervals are wide.) At 125 days no grid gain reaches 80% (70% at 0.15), and at 60 days none exceeds 29%.
4. **The first two looks have almost no power by construction.** The nominal levels are 6.3e-5 (60 days) and 5.6e-3 (125
   days), so a bound above 0 there needs an extreme resample (marked question Q3).
5. **Size is small.** Under the null (R plus tie-breaking noise, gain about 0) the test supports 0% of windows at 60 and
   125 days and 1% at 250. The point estimate alone is at or above 0.05 in 4%, 10% and 13% of windows: the lower bound,
   not the point, is what keeps the size down.

Read with care: windows start every 20 days and overlap, so the Wilson intervals are taken at the effective number of
windows, and most of them are wide. The events come in two clusters (2019–20, 2025), so the power depends on whether the
future resembles them. The planting shifts event days by a constant (an oracle signal); a real estimator's information
would be noisier.

## Tables
| Era (of the day) | Scored days | Events |
|---|---|---|
| to 2020 | 323 | 190 |
| 2021-24 | 998 | 1 |
| 2025 on | 249 | 30 |
| all | 1570 | 221 |

**60-day windows** (power = share of windows supported; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events per window (min / median / max) | Windows with at least 10 events | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 76 (25.3) | 0 / 0 / 60 | 12 | 0% (0%–13%) | 0% (0%–13%) | 0% (0%–13%) | 1% (0%–15%) | 1% (0%–15%) | 3% (0%–17%) | 3% (0%–17%) | 3% (0%–17%) | 3% (0%–17%) |
| to 2020 | 17 (5.7) | 0 / 36 / 60 | 10 | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) | 0% (0%–40%) |
| 2021-24 | 50 (16.7) | 0 / 0 / 1 | 0 | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) | 0% (0%–19%) |
| 2025 on | 9 (3.0) | 0 / 1 / 24 | 2 | 0% (0%–56%) | 0% (0%–56%) | 0% (0%–56%) | 11% (1%–65%) | 11% (1%–65%) | 22% (3%–73%) | 22% (3%–73%) | 22% (3%–73%) | 22% (3%–73%) |

**125-day windows** (power = share of windows supported; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events per window (min / median / max) | Windows with at least 10 events | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 73 (11.7) | 0 / 0 / 125 | 12 | 0% (0%–25%) | 1% (0%–27%) | 3% (0%–29%) | 3% (0%–29%) | 5% (1%–32%) | 7% (1%–34%) | 8% (1%–36%) | 8% (1%–36%) | 10% (2%–37%) |
| to 2020 | 17 (2.7) | 0 / 36 / 125 | 10 | 0% (0%–59%) | 0% (0%–59%) | 0% (0%–59%) | 0% (0%–59%) | 12% (1%–67%) | 18% (2%–71%) | 24% (3%–75%) | 24% (3%–75%) | 29% (5%–78%) |
| 2021-24 | 50 (8.0) | 0 / 0 / 1 | 0 | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) | 0% (0%–32%) |
| 2025 on | 6 (1.0) | 1 / 5 / 26 | 2 | 0% (0%–80%) | 17% (1%–86%) | 33% (2%–91%) | 33% (2%–91%) | 33% (2%–91%) | 33% (2%–91%) | 33% (2%–91%) | 33% (2%–91%) | 33% (2%–91%) |

**250-day windows** (power = share of windows supported; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events per window (min / median / max) | Windows with at least 10 events | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 67 (5.4) | 0 / 0 / 190 | 13 | 1% (0%–43%) | 4% (0%–47%) | 9% (1%–51%) | 15% (2%–57%) | 16% (3%–58%) | 18% (3%–59%) | 18% (3%–59%) | 18% (3%–59%) | 18% (3%–59%) |
| to 2020 | 17 (1.4) | 0 / 36 / 190 | 10 | 0% (0%–74%) | 6% (0%–77%) | 18% (1%–82%) | 41% (5%–90%) | 47% (6%–92%) | 53% (8%–94%) | 53% (8%–94%) | 53% (8%–94%) | 53% (8%–94%) |
| 2021-24 | 50 (4.0) | 0 / 0 / 30 | 3 | 2% (0%–51%) | 4% (0%–53%) | 6% (0%–55%) | 6% (0%–55%) | 6% (0%–55%) | 6% (0%–55%) | 6% (0%–55%) | 6% (0%–55%) | 6% (0%–55%) |
| 2025 on | 0 | none | none | none | none | none | none | none | none | none | none | none |

**Among the windows with at least 10 events** (supported share; pooled over eras)

| Window | Windows at the floor | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|
| 60 days | 12 of 76 | 0% | 0% | 0% | 14% | 14% | 29% | 29% | 29% | 29% |
| 125 days | 12 of 73 | 0% | 10% | 20% | 20% | 40% | 50% | 60% | 60% | 70% |
| 250 days | 13 of 67 | 8% | 23% | 46% | 77% | 85% | 92% | 92% | 92% | 92% |

**Size and the mean statistic at gain 0** (pooled)

| Window | Supported | Lower bound above 0 | Point at or above the MME | Mean point |
|---|---|---|---|---|
| 60 days | 0% | 0% | 4% | -0.0026 |
| 125 days | 0% | 0% | 10% | +0.0042 |
| 250 days | 1% | 1% | 13% | +0.0127 |

**Days to 10 events** (from every 20th scored day; era of the start)

| Era | Starts | Never reach 10 | Median days | 90th percentile |
|---|---|---|---|---|
| to 2020 | 17 | 0 | 13 | 1286 |
| 2021-24 | 50 | 0 | 696 | 1086 |
| 2025 on | 12 | 1 | 87 | 167 |

**The MME at 250 days**

| Scope | Power at 0.05 | Detectable (80%) | Smallest grid gain at 80% |
|---|---|---|---|
| pooled | 15% | False | none on the grid |
| to 2020 | 41% | False | none on the grid |
| 2021-24 | 6% | False | none on the grid |
| 2025 on | n/a | n/a | none on the grid |

## What this study does and does not show

- **It shows** how often the declared test would support a planted gain of a given size in windows of 60, 125 and 250
  days replayed over 2019-09-17 to 2025-12-31, and how many days and events a window holds.
- **It does not show** that any estimator carries information beyond R and S. Goalposts 1 and 2 are assumed to hold; the
  planted estimates have no refit history or interval width.
- **Labelled days end on 2025-12-31**, not 2026-09-03 as the directive assumed: the parent has no material-use event
  after its repo-operation snapshots end (Q1; finding #75). R and S are read to 2026-09-03; 169 days in 2019–21 with no
  Desk operation row carry no label under the parent's rule (#659) and are dropped.
- **Draws.** 100,000 at the first two looks (the model repo's ruling of 13 October 2026) and 10,000 at the third. Each
  window shares its resamples across the grid, so the grid's columns are paired.

## Marked questions for Eleonora (none is settled in code)

- **Q1. The event after 2025-12-31.** What defines it? The 2026 standing-repo take-up in `nyfed_srf` shows $9bn to $31bn
  on four dates, which the parent's module reads as zero. This is data meaning, and hers.
- **Q2. The MME and the event floor.** The MME of 0.05 is detectable at 250 days only in windows that reach 10 events,
  and then at about 77%. Whether to keep 0.05, raise it to 0.065, or lower the floor or the bar is hers, once, before
  registration (protocol §5, §9). The study changes neither.
- **Q3. Look 1.** The O'Brien–Fleming boundary gives 6.3e-5 at 60 days. The power there is at most 3% pooled (22% in the nine windows that start in 2025, with a Wilson interval from 3% to 73%).
- **Q4. The upper bound for "killed".** The protocol gives no level; `goalposts.verdict` has no default.
- **Q5. The null and the planting** are the study's declared choices, not the protocol's.
- **Q6. The reading rule.** The declared rule counts every window, including those that can never hold 10 events. The
  table above also gives the rate among windows at the floor. Which of the two answers "is 0.05 detectable" is hers.
