# H7m: the account of the bank distribution for A and C (development)

Generated from `results/h7/distribution-account.json` by `scripts/h7_account.py --render`; never edited by hand.
Tier: **development**. Development evidence, not a verdict. The account's size decides nothing (docs/decisions/measurement-protocol.md section 8). Stage document: `docs/stages/h7-step4.md`.

Panel version 4 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`; parent `08ff67e27bc3d7e357491cf8e1da59793702b3fb`; days served 2020-03-17 to 2025-12-31 (window ends 2025-12-31); 2000 bootstrap draws for C's intervals. Unit: points of bank assets. Sources: `results/h7/calendar-clean.json` (`c3acfc90f9e4`), `results/h7/kink.json` (`c37bf6b6f16a`).

The three alternatives for how the same reserves spread over the three H.8 groups: `as_observed`, `all_large_domestic`, `proportional_to_assets` (protocol section 8). Each keeps the week's total reserves.

**A as defined.** A as defined is R - k. It has no per-group term, so no redistribution of the same reserves over the groups changes it: all three alternatives give the same figure.

**Marked reading, for Eleonora.** A through step 2's group machinery, with A's single kink read as every group's buffer share (shares = (k, k, k)), is a marked reading (docs/stages/h7-step4.md section 2). It is reported beside A as defined, never in its place.

## Days served

| Estimator | View | Calendar days | Served | Missing | Break-week days |
|---|---|---|---|---|---|
| A_B | A as defined | all (provisional: trained on calendar days) | 1447 | 0 | 48 |
| A_V1 | A as defined | clean | 1363 | 84 (the refit in force did not fit: 84) | 38 |
| A_V2 | A as defined | all (provisional: trained on calendar days) | 1342 | 105 (the refit in force did not fit: 105) | 48 |
| A_V3 | A as defined | all (provisional: trained on calendar days) | 1384 | 63 (the refit in force did not fit: 63) | 48 |
| A_V4 | A as defined | clean | 1363 | 84 (the refit in force did not fit: 84) | 48 |
| A_V5 | A as defined | clean | 1321 | 126 (the refit in force did not fit: 126) | 48 |
| A_V6 | A as defined | clean | 1090 | 357 (the refit in force did not fit: 357) | 30 |
| Ag_B | A through the group machinery | all (provisional: trained on calendar days) | 1447 | 0 | 48 |
| Ag_V1 | A through the group machinery | clean | 1363 | 84 (the refit in force did not fit: 84) | 38 |
| Ag_V2 | A through the group machinery | all (provisional: trained on calendar days) | 1342 | 105 (the refit in force did not fit: 105) | 48 |
| Ag_V3 | A through the group machinery | all (provisional: trained on calendar days) | 1384 | 63 (the refit in force did not fit: 63) | 48 |
| Ag_V4 | A through the group machinery | clean | 1363 | 84 (the refit in force did not fit: 84) | 48 |
| Ag_V5 | A through the group machinery | clean | 1321 | 126 (the refit in force did not fit: 126) | 48 |
| Ag_V6 | A through the group machinery | clean | 1090 | 357 (the refit in force did not fit: 357) | 30 |
| C | C | all (provisional: trained on calendar days) | 1447 | 0 | 48 |
| CV1 | C | clean | 0 | 1447 (the refit in force did not fit: 1447) | 0 |
| CV2 | C | clean | 0 | 1447 (the refit in force did not fit: 1447) | 0 |
| CV3 | C | clean | 1447 | 0 | 48 |
| CV4 | C | all (provisional: trained on calendar days) | 0 | 1447 (the refit in force did not fit: 1447) | 0 |

An estimator that serves no day has an empty account, and is listed.

## Aggregate deployable liquidity under each alternative

Points of bank assets over the served days. Interval: the median width of the 90% interval, where the estimator has one.

| Estimator | Alternative | Days | Median | Min | Max | Median 90% width | Days at zero | Median difference from as observed |
|---|---|---|---|---|---|---|---|---|
| A_B | all_large_domestic | 1447 | 1.11 | -3.41 | 7.19 | 3.25 | 0 | 0.00 |
| A_B | as_observed | 1447 | 1.11 | -3.41 | 7.19 | 3.25 | 0 | 0.00 |
| A_B | proportional_to_assets | 1447 | 1.11 | -3.41 | 7.19 | 3.25 | 0 | 0.00 |
| A_V1 | all_large_domestic | 1363 | 0.94 | -3.95 | 7.19 | 2.25 | 0 | 0.00 |
| A_V1 | as_observed | 1363 | 0.94 | -3.95 | 7.19 | 2.25 | 0 | 0.00 |
| A_V1 | proportional_to_assets | 1363 | 0.94 | -3.95 | 7.19 | 2.25 | 0 | 0.00 |
| A_V2 | all_large_domestic | 1342 | 0.60 | -4.16 | 7.19 | 2.75 | 0 | 0.00 |
| A_V2 | as_observed | 1342 | 0.60 | -4.16 | 7.19 | 2.75 | 0 | 0.00 |
| A_V2 | proportional_to_assets | 1342 | 0.60 | -4.16 | 7.19 | 2.75 | 0 | 0.00 |
| A_V3 | all_large_domestic | 1384 | 3.50 | -3.45 | 9.45 | 2.50 | 0 | 0.00 |
| A_V3 | as_observed | 1384 | 3.50 | -3.45 | 9.45 | 2.50 | 0 | 0.00 |
| A_V3 | proportional_to_assets | 1384 | 3.50 | -3.45 | 9.45 | 2.50 | 0 | 0.00 |
| A_V4 | all_large_domestic | 1363 | 0.77 | -4.16 | 7.19 | 2.50 | 0 | 0.00 |
| A_V4 | as_observed | 1363 | 0.77 | -4.16 | 7.19 | 2.50 | 0 | 0.00 |
| A_V4 | proportional_to_assets | 1363 | 0.77 | -4.16 | 7.19 | 2.50 | 0 | 0.00 |
| A_V5 | all_large_domestic | 1321 | 2.09 | -4.41 | 8.94 | 2.25 | 0 | 0.00 |
| A_V5 | as_observed | 1321 | 2.09 | -4.41 | 8.94 | 2.25 | 0 | 0.00 |
| A_V5 | proportional_to_assets | 1321 | 2.09 | -4.41 | 8.94 | 2.25 | 0 | 0.00 |
| A_V6 | all_large_domestic | 1090 | 2.33 | -2.30 | 7.69 | 1.75 | 0 | 0.00 |
| A_V6 | as_observed | 1090 | 2.33 | -2.30 | 7.69 | 1.75 | 0 | 0.00 |
| A_V6 | proportional_to_assets | 1090 | 2.33 | -2.30 | 7.69 | 1.75 | 0 | 0.00 |
| Ag_B | all_large_domestic | 1447 | 5.48 | 2.09 | 10.40 | 1.88 | 0 | 2.19 |
| Ag_B | as_observed | 1447 | 3.19 | 1.70 | 5.53 | 0.66 | 0 | 0.00 |
| Ag_B | proportional_to_assets | 1447 | 0.00 | 0.00 | 5.53 | 1.36 | 805 | -2.87 |
| Ag_V1 | all_large_domestic | 1363 | 5.38 | 2.09 | 10.25 | 1.31 | 0 | 2.10 |
| Ag_V1 | as_observed | 1363 | 3.16 | 1.70 | 5.34 | 0.35 | 0 | 0.00 |
| Ag_V1 | proportional_to_assets | 1363 | 0.00 | 0.00 | 5.34 | 0.50 | 815 | -2.87 |
| Ag_V2 | all_large_domestic | 1342 | 5.23 | 2.11 | 10.16 | 1.59 | 0 | 1.99 |
| Ag_V2 | as_observed | 1342 | 3.06 | 1.67 | 5.34 | 0.38 | 0 | 0.00 |
| Ag_V2 | proportional_to_assets | 1342 | 0.00 | 0.00 | 5.34 | 0.00 | 952 | -2.93 |
| Ag_V3 | all_large_domestic | 1384 | 6.74 | 2.68 | 11.81 | 1.46 | 0 | 3.14 |
| Ag_V3 | as_observed | 1384 | 3.75 | 1.81 | 7.64 | 1.33 | 0 | 0.00 |
| Ag_V3 | proportional_to_assets | 1384 | 2.28 | 0.00 | 7.64 | 2.50 | 273 | -1.38 |
| Ag_V4 | all_large_domestic | 1363 | 5.29 | 2.11 | 10.40 | 1.44 | 0 | 2.05 |
| Ag_V4 | as_observed | 1363 | 3.16 | 1.70 | 5.53 | 0.33 | 0 | 0.00 |
| Ag_V4 | proportional_to_assets | 1363 | 0.00 | 0.00 | 5.53 | 0.00 | 905 | -2.92 |
| Ag_V5 | all_large_domestic | 1321 | 6.04 | 1.77 | 11.18 | 1.28 | 0 | 2.64 |
| Ag_V5 | as_observed | 1321 | 3.47 | 1.53 | 7.09 | 0.61 | 0 | 0.00 |
| Ag_V5 | proportional_to_assets | 1321 | 0.89 | 0.00 | 7.09 | 1.50 | 427 | -2.41 |
| Ag_V6 | all_large_domestic | 1090 | 6.16 | 1.77 | 9.84 | 1.02 | 0 | 2.74 |
| Ag_V6 | as_observed | 1090 | 3.55 | 1.53 | 5.82 | 0.25 | 0 | 0.00 |
| Ag_V6 | proportional_to_assets | 1090 | 1.11 | 0.00 | 5.82 | 1.67 | 191 | -2.29 |
| C | all_large_domestic | 1447 | 9.03 | 4.49 | 13.56 | 2.31 | 0 | 4.35 |
| C | as_observed | 1447 | 4.69 | 0.57 | 9.30 | 3.46 | 0 | 0.00 |
| C | proportional_to_assets | 1447 | 5.58 | 1.61 | 9.60 | 2.55 | 0 | 0.90 |
| CV3 | all_large_domestic | 1447 | 7.88 | 3.35 | 12.41 | 1.16 | 0 | 4.44 |
| CV3 | as_observed | 1447 | 3.43 | 0.36 | 8.10 | 2.54 | 0 | 0.00 |
| CV3 | proportional_to_assets | 1447 | 4.72 | 1.05 | 8.76 | 2.01 | 0 | 1.27 |

## Group by group

Each group's reserves above its own buffer, as points of the groups' total assets (they sum to the aggregate). Median over the served days, and the days on which the group's term is zero.

| Estimator | Alternative | large_domestic median | small_domestic median | foreign_related median | large_domestic days at zero | small_domestic days at zero | foreign_related days at zero |
|---|---|---|---|---|---|---|---|
| Ag_B | all_large_domestic | 5.48 | 0.00 | 0.00 | 0 | 1447 | 1447 |
| Ag_B | as_observed | 0.00 | 0.00 | 3.10 | 1163 | 1417 | 0 |
| Ag_B | proportional_to_assets | 0.00 | 0.00 | 0.00 | 805 | 805 | 805 |
| Ag_V1 | all_large_domestic | 5.38 | 0.00 | 0.00 | 0 | 1363 | 1363 |
| Ag_V1 | as_observed | 0.00 | 0.00 | 3.07 | 1102 | 1343 | 0 |
| Ag_V1 | proportional_to_assets | 0.00 | 0.00 | 0.00 | 815 | 815 | 815 |
| Ag_V2 | all_large_domestic | 5.23 | 0.00 | 0.00 | 0 | 1342 | 1342 |
| Ag_V2 | as_observed | 0.00 | 0.00 | 2.99 | 1133 | 1332 | 0 |
| Ag_V2 | proportional_to_assets | 0.00 | 0.00 | 0.00 | 952 | 952 | 952 |
| Ag_V3 | all_large_domestic | 6.74 | 0.00 | 0.00 | 0 | 1384 | 1384 |
| Ag_V3 | as_observed | 0.00 | 0.00 | 3.43 | 811 | 1180 | 0 |
| Ag_V3 | proportional_to_assets | 1.32 | 0.65 | 0.30 | 273 | 273 | 273 |
| Ag_V4 | all_large_domestic | 5.29 | 0.00 | 0.00 | 0 | 1363 | 1363 |
| Ag_V4 | as_observed | 0.00 | 0.00 | 3.00 | 1128 | 1307 | 0 |
| Ag_V4 | proportional_to_assets | 0.00 | 0.00 | 0.00 | 905 | 905 | 905 |
| Ag_V5 | all_large_domestic | 6.04 | 0.00 | 0.00 | 0 | 1321 | 1321 |
| Ag_V5 | as_observed | 0.00 | 0.00 | 3.03 | 1049 | 1222 | 0 |
| Ag_V5 | proportional_to_assets | 0.51 | 0.26 | 0.12 | 427 | 427 | 427 |
| Ag_V6 | all_large_domestic | 6.16 | 0.00 | 0.00 | 0 | 1090 | 1090 |
| Ag_V6 | as_observed | 0.00 | 0.00 | 3.34 | 849 | 1012 | 0 |
| Ag_V6 | proportional_to_assets | 0.64 | 0.32 | 0.15 | 191 | 191 | 191 |
| C | all_large_domestic | 9.03 | 0.00 | 0.00 | 0 | 1447 | 1447 |
| C | as_observed | 2.15 | 0.30 | 2.41 | 10 | 109 | 0 |
| C | proportional_to_assets | 3.51 | 2.09 | 0.00 | 0 | 0 | 1447 |
| CV3 | all_large_domestic | 7.88 | 0.00 | 0.00 | 0 | 1447 | 1447 |
| CV3 | as_observed | 0.99 | 0.58 | 2.02 | 180 | 0 | 0 |
| CV3 | proportional_to_assets | 2.35 | 2.37 | 0.00 | 10 | 0 | 1447 |

## Median aggregate by calendar year

| Estimator | Year | Days | as_observed | all_large_domestic | proportional_to_assets |
|---|---|---|---|---|---|
| A_B | 2020 | 200 | 2.72 | 2.72 | 2.72 |
| A_B | 2021 | 250 | 3.73 | 3.73 | 3.73 |
| A_B | 2022 | 249 | -1.78 | -1.78 | -1.78 |
| A_B | 2023 | 249 | 1.23 | 1.23 | 1.23 |
| A_B | 2024 | 250 | 1.38 | 1.38 | 1.38 |
| A_B | 2025 | 249 | 0.78 | 0.78 | 0.78 |
| A_V1 | 2020 | 179 | 2.70 | 2.70 | 2.70 |
| A_V1 | 2021 | 187 | 3.91 | 3.91 | 3.91 |
| A_V1 | 2022 | 249 | -2.85 | -2.85 | -2.85 |
| A_V1 | 2023 | 249 | 1.17 | 1.17 | 1.17 |
| A_V1 | 2024 | 250 | 1.30 | 1.30 | 1.30 |
| A_V1 | 2025 | 249 | 0.53 | 0.53 | 0.53 |
| A_V2 | 2020 | 158 | 2.56 | 2.56 | 2.56 |
| A_V2 | 2021 | 187 | 0.46 | 0.46 | 0.46 |
| A_V2 | 2022 | 249 | -3.10 | -3.10 | -3.10 |
| A_V2 | 2023 | 249 | 0.92 | 0.92 | 0.92 |
| A_V2 | 2024 | 250 | 1.05 | 1.05 | 1.05 |
| A_V2 | 2025 | 249 | 0.28 | 0.28 | 0.28 |
| A_V3 | 2020 | 200 | 4.69 | 4.69 | 4.69 |
| A_V3 | 2021 | 250 | 7.69 | 7.69 | 7.69 |
| A_V3 | 2022 | 249 | -1.47 | -1.47 | -1.47 |
| A_V3 | 2023 | 249 | 3.43 | 3.43 | 3.43 |
| A_V3 | 2024 | 249 | 3.55 | 3.55 | 3.55 |
| A_V3 | 2025 | 187 | 2.69 | 2.69 | 2.69 |
| A_V4 | 2020 | 158 | 2.72 | 2.72 | 2.72 |
| A_V4 | 2021 | 208 | 0.79 | 0.79 | 0.79 |
| A_V4 | 2022 | 249 | -3.14 | -3.14 | -3.14 |
| A_V4 | 2023 | 249 | 0.92 | 0.92 | 0.92 |
| A_V4 | 2024 | 250 | 1.29 | 1.29 | 1.29 |
| A_V4 | 2025 | 249 | 0.53 | 0.53 | 0.53 |
| A_V5 | 2020 | 200 | 4.35 | 4.35 | 4.35 |
| A_V5 | 2021 | 187 | 0.46 | 0.46 | 0.46 |
| A_V5 | 2022 | 249 | -3.12 | -3.12 | -3.12 |
| A_V5 | 2023 | 249 | 2.42 | 2.42 | 2.42 |
| A_V5 | 2024 | 249 | 2.55 | 2.55 | 2.55 |
| A_V5 | 2025 | 187 | 1.69 | 1.69 | 1.69 |
| A_V6 | 2020 | 200 | 3.05 | 3.05 | 3.05 |
| A_V6 | 2021 | 157 | 0.95 | 0.95 | 0.95 |
| A_V6 | 2022 | 48 | 2.13 | 2.13 | 2.13 |
| A_V6 | 2023 | 249 | 2.42 | 2.42 | 2.42 |
| A_V6 | 2024 | 249 | 2.55 | 2.55 | 2.55 |
| A_V6 | 2025 | 187 | 1.69 | 1.69 | 1.69 |
| Ag_B | 2020 | 200 | 2.35 | 6.25 | 1.43 |
| Ag_B | 2021 | 250 | 3.00 | 7.19 | 2.41 |
| Ag_B | 2022 | 249 | 2.86 | 4.68 | 0.00 |
| Ag_B | 2023 | 249 | 3.43 | 5.41 | 0.00 |
| Ag_B | 2024 | 250 | 3.33 | 5.62 | 0.17 |
| Ag_B | 2025 | 249 | 3.39 | 4.99 | 0.00 |
| Ag_V1 | 2020 | 179 | 2.45 | 6.31 | 1.44 |
| Ag_V1 | 2021 | 187 | 2.99 | 7.35 | 2.51 |
| Ag_V1 | 2022 | 249 | 2.80 | 3.50 | 0.00 |
| Ag_V1 | 2023 | 249 | 3.40 | 5.39 | 0.00 |
| Ag_V1 | 2024 | 250 | 3.33 | 5.57 | 0.08 |
| Ag_V1 | 2025 | 249 | 3.36 | 4.85 | 0.00 |
| Ag_V2 | 2020 | 158 | 2.27 | 6.25 | 1.33 |
| Ag_V2 | 2021 | 187 | 2.93 | 6.64 | 0.00 |
| Ag_V2 | 2022 | 249 | 2.79 | 3.13 | 0.00 |
| Ag_V2 | 2023 | 249 | 3.37 | 5.25 | 0.00 |
| Ag_V2 | 2024 | 250 | 3.30 | 5.42 | 0.00 |
| Ag_V2 | 2025 | 249 | 3.32 | 4.71 | 0.00 |
| Ag_V3 | 2020 | 200 | 3.73 | 7.47 | 3.44 |
| Ag_V3 | 2021 | 250 | 5.82 | 9.84 | 5.82 |
| Ag_V3 | 2022 | 249 | 2.93 | 4.82 | 0.00 |
| Ag_V3 | 2023 | 249 | 3.74 | 6.72 | 2.20 |
| Ag_V3 | 2024 | 249 | 3.78 | 6.87 | 2.33 |
| Ag_V3 | 2025 | 187 | 3.76 | 6.10 | 1.54 |
| Ag_V4 | 2020 | 158 | 2.34 | 6.33 | 1.45 |
| Ag_V4 | 2021 | 208 | 2.99 | 6.86 | 0.00 |
| Ag_V4 | 2022 | 249 | 2.79 | 3.14 | 0.00 |
| Ag_V4 | 2023 | 249 | 3.37 | 5.25 | 0.00 |
| Ag_V4 | 2024 | 250 | 3.30 | 5.52 | 0.05 |
| Ag_V4 | 2025 | 249 | 3.36 | 4.85 | 0.00 |
| Ag_V5 | 2020 | 200 | 3.62 | 7.43 | 3.15 |
| Ag_V5 | 2021 | 187 | 2.97 | 6.64 | 0.00 |
| Ag_V5 | 2022 | 249 | 2.79 | 3.36 | 0.00 |
| Ag_V5 | 2023 | 249 | 3.60 | 6.12 | 1.18 |
| Ag_V5 | 2024 | 249 | 3.52 | 6.29 | 1.33 |
| Ag_V5 | 2025 | 187 | 3.61 | 5.53 | 0.54 |
| Ag_V6 | 2020 | 200 | 2.87 | 6.61 | 1.79 |
| Ag_V6 | 2021 | 157 | 2.76 | 6.86 | 0.00 |
| Ag_V6 | 2022 | 48 | 3.73 | 5.89 | 0.94 |
| Ag_V6 | 2023 | 249 | 3.60 | 6.12 | 1.18 |
| Ag_V6 | 2024 | 249 | 3.52 | 6.29 | 1.33 |
| Ag_V6 | 2025 | 187 | 3.61 | 5.53 | 0.54 |
| C | 2020 | 200 | 4.83 | 8.94 | 5.64 |
| C | 2021 | 250 | 8.37 | 12.60 | 8.76 |
| C | 2022 | 249 | 4.93 | 9.27 | 5.81 |
| C | 2023 | 249 | 4.48 | 8.87 | 5.42 |
| C | 2024 | 250 | 4.59 | 9.03 | 5.54 |
| C | 2025 | 249 | 3.83 | 8.34 | 4.89 |
| CV3 | 2020 | 200 | 3.64 | 7.78 | 4.78 |
| CV3 | 2021 | 250 | 7.17 | 11.44 | 7.92 |
| CV3 | 2022 | 249 | 3.69 | 8.11 | 4.95 |
| CV3 | 2023 | 249 | 3.19 | 7.71 | 4.55 |
| CV3 | 2024 | 250 | 3.31 | 7.88 | 4.66 |
| CV3 | 2025 | 249 | 2.61 | 7.17 | 4.02 |

## Checks the run made

- Refits re-run and equal to the tracked calendar-clean record: C, CV3.
- Served-day counts equal to the tracked records': C, CV1, CV2, CV3, CV4, A_B, A_V1, A_V2, A_V3, A_V4, A_V5, A_V6.

## Not reported

- D: not reported (D dropped under #142).
- DV1: not reported (D dropped under #142).
- DV2: not reported (D dropped under #142).
- DV3: not reported (D dropped under #142).
- DV4: not reported (D dropped under #142).
