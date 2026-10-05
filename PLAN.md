# Plan: Phase 3, latent reserves and deployable liquidity

Moved from [repo-market-model#233](https://github.com/eleonorabjornberg/repo-market-model/issues/233), where Eleonora's
rulings of 5 October 2026 were made. The parent's `PLAN.md` (Phase 3) is the origin of the goal and the exit criterion.

## Goal

Estimate **deployable liquidity**: observed reserves minus the buffer banks want to keep, a quantity no one reports,
inferred from what the market reveals (the spread, SOFR dispersion, volume, ON RRP and facility usage, payment timing).

**Exit criterion (parent `PLAN.md`):** stable posterior intervals for aggregate effective liquidity, with a clear
account of their sensitivity to the bank-level distribution of reserves, which is not observed.

## How the work runs (Eleonora, 5 October 2026)

- **Staged, one stage at a time.** Each stage is its own piece of work, written only after the previous stage has been
  reviewed. No stage is started ahead of that review.
- **Every stage ends with Eleonora.** She reviews each stage's result and decides whether the next goes ahead, changes,
  or stops.
- **Each stage states up front what it must show** for the next one to be worth doing, and its write-up says plainly
  whether it did.
- **Separate from the final test.** The parent's "no new model variants" rule covers its final test only. Nothing here
  changes the parent's published model, pre-registration or live record.

## Stages

1. **Data, as of 4 pm.**
   - Already in the parent panel: reserves, TGA, ON RRP, Treasury settlements (including the Fed's SOMA share), H.8 bank
     assets as first prints.
   - To add, subject to the data question below: the Fed's Treasury holdings (`TREAST`), the QE/QT pace, the announced
     runoff caps as a scheduled input, and standing repo facility usage.
   - Each new input gets an availability declaration under the parent's information-set rule and a leakage test.
   - *Must show:* every input reads only what was public at the decision instant, and covers 2018 to now.
2. **The reserve demand curve (descriptive).** The spread against reserves relative to bank assets, by regime,
   extending the parent's declared scarcity state (`src/repo_model/scarcity.py`). Where the curve bends is a first,
   transparent estimate of the desired buffer.
   - *Must show:* a curve whose bend is stable enough across regimes to be worth modelling. If it is not, Stage 3 is
     reconsidered before it is designed.
3. **The latent model.** Not designed until Stage 2 is reviewed. Expected form: a state-space model with deployable
   liquidity as the hidden state, moved by known flows (TGA, settlements, QT runoff) and seen through the spread,
   dispersion, volume, ON RRP and facility usage.
4. **Evaluation.** Under [`docs/decisions/evaluation.md`](docs/decisions/evaluation.md): as-of walk-forward, posterior
   stability, and the practical test against the parent's published pressure probability; a sensitivity run on reserve
   concentration (H.8 large versus small banks).
5. **Monitoring.** The latent state beside the parent's live record, computed from tracked inputs, never changing the
   parent's frozen daily file.

## Open question: data meaning (Nicholas Beroud, the project's advisor)

Under the parent's `PLAN.md`, the choice of data and its meaning rests with Nicholas. Before Stage 1 is written:

1. Which QE/QT measure: the level of the Fed's holdings, its weekly change, the announced runoff caps, or a combination?
2. Are standing repo facility usage and H.8 bank assets the right proxies for the facility outside option and bank
   balance-sheet size?
3. Do the announced runoff caps count as a scheduled input (known in advance, like a settlement)?

His evidence pack (parent branch `advisor/evidence-pack`, and his comment on parent PR #219) points to the ON RRP buffer
and a QT restart as the levers.
