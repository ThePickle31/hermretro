"""The trial rounds' regressions for this area (RoundTen, RoundTenReview), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_plan_shared
"""

from pathlib import Path
from retrodev import gates, ship
from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write
import io
from retrodev import config, output, state

load_tests = parallel

SHARED_PLAN = FILLED_PLAN.replace("Make {topic} work.", "Make {topic} work, in two pull requests.") + (
    "\n## duo-two\nThe second half: the tests for {topic}.\n"
)


class SharedPlan(RepoCase):
    def started(self, name: str, topic: str = "duo") -> str:
        code, out = self.run_cli("start", name, "--plan", topic, "--no-setup")
        self.assertEqual(code, 0, out)
        return (self.main / "notes" / "pr" / f"{name.partition('/')[2]}.md").read_text()

    def approved(self, text: str, topic: str = "duo") -> None:
        titled = text.replace("\n\n## Goal", "\n\nTitle: Make the whole duo work\n\n## Goal")
        write(self.main, f"notes/plans/{topic}.md", titled)
        code, out = self.run_cli("plan", "approve", topic, "--words", "start")
        self.assertEqual(code, 0, out)

    def ctx(self):
        from retrodev import config, output
        import io

        return config.Context.make(self.main, output.Out(stream=io.StringIO()))

    def test_a_second_branch_gets_no_goal_not_done_or_title_from_the_whole_plan(self):
        self.approved(FILLED_PLAN.format(topic="duo"))
        first = self.started("feat/duo-one")
        self.assertIn("## Why\nMake duo work.\n", first)  # the plan's first branch: its Goal is its Why
        second = self.started("feat/duo-three")
        self.assertNotIn("Make duo work.", second)
        self.assertIn("## Why\n" + ship.SHARED + "\n", second)
        self.assertNotIn("Nothing else.", second, "the whole plan's Not in scope is not this branch's Not done")
        self.assertIn("The code of duo.", second)  # What changed still comes from the plan (README step 7 rechecks it)
        record = {"branch": "feat/duo-three", "topic": "duo-three", "plan": "duo", "created": "9999"}
        self.assertIsNone(ship.plan_title(self.ctx(), "feat/duo-three", record))
        self.assertIn("the plan covers several branches", ship.title_note(self.ctx(), "feat/duo-three", record))
        problems = gates.body_problems(second, ["Why", "Not done"])
        self.assertEqual(problems[:2], ["section '## Why' is empty", "section '## Not done' is empty"])

    def test_the_branch_s_own_section_is_its_why(self):
        self.approved(SHARED_PLAN.format(topic="duo"))
        self.started("feat/duo-one")
        second = self.started("feat/duo-two")
        self.assertIn("## Why\nThe second half: the tests for duo.\n", second)
        self.assertNotIn("in two pull requests", second)

    def test_a_branches_list_of_several_shares_the_plan_from_its_first_branch(self):
        listed = FILLED_PLAN.format(topic="pair") + "\n## Branches\n- feat/pair-a\n- feat/pair-b\n"
        self.approved(listed, "pair")
        first = self.started("feat/pair-a", "pair")
        self.assertNotIn("Make pair work.", first)
        self.assertIn(ship.SHARED, first)


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
        state.drop_branch(self.main, name, self.ctx().policy["branches"]["no_plan"])
        self.assertFalse(any(r.get("branch") == name for r in state.branches(self.main)))

    def before_the_update(self) -> None:
        """What a record from before plans kept their branches leaves: the plan record has no branches map."""
        record = state.load_plan(self.main, "duo") or {}
        record.pop("branches", None)
        state.save_plan(self.main, record)

    def assert_second_shares(self) -> None:
        second = self.started("feat/duo-two")
        self.assertNotIn("Make duo work.", second)
        self.assertNotIn("Nothing else.", second, "the whole plan's Not in scope is not this branch's Not done")
        record = state.load_branch(self.main, "feat/duo-two")
        self.assertIsNone(ship.plan_title(self.ctx(), "feat/duo-two", record))

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

    def test_start_replacing_a_stale_record_from_before_the_update_keeps_its_time_in_the_plan(self):
        self.approved()
        self.started("feat/duo-one")
        self.before_the_update()
        old = state.load_branch(self.main, "feat/duo-one")
        state.save_branch(self.main, old | {"created": "2000-01-01T00:00:00+0000"})  # an older second than now()
        git(self.main, "worktree", "remove", "--force", old["worktree"])
        git(self.main, "branch", "-D", "feat/duo-one")  # by hand: the record stays behind
        self.started("feat/duo-one")
        self.assertEqual(
            (state.load_plan(self.main, "duo") or {})["branches"]["feat/duo-one"], "2000-01-01T00:00:00+0000"
        )

    def test_plan_link_moves_a_branch_off_its_old_plan(self):
        self.approved()
        write(self.main, "notes/plans/solo.md", FILLED_PLAN.format(topic="solo"))
        self.started("feat/duo-one")
        tree = Path(state.load_branch(self.main, "feat/duo-one")["worktree"])
        code, out = self.run_cli("plan", "link", "solo", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("feat/duo-one", (state.load_plan(self.main, "duo") or {}).get("branches", {}))
        self.assertIn("feat/duo-one", (state.load_plan(self.main, "solo") or {}).get("branches", {}))
