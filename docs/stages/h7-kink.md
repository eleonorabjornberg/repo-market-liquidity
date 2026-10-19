# H7m, a declared variant of the kink: calendar-clean pairs, a least-absolute-deviation hinge, one intercept per width regime

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, development, the kink the estimator subtracts in
step 1 (`docs/stages/h7-step1.md`, section 1) and that candidate C leaves aside (`docs/stages/h7-step2.md`). Directive #133.
It applies Eleonora's ruling of 19 October 2026 on Lens B of eleonorabjornberg/repo-market-model#958 ("We need both"): the
re-specified kink is a **variant**, declared next to the current estimator, not a replacement for it.

**This is a declaration. Nothing is computed, scored or run here, and no figure appears.** No code is written for it. The run
that follows is a separate directive, written after this document has been reviewed (`CLAUDE.md`, step by step), and it
implements what is below with no further choice. Development, never a verdict (`docs/decisions/measurement-protocol.md` §1).

## 1. Why

Step 1's kink is the parent's `repo_model.satiation.fit_level` at the pin (8fd2cf8, `src/repo_model/satiation.py`, function
`fit_level`): `spread = a + b × max(0, k − ratio)`, `b ≥ 0`, `k` on `KINK_GRID` (0.080 to 0.200 in steps of 0.0025), least
squares in levels of raw SOFR − IORB (basis points), on every training pair, with one intercept. Three things in that
specification are open to a data-driven objection, and each is one change below:

- **A few days set the kink.** Squared error weights 2019-09-17 (+315 bp) and the quarter-ends far above an ordinary day, so
  the hinge may be fitted to the calendar spikes rather than to the demand curve's bend.
- **One intercept absorbs a vertical shift.** Stage 2 found an upward shift of the bend between its two episodes
  (`docs/decisions/stage-2-bend.md`, finding (4)); a single `a` forces the hinge to carry it. The corridor's width changes
  are the dated candidate the ruling names for it; that they cause the shift is not claimed here.
- **The tie.** Finding #54 (closed): when every grid point at or above the training sample's highest ratio fits alike, the
  choice among them is rounding, and the kink jumped by up to 4.25 points between refits, against a goalpost of 0.5
  (protocol §3). The parent has since refused to pick among such points (#747, `KINK_TIE_RTOL`). A variant must keep that.

This is not a claim that any of the three is the cause. Whether a variant helps is what the later run measures.

## 2. The specification

A variant is a choice on three axes. The **baseline** is the current estimator (all pairs, squared error, one intercept, SOFR −
IORB). It is not a new variant; every variant is compared with it.

### (a) The pairs

A training pair is as in step 1: the ratio public at the scored day's own decision (`asof_days`, the parent's
`InformationRule`) and that day's spread in basis points. Two changes:

- **Calendar-clean pairs.** A pair is dropped when its scored day T satisfies either of:
  - `settlement_day` = 1, the parent's composed feature (`contract.COMPOSED_FEATURES`, `asof.COMPOSERS`): `quarter_end`, or
    `tax_date`, or `days_to_month_end ≤ SETTLEMENT_DAY_MONTH_END_DAYS` (2 calendar days up to and including the month's
    last day), or `treasury_settlement_coupons > 0`;
  - `quarter_end_window` = 1, the parent's opt-in column (`data.quarter_end_window`: the quarter's last business day and the
    two business days either side, `data.QUARTER_END_WINDOW_BUSINESS_DAYS`).

  Both are read from the parent's panel columns and functions at the pin, as of the day's decision instant (the first three
  clauses and the window are functions of the date and the tracked market-holiday table; the coupon settlement is a
  scheduled Treasury input, public before T). None is re-implemented here. **The ratios the pairs are fitted on are
  unchanged;** only which days enter changes. The estimate on a dropped day is still served, from the refit in force.
- **The left side.** Either SOFR − IORB (`spread_bps`) or EFFR − IORB (`effr_minus_iorb_bp`, parent `contract.py:410`, in
  whole basis points). EFFR is a slower gauge of how ample reserves are (the parent's note at that line). The two are run
  as separate variants, never pooled. Whether a variant uses EFFR is stated in the variant table (section 3).

*Marked reading for Eleonora:* "month-end ±2" is read as the parent's own month-end clause (the last two calendar days up to
the month's last day). The parent has no column for the first days of the next month, and adding one here would re-implement
the calendar; if the days after month-end must be dropped too, that needs a parent column, hers to order.

### (b) A least-absolute-deviation hinge

The same model, `left = a + b × max(0, k − ratio)`, `b ≥ 0`, on the **same grid** (`KINK_GRID`) and with the same minimum of
`KINK_MINIMUM_PAIRS` (250) pairs, but with the objective the sum of absolute deviations instead of squares. For each `k` the
inner fit is exact: the least-absolute-deviation line in `(hinge(ratio, k), left)` with `b ≥ 0`. The solver is the run's choice
within `docs/decisions/dependencies.md`, with two conditions: it returns the exact optimum (to a relative 1e-9), and a test
checks it against brute force over all two-point vertices on small constructed cases. A `k` with no spread in `hinge` (zero
variance) is skipped, as in the parent.

### (c) One intercept per width regime

`a` becomes `a_r`, one per **regime of the corridor's width**, the IORB minus the ON RRP offering rate in force:
`left = a_r + b × max(0, k − ratio)` with one shared slope `b ≥ 0` and one shared `k`.

- **The regime of a pair** is the width in force at that pair's scored day, read at its decision instant. The ON RRP offering
  rate is the repository's own snapshot (`snapshots/on_rrp_rate`, `repo_liquidity.scheduled.on_rrp_rate_values`), dated at
  **announcement**, and IORB is the parent's as-of column. A width becomes the regime's label the moment both rates in it
  are public, never at the effective date. A day that reads no ON RRP rate has no regime and is dropped from this variant's
  pairs, and reported.
- **The regimes expected** are widths of 25, 20, 15, 10 and 15 bp, in that order in time (the second 15 is a new regime, not
  a return to the first). **That list is from the directive, not from this document's reading of the data.** The first
  action of the run is to derive the regime table from the two series and print it; if it differs from the list in the
  number of regimes or in a width, the run stops and reports a finding rather than choosing.
- **A regime with fewer than 50 pairs at a refit** (fewer than a quarter of the minimum 250) has no intercept of its own at
  that refit: the refit is **not fitted**, and reported as such. No regime is merged into a neighbour.

### The tie rule (finding #54)

For every variant, the rule is the parent's (#747), with the objective of the variant:

- The candidates are the grid points that are feasible (`b ≥ 0`).
- **Tied** grid points are those whose objective is within `KINK_TIE_RTOL` (relative 1e-9) of the least.
- If the tied points span more than one grid step, the refit is **not fitted** ("not identified", with the tied span). It
  serves no kink and no interval, is reported (protocol §11), and **is never replaced by a picked point or by the fixed
  0.12.** If they span one step or fewer, the lower objective wins, then the lower index.
- The tie is tested at the objective actually in use. A least-absolute-deviation objective is piecewise linear, so exact ties
  between grid points are more likely than under squares; the rule applies the same way.

The later run must show, before any real data: the finding-#54 construction (linear data with no kink, ratios 0.10 to 0.15)
gives "not identified" under every variant, never a jump; and a planted kink at 0.12 is recovered exactly.

## 3. The variants

Each specification run is **one development variant** under protocol §7 and §10. The declaration runs these six, in this order
(a one-change step from the baseline on each axis, then the combinations the ruling names):

| # | Pairs | Left side | Objective | Intercepts |
|---|---|---|---|---|
| V1 | calendar-clean | SOFR − IORB | squares | one |
| V2 | all | SOFR − IORB | absolute deviation | one |
| V3 | all | SOFR − IORB | squares | per width regime |
| V4 | calendar-clean | SOFR − IORB | absolute deviation | one |
| V5 | calendar-clean | SOFR − IORB | absolute deviation | per width regime |
| V6 | calendar-clean | EFFR − IORB | absolute deviation | per width regime |

**The variant count this declaration adds is 6.** It is added to the count counted from Stages 2 to 6's records
(protocol §10); nothing is stated here about that earlier number. No other specification is run. A seventh would be a new
declaration, and a changed table after the run has seen data is a change motivated by a result (protocol §12).

## 4. The first experiment, for the later run

H7m steps 1 to 5 under `docs/decisions/measurement-protocol.md`, for the baseline and each of V1 to V6, on the development
walk-forward with the same refit dates, the same bootstrap (mean block 10, the parent's seed, the same number of draws) and
the same days:

- **Goalpost 1 (protocol §3):** the worst gap between a refit and the one before it, on every served day, against 0.5 points of
  bank assets.
- **Goalpost 2 (protocol §4):** the median width of the 90% interval, against 3 points.
- Each variant is compared with the current estimator on both. The count of refits that are **not fitted** is reported
  beside them, per variant, because a variant that is not fitted cannot breach a gap.
- **The RDE's sign changes from 2024-10-17 (directive #132) are an outside check:** reported, never deciding.
- A variant's figures carry the Tier "development". No figure is a verdict, and none is compared on a locked day
  (`docs/decisions/lockbox.md` in the parent; the run reads through `lockbox.require_unlocked`, as step 1 does).

**Kill.** No specification reduces the worst refit gap below the baseline's, **or** the clean-day kink's interval (V1, V4, V5,
V6) is wider than the raw one's (the baseline's) in median width. If the kill holds, the variant line stops and the baseline
stays the kink; this is recorded in the research log. If it does not, the variants are not chosen by this document: whether
any becomes a candidate is the choice rule of protocol §7.

## 5. What it does not change

- The protocol, the goalposts, the MME, and R and S as the deciding benchmarks (protocol §5).
- The parent's `satiation.py` and every other parent file. The variant is implemented in this repository only; the parent is
  imported, never edited and never copied (the tie rule above is restated, not re-implemented from a copy of its code).
- The estimand: still `D_T = R_T − k_T` in points of bank assets (step 1, section 1), the same interval construction, the same
  as-of rule.
- Candidate C, which has its own buffer and does not use this kink.
- No new input beyond those already declared: the calendar columns are the parent's, the ON RRP rate is this repository's
  existing snapshot, EFFR and IORB are the parent's panel. No new package.

## 6. What the run that follows must contain

Tests first. For every part of section 2, a test written and watched failing; the tie rule and the finding-#54 construction
under all six variants; the calendar-clean flag against the parent's own columns on a constructed week; the regime table;
the exact solver against brute force. A leakage test with one recorded mutation for the regime read (a width read at its
effective date instead of its announcement must raise `LookAheadError`), per `CLAUDE.md`. The run keeps long computation to
the Mac if it is expected to take over about two hours.
