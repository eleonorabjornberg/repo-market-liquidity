# Stage 5a directive: Phase 3's own daily log

**Written 7 October 2026, after Stage 4 (#15) was merged and before anything in Stage 5a is built.** Nothing below is
built until Eleonora has merged this directive and the Stage 4 freeze that comes with it
(`docs/decisions/stage-4-freeze.md`).

## What decided this

- **`docs/decisions/evaluation.md`, with its amendment of 7 October 2026.**
  - Only days Phase 3 logs before their outcome, from the frozen declaration, are confirmatory evidence.
  - The log records both arms each business day: the published gbm without the curve-implied spread and with it.
  - The scoring dates are 2027-04-01, then each 1 October.
- **Stage 4's result (#15): not shown in development.** Under Eleonora's ruling of 7 October 2026, the freeze and this
  log go ahead whatever the development verdict.
- **Her rulings of 7 October 2026 on this stage, each the recommended option:**
  1. **The rate tables.** IORB moves to this repository's own table, seeded from the parent's and tested equal to it
     through the pin (done in this pull request, before the freeze). After each FOMC, both rate tables are extended by
     a reviewed pull request. The log refuses a day the tables do not yet cover (below).
  2. **The log's home.** One JSON file per decision day on an append-only `live-log` branch of this repository, written
     by a GitHub Actions workflow. Eleonora adds the ruleset that blocks deletion and force-pushes.
  3. **The start.** The workflow is merged with its schedule off. It is run by hand in dry-run mode for about five
     decision days, and Eleonora checks the outputs. Then a one-line pull request turns the schedule on. The first
     day that counts is the first decision day after that merge.

## What Stage 5a must show

Fixed before anything is built. The pull request that builds it says plainly which of these held.

1. **The log forecasts with the frozen declaration, and nothing else.** Before each run, the declaration's checksum
   equals the one pinned in `docs/decisions/stage-4-freeze.md`, and the run refuses otherwise.
2. **A replayed day reproduces the development run.** Run as of a past day on the tracked fixtures, the log's
   forecasts for both arms equal the Stage 4 records for that day:
   - each arm's CRPS, computed from the logged quantiles and the realized spread, matches
     `results/stage4/comparison.json`'s per-origin losses to 1e-9 bp;
   - each arm's P(spread > +5 bp) matches the probabilities `results/stage4/brier.json` was scored on.

   This is checked on the first scored day of every refit block in 2025.
3. **No look-ahead, by test.** Each new guard raises `LookAheadError` or `ValueError` and has one recorded mutation that
   kills it:
   - nothing but a scheduled or calendar column is read off a row after the last real one (the parent's
     `require_reads_on_real_rows`);
   - **the FOMC guard:** a day whose decision instant falls after a scheduled FOMC statement that either rate table
     does not yet cover is refused;
   - a day is written once, never backfilled, and never written for a day on or before 2025-12-31;
   - H.8 bank assets are read as first prints, dated as `frb_h8` declares them.
4. **Five dry-run days** on the live data, each producing a valid record that Eleonora has checked, before the schedule
   is turned on.

## The design

**One run, for one decision day T,** mirroring the parent's `scripts/live_record.py`:

1. **Refuse first.** T must not already have a record. T must be a decision day (the parent's `is_decision_day` and
   holiday table). The FOMC guard must pass. The declaration's checksum must equal the pinned one.
2. **Fetch.** The parent's own fetchers, through its command line, as its live record does: SOFR (NY Fed), FRED macro,
   Treasury bill rates and Treasury auctions. Plus what the parent's live record does not fetch: the H.8 release,
   for bank assets as first prints, through the parent's declared `frb_h8` source and its fetcher.
3. **Build.** The Phase 3 panel, version 3, from the fetched snapshots, with `iorb_in_force` and `on_rrp_rate` read
   from the two tables. Then the parent's `extend_panel` adds placeholder rows for T, and `require_reads_on_real_rows`
   checks them.
4. **Forecast both arms.**
   - The CRPS arms use the parent's `distribution_run`: `paired_model_comparison`'s fold loop walked through T. It
     scores nothing, so it neither consults nor spends the lockbox, as the parent's live record explains. Model A uses
     the published fitter and its nested PID. Model B uses the same with `curve_feature.CurveFeatureFitter`.
   - The probability arms use the parent's `forecast_run` with the two exceedance predictors, plus the two
     benchmarks.
   - The refit grid, the curve's carry rule and the online calibration's state are therefore exactly the frozen
     declaration's, through T.
5. **Write** `live/YYYY-MM-DD.json` with exclusive create, then commit it to `live-log` and push. Nothing is ever
   rewritten.

**The record** follows the parent's `RECORD_KEYS` where the fields mean the same:
- `decision_day`, `decision_instant`;
- `code` (this repository's SHA, the parent pin, the declaration checksum);
- `packages`;
- `inputs` (snapshots with their digests, the panel digest, both rate tables' digests and last effective dates);
- `targets`;
- `distributions`: `model_a` and `model_b` quantile vectors, and persistence's;
- `probabilities`: both arms at +5 and +10 bp, and the two benchmarks;
- `curve`: the curve model B used, with its cutoff, or where it was carried from;
- `run`.

**The FOMC guard** reads a declared calendar of scheduled FOMC statements (`metadata/fomc_calendar.json`). It is built
from the Board's FOMC calendar page, with the source page saved as a fixture. A day T is refused when a statement on
or before T's decision instant is later than the last announcement in either rate table. A statement that changes
no rate still needs its row, marked unchanged, so the guard stays a plain date test. Unscheduled actions (such as
15 March 2020) are not in any calendar. If one happens, the log refuses only once the table update is late, and
Eleonora is told through the failures issue.

**The workflow** (`.github/workflows/live-log.yml`) is the parent's, adapted:
- weekdays at 21:30 UTC, plus manual runs; `contents: write` and `issues: write`, with `github.token` only;
- Python 3.11, this repository at `main`, and the parent at the pin, installed editable with the exact pins;
- failures and missed days reported on a "Phase 3 log: failed runs" issue, never backfilled.

It is merged with the schedule commented out (her ruling on the start).

## After each FOMC

A small pull request adds the meeting's rows to `iorb_rate.csv` and `on_rrp_rate.csv`, with the saved implementation
note, and updates their manifests. `tests/test_scheduled.py` and `tests/test_curve_feature.py` check each new rate
against its page. The freeze is unaffected: it fixes the tables' rows at the freeze and allows rows to be appended
(`scripts/stage4_freeze.py`). Days the log refused while the update was pending stay unlogged.

## Not in Stage 5a

- No scoring. The first score is on 2027-04-01, under `evaluation.md`.
- No change to the frozen declaration, the parent, or the parent's live record.
- No publishing.
- No backfilling.
- No use of 2026 as evidence. Days before the schedule is turned on are not confirmatory.

## Built (7 October 2026)

Built under this directive after Eleonora merged it (#16). The schedule is off; nothing has been logged.

**Must-show 1, the frozen declaration alone: built.** Each run recomputes the declaration's checksum
(`scripts/stage4_freeze.py`) and refuses unless it is the one pinned in `docs/decisions/stage-4-freeze.md`. A test
changes a setting and sees the run refused.

**Must-show 2, a replayed day reproduces the development run: held.** `scripts/stage5a_replay.py` writes
`results/stage5a/replay.json`. It runs the log's forecast core on the development panel cut at the first scored day of
each of the twelve 2025 refit blocks. Both arms' CRPS equal the Stage 4 per-origin losses, and both arms' P(> +5 bp)
and P(> +10 bp) equal the development run's, with every gap 0. The development probabilities were recomputed by
`scripts/stage4_brier.py`'s code, and reproduce its Brier record exactly. Separately, the live build path, run on the
tracked fixtures, reproduces the development panel on every column the declaration reads, on every date
(`tests/test_live.py`).

**Must-show 3, no look-ahead, by test: held.** Each guard has a recorded mutation that was run and killed:
- the placeholder guard: the parent's, with the two scheduled rates allowed on a placeholder;
- the FOMC guard;
- write-once, and no development day;
- the H.8 seam: the live first-print extract continues the tracked one week for week. Within each extract, the parent's
  `extract_h8_first_prints.py` refuses a missing week or one printed later than `frb_h8` declares.

**Must-show 4, five dry-run days checked by Eleonora: not yet.** Two dry runs were made in the build session:
- one on the tracked fixtures, for 2026-09-04;
- one fetching live, for 2026-10-07: every source fetched, H.8 included, with real rows through 6 October and a forecast for 8 October, in about 17 minutes.

The five that count are made by the workflow, by hand, and posted on the "Phase 3 log: dry runs" issue for her.

**What was built:**
- `metadata/fomc_calendar.json`, with the saved calendar page;
- `src/repo_liquidity/live.py`: the guards, the live build and the forecast core;
- `scripts/stage5a_log.py`: the runner;
- `scripts/stage5a_replay.py`;
- `.github/workflows/live-log.yml`, with the schedule commented out.

**Costs.** A run takes about 15 minutes on one thread: the walk-forward through the day for six arms. A run with
fetching adds a few minutes. Both fit within the workflow's 150-minute limit.

**Known before the first counted day:**
- The next scheduled FOMC statement is on 28 October 2026. From 29 October, the log refuses each day until the rate
  tables carry that meeting's implementation note.
- A dry run of a past day reads today's vintage of every source. It is a check of the machinery, never evidence.
