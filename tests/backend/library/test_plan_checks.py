"""plan_checks: the open check IDs of a game's docs/game/TEST-PLAN.md."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import plan_checks  # noqa: E402 - the repository root goes on sys.path first

PLAN = """# Test plan

Brief revision this plan follows: 2

## Checks

| ID | Given | When | Then | Evidence kind | Status |
|---|---|---|---|---|---|
| T1 | a fresh boot | 2 s pass | the title shows | PyBoy frames | passed |
| T2 | the title | Start | the meadow loads | PyBoy frames | not run |
| T3 | 2 of 3 seeds | the gate | it stays shut | PyBoy frames | superseded (by D2) |
| T3b | 3 seeds | the gate | it opens | PyBoy frames | failed |
| AUD1 | any | a seed is taken | a chime plays | human listening | needs review |
| T2 | a duplicate row | | | | |
| Example | not an ID | | | | |

| Date | Check | ROM SHA-256 / size | Inputs | Observed | Result | Evidence path |
|---|---|---|---|---|---|---|
| T9 | T1 | abc | Start | title | passed | frames/1.png |
"""


class OpenChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, text):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_game_without_a_test_plan_has_none(self):
        self.assertIsNone(plan_checks.open_checks(self.root))

    def test_the_checks_table_gives_its_ids_in_order_without_superseded_ones_or_the_results_log(self):
        self.plan(PLAN)
        self.assertEqual(plan_checks.open_checks(self.root), ["T1", "T2", "T3b", "AUD1"])

    def test_a_plan_without_a_checks_table_has_no_checks(self):
        self.plan("# Test plan\nT1: Given a fresh boot, when it starts, then the title shows.\n")
        self.assertEqual(plan_checks.open_checks(self.root), [])

    def test_damaged_text_is_still_read(self):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"| ID | Then |\n|---|---|\n| T1 | caf\xe9 |\n")
        self.assertEqual(plan_checks.open_checks(self.root), ["T1"])


if __name__ == "__main__":
    unittest.main()
