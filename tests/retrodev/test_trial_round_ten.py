"""Friction the tenth round of fresh-agent trials found: agents looked for the plan and the body in the worktree
(takeover and status named them relative); plan approve left the plan saying draft; the Made by line without a
GitHub remote named no agent while the hint said it named Hermes, and dropped RETRODEV_AGENT; start under a plan
shared by several branches copied the whole plan's Goal, Not in scope and Title into the second branch's body. Each
test failed before its fix. `new`'s side is in test_trial_round_ten_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_ten
"""

import re
from pathlib import Path
from types import SimpleNamespace

from retrodev import gates, plan, ship, status

from tests.retrodev.fixture import FILLED_PLAN, GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]


def line_with(text: str, start: str) -> str:
    return next((line for line in text.splitlines() if line.startswith(start)), "")


class Paths(RepoCase):
    def pushed(self) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")

    def test_takeover_and_status_name_the_plan_by_its_path_in_the_main_checkout(self):
        self.pushed()
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        wanted = self.main / "notes" / "plans" / "mate.md"
        self.assertIn(f"python tools/retrodev plan new mate (writes {wanted}:", out)
        self.assertIn(f"next: show the owner {wanted}; when they say start", out)
        self.assertNotIn("show the owner notes/plans/", out)
        self.new_plan("mate")
        tree = self.base / "hermretro-wt" / "mate"
        code, out = self.run_cli("status", cwd=tree)
        self.assertIn(f"show the owner {wanted}; when they say start", out)
        self.assertNotIn("show the owner notes/plans/", out)

    def test_start_names_the_body_by_its_path_and_where_notes_live(self):
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "goalie.md"
        step = line_with(out, "next: ")
        self.assertIn(f"fill in {body} as you go: notes/ is in the main checkout, shared by every worktree", step)

    def test_status_without_a_body_names_its_full_path(self):
        facts = {
            "needs_plan": False,
            "checks_passed": True,
            "dirty": False,
            "topic": "t",
            "body_path": "/m/notes/pr/t.md",
        }
        self.assertIn("no body yet: ship writes /m/notes/pr/t.md from the template", status.next_step(facts))

    def test_the_readme_says_notes_is_in_the_main_checkout_and_to_recheck_what_changed(self):
        readme = retrodev_docs("README.md")
        self.assertIn("`notes/` is in the main checkout, shared by every worktree", readme)
        seven = line_with((ROOT / "tools/retrodev/README.md").read_text(), "7. ")
        self.assertIn("check What changed still matches the code; start copied it from the plan", seven)


class Approve(RepoCase):
    def test_plan_approve_rewrites_the_status_line_with_the_day_and_the_words(self):
        path = self.main / "notes/plans/stat.md"
        text = FILLED_PLAN.format(topic="stat").replace(
            "\n\n## Goal", "\n\nStatus: draft for the owner's approval.\n\n## Goal"
        )
        text += "\n## Notes\nStatus: a line in a section stays.\n"
        write(self.main, "notes/plans/stat.md", text)
        code, out = self.run_cli("plan", "approve", "stat", "--words", 'go  ahead\nwith it')
        self.assertEqual(code, 0, out)
        after = path.read_text()
        day = re.search(r'^Status: approved (\d{4}-\d{2}-\d{2}): "go ahead with it"$', after, re.M)
        self.assertIsNotNone(day, after)
        self.assertNotIn("draft for the owner's approval", after)
        self.assertIn("Status: a line in a section stays.", after)
        data: dict = self.run_cli("plan", "show", "stat", as_json=True)[1]
        self.assertFalse(data["changed_since_approval"], "the rewrite is part of what was approved")
        self.assertEqual(data["approved"]["at"][:10], day and day.group(1))
        self.assertIn("Status: draft for the owner's approval.", plan.TEMPLATE)


class MadeBy(RepoCase):
    def test_the_written_line_names_the_agent_and_agrees_with_the_hint(self):
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        body = (self.main / "notes/pr/goalie.md").read_text()
        self.assertTrue(body.endswith("## Made by\nMade by an agent (Hermes) for the owner.\n"), body)
        self.assertIn("names no agent but Hermes", out)  # the hint says what the line says
        ctx = SimpleNamespace(remote="origin", top=self.main)  # no GitHub remote
        named = gates.made_by(ctx, env={"RETRODEV_AGENT": "Hermes, claude-opus-5-5"})
        self.assertEqual(named, "Made by an agent (Hermes, claude-opus-5-5) for the owner.")
        filled = GOOD_BODY.replace("Made by an agent (Hermes) for the owner.", named)
        self.assertEqual(gates.body_problems(filled, ["Why", "What changed", "How verified", "Not done"]), [])
        self.assertEqual(gates.agent_hint(filled, env={}), "")
        self.assertEqual(gates.agent_hint(None, env={"RETRODEV_AGENT": "Codex"}), "")
        older = gates.agent_hint("Made by an agent for the owner.", env={})  # a body an older retrodev wrote
        self.assertIn("names no agent:", older)


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

    def ctx(self):
        from retrodev import config, output
        import io

        return config.Context.make(self.main, output.Out(stream=io.StringIO()))
