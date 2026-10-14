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
2. **The weekly series** (`repo_liquidity.group_reserves`, `scripts/build_group_reserves.py`). Large and small domestic levels are
   the latest anchor public at the row's instant, moved by the ratio of the group's H.8 cash assets; the foreign-related level
   is the H.8 foreign-related cash assets (Eleonora's ruling of 14 October 2026, option a, an approximation); the residual
   "other depository institutions" is H.4.1 reserve balances (`WRESBAL`) less the three groups, not clipped.

## The small-domestic caveat (answer 17(a), named as the directive requires)

Cash assets overstate small domestic banks' reserves: vault cash and balances at correspondent banks are a much larger share of
them. The small group here is built from RC-A balances at the Reserve Banks, not from cash assets, which removes the overstatement
at the anchor; but the weekly *moves* of the small group are H.8 cash-asset moves, which still include vault cash and
correspondent balances, and the small group's anchor covers only the filers that carry item 0090. The groups must not be summed
naively: balances due from other depository institutions double-count. The foreign-related level is a cash-asset
approximation for the same reason. The residual absorbs every difference and is not a measure of anything on its own.

## What it shows

See `docs/research/rca-anchor-coverage.md` and `docs/research/group-reserves-coverage.md`, both generated. In short: under the
ruled vintage reading the large-bank anchor is public years after the quarter-end, and with the H.8 break weeks no week of the
development period has a row, so **no snapshot of the weekly series is published**. The three open readings that would change
this are marked questions for Eleonora (row 18 of the data-meaning record, and PR #50).

## Guards (each with one recorded mutation in its test's docstring)

- `rca.withhold_locked` and `rca.load_extract`: nothing past the parent's development end (`LookAheadError`).
- `rca.check_declared_lag`: no figure read before its last update (`LookAheadError`); no declared lag above the measured
  worst case (`StaleReadError`).
- `rca.read`: a read before the slowest member's update is `LookAheadError`; a read of an older quarter than the latest public
  is `StaleReadError`.
- `group_reserves.build` and `verify`: an anchor not public at the row's instant (`LookAheadError`), an older anchor than the
  latest public (`StaleReadError`), a move across a break week (a listed hole), an anchor quarter after its week
  (`LookAheadError`).
