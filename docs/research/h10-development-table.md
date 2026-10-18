# H10: the development table

<!-- generated: scripts/emit_h10_table.py from results/h10/development.json, results/h10/sensitivity_onrrp_interaction.json and results/h10/sensitivity_onrrp_regimes.json; never hand-edited -->

**Serves:** H10 (pressure episodes can be attributed to drivers), development step 3 of the plan (`docs/research/plan.md`). Directives #77 and #86. **Development evidence, not a verdict** (`docs/decisions/measurement-protocol.md` section 1; eleonorabjornberg/repo-market-model#640): it confirms nothing, and there is no registration. Registering the frozen method is Eleonora's attested action.

## Header

- **Parent pin:** `53e61af9b4175e854c196908d3c76b228c039667`; the parent's published panel digest `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999`.
- **Panel:** version 1, digest `acb77874e0ca2c9eeee1c33a229f5e12745e65bb1224088d52c391dbf54be2ab`, 2104 rows, 2018-04-03 to 2026-09-03 (the last day read: 2026-09-03).
- **Seeds and draws:** seed 20261013; 10000 bootstrap draws per episode; the selection-aware null 1000 draws at the 95% quantile (bar 0.234); 20 placebo windows per episode.
- **Record read, byte for byte:** `results/h10/development.json`, sha256 `21fa38197d75822024a121106510a6b340cb842ddd2cbf5c643226e34b8dd8af` (H10 step 2, #70, PR #73). It is not re-fitted or re-run for this page.
- **The method:** `docs/decisions/h10-method.md`, sha256 `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9`. This is the digest to register; the commit is named in the pull request.

## What the development table shows

Over the 31 development onsets: 4 of 31 (6% to 26%) under the residual bar, 14 of 31 (31% to 60%) beating the null, 4 of 31 (6% to 26%) both. Intervals are Wilson 90% intervals on the share of episodes and treat the episodes as independent, which they are not quite (they cluster at quarter-ends and in 2018-19), so they are, if anything, too narrow.

Under the plan's rule ("drivers named" needs more than half the episodes) the table reads **residual dominates**; on the residual bar alone it reads **residual dominates**. This describes the development table. It is not a verdict.

| Group | Episodes | Under the residual bar | Beats the null | Both (counted) | Not attributable |
|---|---|---|---|---|---|
| All development onsets | 31 | 4 (6% to 26%) | 14 (31% to 60%) | 4 (6% to 26%) | 0 |
| ON RRP depleted | 29 | 4 (6% to 27%) | 12 (28% to 57%) | 4 (6% to 27%) | 0 |
| ON RRP abundant | 2 | 0 (0% to 57%) | 2 (43% to 100%) | 0 (0% to 57%) | 0 |
| Quarter-end onsets | 4 | 1 (6% to 64%) | 4 (60% to 100%) | 1 (6% to 64%) | 0 |
| Other onsets | 27 | 3 (5% to 25%) | 10 (24% to 53%) | 3 (5% to 25%) | 0 |

Progress markers (each over the attributed episodes, with a distribution-free 90% interval on the median):

- median residual share: 0.78 (90% interval 0.66 to 0.85, n = 31);
- explained share above reserves alone: 0.23 (90% interval 0.13 to 0.37, n = 31);
- placebo gap, the episode's explained share less its placebo windows' median: -0.39 (90% interval -0.62 to -0.19, n = 31).

## One row per episode

Each driver's Shapley share has its 90% interval first, the point share after the interval. "Above reserves alone" is the drivers' explained share less that of reserves alone. "Placebo ≥ episode" is the share of the episode's placebo windows (same length and day type, touching no episode) whose explained share is at least the episode's, with the number of attributable placebo windows.

| Onset | Rise (bp) | Regime | Quarter-end | treasury_settlement | tga | reserve_balances | quarter_end | on_rrp | Residual | Explained | Above reserves alone | Placebo ≥ episode | Under bar | Beats null |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2018-05-31 | 6.40 | depleted | no | 0.069 [0.053, 0.086] | -0.005 [-0.010, 0.001] | 0.001 [-0.000, 0.004] | -0.013 [-0.021, -0.005] | 0.000 [-0.008, 0.009] | 0.947 [0.923, 0.967] | 0.053 | 0.053 | 0.75 of 12 | no | no |
| 2018-06-29 | 10.00 | depleted | yes | 0.026 [0.017, 0.035] | -0.004 [-0.011, 0.004] | 0.016 [0.007, 0.028] | 0.209 [0.110, 0.333] | 0.007 [0.002, 0.013] | 0.746 [0.611, 0.853] | 0.254 | 0.231 | 1.00 of 16 | no | yes |
| 2018-11-15 | 3.40 | depleted | no | 0.117 [0.090, 0.148] | 0.018 [0.002, 0.035] | 0.050 [0.024, 0.079] | -0.032 [-0.054, -0.014] | 0.001 [-0.018, 0.020] | 0.845 [0.790, 0.893] | 0.155 | 0.084 | 0.81 of 16 | no | no |
| 2018-11-30 | 7.40 | depleted | no | -0.002 [-0.003, -0.001] | 0.003 [0.001, 0.005] | 0.010 [0.005, 0.016] | -0.001 [-0.002, -0.000] | 0.000 [-0.000, 0.000] | 0.990 [0.984, 0.996] | 0.010 | -0.004 | 0.71 of 7 | no | no |
| 2018-12-17 | 6.20 | depleted | no | 0.087 [0.067, 0.109] | 0.005 [0.001, 0.009] | 0.022 [0.010, 0.036] | -0.012 [-0.020, -0.005] | 0.000 [-0.004, 0.005] | 0.898 [0.866, 0.925] | 0.102 | 0.073 | 0.67 of 12 | no | no |
| 2018-12-28 | 33.20 | depleted | no | 0.002 [0.000, 0.004] | 0.001 [0.000, 0.002] | 0.007 [0.003, 0.012] | 0.049 [0.029, 0.070] | 0.001 [-0.001, 0.003] | 0.939 [0.916, 0.961] | 0.061 | 0.050 | 0.58 of 12 | no | no |
| 2019-01-15 | 0.40 | depleted | no | 2.534 [1.955, 3.187] | -0.087 [-0.166, -0.015] | -0.257 [-0.397, -0.126] | -0.236 [-0.393, -0.087] | -0.002 [-0.047, 0.047] | -0.952 [-1.662, -0.342] | 1.952 | 2.303 | 0.25 of 12 | no | yes |
| 2019-01-31 | 4.80 | depleted | no | 0.256 [0.197, 0.323] | 0.001 [-0.001, 0.003] | -0.004 [-0.008, -0.001] | -0.028 [-0.049, -0.011] | -0.001 [-0.003, 0.001] | 0.776 [0.708, 0.834] | 0.224 | 0.229 | 0.56 of 9 | no | no |
| 2019-02-28 | 3.60 | depleted | no | 0.321 [0.249, 0.404] | -0.047 [-0.096, 0.006] | -0.024 [-0.038, -0.012] | -0.026 [-0.046, -0.008] | -0.000 [-0.004, 0.004] | 0.776 [0.669, 0.866] | 0.224 | 0.277 | 0.82 of 11 | no | no |
| 2019-03-15 | 4.40 | depleted | no | 0.124 [0.095, 0.156] | 0.038 [-0.002, 0.075] | 0.048 [0.024, 0.075] | -0.025 [-0.044, -0.010] | -0.001 [-0.005, 0.003] | 0.816 [0.753, 0.871] | 0.184 | 0.107 | 0.56 of 9 | no | no |
| 2019-03-29 | 9.40 | depleted | yes | 0.015 [0.007, 0.023] | -0.001 [-0.005, 0.003] | 0.006 [0.002, 0.011] | 0.242 [0.129, 0.374] | 0.007 [-0.006, 0.021] | 0.731 [0.587, 0.855] | 0.269 | 0.257 | 1.00 of 17 | no | yes |
| 2019-05-28 | 4.40 | depleted | no | 0.178 [0.136, 0.224] | -0.048 [-0.097, 0.007] | -0.019 [-0.032, -0.009] | -0.007 [-0.016, 0.000] | -0.000 [-0.009, 0.008] | 0.896 [0.817, 0.962] | 0.104 | 0.151 | 0.67 of 12 | no | no |
| 2019-06-17 | 1.00 | depleted | no | 0.732 [0.566, 0.923] | -0.028 [-0.053, -0.004] | -0.052 [-0.078, -0.025] | -0.121 [-0.210, -0.046] | 0.005 [-0.079, 0.096] | 0.463 [0.225, 0.672] | 0.537 | 0.607 | 0.45 of 11 | yes | yes |
| 2019-06-25 | 6.20 | depleted | no | 0.041 [0.027, 0.056] | 0.024 [0.002, 0.046] | 0.042 [0.021, 0.068] | 0.367 [0.199, 0.566] | 0.011 [-0.009, 0.030] | 0.516 [0.287, 0.708] | 0.484 | 0.413 | 0.57 of 7 | no | yes |
| 2019-08-13 | 3.60 | depleted | no | 0.266 [0.205, 0.335] | -0.009 [-0.017, -0.000] | -0.016 [-0.024, -0.008] | -0.031 [-0.054, -0.012] | -0.000 [-0.005, 0.005] | 0.790 [0.718, 0.852] | 0.210 | 0.233 | 0.57 of 14 | no | no |
| 2019-08-30 | 6.20 | depleted | no | 0.149 [0.116, 0.185] | 0.007 [-0.004, 0.015] | 0.014 [0.007, 0.023] | -0.021 [-0.036, -0.009] | -0.001 [-0.002, -0.000] | 0.853 [0.817, 0.885] | 0.147 | 0.127 | 0.86 of 7 | no | no |
| 2019-10-15 | 10.20 | depleted | no | 0.037 [0.029, 0.047] | -0.001 [-0.002, 0.000] | 0.004 [0.002, 0.007] | -0.006 [-0.010, -0.002] | 0.000 [-0.002, 0.003] | 0.965 [0.952, 0.975] | 0.035 | 0.030 | 0.60 of 5 | no | no |
| 2019-11-29 | 2.20 | depleted | no | 0.699 [0.536, 0.883] | -0.023 [-0.044, -0.004] | -0.068 [-0.109, -0.033] | -0.062 [-0.111, -0.021] | -0.003 [-0.017, 0.011] | 0.457 [0.274, 0.615] | 0.543 | 0.639 | 0.71 of 7 | yes | yes |
| 2019-12-16 | 0.60 | depleted | no | 0.908 [0.703, 1.147] | -0.001 [-0.064, 0.060] | -0.449 [-0.722, -0.209] | -0.112 [-0.200, -0.041] | -0.001 [-0.071, 0.078] | 0.656 [0.286, 1.021] | 0.344 | 0.891 | 1.00 of 6 | no | yes |
| 2020-03-04 | 3.20 | depleted | no | -0.361 [-0.455, -0.277] | -0.090 [-0.176, -0.002] | -0.129 [-0.207, -0.066] | 0.064 [0.025, 0.111] | 0.002 [-0.003, 0.009] | 1.513 [1.373, 1.677] | -0.513 | -0.312 | 0.64 of 11 | no | no |
| 2020-03-12 | 12.60 | depleted | no | 0.037 [0.028, 0.047] | 0.005 [-0.003, 0.013] | -0.028 [-0.046, -0.014] | -0.004 [-0.008, -0.001] | 0.001 [-0.002, 0.005] | 0.988 [0.970, 1.009] | 0.012 | 0.049 | 1.00 of 5 | no | no |
| 2024-09-30 | 8.60 | abundant | yes | 0.150 [0.114, 0.190] | -0.006 [-0.024, 0.014] | 0.080 [0.036, 0.132] | 0.251 [0.135, 0.390] | 0.008 [-0.027, 0.040] | 0.517 [0.331, 0.674] | 0.483 | 0.383 | 1.00 of 15 | no | yes |
| 2024-12-26 | 12.40 | abundant | no | 0.240 [0.183, 0.303] | -0.003 [-0.010, 0.005] | 0.033 [0.015, 0.060] | 0.115 [0.066, 0.177] | -0.011 [-0.062, 0.044] | 0.626 [0.497, 0.732] | 0.374 | 0.329 | 0.62 of 8 | no | yes |
| 2025-09-15 | 0.80 | depleted | no | 1.051 [0.809, 1.321] | 0.459 [-0.031, 0.918] | 0.352 [0.183, 0.560] | -0.185 [-0.337, -0.071] | -0.013 [-0.042, 0.010] | -0.664 [-1.275, -0.088] | 1.664 | 1.021 | 0.43 of 7 | no | yes |
| 2025-09-30 | 5.00 | depleted | yes | 0.216 [0.166, 0.273] | -0.001 [-0.011, 0.011] | 0.053 [0.026, 0.087] | 0.444 [0.241, 0.685] | 0.012 [-0.025, 0.047] | 0.274 [-0.008, 0.509] | 0.726 | 0.652 | 0.94 of 16 | yes | yes |
| 2025-10-15 | 8.60 | depleted | no | -0.109 [-0.137, -0.083] | 0.003 [-0.004, 0.008] | -0.023 [-0.037, -0.010] | 0.013 [0.005, 0.022] | 0.000 [-0.001, 0.002] | 1.115 [1.083, 1.154] | -0.115 | -0.089 | 0.64 of 11 | no | no |
| 2025-12-15 | 1.80 | depleted | no | 0.427 [0.329, 0.540] | -0.118 [-0.229, 0.005] | -0.132 [-0.203, -0.071] | -0.027 [-0.052, -0.004] | 0.000 [-0.004, 0.005] | 0.849 [0.661, 1.001] | 0.151 | 0.368 | 0.50 of 6 | no | no |
| 2025-12-26 | 10.80 | depleted | no | 0.288 [0.221, 0.364] | -0.000 [-0.002, 0.002] | -0.003 [-0.007, 0.002] | 0.167 [0.093, 0.258] | 0.006 [0.001, 0.011] | 0.542 [0.408, 0.654] | 0.458 | 0.456 | 0.67 of 9 | no | yes |
| 2026-02-17 | 3.80 | depleted | no | 0.324 [0.249, 0.409] | 0.002 [-0.004, 0.008] | -0.026 [-0.042, -0.013] | -0.035 [-0.061, -0.013] | -0.001 [-0.003, 0.000] | 0.736 [0.651, 0.812] | 0.264 | 0.295 | 0.58 of 12 | no | yes |
| 2026-03-02 | 0.80 | depleted | no | 1.432 [1.101, 1.799] | -0.248 [-0.500, 0.012] | -0.212 [-0.327, -0.109] | -0.088 [-0.169, -0.021] | -0.003 [-0.041, 0.035] | 0.119 [-0.372, 0.531] | 0.881 | 1.262 | 0.27 of 11 | yes | yes |
| 2026-04-15 | 4.80 | depleted | no | 0.247 [0.191, 0.313] | 0.005 [-0.003, 0.012] | -0.021 [-0.035, -0.010] | -0.027 [-0.048, -0.010] | -0.001 [-0.002, 0.000] | 0.797 [0.733, 0.854] | 0.203 | 0.227 | 0.64 of 11 | no | no |

Fixed-coefficient shares, beside the Shapley shares above (reported only; no outcome rule reads them):

| Onset | treasury_settlement | tga | reserve_balances | quarter_end | on_rrp |
|---|---|---|---|---|---|
| 2018-05-31 | 0.061 | -0.002 | -0.000 | 0.000 | -0.006 |
| 2018-06-29 | 0.076 | -0.000 | 0.018 | 0.166 | -0.005 |
| 2018-11-15 | 0.104 | 0.008 | 0.053 | 0.000 | -0.011 |
| 2018-11-30 | -0.002 | 0.001 | 0.010 | 0.000 | 0.000 |
| 2018-12-17 | 0.079 | 0.003 | 0.022 | 0.000 | -0.002 |
| 2018-12-28 | 0.018 | 0.001 | 0.008 | 0.034 | -0.000 |
| 2019-01-15 | 2.287 | -0.044 | -0.270 | 0.000 | -0.022 |
| 2019-01-31 | 0.226 | 0.000 | -0.004 | 0.000 | 0.001 |
| 2019-02-28 | 0.283 | -0.020 | -0.040 | 0.000 | -0.000 |
| 2019-03-15 | 0.110 | 0.017 | 0.058 | 0.000 | -0.001 |
| 2019-03-29 | 0.068 | 0.001 | 0.009 | 0.190 | 0.000 |
| 2019-05-28 | 0.156 | -0.020 | -0.036 | 0.000 | 0.003 |
| 2019-06-17 | 0.653 | -0.015 | -0.053 | 0.000 | -0.048 |
| 2019-06-25 | 0.120 | 0.013 | 0.053 | 0.297 | 0.001 |
| 2019-08-13 | 0.234 | -0.004 | -0.018 | 0.000 | -0.003 |
| 2019-08-30 | 0.130 | 0.001 | 0.017 | 0.000 | 0.000 |
| 2019-10-15 | 0.033 | -0.000 | 0.003 | 0.000 | -0.001 |
| 2019-11-29 | 0.618 | -0.011 | -0.072 | 0.000 | 0.008 |
| 2019-12-16 | 0.806 | -0.016 | -0.408 | 0.000 | -0.038 |
| 2020-03-04 | -0.320 | -0.038 | -0.154 | 0.000 | -0.001 |
| 2020-03-12 | 0.033 | 0.000 | -0.021 | 0.000 | -0.001 |
| 2024-09-30 | 0.193 | 0.002 | 0.074 | 0.203 | 0.011 |
| 2024-12-26 | 0.251 | -0.001 | 0.037 | 0.147 | -0.060 |
| 2025-09-15 | 0.944 | 0.208 | 0.481 | 0.000 | 0.031 |
| 2025-09-30 | 0.292 | 0.004 | 0.056 | 0.367 | 0.007 |
| 2025-10-15 | -0.096 | 0.000 | -0.020 | 0.000 | -0.000 |
| 2025-12-15 | 0.372 | -0.053 | -0.163 | 0.000 | -0.005 |
| 2025-12-26 | 0.304 | 0.001 | 0.001 | 0.160 | -0.007 |
| 2026-02-17 | 0.287 | 0.000 | -0.023 | 0.000 | 0.001 |
| 2026-03-02 | 1.263 | -0.108 | -0.287 | 0.000 | 0.012 |
| 2026-04-15 | 0.219 | 0.002 | -0.018 | 0.000 | -0.000 |

## Sensitivity: ON RRP as an interaction with the depleted regime

**Superseded (15 October 2026, finding #79).** This sensitivity took the window change of a truncated level, `v if v < 100 else 0`, which gives the regressor the wrong sign in 92 of the 128 windows that straddle the $100 bn break, and it held the abundant regime's coefficient at 0 although the method record says each regime has its own. It stands as published; the corrected sensitivity is the next section, from `results/h10/sensitivity_onrrp_regimes.json`, and supersedes it.

**Reported only** (her answer 5 on #69: "the interaction reported later as a sensitivity"). The method record's decided driver set is unchanged, and this sensitivity does not change the published outcome above. ON RRP enters as `on_rrp x 1(on_rrp < 100.0 bn)`, the parent's `ON_RRP_DEPLETION_BREAK_BN`, in place of its window change; everything else (window, bootstrap, seeds, placebo, benchmark, null, outcome rule) is as in the published record. The record is `results/h10/sensitivity_onrrp_interaction.json`; its null bar is 0.233.

What the sensitivity shows: 5 of 31 (8% to 30%) under the residual bar, 16 of 31 (37% to 66%) beating the null, 5 of 31 (8% to 30%) both, against 4 of 31 (6% to 26%) under the residual bar, 14 of 31 (31% to 60%) beating the null, 4 of 31 (6% to 26%) both in the published record. Labelled sensitivity; it is not a result.

**The abundant regime has 2 onsets**, so the interaction is estimated almost entirely from the depleted regime and its term says little about the abundant one.

| Group | Episodes | Under the residual bar | Beats the null | Both (counted) | Not attributable |
|---|---|---|---|---|---|
| All development onsets | 31 | 5 (8% to 30%) | 16 (37% to 66%) | 5 (8% to 30%) | 0 |
| ON RRP depleted | 29 | 5 (9% to 31%) | 14 (34% to 63%) | 5 (9% to 31%) | 0 |
| ON RRP abundant | 2 | 0 (0% to 57%) | 2 (43% to 100%) | 0 (0% to 57%) | 0 |
| Quarter-end onsets | 4 | 1 (6% to 64%) | 4 (60% to 100%) | 1 (6% to 64%) | 0 |
| Other onsets | 27 | 4 (7% to 29%) | 12 (30% to 60%) | 4 (7% to 29%) | 0 |

Progress markers under the interaction:

- median residual share: 0.76 (90% interval 0.63 to 0.80, n = 31);
- explained share above reserves alone: 0.25 (90% interval 0.13 to 0.35, n = 31);
- placebo gap: -0.37 (90% interval -0.52 to -0.13, n = 31).

### Episodes whose outcome differs

Published / interaction in each outcome column.

| Onset | Residual (published) | Residual (interaction) | Under bar | Beats null |
|---|---|---|---|---|
| 2018-11-15 | 0.845 | 0.743 | no / no | no / yes |
| 2019-08-13 | 0.790 | 0.759 | no / no | no / yes |
| 2019-11-29 | 0.457 | 0.524 | yes / no | yes / yes |
| 2019-12-16 | 0.656 | 0.292 | no / yes | yes / yes |
| 2025-09-15 | -0.664 | -0.390 | no / yes | yes / yes |

### Per episode, beside the published figures

| Onset | Regime | ON RRP share (published) | ON RRP share (interaction) | Residual (published) | Residual (interaction) | Explained (interaction) | Under bar | Beats null |
|---|---|---|---|---|---|---|---|---|
| 2018-05-31 | depleted | 0.000 [-0.008, 0.009] | 0.042 [-0.024, 0.132] | 0.947 [0.923, 0.967] | 0.903 [0.808, 0.974] | 0.097 | no | no |
| 2018-06-29 | depleted | 0.007 [0.002, 0.013] | 0.025 [-0.036, 0.110] | 0.746 [0.611, 0.853] | 0.730 [0.557, 0.858] | 0.270 | no | yes |
| 2018-11-15 | depleted | 0.001 [-0.018, 0.020] | 0.098 [-0.044, 0.303] | 0.845 [0.790, 0.893] | 0.743 [0.536, 0.888] | 0.257 | no | yes |
| 2018-11-30 | depleted | 0.000 [-0.000, 0.000] | -0.000 [-0.002, 0.000] | 0.990 [0.984, 0.996] | 0.991 [0.984, 0.997] | 0.009 | no | no |
| 2018-12-17 | depleted | 0.000 [-0.004, 0.005] | 0.019 [-0.015, 0.064] | 0.898 [0.866, 0.925] | 0.878 [0.819, 0.924] | 0.122 | no | no |
| 2018-12-28 | depleted | 0.001 [-0.001, 0.003] | 0.003 [-0.006, 0.014] | 0.939 [0.916, 0.961] | 0.938 [0.914, 0.961] | 0.062 | no | no |
| 2019-01-15 | depleted | -0.002 [-0.047, 0.047] | 0.177 [-0.146, 0.622] | -0.952 [-1.662, -0.342] | -1.152 [-2.116, -0.364] | 2.152 | no | yes |
| 2019-01-31 | depleted | -0.001 [-0.003, 0.001] | -0.013 [-0.039, 0.005] | 0.776 [0.708, 0.834] | 0.786 [0.726, 0.842] | 0.214 | no | no |
| 2019-02-28 | depleted | -0.000 [-0.004, 0.004] | 0.001 [-0.003, 0.005] | 0.776 [0.669, 0.866] | 0.777 [0.669, 0.868] | 0.223 | no | no |
| 2019-03-15 | depleted | -0.001 [-0.005, 0.003] | 0.008 [-0.003, 0.025] | 0.816 [0.753, 0.871] | 0.804 [0.737, 0.860] | 0.196 | no | no |
| 2019-03-29 | depleted | 0.007 [-0.006, 0.021] | -0.005 [-0.018, 0.002] | 0.731 [0.587, 0.855] | 0.752 [0.622, 0.866] | 0.248 | no | yes |
| 2019-05-28 | depleted | -0.000 [-0.009, 0.008] | -0.024 [-0.073, 0.010] | 0.896 [0.817, 0.962] | 0.924 [0.848, 0.995] | 0.076 | no | no |
| 2019-06-17 | depleted | 0.005 [-0.079, 0.096] | 0.454 [-0.208, 1.375] | 0.463 [0.225, 0.672] | -0.012 [-0.967, 0.707] | 1.012 | yes | yes |
| 2019-06-25 | depleted | 0.011 [-0.009, 0.030] | -0.011 [-0.039, 0.004] | 0.516 [0.287, 0.708] | 0.549 [0.343, 0.731] | 0.451 | no | yes |
| 2019-08-13 | depleted | -0.000 [-0.005, 0.005] | 0.028 [-0.013, 0.086] | 0.790 [0.718, 0.852] | 0.759 [0.654, 0.843] | 0.241 | no | yes |
| 2019-08-30 | depleted | -0.001 [-0.002, -0.000] | -0.001 [-0.004, 0.001] | 0.853 [0.817, 0.885] | 0.851 [0.817, 0.884] | 0.149 | no | no |
| 2019-10-15 | depleted | 0.000 [-0.002, 0.003] | 0.015 [-0.007, 0.045] | 0.965 [0.952, 0.975] | 0.950 [0.916, 0.975] | 0.050 | no | no |
| 2019-11-29 | depleted | -0.003 [-0.017, 0.011] | -0.070 [-0.219, 0.034] | 0.457 [0.274, 0.615] | 0.524 [0.367, 0.688] | 0.476 | no | yes |
| 2019-12-16 | depleted | -0.001 [-0.071, 0.078] | 0.331 [-0.139, 0.999] | 0.656 [0.286, 1.021] | 0.292 [-0.473, 0.937] | 0.708 | yes | yes |
| 2020-03-04 | depleted | 0.002 [-0.003, 0.009] | 0.006 [-0.003, 0.021] | 1.513 [1.373, 1.677] | 1.516 [1.377, 1.676] | -0.516 | no | no |
| 2020-03-12 | depleted | 0.001 [-0.002, 0.005] | 0.023 [0.002, 0.055] | 0.988 [0.970, 1.009] | 0.965 [0.932, 0.993] | 0.035 | no | no |
| 2024-09-30 | abundant | 0.008 [-0.027, 0.040] | -0.001 [-0.010, 0.002] | 0.517 [0.331, 0.674] | 0.547 [0.387, 0.682] | 0.453 | no | yes |
| 2024-12-26 | abundant | -0.011 [-0.062, 0.044] | -0.053 [-0.149, 0.012] | 0.626 [0.497, 0.732] | 0.631 [0.525, 0.740] | 0.369 | no | yes |
| 2025-09-15 | depleted | -0.013 [-0.042, 0.010] | -0.300 [-0.894, 0.126] | -0.664 [-1.275, -0.088] | -0.390 [-1.069, 0.383] | 1.390 | yes | yes |
| 2025-09-30 | depleted | 0.012 [-0.025, 0.047] | -0.065 [-0.214, 0.032] | 0.274 [-0.008, 0.509] | 0.372 [0.142, 0.594] | 0.628 | yes | yes |
| 2025-10-15 | depleted | 0.000 [-0.001, 0.002] | 0.003 [-0.002, 0.009] | 1.115 [1.083, 1.154] | 1.113 [1.080, 1.151] | -0.113 | no | no |
| 2025-12-15 | depleted | 0.000 [-0.004, 0.005] | 0.047 [-0.025, 0.143] | 0.849 [0.661, 1.001] | 0.804 [0.567, 0.992] | 0.196 | no | no |
| 2025-12-26 | depleted | 0.006 [0.001, 0.011] | 0.010 [-0.005, 0.026] | 0.542 [0.408, 0.654] | 0.537 [0.399, 0.655] | 0.463 | no | yes |
| 2026-02-17 | depleted | -0.001 [-0.003, 0.000] | -0.005 [-0.017, 0.002] | 0.736 [0.651, 0.812] | 0.738 [0.658, 0.810] | 0.262 | no | yes |
| 2026-03-02 | depleted | -0.003 [-0.041, 0.035] | -0.105 [-0.328, 0.048] | 0.119 [-0.372, 0.531] | 0.236 [-0.208, 0.649] | 0.764 | yes | yes |
| 2026-04-15 | depleted | -0.001 [-0.002, 0.000] | 0.000 [-0.002, 0.002] | 0.797 [0.733, 0.854] | 0.794 [0.731, 0.850] | 0.206 | no | no |

## Sensitivity: ON RRP as two regime-specific terms

**Reported only** (finding #79; her ruling of 14 October 2026; directive #86). The method record's decided driver set is unchanged, and this sensitivity does not change the published outcome above. Each window's regime is fixed by its **baseline** mean ON RRP against the parent's `ON_RRP_DEPLETION_BREAK_BN` (100.0 bn); ON RRP then enters as two drivers in place of its window change, `on_rrp window change x 1(baseline mean on_rrp < 100.0 bn)` and `on_rrp window change x 1(baseline mean on_rrp >= 100.0 bn)`, each with its own coefficient. A window that straddles the break keeps the sign of its change. Everything else (window, bootstrap, seeds, placebo, benchmark, null, outcome rule) is as in the published record. The record is `results/h10/sensitivity_onrrp_regimes.json`; its null bar is 0.244.

What the sensitivity shows: 3 of 31 (4% to 22%) under the residual bar, 13 of 31 (29% to 57%) beating the null, 3 of 31 (4% to 22%) both, against 4 of 31 (6% to 26%) under the residual bar, 14 of 31 (31% to 60%) beating the null, 4 of 31 (6% to 26%) both in the published record and 5 of 31 (8% to 30%) under the residual bar, 16 of 31 (37% to 66%) beating the null, 5 of 31 (8% to 30%) both in the superseded interaction sensitivity. Labelled sensitivity; it is not a result.

**The abundant regime has 2 onsets**, so its coefficient rests on the fitting sample's abundant windows, not on the onsets.

| Group | Episodes | Under the residual bar | Beats the null | Both (counted) | Not attributable |
|---|---|---|---|---|---|
| All development onsets | 31 | 3 (4% to 22%) | 13 (29% to 57%) | 3 (4% to 22%) | 0 |
| ON RRP depleted | 29 | 3 (4% to 23%) | 11 (25% to 53%) | 3 (4% to 23%) | 0 |
| ON RRP abundant | 2 | 0 (0% to 57%) | 2 (43% to 100%) | 0 (0% to 57%) | 0 |
| Quarter-end onsets | 4 | 1 (6% to 64%) | 3 (36% to 94%) | 1 (6% to 64%) | 0 |
| Other onsets | 27 | 2 (2% to 20%) | 10 (24% to 53%) | 2 (2% to 20%) | 0 |

Progress markers under the regime terms:

- median residual share: 0.78 (90% interval 0.68 to 0.85, n = 31);
- explained share above reserves alone: 0.23 (90% interval 0.13 to 0.36, n = 31);
- placebo gap: -0.39 (90% interval -0.62 to -0.20, n = 31).

### Episodes whose outcome differs from the published record

Published / regime terms in each outcome column.

| Onset | Residual (published) | Residual (regime terms) | Under bar | Beats null |
|---|---|---|---|---|
| 2018-06-29 | 0.746 | 0.758 | no / no | yes / no |
| 2019-06-17 | 0.463 | 0.508 | yes / no | yes / yes |

### Per episode, beside the published figures

| Onset | Regime | Depleted-term share | Abundant-term share | Residual (published) | Residual (regime terms) | Explained (regime terms) | Under bar | Beats null |
|---|---|---|---|---|---|---|---|---|
| 2018-05-31 | depleted | 0.001 [-0.053, 0.142] | -0.001 [-0.001, 0.000] | 0.947 [0.923, 0.967] | 0.955 [0.822, 1.009] | 0.045 | no | no |
| 2018-06-29 | depleted | -0.004 [-0.043, 0.112] | 0.005 [-0.005, 0.013] | 0.746 [0.611, 0.853] | 0.758 [0.581, 0.867] | 0.242 | no | no |
| 2018-11-15 | depleted | 0.008 [-0.116, 0.328] | -0.001 [-0.004, 0.001] | 0.845 [0.790, 0.893] | 0.858 [0.561, 0.974] | 0.142 | no | no |
| 2018-11-30 | depleted | -0.000 [-0.002, 0.000] | 0.000 [-0.000, 0.000] | 0.990 [0.984, 0.996] | 0.990 [0.985, 0.997] | 0.010 | no | no |
| 2018-12-17 | depleted | -0.001 [-0.030, 0.072] | -0.000 [-0.001, 0.000] | 0.898 [0.866, 0.925] | 0.904 [0.828, 0.941] | 0.096 | no | no |
| 2018-12-28 | depleted | -0.000 [-0.006, 0.014] | 0.001 [-0.002, 0.003] | 0.939 [0.916, 0.961] | 0.941 [0.916, 0.962] | 0.059 | no | no |
| 2019-01-15 | depleted | -0.010 [-0.241, 0.714] | -0.008 [-0.020, 0.002] | -0.952 [-1.662, -0.342] | -0.905 [-2.034, -0.229] | 1.905 | no | yes |
| 2019-01-31 | depleted | -0.001 [-0.045, 0.016] | -0.001 [-0.002, 0.000] | 0.776 [0.708, 0.834] | 0.774 [0.713, 0.839] | 0.226 | no | no |
| 2019-02-28 | depleted | -0.000 [-0.009, 0.007] | -0.000 [-0.004, 0.002] | 0.776 [0.669, 0.866] | 0.776 [0.671, 0.867] | 0.224 | no | no |
| 2019-03-15 | depleted | 0.001 [-0.013, 0.028] | -0.001 [-0.003, 0.002] | 0.816 [0.753, 0.871] | 0.817 [0.747, 0.871] | 0.183 | no | no |
| 2019-03-29 | depleted | 0.002 [-0.031, 0.019] | 0.006 [-0.005, 0.015] | 0.731 [0.587, 0.855] | 0.730 [0.594, 0.862] | 0.270 | no | yes |
| 2019-05-28 | depleted | -0.002 [-0.087, 0.031] | 0.000 [-0.003, 0.004] | 0.896 [0.817, 0.962] | 0.894 [0.819, 0.996] | 0.106 | no | no |
| 2019-06-17 | depleted | 0.041 [-0.483, 1.501] | -0.006 [-0.016, 0.004] | 0.463 [0.225, 0.672] | 0.508 [-0.917, 1.056] | 0.492 | no | yes |
| 2019-06-25 | depleted | 0.002 [-0.058, 0.029] | 0.009 [-0.006, 0.023] | 0.516 [0.287, 0.708] | 0.514 [0.296, 0.723] | 0.486 | no | yes |
| 2019-08-13 | depleted | 0.003 [-0.027, 0.090] | -0.001 [-0.002, -0.000] | 0.790 [0.718, 0.852] | 0.793 [0.671, 0.864] | 0.207 | no | no |
| 2019-08-30 | depleted | -0.000 [-0.005, 0.001] | -0.001 [-0.001, 0.000] | 0.853 [0.817, 0.885] | 0.852 [0.817, 0.886] | 0.148 | no | no |
| 2019-10-15 | depleted | 0.001 [-0.017, 0.051] | -0.000 [-0.000, 0.000] | 0.965 [0.952, 0.975] | 0.967 [0.918, 0.987] | 0.033 | no | no |
| 2019-11-29 | depleted | -0.007 [-0.244, 0.091] | -0.001 [-0.004, 0.000] | 0.457 [0.274, 0.615] | 0.448 [0.285, 0.676] | 0.552 | yes | yes |
| 2019-12-16 | depleted | 0.030 [-0.310, 1.113] | -0.009 [-0.031, 0.012] | 0.656 [0.286, 1.021] | 0.683 [-0.543, 1.189] | 0.317 | no | yes |
| 2020-03-04 | depleted | 0.001 [-0.002, 0.023] | 0.002 [-0.003, 0.006] | 1.513 [1.373, 1.677] | 1.513 [1.370, 1.672] | -0.513 | no | no |
| 2020-03-12 | depleted | 0.020 [0.004, 0.060] | -0.000 [-0.002, 0.001] | 0.988 [0.970, 1.009] | 0.974 [0.930, 0.998] | 0.026 | no | no |
| 2024-09-30 | abundant | 0.002 [-0.031, 0.013] | 0.007 [-0.024, 0.034] | 0.517 [0.331, 0.674] | 0.517 [0.339, 0.685] | 0.483 | no | yes |
| 2024-12-26 | abundant | 0.001 [-0.016, 0.009] | -0.015 [-0.060, 0.033] | 0.626 [0.497, 0.732] | 0.625 [0.515, 0.730] | 0.375 | no | yes |
| 2025-09-15 | depleted | -0.032 [-0.985, 0.279] | -0.005 [-0.032, 0.021] | -0.664 [-1.275, -0.088] | -0.682 [-1.329, 0.330] | 1.682 | no | yes |
| 2025-09-30 | depleted | -0.001 [-0.262, 0.098] | 0.012 [-0.010, 0.031] | 0.274 [-0.008, 0.509] | 0.267 [0.003, 0.610] | 0.733 | yes | yes |
| 2025-10-15 | depleted | 0.000 [-0.003, 0.013] | 0.000 [-0.001, 0.001] | 1.115 [1.083, 1.154] | 1.116 [1.079, 1.152] | -0.116 | no | no |
| 2025-12-15 | depleted | 0.002 [-0.038, 0.140] | -0.001 [-0.006, 0.004] | 0.849 [0.661, 1.001] | 0.854 [0.603, 1.013] | 0.146 | no | no |
| 2025-12-26 | depleted | -0.004 [-0.063, 0.176] | 0.003 [-0.004, 0.010] | 0.542 [0.408, 0.654] | 0.555 [0.321, 0.688] | 0.445 | no | yes |
| 2026-02-17 | depleted | -0.001 [-0.019, 0.011] | -0.001 [-0.003, 0.000] | 0.736 [0.651, 0.812] | 0.735 [0.655, 0.808] | 0.265 | no | yes |
| 2026-03-02 | depleted | -0.009 [-0.391, 0.158] | -0.000 [-0.017, 0.013] | 0.119 [-0.372, 0.531] | 0.105 [-0.325, 0.613] | 0.895 | yes | yes |
| 2026-04-15 | depleted | -0.000 [-0.002, 0.004] | -0.001 [-0.003, 0.000] | 0.797 [0.733, 0.854] | 0.797 [0.731, 0.851] | 0.203 | no | no |

## Note (15 October 2026): the placebo with a 2 bp rise floor

**Development evidence, not a verdict.** A new record, `results/h10/placebo_floor_2bp.json` (sha256 `4d3ee5cdfcc9d12f45b3c8f1c72b706e0cb71fd6c7df1983f1715b03651458ae`, directive #85), re-runs only the placebo of the published record at the same pin, seeds and episodes, with and without the floor of the draft amendment in section 10 of the method record. The step 2 record above is unchanged.

- unfloored (the published reading): placebo gap -0.39 (90% interval -0.62 to -0.19, n = 31), 620 placebo windows, 324 attributable;
- floored (a placebo window needs a rise of at least 2 bp): placebo gap -0.20 (90% interval -0.39 to -0.02, n = 31), 508 of 620 windows excluded, 112 attributable.

## What this page does not do

It states no verdict, registers nothing, scores no forecast, publishes no figure of the model repo and changes nothing in it. Registration of the frozen method is her attested action (plan, H10, "Registration").
