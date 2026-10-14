# H7m, groundwork G4: group reserves (the anchor and the weekly series)

**Serves:** H7 (reserve scarcity can be tracked), measurement question H7m, groundwork G4 of the plan
(`docs/research/plan.md`), for candidate C (#41). Directive #43, PR #50. **Inputs built, nothing scored.** Development, never a
verdict.

Read with `docs/research/rca-fed-balances-due-diligence.md` (section 7 is the update) and row 18 of
`docs/decisions/data-meaning.md`.

## What it builds

1. **The quarterly anchor** (`repo_liquidity.rca`, `declarations/ffiec_call_rca.json`, snapshot `snapshots/rca_anchor/`).
   Schedule RC-A item 0090, balances due from Federal Reserve Banks, summed over two domestic groups: the 25 filers with the
   largest total assets (a labelled approximation of the Board's panel) and every other filer that carries the item. Latest-filed
   figures (answer 16(d) as amended), a group available from the day after its slowest member's latest update.
2. **The weekly series** (`repo_liquidity.group_reserves`, `scripts/build_group_reserves.py`). Eleonora's rulings of 14 October 2026
   (option (a) for the foreign-related group, option (i) for the domestic split): the large domestic, small domestic and
   foreign-related levels are each the H.8 group's cash assets, first print, unanchored and labelled an approximation
   (`domestic_basis`, `foreign_basis`); the residual "other depository institutions" is H.4.1 reserve balances (`WRESBAL`) less
   the three, not clipped. The weekly series does **not** read the RC-A anchor: that would break rule 16(d). A week at an H.8 break
   (`h8_break_week`) is flagged, not refused, because a level is a first print and not a ratio.

## The small-domestic caveat (answer 17(a), named as the directive requires)

Cash assets overstate small domestic banks' reserves: vault cash and balances at correspondent banks are a much larger share of
them. The small group here is the H.8 small domestic banks' cash assets, unanchored (the RC-A anchor of this PR is not read by
the weekly series), so the overstatement is not removed. The groups must not be summed naively: balances due from other
depository institutions double-count. The large and foreign-related levels are cash-asset approximations for the same reason.
The residual absorbs every difference and is not a measure of anything on its own.

## What it shows

See `docs/research/rca-anchor-coverage.md` and `docs/research/group-reserves-coverage.md`, both generated. The weekly series has a
row for every H.8 week (the first public on 2018-01-05). **The residual is negative in most weeks** (see the coverage record
for the count and its range): the three groups' cash assets together exceed H.4.1 reserves, as answer 17(a) warns, because cash
assets include vault cash, cash items in process of collection and balances due from other depository institutions. The residual
is flagged and never clipped; it measures the approximation's overshoot and not a group of institutions. The weekly series is
tracked, not published as a snapshot; whether it should be is a marked question in PR #50.

## Guards (each with one recorded mutation in its test's docstring)

- `rca.withhold_locked` and `rca.load_extract`: nothing past the parent's development end (`LookAheadError`).
- `rca.check_declared_lag`: no figure read before its last update (`LookAheadError`); no declared lag above the measured
  worst case (`StaleReadError`).
- `rca.read`: a read before the slowest member's update is `LookAheadError`; a read of an older quarter than the latest public
  is `StaleReadError`.
- `group_reserves._public_at` (used by `build`) and `verify`: a row is public only from the later of its H.8 release and its
  reserves' declared availability; `verify` raises `LookAheadError` for a row public earlier, and `ValueError` for a level
  that is not the first print. Both inputs are first prints, so there is no staleness guard.
