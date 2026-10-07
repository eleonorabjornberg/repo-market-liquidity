# Decision: the Stage 4 freeze

**Status: a draft for Eleonora's review. It is in force once she merges it.** From then, Stage 4's declaration does not
change, and Phase 3's daily log (Stage 5a) forecasts with it alone.

Ruling (Eleonora, 7 October 2026): "freeze it and start Stage 5a", after reviewing Stage 4's result (#15, not shown in
development). Under her ruling of 7 October 2026 on the plan, the freeze goes ahead whatever the development verdict
(`docs/stages/stage-4.md`, "After the run").

## What is frozen

`scripts/stage4_freeze.py` writes the declaration (`--json`) and its checksum. The declaration covers:

- **both arms:** the published gbm with nested conformal PID, as the parent's own `compare` and
  `exceedance-backtest` code build it, and the same with the curve-implied spread;
- **the curve:** Stage 2's broken stick on SOFR's corridor position, slope held at or above 0, refit as of each refit,
  with a failed curve carrying the latest fitted one (the curve-pass amendment);
- **the declared features**, the fold settings (minimum history 61, refit every 21, decision 16:00, h = 1) and panel
  version 3 with its digest;
- **the parent pin** and its panel digest, the package pins, and the Stage 4 overlay (`metadata/sources_stage4.json`);
- **the source of every definition a forecast reaches,** hashed definition by definition, as the parent hashes its
  final test's (`scripts/final_test_preregistration.py`);
- **the rows the two rate tables had at the freeze:** 31 rows of `iorb_rate.csv`, through the note of 16 September
  2026, and 32 rows of `on_rrp_rate.csv`. Rows appended after each FOMC are allowed (Eleonora, 7 October 2026). A
  change to a frozen row is not.

- **Declaration checksum:** `9706d3976558da4380426b703554506fe1044a66df1e5b68b201f051e077528a`

`tests/test_stage4_freeze.py` refuses a tree whose declaration no longer has this checksum. It also checks that an
edited definition, an edited frozen rate row or a changed setting each move the checksum, and that an appended rate row
does not.

## Before the freeze (7 October 2026)

- **IORB moved to this repository's own table** (`tests/fixtures/snapshots/fomc_notes/iorb_rate.csv`), seeded from
  the parent's at the pin and tested equal to it row for row. This was Eleonora's ruling, so that the log is not tied to
  the pin. `docs/stages/stage-4.md` still names the parent's table; it describes the development run, which read the
  same values.
- **The three Stage 4 records were re-scored on that code** (commit `f15b655`). They are identical to the merged ones
  apart from their provenance. The frozen code is the code that produced them.

## What it means

- **Confirmatory evidence starts with the log**, from the first decision day after Eleonora turns its schedule on
  (`docs/stages/stage-5a.md`). Days before that are not evidence.
- **A change to anything frozen is a new declaration,** with its own pre-registered comparison and its own log, never
  an edit to this one.
