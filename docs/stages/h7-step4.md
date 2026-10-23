# H7m, development step 4: the account of the bank distribution for A and C

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development step 4 of the plan
(`docs/research/plan.md`). Directive #144. It follows step 3 (`docs/stages/h7-step3.md`, PR #143), the calendar-clean declaration
(`docs/stages/h7-calendar-clean.md`, PR #146) and the two calendar-clean runs (#147, PR #150, the variants of C; #151, PR #154, the
variants of A). It produces the account `docs/decisions/measurement-protocol.md` section 8 requires for eligibility
(`docs/stages/stage-6.md:90-94`, rule 3), which has been pending for A since Stage 6 (`stage-6.md:146-147`).

**It decides nothing.** The account's size decides nothing (protocol section 8). There is no goalpost, AUROC, stability or width
verdict here, no comparison between candidates, and no score against the stress events; those are step 5. **Development, never a
verdict** (protocol section 1): no locked day is read, and nothing here is a prospective result. This document is written before
the code (`src/repo_liquidity/h7_account.py`) and the code is held to it.

## 1. What is reported

On every development day a refit serves, as of that day's decision instant, for each estimator in play, **aggregate deployable
liquidity under the three declared alternatives** for how the same reserves spread over the three H.8 groups (protocol section 8):

| Alternative | The reserves of the three groups are |
|---|---|
| `as_observed` | the week's group reserves (data-meaning row 18's approximation) |
| `all_large_domestic` | all held by the large domestic group; the other two hold none |
| `proportional_to_assets` | spread in proportion to the groups' total assets |

Each alternative keeps the week's **total** reserves of the three groups. The machinery is step 2's, unchanged
(`h7_candidate_c.distribution`: each group's reserves above its own buffer, never negative, over the groups' total assets). The
unit is points of bank assets (`100 x` a share), as in steps 1 to 3.

For each estimator and alternative the record carries, per served day, the aggregate with its 90% interval where the estimator has
one, and for the estimators that model groups the group-by-group terms; and over the served days the median, the range, the median
interval width, the days on which the aggregate is zero, and the same by calendar year. Over the alternatives it carries the median
difference from `as_observed`.

**The estimators.** The list is fixed here, before any figure, and is every fit the two calendar-clean runs produced; nothing is
chosen after seeing a result.

- **C, the current estimator** (`h7_candidate_c`, trained on every day of its counted episodes, so on calendar days; marked
  provisional by "Calendar first") and **CV1 to CV4**, the calendar-clean variants of #147. A variant that is not identified at a refit
  serves no day (`h7-calendar-clean.md` section 5); one that serves no day has an empty account, said so, not left out. The shares
  and the bootstrap draws are the refits' own: the two distinct fits of each estimator are re-run with the run's settings (2000
  draws, seed 115, 70 refits) and **compared with the tracked record** (`results/h7/calendar-clean.json`, each refit's parameters
  and training days); a refit that differs raises `ValueError`.
- **A, the curve's bend**, as step 1 and the kink run built it: the baseline `B` (the parent's satiation fit on every day, also
  provisional) and the six declared variants `V1` to `V6` of `h7-kink.md`. Their kinks, intervals and fitted flags are read from
  `results/h7/kink.json`, not re-fitted.
- **D** is not reported: it was dropped under #142 (`docs/stages/h7-step3.md`, #148, PR #153), no first-print headroom history exists, and
  the calendar-clean run did not run it. The record lists D and its variants as "not reported (D dropped under #142)". The directive's
  list of D's unserved days is therefore empty by construction, and #142's questions stay hers.

## 2. Candidate A has no groups: the two readings

A's aggregate on day T is `R_T - k`, the all-banks reserves ratio at T's decision instant minus the kink in force. It models no
group and has no per-group term, so **no redistribution of the same reserves over the groups changes it**: all three alternatives
give the same number. The record reports that as A's account ("A as defined") and says why, with a constructed test.

The directive also says to give the aggregate for A "by the same machinery". That is a reading, marked for Eleonora: **A through
step 2's group machinery, with A's single kink read as every group's buffer share** (`shares = (k, k, k)`, each group's reserves
above `k` of its own assets, never negative, over the groups' total assets). There the alternatives differ, because the per-group
clip at zero is where the distribution matters. It needs a group week at the day (the day is not in this view without one), and
its interval is the interval of the kink mapped through the same function: the aggregate does not increase with `k`, so the
endpoints are the aggregate at the kink's upper and lower ends (tested). It is reported beside "A as defined", never in its place,
and it is not A's estimand. If she does not want the second reading it can be dropped without touching the first.

## 3. The serving schedule and the guards

Each refit serves from the second business day after its cutoff to the day before the next refit serves from, as in every
earlier step (`SERVING_LAG`); a refit that did not fit, a day with no group week (for the group views), or a day with no ratio is not
served and is counted. The final C refit (2025-12-31, #160) serves no day of the window. The window is the runs' own, to
2025-12-31: the fits exist only for that window and no 2026 day is served by any of them. (The directive says development days
"through 2026-09-03"; that is the outer limit of the development tier and not a day any record refit serves.)

Two guards, both raising `LookAheadError`:

- a served day is at least `SERVING_LAG` business days after its refit's cutoff (`check_served_after_cutoff`);
- no group week a served day reads was public only after its decision instant (`check_weeks_public`).

Every input is read through `repo_model.asof` and `h7_candidate_c.sample_c`, which also refuse a stale week
(`h7_candidate_c.check_reads`, `StaleReadError`) and a locked day (`lockbox.require_unlocked`); the account adds the two checks above on
top and rewrites neither.

## 4. What it does not do

- It fits nothing new and chooses nothing: the shares and kinks are the earlier runs' (C's re-run is a check of the record, not a new
  result).
- It does not read goalposts 1 to 3, AUROC, stability or width verdicts, and compares no estimator with another.
- It does not decide which estimator is eligible or best (step 5), nor the questions of finding #142 or the exit criterion's weight (plan, Q2).
- The group reserves are an approximation (data-meaning row 18) and break weeks of the H.8 groups are flagged, never adjusted: the
  number of served days that read a break week is in the record.

## 5. The record

`scripts/h7_account.py` writes `results/h7/distribution-account.json` and prints `docs/research/h7-distribution-account.md` from
it; `--render` prints the page again from the record and `--render --check` exits 1 if the tracked page is stale. Neither is ever
edited by hand. The record is listed in `repo_liquidity.records.OWN_CHECK` with `tests/test_h7_account_record.py`.

Command (from a tree with the parent at the pin `08ff67e`, about twenty minutes on four cores; the whole of it is under the two-hour line, so it ran in the cloud):

    PYTHONPATH=src:<parent at 08ff67e>/src python3 -B scripts/h7_account.py
