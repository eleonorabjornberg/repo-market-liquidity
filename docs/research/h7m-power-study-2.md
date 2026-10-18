# H7m, groundwork G6: the power study for goalpost 3, second record (milestone M7)

**Development evidence, never a verdict. No candidate is scored** (not A, not B, not step 1's estimator, not C): the
estimate is R plus a planted signal. This record supersedes PR #76's, which is archived unedited in
`archive/h7m-power-study-1/` with the reasons (finding #95). The declaration (`docs/stages/h7-g6.md`, §9 and §10) was
committed before any number of this record. Part B was amended twice before any Part B result, each in its own commit
that says so (§10): the replicates' event stream, and the planting, which a 12-replicate smoke run showed to overshoot. `docs/decisions/measurement-protocol.md` is unchanged. The record is
`docs/research/h7m-power-study-2.json` (`PYTHONPATH=src python3 scripts/g6_power_study.py`, about sixteen minutes on four
cores); the tables below are printed from it by `--tables` and not recomputed. Pins: model `8fd2cf8`, panel (version 1)
digest `acb77874…`; the parent's published panel digest is `4ddc3882…`.

**Which reading decides is Eleonora's (Q6, ruled 15 October 2026: "among windows at the floor").** This record reports
both readings side by side, each with its interval and its size, and picks none. Every figure below names its reading.

## What changed from the first record

| | First record (archived) | This record |
|---|---|---|
| Event floor counts | events in usable strata | events in the window (protocol §9) |
| Labelled days | 1,570, to 2025-12-31 | 1,739, to 2026-09-03 (225 events) |
| Seed | `SEED + start*10 + look` | `20261014 +` the window's first index |
| Calibration | realised gains missed 1e-4 at 0.02 and 0.065 | every realised gain within 1e-4 (table at the end of Part A) |
| 250-day windows | 67, of which 13 "at the floor" | 75, of which 21 at the floor |
| Power at 0.05, 250 days, every window | 15% (67 windows) | 19% (14/75; interval 4%–58%) |
| Power at 0.05, 250 days, windows at the floor | 77% (10 of 13, no interval; effective windows 1.04) | 67% (14/21; interval 14%–96%; effective windows 1.68) |
| Size at 250 days, every window / at the floor | 1% / 8%, the first quoted alone | 1% (1/75) / 5% (1/21) |

The window-event count, the extended labels and the seed changed together, so the differences are not attributed to one of
them.

## Headline (Part A: the second record on the 1,739 labelled days)

1. **On the reading "every window" the MME of 0.05 is not detectable at 250 days.** Power at 0.05 is 19% (14 of 75
   windows; interval 4%–58% at 6.0 effective windows); no grid gain reaches 80%. The size on this reading is 1% (1 of 75).
2. **On the reading "among windows at the floor" the MME is not shown to be detectable either, and the interval is very
   wide.** 21 of the 75 250-day windows hold at least 10 events in the window. Power at 0.05 is 67% (14 of 21; interval
   14%–96% at 1.68 effective windows, because the windows overlap heavily); the smallest grid gain at 80% is 0.08
   (19 of 21; interval 25%–100%). The size on this reading is 5% (1 of 21; interval 0%–72%).
3. **The two readings differ because of the eras, not the test.** The 21 windows at the floor are 10 that start to 2020
   (power at 0.05: 30%, 3 of 10), 3 that start in 2021-24 (all supported) and all 8 that start in 2025 (all supported at
   0.05 and above, 88% at 0.035). The 8 windows from 2025 carry the information of 0.64 independent windows, so this is
   one run of events seen eight times, not eight confirmations.
4. **Events remain the binding constraint.** The 1,739 scored days hold 225 material-use events: 190 in 2019-20, 1 in
   2021-24 and 34 in 2025 to 2026-09-03. From a start in 2021-24 the median wait for 10 events was 696 scored days; from a
   start in 2025, 87, and 9 of the 20 starts in 2025 never reach 10 before the data end.
5. **Shorter windows have little power on either reading.** At 125 days, power at 0.05 is 6% (every window; 5/81) and 29%
   (windows at the floor; 5/17); at 60 days it is 0% at 0.05 on both readings. The first
   two looks' nominal levels (6.3e-5 and 5.6e-3, Q3) make this by construction.
6. **The point estimate alone is at or above the MME in 16% of windows at 250 days under the null** (a gain is supported by the
   lower bound, not the point).

## Part B (avenue #98): events at the 2025-26 rate

A two-state chain fitted to the 418 labelled days from 2025-01-02 to 2026-09-03 (34 events, 8.1% of days): an event
follows a quiet day with probability 4.2% and follows an event day with probability 53%. Declared before the run
(`docs/stages/h7-g6.md` §10, Q7).

1. **Ten events arrive in about 125 days.** From a 2025 start, in 2,000 simulated series of 1,000 days, every series
   reaches 10 events; the median is 125 days (mean 133, 90th percentile 215), and 96% reach 10 within 250 days.
2. **At that rate and 250 days, the MME is not detectable on either reading.** Power at 0.05 is 21% (85 of 400
   replicates; interval 18%–26%) over every replicate and 22% (85 of 380; interval 18%–27%) over the 380 replicates that
   hold at least 10 events. The size is 5% (20 of 400; interval 3%–8%). No grid gain reaches 80% over every replicate
   (0.15: 78%); among replicates at the floor 0.15 reaches 82%.
3. **Part B is not comparable to Part A's 2025 windows.** In Part A the events are the real ones, which R already
   separates, and the 2025 windows are one overlapping run. In Part B they are drawn independently of R and S, so R has
   nothing to lose and the replicates are independent. The headline of Part B is the planning figure for days and events, and
   is a different thing from an estimator's power. It is not an input to the verdict, the MME or the floor.

## Tables (Part A)

| Era (of the day) | Scored days | Events |
|---|---|---|
| to 2020 | 323 | 190 |
| 2021-24 | 998 | 1 |
| 2025 on | 418 | 34 |
| all | 1739 | 225 |

**60-day windows, every window.** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 84 (28.00) | 0 / 0 / 60 | 0 / 0 / 52 | 0% (0/84; 0%–12%) | 0% (0/84; 0%–12%) | 0% (0/84; 0%–12%) | 0% (0/84; 0%–12%) | 2% (2/84; 0%–16%) | 2% (2/84; 0%–16%) | 4% (3/84; 1%–18%) | 4% (3/84; 1%–18%) | 4% (3/84; 1%–18%) |
| to 2020 | 17 (5.67) | 0 / 36 / 60 | 0 / 0 / 52 | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) |
| 2021-24 | 50 (16.67) | 0 / 0 / 1 | 0 / 0 / 1 | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) | 0% (0/50; 0%–19%) |
| 2025 on | 17 (5.67) | 0 / 2 / 26 | 0 / 2 / 26 | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 0% (0/17; 0%–40%) | 12% (2/17; 2%–53%) | 12% (2/17; 2%–53%) | 18% (3/17; 3%–58%) | 18% (3/17; 3%–58%) | 18% (3/17; 3%–58%) |

**60-day windows, windows at the floor (10 events in the window).** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 14 of 84 (4.67) | 0 / 0 / 60 | 0 / 0 / 52 | 0% (0/14; 0%–45%) | 0% (0/14; 0%–45%) | 0% (0/14; 0%–45%) | 0% (0/14; 0%–45%) | 14% (2/14; 2%–59%) | 14% (2/14; 2%–59%) | 21% (3/14; 4%–65%) | 21% (3/14; 4%–65%) | 21% (3/14; 4%–65%) |
| to 2020 | 10 of 17 (3.33) | 0 / 36 / 60 | 0 / 0 / 52 | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) | 0% (0/10; 0%–54%) |
| 2021-24 | 0 of 50 (0.00) | 0 / 0 / 1 | 0 / 0 / 1 | none | none | none | none | none | none | none | none | none |
| 2025 on | 4 of 17 (1.33) | 0 / 2 / 26 | 0 / 2 / 26 | 0% (0/4; 0%–74%) | 0% (0/4; 0%–74%) | 0% (0/4; 0%–74%) | 0% (0/4; 0%–74%) | 50% (2/4; 7%–93%) | 50% (2/4; 7%–93%) | 75% (3/4; 15%–98%) | 75% (3/4; 15%–98%) | 75% (3/4; 15%–98%) |

**125-day windows, every window.** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 81 (12.96) | 0 / 0 / 125 | 0 / 0 / 57 | 0% (0/81; 0%–23%) | 0% (0/81; 0%–23%) | 1% (1/81; 0%–25%) | 6% (5/81; 1%–31%) | 10% (8/81; 2%–36%) | 12% (10/81; 3%–39%) | 14% (11/81; 4%–40%) | 14% (11/81; 4%–40%) | 14% (11/81; 4%–40%) |
| to 2020 | 17 (2.72) | 0 / 36 / 125 | 0 / 5 / 57 | 0% (0/17; 0%–59%) | 0% (0/17; 0%–59%) | 0% (0/17; 0%–59%) | 0% (0/17; 0%–59%) | 12% (2/17; 1%–67%) | 18% (3/17; 2%–71%) | 24% (4/17; 3%–75%) | 24% (4/17; 3%–75%) | 24% (4/17; 3%–75%) |
| 2021-24 | 50 (8.00) | 0 / 0 / 1 | 0 / 0 / 1 | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) | 0% (0/50; 0%–32%) |
| 2025 on | 14 (2.24) | 1 / 11.5 / 31 | 1 / 11.5 / 31 | 0% (0/14; 0%–63%) | 0% (0/14; 0%–63%) | 7% (1/14; 0%–68%) | 36% (5/14; 6%–84%) | 43% (6/14; 8%–87%) | 50% (7/14; 10%–90%) | 50% (7/14; 10%–90%) | 50% (7/14; 10%–90%) | 50% (7/14; 10%–90%) |

**125-day windows, windows at the floor (10 events in the window).** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 17 of 81 (2.72) | 0 / 0 / 125 | 0 / 0 / 57 | 0% (0/17; 0%–59%) | 0% (0/17; 0%–59%) | 6% (1/17; 0%–63%) | 29% (5/17; 5%–78%) | 47% (8/17; 11%–87%) | 59% (10/17; 16%–92%) | 65% (11/17; 19%–94%) | 65% (11/17; 19%–94%) | 65% (11/17; 19%–94%) |
| to 2020 | 10 of 17 (1.60) | 0 / 36 / 125 | 0 / 5 / 57 | 0% (0/10; 0%–71%) | 0% (0/10; 0%–71%) | 0% (0/10; 0%–71%) | 0% (0/10; 0%–71%) | 20% (2/10; 1%–81%) | 30% (3/10; 3%–85%) | 40% (4/10; 5%–89%) | 40% (4/10; 5%–89%) | 40% (4/10; 5%–89%) |
| 2021-24 | 0 of 50 (0.00) | 0 / 0 / 1 | 0 / 0 / 1 | none | none | none | none | none | none | none | none | none |
| 2025 on | 7 of 14 (1.12) | 1 / 11.5 / 31 | 1 / 11.5 / 31 | 0% (0/7; 0%–77%) | 0% (0/7; 0%–77%) | 14% (1/7; 1%–83%) | 71% (5/7; 12%–98%) | 86% (6/7; 17%–99%) | 100% (7/7; 23%–100%) | 100% (7/7; 23%–100%) | 100% (7/7; 23%–100%) | 100% (7/7; 23%–100%) |

**250-day windows, every window.** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 75 (6.00) | 0 / 0 / 190 | 0 / 0 / 57 | 1% (1/75; 0%–41%) | 4% (3/75; 0%–44%) | 15% (11/75; 2%–55%) | 19% (14/75; 4%–58%) | 20% (15/75; 4%–59%) | 25% (19/75; 6%–64%) | 27% (20/75; 7%–65%) | 27% (20/75; 7%–65%) | 27% (20/75; 7%–65%) |
| to 2020 | 17 (1.36) | 0 / 36 / 190 | 0 / 36 / 57 | 0% (0/17; 0%–74%) | 0% (0/17; 0%–74%) | 12% (2/17; 0%–80%) | 18% (3/17; 1%–82%) | 24% (4/17; 2%–84%) | 47% (8/17; 6%–92%) | 53% (9/17; 8%–94%) | 53% (9/17; 8%–94%) | 53% (9/17; 8%–94%) |
| 2021-24 | 50 (4.00) | 0 / 0 / 30 | 0 / 0 / 30 | 0% (0/50; 0%–49%) | 0% (0/50; 0%–49%) | 4% (2/50; 0%–53%) | 6% (3/50; 0%–55%) | 6% (3/50; 0%–55%) | 6% (3/50; 0%–55%) | 6% (3/50; 0%–55%) | 6% (3/50; 0%–55%) | 6% (3/50; 0%–55%) |
| 2025 on | 8 (0.64) | 31 / 33 / 34 | 31 / 33 / 34 | 12% (1/8; 0%–89%) | 38% (3/8; 2%–94%) | 88% (7/8; 11%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) |

**250-day windows, windows at the floor (10 events in the window).** Each cell: supported share (supported/windows; 95% Wilson interval at the effective number of windows)

| Era of the first day | Windows (effective) | Events in the window (min / median / max) | Events in usable strata (min / median / max) | gain 0.0 | gain 0.02 | gain 0.035 | gain 0.05 | gain 0.065 | gain 0.08 | gain 0.1 | gain 0.125 | gain 0.15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 21 of 75 (1.68) | 0 / 0 / 190 | 0 / 0 / 57 | 5% (1/21; 0%–72%) | 14% (3/21; 1%–77%) | 52% (11/21; 9%–92%) | 67% (14/21; 14%–96%) | 71% (15/21; 16%–97%) | 90% (19/21; 25%–100%) | 95% (20/21; 28%–100%) | 95% (20/21; 28%–100%) | 95% (20/21; 28%–100%) |
| to 2020 | 10 of 17 (0.80) | 0 / 36 / 190 | 0 / 36 / 57 | 0% (0/10; 0%–83%) | 0% (0/10; 0%–83%) | 20% (2/10; 1%–89%) | 30% (3/10; 2%–91%) | 40% (4/10; 3%–94%) | 80% (8/10; 11%–99%) | 90% (9/10; 14%–100%) | 90% (9/10; 14%–100%) | 90% (9/10; 14%–100%) |
| 2021-24 | 3 of 50 (0.24) | 0 / 0 / 30 | 0 / 0 / 30 | 0% (0/3; 0%–94%) | 0% (0/3; 0%–94%) | 67% (2/3; 3%–99%) | 100% (3/3; 6%–100%) | 100% (3/3; 6%–100%) | 100% (3/3; 6%–100%) | 100% (3/3; 6%–100%) | 100% (3/3; 6%–100%) | 100% (3/3; 6%–100%) |
| 2025 on | 8 of 8 (0.64) | 31 / 33 / 34 | 31 / 33 / 34 | 12% (1/8; 0%–89%) | 38% (3/8; 2%–94%) | 88% (7/8; 11%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) | 100% (8/8; 14%–100%) |

**Size** (the supported share at gain 0, pooled over eras; the two readings side by side)

| Window | Every window | Windows at the floor | Lower bound above 0 (every window) | Point at or above the MME (every window) | Mean point (every window) |
|---|---|---|---|---|---|
| 60 days | 0% (0/84; 0%–12%) | 0% (0/14; 0%–45%) | 0% | 10% | +0.0107 |
| 125 days | 0% (0/81; 0%–23%) | 0% (0/17; 0%–59%) | 0% | 16% | +0.0150 |
| 250 days | 1% (1/75; 0%–41%) | 5% (1/21; 0%–72%) | 1% | 16% | +0.0088 |

**Days to 10 events** (observed, from every 20th scored day; era of the start)

| Era | Starts | Never reach 10 | Median days | 90th percentile |
|---|---|---|---|---|
| to 2020 | 17 | 0 | 13 | 1286 |
| 2021-24 | 50 | 0 | 696 | 1086 |
| 2025 on | 20 | 9 | 87 | 167 |

**The MME at 250 days** (power at gain 0.05, both readings)

| Scope | Every window | Detectable (80%) | Smallest grid gain at 80% | Windows at the floor | Detectable (80%) | Smallest grid gain at 80% |
|---|---|---|---|---|---|---|
| pooled | 19% (4%–58%; 75 windows) | False | none on the grid | 67% (14%–96%; 21 windows) | False | 0.08 |
| to 2020 | 18% (1%–82%; 17 windows) | False | none on the grid | 30% (2%–91%; 10 windows) | False | 0.08 |
| 2021-24 | 6% (0%–55%; 50 windows) | False | none on the grid | 100% (6%–100%; 3 windows) | True | 0.05 |
| 2025 on | 100% (14%–100%; 8 windows) | True | 0.035 | 100% (14%–100%; 8 windows) | True | 0.035 |

**Planting: realised gain on the whole span against the target** (tolerance 0.0001)

| Target | Shift (sigma) | Realised gain | Miss |
|---|---|---|---|
| 0.0 (the null: tie-breaking noise only) | 0.000000 | 0.011109 | +1.11e-02 |
| 0.02 | 0.019719 | 0.019987 | -1.29e-05 |
| 0.035 | 0.051060 | 0.034991 | -8.58e-06 |
| 0.05 | 0.083240 | 0.049993 | -7.48e-06 |
| 0.065 | 0.115587 | 0.065001 | +6.26e-07 |
| 0.08 | 0.151250 | 0.080001 | +5.69e-07 |
| 0.1 | 0.207312 | 0.099987 | -1.28e-05 |
| 0.125 | 0.288158 | 0.125009 | +9.20e-06 |
| 0.15 | 0.400429 | 0.150006 | +5.85e-06 |

## Tables (Part B)

| Process fitted to | Labelled days | Events | P(event, after a quiet day) | P(event, after an event day) | Long-run share | Transitions from quiet / event |
|---|---|---|---|---|---|---|
| 2025-01-02 to 2026-09-03 | 418 | 34 | 0.0418 | 0.5294 | 0.0815 | 383 / 34 |

**Days until 10 events are logged**, from day 0 (2000 simulated series of 1000 days)

| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median (of those that reach) | 90th percentile (of those that reach) |
|---|---|---|---|---|
| 0% (0 of 2000) | 96% | 133.3 | 125 | 215 |

**Power at 250 days** (400 replicates from 2025-01-02, 10,000 draws; events per replicate 5 / 20 / 52; 380 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval at the replicates)

| Gain | Every replicate | Replicates at the floor | Point at or above the MME | Mean point |
|---|---|---|---|---|
| 0.0 (size) | 5% (20/400; 3%–8%) | 5% (20/380; 3%–8%) | 22% | +0.0074 |
| 0.02 | 10% (42/400; 8%–14%) | 11% (42/380; 8%–15%) | 34% | +0.0275 |
| 0.035 | 14% (57/400; 11%–18%) | 15% (57/380; 12%–19%) | 44% | +0.0427 |
| 0.05 | 21% (85/400; 18%–26%) | 22% (85/380; 18%–27%) | 56% | +0.0574 |
| 0.065 | 29% (117/400; 25%–34%) | 31% (117/380; 26%–36%) | 64% | +0.0721 |
| 0.08 | 39% (157/400; 35%–44%) | 41% (157/380; 36%–46%) | 74% | +0.0868 |
| 0.1 | 50% (201/400; 45%–55%) | 53% (201/380; 48%–58%) | 83% | +0.1063 |
| 0.125 | 67% (267/400; 62%–71%) | 70% (267/380; 65%–75%) | 90% | +0.1309 |
| 0.15 | 78% (312/400; 74%–82%) | 82% (312/380; 78%–86%) | 95% | +0.1555 |

**Planting: mean gain on the 200 reference series against the target**

| Target | Shift (sigma) | Mean gain | Miss |
|---|---|---|---|
| 0.0 (the null) | 0.000000 | -0.000374 | -3.74e-04 |
| 0.02 | 0.011220 | 0.019997 | -3.42e-06 |
| 0.035 | 0.019519 | 0.034998 | -2.46e-06 |
| 0.05 | 0.027780 | 0.050000 | +1.23e-07 |
| 0.065 | 0.036132 | 0.065001 | +6.30e-07 |
| 0.08 | 0.044565 | 0.080007 | +6.66e-06 |
| 0.1 | 0.055795 | 0.100000 | +2.58e-07 |
| 0.125 | 0.070091 | 0.124999 | -8.63e-07 |
| 0.15 | 0.084609 | 0.150001 | +6.54e-07 |

## What this study does and does not show

- **It shows** how often the declared test would support a planted gain of a given size in windows of 60, 125 and 250
  days replayed over 2019-09-17 to 2026-09-03, on two readings with their intervals and sizes, and how many days and
  events a window holds; and, in Part B, how many days ten events take and how often the test would support a planted
  gain if events came at the 2025-26 rate.
- **It does not show** that any estimator carries information beyond R and S. Goalposts 1 and 2 are assumed to hold; the
  planted estimates have no refit history or interval width.
- **Windows overlap** (every 20th day), so the intervals are Wilson intervals at the effective number of windows, and they
  are wide. A share of 100% in 8 windows is not evidence of certainty.
- **Draws.** 100,000 at the first two looks (the model repo's ruling of 13 October 2026) and 10,000 at the third. Each
  window shares its resamples across the grid, so the grid's columns are paired.
- **The null is not exactly zero.** At gain 0 the estimate is R plus tie-breaking noise, which moves the statistic by
  about +0.011 on the whole span (the first row of the planting table); the size figures are rates under that null.

## Marked questions for Eleonora (none is settled in code)

- **Q2 and Q6 (the MME, the floor and the deciding reading)** are ruled (15 October 2026) and unchanged here. She is to
  reconfirm them on these corrected figures before H7m registration; the headline above gives the two readings
  side by side with their intervals.
- **Q7. The event process of Part B.** Whether a two-state chain fitted to 2025-01-02 to 2026-09-03 is the process to plan
  the confirmation window against, or a different calibration window, a longer memory, or events tied to calendar dates
  should replace it (`docs/stages/h7-g6.md` §10).
