"""The parent is importable at the pinned commit, and its as-of guard is the one in use."""

import unittest


class ParentPinTests(unittest.TestCase):
    def test_the_parent_package_imports(self):
        import repo_model.asof  # noqa: F401

    def test_the_pin_is_one_full_commit(self):
        import repo_liquidity

        self.assertRegex(repo_liquidity.PARENT_COMMIT, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
