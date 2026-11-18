"""Printed commands quote their paths: with the main checkout and its worktrees under a folder whose name has a
space, every command retrodev prints for people to run (next steps, recovery hints, FIX lines) still works when it
is pasted into a shell. Each test runs the printed fragment through sh -c (up to the retrodev call, which needs this
checkout's tools) and checks what it did.

Run alone: python -m unittest tests.retrodev.test_quoted_paths
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

from retrodev import state

from tests.retrodev.fixture import RepoCase, git, parallel, write
from tests.retrodev.landing import PR, LandCase

load_tests = parallel
SPACED = "retrodev with spaces-"


def sh(command: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", "-c", command], cwd=cwd, capture_output=True, text=True, check=False)


def line_with(out: str, start: str) -> str:
    return next(line for line in out.splitlines() if line.startswith(start))


def before_retrodev(command: str) -> str:
    """The shell part of a printed command, without its python tools/retrodev call."""
    return command.split(" && python tools/retrodev", 1)[0]


class Spaced(RepoCase):
    prefix = SPACED

    def lands_in(self, fragment: str, where: Path, cwd: Path) -> None:
        """A `cd ...` fragment run by sh ends in ``where``."""
        done = sh(fragment + " && pwd", cwd)
        self.assertEqual((done.returncode, done.stderr), (0, ""), fragment)
        self.assertEqual(done.stdout.strip(), str(where), fragment)

    def under_plan(self, branch: str) -> Path:
        self.assertIn(" ", str(self.base))
        self.run_cli("plan", "new", "big")
        tree = self.worktree(branch)
        record = state.load_branch(self.main, branch)
        record["plan"] = "big"
        state.save_branch(self.main, record)
        return tree

    def test_plan_approve_cd_into_a_live_worktree(self):
        tree = self.under_plan("fix/part")
        code, out = self.run_cli("plan", "approve", "big", "--words", "start")
        self.assertEqual(code, 0, out)
        line = line_with(out, "next: fix/part")
        self.lands_in(before_retrodev(line[line.index("cd ") :]), tree, self.base)

    def test_plan_approve_restores_a_worktree_deleted_by_hand(self):
        tree = self.under_plan("fix/part")
        shutil.rmtree(tree)  # git still has it registered
        code, out = self.run_cli("plan", "approve", "big", "--words", "start")
        line = line_with(out, "next: fix/part")
        done = sh(before_retrodev(line[line.index("git worktree prune") :]) + " && pwd", self.main)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.splitlines()[-1], str(tree))
        self.assertEqual(git(tree, "branch", "--show-current").strip(), "fix/part")

    def status_hint(self) -> str:
        code, data = self.run_cli("status", as_json=True)
        self.assertEqual(code, 0, data)
        return next(row["next"] for row in data["branches"] if row["branch"] == "fix/part")

    def test_status_restores_a_worktree_deleted_by_hand_with_a_prune(self):
        tree = self.worktree("fix/part")
        shutil.rmtree(tree)
        hint = self.status_hint()
        self.assertIn("git worktree prune && git worktree add", hint)
        done = sh(before_retrodev(hint[hint.index("git worktree prune") :]) + " && pwd", self.main)
        self.assertEqual((done.returncode, done.stdout.splitlines()[-1]), (0, str(tree)), done.stderr)

    def test_status_restores_a_removed_worktree_where_start_puts_it(self):
        tree = self.worktree("fix/part")
        git(self.main, "worktree", "remove", str(tree))
        hint = self.status_hint()
        self.assertNotIn("prune", hint)
        done = sh(before_retrodev(hint[hint.index("git worktree add") :]) + " && pwd", self.main)
        self.assertEqual((done.returncode, done.stdout.splitlines()[-1]), (0, str(tree)), done.stderr)

    def test_start_says_where_to_cd_and_how_to_look_at_a_dirty_main_checkout(self):
        code, out = self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")
        self.assertEqual(code, 0, out)
        line = line_with(out, "next: cd ")
        self.lands_in(line[len("next: ") : line.index(", build")], self.base / "hermretro-wt" / "tidy", self.base)
        write(self.main, "docs/loose.md", "# Loose\n")
        code, out = self.run_cli("start", "docs/other", "--no-plan", "--no-setup")
        self.assertEqual(code, 3, out)  # the owner's changes
        done = sh(re.search(r"\((git -C .* status)\)", out).group(1) + " --short", self.base)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("docs/", done.stdout)

    def test_gc_move_out_command_moves_the_held_files(self):
        tree = self.worktree("docs/notes")
        self.commit(tree, "docs/notes.md", "# Notes\n")
        git(self.main, "push", "-q", "origin", "docs/notes")
        git(tree, "push", "-q", "origin", "HEAD:dev")  # merged
        write(tree, "notes/x.md", "the owner's notes\n")  # ignored data: gc keeps the worktree
        (self.main / "notes").mkdir(exist_ok=True)
        code, data = self.run_cli("gc", as_json=True)
        fix = next(row["fix"] for row in data["kept"] if row["branch"] == "docs/notes")
        move = re.search(r"notes/: (mv .*?)\), then", fix).group(1)
        done = sh(move, self.base)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.main / "notes" / "notes" / "x.md").is_file())


class SpacedLand(LandCase):
    prefix = SPACED

    def test_approve_and_status_cd_into_the_main_checkout(self):
        self.run_cli("plan", "new", "thing")  # feat/ needs an approved plan before status names land
        self.run_cli("plan", "approve", "thing", "--words", "start")
        tree = self.open_pr(approve=False)
        self.assertIn(" ", str(self.main))
        code, out = self.run_cli("approve", PR, "--words", "looks good, merge it")
        self.assertEqual(code, 0, out)
        line = line_with(out, "next: cd ")
        self.lands_in(before_retrodev(line[len("next: ") :]), self.main, tree)
        code, out = self.run_cli("status", cwd=tree)
        line = line_with(out, "next: cd ")
        self.lands_in(before_retrodev(line[len("next: ") :]), self.main, tree)

    def test_land_from_the_worktree_says_a_cd_that_works(self):
        tree = self.open_pr()
        code, out = self.run_cli("land", PR, "--ci-timeout", "0", "--no-review", cwd=tree)
        self.assertEqual(code, 0, out)
        moved = line_with(out, "your shell may still be in")
        self.lands_in(moved[moved.index("(removed): ") + len("(removed): ") :], self.main, self.base)
        line = line_with(out, "next: cd ")
        self.lands_in(before_retrodev(line[len("next: ") :]), self.main, self.base)

    lands_in = Spaced.lands_in


if __name__ == "__main__":
    unittest.main()
