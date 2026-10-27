# H7m: the account of the bank distribution for A and C (development)

Generated from `results/h7/distribution-account.json` by `scripts/h7_account.py --render`; never edited by hand.
Tier: **development**. Development evidence, not a verdict. The account's size decides nothing (docs/decisions/measurement-protocol.md section 8). Stage document: `docs/stages/h7-step4.md`.

Panel version 4 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`; parent `08ff67e27bc3d7e357491cf8e1da59793702b3fb`; days served 2020-03-17 to 2025-12-31 (window ends 2025-12-31); 2000 bootstrap draws for C's intervals. Unit: points of bank assets. Sources: `results/h7/calendar-clean.json` (`c3acfc90f9e4`), `results/h7/kink.json` (`c37bf6b6f16a`).

The three alternatives for how the same reserves spread over the three H.8 groups: `as_observed`, `all_large_domestic`, `proportional_to_assets` (protocol section 8). Each keeps the week's total reserves.

**A as defined.** A as defined is R - k. It has no per-group term, so no redistribution of the same reserves over the groups changes it: all three alternatives give the same figure.

**withdrawn: base mismatch (#182).** The reading "A through the group machinery" is no longer reported: A's kink k was fitted on the parent's all-banks reserves ratio R, but this reading subtracts it from the three groups' reserves over the groups' assets, a base about one point of bank assets lower: day by day, the proportional reading minus max(A, 0) has a median of -0.98 points, so most of its days at zero came from the base mismatch and not from the distribution (finding #182). Withdrawn under Eleonora's ruling of 26 October 2026, option (a); nothing is re-fitted, and A as defined, C and every other row and field are unchanged.

This record replaces the one with sha256 `5b8ee596d16ccf6277f7174e109746c342bbfad270d10cfd9071fa9a8ebd20e8`: the rows of "A through the group machinery" are withdrawn for the base mismatch (#182): they subtracted A's kink, fitted on the all-banks ratio R, from group reserves over group assets. Every other row and field is copied as it was, nothing is re-fitted (Eleonora's ruling on repo-market-liquidity#182, 26 October 2026, directive #186). The superseded record is kept as it was in archive/h7-distribution-account-5b8ee596/.

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
