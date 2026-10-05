# repo-market-liquidity: standing rules

**DRAFT, proposed by the orchestrating session for Eleonora's review. This file is hers.**

This repository is Phase 3 of repo-market-model. The parent's rules apply here unless this file says otherwise. Where
they disagree, the parent's `docs/decisions/` and this repository's `docs/decisions/` decide, and this file is the bug.

## How work happens

- One session, one branch, one pull request. Never push to `main`.
- **Staged work (Eleonora, 5 October 2026).** One stage at a time, each written only after the previous stage was
  reviewed. **Every stage's pull request is reviewed and merged by Eleonora.** Delegated review does not merge here.
- Each stage's pull request states what the stage had to show and whether it showed it.
- Judgement calls (a threshold, a data meaning, a published figure, a package) are hers; data meaning is Nicholas
  Beroud's under the parent's `PLAN.md`. Do not settle them in code.

## The science rules

- **The parent's information set binds every input.** Read the parent's panel and use its as-of guards
  (`repo_model.asof.InformationRule`); never re-implement them. A new input gets an availability declaration and a
  leakage test with one recorded mutation that kills it.
- **The evaluation rule is `docs/decisions/evaluation.md`.** Nothing is scored before it is merged.
- Never touch the parent's published model, pre-registration, live record or records.
- Leakage guards raise `LookAheadError`; data guards raise `ValueError`.
- Never edit a published record in place.

## Tests

- Write the test first and watch it fail. Run the full suite in one process before asking for review.
- CI checks the parent pin and the panel digest (`tests/test_parent_pin.py`).
