"""Friction the second round of fresh-agent trials found in ship --dry-run, status, the check budgets, the area
labels, the README and `new` (tool --module, event --when, the listener test, the test templates, the rpc and tab
next steps); each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_two
"""

import ast
import importlib.util
import io
import re
import shlex
import shutil
import unittest
from pathlib import Path

import retrodev
from retrodev import checks, config, output, repo, ship, state

from tests.retrodev.fixture import RepoCase, git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
TITLE = "Make the goalie work"
STANDARD = "  # noqa: E402 - the repository root goes on sys.path first"


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_dry_run_writes_the_skeleton_and_its_fix_names_the_real_title(self):
        tree = self.feat()
        code, out = self.run_cli("ship", "--title", TITLE, "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertIn("## Why\nMake goalie work.\n", path.read_text(), "the plan's Goal is the Why")
        self.assertIn(f"NO  body: fill in {path}", out)
        fix = line_with(out, "FIX: fill in")
        self.assertNotIn("--title ...", out)
        self.assertEqual(
            shlex.split(fix.split(", then ")[1]),
            [*["python", "tools/retrodev", "ship"], "--title", TITLE, "--body", str(path)],
        )
        self.assertIsNone(git(self.origin, "rev-parse", "-q", "--verify", "feat/goalie", check=False).strip() or None)

    def test_without_a_plan_the_why_is_a_visible_placeholder(self):
        tree = self.worktree("docs/tidy")  # --no-plan: the record names no plan
        self.commit(tree, "docs/guide.md", "# Tidier\n")
        self.passed(tree, "docs/tidy")
        code, out = self.run_cli("ship", "--title", "Tidy the guide", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        text = (self.main / "notes" / "pr" / "tidy.md").read_text()
        self.assertIn("## Why\n<!-- no plan: say why -->\n", text)
        self.assertNotIn("the plan's Goal is its Why", out)
        self.assertIn("no plan Goal: write the Why", out)

    def test_status_names_the_ship_with_its_body_and_how_far_dev_moved_on(self):
        tree = self.feat()
        self.run_cli("ship", "--title", TITLE, "--dry-run", cwd=tree)  # writes the body, records the title
        path = self.main / "notes" / "pr" / "goalie.md"
        _code, out = self.run_cli("status", cwd=tree)
        words = shlex.split(line_with(out, "next:").removeprefix("next: ").split(" (")[0])
        self.assertEqual(words, [*["python", "tools/retrodev", "ship"], "--title", TITLE, "--body", str(path)], out)
        self.assertNotIn("behind", out)
        self.on_dev("docs/other.md", "# Other\n")
        self.on_dev("docs/more.md", "# More\n")
        git(tree, "fetch", "-q", "origin")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("behind origin/dev: 2 commits (python tools/retrodev sync)", out)

    def test_the_first_real_ship_records_the_title_before_it_stops_and_reads_a_goals_heading(self):
        tree = self.feat("keeper")
        plan = self.main / "notes" / "plans" / "keeper.md"
        plan.write_text(plan.read_text().replace("## Goal\n", "## Goals\n"))
        code, out = self.run_cli("ship", "--title", TITLE, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("## Why\nMake keeper work.\n", (self.main / "notes" / "pr" / "keeper.md").read_text())
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(f"--title '{TITLE}' --body", line_with(out, "next:"), "the title given, not the plan's")

    def test_status_falls_back_to_the_plan_s_title(self):
        tree = self.feat("keeper")
        plan = self.main / "notes" / "plans" / "keeper.md"
        plan.write_text(plan.read_text().replace("# Plan: keeper", "# Plan: Keep the keeper in goal"))
        write(self.main, "notes/pr/keeper.md", "## Why\n")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("--title 'Keep the keeper in goal' --body", line_with(out, "next:"))

    def test_a_check_warns_only_on_the_second_run_over_budget(self):
        tree = self.worktree()
        policy = (tree / "tools/retrodev/policy.toml").read_text()
        policy = re.sub(r"(?m)^(fast_total|unit|lint|scan|default) = \d+$", r"\1 = 0.01", policy)
        self.commit(tree, "tools/retrodev/policy.toml", policy, "Tiny budgets")
        code, out = self.run_cli("check", "--again", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("warning:", out, "one run over budget says nothing")
        self.assertEqual(state.load_branch(self.main, "docs/tidy")["durations"]["unit"], 0.1)
        code, out = self.run_cli("check", "--again", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("warning: unit took 0.1 s, over its 0.01 s budget twice in a row", out)

    def test_the_budgets_are_measured_cold_runs_and_the_readme_agrees(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        budgets = ctx.policy["checks"]["budgets"]
        self.assertEqual((budgets["unit"], budgets["scaffold"], budgets["fast_total"]), (45, 30, 60))
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        self.assertIn("unit 45 s, scaffold 30 s, the fast checks together 60 s", readme)
        self.assertIn("over its budget twice in a row", readme)
        self.assertNotIn("Over twice its budget", readme)

    def test_github_community_files_are_documentation_not_ci(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        for name in ("CONTRIBUTING", "SECURITY", "CODE_OF_CONDUCT"):
            self.assertEqual(ship.labels(ctx, [f".github/{name}.md"]), ["documentation"], name)
        self.assertEqual(ship.labels(ctx, [".github/workflows/ci.yml"]), ["ci"])
        self.assertEqual(ship.labels(ctx, [".github/actions/hermes/action.yml"]), ["ci"])

    def test_the_readme_flow_covers_taking_over_a_teammate_s_branch(self):
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        flow = " ".join(readme.split("## Commands")[0].split())
        self.assertIn("Taking over a teammate's branch", flow)
        self.assertIn("`plan new <topic>` describing what the branch does", flow)
        self.assertIn(
            "`sync`, `check` and `ship` work in any checkout of the branch; only `start` and `land` need "
            "the main checkout on `dev`",
            flow,
        )


class NewKindsRoundTwo(ScaffoldCase):
    def test_a_tool_in_its_own_module_is_taken_in_by_tools_py(self):
        out = self.new("tool", "history", "rdprobe_mod", "--module", "rdprobe_extra")
        self.assertIn("backend/history/rdprobe_extra.py", out["created"])
        module = self.read("backend/history/rdprobe_extra.py")
        self.assertIn("Tool(RDPROBE_MOD_TOOL, rdprobe_mod_handler", module)
        index = self.read("backend/history/tools.py")
        tree = ast.parse(index)
        self.assertIn("from . import rdprobe_extra", index)
        tools = next(node for node in tree.body if isinstance(node, ast.Assign) and node.targets[0].id == "TOOLS")
        self.assertEqual([ast.unparse(elt) for elt in tools.value.elts], ["*rdprobe_extra.TOOLS"])
        self.assertIn("`chromatic_rdprobe_mod` (`backend/history/rdprobe_extra.py`)", self.read("docs/dev/CONTRACT.md"))
        self.new("tool", "history", "rdprobe_two", "--module", "rdprobe_extra")  # the same module again: once
        self.assertEqual(self.read("backend/history/tools.py").count("rdprobe_extra.TOOLS"), 1)
        self.assertEqual(self.read("backend/history/rdprobe_extra.py").count("Tool(RDPROBE_"), 2)
        out = self.new("tool", "history", "rdprobe_bad", "--module", "rpcs", code=1)
        self.assertIn("--module rpcs", out["error"]["message"])

    def test_module_refuses_a_name_tools_py_already_binds_and_nothing_changes(self):
        for name in ("__init__.py", "tools.py", "README.md"):
            shutil.copyfile(ROOT / "backend/library" / name, self.tree / "backend/library" / name)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Library tools")
        for module in ("json", "logger", "library"):  # a stdlib import, an assignment, `games as library`
            out = self.new("tool", "library", "rdprobe_ping", "--module", module, code=1)
            self.assertIn(f"backend/library/tools.py binds {module} already", out["error"]["message"])
            self.assertIn("--module", out["error"]["fix"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", f"--module {module} wrote something")
        self.new("tool", "library", "rdprobe_ping", "--module", "rdprobe_extra")  # a free name still works
        self.assertIn("from . import rdprobe_extra", self.read("backend/library/tools.py"))

    def test_a_plain_tool_after_an_aggregator_tools_py_goes_to_its_own_module(self):
        self.new("tool", "history", "rdprobe_first", "--module", "rdprobe_extra")
        out = self.new("tool", "history", "rdprobe_second", as_json=False)
        self.assertIn("the tool goes in its own module backend/history/rdprobe_second_tools.py", out)
        index = self.read("backend/history/tools.py")
        tools = next(n for n in ast.parse(index).body if isinstance(n, ast.Assign) and n.targets[0].id == "TOOLS")
        self.assertEqual(
            [ast.unparse(elt) for elt in tools.value.elts], ["*rdprobe_extra.TOOLS", "*rdprobe_second_tools.TOOLS"]
        )
        self.assertNotIn("def rdprobe_second_handler", index)
        self.assertIn(
            "Tool(RDPROBE_SECOND_TOOL, rdprobe_second_handler", self.read("backend/history/rdprobe_second_tools.py")
        )

    def test_an_event_says_when_lists_its_keys_and_sits_after_its_owner_s_rows(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        payload = "game=<id> (None without a project, or a list), root=<project>"
        out = self.new("event", "library", "rdprobe_moved", "--payload", payload, "--when", "a game moved folders")
        door = self.read("backend/library/__init__.py")
        self.assertIn(f'"library.rdprobe_moved": "a game moved folders; payload: {payload}"', door)
        self.assertNotIn("    # emits.", door, "no hint comment inside EVENTS")
        rows = [line for line in self.read("docs/dev/CONTRACT.md").splitlines() if line.startswith("| `")]
        mine = "| `library.rdprobe_moved` | `game`, `root` | a game moved folders | — |"
        self.assertIn(mine, rows)
        before = rows[rows.index(mine) - 1]
        self.assertTrue(before.startswith("| `library."), before)
        self.assertTrue(rows[rows.index(mine) + 1].startswith("| `setup."), "after the owner's last row only")
        self.assertIn('emit("library.rdprobe_moved", ...)', " ".join(out["next"]))

    def test_the_listener_test_uses_isolated_home_when_tests_support_has_it(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        self.new("listener", "rdprobe_ears", "library.build_reported")
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_library_build_reported.py")
        self.assertIn('mock.patch.object(host, "_data_dir", lambda: data)', test)
        self.assertIn('"HERMRETRO_HOME": home.name', test)
        self.assertNotIn("TODO", test)
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        self.new("listener", "rdprobe_ears", "library.game_presented")
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_library_game_presented.py")
        self.assertIn("from tests.support import isolated_home" + STANDARD, test)
        self.assertIn("        isolated_home(self)\n", test)

    def test_every_generated_test_gives_its_noqa_reason_and_imports_tests_support_as_a_package(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        for step in (
            ["feature", "rdprobe_all"],
            ["rpc", "rdprobe_all", "rdprobe_all_ping"],
            ["tool", "rdprobe_all", "rdprobe_all_ping"],
            ["event", "rdprobe_all", "pinged"],
            ["listener", "rdprobe_all", "library.build_reported"],
        ):
            self.new(*step)
        tests = sorted((self.tree / "tests/backend/rdprobe_all").glob("test_*.py"))
        self.assertEqual(len(tests), 5, tests)
        for path in tests:
            for line in path.read_text().splitlines():
                if "noqa: E402" in line:
                    self.assertTrue(line.endswith(STANDARD), f"{path.name}: {line}")
                if "sys.path.insert" in line:
                    self.assertEqual(line, "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))", path.name)
                if "support" in line and "import" in line:
                    self.assertTrue(line.startswith("from tests.support import "), f"{path.name}: {line}")
        spec = importlib.util.spec_from_file_location("check_py_round_two", ROOT / "tools" / "check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fix = module.scaffold_fix(["/usr/bin/python3", "-m", "unittest", "-v", "tests.retrodev.test_scaffold_tree"])
        self.assertTrue(fix.startswith("python -B -m unittest -v tests.retrodev.test_scaffold_tree"), fix)

    def test_rpc_next_steps_show_the_page_query_and_the_test_answer(self):
        out = self.new("rpc", "history", "rdprobe_recent")
        steps = " ".join(out["next"])
        self.assertIn(
            "useQuery({ queryKey: [ID, 'rdprobe_recent', viaProfile], queryFn: () => "
            "callStudio(RPC_RDPROBE_RECENT), enabled })",
            steps,
        )
        self.assertIn("scenario.rdprobe_recent = answered(", steps)
        studio = (ROOT / "page/app/studio-page.js").read_text()  # the names the snippet uses are the real ones
        self.assertIn("queryKey: [ID, 'games', viaProfile]", studio)
        self.assertIn("export async function callStudio(", (ROOT / "page/app/backend.js").read_text())
        self.assertIn("export const ID = ", (ROOT / "page/app/ids.js").read_text())
        self.assertIn("const answered = ", (ROOT / "tests/page/harness.mjs").read_text())
        self.assertIn("const key = options.queryKey[1]", (ROOT / "tests/page/sdk-stub.mjs").read_text())

    def test_tab_next_steps_name_the_file_that_defines_the_page_component(self):
        out = self.new("tab", "home", "rdprobe-extra")
        steps = " ".join(out["next"])
        self.assertIn("the page's own Page component (page/pages/home/index.js) still renders", steps)
        self.assertNotIn("home-page.js", steps, "Home's Page is the Home function in index.js")
        self.assertIn("a single tab still shows a tab bar", steps)


if __name__ == "__main__":
    unittest.main()
