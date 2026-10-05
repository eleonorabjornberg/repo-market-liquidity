# Repo Market Liquidity

Phase 3 of [repo-market-model](https://github.com/eleonorabjornberg/repo-market-model): how much of the banking
system's cash is actually deployable on a given day, and how much banks hold back.

```text
deployable reserves = observed reserves - latent desired buffer
```

The parent project forecasts overnight funding stress from public data, read as it stood at 4 pm the day before.
This repository estimates the hidden quantity behind that stress, the liquidity banks are willing to lend, and asks
one practical question: **does knowing it make the stress forecast better?**

**Status: planning.** Nothing is scored yet. The plan is [`PLAN.md`](PLAN.md); the rules every result must pass are in
[`docs/decisions/`](docs/decisions). Each stage is reviewed before the next one is written.

## How it relates to the parent

- It reads the parent's point-in-time panel and its as-of guards, pinned to one parent commit and the panel's
  published digest. It never copies or re-implements them, so no input can be read before it was public.
- It may use state-space and Bayesian libraries the parent keeps out of its own code
  ([`docs/decisions/dependencies.md`](docs/decisions/dependencies.md)).
- It never changes the parent's published model, its pre-registered final test or its live record.

## Licence

MIT, as the parent.
