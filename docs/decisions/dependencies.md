# Decision: dependencies

Ruling (Eleonora, 5 October 2026, on repo-market-model#233, question 3): "Let's create a separate repo for this then, no
need to crowd the model."

- This repository exists so that Phase 3 may use state-space and Bayesian libraries that the parent keeps out of its own
  standard-library code.
- **Which packages, and their versions, is Eleonora's decision**, recorded here before a package is first used. The
  candidates are proposed by Stage 3 once Stage 2 has been reviewed. Until then the code uses the parent package and the
  standard library only.
- The parent is a pinned dependency: one commit, named in `pyproject.toml` and as `PARENT_COMMIT`, with the panel's
  published digest checked in CI. Moving the pin is a change reviewed like any other.
- The parent reads its `metadata/` relative to its own source tree, so it is installed editable from a checkout at the
  pinned commit, not from a built package. `tests/test_parent_pin.py` checks that the imported parent is a clean
  checkout of `PARENT_COMMIT`, that `pyproject.toml` pins the same commit, and that the panel rebuilt from the
  parent's tracked fixtures has the published digest.
- Python follows the parent's declaration (3.11), so the parent's records reproduce here to the bit.
