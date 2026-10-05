# Decision: dependencies

Ruling (Eleonora, 5 October 2026, on repo-market-model#233, question 3): "Let's create a separate repo for this then, no
need to crowd the model."

- This repository exists so that Phase 3 may use state-space and Bayesian libraries that the parent keeps out of its own
  standard-library code.
- **Which packages, and their versions, is Eleonora's decision**, recorded here before a package is first used. The
  candidates are proposed by Stage 3 once Stage 2 has been reviewed. Until then the code uses the parent package and the
  standard library only.
- The parent is a pinned dependency: one commit, named in `pyproject.toml`, with the panel's published digest checked
  in CI. Moving the pin is a change reviewed like any other.
- Python follows the parent's declaration (3.11), so the parent's records reproduce here to the bit.
