# Phase 3's exit criterion: not met on development, and H7m is closed

**Status: drafted for Eleonora; in force once she merges it.** A decision-level record, for her review. It scores nothing and changes no figure.

**Serves:** H7, the close of H7m, and Phase 3's exit criterion (`docs/research/plan.md`). Directive #198. Development tier.

## 1. The criterion

`docs/decisions/evaluation.md:88-112`, merged in #29:

> ## Amendment: Phase 3 is judged by the parent's exit criterion (draft for Eleonora)
>
> **Status: a draft for Eleonora's review. It is in force only once she merges it.**
>
> Ruling (Eleonora, 7 October 2026), after Stage 4 (#15) showed that a curve-based input to the parent's forecast is,
> in substance, the parent's own model: "Let's use the parent exit criterion".
>
> - **Phase 3's verdict is the parent's exit criterion:** stable posterior intervals for aggregate deployable liquidity,
>   with a clear account of their sensitivity to how reserves are distributed across banks (parent `PLAN.md`, Phase 3).
>   Whether it is met is Eleonora's verdict, on the evidence `docs/stages/stage-6.md` fixes:
>   - which candidates are eligible;
>   - which one is chosen;
>   - the account of the distribution.
> - **The forecast comparison stays, reported only.** The CRPS comparison above (the published gbm with and without
>   Phase 3's addition), the frozen Stage 4 declaration and the Stage 5a log are unchanged. They are still scored on the
>   dates above, with the same pass rule and labels, but a "shown better" or "not shown" there no longer decides
>   Phase 3. Each Stage 6 candidate's forecast gain is reported beside its result, never deciding.
> - **The evidence rules are unchanged:**
>   - development is the as-of walk-forward to 2025-12-31;
>   - 2026 to date is not evidence;
>   - confirmatory evidence is only what Phase 3 logs before the outcome, from a frozen declaration.
>
>   For deployable liquidity, which has no outcome of its own, confirmatory evidence is the chosen model's frozen daily
>   estimate, logged before each day's spread and facility take-up are known, and judged against them on the scoring
>   dates above.

`docs/research/plan.md:323-330` places the criterion inside H7m: its stability and sharpness goalposts cover the first half, and step 4 (the distribution account) the second.

## 2. Her ruling

Eleonora, 28 October 2026, relayed by the orchestrating session on directive #198: **Phase 3 after H7m, option (a).** "Record Phase 3's exit as not met on development and close H7m. H7f goes on with R+S in the model repo (`docs/research/plan.md:193-194`), and H10 carries on live."

## 3. The evidence

H7m's stage verdict is "not testable as stated": no eligible candidate after steps 2 to 5. It is the record `results/h7/verdict.json` (`7c753f0f2af99c3daea97905c44563e4eb3abdd0096b437ff8963482954251d0`), published by PR #191 and republished by PR #196, with its page `docs/stages/h7m-verdict.md`. This page restates no figure from it.

## 4. The outcome

Phase 3's exit criterion is **not met on development**, and **H7m is closed**. Whether the criterion is met is her verdict, and this is it, as she ruled on 28 October 2026.

## 5. What continues

- **H7f**, in the model repository, with R+S alone (`docs/research/plan.md:193-194`). It is the model repository's to run.
- **H10**, live, under its registration of 22 October 2026 on #23 (the comment at the new parent pin, which carries the commit and the method digest).

## 6. What this does not claim

The record states the rule's result and nothing more. It makes no claim about whether scarcity can be measured, and says nothing about the outcome of H7f.

## 7. Untouched

`docs/decisions/evaluation.md` and every published record are not edited. The plan gains a pointer to this page and a current step for H7m; every rule in it stands.
