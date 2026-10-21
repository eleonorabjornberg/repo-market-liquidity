"""H7m, groundwork G6 (L27, #105): the material-use event has a label after 2025-12-31.

At the parent's `53e61af`, `fed_liquidity.assemble` refused any date after 2025-12-31, so `goalposts.labelled_days`
had no label after that date. At `8fd2cf8` (repo-market-model#772) the Desk's repo-operation snapshots run to
2026-09-03. These tests read the labels exactly as `scripts/g6_power_study.py` does, through the parent's
`fed_liquidity.assemble`; no as-of rule is re-implemented here.

Written first, and watched failing against the parent at `53e61af` (CPython 3.11, `PYTHONDONTWRITEBYTECODE=1`):
`AssertionError: datetime.date(2025, 12, 31) not greater than or equal to datetime.date(2026, 9, 3)` for the declared
coverage end, and `AssertionError: 0 not greater than 0` for the labelled days after 2025-12-31.
"""

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from repo_model import fed_liquidity
from repo_model.data import load_daily_panel

from repo_liquidity import goalposts as gp, panel, parent_root

LAST_LABEL_DAY = date(2026, 9, 3)


def _accepted():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        manifest = panel.build(path, version=4)
        rows = load_daily_panel(path)
    snapshots = parent_root() / "tests" / "fixtures" / "snapshots" / "repo_ops_inputs"
    end = fed_liquidity.declared_coverage_end(fed_liquidity.NYFED_REPO_OPS_SOURCE_ID)
    assembled, _ = fed_liquidity.assemble(rows, snapshots, cutoff=datetime.fromisoformat(manifest["build_cutoff"]), end=end)
    return {row.date: row.values.get("fed_repo_accepted") for row in assembled}


class RepoOperationLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accepted = _accepted()

    def test_the_declared_coverage_reaches_the_last_development_day(self):
        end = fed_liquidity.declared_coverage_end(fed_liquidity.NYFED_REPO_OPS_SOURCE_ID)
        self.assertGreaterEqual(end, LAST_LABEL_DAY)

    def test_days_after_2025_are_labelled(self):
        later = {d: v for d, v in self.accepted.items() if d > date(2025, 12, 31) and v is not None}
        self.assertGreater(len(later), 0)
        self.assertIn(LAST_LABEL_DAY, later)

    def test_the_event_is_read_from_those_labels(self):
        from repo_liquidity.h7_estimator import Day

        days = [Day(d, 0.12, 0.0, 1.0) for d in sorted(self.accepted) if d > date(2025, 12, 31)]
        out = gp.labelled_days(days, self.accepted)
        self.assertGreater(len(out.days), 0)
        self.assertEqual(out.days[-1].day, LAST_LABEL_DAY)
        self.assertEqual(out.dropped["no label"], len(days) - len(out.days))


if __name__ == "__main__":
    unittest.main()
