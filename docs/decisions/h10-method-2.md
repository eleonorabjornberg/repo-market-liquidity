# Decision: H10's second declaration, with SRF, volume, dispersion and fails as drivers (a development declaration)

**Status: DRAFT, dated 9 November 2026, for Eleonora to review. It is in force only once she merges it, and the
declaration needs her attestation (GO) before it is more than a development declaration. Step 1 of H10 with new
drivers (repo-market-liquidity#204; her option (b) of 9 November 2026, "do all four please", on #24). Development only:
nothing here is scored, registered or live.**

**Amended 10 November 2026** (repo-market-liquidity#208), for her rulings of that day on #206 ([her
comment](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/206#issuecomment-6780902686)): the facility event
counts the 2019 to 2021 term repo operations as well (section 1, section 4 item 2), and this declaration reports at 11 panel
days (section 4 item 3, section 5). The record's date stays 9 November 2026; the amendment is a new pull request, and the
history of #206 is not edited. **This amendment is for her to merge**: it changes a decision record. The registered method and
its digest are not touched.

This record declares a second H10 method *beside* the registered one. It is the decision record that
[`plan.md`](../research/plan.md) H10 asks for ("A changed method is a new declaration with a new date"). The date of the
declaration in force is the date she merges it.

## 0. The registered method stays untouched (her ruling, 9 November 2026)

Her ruling on #204: *run beside*; a separate development declaration; the registered H10 method stays untouched. The
registered method is `docs/decisions/h10-method.md`, `attribution.DRIVERS*`, `h10_apply.py`, `h10_live.py`,
`h10_registration.py` and the live record, registered by her on #23 on 3 November 2026 at digest
`54b5f151c757b1cff5d3ebe6e8ce202bd41cafc4d8104effb00f3da4617c8770`.

- **Nothing registered is edited.** The new set lives under new names: `src/repo_liquidity/h10_drivers_2.py`,
  `declarations/nyfed_pd_fails.json` and this record. `h10_live.method_digest()` at the head of the pull request equals the
  registered digest (`tests/test_h10_drivers_2.py`, `test_the_method_digest_is_still_the_registered_one`, which also checks
  that no new file is among `h10_live.METHOD_FILES`).
- **Any move to live is a new registration by her.** Under the 2 November freeze nothing is adopted.
- The episode list, the window (5 baseline days, 5 window days), the leave-episode-out regression with Shapley shares, the
  stationary bootstrap, the placebo, the 2 bp floor and the outcome rule are `h10-method.md`'s, unchanged. Only the driver
  set and what it needs are new.

## 1. The driver set

The registered five are kept, in their order (`attribution.DRIVERS_WITH_ON_RRP`: Treasury settlement, TGA, reserves,
quarter-end, ON RRP take-up), then four new drivers. Each enters like the registered ones, as the **window change**: the
mean of the column over the onset day and the four after it, minus its mean over the five panel days before the onset
(`attribution.change`), read at the value first published.

| Driver (`h10_drivers_2.NEW_DRIVERS`) | Exact form | Source and availability | Data meaning |
|---|---|---|---|
| `facility_material_use` (renamed from `srf_material_use`, which no longer says what it is: the event is no longer the standing facility alone) | `1(srf_take_up >= 1.0 or fed_repo_material_use)` on each panel day, `srf_take_up` in USD bn and `fed_repo_material_use` the 2019 to 2021 term repo event (`h10_drivers_2.facility_event`); its window change is the share of window days with an event less the share of baseline days. The amount is not an input, and it is **one driver**. | **(a) The standing facility:** the New York Fed's SRF operation results (`nyfed_srf.srf_total_accepted`), declared by the parent and switched on in Phase 3's declaration; available 16:00 the next business day; the Phase 3 panel carries the amount as `srf_take_up`. **(b) The 2019 to 2021 term repos:** `fed_repo_material_use` (see below), from the New York Fed's repo operation results, `nyfed_temp_repo`, declared in `metadata/sources_phase3.json` (`temp_repo_take_up`, `temp_repo_term_take_up`, USD bn per operation date, overnight and term alike); available 16:00 the next business day, as (a). | Row 13: material use of $1bn or more is an event the model should explain; the amount is not modelled. Row 14: a term repo operation counts on its operation date. **Her rulings: it enters as an event (9 November); the 2019 to 2021 term repo operations count as well (10 November, Q2).** |
| `sofr_volume` | the level, USD bn | The New York Fed's SOFR (`nyfed_sofr.SOFR_volume`), declared available 15:00 the next business day. In every Phase 3 panel. | Row 11: a **measurement break at 2027-06-30** (section 3). |
| `sofr_p99_p1_bp` | `100 x (SOFR_p99 - SOFR_p1)`, in bp (`indicators.SPREADS`) | `nyfed_sofr.SOFR_p99` and `SOFR_p1`, the same lag as the volume. In the version 3 panel only; **not in version 5**. | Row 7 puts it in the pricing family. Row 11: the same break. |
| `pd_fails_deliver_ust` | the weekly level of primary dealer fails to deliver US Treasuries, USD bn, cumulative over the week to the Wednesday, carried across the following rows | The New York Fed's Primary Dealer Statistics, `PDFTD-UST`, declared in `declarations/nyfed_pd_fails.json`: the Thursday of the following week, 16:30. Copied from the parent's `nyfed_pd_financing`; the parent does not read it in any published declaration. | Row 8: a good *collateral*-scarcity measure, kept on its own axis, apart from cash scarcity. **Her ruling of 9 November: it enters as a driver, labelled collateral.** |

- **`fed_repo_material_use`: source, availability and how it reaches the panel (Q2).** It is 1 on an operation date whose
  accepted amount, overnight and term alike, is $1bn or more (data-meaning row 14, and its note on how the parent builds the
  same event: 190 events from 2019-09-17 to 2021-07-28, 31 from 2021-07-29). Its source is the New York Fed's repo operation
  results, the same endpoint as `nyfed_srf`. **The declaration exists and states its lag**, so no new overlay is added:
  `nyfed_temp_repo` in `metadata/sources_phase3.json` declares a day's results available 16:00 on the next business day (not at
  the 13:45 close, because the Desk states no publication time and `lastUpdated` is a write time rewritten days later on
  2021-09-03 and 2021-09-10); the parent's `nyfed_repo_ops` declares the same lag for the same endpoint, and a test asserts the
  three lags are equal (`test_the_declared_lag_of_the_term_repo_source_is_the_standing_facilitys_and_the_parents_repo_ops`).
  The column is in the version 2 and version 3 manifests and **not in version 5**; the version 2 and 3 snapshots and the module
  that built it were deleted on 12 October 2026 (`deleted-duplicates.md`; those versions are records). **Panel version 6 must
  carry it**, with `facility_material_use` derived on each row from `srf_take_up` and `fed_repo_material_use`. Step 2 builds that
  column from the parent's `repo_model.fed_liquidity` (`fed_repo_accepted` over `nyfed_repo_ops`: the same events on every date
  through 2025-12-31, data-meaning row 14's note) or from a restored `nyfed_temp_repo` snapshot; that is a build choice, recorded
  with the panel, and each is declared 16:00 the next business day. The leakage and staleness tests of the lag are in
  `FacilityLagGuardTests` (`check_declared_facility_lag`; the mutated line and the exception are in each docstring). This
  amendment builds no panel.
- **Labelling.** Every table and page that shows these shares labels `pd_fails_deliver_ust` as a *collateral* driver and the
  other drivers as cash-side or calendar drivers (row 8). The share of fails is not read as cash scarcity.
- **Nine drivers** (Q4, as ruled: all nine in one fit; the facility event with the term repos is one driver, so the set stays nine). The Shapley shares refit every subset of drivers: 512 subsets, against 32 for the registered five, on
  each of 10,000 bootstrap draws. Step 2 is therefore expected to run longer than about two hours, and goes to her Mac
  (`needs-mac:`, #46's standing order), not the cloud. This is a fact about cost, not a choice made here.
- **Panel version 6 (named, not built).** The version 5 panel does not carry `sofr_p99_p1_bp` (it left after version 3), the
  derived `facility_material_use` (with `fed_repo_material_use`) or the fails. Step 2 builds **Phase 3 panel version 6**, as #149 named version 4: version 5's
  columns plus `sofr_p1` and `sofr_p99` (the indicator is computed on the row), the derived `fed_repo_material_use` and `facility_material_use`, and
  `pd_fails_deliver_ust` with a snapshot of the two fails series. Version 5, its manifest and the registered method's input
  are not touched. This step builds no panel.

## 2. The inputs and their guards

Each input is read through the parent's `repo_model.asof.InformationRule` (never re-implemented), under Phase 3's
declaration, and each has an availability declaration, a leakage test and a staleness test with a recorded mutation
(`tests/test_h10_drivers_2.py`; the mutated line and the exception type are in each docstring).

- **Fails** are the one new source: `declarations/nyfed_pd_fails.json`, id `nyfed_pd_fails`, fields `PDFTD-UST` and
  `PDFTR-UST` (the receive series is declared and mapped to `pd_fails_receive_ust` but is not a driver here), six business
  days, 16:30. Its lag equals the parent's `nyfed_pd_financing` (`test_the_lag_is_the_parents`) and is checked against the
  published schedule by `h10_drivers_2.check_declared_fails_lag`: a week declared public before its Thursday raises
  `LookAheadError`, one declared later raises `StaleReadError`. The declaration passes the parent's validators
  (`declaration.validate()`).
- **The standing facility's take-up, the 2019 to 2021 term repos, SOFR volume and SOFR percentiles** are declared (the first and third by the parent, the term repos in Phase 3's own `nyfed_temp_repo`) and already read by Phase 3. Their
  declared lags are asserted (`TheOtherInputsDeclarationsTests`), and the window of each is checked public at the report
  day by `attribution.check_window_public`, the registered method's own guard (`test_the_window_is_public_at_the_returned_day_and_not_before`).

## 3. The 30 June 2027 break (data-meaning row 11)

**Mandatory clearing of Treasury repo starts on 2027-06-30. Uncleared bilateral repo then enters SOFR, so SOFR's volume and
its percentiles change meaning** (`indicators.MEASUREMENT_BREAKS`). Two drivers are broken: `sofr_volume` and
`sofr_p99_p1_bp`. Her ruling of 9 November: **those series are not read across the break.**

- **Rule (enforced in code, `h10_drivers_2`).** `mask_across_break` makes the two series missing on and after 2027-06-30, so
  a fitting window that touches the break has no change and is dropped from the sample. `break_refusal` makes an onset whose
  window (its five baseline days and its five days) touches a day on or after 2027-06-30 **"not attributable", with the
  reason, never dropped**; the reason reads `BREAK_REASON`. It stays in the denominator of the outcome rule as a miss
  (`h10-method.md` section 6). `attribute_2` applies both before it calls `attribution.attribute`.
- **Until she declares a re-based series, the two series are not used after the break.** Every onset from the break's
  window on is therefore "not attributable" under this declaration, however well the other seven drivers would do. That is
  the cost of the rule, and it is stated here so that it is not found later.
- **Alternatives (listed, not chosen):** a break dummy that lets the two series stay in the regression with a level shift
  from 2027-06-30, or a separate scaling before and after (a re-based series). Both would be a new data-meaning decision.
- The other three new drivers and the registered five are not broken by it.

## 4. Her rulings of 9 and 10 November 2026

Her rulings of 9 November settled the SRF form (an event), fails (a driver, labelled collateral), run beside, and the break
(not read across). Her rulings of 10 November on the four questions this section first marked
([her comment on #206](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/206#issuecomment-6780902686), relayed
by the orchestrating session; amended here under #208):

1. **Q1, the fails series: fails to deliver only, as drafted.** `PDFTD-UST` is the driver. The receive series is declared and
   mapped (`pd_fails_receive_ust`) but is not a driver, and the sum is not used.
2. **Q2, which facility's material use: also count the 2019 to 2021 term repo operations (`fed_repo_material_use`), not only
   the standing facility.** The event is the standing facility's take-up at $1bn or more, or a term repo operation that is
   material on its own operation date (data-meaning row 14). It stays one driver (an event, the amount not an input), so the
   set stays nine. It is named `facility_material_use`, because `srf_material_use` would now name only half of it. Its source,
   availability and route to panel version 6 are in section 1.
3. **Q3, the report window: this declaration reports at 11 panel days.** The constant is `h10_drivers_2.REPORT_DAYS_2 = 11`,
   used in this declaration's window checks (`report_index_2`, `attribute_2`) and in section 5. The registered method's
   `REPORT_DAYS = 10` (`h10_apply.py`) is not touched, and neither is anything its digest covers.
4. **Q4, nine drivers in one fit: as drafted.** All nine in one fit, not one new driver at a time.

## 5. Availability and the report window (`REPORT_DAYS_2 = 11`)

`h10_drivers_2.report_days_summary` asks the parent's rule, at the report day's decision instant (18:00 of the panel day
before it), the registered method's own `check_window_public` test: the whole window, the five baseline days and the
five days from the onset, public. It reads each window day's value as declared available from that day's own row, the
conservative reading the registered method uses for TGA. It was run over every onset position of the development panel
(version 5 dates; no value is read and nothing is attributed).

| Input | Declared lag | Panel days after the onset until the whole window is public | Past `REPORT_DAYS_2` = 11? | Past the registered `REPORT_DAYS` = 10? |
|---|---|---|---|---|
| `facility_material_use` (the standing facility; and the term repos, `nyfed_temp_repo`, the same lag) | 1 business day, 16:00 | 6 panel days | no | no |
| `sofr_volume` | 1 business day, 15:00 | 6 panel days | no | no |
| `sofr_p99_p1_bp` | 1 business day, 15:00 | 6 panel days | no | no |
| **`pd_fails_deliver_ust`** | **6 business days, 16:30 (weekly)** | **11 panel days** | **no (exactly at it, at every onset)** | **yes, at every onset** |
| `tga` (registered, for comparison) | weekly | 7 to 10 panel days | no | no (the live run is at 9 of 10 for the 3 November onset) |

**Fails make every onset's whole window public 11 panel days after it, one more than the registered `REPORT_DAYS = 10`; her
ruling Q3 sets this declaration's report window at `REPORT_DAYS_2 = 11`, which holds at every onset.** The other three new
inputs (the facility event, with the 2019 to 2021 term repos, and the two SOFR series) are public within 6 panel days, the
spread's own lag. `REPORT_DAYS` is the registered method's constant and is not changed here. The figure for
`facility_material_use` is the term repos' too: `fed_repo_material_use` has the same declared lag as the standing facility, so
the union is public when the later of the two is, 6 panel days.

## 6. What this record does not do

- It attributes no episode, scores nothing and publishes no figure. Step 2 is written only after this step is reviewed
  (`CLAUDE.md`, "step by step").
- It changes no registered file and registers nothing; the registration of this declaration, if she chooses it, is her
  attested action.
- It builds no panel and fetches no data.
- It does not change `data-meaning.md` (rows 7, 8, 11, 13 and 14 are cited as they stand).
