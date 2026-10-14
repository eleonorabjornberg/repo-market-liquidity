# H10, step 2: the declared method applied to the development onsets

**Serves:** H10 (pressure episodes can be attributed to drivers), development step 2 of the plan (`docs/research/plan.md`).
Directive #70. **Development evidence, never a verdict** (`docs/decisions/measurement-protocol.md` section 1;
eleonorabjornberg/repo-market-model#640): it confirms nothing, registers nothing and publishes no figure. The record is
`results/h10/development.json`; the code is `src/repo_liquidity/h10_apply.py` and `scripts/h10_step2.py`.

## 1. What the step had to show, and whether it did

| Had to show | Shown? |
|---|---|
| The episode list equals the model repo's onsets at the pin, and the cross-check holds | Yes: 31 onsets from `repo_model.onset.onset_flags`, equal to `repo_model.pressure.onsets` at +5 bp (`tests/test_h10_step2.py`, `RecordTests`) |
| Every episode is in the table: attributed, missed or not attributable | Yes: 31 rows, 0 not attributable |
| The full suite passes in one process, zero `expectedFailure` | See the pull request |
| No day after 2026-09-03 is read | Yes: the last day read is 2026-09-03, the parent's development end, read from its lockbox |

## 2. What was applied

- **The method** is `docs/decisions/h10-method.md`, sections 1 to 9 and the answers of 9f, unchanged: a window of 5 baseline
  days and 5 window days, a leave-neighbourhood-out regression of the spread change on the driver changes with
  Shapley shares, the stationary bootstrap (mean block 10, 10,000 draws, seed 20261013, 90% intervals),
  20 placebo windows per episode, the residual bar 0.5 read as an absolute value.
- **The drivers** are the five of `DRIVERS_WITH_ON_RRP`: Treasury settlement, TGA, reserves, quarter-end and ON RRP take-up
  (the New York Fed's operation results, `reverse_repo_total_accepted`), each as the window change. Shapley shares run over 32 refits.
- **The null** is N1 (1,000 draws, seed 20261013): the spread less the drivers' fitted effect, resampled by the stationary
  bootstrap, onsets picked from each resample by the parent's rule, each pick attributed against the real drivers. It gave
  22,401 picks. The bar is the 95th percentile of their explained shares: **0.234** (median 0.003,
  90th 0.125, 99th 0.743). An episode **beats the null** when its explained share is above the bar.
- **The outcome rule** counts an episode only if it is under the residual bar *and* beats the null (9f, answer 4). Every episode is in the
  denominator; a negative residual is a miss.
- **The panel** is version 1 (digest `acb77874e0ca2c9eeee1c33a229f5e12745e65bb1224088d52c391dbf54be2ab`, 2104 rows, 2018-04-03 to 2026-09-03), rebuilt
  from the tracked fixtures to its manifest. The parent is pinned at `09640f5bb4063da150e09a285d242cd28db1c136`; its published panel digest is `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999`.
- **Information set.** Each episode goes through `attribution.attribute`, which asks the parent's `InformationRule` (Phase 3's declaration, 16:00
  decision instant) whether the spread and all five drivers of the window were public at the **report day**: 10 panel days after the
  onset (plan, Q7). No episode raised `LookAheadError`. `attribute`'s `rule`, `dates` and `report_index` are required (PR #61's ruling); the
  synthetic tests use the separate `attribute_synthetic`.
- **Not built:** the ON RRP regime interaction, which her answer 5 defers to a later sensitivity.

## 3. The outcome counts

| Group | Episodes | Under the residual bar | Beats the null | Both (counted) | Not attributable |
|---|---|---|---|---|---|
| All development onsets | 31 | 4 (6% to 26%) | 14 (31% to 60%) | 4 (6% to 26%) | 0 |
| ON RRP depleted | 29 | 4 (6% to 27%) | 12 (28% to 57%) | 4 (6% to 27%) | 0 |
| ON RRP abundant | 2 | 0 (0% to 57%) | 2 (43% to 100%) | 0 (0% to 57%) | 0 |
| Quarter-end onsets | 4 | 1 (6% to 64%) | 4 (60% to 100%) | 1 (6% to 64%) | 0 |
| Other onsets | 27 | 3 (5% to 25%) | 10 (24% to 53%) | 3 (5% to 25%) | 0 |

Each count is shown with a Wilson 90% interval on the share of episodes. It treats the episodes as independent, which they are not
quite (they cluster at quarter-ends and in 2018-19), so it is, if anything, too narrow.

What the development table shows: the residual share is under 0.5 in 4 of 31 (6% to 26%) of the development episodes, and
4 of 31 (6% to 26%) also beat the null. Under the plan's rule ("drivers named" needs more than half) the table reads **residual dominates**;
on the residual bar alone it reads **residual dominates**. This is a description of the development table, not a verdict: there is none under the
measurement protocol until a method is registered and confirmed prospectively.

The counted episodes are 2019-06-17, 2019-11-29, 2025-09-30, 2026-03-02.

**Progress markers** (plan, H10; each over the attributed episodes, with a distribution-free 90% interval on the median):

- median residual share: 0.78 (90% interval 0.66 to 0.85, n = 31);
- explained share above reserves alone: 0.23 (90% interval 0.13 to 0.37, n = 31);
- placebo gap, the episode's explained share less its placebo windows' median: -0.39 (90% interval -0.62 to -0.19, n = 31).

## 4. Reading the table (for the review, not a verdict)

- **The drivers explain ordinary windows of the same day type at least as well as they explain the episodes.** The median placebo gap is negative,
  and in the table's last column the share of an episode's placebo windows that explain at least as much is often above one half.
- **Beating the null is easier than being under the bar.** 14 of 31 (31% to 60%) beat the null; only 4 are under the residual bar.
- **Small rises.** 5 episodes have a window rise under 1 bp (2019-01-15, 2019-06-17, 2019-12-16, 2025-09-15, 2026-03-02): their shares are a ratio to a small
  number and are unstable. They are in the table and in the denominator. 2 episodes have a negative residual share, that is, the drivers'
  prediction is larger than the rise (2019-01-15, 2025-09-15); under the decided rule these are misses.
- **ON RRP regime.** Only 2 onsets are in the abundant regime (2024-09-30, 2024-12-26), so that group says little; the finding's concern (one fit across
  both regimes) is still open until the interaction sensitivity is run.
- **Quarter-end onsets** are 4; the count is given, not interpreted.
- **The null is conservative** by construction (the fit for a null pick does not leave it out), so beating it is a low bar.

## 5. The table

Shapley shares with their 90% bootstrap intervals first, the point share after the interval (section 2 of the method record).
"Above reserves alone" is the drivers' explained share less that of reserves alone. "Placebo >= episode" is the share of the episode's placebo
windows (same length and day type, touching no episode) whose explained share is at least the episode's, with the number of attributable placebo windows.

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

## 6. Reproduce

```
PYTHONPATH=src python3 scripts/h10_step2.py --workers 4     # about 8 minutes on four cores; rewrites results/h10/development.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover -s tests
```

`tests/test_h10_step2.py` rebuilds the panel, recomputes every point share, the benchmark and the placebo windows and compares them with the
record, and recomputes the first episode's interval in full. The record is a development record made at the pin above; it is not edited in place.

## 7. What this step does not do

It states no verdict, registers nothing, scores no forecast, publishes nothing and changes nothing in the model repo. The H10 method record changed
only by recording her answers (section 9f) and its status line.
