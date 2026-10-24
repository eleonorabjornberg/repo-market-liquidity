# H7m: the three goalposts, scored on development days (step 5)

Generated from `results/h7/step5-scores.json` by `scripts/h7_step5.py --render`; never edited by hand.
Tier: **development**. Development evidence, **not a verdict**. A development reading is never a verdict (docs/decisions/measurement-protocol.md section 1). Stage document: `docs/stages/h7-step5.md`. No estimator is re-fitted; every estimate is the account's (`results/h7/distribution-account.json`).

Panel version 4 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`; parent `08ff67e27bc3d7e357491cf8e1da59793702b3fb`. Window 2020-03-17 to 2025-12-31: 1447 scored days, 98 stress events (a day with Fed repo operations accepted of $1 bn or more). Scarcity-state days by level: S=0: 1041, S=1: 313, S=2: 41, S=3: 52. 10000 stationary-bootstrap draws, mean block 10, seed 20261024 plus the split's position; intervals are the 5th and 95th percentiles, no look spent. The MME is 0.05 AUROC points; the event floor is 10. Estimates are in shares of bank assets; widths in points. Sources: `results/h7/calendar-clean.json` (`c3acfc90f9e4`), `results/h7/distribution-account.json` (`5b8ee596d16c`), `results/h7/kink.json` (`c37bf6b6f16a`).

A gain is AUROC(estimate) minus AUROC of the benchmark, ranked low to high, ties half, in AUROC points. Against R: all days; against R+S: within each scarcity-state level, pooled by events (protocol section 5); against S: AUROC(-S), on the days the estimator serves. A missing estimate takes R's place for R and R+S (section 11). A position against the MME is in words only.

## Goalpost 1 (stable)

| Estimator | Calendar days | Reading |
|---|---|---|
| B | all (provisional: trained on calendar days) | as in A's restated record (results/h7/kink.json): worst gap 6.25 points on 2021-07-20 over 1426 days compared; 0 missing refits; bar 0.5 points; holds: false |
| C | all (provisional: trained on calendar days) | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) |
| CV1 | clean | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) |
| CV2 | clean | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) |
| CV3 | clean | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) |
| CV4 | all (provisional: trained on calendar days) | unreadable on development data, read prospectively (Eleonora, 22 Oct, option 6) |
| V1 | clean | as in A's restated record (results/h7/kink.json): worst gap 3.50 points on 2022-11-22 over 1300 days compared; 4 missing refits; bar 0.5 points; holds: false |
| V2 | all (provisional: trained on calendar days) | as in A's restated record (results/h7/kink.json): worst gap 3.00 points on 2022-12-22 over 1300 days compared; 5 missing refits; bar 0.5 points; holds: false |
| V3 | all (provisional: trained on calendar days) | as in A's restated record (results/h7/kink.json): worst gap 8.75 points on 2021-09-17 over 1342 days compared; 3 missing refits; bar 0.5 points; holds: false |
| V4 | clean | as in A's restated record (results/h7/kink.json): worst gap 3.50 points on 2022-12-22 over 1321 days compared; 4 missing refits; bar 0.5 points; holds: false |
| V5 | clean | as in A's restated record (results/h7/kink.json): worst gap 5.50 points on 2022-11-22 over 1258 days compared; 6 missing refits; bar 0.5 points; holds: false |
| V6 | clean | as in A's restated record (results/h7/kink.json): worst gap 2.00 points on 2020-10-15 over 1006 days compared; 17 missing refits; bar 0.5 points; holds: false |

## Goalpost 2 (sharp): median 90% interval width, points, against the 3-point bar

A missing day counts as over the bar (sections 4 and 11); the median over the days with an interval is beside it (the form A's record gives).

| Estimator | Window days | Missing | Median, missing counted over | Position | Median over served days | Position |
|---|---|---|---|---|---|---|
| B | 1447 | 0 | 3.25 | not under the bar | 3.25 | not under the bar |
| C | 1447 | 0 | 3.46 | not under the bar | 3.46 | not under the bar |
| CV3 | 1447 | 0 | 2.54 | under the bar | 2.54 | under the bar |
| V1 | 1447 | 84 | 2.25 | under the bar | 2.25 | under the bar |
| V2 | 1447 | 105 | 2.75 | under the bar | 2.75 | under the bar |
| V3 | 1447 | 63 | 2.50 | under the bar | 2.50 | under the bar |
| V4 | 1447 | 84 | 2.50 | under the bar | 2.50 | under the bar |
| V5 | 1447 | 126 | 2.25 | under the bar | 2.25 | under the bar |
| V6 | 1447 | 357 | 2.75 | under the bar | 1.75 | under the bar |

## Goalpost 3 (informative): the information gain, pooled

| Estimator | Missing share | Against R | Against S | Against R+S | R+S against the MME |
|---|---|---|---|---|---|
| B | 0.0% | -0.205 [-0.323, -0.105] | -0.482 [-0.639, -0.295] | -0.096 [-0.312, +0.113] | straddles the MME |
| C | 0.0% | +0.031 [-0.006, +0.072] | -0.245 [-0.430, -0.052] | +0.072 [+0.006, +0.161] | straddles the MME |
| CV3 | 0.0% | +0.034 [-0.004, +0.075] | -0.243 [-0.428, -0.050] | +0.104 [+0.026, +0.212] | straddles the MME |
| V1 | 5.8% | -0.266 [-0.444, -0.110] | -0.485 [-0.654, -0.279] | -0.090 [-0.318, +0.132] | straddles the MME |
| V2 | 7.3% | -0.311 [-0.490, -0.151] | -0.461 [-0.649, -0.230] | -0.174 [-0.403, +0.065] | straddles the MME |
| V3 | 4.4% | -0.111 [-0.193, -0.032] | -0.412 [-0.574, -0.237] | +0.004 [-0.174, +0.167] | straddles the MME |
| V4 | 5.8% | -0.323 [-0.503, -0.162] | -0.463 [-0.645, -0.239] | -0.187 [-0.413, +0.048] | below the MME |
| V5 | 8.7% | -0.120 [-0.213, -0.032] | -0.444 [-0.609, -0.272] | +0.195 [+0.006, +0.382] | straddles the MME |
| V6 | 24.7% | +0.040 [-0.017, +0.106] | -0.338 [-0.544, -0.121] | +0.160 [+0.038, +0.300] | straddles the MME |

Missing days take R's place (section 11). More than 5% missing days would void a registration; that is a registration rule, reported here and not applied: V1 (5.8%), V2 (7.3%), V4 (5.8%), V5 (8.7%), V6 (24.7%) over the line.

## Not scorable

- CV1: not scorable. the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted.
- CV2: not scorable. the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted.
- CV4: not scorable. the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted.

## R, S and R+S, scored on the same days (AUROC, 90% interval)

R+S is R within a scarcity-state level, pooled by events (section 5 fits no model). Each is computed here and not cited from Stage 6.

| Split | Days | Events | R | S | R+S |
|---|---|---|---|---|---|
| all: all | 1447 | 98 | 0.628 [0.432, 0.844] | 0.904 [0.865, 0.939] | 0.449 [0.273, 0.611] |
| day_type: month_end | 116 | 11 | 0.659 [0.272, 1.000] | 0.954 [0.500, 1.000] | 0.325 [0.029, 0.551] |
| day_type: ordinary | 1236 | 73 | 0.617 [0.393, 0.869] | 0.910 [0.868, 0.953] | 0.464 [0.258, 0.665] |
| day_type: quarter_end (under the event floor) | 24 | 5 | 0.737 [0.522, 0.841] | 0.726 [0.500, 0.891] | 0.517 [0.353, 0.737] |
| day_type: tax_date (under the event floor) | 71 | 9 | 0.673 [0.414, 0.989] | 0.903 [0.500, 0.993] | 0.674 [0.250, 0.875] |
| era: 2021 on | 1247 | 31 | 0.961 [0.907, 0.985] | 0.948 [0.862, 0.987] | 0.459 [0.311, 0.608] |
| regime: 2020 | 200 | 67 | 0.346 [0.079, 0.667] | 0.591 [0.500, 0.729] | 0.177 [0.032, 0.390] |
| regime: 2021-23 (under the event floor) | 748 | 0 | 0.500 [0.500, 0.500] | 0.500 [0.500, 0.500] | 0.500 [0.500, 0.500] |
| regime: 2024 (under the event floor) | 250 | 1 | 0.671 [0.500, 0.794] | 0.498 [0.496, 0.500] | 0.673 [0.500, 0.795] |
| regime: 2025-26 | 249 | 30 | 0.884 [0.795, 0.944] | 0.892 [0.812, 0.948] | 0.439 [0.277, 0.576] |

## Splits: the gain against R+S (the section 5 statistic) by regime and by pressure-day type

Each split is bootstrapped on its own days. † marks a split under the event floor of 10 events: it is reported and labelled, never dropped. "no usable event" means the split (or every scarcity-state level in it) has no event or no other day.

| Estimator | all: all | day_type: month_end | day_type: ordinary | day_type: quarter_end † | day_type: tax_date † | era: 2021 on | regime: 2020 | regime: 2021-23 † | regime: 2024 † | regime: 2025-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | -0.096 [-0.312, +0.113] | +0.009 [-0.286, +0.291] | -0.129 [-0.406, +0.143] | +0.133 [-0.228, +0.333] | +0.000 [-0.150, +0.222] | -0.095 [-0.240, +0.042] | +0.142 [-0.035, +0.330] | no usable event | -0.157 [-0.262, +0.000] | -0.076 [-0.209, +0.067] |
| C | +0.072 [+0.006, +0.161] | +0.132 [+0.000, +0.253] | +0.069 [+0.005, +0.159] | +0.083 [+0.000, +0.190] | -0.194 [-0.438, +0.000] | +0.076 [-0.060, +0.273] | +0.096 [+0.000, +0.201] | no usable event | -0.044 [-0.095, +0.010] | +0.079 [-0.057, +0.284] |
| CV3 | +0.104 [+0.026, +0.212] | +0.167 [+0.000, +0.305] | +0.096 [+0.022, +0.208] | +0.083 [+0.000, +0.190] | -0.194 [-0.438, +0.000] | +0.148 [-0.007, +0.362] | +0.102 [-0.013, +0.224] | no usable event | -0.024 [-0.065, +0.022] | +0.158 [+0.003, +0.381] |
| V1 | -0.090 [-0.318, +0.132] | +0.044 [-0.263, +0.338] | -0.125 [-0.416, +0.157] | +0.192 [-0.125, +0.367] | -0.030 [-0.200, +0.222] | -0.089 [-0.230, +0.048] | +0.186 [-0.015, +0.394] | no usable event | +0.000 [+0.000, +0.000] | -0.076 [-0.209, +0.067] |
| V2 | -0.174 [-0.403, +0.065] | -0.096 [-0.442, +0.242] | -0.200 [-0.484, +0.092] | +0.158 [-0.188, +0.354] | -0.212 [-0.429, +0.200] | -0.110 [-0.233, -0.003] | +0.074 [-0.197, +0.314] | no usable event | +0.000 [+0.000, +0.000] | -0.096 [-0.212, +0.009] |
| V3 | +0.004 [-0.174, +0.167] | +0.237 [+0.000, +0.382] | -0.015 [-0.238, +0.180] | +0.008 [-0.107, +0.184] | -0.020 [-0.114, +0.000] | -0.084 [-0.217, +0.054] | +0.183 [+0.039, +0.352] | no usable event | +0.004 [+0.000, +0.008] | -0.072 [-0.203, +0.081] |
| V4 | -0.187 [-0.413, +0.048] | -0.114 [-0.446, +0.188] | -0.213 [-0.493, +0.075] | +0.100 [-0.304, +0.333] | -0.242 [-0.491, +0.200] | -0.110 [-0.240, -0.000] | +0.042 [-0.212, +0.270] | no usable event | -0.020 [-0.045, +0.000] | -0.092 [-0.211, +0.016] |
| V5 | +0.195 [+0.006, +0.382] | +0.412 [+0.000, +0.611] | +0.221 [-0.000, +0.434] | -0.058 [-0.171, +0.111] | +0.061 [+0.000, +0.143] | -0.093 [-0.231, +0.044] | +0.517 [+0.246, +0.743] | no usable event | +0.004 [+0.000, +0.008] | -0.072 [-0.203, +0.081] |
| V6 | +0.160 [+0.038, +0.300] | +0.325 [+0.000, +0.500] | +0.174 [+0.036, +0.336] | +0.075 [+0.000, +0.227] | +0.030 [-0.100, +0.182] | -0.006 [-0.021, +0.003] | +0.300 [+0.099, +0.525] | no usable event | +0.004 [+0.000, +0.008] | +0.004 [-0.011, +0.031] |

## Splits: the gain against R

| Estimator | all: all | day_type: month_end | day_type: ordinary | day_type: quarter_end † | day_type: tax_date † | era: 2021 on | regime: 2020 | regime: 2021-23 † | regime: 2024 † | regime: 2025-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | -0.205 [-0.323, -0.105] | -0.145 [-0.279, +0.000] | -0.220 [-0.359, -0.098] | -0.158 [-0.275, +0.008] | -0.186 [-0.339, +0.000] | -0.130 [-0.205, -0.074] | +0.089 [-0.095, +0.273] | no usable event | -0.157 [-0.261, +0.000] | -0.008 [-0.035, +0.004] |
| C | +0.031 [-0.006, +0.072] | +0.047 [-0.004, +0.098] | +0.023 [-0.011, +0.057] | +0.053 [-0.016, +0.138] | +0.061 [-0.007, +0.119] | +0.003 [-0.002, +0.012] | +0.070 [-0.007, +0.149] | no usable event | -0.044 [-0.094, +0.010] | +0.006 [-0.008, +0.032] |
| CV3 | +0.034 [-0.004, +0.075] | +0.050 [-0.004, +0.106] | +0.025 [-0.010, +0.061] | +0.053 [-0.016, +0.138] | +0.061 [-0.007, +0.119] | +0.007 [-0.000, +0.019] | +0.087 [-0.007, +0.184] | no usable event | -0.024 [-0.065, +0.022] | +0.025 [+0.005, +0.059] |
| V1 | -0.266 [-0.444, -0.110] | -0.197 [-0.334, +0.000] | -0.297 [-0.517, -0.104] | -0.079 [-0.200, +0.105] | -0.197 [-0.347, +0.000] | -0.165 [-0.240, -0.099] | -0.053 [-0.453, +0.261] | no usable event | +0.000 [+0.000, +0.000] | -0.008 [-0.035, +0.004] |
| V2 | -0.311 [-0.490, -0.151] | -0.228 [-0.367, +0.000] | -0.335 [-0.550, -0.143] | -0.111 [-0.250, +0.091] | -0.328 [-0.487, +0.000] | -0.181 [-0.257, -0.113] | -0.145 [-0.551, +0.195] | no usable event | +0.000 [+0.000, +0.000] | -0.010 [-0.036, +0.000] |
| V3 | -0.111 [-0.193, -0.032] | -0.096 [-0.267, +0.055] | -0.116 [-0.209, -0.031] | -0.068 [-0.250, +0.148] | -0.134 [-0.268, +0.000] | -0.165 [-0.243, -0.087] | +0.153 [+0.028, +0.297] | no usable event | +0.004 [+0.000, +0.008] | -0.001 [-0.032, +0.031] |
| V4 | -0.323 [-0.503, -0.162] | -0.243 [-0.392, +0.000] | -0.347 [-0.563, -0.153] | -0.158 [-0.304, +0.059] | -0.339 [-0.500, +0.000] | -0.195 [-0.275, -0.125] | -0.171 [-0.566, +0.152] | no usable event | -0.020 [-0.044, +0.000] | -0.010 [-0.036, +0.002] |
| V5 | -0.120 [-0.213, -0.032] | -0.129 [-0.327, +0.065] | -0.113 [-0.216, -0.015] | -0.142 [-0.305, +0.086] | -0.177 [-0.361, +0.000] | -0.237 [-0.322, -0.153] | +0.433 [+0.172, +0.671] | no usable event | +0.004 [+0.000, +0.008] | -0.001 [-0.032, +0.031] |
| V6 | +0.040 [-0.017, +0.106] | +0.040 [-0.045, +0.148] | +0.044 [-0.019, +0.119] | +0.058 [-0.043, +0.196] | -0.009 [-0.121, +0.096] | -0.018 [-0.046, +0.000] | +0.252 [+0.076, +0.457] | no usable event | +0.004 [+0.000, +0.008] | +0.007 [-0.001, +0.033] |

## Splits: the gain against S

| Estimator | all: all | day_type: month_end | day_type: ordinary | day_type: quarter_end † | day_type: tax_date † | era: 2021 on | regime: 2020 | regime: 2021-23 † | regime: 2024 † | regime: 2025-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | -0.482 [-0.639, -0.295] | -0.441 [-0.799, +0.000] | -0.512 [-0.680, -0.306] | -0.147 [-0.397, +0.097] | -0.417 [-0.685, +0.000] | -0.118 [-0.183, -0.061] | -0.155 [-0.324, +0.004] | no usable event | +0.016 [-0.139, +0.151] | -0.016 [-0.049, +0.006] |
| C | -0.245 [-0.430, -0.052] | -0.248 [-0.587, +0.000] | -0.270 [-0.479, -0.053] | +0.063 [-0.190, +0.318] | -0.169 [-0.460, +0.021] | +0.015 [-0.001, +0.056] | -0.175 [-0.393, +0.056] | no usable event | +0.129 [-0.016, +0.247] | -0.003 [-0.027, +0.027] |
| CV3 | -0.243 [-0.428, -0.050] | -0.245 [-0.585, +0.000] | -0.268 [-0.477, -0.050] | +0.063 [-0.190, +0.318] | -0.169 [-0.460, +0.021] | +0.019 [+0.002, +0.062] | -0.158 [-0.378, +0.071] | no usable event | +0.149 [+0.000, +0.269] | +0.017 [-0.005, +0.048] |
| V1 | -0.485 [-0.654, -0.279] | -0.464 [-0.799, +0.000] | -0.528 [-0.707, -0.288] | -0.150 [-0.417, +0.154] | -0.381 [-0.673, +0.000] | -0.163 [-0.240, -0.088] | -0.104 [-0.336, +0.170] | no usable event | +0.173 [+0.000, +0.295] | -0.016 [-0.049, +0.006] |
| V2 | -0.461 [-0.649, -0.230] | -0.407 [-0.755, +0.000] | -0.499 [-0.705, -0.226] | -0.165 [-0.421, +0.125] | -0.473 [-0.787, +0.000] | -0.180 [-0.258, -0.105] | -0.120 [-0.335, +0.140] | no usable event | +0.173 [+0.000, +0.295] | -0.019 [-0.052, +0.004] |
| V3 | -0.412 [-0.574, -0.237] | -0.413 [-0.732, +0.000] | -0.434 [-0.614, -0.239] | -0.088 [-0.439, +0.219] | -0.365 [-0.630, +0.000] | -0.163 [-0.246, -0.072] | -0.092 [-0.312, +0.130] | no usable event | +0.175 [+0.000, +0.296] | -0.022 [-0.066, +0.008] |
| V4 | -0.463 [-0.645, -0.239] | -0.414 [-0.751, +0.000] | -0.499 [-0.709, -0.236] | -0.218 [-0.456, +0.047] | -0.469 [-0.766, +0.000] | -0.191 [-0.272, -0.117] | -0.180 [-0.380, +0.073] | no usable event | +0.153 [-0.004, +0.273] | -0.018 [-0.051, +0.005] |
| V5 | -0.444 [-0.609, -0.272] | -0.471 [-0.788, +0.000] | -0.455 [-0.642, -0.262] | -0.194 [-0.551, +0.118] | -0.442 [-0.732, +0.000] | -0.255 [-0.349, -0.155] | +0.188 [+0.005, +0.325] | no usable event | +0.175 [+0.000, +0.296] | -0.022 [-0.066, +0.008] |
| V6 | -0.338 [-0.544, -0.121] | -0.350 [-0.741, +0.000] | -0.351 [-0.592, -0.104] | -0.055 [-0.417, +0.244] | -0.330 [-0.652, +0.000] | -0.023 [-0.060, +0.005] | +0.007 [-0.216, +0.189] | no usable event | +0.175 [+0.000, +0.296] | -0.011 [-0.042, +0.014] |

## Splits: goalpost 2, median width in points (missing counted over the bar)

| Estimator | all: all | day_type: month_end | day_type: ordinary | day_type: quarter_end † | day_type: tax_date † | era: 2021 on | regime: 2020 | regime: 2021-23 † | regime: 2024 † | regime: 2025-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | 3.25 | 3.25 | 3.25 | 3.00 | 3.25 | 2.75 | 3.50 | 5.76 | 2.25 | 2.50 |
| C | 3.46 | 3.49 | 3.46 | 3.43 | 3.48 | 3.49 | 3.13 | 3.37 | 3.63 | 3.58 |
| CV3 | 2.54 | 2.55 | 2.54 | 2.53 | 2.54 | 2.55 | 2.41 | 2.52 | 2.57 | 2.69 |
| V1 | 2.25 | 2.25 | 2.25 | 2.25 | 2.25 | 2.25 | 3.00 | 5.00 | 2.25 | 2.25 |
| V2 | 2.75 | 2.75 | 2.75 | 2.75 | 2.75 | 2.75 | 4.00 | 2.75 | 1.01 | 2.75 |
| V3 | 2.50 | 2.50 | 2.50 | 2.63 | 2.50 | 2.75 | 2.25 | 8.00 | 2.47 | 2.50 |
| V4 | 2.50 | 2.50 | 2.50 | 2.50 | 2.50 | 2.25 | 3.75 | 4.00 | 1.00 | 2.50 |
| V5 | 2.25 | 2.25 | 2.25 | 2.50 | 2.25 | 2.00 | 2.50 | 6.85 | 1.50 | 2.00 |
| V6 | 2.75 | 2.62 | 2.75 | 2.75 | 1.75 | 2.00 | 2.75 | 8.50 | 1.75 | 1.75 |

## The variant count (for step 6)

- Estimators declared and run: 12 (A's B and six variants, C and four variants), of which 10 are variants; scored: B, V1, V2, V3, V4, V5, V6, C, CV3; not scorable: CV1, CV2, CV4.
- Declared and not run: D, DV1, DV2, DV3, DV4 (D dropped under #142).
- Added by the records: the kink record 6, the calendar-clean record 4. The count from Stages 2 to 6: stated by no record; not counted here.
- How a not-scorable estimator counts is a marked question (Q4 in the stage document); the default counts it.

## Checks the run made

- Served-day counts equal to the tracked records': B, V1, V2, V3, V4, V5, V6, C, CV1, CV2, CV3, CV4.
- Median served widths equal to the tracked records' (to 0.001 point): B, V1, V2, V3, V4, V5, V6, C, CV3.
- A's account equals 100 x (R - k of the refit in force) on every served day, to the rounding: B, V1, V2, V3, V4, V5, V6.
