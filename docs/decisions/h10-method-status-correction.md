# Amendment (draft): section 10 of H10's attribution method is in force

**Status: DRAFT for Eleonora's review (directive #121; finding #119). In force only once she has merged it.** It changes no
value, no rule and no byte of `docs/decisions/h10-method.md`.

**What it corrects.** Section 10 of `docs/decisions/h10-method.md` (the 2 bp floor on the placebo's rise, finding #82) still
carries the line "Status: DRAFT for Eleonora's review (directive #85). In force only once she has merged it." She merged PR #88,
which added section 10, on 17 October 2026 (merge commit `764694eb7b93c42976124876e80b37711f0448e2`). Section 10 has been in force
since then, with its three rules and its marked question as merged. Her merge of this amendment makes that line read as
superseded.

**Why a separate record.** The line is inside the method record. Editing it there moves the record's sha256
(`642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9`), which `docs/research/h10-development-table.md` (published
in PR #78 and amended by PR #88) states and `tests/test_h10_step3.py` checks, and it would edit a published page's stated digest
in place. This note leaves the record and the page as they are. If she prefers the line corrected in the record itself, that is a
one-line edit with a new record digest, a re-stated page and a changed test; say so and a later directive does it.

**What it does not do.** It does not touch section 10's rules, `attribution.PLACEBO_RISE_FLOOR_BP`, the marked question in
section 10 (whether the rise is compared rounded), or the development records. It registers nothing.
