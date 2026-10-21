# Panel version 4: the Phase 3 panel at the pin of 08ff67e

**Development data, not a verdict.** Nothing here is scored. This page records a panel, not a result. It applies
Eleonora's ruling of 21 October 2026 on #149 (question 1, option (a)): the Phase 3 panel rebuilt at the new parent pin is
published as a new version with its own manifest, and version 1 stays as published.

## Why it is a new version

Moving `PARENT_COMMIT` from 8fd2cf8 to 08ff67e brings the parent's Desk test-trade rule (repo-market-model#933). It
changes the `srf_take_up` column and no other. The same build now gives sha256 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`, not version 1's
`acb77874e0ca2c9eeee1c33a229f5e12745e65bb1224088d52c391dbf54be2ab`. The parent's published panel digest (`4ddc3882...8999`) is the same at both pins, because the
funding panel does not carry the column.

- **Version 1** (`metadata/phase3_panel_manifest.json`) is not edited. It is a record, verified at the commit and parent pin
  it was made from (`scripts/verify_records.py`). `panel.build` refuses it at this pin.
- **Version 4** (`metadata/phase3_panel_v4_manifest.json`) is version 1's build at 08ff67e: the same columns, dates and
  coverage. Its manifest names version 1's digest (`v1_sha256`). The numbers 2 and 3 were taken (the Stage 1a correction
  and Stage 1b), so the next free number is 4. The ruling said "version 2".
- Readers take the version from the record they name. `h10_apply.load_development` reads version 4 by default and takes a
  `version`. The published H10 records name version 1 and are untouched; their tests check them against version 1's manifest.

## The changed rows

391 rows of `srf_take_up`, 2021-09-23 to 2026-09-01 (`results/panel/v4_changes.json` holds each date with its
version 1 and version 4 value): 374 become 0, and 17 lose a test-trade amount and stay positive. The
largest change is 0.076 (USD billion). Every change is a decrease, and no other column differs. By
year: 2021 10, 2022 37, 2023 72, 2024 104, 2025 87, 2026 81.

The dates (day of month, by month):

```
2021-09: 23 30
2021-10: 04 05 14 25
2021-12: 08 10 28 30
2022-01: 03 04 11
2022-03: 03 30
2022-04: 06 07 28
2022-05: 04 19 31
2022-06: 23 29
2022-07: 07 12 13 27 28
2022-08: 01 04 15 16
2022-09: 01 07
2022-10: 03 20 21 25 26
2022-11: 03 08 09
2022-12: 05 06 14 15 16
2023-01: 04 06 17 18 19 20 24 31
2023-02: 02 07 08 21 23 27
2023-03: 03 06 09 20 21 22 23 28
2023-04: 03 10
2023-05: 02 05 08 15 16 17 23
2023-06: 08 21 27
2023-07: 11 12 20 24 27
2023-08: 01 02 03 10 11 15 16 17 29
2023-09: 06 11 21 27 28
2023-10: 03 12 20 23 25 26 27
2023-11: 06 07 28 29
2023-12: 01 06 12 13 14 18 21 22
2024-01: 12 18 22 23 25 29
2024-02: 05 08 09 12 21 23 27 28 29
2024-03: 01 05 06 12 13 14 15 19 20 26 28
2024-04: 03 09 10 15 16 17 19 24 25 30
2024-05: 02 13 20 21 29
2024-06: 04 06 07 10 11 20 21 26 28
2024-07: 15 18 23 25 31
2024-08: 01 06 07 13 20 27
2024-09: 03 09 11 12 13 17 19 24 25 26
2024-10: 02 09 15 16 22 24 25 29
2024-11: 01 04 05 12 13 14 18 19 20 21 26 29
2024-12: 02 03 04 05 06 11 12 13 16 17 19 24 26
2025-01: 02 07 14 16 17 29
2025-02: 06 25 26
2025-03: 10 12 13 19 27 28 31
2025-04: 03 10 11 16 21 22 24
2025-05: 07 08 13 14 15 19 21 22 28 29
2025-06: 02 03 05 09 12 16 26
2025-07: 07 15 22 23 28 29
2025-08: 04 05 06 11 13 14 20 21 25 26 27
2025-09: 03 08 10 16 17 24 25
2025-10: 02 07 08 09 20 22
2025-11: 05 06 10 14 19 20 24
2025-12: 03 04 05 09 10 11 12 17 23 24
2026-01: 12 21 26 27 28
2026-02: 03 04 05 06 09 18 23 25
2026-03: 03 04 05 06 11 12 18 24 25 26 30 31
2026-04: 08 14 15 16 21 22 27 28 29
2026-05: 01 05 07 13 18 19 20 21 26 27 28 29
2026-06: 02 03 04 05 09 10 11 15 16 17 18 24 25
2026-07: 01 06 07 14 15 23 24 28 29 30
2026-08: 04 05 13 17 18 19 25 26 27 28 31
2026-09: 01
```

## Does any H10 development figure change?

No. H10's drivers are `treasury_settlement`, `tga`, `reserve_balances`, `quarter_end` and `on_rrp`
(`attribution.DRIVERS_WITH_ON_RRP`) against `spread_bps`; `srf_take_up` is not among them
(`tests/test_panel.py`, `test_h10s_drivers_do_not_read_srf_take_up`). The published development record's deterministic
parts, the placebo-floor record and the point shares are recomputed from version 4 rows and agree with the published
records (`tests/test_h10_step2.py`, `test_h10_placebo_floor.py`, `test_h10_step3.py`, `test_h10_regimes.py`). #152 must check
this again, and say it, before she registers.

## Stage 4

Stage 4 read version 3 (a record). Its fitter moves to direct pairs in the same pull request, so its published figures
are provisional until re-run (`docs/stages/stage-4.md`). The re-run is a later line on #24.
