"""Review findings on the tenth round's fixes: a plan forgot it was shared once its first branch landed and land or
gc forgot that branch's record; the page-test helper scan read six lines past each declaration, so a short helper
swallowed the next one and took the credit for its selector. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_ten_review
"""

import io
import unittest
from pathlib import Path

from retrodev import config, output, scaffold_page_tests, ship, state
from retrodev.scaffold import Plan

from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write

load_tests = parallel


class SharedAfterLanding(RepoCase):
    def ctx(self):
        return config.Context.make(self.main, output.Out(stream=io.StringIO()))

    def approved(self) -> None:
        titled = FILLED_PLAN.format(topic="duo").replace("\n\n## Goal", "\n\nTitle: Make the whole duo work\n\n## Goal")
        write(self.main, "notes/plans/duo.md", titled)
        code, out = self.run_cli("plan", "approve", "duo", "--words", "start")
        self.assertEqual(code, 0, out)

    def started(self, name: str) -> str:
        code, out = self.run_cli("start", name, "--plan", "duo", "--no-setup")
        self.assertEqual(code, 0, out)
        return (self.main / "notes" / "pr" / f"{name.partition('/')[2]}.md").read_text()

    def landed(self, name: str) -> None:
        """What land and gc leave of a merged branch: no worktree, no branch, no record."""
        record = state.load_branch(self.main, name)
        git(self.main, "worktree", "remove", "--force", record["worktree"])
        git(self.main, "branch", "-D", name)
        state.drop_branch(self.main, name)
        self.assertFalse(any(r.get("branch") == name for r in state.branches(self.main)))

    def test_a_branch_started_after_the_first_landed_still_shares_the_plan(self):
        self.approved()
        self.assertIn("## Why\nMake duo work.\n", self.started("feat/duo-one"))
        self.landed("feat/duo-one")
        second = self.started("feat/duo-two")
        self.assertNotIn("Make duo work.", second)
        self.assertIn("## Why\n" + ship.SHARED + "\n", second)
        self.assertNotIn("Nothing else.", second, "the whole plan's Not in scope is not this branch's Not done")
        record = state.load_branch(self.main, "feat/duo-two")
        self.assertIsNone(ship.plan_title(self.ctx(), "feat/duo-two", record))

    def test_the_second_branch_keeps_its_title_protection_after_the_first_is_forgotten(self):
        self.approved()
        self.started("feat/duo-one")
        self.started("feat/duo-two")
        self.landed("feat/duo-one")
        record = state.load_branch(self.main, "feat/duo-two")
        self.assertIsNone(ship.plan_title(self.ctx(), "feat/duo-two", record))
        self.assertIn("the plan covers several branches", ship.title_note(self.ctx(), "feat/duo-two", record))
        self.assertTrue(ship.plan.shared(self.ctx(), "feat/duo-two", record))
        # The first branch alone is still not shared: nothing started before it.
        first = {"branch": "feat/duo-one", "topic": "duo-one", "plan": "duo", "created": "0000"}
        self.assertFalse(ship.plan.shared(self.ctx(), "feat/duo-one", first))

    def test_plan_link_moves_a_branch_off_its_old_plan(self):
        self.approved()
        write(self.main, "notes/plans/solo.md", FILLED_PLAN.format(topic="solo"))
        self.started("feat/duo-one")
        tree = Path(state.load_branch(self.main, "feat/duo-one")["worktree"])
        code, out = self.run_cli("plan", "link", "solo", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("feat/duo-one", (state.load_plan(self.main, "duo") or {}).get("branches", {}))
        self.assertIn("feat/duo-one", (state.load_plan(self.main, "solo") or {}).get("branches", {}))


def helpers_for(test: str, rendered: str) -> list[str]:
    plan = Plan(top=Path("/nonexistent"), created={"t.test.mjs": test, "menu.js": rendered})
    return scaffold_page_tests.slot_helpers(plan, "t.test.mjs", "menu.js")


class BoundedHelpers(unittest.TestCase):
    MENU = "jsx('div', { className: 'cs-menu', children: jsx(Slot, { name: 'games.cardMenu' }) })\n"

    def test_adjacent_short_helpers_are_each_their_own_function(self):
        test = (
            "  const openCard = async card => { await click(card.querySelector('.cs-card')) }\n"
            "  const openMenu = async card => {\n"
            "    await click(card.querySelector('.cs-menu'))\n"
            "  }\n"
        )
        self.assertEqual(helpers_for(test, self.MENU), ["openMenu"])
        expression = "  const a = async () => click('.cs-card')\n  const b = async () => click('.cs-menu')\n"
        self.assertEqual(helpers_for(expression, self.MENU), ["b"])

    def test_strings_comments_and_templates_do_not_end_or_extend_a_helper(self):
        test = (
            "  const openCard = async card => {\n"
            "    // } a brace in a comment, and .cs-menu named only here\n"
            "    await click(card.querySelector(`.cs-card-${'}'}`))\n"
            "    await click('}')\n"
            "  }\n"
            "  const openMenu = async () => { await click('.cs-menu') }\n"
        )
        self.assertEqual(helpers_for(test, self.MENU), ["openMenu"])

    def test_the_harness_doubles_are_its_os_object_s_own_keys(self):
        harness = (
            "    os: { writeClipboard: async () => true, revealPath: async path => { scenario.revealed = path; "
            "return true }, openExternal: async () => true },\n"
        )
        self.assertEqual(
            scaffold_page_tests.object_keys(harness, "os"), ["writeClipboard", "revealPath", "openExternal"]
        )


if __name__ == "__main__":
    unittest.main()
