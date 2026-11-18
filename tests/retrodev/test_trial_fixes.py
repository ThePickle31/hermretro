"""Friction the first round of fresh-agent trials found in plan, ship, status, doctor, config and check.py's lint
line; each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_fixes
"""

import importlib.util
import io
import re
import shlex
import types
import unittest
from pathlib import Path

import retrodev
from retrodev import checks, config, gates, output, release_publish, repo, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
APOSTROPHE = "Fix the game's title"
SECTIONS = ["Why", "What changed", "How verified", "Risk and rollback", "Not done"]
NOT_GITHUB = "none of the git remotes configured for this repository point to a known GitHub host"


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def ready(self, name="docs/tidy"):
        tree = self.worktree(name)
        self.commit(tree, "docs/guide.md", "# Guide, better\n", "Improve the guide")
        self.passed(tree, name)
        return tree, str(write(self.base, "body.md", GOOD_BODY))

    def test_plan_approve_refuses_a_plan_that_is_still_the_template(self):
        code, out = self.run_cli("plan", "new", "empty")
        self.assertIn("edit it in place", out)
        code, out = self.run_cli("plan", "approve", "empty", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("'## Goal'", out)
        self.assertTrue(line_with(out, "FIX:").startswith("FIX: fill in notes/plans/empty.md first"), out)
        self.assertIsNone(state.load_plan(self.main, "empty").get("approved"))
        self.new_plan("empty")  # written: now it may be approved
        self.assertEqual(self.run_cli("plan", "approve", "empty", "--words", "start")[0], 0)

    def test_printed_commands_survive_a_quote_in_the_title(self):
        tree, body = self.ready()
        code, data = self.run_cli("ship", "--title", APOSTROPHE, "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        code, out = self.run_cli("ship", "--title", APOSTROPHE, "--body", body, "--dry-run", cwd=tree)
        self.assertEqual(shlex.split(line_with(out, "gh pr")), data["gh"])
        self.assertEqual(shlex.split(line_with(out, "git push")), data["push"])
        record = state.load_branch(self.main, "docs/tidy")
        record.update(
            pr={"number": 5, "url": "u", "title": APOSTROPHE}, pushed="0" * 40, body=str(self.base / "a b.md")
        )
        state.save_branch(self.main, record)
        code, out = self.run_cli("status", cwd=tree)
        words = shlex.split(line_with(out, "next:").removeprefix("next: ").split(" (")[0])
        self.assertEqual(words[3:], ["--title", APOSTROPHE, "--body", str(self.base / "a b.md")], out)
        step = {"run": ["gh", "release", "create", "v1", "--title", "it's"], "env": {"X": "a b"}}
        self.assertEqual(shlex.split(release_publish.shown(step)), ["X=a b", *step["run"]])

    def test_ship_without_a_body_writes_the_skeleton_in_the_main_checkout_and_stops(self):
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        tree = self.worktree("feat/goalie")
        self.commit(tree, "docs/guide.md", "# Goal\n")
        self.passed(tree, "feat/goalie")
        code, out = self.run_cli("ship", "--title", APOSTROPHE, cwd=tree)
        self.assertEqual(code, 1, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertFalse((tree / "notes").exists(), "never in the worktree: gc would keep it")
        text = path.read_text()
        self.assertIn("## Why\nMake goalie work.\n", text)
        self.assertIn("Made by an agent (Hermes) for the owner.", text)
        fix = line_with(out, "FIX:")
        self.assertTrue(fix.startswith(f"FIX: fill in {path}, then python tools/retrodev ship --title"), fix)
        self.assertEqual(shlex.split(fix.split(", then ")[1])[-2:], ["--body", str(path)])
        self.assertEqual(self.run_cli("ship", "--title", "T", "--new-body", cwd=tree)[0], 1)
        self.assertEqual(path.read_text(), text, "an existing body is never overwritten")
        path.write_text(GOOD_BODY)  # filled in: --body defaults to it
        code, data = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertIn(str(path), data["gh"])

    def test_the_skeleton_s_attribution_fills_no_section(self):
        # Under the template's last heading the attribution once counted as that section's content.
        self.new_plan("credit")
        self.run_cli("plan", "approve", "credit", "--words", "start")
        tree = self.worktree("feat/credit")
        self.commit(tree, "docs/guide.md", "# Credit\n")
        path = self.main / "notes" / "pr" / "credit.md"
        real = (ROOT / ".github/pull_request_template.md").read_text()
        made_by = real.rstrip("\n") + "\n\n## Made by\n<!-- Which agent, for whom. -->\n"
        for template in (None, real, made_by):  # none (the policy's sections), the real one, one with '## Made by'
            if template is not None:
                self.commit(tree, ".github/pull_request_template.md", template, "Template")
            self.passed(tree, "feat/credit")
            path.unlink(missing_ok=True)
            self.assertEqual(self.run_cli("ship", "--title", "Credit", cwd=tree)[0], 1)
            text = path.read_text()
            self.assertEqual(text.count("Made by an agent (Hermes) for the owner."), 1, text)
            if template == made_by:
                self.assertIn("## Made by\n<!-- Which agent, for whom. -->\nMade by an agent", text)
            else:
                self.assertTrue(text.endswith("\n---\n\nMade by an agent (Hermes) for the owner.\n"), text)
            filled = re.sub(
                r"^## (Why|What changed|How verified|Risk and rollback)\n", r"\g<0>Filled.\n", text, flags=re.M
            )
            path.write_text(filled)
            code, data = self.run_cli("ship", "--title", "Credit", "--dry-run", cwd=tree, as_json=True)
            self.assertEqual(code, 1, (template, data))
            gate = next(gate for gate in data["gates"] if gate["name"] == "body")
            self.assertEqual(
                gate["message"].split(" (")[0], "section '## Not done' is empty", (template, gate["message"])
            )
            path.write_text(re.sub(r"^## Not done\n", "## Not done\nNothing.\n", filled, flags=re.M))
            code, data = self.run_cli("ship", "--title", "Credit", "--dry-run", cwd=tree, as_json=True)
            self.assertEqual(code, 0, (template, data))
        self.assertIn(
            "section '## Not done' is empty",
            "; ".join(gates.body_problems(GOOD_BODY.replace("Nothing.\n", ""), SECTIONS)),
        )
        self.assertEqual(gates.body_problems(GOOD_BODY, SECTIONS), [])

    def test_no_github_remote_is_a_note_not_gh_s_error(self):
        tree, body = self.ready()
        self.gh.answers[("pr", "list")] = (1, "", NOT_GITHUB)
        self.gh.answers[("pr", "checks")] = (1, "", NOT_GITHUB)
        code, out = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("note: no GitHub remote; the open pull request lookup was skipped", out)
        self.assertNotIn(NOT_GITHUB, out)
        record = state.load_branch(self.main, "docs/tidy")
        record["pr"] = {"number": 5, "url": "u"}
        state.save_branch(self.main, record)
        for command in ("status", "report"):
            code, out = self.run_cli(command, cwd=tree)
            self.assertIn("note: no GitHub remote", out, command)
            self.assertNotIn(NOT_GITHUB, out, command)

    def test_a_branch_that_changes_no_file_is_refused(self):
        tree, body = self.ready()
        git(tree, "revert", "--no-edit", "HEAD")
        self.passed(tree, "docs/tidy")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)
        gate = next(gate for gate in data["gates"] if gate["name"] == "has commits")
        self.assertIn("nothing to ship: the branch changes no file", gate["message"])

    def test_a_branch_that_undoes_itself_is_refused_while_dev_moves_on(self):
        # Its tree differs from origin/dev's tip only by dev's newer commit; from the merge base it changes nothing.
        tree, body = self.ready()
        git(tree, "revert", "--no-edit", "HEAD")
        self.on_dev("docs/other.md", "# Other\n")
        git(tree, "fetch", "-q", "origin")
        self.passed(tree, "docs/tidy")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)
        gate = next(gate for gate in data["gates"] if gate["name"] == "has commits")
        self.assertFalse(gate["ok"], gate)
        self.assertIn("nothing to ship: the branch changes no file", gate["message"])

    def test_a_missing_plan_says_none_written_and_plan_new(self):
        tree = self.worktree("feat/ghost")
        code, out = self.run_cli("status", cwd=tree)
        self.assertIn("plan:   ghost (none written)", out)
        self.assertIn("next: python tools/retrodev plan new ghost", out)

    def test_plan_approve_points_a_branch_made_by_hand_at_check(self):
        path = self.base / "hermretro-wt" / "handy"
        git(self.main, "worktree", "add", "-q", "-b", "fix/handy", str(path), "origin/dev")
        self.new_plan("handy")
        code, out = self.run_cli("plan", "approve", "handy", "--words", "start")
        self.assertEqual(code, 0, out)
        self.assertIn(f"next: fix/handy already works under it: cd {path} && python tools/retrodev check", out)

    def test_config_list_shows_where_the_worktrees_go(self):
        code, out = self.run_cli("config", "list")
        root = self.base / "hermretro-wt"
        self.assertIn(f"worktree_root = ''  (policy; resolves to {root})", out)

    def test_doctor_warns_when_the_main_checkout_is_off_dev(self):
        git(self.main, "switch", "-q", "-c", "elsewhere")
        _code, data = self.run_cli("doctor", as_json=True)
        row = next(row for row in data["items"] if row["name"] == "main checkout on the base branch")
        self.assertEqual((row["ok"], row["warning"]), (True, True))
        self.assertIn("only start and land need it", row["detail"])

    def test_the_lint_summary_names_each_page_warning(self):
        spec = importlib.util.spec_from_file_location("check_py_copy", ROOT / "tools" / "check.py")
        module = importlib.util.module_from_spec(spec)  # a private copy: rebinding its names touches no other test
        spec.loader.exec_module(module)
        lint = "warning: page/a.js:208:9  'x' is unused. [no-unused-vars]\n    why: ...\n3 files: 0 errors, 1 warnings"

        class Done:
            def __init__(self, text):
                self.text, self.returncode = text, 0

            def communicate(self):
                return self.text, None

        module.shutil = types.SimpleNamespace(which=lambda name: "/usr/bin/" + name)
        module.ruff_missing = lambda: None
        module.start = lambda command: Done(lint if "lint-page.mjs" in " ".join(command) else "")
        summary = module.check_lint(types.SimpleNamespace(strict=False))
        self.assertIn("page: 3 files: 0 errors, 1 warnings (warnings: page/a.js:208)", summary)


if __name__ == "__main__":
    unittest.main()
