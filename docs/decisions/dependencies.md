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

## statsmodels (approved 6 October 2026)

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), on `PLAN.md` D3: "Approve statsmodels now."

- **statsmodels is approved** for Phase 3's state-space models and their estimation (Stage 3 on).
- **Version:** 0.14.6, the latest release pip resolves for CPython 3.11 on 6 October 2026 (0.15.0 exists but does not
  install on 3.11). 0.14.6 fixes an import error under numpy 2.4, the version the parent's `ml` extra pins.
- **It enters `pyproject.toml` when Stage 3 first uses it,** as an optional extra pinned exactly, together with the
  versions of its own dependencies (scipy, pandas, patsy) that the install resolves; CI installs the same pins. Those
  transitive pins are recorded here in the same pull request.
- A figure that moves with statsmodels' version is a figure of record only on the pinned version.
- **Entered for Stage 3 (6 October 2026)** as the `state-space` extra in `pyproject.toml`, pinned exactly with what
  the install resolved on CPython 3.11: statsmodels 0.14.6, numpy 2.4.6 (the parent's `ml` pin), scipy 1.17.1,
  pandas 3.0.6, patsy 1.0.3, python-dateutil 2.9.0.post0, six 1.17.0, packaging 26.3. CI installs the same pins.
