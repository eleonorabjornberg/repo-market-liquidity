# MBS scenario (advisor work, Nicholas Beroud)

The scenario narrative for the Fed's agency MBS holdings, assigned on #1. Descriptive work for review; nothing here is
scored, and nothing is an input to any model until Eleonora decides it is.

## The question

The Fed has said since 2019 that it wants to hold "primarily Treasury securities in the longer run", yet it still holds
about \$2tn of agency MBS. How it gets out of them matters for repo, because the three ways it can treat its MBS hit
reserves very differently:

1. **Passive runoff** (2017–19, 2022–25): paydowns drain reserves one-for-one, at a pace set by mortgage prepayments,
   not by the cap.
2. **Reinvestment into bills** (since 1 Dec 2025): reserve-neutral; holdings shift from MBS into bills.
3. **Active sales** (never done; the tail scenario): a double hit. Reserves fall by the amount sold, and the buyers
   finance part of the MBS in repo, so repo demand rises as the cash to meet it falls. Levered holders such as
   mortgage REITs, funded in repo, face margin calls into a falling market.

With the ON RRP buffer near zero, any drain now comes out of reserves directly. That is why this matters for the
deployable-liquidity model.

## What is here

| File | Stage | Status |
|---|---|---|
| [`01-facts.md`](01-facts.md) | 1, facts note: policy timeline, holdings, caps against realized runoff and mortgage rates | Done, for review |
| [`02-sizing.md`](02-sizing.md) | 2, sizing: reserve paths for S0–S3, the double hit, the hand-off to H7 | Draft, with two questions |
| [`compute.py`](compute.py) | Generates both notes from tracked data; `--check` fails if either is stale | |
| [`data/`](data) | Pre-2026 FRED snapshots (mortgage rate, reserves, ON RRP), each with a SHA-256 manifest | |

## How to reproduce

```bash
python3 docs/advisor/mbs-scenario/compute.py --check
```

Standard library only. It reads this repository's `h41_mbs_first_print.csv` and `runoff_caps.csv` plus the snapshots in
`data/`. Everything is cut at 2025-12-31, so no 2026 data informs the scenarios (the lockbox).

## Limits

- FRED snapshots are the latest revised vintage, not point-in-time; they are used descriptively and for sizing.
- Monthly holdings changes are noisy around MBS settlement dates; the notes rely on averages.
- Scenarios hold everything else equal (TGA, currency, the Fed's reserve-management purchases).
- "MBS" means agency securities in total; agency debt is about \$2.3bn.
