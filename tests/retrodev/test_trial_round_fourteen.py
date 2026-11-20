"""Friction the fourteenth round of fresh-agent trials found: a tests/repo test that read the surrounding tree failed
only in CI's nested scaffold guard (`check` never ran it nested); the body's 'What changed' warning named bare file
names (`tools.py`) and runtime data files (`games.json`); a bare `config` was an error; takeover planned before
sync; sync's per-hunk steps were buried at the end of its FIX paragraph; `new rpc` left the RPC list of rpcs.py's
docstring stale; `new tab` on a tabless page did not say to turn its Page into a tab first, nor add the id to the
README's taken ones; `new slot` wrote props without backticks and `new contribution` left the host's Slots line to
the author; the page-test step pointed a Home slot at page-setup.test.mjs; the README had no worked tool example and
`new tool` did not quote the CONTRACT placeholder; the plan template did not say where a page's tests are named.
Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_fourteen
"""

import io
import os
import re
import shutil
from pathlib import Path

from retrodev import (
    body_names,
    checks,
    checks_triggers,
    config,
    output,
    plan,
    scaffold,
    scaffold_page_tests,
    scaffold_rpc,
)

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


class NestedScaffold(RepoCase):
    def checked(self, name: str, text: str, branch: str):
        tree = self.worktree(branch)
        self.commit(tree, name, text)
        code, out = self.run_cli("check", cwd=tree)
        scaffold = [entry for entry in self.check_log() if "scaffold" in entry.get("names", [])]
        return code, out, scaffold

    def test_a_repo_test_or_tests_support_adds_scaffold_run_nested_and_says_why(self):
        for name, branch in (("tests/repo/test_probe.py", "fix/probe"), ("tests/support.py", "fix/support")):
            with self.subTest(name=name):
                self.clear_log()
                code, out, scaffold = self.checked(name, "VALUE = 1\n", branch)
                self.assertEqual(code, 0, out)
                self.assertIn(f"adding scaffold: changed {name}; run nested (RD_SCAFFOLD_FULL=nested)", out)
                self.assertIn("as CI's page job runs those tests in its grown copy", out)
                self.assertEqual([entry.get("mode") for entry in scaffold], ["nested"])

    def test_the_page_harness_adds_it_nested_too(self):
        code, out, scaffold = self.checked("tests/page/harness.mjs", "export const x = 1\n", "fix/harness")
        self.assertIn("adding scaffold: changed tests/page/harness.mjs; run nested", out)
        self.assertEqual([entry.get("mode") for entry in scaffold], ["nested"])

    def test_other_branches_are_unchanged(self):
        code, out, scaffold = self.checked("backend/library/core.py", "VALUE = 2\n", "fix/core")
        self.assertNotIn("adding scaffold", out)
        self.assertEqual(scaffold, [])
        self.clear_log()
        code, out, scaffold = self.checked("tools/retrodev/scaffold_probe.py", "X = 1\n", "fix/scaffolds")
        self.assertIn("adding scaffold: changed tools/retrodev/scaffold_probe.py", out)
        self.assertNotIn("run nested", out)
        if os.environ.get("RD_SCAFFOLD_FULL") != "nested":  # the caller's own mode passes through
            self.assertNotEqual([entry.get("mode") for entry in scaffold], ["nested"])

    def test_a_fast_mode_pass_never_stands_for_the_nested_one_and_nested_has_its_own_budget(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        ids = {"a.py": "1"}
        fast = checks.input_digest(ctx, ids, "scaffold", "changed tools/retrodev/scaffold.py")
        deep = checks.input_digest(ctx, ids, "scaffold", "changed tests/support.py" + checks_triggers.NESTED)
        self.assertNotEqual(fast, deep)
        self.assertIn("scaffold_nested", ctx.policy["checks"]["budgets"])
        self.assertGreater(checks.budget(ctx, "scaffold_nested"), checks.budget(ctx, "scaffold"))
        rows = [{"name": "scaffold", "state": "ok", "seconds": 150.0, "cached": False, "budget": "scaffold_nested"}]
        self.assertEqual(checks.budget_warnings(ctx, rows, None, False, {"scaffold_nested": 150.0}), [])
        self.assertEqual(checks.durations(rows, None, {}), {"scaffold_nested": 150.0})


class BodyBareNames(RepoCase):
    def warning(self, what: str) -> str:
        tree = self.worktree("fix/core")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_bare_names_and_runtime_data_files_are_quiet_and_a_stale_repository_path_still_warns(self):
        said = self.warning(
            "- Changed `backend/library/core.py`; `tools.py` and `glue.py` call it unchanged.\n"
            "- The library reads `games.json` and `library.toml` at run time.\n"
            "- Moved the check into `backend/x/y.py`."
        )
        self.assertNotIn("`tools.py`", said)
        self.assertNotIn("`games.json`", said)
        self.assertNotIn("`library.toml`", said)
        self.assertIn("names the file(s) `backend/x/y.py`, which the", said)

    def test_only_paths_under_the_repository_s_top_folders_count(self):
        self.assertTrue(body_names.is_repo_path("backend/x/y.py"))
        self.assertTrue(body_names.is_repo_path(".github/workflows/ci.yml"))
        for word in ("games.json", "tools.py", "foo/bar.py", "/abs/path.py", "engine-ish"):
            with self.subTest(word=word):
                self.assertFalse(body_names.is_repo_path(word))


class ConfigDefault(RepoCase):
    def test_a_bare_config_lists_the_settings(self):
        code, out = self.run_cli("config")
        self.assertEqual(code, 0, out)
        root = line = next(line for line in out.splitlines() if line.startswith("worktree_root = "))
        self.assertIn("resolves to ", root)
        self.assertTrue(line.rstrip(")").endswith(str(self.main) + "-wt"), line)


class TakeoverOrder(RepoCase):
    def test_sync_comes_before_plan_new(self):
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        self.on_dev("backend/library/core.py", "VALUE = 3\n")
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        said = steps(out)
        sync = next(i for i, step in enumerate(said) if step.startswith("python tools/retrodev sync "))
        planned = next(i for i, step in enumerate(said) if step.startswith("python tools/retrodev plan new "))
        self.assertLess(sync, planned, said)
        self.assertIn("before sync merges it", said[1])


MOVING = "def moving_block():\n    return 2\n\n\nKEEP = 1\n"


class SyncHunkLines(RepoCase):
    def test_each_hunk_s_step_has_its_own_line_before_the_fix(self):
        name = "backend/library/moving.py"
        self.on_dev(name, MOVING, "A block")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/moved")
        self.commit(tree, name, MOVING.replace("return 2", "return 22"))
        self.on_dev(name, MOVING.replace("def moving_block():\n    return 2\n\n\n", ""))
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        lines = out.splitlines()
        hint = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
        fix = next(i for i, line in enumerate(lines) if line.startswith("FIX: "))
        self.assertLess(hint, fix, out)
        self.assertIn("dev deleted this block", lines[hint])
        self.assertNotIn("dev deleted this block", lines[fix])
        self.assertIn("first do what each hunk's line above says", lines[fix])
        git(tree, "merge", "--abort")


# Hermetic inputs: CI's nested scaffold guard runs this module in a copy of the tree that `new` has grown (setup
# has more tabs, home a slot), so these tests write the files they read instead of copying the surrounding ones.
SETUP_RPCS = '''"""The Setup page's RPCs: status, doctor, activity, studio_profile, install and remove_tools. Declared with
@rpc; registered in this order (backend/hermes/declare.py)."""

from __future__ import annotations

from ..hermes import host
from ..hermes.declare import rpc

logger = host.logger
''' + "".join(
    f'\n\n@rpc("{name}")\ndef rpc_{name}(ctx):\n    return lambda params, **_kwargs: {{"ok": True}}\n'
    for name in ("status", "doctor", "activity", "studio_profile", "install", "remove_tools")
)
README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""


class Scaffolds(ScaffoldCase):
    def real(self, *names: str) -> None:
        for name in names:
            (self.tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, self.tree / name)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def files(self, files: dict) -> None:
        for name, text in files.items():
            write(self.tree, name, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Known files")

    def readmes(self) -> None:
        taken = " (`install` and `onboarding` are taken: pick another id)"
        self.real("page/pages/setup/index.js")
        self.files(
            {
                "page/pages/home/README.md": README.format(Label="Home", page="home", taken=""),
                "page/pages/setup/README.md": README.format(Label="Setup", page="setup", taken=taken),
            }
        )

    def test_new_rpc_adds_its_name_to_the_docstring_s_rpc_list(self):
        self.real("backend/setup/__init__.py", "backend/setup/README.md")
        self.files({"backend/setup/rpcs.py": SETUP_RPCS})
        out = self.new("rpc", "setup", "rdfourteen_ping")
        doc = self.read("backend/setup/rpcs.py").split('"""')[1]
        self.assertIn("install, remove_tools and rdfourteen_ping.", " ".join(doc.split()))
        self.assertTrue(all(len(line) <= 120 for line in doc.split("\n")))
        self.assertIn("added `rdfourteen_ping` to the list of RPCs in backend/setup/rpcs.py's docstring", out["done"])

    def test_a_long_name_rewraps_the_docstring(self):
        said = scaffold_rpc.docstring_listed(SETUP_RPCS, "a_rather_long_rpc_name_for_wrapping")
        doc = said.split('"""')[1]
        self.assertIn("remove_tools and a_rather_long_rpc_name_for_wrapping.", " ".join(doc.split()))
        self.assertTrue(all(len(line) <= 117 for line in doc.split("\n")), doc)
        other = SETUP_RPCS.replace("status, doctor, activity, studio_profile, install and remove_tools", "the setup")
        self.assertIsNone(scaffold_rpc.docstring_listed(other, "x_y"))

    def test_new_tab_on_a_tabless_page_says_to_make_its_page_a_tab_first(self):
        out = self.new("tab", "home", "extra")
        self.assertTrue(
            out["next"][0].startswith(
                "this page has no tabs yet: run new tab home main --from-page first so its current content becomes "
                "a tab"
            ),
            out["next"],
        )
        out = self.new("tab", "home", "more")
        self.assertFalse(any(step.startswith("this page has no tabs yet") for step in out["next"]), out["next"])

    def test_new_tab_adds_its_id_to_the_readme_s_taken_ones(self):
        self.readmes()
        out = self.new("tab", "setup", "extra")
        self.assertIn(
            "(`install`, `onboarding` and `extra` are taken: pick another id)", self.read("page/pages/setup/README.md")
        )
        self.assertIn(
            "added `extra` to the taken tab ids in page/pages/setup/README.md 'Adding a tab here'", out["done"]
        )

    def test_new_slot_backticks_props_and_identifiers_and_wraps_at_120(self):
        self.readmes()
        doc = (
            "Below the quick start buttons, under the hero band, for the own extras of plugins. Props { ctx, game, "
            "hardwareOn }, plus go(pageId) on the page only"
        )
        self.new("slot", "home", "rdfourteenExtras", "--doc", doc)
        text = self.read("page/pages/home/README.md")
        block = text[text.index("**Slots:**") :].split("\n\n")[0]
        flat = " ".join(block.split())
        self.assertIn("Props `{ ctx, game, hardwareOn }`, plus `go(pageId)` on the page only", flat)
        self.assertTrue(all(len(line) <= 120 for line in block.split("\n")), block)

    def test_new_contribution_says_who_fills_the_slot_on_the_host_readme(self):
        self.readmes()
        self.new("slot", "home", "rdfourteenExtras", "--doc", "Below the hero. Props { ctx }")
        out = self.new("contribution", "setup", "home.rdfourteenExtras", "HeroNote")
        text = self.read("page/pages/home/README.md")
        block = " ".join(text[text.index("**Slots:**") :].split("\n\n")[0].split())
        self.assertIn("Props `{ ctx }`. Setup fills it with `HeroNote`.", block)
        self.assertFalse(any("**Slots:** line: say" in step for step in out["next"]), out["next"])
        self.assertTrue(any("page/pages/home/README.md **Slots:** line" in item for item in out["done"]), out)

    def test_a_home_slot_s_test_is_the_one_that_reaches_a_ready_home(self):
        self.files(
            {  # page-setup's shape: Home looked at during setup, more often; page-studio's: Home opened and used
                "tests/page/page-setup.test.mjs": "await tab('Home')\ncheck('a', () => {})\n" * 3,
                "tests/page/page-studio.test.mjs": "await tab('Home')\nscenario.calls.length = 0\nawait click('Use')\n",
                "tests/page/page-games.test.mjs": "await tab('Games')\n",
                "tests/page/page-other.test.mjs": "await tab('Games')\nawait click('Play')\n",
            }
        )
        plan = scaffold.Plan(self.tree)
        found = scaffold_page_tests.scenario_tests(plan, "home")
        self.assertEqual(found, ["tests/page/page-studio.test.mjs", "tests/page/page-setup.test.mjs"])
        self.assertEqual(scaffold_page_tests.scenario_tests(plan, "games")[0], "tests/page/page-games.test.mjs")

    def test_new_tool_quotes_the_contract_placeholder_with_its_line(self):
        out = self.new("tool", "history", "rdfourteen")
        contract = self.read("docs/dev/CONTRACT.md").split("\n")
        first = out["next"][0]
        found = re.search(
            r"in docs/dev/CONTRACT\.md:(\d+) replace 'say what it does and when the agent calls it' "
            r"after `chromatic_rdfourteen`",
            first,
        )
        self.assertTrue(found, first)
        self.assertIn("say what it does and when the agent calls it", contract[int(found.group(1)) - 1])


class Docs(RepoCase):
    def test_the_quick_path_has_a_worked_tool_example(self):
        readme = retrodev_docs("README.md")
        section = readme[readme.index("### Add a plugin tool") :]
        self.assertIn("python tools/retrodev new tool library probe --step", section)
        for edited in (
            "the handler module",
            "tests/backend/<feature>/test_tool_<name>.py",
            "docs/dev/CONTRACT.md:<line>",
        ):
            self.assertIn(edited, section)

    def test_the_plan_template_says_where_a_page_s_tests_are_named(self):
        tested = plan.TEMPLATE[plan.TEMPLATE.index("## How it is tested") :].split("##")[1]
        self.assertIn("each page README's Tests: line names the test file that covers it", " ".join(tested.split()))


if __name__ == "__main__":  # pragma: no cover
    import unittest

    unittest.main()
