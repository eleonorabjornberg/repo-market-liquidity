# H10, second declaration, step 2: panel version 6 and the nine-driver development attribution

**Serves:** H10's second declaration (`docs/decisions/h10-method-2.md`), **step 2, development**. Directive #209. It runs
**beside** the registered H10 method, never in place of it. **Development evidence, never a verdict**
(`docs/decisions/measurement-protocol.md` section 1). Under the 2 November freeze nothing is adopted, and nothing is registered:
registering this declaration is her attested act, later and separately.

**State of this page.** The code, the panel and the commands are in this pull request. **The attribution itself is a long run for
Eleonora's Mac** (#46's standing order; 512 subsets on each of 10,000 draws for 31 episodes, and a 1,000-draw null, more than two
hours), and its results come back as a commit on the same branch. The result record is `results/h10/development_2.json` and the
result page is `docs/research/h10-method2-development-table.md`, rendered from it by `scripts/emit_h10_method2_table.py` and never
hand-edited. Until they exist, this page states no figure.

## What the step had to show, and whether it did

| Had to show | Shown? |
|---|---|
| Phase 3 panel version 6 is built, with its manifest and digest, and version 5 and the registered inputs are untouched | Yes: `docs/stages/panel-v6.md`; `tests/test_panel_v6.py` |
| The code path of the nine-driver attribution works on every development episode | Yes, at a smoke setting (a handful of draws), labelled so: `tests/test_h10_apply_2.py`, `SmokeRunTests`. It is not a result |
| The nine-driver attribution, its placebo (floored and unfloored), its null, and the residual share against the registered five | **Not yet**: the Mac run |
| `h10_live.method_digest()` unchanged | Yes: `54b5f151...8770`, `tests/test_h10_apply_2.py`, `RegisteredMethodUntouchedTests` |

## What the run does

- **Drivers:** the nine of `h10_drivers_2.DRIVERS_2` in one fit (the registered five, then `facility_material_use`, `sofr_volume`,
  `sofr_p99_p1_bp`, `pd_fails_deliver_ust`), each as the window change. **`pd_fails_deliver_ust` is a collateral driver**, shown so
  everywhere (row 8); every other driver is shown as cash-side or calendar.
- **Method:** the registered one, unchanged: 5 baseline days and 5 window days, leave-neighbourhood-out regression, Shapley shares
  over all 512 subsets, the stationary bootstrap (mean block 10, 10,000 draws, seed 20261013, 90% intervals), 20 placebo windows per
  episode (the registered record's own windows, read unfloored and floored at 2 bp), the selection null (1,000 draws, 95% quantile).
  The episode list is the parent's onset rule, cross-checked as in the registered run.
- **Report window:** 11 panel days (`REPORT_DAYS_2`, her ruling Q3), through `h10_drivers_2.attribute_2`, which also applies the
  30 June 2027 break. No development episode meets the break (development ends 2026-09-03), so the break's refusal applies to none.
  The 11-day window is a property of this declaration (record section 5); it is not tested on development data.
- **Pieces:** one file per episode and one for the null (`results/h10/method2/`), so an interrupted run is finished by running it
  again and a lost piece costs only itself. The record is assembled only when every piece is there, from one clean commit, with the
  registered digest unchanged.
- **The comparison:** the registered five drivers' development table is shown beside it unchanged (the registered record, byte for
  byte), and the residual share under nine drivers is set against five, paired by episode, with intervals and the regime and
  pressure-day-type splits. The five drivers are refitted on panel version 6 and must give the registered residual shares to 1e-9, or
  the assembly refuses (the comparison would not be like for like).
- **Not attributable:** each such episode is listed with its reason and the registered method's status for it.

## The commands

`scripts/h10_method2_step2.py` (`run`, `status`, `assemble`), then `scripts/emit_h10_method2_table.py`. The exact paste for her Mac is
on the pull request (`needs-mac:`).
