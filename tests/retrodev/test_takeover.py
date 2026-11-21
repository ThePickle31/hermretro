"""The trial rounds' regressions for this area (RoundEight, RoundFifteen, RoundSeven, RoundSeventeen, RoundSix, RoundTen, RoundTwelve, RoundTwenty), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_takeover
"""

from pathlib import Path
from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write
import retrodev
from tests.retrodev.fixture import retrodev_docs
import io
from retrodev import config, gates, output
import subprocess
from retrodev import state

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]


def line_with(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


AGENT = "Hermes, claude-opus-5-5"


def line_with_RoundSeven(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundSix(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundTen(text: str, start: str) -> str:
    return next((line for line in text.splitlines() if line.startswith(start)), "")


class Takeover(RepoCase):
    def pushed(self, branch: str) -> Path:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "tests/backend/library/test_extra.py", "EXTRA = 1\n")
        git(mate, "push", "-q", "origin", branch)
        return self.base / "hermretro-wt" / branch.partition("/")[2]

    def test_a_test_branch_keeps_its_name_and_plan_approve_there_writes_its_body(self):
        tree = self.pushed("test/extra")
        code, out = self.run_cli("takeover", "test/extra")
        self.assertEqual(code, 0, out)
        note = line_with(out, "note: 'test' is not one of this repository's kinds")
        self.assertIn("test/extra keeps its name: ship, land and CI accept any work branch", note)
        self.assertIn("so keep it", note)
        self.assertNotIn("git branch -m", note)  # a rename would strand the branch's retrodev record
        self.new_plan("extra")
        code, out = self.run_cli("plan", "approve", "extra", "--words", "start", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.main / "notes/pr/extra.md").is_file(), out)


class TakeoverAgent(RepoCase):
    def test_the_plan_approve_step_names_the_agent_while_it_is_unset(self):
        self.assertEqual(gates.agent_prefix({}), "RETRODEV_AGENT='<agent, model>' ")
        # round seventeen: a set variable is printed with its real value (the new process may not have it)
        self.assertEqual(gates.agent_prefix({"RETRODEV_AGENT": "Hermes, a model"}), "RETRODEV_AGENT='Hermes, a model' ")
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        approve = next(step for step in steps(out) if "plan approve" in step)
        self.assertIn(
            "when they say start: RETRODEV_AGENT='<agent, model>' python tools/retrodev plan approve", approve
        )
        note = next(part for part in retrodev_docs("README.md").split("\n\n") if part.startswith("`RETRODEV_AGENT="))
        self.assertIn("`takeover`", note)
        self.assertIn("`plan approve`", note)


class TakeoverRoundSeven(RepoCase):
    def pushed(self, retrodev_too: bool = False) -> Path:
        """feat/mate edits backend/library/core.py; dev then edits it too (and tools/retrodev, when asked)."""
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        self.on_dev("backend/library/core.py", "VALUE = 3\n")
        self.on_dev("docs/other.md", "# Other\n")
        if retrodev_too:
            self.on_dev("tools/retrodev/newer.py", "NEWER = 1\n")
        return self.base / "hermretro-wt" / "mate"

    def retrodev_copy(self, older: bool) -> None:
        """This checkout's real tools/retrodev into the test's main checkout (its policy kept): the older copy is the
        same code with sync.older always empty, as a retrodev from before the newer-runner steps was."""
        source = ROOT / "tools" / "retrodev"
        for path in source.rglob("*"):
            name = path.relative_to(source).as_posix()
            if path.is_file() and "__pycache__" not in name and name != "policy.toml":
                text = path.read_text()
                if older and name == "sync.py":
                    text = text.replace(
                        'def older(ctx, path) -> str:\n', 'def older(ctx, path) -> str:\n    return ""\n'
                    )
                write(self.main / "tools" / "retrodev", name, text)
        git(self.main, "add", "-A")
        git(self.main, "commit", "-q", "-m", "Older retrodev" if older else "Newer retrodev")
        git(self.main, "push", "-q", "origin", "dev")

    def test_the_files_dev_also_changed_are_read_before_the_plan(self):
        tree = self.pushed()
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        read = (
            "read `git diff HEAD...origin/dev -- backend/library/core.py` and `git log --oneline HEAD..origin/dev -- "
            "backend/library/core.py` before sync merges it (origin/dev changed these files of the branch too)"
        )
        self.assertEqual(steps[1], read)
        self.assertEqual(steps[2], "python tools/retrodev sync (HEAD lacks 2 commit(s) of origin/dev)")  # round 14
        self.assertTrue(steps[3].startswith("python tools/retrodev plan new mate"), steps)
        read = read.replace("before sync merges it", "before writing the plan")  # status's own wording
        code, out = self.run_cli("status", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertTrue(
            line_with_RoundSeven(out, "next: ").startswith(
                f"next: {read}, then python tools/retrodev sync (HEAD lacks 2 commit(s) of origin/dev), then "
                "python tools/retrodev plan new mate"
            ),
            out,
        )

    def test_plan_approve_and_status_after_takeover_also_sync_with_the_newer_retrodev(self):
        tree = self.pushed(retrodev_too=True)
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        sync = line_with_RoundSeven(
            out, f"next: python {self.main}/tools/retrodev sync (HEAD lacks 3 commit(s) of origin/dev; "
        )
        self.assertIn("this branch's own tools/retrodev is older than origin/dev's", sync, out)  # round seven's row
        runner = f"python {self.main}/tools/retrodev"
        newer = f"{runner} sync"
        self.new_plan("mate")
        code, out = self.run_cli("plan", "approve", "mate", "--words", "start")
        self.assertEqual(code, 0, out)
        self.assertIn(f"next: feat/mate already works under it: cd {tree} && {newer} (HEAD lacks 3", out)
        self.assertIn(f"origin/dev), then {runner} check\n", out)  # review 3, 1: every command, not only sync
        for where in (tree, self.main):  # the branch's own status, and the main checkout's list of every branch
            code, out = self.run_cli("status", cwd=where)
            self.assertEqual(code, 0, out)
            self.assertIn(f"commits ({newer})", out)
            self.assertIn(f"next: {newer} (HEAD lacks 3 commit(s) of origin/dev), then {runner} check", out)
            self.assertNotIn("python tools/retrodev ", out, out)  # review 3, 1: no older retrodev command at all
        code, out = self.run_cli("status", cwd=tree, as_json=True)
        self.assertEqual(out["sync"], newer, out)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)  # core.py conflicts: sync's own "sync again" too
        self.assertEqual(code, 1, out)
        self.assertIn(f"then {newer} again", out["error"]["fix"])
        code, out = self.run_cli("status", cwd=tree)
        self.assertIn(f", then {newer} (it rebuilds the generated files", out)

    def test_every_step_takeover_prints_for_an_older_branch_runs_the_newer_retrodev(self):  # review 3, 1
        def sh(command: str, cwd: Path) -> str:
            done = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 0, (command, done.stdout, done.stderr))
            return done.stdout

        self.retrodev_copy(older=True)
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        self.retrodev_copy(older=False)  # dev moves on: the main checkout's retrodev is the newer one
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "pull", "-q", "origin", "dev")
        runner = f"python {self.main}/tools/retrodev"
        out = sh(f"{runner} takeover feat/mate", self.main)
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        tree = self.base / "hermretro-wt" / "mate"
        self.assertEqual(steps[0], f"cd {tree}", out)
        self.assertEqual(len(steps), 5, steps)  # cd, sync, plan new, plan approve, check
        self.assertNotIn("python tools/retrodev ", out)
        self.assertIn('-> str:\n    return ""\n', (tree / "tools/retrodev/sync.py").read_text())  # its own is older
        for step in steps[1:]:
            command = step.partition("when they say start: ")[2] or step
            command = command.split(" (", 1)[0].replace("<their exact words>", "start")
            agent = "RETRODEV_AGENT='<agent, model>' "  # round 15: plan approve names the agent (start's step 3)
            self.assertTrue(command.removeprefix(agent).startswith(runner + " "), step)
            command = command.replace("<agent, model>", "Hermes, a test")
            done = sh(command, tree)  # verbatim, in the worktree the first step went to
            if " plan new " in command:
                (self.main / "notes/plans/mate.md").write_text(FILLED_PLAN.format(topic="mate"))
            if " plan approve " in command:  # sync ran first (round 14): nothing is left to merge
                approve = line_with_RoundSeven(done, "next: feat/mate already works under it: ")
                self.assertNotIn(" sync (HEAD lacks ", approve)
                self.assertTrue(approve.endswith(f" && {runner} check") or approve.endswith(" check"), approve)
        self.assertEqual(git(tree, "rev-list", "--count", "HEAD..origin/dev").strip(), "0")
        self.assertEqual(sh("python tools/retrodev status", tree).count(f"{runner} "), 0)  # synced: its own again


class TakeoverRecordsTheAgent(RepoCase):
    def test_plan_approve_without_the_variable_names_the_agent_takeover_saw(self):
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        self.fakes["env"] = {"RETRODEV_AGENT": AGENT}
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        approve = next(step for step in steps(out) if "plan approve" in step)
        self.assertIn(f"when they say start: RETRODEV_AGENT='{AGENT}' python tools/retrodev plan approve", approve)
        self.assertEqual(state.load_branch(self.main, "feat/mate")["agent"], AGENT)
        self.fakes["env"] = {}  # plan approve: a new process without the variable
        tree = self.base / "hermretro-wt" / "mate"
        self.new_plan("mate")
        code, out = self.run_cli("plan", "approve", "mate", "--words", "go ahead", cwd=tree)
        self.assertEqual(code, 0, out)
        body = (self.main / "notes" / "pr" / "mate.md").read_text()
        self.assertIn(f"Made by an agent ({AGENT})", body)
        self.assertNotIn("Made by an agent (Hermes)", body)

    def test_start_records_it_too_and_the_body_names_it(self):
        self.fakes["env"] = {"RETRODEV_AGENT": AGENT}
        code, out = self.run_cli("start", "docs/words", "--no-plan", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertEqual(state.load_branch(self.main, "docs/words")["agent"], AGENT)
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()), fakes={"env": {}})
        record = state.load_branch(self.main, "docs/words")
        self.assertIn(f"({AGENT})", gates.made_by(ctx, record=record))
        self.assertEqual(gates.agent_hint("Made by an agent (Hermes) for @x.", {}, record), "")


class TakeoverRoundSix(RepoCase):
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


class TakeoverRoundTwelve(RepoCase):
    def pushed(self, branch: str) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "docs/guide.md", "# Guide\n\nMore.\n")
        git(mate, "push", "-q", "origin", branch)

    def test_takeover_writes_the_body_from_the_template_and_names_its_absolute_path(self):
        self.pushed("docs/mate")
        code, out = self.run_cli("takeover", "docs/mate", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "mate.md"
        self.assertTrue(body.is_file(), out)
        self.assertIn("## What changed", body.read_text())
        self.assertIn(f"next: fill in {body} as you work", out)
        self.assertTrue(body.is_absolute())

    def test_a_branch_waiting_for_its_plan_gets_the_body_from_plan_approve(self):
        self.pushed("feat/mate")
        code, out = self.run_cli("takeover", "feat/mate", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "mate.md"
        self.assertFalse(body.exists(), "plan approve writes it, from the plan")
        self.assertIn(f"(it also writes the pull request body {body})", out)


class TakeoverAdvice(RepoCase):
    def pushed(self, retrodev_too: bool) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        if retrodev_too:
            self.on_dev("tools/retrodev/newer.py", "NEWER = 1\n")

    def test_the_plan_step_says_what_a_takeover_plan_holds_and_the_runner_step_how_long_it_lasts(self):
        self.pushed(retrodev_too=True)
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        plan = next(step for step in steps if " plan new mate " in step)
        self.assertIn("git log --oneline --no-merges origin/dev..HEAD", plan)
        self.assertIn("what is left for you, and that you took the branch over", plan)
        sync = next(step for step in steps if step.startswith(f"python {self.main}/tools/retrodev sync"))
        self.assertIn("every retrodev step until sync is done: then the worktree's own copy is current", sync)
