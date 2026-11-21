"""Friction the third round of fresh-agent trials found in status (the body clause, behind dev, docs/chore plans),
plan approve, check (the clean install on uncommitted changes, scaffold on a tree that fails lint) and `new` (the
agent-half row, --dry-run's diff, the listener, tool --project and rpc next steps); each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_three
"""

import ast
import json
import shutil
import unittest
from pathlib import Path

import retrodev
from retrodev import state

from tests.retrodev import test_trial_round_two as two
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase
from tests.retrodev.test_trial_round_two import TITLE, line_with

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]


class Status(two.Flow):  # its helpers (two.Flow's own tests run in test_trial_round_two)
    def test_a_filled_body_drops_the_fill_in_clause_and_a_passing_dry_run_is_named(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", "--json", cwd=tree)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("fill in every section", line_with(out, "next:"), out)
        self.assertIn("ship --dry-run passed at ", line_with(out, "next:"), out)
        write(tree, "docs/guide.md", "# changed\n")  # another tree: that dry run no longer speaks for it
        git(tree, "commit", "-qam", "More")
        self.passed(tree, "feat/goalie")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)

    def test_a_body_emptied_after_a_passing_dry_run_says_fill_it_in(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        body.write_text(GOOD_BODY.replace("Because.", ""))  # the tree is the same; only the body changed
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(fill in every section of the body first)", line_with(out, "next:"), out)
        self.assertNotIn("dry-run passed", out)
        body.write_text(GOOD_BODY.replace("Things.", "Other things."))  # filled in, but not the body that passed
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)

    def test_a_dry_run_stopped_by_the_base_gate_is_recorded_as_failed(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        answer = [{"number": 12, "url": "u", "baseRefName": "main"}]  # opened by hand into main
        self.gh.answers[("pr", "list")] = (0, json.dumps(answer), "")
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("into main", out)
        self.assertFalse(state.load_branch(self.main, "feat/goalie")["dry_run"]["ok"])
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("dry-run passed", out)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)

    def test_an_unfilled_body_still_says_fill_it_in(self):
        tree = self.feat()
        self.run_cli("ship", "--title", TITLE, "--dry-run", cwd=tree)  # writes the skeleton
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(fill in every section of the body first)", line_with(out, "next:"), out)

    def test_behind_origin_dev_names_sync_in_a_worktree_and_in_the_main_checkout(self):
        tree = self.worktree("docs/tidy")
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")  # the cached ref moves; status itself never fetches
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("behind origin/dev: 1 commits (python tools/retrodev sync)", out)
        self.assertTrue(line_with(out, "next:").startswith("next: python tools/retrodev sync"), out)
        _code, out = self.run_cli("status", cwd=self.main)
        self.assertIn("behind origin/dev: 1 commits (python tools/retrodev sync)", out)
        self.assertIn("next: python tools/retrodev sync", out)
        write(tree, "docs/guide.md", "# dirty\n")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("git commit", line_with(out, "next:"))
        self.assertIn("then python tools/retrodev sync", line_with(out, "next:"))

    def test_behind_origin_dev_on_a_branch_in_the_main_checkout(self):
        git(self.main, "switch", "-q", "-c", "docs/here")
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")
        _code, out = self.run_cli("status", cwd=self.main)
        self.assertIn("behind origin/dev: 1 commits", out)
        self.assertIn("python tools/retrodev sync", line_with(out, "next:"))

    def test_docs_and_chore_without_a_plan_need_none(self):
        for name in ("docs/tidy", "chore/sweep"):
            tree = self.worktree(name)
            _code, out = self.run_cli("status", cwd=tree)
            self.assertIn("plan:   none needed (docs/chore)", out)
            self.assertNotIn("plan new", out)
            self.assertNotIn("none written", out)


class Approve(RepoCase):
    def test_plan_approve_names_every_kind_and_what_chore_is_for(self):
        self.new_plan("alone")
        _code, out = self.run_cli("plan", "approve", "alone", "--words", "start")
        line = line_with(out, "next:")
        self.assertIn("start <kind>/alone", line)
        for kind in ("feat", "fix", "docs", "chore"):
            self.assertIn(kind, line)
        self.assertIn("chore (refactors that change no behaviour)", line)
        self.assertNotIn("start feat/alone", line)


class Check(RepoCase):
    def test_the_clean_install_on_uncommitted_changes_is_refused_before_anything_runs(self):
        tree = self.worktree("chore/glue")
        self.commit(tree, "backend/hermes/glue.py", "GLUE = 2\n")
        write(tree, "docs/guide.md", "# not committed\n")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertEqual(self.check_log(), [], "nothing ran")
        self.assertIn("FIX: commit first: the clean install installs the committed tree", out)

    def test_scaffold_on_a_tree_that_fails_lint_is_skipped_not_a_rerun_fix(self):
        tree = self.worktree("chore/lint")
        self.fail_checks("lint", "scaffold")
        code, out = self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails lint (fix lint first)", out)
        self.assertNotIn("FIX: fix scaffold", out)
        self.assertIn("FIX: fix lint", out)
        code, out = self.run_cli("check", "scaffold", cwd=tree)  # lint's recorded failure, on these very inputs
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails lint (fix lint first)", out)
        self.assertNotIn("FIX: fix scaffold", out)
        self.fail_checks("scaffold")
        self.run_cli("check", "lint", cwd=tree)
        _code, out = self.run_cli("check", "scaffold", cwd=tree)  # lint passes now: scaffold's own failure shows
        self.assertIn("FIX: fix scaffold", out)


class New(ScaffoldCase):
    def test_a_feature_s_agent_half_row_goes_in_the_feature_table(self):
        path = self.tree / "docs/dev/ARCHITECTURE.md"
        text = path.read_text()
        other = "\n| Module | Why |\n|---|---|\n| `backend/hermes/contracts.py` | pinned contracts |\n"
        at = text.index("`__init__.register()` collects")
        path.write_text(text[:at] + other.lstrip("\n") + "\n" + text[at:])
        git(self.tree, "commit", "-qam", "Another table")
        last = last_feature_row(path.read_text())  # whatever row ends the table now (a branch may have added one)
        self.new("feature", "rdprobe")
        lines = path.read_text().splitlines()
        mine = lines.index("| `backend/rdprobe/` | nothing yet | nothing; no events |")
        self.assertEqual(lines[mine - 1], last)
        self.assertEqual(lines[mine + 1], "")
        self.assertEqual(lines.count("| `backend/rdprobe/` | nothing yet | nothing; no events |"), 1)

    def test_dry_run_prints_the_diff_of_every_file(self):
        out = self.new("feature", "rdprobe", "--dry-run")
        diff = out["diff"]
        self.assertIn("--- /dev/null\n+++ b/backend/rdprobe/__init__.py\n", diff)
        self.assertIn("--- a/backend/features.py\n+++ b/backend/features.py\n", diff)
        self.assertIn('+    "rdprobe",', diff)
        self.assertIn("+++ b/docs/dev/ARCHITECTURE.md", diff)
        text = self.new("feature", "rdprobe", "--dry-run", as_json=False)
        self.assertIn("+++ b/tools/layout.toml", text)
        self.assertFalse((self.tree / "backend/rdprobe").exists())

    def test_a_change_the_clean_install_covers_says_commit_then_check_then_ship(self):
        out = self.new("feature", "rdprobe", as_json=False)
        then = line_with(out, "then:")
        self.assertLess(then.index("commit"), then.index("retrodev check"))
        self.assertLess(then.index("retrodev check"), then.index("retrodev ship"))
        out = self.new("tab", "build", "rdprobe-extra", as_json=False)  # not itself, but the branch's feature is
        then = line_with(out, "then:")
        self.assertLess(then.index("commit"), then.index("retrodev check"), "the branch, not just this scaffold")
        self.assertLess(then.index("retrodev check"), then.index("retrodev ship"))
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Feature and tab")  # committed, the branch still changes what it covers
        out = self.new("rpc", "rdprobe", "rdprobe_recent", as_json=False)
        then = line_with(out, "then:")
        self.assertLess(then.index("commit"), then.index("retrodev check"))

    def test_a_branch_the_clean_install_does_not_cover_says_check_then_commit(self):
        git(self.tree, "update-ref", "refs/remotes/origin/dev", "HEAD")  # the real files are dev's own here
        out = self.new("tab", "build", "rdprobe-extra", as_json=False)
        self.assertEqual(
            line_with(out, "then:"), "then: python tools/retrodev check, commit, python tools/retrodev ship"
        )

    def test_listener_next_steps_name_the_placeholders_and_the_emitter_s_tests(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        steps = " ".join(self.new("listener", "rdprobe_ears", "library.build_reported")["next"])
        self.assertIn("'rdprobe_ears (say what it does)'", steps)
        self.assertIn("'say what this listener does'", steps)
        self.assertIn("grep -rn 'emit(\"library.build_reported\"' backend tests", steps)
        self.assertIn("isolated_home(self)", steps)

    def test_rpc_next_steps_say_when_to_set_the_scenario_and_what_each_call_resolves_to(self):
        steps = " ".join(self.new("rpc", "history", "rdprobe_recent")["next"])
        self.assertIn("set before the page renders", steps)
        self.assertNotIn("enabled", steps)  # round nine: a page's query, as a page writes it (no enabled)
        self.assertIn("callStudio and callStudioOnly resolve to the RPC's answer itself", steps)
        self.assertIn("callBackend resolves to { data }", steps)
        backend = (ROOT / "page/app/backend.js").read_text()  # what the hint claims, in the real page
        self.assertIn("return { data: await host.requestProfile(", backend)
        studio = backend[backend.index("export async function callStudio(") :].split("\n}")[0]
        self.assertNotIn("data:", studio)


def last_feature_row(text: str) -> str:
    """The last `backend/` row of "The agent half"'s feature table (the one starting '| Feature | Declares |')."""
    lines = text.split("## The agent half", 1)[1].split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("| Feature | Declares |"))
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return [line for line in lines[start:end] if line.startswith("| `backend/")][-1]


class ToolProject(ScaffoldCase):
    def setUp(self):
        super().setUp()
        self.new("feature", "rdprobe_lib")
        write(self.tree, "backend/rdprobe_lib/tool_args.py", (ROOT / "backend/library/tool_args.py").read_text())
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "A feature with tool_args")

    def test_a_feature_with_tool_args_gets_a_project_tool_by_default(self):
        self.new("tool", "rdprobe_lib", "rdprobe_open")
        source = self.read("backend/rdprobe_lib/tools.py")
        self.assertIn("from .tool_args import tool_error, tool_project", source)
        self.assertIn('root, error = tool_project("chromatic_rdprobe_open", args, kwargs)', source)
        self.assertIn('"project": {', source)
        self.assertIn('return tool_error(f"{type(error).__name__}: {error}", "ADAPTER_ERROR")', source)
        ast.parse(source)
        test = self.read("tests/backend/rdprobe_lib/test_tool_rdprobe_open.py")
        self.assertIn("        self.home = isolated_home(self)\n", test)
        self.assertIn('"PROJECT_NOT_FOUND"', test)
        self.new("tool", "rdprobe_lib", "rdprobe_plain", "--no-project")
        self.assertNotIn('tool_project("chromatic_rdprobe_plain"', self.read("backend/rdprobe_lib/tools.py"))

    def test_project_is_refused_without_tool_args(self):
        out = self.new("tool", "history", "rdprobe_open", "--project", code=1)
        self.assertIn("tool_args.py", out["error"]["message"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_a_tool_in_a_sibling_module_names_that_module_on_the_readme_tools_line(self):
        self.new("tool", "rdprobe_lib", "rdprobe_far", "--module", "far_tools")
        readme = self.read("backend/rdprobe_lib/README.md")
        self.assertIn("- Tools (`tools.py`, `far_tools.py`): `chromatic_rdprobe_far`.", readme)
        self.assertIn("from .tool_args import tool_error, tool_project", self.read("backend/rdprobe_lib/far_tools.py"))


if __name__ == "__main__":
    unittest.main()
