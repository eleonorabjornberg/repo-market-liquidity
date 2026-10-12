# repo-market-liquidity: standing rules

**This file is Eleonora's** (approved 5 October 2026). A pull request may propose changes to it, and must say so in its
description.

This repository is Phase 3 of repo-market-model. The parent's rules apply here unless this file says otherwise. Where
they disagree, the parent's `docs/decisions/` and this repository's `docs/decisions/` decide, and this file is the bug.

## How work happens

- One session, one branch, one pull request. Never push to `main`.
Delegated review (Eleonora, 12 October 2026, repo-market-model#643, T2). Queued pull requests here are reviewed and merged by the "Directive loop" routine (its review part), under "Delegated review" in repo-market-model's docs/decisions/workflow.md. Except: a stage verdict, a registration, a decision record, a published record and any change to this file are reviewed and merged by Eleonora.
- Each stage's pull request states what the stage had to show and whether it showed it.
- Judgement calls (a threshold, a data meaning, a published figure, a package) are hers; data meaning is Nicholas
  Beroud's under the parent's `PLAN.md`. Do not settle them in code.
  •	Step by step (Eleonora, 5 October 2026). One step of a hypothesis at a time, each written only after the previous one was reviewed.

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
