# H7m: the calendar-clean variants of candidate C (development)

Generated from `results/h7/calendar-clean.json` by `scripts/h7_calendar_clean.py --render`; never edited by hand.
Tier: **development**. Development evidence, not a verdict. Declaration: `docs/stages/h7-calendar-clean.md`. Variants added: **4**.

Panel version 4 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`; parent `08ff67e27bc3d7e357491cf8e1da59793702b3fb`; `effr` series `0b59d4e07ac43885f09ac212eb43da30feefa49221db1072b33532e271782ae1`; days 2018-04-03 to 2025-12-31; 2000 bootstrap draws; 70 refits from 2020-03-13 every 21 observation days, plus a final refit on 2025-12-31.

## The scarce episodes, with and without the calendar days

The floor of 60 scarce days is read on all days, the same for every variant; the clean variants then fit on the counted episode's clean days (declaration section 10, her ruling on PR #150).

| Candidate | Episode | Training days | Scarce | Clean days | Clean scarce | Counts (all variants) |
|---|---|---|---|---|---|---|
| C | 2018 to March 2020 | 486 | 477 | 351 | 344 | True |
| C | 2025 | 249 | 77 | 182 | 54 | True |

## Goalposts 1 and 2 on development days

| Estimator | Days | Objective | Left side | Refits | Not fitted | Status | Worst gap (pts) | Gp1 | Median width (pts) | Gp2 | Politis-White block, median (max) | Served days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C | all | ls | corridor | 70 | 0 | fitted: 70 | 0.000 | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) | 3.465 | does not hold | 3.9 (4.5) over 70 refits | 1447 |
| CV1 | clean | lad | corridor | 70 | 69 | fitted: 1, not identified: 69 | n/a | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) | no interval | does not hold | 33.6 (33.6) over 1 refits | 0 |
| CV2 | clean | lad | effr_corridor | 70 | 69 | fitted: 1, not identified: 69 | n/a | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) | no interval | does not hold | 33.7 (33.7) over 1 refits | 0 |
| CV3 | clean | ls | corridor | 70 | 0 | fitted: 70 | 0.000 | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) | 2.544 | holds | 19.1 (33.0) over 70 refits | 1447 |
| CV4 | all | lad | corridor | 70 | 69 | fitted: 1, not identified: 69 | n/a | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) | no interval | does not hold | 4.6 (4.6) over 1 refits | 0 |

**Goalpost 1 is unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6)** for C and CV1 to CV4 (declaration section 12); the Gp1 column carries that reading, and the worst gap beside it is a description of the gaps, not a reading of the goalpost.

Goalpost 1, were it read, is read on the gaps between consecutive refits on the days both serve; a refit that is not fitted or not identified serves nothing, so it makes no gap and is counted beside the figure. Goalpost 2's median counts a served day with no interval, and a day a refit left unserved, as over the limit.

The Politis-White block length (Politis and White 2004, with the correction of Patton, Politis and White 2009) is computed from each fitted refit's training residuals, taken in time order, and reported only. The bootstrap that gives the 90% interval keeps its mean block of 10: a figure far above it means the interval may be too narrow, and whether a longer block is needed is Eleonora's call on that figure. Days dropped or separated between episodes are not closed up or marked, as in the bootstrap itself.

## Each variant against its own baseline

| Variant | Against | Worst gap | Baseline | Median width | Baseline | Not fitted | Baseline not fitted |
|---|---|---|---|---|---|---|---|
| CV1 | C | n/a | 0.000 | no interval | 3.465 | 69 | 0 |
| CV2 | C | n/a | 0.000 | no interval | 3.465 | 69 | 0 |
| CV3 | C | 0.000 | 0.000 | 2.544 | 3.465 | 0 | 0 |
| CV4 | C | n/a | 0.000 | no interval | 3.465 | 69 | 0 |

## Training sample size at each refit (days fitted on)

| Refit | C | CV1 | CV2 | CV3 | CV4 |
|---|---|---|---|---|---|
| 2020-03-13 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-04-14 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-05-13 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-06-12 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-07-14 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-08-12 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-09-11 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-10-13 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-11-12 | 486 | not fitted | not fitted | 351 | not fitted |
| 2020-12-14 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-01-14 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-02-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-03-17 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-04-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-05-17 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-06-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-07-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-08-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-09-15 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-10-15 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-11-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2021-12-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-01-18 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-02-16 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-03-18 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-04-19 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-05-18 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-06-17 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-07-20 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-08-18 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-09-19 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-10-19 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-11-18 | 486 | not fitted | not fitted | 351 | not fitted |
| 2022-12-20 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-01-23 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-02-22 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-03-23 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-04-24 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-05-23 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-06-23 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-07-25 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-08-23 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-09-22 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-10-24 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-11-22 | 486 | not fitted | not fitted | 351 | not fitted |
| 2023-12-22 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-01-25 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-02-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-03-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-04-25 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-05-24 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-06-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-07-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-08-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-09-25 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-10-25 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-11-26 | 486 | not fitted | not fitted | 351 | not fitted |
| 2024-12-27 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-01-29 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-02-28 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-03-31 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-04-30 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-05-30 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-07-01 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-07-31 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-08-29 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-09-30 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-10-30 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-12-02 | 486 | not fitted | not fitted | 351 | not fitted |
| 2025-12-31 | 735 | 533 | 533 | 533 | 735 |

Days whose flags the parent's rule cannot read (left out of every clean fit): 2018-04-04.

## Not run

- D: not run (D dropped under #142); it does not count as a run variant.
- DV1: not run (D dropped under #142); it does not count as a run variant.
- DV2: not run (D dropped under #142); it does not count as a run variant.
- DV3: not run (D dropped under #142); it does not count as a run variant.
- DV4: not run (D dropped under #142); it does not count as a run variant.
