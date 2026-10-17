# H7m G6: the first power study, archived

**Archived, not edited.** These are PR #76's record and write-up, byte for byte, moved here from `docs/research/` by
directive #106. The second record, `docs/research/h7m-power-study-2.{json,md}`, supersedes them.

| File | SHA-256 |
|---|---|
| `h7m-power-study.json` | `5a44c9a00955ea8c90b5ee5f2ce772bd143cc9aa9b5abf3f256bc143dfe3a0b9` |
| `h7m-power-study.md` | `0e0c1cc68e6f0423ba497fd0be5ed7da9a42b3aa09af282a909ff20ad06f2597` |

## Why it is archived (finding #95)

- The event floor counted the events in usable strata (`test.events`), not the events in the window that protocol §9 and
  `docs/stages/h7-g6.md` §4 name. The 60-day window from 2019-09-17 has 60 events and 0 usable ones. The table's
  "windows at the floor" counted one thing and the shares beneath it another.
- The reading "among windows at the floor" had no interval and no size, and "size is small (1%)" in headline 5 belonged
  to the pooled reading only (the other reading's size was 8%).
- The bootstrap seed was `SEED + start*10 + look`, not the declared `20261014 +` the window's first index.
- The realised gains at 0.02 and 0.065 missed the declared 1e-4 calibration tolerance.
- The labels ended on 2025-12-31; the pin at `8fd2cf8` brings them to 2026-09-03.

The first record was made at the parent pin `53e61af9b4175e854c196908d3c76b228c039667` and panel digest `acb77874…`
(panel version 1). Its figures stand as what that run computed. Nothing in it is used for a decision.
