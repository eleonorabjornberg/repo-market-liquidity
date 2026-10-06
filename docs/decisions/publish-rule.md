# Decision: publishing a Phase 3 record

**Status: decided by Eleonora, 6 October 2026. In force once this record merges.**

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), accepting `PLAN.md` D4 as drafted.

It mirrors the parent's `docs/decisions/publish-rule.md`, adapted to a repository that is pinned to another.

## The rule

- **A record scored at commit R of this repository is publishable on `main` only if nothing that decides a figure has
  changed since R:** `git diff --name-only R main -- src/ metadata/ tests/fixtures/` is empty, and `PARENT_COMMIT` is
  the same at R and on `main`. Otherwise it is re-scored, never published with an explanation instead.
- **Every record carries its provenance:** this repository's commit and whether its tree was modified, the parent pin,
  the parent panel digest and the Phase 3 panel digest.
- **A figure of record is computed on Python 3.11** with the parent's pinned numpy and scikit-learn, and reproduced in
  CI before it is published. A figure computed elsewhere is development evidence only.
- **A publish is a pull request** that adds the records and regenerates anything rendered from them in the same commit,
  with CI green. Eleonora merges it.
- **A published record is never edited in place.** It is re-scored and published anew, or archived with a note saying
  why.
- **No figure is transcribed by hand** into a published page; pages cite the record.

## Amendment: publish when Eleonora says so

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), on D4: "publish when i say so."

- **A Phase 3 record is published only when Eleonora says so.** The conditions above are necessary, not sufficient.
- **No session opens a publish pull request on its own initiative.** A record that has been scored waits unpublished,
  outside `docs/runs/`, until she asks for it to be published.
