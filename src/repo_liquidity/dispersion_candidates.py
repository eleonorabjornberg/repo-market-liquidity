"""HX step 3 (M2, #214): the candidate set and its variant count, declared before any candidate is run.

A draft for Eleonora (`docs/research/dispersion-candidates.md`). Nothing here fits, runs or scores anything: it holds the
declared set, the benchmarks and the count, so that a test can pin them.
"""

from . import dispersion_estimator as w1

CANDIDATES = ("W1",)
PRIMARY = "W1"
INPUTS_OF = {"W1": (w1.LEFT_COLUMN,)}
BENCHMARKS = ("R", "S", "R+S")

# Step 2 (#210) already counted W1 (12 carried, 13 in play). Declaring it here as the candidate adds nothing.
ADDED_AT_M2 = 0
ESTIMATORS_IN_PLAY = w1.VARIANTS_IN_PLAY + ADDED_AT_M2
VARIANTS_IN_PLAY = ESTIMATORS_IN_PLAY - 2  # A and C are the two estimators that are not variants of another


def count_with(names):
    """The count in play if exactly `names` were declared: W1 is already in the 13, every other name adds one."""

    return w1.VARIANTS_CARRIED + 1 + len([n for n in names if n != "W1"])
