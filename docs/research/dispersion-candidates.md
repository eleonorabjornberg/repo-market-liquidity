# HX step 3: the candidate set, the benchmarks and the variant count, declared before any is run (milestone M2)

**Draft for Eleonora's review (#214); in force only once she merges it.** It is a planning decision: the merge is hers. Written
11 November 2026. **Nothing is run, fitted or scored.** No goalpost is read, no R, S or R+S comparison is made, no day after
2026-09-03 is read, and no locked tier is touched. The power study is M3 and the development scores are M4, each a separate step.

**Hypothesis and step:** HX (provisional label; log tag `H7`), step 3, milestone M2 of `docs/research/dispersion-volume-hypothesis.md`
(section 4): "The candidates are declared, with their variant count, before any is run."
Rulings it follows: Eleonora, 11 November 2026 on step 2
([#212](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/212#issuecomment-6787609029)): form W1 as declared;
"Proceed; M3 and M4 show it"; training on every development day from 2018-04-04. And her ruling of 10 November on #207
(`sofr_p75_p25_bp` primary; volume secondary or context).

## 1. The candidate set

**W1 alone** (the draft, and the default).

| Candidate | Exact form | Input | Why it is there |
|---|---|---|---|
| **W1** | Declared in `docs/research/dispersion-estimator.md` section 1: candidate A's kink, left side the target day's `sofr_p75_p25_bp`, the kink `k` on the parent's grid minimising squared error of `width = a + b * max(0, k - ratio)` with `b >= 0`, fitted on calendar-clean development days from 2018-04-04, 90% stationary-bootstrap interval, refits and serving lag as H7m's | `sofr_p75_p25_bp` (the primary measure) | It is the primary-measure candidate, and the form she ruled on 11 November. |

**Why no second candidate.** Her refocus rule of 22 October is to stop patching failed models with variants, and this page's own
reasons give no specific one for another:

- **A secondary dispersion input** (`sofr_p99_p1_bp`) is the same observable family with the 1st percentile, which the data-meaning
  record marks as a noisy specials proxy (`data-meaning.md`, answer 8); the hypothesis is about cash scarcity.
- **A volume input** (`sofr_volume`, `bgcr_volume`) has a trend to remove, so any volume candidate needs a normalisation that is
  itself a choice (hypothesis page, section 3). `bgcr_volume` is treated as broken at 2027-06-30 until she rules.
- **`ofr_dvp_volume`** is context only: the OFR keeps no vintages, so it cannot enter a registration.
- Her 10 November ruling on #207 made the width primary and left volume secondary, promotable only by her.

## 2. What each candidate would cost in the variant count (v1 section 10)

The count is carried, not reset: 13 estimators in play, 11 of them variants, after step 2 (W1 is the 13th).

| Set | Added here | Count in play after M2 | Variants |
|---|---|---|---|
| **W1 alone (default)** | **0** (W1 was counted when step 2 declared it) | **13** | **11** |
| W1 and one more (for example the p99-p1 range, or a volume measure) | 1 | 14 | 12 |
| W1 and two more (a dispersion and a volume candidate) | 2 | 15 | 13 |

Every estimator declared at M2 counts, a not-scorable one included (`docs/stages/h7-step5.md` section 6, Q4). The count stays
the same as in the hypothesis page, section 4, and is pinned by `tests/test_dispersion_candidates.py`.

## 3. The benchmarks, unchanged

As in H7m (`plan.md`, "Benchmarks (the ones to beat)") and the hypothesis page, section 2. They come from the model repository's
two functions only.

- **R:** the plain reserves ratio, `reserves_ratio` (`src/repo_model/scarcity.py:161`).
- **S:** the current scarcity state (`scarcity.py:194`).
- **R+S:** both together.

## 4. Marked question for Eleonora (nothing is settled in code)

**The candidate set.**
1. **W1 alone (the draft).** **Default if unanswered by the next 5 pm batch.** Count stays 13, 11 variants. M3 and M4 run on W1.
2. W1 and a second candidate she names (its form, input and reason in a new directive before M3). Count 14, 12 variants.
3. W1 and a dispersion and a volume candidate she names. Count 15, 13 variants.

Any option other than 1 needs a candidate she specifies, so a reply of 2 or 3 is followed by a directive that declares the added
form before anything is run.

## 5. What this step does not do

- It runs, fits and scores nothing, reads no goalpost, and compares nothing with R, S or R+S.
- It makes no protocol change and no change to the parent, its pin, its panel, `sources_phase3.json` or any record.
- It does not decide whether BGCR's volume is affected by the 2027-06-30 break, nor whether a volume input is promoted.
