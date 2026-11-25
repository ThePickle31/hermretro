"""plan_checks: the open checks of a game's docs/game/TEST-PLAN.md."""

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
| t2 | a duplicate row in another case | | | | |
| `GATE-1` | the gate | A | it opens | PyBoy frames | blocked |
| **T3B** | the gate | B | it says superseded on screen | PyBoy frames | passed |
| Example | not an ID | | | | |
|  | an empty ID | | | | |

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
        self.assertIsNone(plan_checks.read_plan(self.root))

    def test_the_checks_table_gives_its_ids_in_order_without_superseded_ones_or_the_results_log(self):
        self.plan(PLAN)
        plan = plan_checks.read_plan(self.root)
        # T3B is T3b in another case: one check, the first row's.
        self.assertEqual(plan.checks, ["T1", "T2", "T3b", "AUD1", "GATE-1"])
        self.assertEqual(plan.unreadable, ["Example"])

    def test_superseded_is_read_from_the_status_column_only(self):
        self.plan(
            "| ID | Then | Result |\n|---|---|---|\n| T1 | the superseded sign shows | passed |\n"
            "| T2 | it ends | superseded (by D3) |\n\n| ID | Then |\n|---|---|\n| T4 | superseded |\n"
        )
        self.assertEqual(plan_checks.read_plan(self.root).checks, ["T1", "T4"])

    def test_checks_written_as_lines_are_read_outside_the_results(self):
        self.plan(
            "# Test plan · revision 1\n"
            "T1: Given a fresh boot, when startup finishes, then a frog appears. PyBoy frames.\n"
            "- **T2**: Given a resting frog, when A is pressed, a croak plays.\n"
            "T3: superseded (by D2). Given the pond, the frog swims.\n"
            "T4: Given the pond, then it ripples. Status: superseded\n"
            "Status: not run / passed\n"
            "Native ROM SHA-256 `1d6a`: valid cartridge.\n"
            "## Results · 2026-11-22\n"
            "T9: passed on the last ROM.\n"
        )
        self.assertEqual(plan_checks.read_plan(self.root), plan_checks.Plan(["T1", "T2"], []))

    def test_a_plan_without_checks_has_none(self):
        self.plan("# Test plan\nEvery check is observable.\n")
        self.assertEqual(plan_checks.read_plan(self.root).checks, [])

    def test_damaged_text_is_still_read(self):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"| ID | Then |\n|---|---|\n| T1 | caf\xe9 |\n")
        self.assertEqual(plan_checks.read_plan(self.root).checks, ["T1"])


if __name__ == "__main__":
    unittest.main()
