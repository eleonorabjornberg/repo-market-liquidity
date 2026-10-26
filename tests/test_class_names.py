"""No test module in `tests/` defines the same class name twice at module level (directive #184, finding #183).

PR #180 appended a second `TrackedCorrectionsTests` to `tests/test_log_push.py`; the second binding replaced the first,
so the two #76 tests were no longer collected and nothing failed. The module is read through `ast`, so a repeat is
caught however the classes are ordered or guarded.

Recorded mutation (the guard: a repeated module-level class name fails): copying `class CorrectionTests` in
`tests/test_log_push.py` under the same name makes `test_no_test_module_repeats_a_class_name` fail with
`AssertionError: Lists differ` naming `test_log_push.py: CorrectionTests`. Written before the fix; it failed the same
way on `tests/test_log_push.py` as merged (`TrackedCorrectionsTests`), and the checker itself is tested below on a
small source string.
"""

import ast
import unittest
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def repeated_classes(source):
    """The class names bound more than once at the top level of `source`, sorted."""
    names = Counter(node.name for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    return sorted(name for name, count in names.items() if count > 1)


class ClassNameTests(unittest.TestCase):
    def test_the_checker_finds_a_repeat_below_a_main_guard(self):
        source = "class A: pass\nif __name__ == '__main__':\n    pass\nclass A: pass\nclass B: pass\n"
        self.assertEqual(repeated_classes(source), ["A"])

    def test_a_nested_class_with_the_same_name_is_not_a_repeat(self):
        self.assertEqual(repeated_classes("class A:\n    class B: pass\nclass B: pass\n"), [])

    def test_no_test_module_repeats_a_class_name(self):
        found = [f"{path.name}: {name}" for path in sorted(TESTS.glob("*.py"))
                 for name in repeated_classes(path.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
