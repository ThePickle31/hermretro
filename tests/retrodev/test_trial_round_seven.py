"""Friction the seventh round of fresh-agent trials found in the flow: a taken-over branch older than dev ran its
own copy of retrodev, whose sync lacked the 'dev removed this block' hint (sync's detection itself works in every
conflict style: Sync below pins that with real merges); takeover and status sent the agent to write the plan
without first reading what dev changed in the branch's own files; the body's Made-by line kept the template's
comment above it and named a GitHub owner a sandbox does not have; check's last line said 'fill in' without
saying what. The `new` kinds' fixes are in test_trial_round_seven_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_seven
"""

import ast
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace

import retrodev
from retrodev import ship, state

from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write
from tests.retrodev.test_trial_round_six import line_with

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
# The trial's case: dev moved _result_payload into the host module; the branch taught it to read bytes.
HOOKS = (
    '"""Hooks."""\n\nimport json\n\nfrom ..hermes import host\n\nlogger = host.logger\n\n\n'
    'def _result_payload(result):\n    """A tool result as the model saw it."""\n'
    "    if isinstance(result, str):\n        try:\n            result = json.loads(result)\n"
    "        except ValueError:\n            return None\n    return result if isinstance(result, dict) else None\n\n\n"
    "def build_succeeded(result) -> bool:\n    payload = _result_payload(result)\n    return bool(payload)\n"
)
BYTES = (
    "    if isinstance(result, (bytes, bytearray)):\n"
    '        result = bytes(result).decode("utf-8", "replace")\n    if isinstance(result, str):\n'
)
MOVED = HOOKS[: HOOKS.index("def _result_payload")] + HOOKS[HOOKS.index("def build_succeeded") :].replace(
    "_result_payload(result)", "host.tool_result_payload(result)"
)


class Sync(RepoCase):
    def test_a_function_dev_deleted_and_the_branch_edited_gets_the_hint_in_every_conflict_style(self):
        self.on_dev("backend/history/hooks.py", HOOKS, "Hooks")
        git(self.main, "fetch", "-q", "origin")
        trees = {}
        for style in ("merge", "diff3", "zdiff3"):
            trees[style] = self.worktree(f"fix/bytes-{style}")
            self.commit(
                trees[style], "backend/history/hooks.py", HOOKS.replace("    if isinstance(result, str):\n", BYTES)
            )
        self.on_dev("backend/history/hooks.py", MOVED, "Move _result_payload to host")
        for style, tree in trees.items():
            git(self.main, "config", "merge.conflictStyle", style)
            code, out = self.run_cli("sync", cwd=tree, as_json=True)
            self.assertEqual(code, 1, (style, out))
            self.assertIn(
                "backend/history/hooks.py: dev removed this block; if it moved, `git log -p origin/dev "
                "-S_result_payload -- page backend` finds where",
                out["error"]["fix"],
                style,
            )
            markers = (tree / "backend/history/hooks.py").read_text()
            self.assertEqual("|||||||" in markers, style != "merge", style)  # the style git really used
            git(tree, "merge", "--abort")


class Takeover(RepoCase):
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

    def test_the_files_dev_also_changed_are_read_before_the_plan(self):
        tree = self.pushed()
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        read = (
            "read `git diff HEAD...origin/dev -- backend/library/core.py` before writing the plan (origin/dev changed "
            "these files of the branch too)"
        )
        self.assertEqual(steps[1], read)
        self.assertTrue(steps[2].startswith("python tools/retrodev plan new mate"), steps)
        self.assertEqual(steps[4], "python tools/retrodev sync (HEAD lacks 2 commit(s) of origin/dev)")
        code, out = self.run_cli("status", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertTrue(
            line_with(out, "next: ").startswith(
                f"next: {read}, then python tools/retrodev sync (HEAD lacks 2 commit(s) of origin/dev), then "
                "python tools/retrodev plan new mate"
            ),
            out,
        )

    def test_a_branch_whose_retrodev_is_older_than_dev_s_syncs_with_the_main_checkout_s(self):
        self.pushed(retrodev_too=True)
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        sync = line_with(out, f"next: python {self.main}/tools/retrodev sync (HEAD lacks 3 commit(s) of origin/dev; ")
        self.assertIn("this branch's own tools/retrodev is older than origin/dev's", sync, out)

    def test_plan_approve_and_status_after_takeover_also_sync_with_the_newer_retrodev(self):
        tree = self.pushed(retrodev_too=True)
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
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
        self.assertEqual(len(steps), 5, steps)  # cd, plan new, plan approve, sync, check
        self.assertNotIn("python tools/retrodev ", out)
        self.assertIn('-> str:\n    return ""\n', (tree / "tools/retrodev/sync.py").read_text())  # its own is older
        for step in steps[1:]:
            command = step.partition("when they say start: ")[2] or step
            command = command.split(" (", 1)[0].replace("<their exact words>", "start")
            self.assertTrue(command.startswith(runner + " "), step)
            done = sh(command, tree)  # verbatim, in the worktree the first step went to
            if " plan new " in command:
                (self.main / "notes/plans/mate.md").write_text(FILLED_PLAN.format(topic="mate"))
            if " plan approve " in command:
                approve = line_with(done, "next: feat/mate already works under it: ")
                self.assertIn(f" && {runner} sync (HEAD lacks ", approve)
                self.assertTrue(approve.endswith(f"), then {runner} check"), approve)
                status = sh(f"{runner} status", tree)
                self.assertIn(f"next: {runner} sync (HEAD lacks ", status)
                self.assertNotIn("python tools/retrodev ", status)
                # the branch's own (older) plan approve would have printed the older sync: the case fixed here
                done = sh("python tools/retrodev plan approve mate --words start", tree)
                self.assertIn("&& python tools/retrodev sync (HEAD lacks ", done)
        self.assertEqual(git(tree, "rev-list", "--count", "HEAD..origin/dev").strip(), "0")
        self.assertEqual(sh("python tools/retrodev status", tree).count(f"{runner} "), 0)  # synced: its own again


class PlanApprove(RepoCase):
    def test_two_linked_worktrees_both_behind_dev_each_get_their_next_step(self):  # review 3, 0
        trees = [self.worktree(name) for name in ("feat/pair", "fix/pair-two")]
        record = state.load_branch(self.main, "fix/pair-two")
        state.save_branch(self.main, {**record, "plan": "pair"})  # as plan link records it
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")
        self.new_plan("pair")
        code, out = self.run_cli("plan", "approve", "pair", "--words", "start")
        self.assertEqual(code, 0, out)
        for branch, tree in zip(("feat/pair", "fix/pair-two"), trees, strict=True):
            self.assertIn(
                f"next: {branch} already works under it: cd {tree} && python tools/retrodev sync (HEAD lacks 1 "
                "commit(s) of origin/dev), then python tools/retrodev check",
                out,
            )

    def test_no_retrodev_function_binds_the_name_of_a_module_it_imports(self):  # review 3, 0: the same flaw anywhere
        found = []
        for path in sorted((ROOT / "tools" / "retrodev").rglob("*.py")):
            tree = ast.parse(path.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom):
                    imported |= {alias.asname or alias.name for alias in node.names}
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    continue
                for node in ast.walk(function):
                    bound = node.id if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) else None
                    bound = node.arg if isinstance(node, ast.arg) else bound
                    if bound in imported:
                        found.append(f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 0)}: {bound}")
        self.assertEqual(found, [], "a local named after an imported name hides it; FIX: rename the local")


class Body(RepoCase):
    def started(self) -> Path:
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie")
        self.assertEqual(code, 0, out)
        return self.base / "hermretro-wt" / "goalie"

    def test_the_made_by_line_replaces_the_template_s_comment_and_names_no_owner_without_github(self):
        self.started()
        body = (self.main / "notes/pr/goalie.md").read_text()
        self.assertTrue(body.endswith("## Made by\nMade by an agent for the owner.\n"), body)
        self.assertNotIn("A person: your name", body)
        github = SimpleNamespace(remote="gh", top=self.main)
        git(self.main, "remote", "add", "gh", "git@github.com:someone/hermretro.git")
        self.assertEqual(ship.made_by(github), "Made by an agent (Hermes) for @someone.")
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        self.assertIn("`Made by an agent for the owner.`", readme)
        self.assertIn("add the agent and model if known", readme)

    def test_check_names_the_sections_still_to_fill_in(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        path = self.main / "notes/pr/goalie.md"
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in How verified, Risk and rollback in {path}, then python tools/retrodev ship --title "
            "'<one plain sentence>'",
        )
        path.write_text(path.read_text().replace("## Risk and rollback\n", "## Risk and rollback\nLow.\n"))
        _code, out = self.run_cli("check", cwd=tree)
        self.assertTrue(out.strip().splitlines()[-1].startswith(f"next: fill in How verified in {path}, then"), out)


class QuickPath(unittest.TestCase):
    def test_the_readme_has_a_short_quick_path_under_the_flow_table(self):
        text = (ROOT / "tools/retrodev/README.md").read_text()
        table_end = text.index("| 8 summary |")
        block = text[table_end:].split("\n\n")[1]
        self.assertTrue(block.startswith("**Quick path**"), block)
        self.assertLessEqual(len(block.splitlines()), 10)
        for step in (
            "plan new",
            "plan approve",
            "start",
            "new ",
            "check.py fix",
            "check",
            "notes/pr/",
            "ship --dry-run",
        ):
            self.assertIn(step, block)


if __name__ == "__main__":
    unittest.main()
