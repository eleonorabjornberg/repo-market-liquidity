# Repo Market Liquidity

Phase 3 of [repo-market-model](https://github.com/eleonorabjornberg/repo-market-model): how much of the banking
system's cash is actually deployable on a given day, and how much banks hold back.

```text
deployable reserves = observed reserves - latent desired buffer
```

**Aim from 12 October 2026** (Eleonora, [repo-market-model#643](https://github.com/eleonorabjornberg/repo-market-model/issues/643)):

- **H7's estimator:** deployable liquidity and the reserve-scarcity state, estimated as a slow variable;
- **H10:** attributing pressure episodes to their drivers.

Forecast claims are scored only in repo-market-model, under
[repo-market-model#640](https://github.com/eleonorabjornberg/repo-market-model/issues/640); this repository scores no
forecast itself. It ingests its own inputs and publishes its estimates as snapshots named by their digest. Where a
module duplicated the parent's, it was deleted in favour of the parent's
([`docs/decisions/deleted-duplicates.md`](docs/decisions/deleted-duplicates.md)).

**Status: restarted 12 Oct 2026; research plan pending Eleonora's decision
([#20](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/20)).** The plan is [`PLAN.md`](PLAN.md); the
rules every result must pass are in [`docs/decisions/`](docs/decisions). Stages 1 to 6 (5 to 12 October 2026) are the
development record: their results are under [`results/`](results), verified at the commit and parent pin they were made
from (`scripts/verify_records.py`).

## How it relates to the parent

- It reads the parent's point-in-time panel and its as-of guards, pinned to one parent commit and the panel's
  published digest. It never copies or re-implements them, so no input can be read before it was public.
- It may use state-space and Bayesian libraries the parent keeps out of its own code
  ([`docs/decisions/dependencies.md`](docs/decisions/dependencies.md)).
- It never changes the parent's published model, its pre-registered final test or its live record.

## The results site

[`scripts/emit_site.py`](scripts/emit_site.py) builds one page, `site/index.html`, from the published records and the
parent's published panel at the pin, in the style of the model repository's page (template: [`site/template.html`](site/template.html)).
Nothing on it is typed, and the built page is never committed: the pages job builds it on main
([`.github/workflows/pages.yml`](.github/workflows/pages.yml)). Locally: `python3 scripts/emit_site.py` (the parent
installed at the pin, as for the tests); `--check` rebuilds it and fails on any error.

## Licence

MIT, as the parent.
