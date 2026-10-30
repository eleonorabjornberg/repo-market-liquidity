# Panel version 5: the Phase 3 panel at the pin of 2032de4

**Development data, not a verdict.** Nothing here is scored. This page records a panel, not a result. It applies the
directive of #200 (Eleonora's ruling of 29 October 2026, option (ii): move liquidity to the post-#1312 parent) and follows the
precedent of `docs/stages/panel-v4.md`: the Phase 3 panel rebuilt at the new parent pin is published as a new version with its own
manifest, and the earlier version stays as published.

## Why it is a new version

`PARENT_COMMIT` moves from 08ff67e to 2032de4, repo-market-model#1315's merge commit (the parent's decision instant moves from 16:00 to
18:00, #1312). The same build now gives sha256 `63fe5f7fd5ccae40e30aad729fab8f8f417a1323b717635a95aae727fb8143c1`, not version 4's
`6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`. The parent's published panel digest
(`4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999`) is the same at both pins: only `decision_time` in the parent's
`metadata/funding_panel_manifest.json` (16:00:00 to 18:00:00) and `metadata/sources.json` changed, and the funding panel's bytes did
not. `scripts/build_panel.py` reads that `decision_time`, so this panel's manifest records 18:00:00.

- **Version 4** (`metadata/phase3_panel_v4_manifest.json`) is not edited. It is a record at 08ff67e and 16:00:00, verified at the
  commit and parent pin it was made from (`scripts/verify_records.py`). `panel.build` refuses it at this pin, as it refuses versions 1
  to 3.
- **Version 5** (`metadata/phase3_panel_v5_manifest.json`) is version 4's build at 2032de4: the same columns, dates and coverage. Its
  manifest names version 1's and version 4's digests (`v1_sha256`, `v4_sha256`).
- Readers take the version from the record they name. `h10_apply.load_development` reads version 5 by default and takes a
  `version`. The published H10 records name versions 1 and 4 and are untouched.

## The changed rows

32 cells, all in `srf_take_up`, 2024-02-22 to 2026-08-27 (`results/panel/v5_changes.json` holds each date with its
version 4 and version 5 value, made by `scripts/panel_v5_changes.py` from version 4 built at 08ff67e and version 5 built at 2032de4): every
one becomes 0 (it was 0.097 to 0.113 USD billion), and no other column differs, which the script refuses to write otherwise. By year: 2024 13,
2025 11, 2026 8. The cause is the parent's afternoon test-trade rule (repo-market-model#938: an overnight operation with no note, released at
13:29 or 13:30, whose main line is 90 to 130 million dollars and whose other lines are each under 10 million, is a test trade), merged between the
two pins. **The decision instant's move to 18:00 changes no cell of this panel.**

The dates (day of month, by month):

```
2024-02: 22
2024-03: 07
2024-04: 18
2024-05: 16
2024-06: 05 13
2024-07: 09 11
2024-08: 08
2024-09: 10
2024-10: 03
2024-11: 06
2024-12: 10
2025-02: 11 12
2025-03: 11
2025-04: 08
2025-05: 06
2025-06: 10
2025-07: 08
2025-08: 12
2025-09: 09
2025-10: 03
2025-12: 09
2026-01: 13
2026-02: 10
2026-03: 10
2026-05: 12
2026-06: 09
2026-07: 14
2026-08: 11 27
```

## Does any H10 development figure change?

`srf_take_up` is not one of H10's drivers (`tests/test_panel.py`, `test_h10s_drivers_do_not_read_srf_take_up`). The re-run of H10's four
development records on version 5 at 18:00, and what it shows, is in `docs/research/h10-reregistration-2.md`.

## Other readers of the panel

Each reader of a version takes its own: `scripts/h7_kink_run.py` and `h10_apply` read `h10_apply.PANEL_VERSION` (now 5); the closed H7
records (`results/h7/`) name version 4 and the pin of 08ff67e and are checked against it by their tests; Stage 4's freeze names version
3. A figure computed from version 4 stays a figure of version 4.
