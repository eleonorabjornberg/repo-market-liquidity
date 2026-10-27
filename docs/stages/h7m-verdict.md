# H7m stage verdict: not testable as stated

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, the verdict after development steps 2 to 5 (`docs/research/plan.md`). Directive #187. Development tier. It is hers to review and merge (a stage verdict).

**Verdict: not testable as stated.** No candidate is eligible after steps 2 to 5. This page states the rule's result and nothing more. Printed from `results/h7/verdict.json`; every figure below is a figure a tracked record carries.

## 1. The rule, quoted

`docs/research/plan.md:185-186`

> - **Not testable as stated:** no candidate meets the stability and sharpness goalposts in development, so nothing can
>   be registered.

`docs/research/plan.md:193-194`

> In development, "no eligible candidate after steps 2–5" ends H7m as not testable as stated. Effort then goes to H7f
> with R+S alone.

`docs/decisions/measurement-protocol.md:51`

> - **Eligibility in development.** Goalposts 1 and 2 hold on the development walk-forward, and the distribution account (§8) exists.

## 2. Her ruling

Eleonora, 2026-10-26, on #181: option (a), "yep", relayed by the model orchestrator. No candidate is eligible after steps 2 to 5, so H7m is not testable as stated, by the two plan lines above. Eligibility follows `docs/decisions/measurement-protocol.md:51` (section 7).

## 3. Each estimator's status

Read from `results/h7/step5-scores.json` (step 5, PR #181) and `results/h7/kink.json` (PR #168). Widths and gaps are in points of bank assets; the bar is on width and the limit is on the gap.

| Estimator | Status | Worst gap (limit) | Median width (bar) | Reason |
|---|---|---|---|---|
| B | ineligible: goalpost 1 does not hold | 6.25 (0.5) | 3.25 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V1 | ineligible: goalpost 1 does not hold | 3.50 (0.5) | 2.25 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V2 | ineligible: goalpost 1 does not hold | 3.00 (0.5) | 2.75 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V3 | ineligible: goalpost 1 does not hold | 8.75 (0.5) | 2.50 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V4 | ineligible: goalpost 1 does not hold | 3.50 (0.5) | 2.50 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V5 | ineligible: goalpost 1 does not hold | 5.50 (0.5) | 2.25 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| V6 | ineligible: goalpost 1 does not hold | 2.00 (0.5) | 2.75 (3.0) | goalpost 1 does not hold on the development walk-forward: the restated record's worst real-time gap is at or above the limit |
| C | ineligible: goalpost 2 does not hold | unreadable on development data | 3.46 (3.0) | goalpost 2 does not hold: the median width of the daily 90% interval is not under the bar |
| CV1 | not scorable | - | - | the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted |
| CV2 | not scorable | - | - | the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted |
| CV3 | ineligible: goalpost 1 is unreadable on development data | unreadable on development data | 2.54 (3.0) | goalpost 2 holds; goalpost 1 is unreadable on development data (her option 6 of 22 October), so it cannot be shown to hold and the candidate is not eligible |
| CV4 | not scorable | - | - | the refit in force did not fit on any window day: 69 of 70 refits were not fitted (calendar-clean record, refit status: 1 fitted, 69 not identified); it serves no day and is not re-fitted |

Family A is B and V1 to V6; family C is C and CV1 to CV4. Goalpost 1 for C and its variants is unreadable on development data under her option 6 of 22 October, which is neither a pass nor a fail; for CV3, whose width is under the bar, that leaves it not eligible.

## 4. Beside the rule, not as the reason

Step 5's goalpost 3, pooled, in AUROC points against the MME of 0.05. Reported as development evidence; not the reason for the verdict.

| Estimator | Gain against R+S | Position | Gain against S alone |
|---|---|---|---|
| B | -0.096 | straddles the MME | -0.482 |
| V1 | -0.090 | straddles the MME | -0.485 |
| V2 | -0.174 | straddles the MME | -0.461 |
| V3 | +0.004 | straddles the MME | -0.412 |
| V4 | -0.187 | below the MME | -0.463 |
| V5 | +0.195 | straddles the MME | -0.444 |
| V6 | +0.160 | straddles the MME | -0.338 |
| C | +0.072 | straddles the MME | -0.245 |
| CV3 | +0.104 | straddles the MME | -0.243 |

No interval against R+S lies at or above the MME, and every gain against S alone is negative.

## 5. The plan's consequence

`docs/research/plan.md:193-194`: "Effort then goes to H7f with R+S alone." H7f is the model repository's. This is stated as the plan's consequence, not an action here.

## 6. What this does not say

The record states the rule's result and nothing more. It makes no claim about whether scarcity can be measured, and says nothing about the outcome of H7f.

## 7. Records read

- `results/h7/step5-scores.json` (`1364be1485f9fcdf186e8ef5e191ac565dfaed2305f9ff55120da23fff0be0c1`)
- `results/h7/kink.json` (`c37bf6b6f16a620b5708bf2eb6746be444454049477d981567e9db7f08de1fce`)
- `results/h7/calendar-clean.json` (`c3acfc90f9e4fd60c548768a17f7a2b0b86315bdf95118de7e4c56303e04608c`)
- `results/h7/distribution-account.json` (`f32e4c8433525071e150b2d43f030e43b22aa3961a9ecd6c6b118b5032bbf922`)

Regenerate with `python3 -B scripts/h7_verdict.py` (`--check` exits 1 if the record or this page is stale). Neither is edited by hand. The record is listed in `repo_liquidity.records.OWN_CHECK` with `tests/test_h7_verdict.py`.
