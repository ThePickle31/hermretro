"""Friction the fifth round of fresh-agent trials found: tests that pinned the real tree's content (the guard is in
test_scaffold_tree.py), the scaffold check's trigger and new's own checks, `new tab --from-page` on a Page defined
in index.js, the listener's README entry and docstring, the event's EVENTS payload, the slot's README line, the rpc
test template, status behind dev without a plan, and ship's gates without a title. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_five
"""

import importlib.util
import io
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import retrodev
from retrodev import cli, config, output, scaffold

from tests.retrodev import test_scaffold_tree as tree_test
from tests.retrodev.fixture import RepoCase, git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
OWN = "page/pages/rdprobe-own"


def inline_page(case, page_id: str = "rdprobe-own") -> None:
    """A probe page whose index.js defines its own Page (as home and prompts do), committed."""
    name = "".join(part.title() for part in page_id.split("-"))
    write(
        case.tree,
        f"page/pages/{page_id}/index.js",
        f"// {name}: a probe page.\nimport {{ jsx }} from '#sdk'\nimport {{ Lede }} from '#shared/ui/text.js'\n"
        f"import {{ PROBE_CSS }} from './probe.css.js'\n\n/** Its own Page. */\nfunction {name}({{ shell }}) {{\n"
        f"  return jsx(Lede, {{ children: shell.label }})\n}}\n\nexport const {page_id.upper().replace('-', '_')}_PAGE = {{\n"
        f"  id: '{page_id}',\n  label: '{name}',\n  Page: {name},\n  css: [PROBE_CSS]\n}}\n",
    )
    write(case.tree, f"page/pages/{page_id}/probe.css.js", "export const PROBE_CSS = ''\n")
    write(case.tree, f"page/pages/{page_id}/README.md", "# Own\n\n**Tabs:** none.\n\n**Slots:** declares none.\n")
    git(case.tree, "add", "-A")
    git(case.tree, "commit", "-q", "-m", "Probe page")


def event_help() -> str:
    """`new event --help`, as argparse prints it."""
    stream = io.StringIO()
    with mock.patch("sys.stdout", stream), unittest.TestCase().assertRaises(SystemExit):
        cli.parser().parse_args(["new", "event", "--help"])
    return stream.getvalue()


class Guard(unittest.TestCase):
    def test_the_guard_runs_every_kind_and_the_real_steps_name_real_features_and_pages(self):
        kinds = {step[0] for step in tree_test.STEPS + tree_test.REAL_STEPS}
        self.assertEqual(kinds, {"feature", "rpc", "tool", "event", "listener", "page", "tab", "slot"})
        for step in tree_test.REAL_STEPS:
            where = "page/pages" if step[0] in ("tab", "slot") else "backend"
            self.assertTrue((ROOT / where / step[1]).is_dir(), step)
        self.assertIn(["slot", "home"], [step[:2] for step in tree_test.REAL_STEPS])
        self.assertIn("--from-page", [word for step in tree_test.REAL_STEPS for word in step])

    def test_ci_runs_the_scaffold_check_nested(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        step = workflow[workflow.index("- name: python tools/check.py bundle lint page scaffold") :].split("\n\n")[0]
        self.assertIn("RD_SCAFFOLD_FULL: nested", step)
        self.assertIn("run: python tools/check.py bundle lint page scaffold --strict", step)

    def test_check_py_reports_a_base_tree_that_fails_unit_as_skipped(self):
        spec = importlib.util.spec_from_file_location("check_py_probe", ROOT / "tools/check.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        said = f"test_new ... skipped '{tree_test.UNIT_FIRST}:\nFAILED (failures=1)'\n\nOK (skipped=1)\n"
        done = subprocess.CompletedProcess([], 0, "", said)
        with (
            mock.patch.object(module, "run", lambda *_a, **_k: done),
            mock.patch.object(module, "ruff_missing", lambda: None),
            mock.patch.object(module, "need", lambda tool: tool),
            mock.patch.object(module, "ROOT", ROOT if (ROOT / "tools/npm/node_modules").is_dir() else Path("/")),
        ):
            if not (module.ROOT / "tools/npm/node_modules").is_dir():
                self.skipTest("the npm tools are not set up here")
            with self.assertRaises(module.Skip) as raised:
                module.check_scaffold(None)
        self.assertEqual(str(raised.exception), "skipped: the tree fails unit (fix unit first)")


class Check(RepoCase):
    def test_a_branch_that_only_adds_architecture_and_contract_rows_adds_no_scaffold(self):
        tree = self.worktree("chore/rows")
        self.commit(tree, "docs/dev/ARCHITECTURE.md", "# rows\n")
        self.commit(tree, "docs/dev/CONTRACT.md", "# rows\n")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("scaffold", [name for entry in self.check_log() for name in entry["names"]])
        ctx = config.Context.make(ROOT, output.Out(stream=io.StringIO()))
        patterns = ctx.policy["checks"]["triggers"]["scaffold"]
        for kept in ("backend/features.py", "page/pages/index.js", "tools/layout.toml", "tools/retrodev/templates/*"):
            self.assertIn(kept, patterns)

    def test_a_scaffold_skipped_for_a_failing_unit_suite_says_so(self):
        tree = self.worktree("chore/templates")
        self.commit(tree, "tools/retrodev/templates/tool/tool.py.tmpl", "# changed\n")
        self.skip_checks("scaffold")
        (self.base / "skip-detail").write_text("skipped: the tree fails unit (fix unit first)")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails unit (fix unit first)", out)
        self.assertNotIn("a tool is missing", out)


class New(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_the_page_kinds_run_lint_bundle_and_page_and_the_backend_kinds_unit(self):
        self.assertEqual(sorted(self.ran("page", "rdprobe-notes")), ["bundle", "lint", "page"])
        self.assertNotIn("unit", self.ran("tab", "rdprobe-notes", "extra"))
        self.assertNotIn("unit", self.ran("slot", "rdprobe-notes", "more", "--doc", "More. Props: { ctx }"))
        self.assertIn("unit", self.ran("rpc", "history", "rdprobe_ping"))
        self.assertEqual(scaffold.PAGE_CHECKS, ("lint", "bundle", "page"))

    def test_from_page_moves_a_page_defined_in_index_js_into_its_own_file(self):
        inline_page(self)
        out = self.new("tab", "rdprobe-own", "first", "--from-page")
        moved = self.read(f"{OWN}/rdprobe-own-page.js")
        self.assertIn("/** Its own Page. */\nexport function RdprobeOwn({ shell }) {", moved)
        self.assertIn("import { jsx } from '#sdk'\nimport { Lede } from '#shared/ui/text.js'\n", moved)
        door = self.read(f"{OWN}/index.js")
        self.assertNotIn("function RdprobeOwn", door)
        self.assertNotIn("import { RdprobeOwn }", door)
        self.assertNotIn("Page:", door)
        self.assertNotIn("#sdk", door, "the imports only the moved Page used go")
        self.assertIn("import { PROBE_CSS } from './probe.css.js'", door)
        tab = self.read(f"{OWN}/first/index.js")
        self.assertIn("import { RdprobeOwn } from '#pages/rdprobe-own/rdprobe-own-page.js'", tab)
        steps = " ".join(out["next"])
        self.assertIn("a single tab shows a tab bar of one", steps)
        self.assertNotIn("still renders between the tab bar and the tab", steps, "the descriptor has no Page now")

    def test_from_page_appends_to_an_existing_page_file_with_the_imports_it_lacks(self):
        inline_page(self)
        write(self.tree, f"{OWN}/rdprobe-own-page.js", "import { jsx } from '#sdk'\n\nexport const OTHER = 1\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Page file")
        self.new("tab", "rdprobe-own", "first", "--from-page")
        moved = self.read(f"{OWN}/rdprobe-own-page.js")
        self.assertEqual(moved.count("import { jsx } from '#sdk'"), 1)
        self.assertIn("import { jsx } from '#sdk'\nimport { Lede } from '#shared/ui/text.js'\n", moved)
        self.assertTrue(moved.rstrip().endswith("return jsx(Lede, { children: shell.label })\n}"), moved)
        self.assertIn("export const OTHER = 1", moved)

    def test_tab_next_steps_follow_the_descriptor(self):
        inline_page(self)
        write(self.tree, "tests/page/own.test.mjs", "render(jsx(pageOf('rdprobe-own').Page, {}))\n")
        steps = " ".join(self.new("tab", "rdprobe-own", "extra")["next"])
        self.assertIn("the page's own Page still renders between the tab bar and the tab: RdprobeOwn", steps)
        self.assertIn(f"({OWN}/index.js)", steps)
        self.assertIn("a single tab shows a tab bar of one", steps)
        self.assertIn("tests/page/own.test.mjs renders pageOf('rdprobe-own').Page", steps)
        steps = " ".join(self.new("tab", "rdprobe-own", "more")["next"])
        self.assertNotIn("a tab bar of one", steps, "two tabs")
        self.assertEqual(
            git(self.tree, "status", "--porcelain", "tests/page/own.test.mjs"), "?? tests/page/own.test.mjs\n"
        )

    def test_a_listener_joins_entries_that_say_what_each_does_as_an_entry_of_its_own(self):
        self.new("feature", "rdprobe_ears")  # a probe feature: what history listens to is the real tree's business
        readme = self.read("backend/rdprobe_ears/README.md")
        readme = readme.replace("Listens to: none.", "Listens to: `library.build_reported` — keeps a note.")
        write(self.tree, "backend/rdprobe_ears/README.md", readme)
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        out = self.new("listener", "rdprobe_ears", "library.game_presented")
        line = next(row for row in self.read("backend/rdprobe_ears/README.md").splitlines() if "Listens to" in row)
        self.assertTrue(
            line.endswith(
                "`library.build_reported` — keeps a note; `library.game_presented` — say what this listener does."
            ),
            line,
        )
        steps = " ".join(out["next"])
        self.assertIn("'say what this listener does' in backend/rdprobe_ears/README.md's 'Listens to' entry", steps)
        source = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("log with host.logger (from ..hermes import host); listeners run only in the gateway", source)

    def test_an_event_s_payload_reads_as_the_existing_entries(self):
        self.new("event", "history", "rdprobe_pruned", "--payload", "game, root=<project>", "--when", "it pruned")
        door = self.read("backend/history/__init__.py")
        self.assertIn('"history.rdprobe_pruned": "it pruned; game=<...>, root=<project>",', door)
        self.assertNotIn("payload: ", door)
        self.assertIn("names in backticks", " ".join(event_help().split()))

    def test_a_slot_s_readme_line_reads_as_a_sentence(self):
        self.new("page", "rdprobe-notes")
        self.new("slot", "rdprobe-notes", "more", "--doc", "Buttons after the lede. Props: { ctx }")
        readme = self.read("page/pages/rdprobe-notes/README.md")
        self.assertIn("declares `rdprobe-notes.more`: buttons after the lede. Props: { ctx }", readme)

    def test_the_rpc_test_uses_isolated_home_and_the_next_steps_name_the_page_docs(self):
        out = self.new("rpc", "history", "rdprobe_ping")
        test = self.read("tests/backend/history/test_rpc_rdprobe_ping.py")
        self.assertIn("from tests.support import isolated_home", test)
        self.assertNotIn("HERMRETRO_HOME\": home.name", test)
        self.assertIn(
            "if a page shows it, describe it in that page's README **Shows:** line and its row in "
            "docs/dev/STUDIO-PAGES.md",
            out["next"],
        )
        self.assertIn("calls `isolated_home(self)`", (ROOT / "tools/retrodev/README.md").read_text())


class Status(RepoCase):
    def test_behind_dev_without_a_plan_syncs_first_and_says_so_up_front(self):
        tree = self.worktree("feat/goalie")
        self.on_dev("docs/other.md", "# Other\n")
        git(tree, "fetch", "-q", "origin")
        _code, out = self.run_cli("status", cwd=tree)
        lines = out.splitlines()
        self.assertTrue(
            lines[1].startswith("  plan:   goalie (none written): a feat branch ships only under"), lines[1]
        )
        self.assertIn("python tools/retrodev plan new goalie", lines[1])
        self.assertIn('python tools/retrodev plan approve goalie --words "<the owner\'s exact words>"', lines[1])
        step = next(line for line in lines if line.startswith("next: "))
        self.assertTrue(step.startswith("next: python tools/retrodev sync (HEAD lacks 1 commit(s)"), step)
        self.assertIn("then python tools/retrodev plan new goalie", step)

    def test_ship_without_a_title_still_runs_and_reports_every_gate(self):
        tree = self.worktree("feat/goalie")
        write(tree, "docs/loose.md", "# uncommitted\n")
        code, out = self.run_cli("ship", cwd=tree)
        self.assertEqual(code, 3, out)  # the plan gate needs the owner: the strictest code among the refusals
        refused = [line.strip().split(":")[0] for line in out.splitlines() if line.strip().startswith("NO  ")]
        for gate in ("NO  title", "NO  body"):
            self.assertIn(gate, refused, out)
        self.assertGreaterEqual(len(refused), 4, out)  # the plan, the commit and the checks too
        self.assertIn("FIX: python tools/retrodev ship --title", out)


if __name__ == "__main__":
    unittest.main()
