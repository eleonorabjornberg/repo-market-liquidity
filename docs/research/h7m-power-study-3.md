# H7m, groundwork G6: the power study for goalpost 3, third record (milestone M7)

**Development evidence, never a verdict. No candidate is scored** (not A, not B, not step 1's estimator, not C): the
estimate is R plus a planted signal. The declaration (`docs/stages/h7-g6.md` §11, directive #126) was committed before any
number or any code of this record. It re-declares record 2's Part B with the planting stated up front, fresh seeds
(`B = 2026101900`), three event processes (independent, two-state, calendar-tied) and two power-raising options (window
lengths 250, 500 and 750 days; a calendar-stratified statistic). The record is `docs/research/h7m-power-study-3.json`,
assembled from three per-process parts run on Eleonora's Mac (commit `c3f4c83`); the tables below are printed from it by
`PYTHONPATH=src python3 scripts/g6_power_study.py --third --tables` and are not recomputed or edited. Pins: model
`8fd2cf8`, panel (version 1) digest `acb77874…`; the parent's published panel digest is `4ddc3882…`. Record 2
(`h7m-power-study-2.*`) is unchanged.

**What it does not change:** the verdict rule, the MME (0.05), the event floor (10 events in the window), the deciding
reading ("among replicates at the floor", Q6) and the nominal levels (Q2). Every figure is a planning figure. No option is
adopted until Eleonora rules on it separately.

Cells below are quoted on the deciding reading (replicates at the floor) at the MME gain 0.05, with 95% Wilson intervals
at the replicates, unless a line says otherwise. The tables carry both readings.

## Headline

1. **Ten events arrive in about 120 days under every process.** Median days to 10 events: 120 (independent), 122
   (two-state), 124.5 (calendar-tied). The share that reach 10 within 250 days is 100%, 95% and 98%; none fails to reach
   it in 1,000 days. The calendar-tied process does not change this planning figure materially.
2. **At 250 days the MME is not shown to be detectable under any process or test.** Power at 0.05 on the section 5
   statistic is 22% (88 of 399; interval 18%–26%) independent, 17% (63 of 378; 13%–21%) two-state and 22% (86 of 388;
   18%–27%) calendar-tied. The grid gain that reaches about 80% is 0.15 (independent: 319 of 399, 79.9%; calendar-tied:
   83%) or is not reached (two-state: 77% at 0.15).
3. **Longer windows are what buys power.** On the section 5 statistic, power at 0.05 rises from 17%–22% at 250 days to
   28%–31% at 500 days (independent 31%, 26%–35%; two-state 28%, 24%–33%; calendar-tied 28%, 24%–33%) and to 45%–51% at
   750 days (independent 51%, 46%–56%; two-state 45%, 40%–50%; calendar-tied 50%, 46%–55%). At 750 days 0.08 reaches 82%
   or more under all three processes (independent 91%, two-state 82%, calendar-tied 87%), and the MME itself is still
   below 80%. At 500 days 80% is reached at 0.10 (independent, 82%) or 0.125 (two-state 85%, calendar-tied 91%).
4. **The calendar-stratified statistic buys nothing at the same planted signal.** In no cell at 250 or 500 days is its
   power at the MME at or above the section 5 statistic's: 17% against 22% (independent, 250), 11% against 17%
   (two-state, 250), 17% against 22% (calendar-tied, 250), 26% against 31%, 24% against 28% and 22% against 28% at 500
   days. At 750 days the two are within each other's intervals at every gain. Its size at gain 0 is 2%–4% against 2%–6%,
   and it drops 4 to 10 of its 15 strata on average. The finer strata spend events on strata that cannot be compared,
   which is what the "dropped" column counts.
5. **Size.** At gain 0, on replicates at the floor, the section 5 statistic's size is 2%–6% and the calendar-stratified
   one's 2%–4%. The nominal level of the third look is 4.8%; two 250-day cells sit above it (independent 5.5%, 22 of 399;
   calendar-tied 6.2%, 24 of 388) with intervals that include it. Planting met its tolerance: every realised mean gain is
   within 1e-4 of its target, except the null row, which is the tie-breaking offset (up to +8.6e-03), as in record 2.
6. **The calendar-tied process is close to the independent one in power.** Its fitted coefficients are modest (logit:
   previous event +2.50, coupon-mid +1.53, coupon-end +0.77, quarter-end +0.72, year-end +0.13, ridge 1.0): a quiet mid-month
   coupon day has a fitted event probability of 17% against 4% on an ordinary day. Its power at 0.05 (22%, 28%, 50% at 250,
   500, 750 days) is within 3 points of the independent process's (22%, 31%, 51%) at every length.

## Comparison with record 2's Part B (the PR's "Must show")

The two-state process, 250 days, the section 5 statistic, is record 2's Part B run again with fresh seeds and the planting
stated up front. Record 3's cell is under "two_state, 250 days" below; record 2's is in `h7m-power-study-2.md`, "Tables
(Part B)".

| Gain | Record 2, every replicate | Record 3, every replicate | Record 2, at the floor | Record 3, at the floor |
|---|---|---|---|---|
| 0.0 (size) | 5% (3%–8%) | 4% (2%–6%) | 5% (3%–8%) | 4% (3%–7%) |
| 0.02 | 10% (8%–14%) | 5% (3%–8%) | 11% (8%–15%) | 6% (4%–8%) |
| 0.035 | 14% (11%–18%) | 8% (6%–11%) | 15% (12%–19%) | 8% (6%–12%) |
| 0.05 | 21% (18%–26%) | 16% (13%–20%) | 22% (18%–27%) | 17% (13%–21%) |
| 0.065 | 29% (25%–34%) | 22% (18%–27%) | 31% (26%–36%) | 24% (20%–28%) |
| 0.08 | 39% (35%–44%) | 30% (26%–35%) | 41% (36%–46%) | 32% (28%–37%) |
| 0.1 | 50% (45%–55%) | 40% (35%–45%) | 53% (48%–58%) | 42% (37%–47%) |
| 0.125 | 67% (62%–71%) | 60% (55%–64%) | 70% (65%–75%) | 63% (58%–68%) |
| 0.15 | 78% (74%–82%) | 72% (68%–77%) | 82% (78%–86%) | 77% (72%–81%) |

**They agree at the size and at the MME, and they do not agree everywhere.** The size (4% against 5%) and power at 0.05
(17% against 22% at the floor; 16% against 21% over every replicate) lie within each other's intervals. Record 3 is below
record 2 at every gain above 0 on both readings, by 5 to 11 points; on the deciding reading the intervals do not overlap
at 0.065 (24%, 20%–28%, against 31%, 26%–36%) or at 0.10 (42%, 37%–47%, against 53%, 48%–58%), and they only touch at 0.02
and 0.035. Over every replicate they do not overlap at 0.02. The process, the days and the test are the same; the seeds
differ, and so do the planted shifts (to reach 0.05 the shift is 0.0237 sigma here and 0.0278 sigma in record 2), because
the shift is calibrated again on 200 reference series drawn from fresh seeds. This record does not isolate what moves the
difference, so it does not say that either record is the better planning figure. Eleonora decides whether the gap needs a
further run.

## Which option buys what

- **Longer windows** buy the most (headline 3). They use real R and S from before 2025 with events at the 2025-26 rate
  (§11.6), so the 500- and 750-day cells are planning figures conditional on that rate, not a measurement of how much a
  longer confirmation will contain. Whether the Lan-DeMets levels, set for 250 days, apply to a longer horizon is not
  decided here (§11.4): hers.
- **Calendar strata** buy nothing (headline 4).
- **The calendar-tied process** changes the planning figures little (headline 6), at the cost of a fit to two years of
  calendar.

## Tables

### Process: independent

Fitted to 2025-01-02 to 2026-09-03 (418 labelled days, 34 events): share 0.0813

**Days until 10 events are logged** (2000 simulated series of 1000 days)

| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median | 90th percentile |
|---|---|---|---|---|
| 0% (0 of 2000) | 100% | 123.7 | 120.0 | 174 |

**independent, 250 days** (2025-01-02 to 2026-01-02; 400 replicates, 10,000 draws; events per replicate 9 / 20 / 32; 399 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 6% (22/400; 4%–8%) | 6% (22/399; 4%–8%) | 4% (16/400; 2%–6%) | 4% (16/399; 2%–6%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.02 | 8% (32/400; 6%–11%) | 8% (32/399; 6%–11%) | 7% (27/400; 5%–10%) | 7% (27/399; 5%–10%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.035 | 14% (54/400; 10%–17%) | 14% (54/399; 11%–17%) | 11% (43/400; 8%–14%) | 11% (43/399; 8%–14%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.05 | 22% (88/400; 18%–26%) | 22% (88/399; 18%–26%) | 16% (66/400; 13%–20%) | 17% (66/399; 13%–21%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.065 | 33% (131/400; 28%–37%) | 33% (131/399; 28%–38%) | 25% (101/400; 21%–30%) | 25% (101/399; 21%–30%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.08 | 43% (171/400; 38%–48%) | 43% (171/399; 38%–48%) | 35% (141/400; 31%–40%) | 35% (141/399; 31%–40%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.1 | 55% (219/400; 50%–60%) | 55% (219/399; 50%–60%) | 47% (189/400; 42%–52%) | 47% (189/399; 43%–52%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.125 | 74% (294/400; 69%–78%) | 74% (294/399; 69%–78%) | 66% (264/400; 61%–70%) | 66% (264/399; 61%–71%) | 3.9 / 0.1; 5.8 / 9.2 |
| 0.15 | 86% (342/400; 82%–89%) | 86% (342/399; 82%–89%) | 80% (319/400; 76%–83%) | 80% (319/399; 76%–84%) | 3.9 / 0.1; 5.8 / 9.2 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss +5.6e-03), 0.02: 0.0076 (miss -5.5e-07), 0.035: 0.0162 (miss +7.8e-07), 0.05: 0.0244 (miss +3.0e-06), 0.065: 0.0328 (miss -6.4e-07), 0.08: 0.0412 (miss -1.8e-06), 0.1: 0.0521 (miss -2.4e-06), 0.125: 0.0664 (miss +1.3e-07), 0.15: 0.0810 (miss +1.9e-06)

**independent, 500 days** (2024-09-03 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 23 / 40 / 57; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 4% (16/400; 2%–6%) | 4% (16/400; 2%–6%) | 3% (13/400; 2%–5%) | 3% (13/400; 2%–5%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.02 | 9% (35/400; 6%–12%) | 9% (35/400; 6%–12%) | 8% (32/400; 6%–11%) | 8% (32/400; 6%–11%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.035 | 17% (68/400; 14%–21%) | 17% (68/400; 14%–21%) | 15% (60/400; 12%–19%) | 15% (60/400; 12%–19%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.05 | 31% (123/400; 26%–35%) | 31% (123/400; 26%–35%) | 26% (103/400; 22%–30%) | 26% (103/400; 22%–30%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.065 | 47% (189/400; 42%–52%) | 47% (189/400; 42%–52%) | 42% (167/400; 37%–47%) | 42% (167/400; 37%–47%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.08 | 62% (247/400; 57%–66%) | 62% (247/400; 57%–66%) | 57% (227/400; 52%–62%) | 57% (227/400; 52%–62%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.1 | 82% (328/400; 78%–85%) | 82% (328/400; 78%–85%) | 76% (303/400; 71%–80%) | 76% (303/400; 71%–80%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.125 | 93% (373/400; 90%–95%) | 93% (373/400; 90%–95%) | 88% (353/400; 85%–91%) | 88% (353/400; 85%–91%) | 4.0 / 0.0; 8.0 / 7.0 |
| 0.15 | 98% (391/400; 96%–99%) | 98% (391/400; 96%–99%) | 96% (383/400; 93%–97%) | 96% (383/400; 93%–97%) | 4.0 / 0.0; 8.0 / 7.0 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss +3.1e-03), 0.02: 0.0086 (miss -5.9e-07), 0.035: 0.0161 (miss -6.1e-07), 0.05: 0.0237 (miss -5.8e-07), 0.065: 0.0314 (miss -4.3e-07), 0.08: 0.0391 (miss +1.0e-08), 0.1: 0.0496 (miss +4.9e-07), 0.125: 0.0627 (miss +2.7e-07), 0.15: 0.0761 (miss +3.2e-07)

**independent, 750 days** (2023-09-01 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 42 / 60 / 81; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 2% (9/400; 1%–4%) | 2% (9/400; 1%–4%) | 2% (9/400; 1%–4%) | 2% (9/400; 1%–4%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.02 | 11% (44/400; 8%–14%) | 11% (44/400; 8%–14%) | 12% (48/400; 9%–16%) | 12% (48/400; 9%–16%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.035 | 28% (112/400; 24%–33%) | 28% (112/400; 24%–33%) | 28% (112/400; 24%–33%) | 28% (112/400; 24%–33%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.05 | 51% (204/400; 46%–56%) | 51% (204/400; 46%–56%) | 51% (203/400; 46%–56%) | 51% (203/400; 46%–56%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.065 | 75% (301/400; 71%–79%) | 75% (301/400; 71%–79%) | 74% (294/400; 69%–78%) | 74% (294/400; 69%–78%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.08 | 91% (364/400; 88%–93%) | 91% (364/400; 88%–93%) | 88% (353/400; 85%–91%) | 88% (353/400; 85%–91%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.1 | 98% (392/400; 96%–99%) | 98% (392/400; 96%–99%) | 98% (391/400; 96%–99%) | 98% (391/400; 96%–99%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.125 | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 4.0 / 0.0; 8.6 / 6.4 |
| 0.15 | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 4.0 / 0.0; 8.6 / 6.4 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss -5.8e-04), 0.02: 0.0140 (miss -1.3e-07), 0.035: 0.0243 (miss +2.2e-07), 0.05: 0.0345 (miss -2.8e-07), 0.065: 0.0449 (miss +2.0e-07), 0.08: 0.0553 (miss -2.6e-07), 0.1: 0.0694 (miss -8.9e-08), 0.125: 0.0876 (miss +7.3e-08), 0.15: 0.1063 (miss +1.6e-07)

### Process: two_state

Fitted to 2025-01-02 to 2026-09-03 (418 labelled days, 34 events): start 0.0418, stay 0.5294, stationary 0.0815, transitions_from_quiet 383, transitions_from_event 34

**Days until 10 events are logged** (2000 simulated series of 1000 days)

| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median | 90th percentile |
|---|---|---|---|---|
| 0% (0 of 2000) | 95% | 131.8 | 122.0 | 218 |

**two_state, 250 days** (2025-01-02 to 2026-01-02; 400 replicates, 10,000 draws; events per replicate 4 / 20 / 44; 378 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 4% (16/400; 2%–6%) | 4% (16/378; 3%–7%) | 4% (14/400; 2%–6%) | 4% (14/378; 2%–6%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.02 | 5% (21/400; 3%–8%) | 6% (21/378; 4%–8%) | 5% (19/400; 3%–7%) | 5% (19/378; 3%–8%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.035 | 8% (32/400; 6%–11%) | 8% (32/378; 6%–12%) | 8% (30/400; 5%–11%) | 8% (30/378; 6%–11%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.05 | 16% (63/400; 13%–20%) | 17% (63/378; 13%–21%) | 10% (42/400; 8%–14%) | 11% (42/378; 8%–15%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.065 | 22% (89/400; 18%–27%) | 24% (89/378; 20%–28%) | 19% (75/400; 15%–23%) | 20% (75/378; 16%–24%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.08 | 30% (121/400; 26%–35%) | 32% (121/378; 28%–37%) | 27% (107/400; 23%–31%) | 28% (107/378; 24%–33%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.1 | 40% (159/400; 35%–45%) | 42% (159/378; 37%–47%) | 37% (148/400; 32%–42%) | 39% (148/378; 34%–44%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.125 | 60% (238/400; 55%–64%) | 63% (238/378; 58%–68%) | 54% (214/400; 49%–58%) | 57% (214/378; 52%–62%) | 3.5 / 0.5; 5.3 / 9.7 |
| 0.15 | 72% (290/400; 68%–77%) | 77% (290/378; 72%–81%) | 68% (274/400; 64%–73%) | 72% (274/378; 68%–77%) | 3.5 / 0.5; 5.3 / 9.7 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss +8.6e-03), 0.02: 0.0065 (miss +1.7e-07), 0.035: 0.0150 (miss -9.6e-07), 0.05: 0.0237 (miss -1.3e-06), 0.065: 0.0322 (miss +1.7e-06), 0.08: 0.0407 (miss +1.8e-07), 0.1: 0.0523 (miss -3.1e-06), 0.125: 0.0671 (miss -2.2e-06), 0.15: 0.0820 (miss +1.6e-06)

**two_state, 500 days** (2024-09-03 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 15 / 41 / 83; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 3% (13/400; 2%–5%) | 3% (13/400; 2%–5%) | 4% (17/400; 3%–7%) | 4% (17/400; 3%–7%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.02 | 10% (38/400; 7%–13%) | 10% (38/400; 7%–13%) | 8% (33/400; 6%–11%) | 8% (33/400; 6%–11%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.035 | 16% (66/400; 13%–20%) | 16% (66/400; 13%–20%) | 15% (60/400; 12%–19%) | 15% (60/400; 12%–19%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.05 | 28% (112/400; 24%–33%) | 28% (112/400; 24%–33%) | 24% (98/400; 21%–29%) | 24% (98/400; 21%–29%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.065 | 38% (154/400; 34%–43%) | 38% (154/400; 34%–43%) | 33% (132/400; 29%–38%) | 33% (132/400; 29%–38%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.08 | 50% (198/400; 45%–54%) | 50% (198/400; 45%–54%) | 48% (191/400; 43%–53%) | 48% (191/400; 43%–53%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.1 | 68% (274/400; 64%–73%) | 68% (274/400; 64%–73%) | 63% (253/400; 58%–68%) | 63% (253/400; 58%–68%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.125 | 85% (339/400; 81%–88%) | 85% (339/400; 81%–88%) | 82% (327/400; 78%–85%) | 82% (327/400; 78%–85%) | 3.9 / 0.1; 7.9 / 7.1 |
| 0.15 | 95% (379/400; 92%–97%) | 95% (379/400; 92%–97%) | 93% (372/400; 90%–95%) | 93% (372/400; 90%–95%) | 3.9 / 0.1; 7.9 / 7.1 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss +1.4e-03), 0.02: 0.0094 (miss -1.3e-07), 0.035: 0.0171 (miss +1.6e-07), 0.05: 0.0249 (miss +3.0e-07), 0.065: 0.0326 (miss -9.2e-08), 0.08: 0.0403 (miss -2.9e-07), 0.1: 0.0508 (miss -9.8e-08), 0.125: 0.0641 (miss -5.7e-07), 0.15: 0.0775 (miss -3.9e-08)

**two_state, 750 days** (2023-09-01 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 26 / 61 / 103; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 2% (10/400; 1%–5%) | 2% (10/400; 1%–5%) | 3% (11/400; 2%–5%) | 3% (11/400; 2%–5%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.02 | 14% (57/400; 11%–18%) | 14% (57/400; 11%–18%) | 14% (55/400; 11%–17%) | 14% (55/400; 11%–17%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.035 | 25% (99/400; 21%–29%) | 25% (99/400; 21%–29%) | 24% (98/400; 21%–29%) | 24% (98/400; 21%–29%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.05 | 45% (181/400; 40%–50%) | 45% (181/400; 40%–50%) | 42% (169/400; 38%–47%) | 42% (169/400; 38%–47%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.065 | 66% (266/400; 62%–71%) | 66% (266/400; 62%–71%) | 65% (260/400; 60%–70%) | 65% (260/400; 60%–70%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.08 | 82% (327/400; 78%–85%) | 82% (327/400; 78%–85%) | 78% (313/400; 74%–82%) | 78% (313/400; 74%–82%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.1 | 92% (370/400; 89%–95%) | 92% (370/400; 89%–95%) | 92% (366/400; 88%–94%) | 92% (366/400; 88%–94%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.125 | 100% (399/400; 99%–100%) | 100% (399/400; 99%–100%) | 99% (395/400; 97%–99%) | 99% (395/400; 97%–99%) | 3.9 / 0.1; 8.5 / 6.5 |
| 0.15 | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 3.9 / 0.1; 8.5 / 6.5 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss -3.7e-04), 0.02: 0.0139 (miss -1.9e-07), 0.035: 0.0242 (miss -2.8e-07), 0.05: 0.0345 (miss +2.0e-07), 0.065: 0.0449 (miss -2.5e-08), 0.08: 0.0554 (miss -2.2e-07), 0.1: 0.0696 (miss -8.8e-08), 0.125: 0.0877 (miss +3.6e-07), 0.15: 0.1066 (miss +8.2e-09)

### Process: calendar

Fitted to 2025-01-02 to 2026-09-03 (418 labelled days, 34 events): ridge 1.0000, pairs 417, share 0.0813

| intercept | previous_event | coupon_mid | coupon_end | quarter_end | year_end |
|---|---|---|---|---|---|
| -3.1157 | +2.4953 | +1.5260 | +0.7687 | +0.7225 | +0.1340 |

| Fitted P(event) | none | coupon_mid | coupon_end | quarter_end | year_end |
|---|---|---|---|---|---|
| previous_quiet | 0.0425 | 0.1694 | 0.0873 | 0.1646 | 0.1839 |
| previous_event | 0.3497 | 0.7121 | 0.5370 | 0.7049 | 0.7320 |

**Days until 10 events are logged** (2000 simulated series of 1000 days)

| Never reach 10 | Reach 10 within 250 days | Mean (of those that reach) | Median | 90th percentile |
|---|---|---|---|---|
| 0% (0 of 2000) | 98% | 132.1 | 124.5 | 198 |

**calendar, 250 days** (2025-01-02 to 2026-01-02; 400 replicates, 10,000 draws; events per replicate 6 / 20 / 42; 388 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 6% (24/400; 4%–9%) | 6% (24/388; 4%–9%) | 4% (15/400; 2%–6%) | 4% (15/388; 2%–6%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.02 | 10% (42/400; 8%–14%) | 11% (42/388; 8%–14%) | 8% (30/400; 5%–11%) | 8% (30/388; 5%–11%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.035 | 15% (60/400; 12%–19%) | 15% (60/388; 12%–19%) | 12% (48/400; 9%–16%) | 12% (48/388; 9%–16%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.05 | 22% (86/400; 18%–26%) | 22% (86/388; 18%–27%) | 16% (65/400; 13%–20%) | 17% (65/388; 13%–21%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.065 | 30% (122/400; 26%–35%) | 31% (122/388; 27%–36%) | 23% (93/400; 19%–28%) | 24% (93/388; 20%–28%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.08 | 41% (164/400; 36%–46%) | 42% (164/388; 37%–47%) | 32% (126/400; 27%–36%) | 32% (126/388; 28%–37%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.1 | 55% (219/400; 50%–60%) | 56% (219/388; 51%–61%) | 46% (183/400; 41%–51%) | 47% (183/388; 42%–52%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.125 | 71% (284/400; 66%–75%) | 73% (284/388; 69%–77%) | 60% (239/400; 55%–64%) | 62% (239/388; 57%–66%) | 3.8 / 0.2; 7.1 / 7.9 |
| 0.15 | 80% (322/400; 76%–84%) | 83% (322/388; 79%–86%) | 70% (282/400; 66%–75%) | 73% (282/388; 68%–77%) | 3.8 / 0.2; 7.1 / 7.9 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss -1.6e-03), 0.02: 0.0125 (miss +1.9e-07), 0.035: 0.0207 (miss -2.8e-06), 0.05: 0.0289 (miss -1.7e-06), 0.065: 0.0376 (miss +3.2e-07), 0.08: 0.0461 (miss +6.3e-07), 0.1: 0.0575 (miss +2.7e-06), 0.125: 0.0721 (miss +1.5e-07), 0.15: 0.0867 (miss +9.4e-07)

**calendar, 500 days** (2024-09-03 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 21 / 41 / 64; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 5% (19/400; 3%–7%) | 5% (19/400; 3%–7%) | 3% (13/400; 2%–5%) | 3% (13/400; 2%–5%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.02 | 9% (36/400; 7%–12%) | 9% (36/400; 7%–12%) | 8% (33/400; 6%–11%) | 8% (33/400; 6%–11%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.035 | 15% (61/400; 12%–19%) | 15% (61/400; 12%–19%) | 14% (57/400; 11%–18%) | 14% (57/400; 11%–18%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.05 | 28% (114/400; 24%–33%) | 28% (114/400; 24%–33%) | 22% (89/400; 18%–27%) | 22% (89/400; 18%–27%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.065 | 42% (166/400; 37%–46%) | 42% (166/400; 37%–46%) | 34% (138/400; 30%–39%) | 34% (138/400; 30%–39%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.08 | 57% (228/400; 52%–62%) | 57% (228/400; 52%–62%) | 47% (188/400; 42%–52%) | 47% (188/400; 42%–52%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.1 | 76% (304/400; 72%–80%) | 76% (304/400; 72%–80%) | 65% (259/400; 60%–69%) | 65% (259/400; 60%–69%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.125 | 91% (363/400; 88%–93%) | 91% (363/400; 88%–93%) | 80% (322/400; 76%–84%) | 80% (322/400; 76%–84%) | 3.9 / 0.1; 10.3 / 4.7 |
| 0.15 | 97% (389/400; 95%–98%) | 97% (389/400; 95%–98%) | 95% (380/400; 92%–97%) | 95% (380/400; 92%–97%) | 3.9 / 0.1; 10.3 / 4.7 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss +4.7e-03), 0.02: 0.0078 (miss +2.5e-07), 0.035: 0.0154 (miss -3.3e-07), 0.05: 0.0231 (miss -3.4e-07), 0.065: 0.0308 (miss +3.6e-07), 0.08: 0.0385 (miss -6.0e-08), 0.1: 0.0488 (miss +5.0e-08), 0.125: 0.0621 (miss +3.9e-07), 0.15: 0.0756 (miss +1.0e-07)

**calendar, 750 days** (2023-09-01 to 2026-09-03; 400 replicates, 10,000 draws; events per replicate 37 / 62 / 99; 400 replicates hold at least 10). Each cell: supported share (supported/replicates; 95% Wilson interval)

| Gain | section5, every replicate | section5, replicates at the floor | calendar_strata, every replicate | calendar_strata, replicates at the floor | Mean strata / dropped (section5; calendar_strata) |
|---|---|---|---|---|---|
| 0.0 (size) | 2% (9/400; 1%–4%) | 2% (9/400; 1%–4%) | 2% (8/400; 1%–4%) | 2% (8/400; 1%–4%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.02 | 13% (51/400; 10%–16%) | 13% (51/400; 10%–16%) | 11% (43/400; 8%–14%) | 11% (43/400; 8%–14%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.035 | 28% (114/400; 24%–33%) | 28% (114/400; 24%–33%) | 26% (106/400; 22%–31%) | 26% (106/400; 22%–31%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.05 | 50% (202/400; 46%–55%) | 50% (202/400; 46%–55%) | 46% (185/400; 41%–51%) | 46% (185/400; 41%–51%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.065 | 72% (288/400; 67%–76%) | 72% (288/400; 67%–76%) | 66% (265/400; 61%–71%) | 66% (265/400; 61%–71%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.08 | 87% (347/400; 83%–90%) | 87% (347/400; 83%–90%) | 83% (331/400; 79%–86%) | 83% (331/400; 79%–86%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.1 | 96% (386/400; 94%–98%) | 96% (386/400; 94%–98%) | 96% (383/400; 93%–97%) | 96% (383/400; 93%–97%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.125 | 100% (399/400; 99%–100%) | 100% (399/400; 99%–100%) | 99% (396/400; 97%–100%) | 99% (396/400; 97%–100%) | 4.0 / 0.0; 10.8 / 4.2 |
| 0.15 | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 100% (400/400; 99%–100%) | 4.0 / 0.0; 10.8 / 4.2 |

Planting: shifts in sigma on the 200 reference series 0.0: 0.0000 (miss -4.6e-04), 0.02: 0.0140 (miss +2.7e-07), 0.035: 0.0244 (miss -3.4e-08), 0.05: 0.0346 (miss +6.2e-08), 0.065: 0.0451 (miss -9.5e-08), 0.08: 0.0556 (miss +2.4e-07), 0.1: 0.0698 (miss +1.0e-07), 0.125: 0.0880 (miss -7.6e-08), 0.15: 0.1068 (miss +2.4e-08)

## What this study does and does not show

- **It shows** how often the declared test (§5 and §11.4's calendar-stratified variant) would support a planted gain of a
  given size in windows of 250, 500 and 750 labelled days when events follow each of three fitted processes, with the
  size at gain 0, both readings, and the days and events a window holds.
- **It does not show** that any estimator carries information beyond R and S. The simulated events are independent of R
  and S given the calendar, so the null is R with no relation to the events, and the planted signal is the same oracle
  shift as in Part A (§11.6).
- **A process fitted to 2025-26** carries the clustering of those months; whether the next year clusters likewise is not
  tested. The calendar-tied process carries one year-end and six quarter-ends, and tax dates are not a flag.
- **Windows of 500 and 750 days** reuse real R and S from before 2025 with events at the 2025-26 rate.
- **The null is not exactly zero.** At gain 0 the estimate is R plus tie-breaking noise (the first row of each planting
  list, a miss of up to +8.6e-03).
- **Monte Carlo.** 400 replicates a cell and 10,000 draws; the Wilson intervals are at the replicates. Cells share their
  replicates across the grid and across the two tests, so the columns are paired.
- **Not an input** to the verdict, the MME or the floor.

## Marked questions for Eleonora (none is settled in code)

- **Which option, if any, to adopt** (a longer confirmation window; the calendar-tied process as the planning process), and
  on what horizon: hers, separately (§11 preamble).
- **Q2 and Q6 on the new figures** (the MME, the floor and the deciding reading): reconfirm or change.
- **Record 3 against record 2** for the same process (comparison above): whether the gap at 0.065 and 0.10 needs a further
  run.
