"""Friction the sixth round of fresh-agent trials found in the flow: the first ship --dry-run always stopped at the
body gate (start and plan approve now write the body from the plan, and check's last line says to fill it in),
plan approve's next step skipped sync, taking over a teammate's branch needed a hand-made worktree (takeover), and
sync's conflict FIX said nothing when dev removed or moved a block. Each test failed before its fix. The `new` kinds'
fixes are in test_trial_round_six_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_six
"""

import unittest
from pathlib import Path

import retrodev
from retrodev import status
from retrodev.gates import agent_hint  # the Made by hint after check's body line (round nine)

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
MOVING = "def keep():\n    return 1\n\n\ndef moving_block():\n    return 2\n\n\ndef tail():\n    return 3\n"


def line_with(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


class Body(RepoCase):
    def started(self, topic: str = "goalie") -> Path:
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        code, out = self.run_cli("start", f"feat/{topic}")
        self.assertEqual(code, 0, out)
        return self.base / "hermretro-wt" / topic

    def test_start_writes_the_body_from_the_plan_and_never_over_an_existing_one(self):
        self.started()
        body = (self.main / "notes" / "pr" / "goalie.md").read_text()
        self.assertIn("## Why\nMake goalie work.\n", body)
        self.assertIn("## What changed\nThe code of goalie.\n", body)
        self.assertIn("## Not done\nNothing else.\n", body)
        self.assertIn(
            "Made by an agent (Hermes) for the owner.", body
        )  # no GitHub remote (flipped in rounds seven, ten)
        write(self.main, "notes/pr/keeper.md", "## Why\nMine.\n")
        self.started("keeper")
        self.assertEqual((self.main / "notes" / "pr" / "keeper.md").read_text(), "## Why\nMine.\n")

    def test_the_first_dry_run_checks_that_body_and_still_refuses_what_the_plan_did_not_fill(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        self.run_cli("check", cwd=tree)
        code, out = self.run_cli("ship", "--title", "Keep the goalie in goal", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        refused = line_with(out, "  NO  body")
        self.assertIn("'## How verified' is empty", refused)
        self.assertIn("'## Risk and rollback' is empty", refused)
        self.assertNotIn("'## What changed' is empty", refused)
        self.assertNotIn("written now", refused, "the body was there before the first ship")
        self.assertNotIn("wrote ", out)

    def test_check_s_last_line_says_to_fill_in_the_body_until_it_passes_the_body_gate(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        last = out.strip().splitlines()[-1]
        path = self.main / "notes" / "pr" / "goalie.md"
        # flipped in round seven: it names the sections still empty
        unfilled = "How verified, Risk and rollback"
        self.assertEqual(
            last,
            f"next: fill in {unfilled} in {path}, then python tools/retrodev ship --title '<one plain sentence>'"
            + agent_hint(None),
        )
        path.write_text(GOOD_BODY)
        _code, out = self.run_cli("check", cwd=tree)
        self.assertNotIn("next: fill in", out)

    def test_check_after_a_refused_dry_run_keeps_the_dry_run_in_its_ship(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        code, out = self.run_cli("ship", "--title", "Keep the goalie in goal", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in How verified, Risk and rollback in {path}, then python tools/retrodev ship --title 'Keep the "
            "goalie in goal' --dry-run" + agent_hint(None),
        )

    def test_plan_approve_inside_its_branch_writes_the_body_too(self):
        tree = self.worktree("feat/keeper")
        self.new_plan("keeper")
        code, out = self.run_cli("plan", "approve", "keeper", "--words", "start", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("## What changed\nThe code of keeper.\n", (self.main / "notes/pr/keeper.md").read_text())
        self.worktree("feat/other")
        self.new_plan("unrelated")
        self.run_cli("plan", "approve", "unrelated", "--words", "start", cwd=self.base / "hermretro-wt" / "other")
        self.assertFalse((self.main / "notes/pr/other.md").exists(), "a plan the branch does not work under")

    def test_the_docs_and_status_say_start_writes_the_body_and_ship_only_when_it_is_missing(self):
        # Review round 2: the quick flow still said the first ship writes the body and stops.
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        build = line_with(readme, "| 4 build |")
        self.assertIn("`start`, or `plan approve` inside the linked branch, writes it", build)
        self.assertIn("`ship` writes it only when it is missing", build)
        for text in (readme, (ROOT / "tools/retrodev/ship.py").read_text()):
            self.assertNotIn("the first one writes the body", text)
            self.assertNotIn("first ship writes the body", text)

        step = status.next_step({"needs_plan": False, "checks_passed": True, "dirty": False, "topic": "t"})
        self.assertNotIn("first ship writes", step)
        self.assertIn("no body yet: ship writes notes/pr/t.md from the template when it is missing", step)


class PlanApprove(RepoCase):
    def test_a_branch_behind_dev_syncs_before_check(self):
        tree = self.worktree("feat/goalie")
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")
        self.new_plan("goalie")
        _code, out = self.run_cli("plan", "approve", "goalie", "--words", "start")
        self.assertIn(
            f"next: feat/goalie already works under it: cd {tree} && python tools/retrodev sync (HEAD lacks 1 "
            "commit(s) of origin/dev), then python tools/retrodev check",
            out,
        )


class Takeover(RepoCase):
    def pushed(self, branch: str) -> None:
        """A teammate's branch, pushed from their own clone; dev moves on after it."""
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "docs/mate.md", "# Theirs\n")
        git(mate, "push", "-q", "origin", branch)
        self.on_dev("docs/other.md", "# Other\n")

    def test_takeover_makes_a_tracking_worktree_sets_it_up_and_names_the_next_steps(self):
        self.pushed("feat/mate")
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        tree = self.base / "hermretro-wt" / "mate"
        self.assertEqual((tree / "docs/mate.md").read_text(), "# Theirs\n")
        self.assertEqual(git(tree, "rev-parse", "--abbrev-ref", "feat/mate@{upstream}").strip(), "origin/feat/mate")
        self.assertIn("ok  ", out)  # start's setup ran there (the fixture's stand-in prints 'set up')
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        self.assertEqual(steps[0], f"cd {tree}")
        self.assertEqual(steps[1], "python tools/retrodev sync (HEAD lacks 1 commit(s) of origin/dev)")  # round 14
        self.assertTrue(steps[2].startswith("python tools/retrodev plan new mate"), steps)
        self.assertIn("python tools/retrodev plan approve mate", steps[3])
        self.assertEqual(steps[4], "python tools/retrodev check")
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 1, out)
        self.assertIn("a local feat/mate exists already", out)

    def test_a_pushed_name_no_record_can_take_is_refused_before_anything_is_made(self):
        self.pushed("feat/Trial")
        code, out = self.run_cli("takeover", "feat/Trial")
        self.assertEqual(code, 1, out)
        self.assertIn("'feat/Trial' cannot name a retrodev record", out)
        self.assertIn("feat/trial", out)
        self.assertFalse(git(self.main, "branch", "--list", "feat/Trial").strip(), "a local branch was made")
        self.assertFalse((self.base / "hermretro-wt" / "Trial").exists(), "a worktree was made")
        self.assertNotIn("Trial", git(self.main, "worktree", "list"))

    def test_a_branch_that_was_never_pushed_is_refused(self):
        code, out = self.run_cli("takeover", "feat/nobody")
        self.assertEqual(code, 1, out)
        self.assertIn("origin/feat/nobody does not exist after the fetch", out)

    def test_the_readme_takes_over_with_the_command(self):
        text = retrodev_docs("REFERENCE.md")
        section = text[text.index("**Taking over a teammate's branch**") :].split("\n\n")[0]
        self.assertIn("python tools/retrodev takeover", section)
        self.assertNotIn("<root>", section)


class Sync(RepoCase):
    def test_a_hunk_dev_removed_gets_the_git_log_hint(self):
        self.on_dev("backend/library/moving.py", MOVING, "A block that will move")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/moved")
        self.commit(tree, "backend/library/moving.py", MOVING.replace("return 2", "return 22"))
        self.on_dev("backend/library/moving.py", MOVING.replace("def moving_block():\n    return 2\n\n\n", ""))
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "backend/library/moving.py:5-11: dev deleted this block (no other file on origin/dev has its lines; if it "
            "moved and changed, `git log -p origin/dev '-Sdef moving_block():'` finds where); delete the HEAD side of "
            "this hunk, git add, sync again",
            out["error"]["message"],
        )


if __name__ == "__main__":
    unittest.main()
