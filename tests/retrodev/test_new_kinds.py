"""`new` friction from the first round of fresh-agent trials (the listener test scaffolds into a throwaway feature): rpc <feature>.<name>, the listener kind, the tool
counts past six and the big tools.py warning, every tab on the README line and the tab template's Heading. Each
test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_new_kinds
"""

import shutil
import unittest

from retrodev import scaffold, scaffold_backend

from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
EVENT = "library.build_reported"


class NewKinds(ScaffoldCase):
    def changed(self):
        return git(self.tree, "status", "--porcelain")

    def test_an_rpc_named_feature_dot_name_and_its_isolated_test(self):
        out = self.new("rpc", "history.rdprobe_recent")
        self.assertIn("tests/backend/history/test_rpc_rdprobe_recent.py", out["created"])
        test = self.read("tests/backend/history/test_rpc_rdprobe_recent.py")
        self.assertIn(
            "        isolated_home(self)\n", test
        )  # round five: tests/support.py's helper, not a hand-made home
        self.assertNotIn("throwaway_profile", test)
        steps = " ".join(out["next"])
        self.assertIn("import { RPC_RDPROBE_RECENT } from '#app/rpc.js' (re-exports the generated rpc-names.js)", steps)
        self.assertIn("plugin.hermretro.rdprobe_recent", steps)
        out = self.new("rpc", "history", code=1)
        self.assertIn("<feature>.<name>", out["error"]["message"])

    def test_a_listener_with_its_test_readme_and_doc_cells(self):
        # In a throwaway feature made in the copy: a real feature (history) may get a listener of its own any day.
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears", "--purpose", "A probe feature that listens")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe feature")
        before = self.read("docs/dev/CONTRACT.md")
        heard = next(line for line in before.splitlines() if line.startswith(f"| `{EVENT}` |")).split(" | ")[-1]
        out = self.new("listener", "rdprobe_ears", EVENT)
        func = "on_library_build_reported"
        test = f"tests/backend/rdprobe_ears/test_listener_{func}.py"
        self.assertEqual(out["created"], ["backend/rdprobe_ears/listeners.py", test])
        self.assertEqual(
            out["changed"], ["backend/rdprobe_ears/README.md", "docs/dev/ARCHITECTURE.md", "docs/dev/CONTRACT.md"]
        )
        source = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("from ..system.events import on", source)
        self.assertIn(f'@on("{EVENT}")\ndef {func}(**_payload) -> None:', source)
        self.assertIn('"HERMRETRO_HOME": home.name', self.read(test))
        self.assertIn(f"Listens to: `{EVENT}`.", self.read("backend/rdprobe_ears/README.md"))
        row = next(line for line in self.read("docs/dev/CONTRACT.md").splitlines() if line.startswith(f"| `{EVENT}`"))
        self.assertTrue(row.endswith(f"{heard.removesuffix(' |')}, rdprobe_ears (say what it does) |"), row)
        arch = self.read("docs/dev/ARCHITECTURE.md").split("## The agent half")[1]
        row = next(line for line in arch.splitlines() if line.startswith("| `backend/rdprobe_ears/` |"))
        self.assertTrue(row.endswith(f"; listens to `{EVENT}` |"), row)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Listener")
        self.new("listener", "rdprobe_ears", EVENT, code=1)  # twice: refused
        self.assertEqual(self.changed(), "")

    def test_an_undeclared_event_or_a_stdlib_only_feature_is_refused_and_nothing_changes(self):
        out = self.new("listener", "history", "library.never_declared", code=1)
        self.assertIn("no front door declares the event 'library.never_declared'", out["error"]["message"])
        self.assertIn("new event", out["error"]["fix"])
        write(self.tree, "backend/broker/__init__.py", '"""Broker."""\n')
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Broker")
        self.new("listener", "broker", "history.build_kept", code=1)
        self.assertEqual(self.changed(), "")

    def test_tool_counts_past_six_are_words(self):
        text = "the 87 tools, and 81 tools, plus six plugin-owned ones. 87 in total.\n"
        changed = scaffold_backend._contract_tool(text, "chromatic_seventh", "history")
        self.assertIn("81 tools, plus seven", changed)
        self.assertIn("88 in total", changed)
        self.assertIn("plus 21", scaffold_backend._contract_tool(text.replace("six", "twenty"), "chromatic_x", "h"))

    def test_a_tool_in_a_tools_py_over_400_lines_suggests_a_sibling_module(self):
        header = (ROOT / "tools/retrodev/templates/tool/tools.py.tmpl").read_text().replace("{Name}", "History")
        write(self.tree, "backend/history/tools.py", header + "\n" + "# filler\n" * 400 + "\nTOOLS = ()\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Big tools")
        out = self.new("tool", "history", "rdprobe_big", as_json=False)
        self.assertRegex(out, r"note: backend/history/tools\.py has \d+ lines, over 400")
        # Flipped: it once only suggested a sibling module; now it writes the tool into one and says so.
        self.assertIn("the tool goes in its own module backend/history/rdprobe_big_tools.py", out)
        self.assertIn("*rdprobe_big_tools.TOOLS", self.read("backend/history/tools.py"))
        self.assertIn(
            "CHROMATIC_RDPROBE_BIG_TOOL".removeprefix("CHROMATIC_"), self.read("backend/history/rdprobe_big_tools.py")
        )

    def test_the_tab_template_uses_heading_and_says_the_page_still_renders(self):
        self.new("page", "rdprobe-tabs")
        out = self.new("tab", "rdprobe-tabs", "first")
        tab = self.read("page/pages/rdprobe-tabs/first/index.js")
        self.assertIn("import { Heading, Lede } from '#shared/ui/text.js'", tab)
        self.assertIn("jsx(Heading, { children: 'First' })", tab)
        steps = " ".join(out["next"])
        self.assertIn(
            "the page's own Page still renders between the tab bar and the tab: RdprobeTabsPage "
            "(page/pages/rdprobe-tabs/rdprobe-tabs-page.js)",
            steps,
        )
        self.assertIn("a single tab shows a tab bar of one", steps)
        text = (ROOT / "page/shared/ui/text.js").read_text()
        self.assertIn(
            "export function Heading({ children }) {\n  return jsx('h2', { className: 'cs-word cs-title'", text
        )


class Pieces(unittest.TestCase):
    def test_readme_items_replace_none_or_append(self):
        self.assertEqual(scaffold.readme_item("- RPCs: none.", "RPCs", "`a`"), "- RPCs: `a`.")
        self.assertEqual(
            scaffold.readme_item("- RPCs (`rpcs.py`): `a`.", "RPCs", "`b`"), "- RPCs (`rpcs.py`): `a`, `b`."
        )
        self.assertEqual(
            scaffold.readme_item("- Events emitted: none. Listens to: none.", "Events emitted", "`x.y`"),
            "- Events emitted: `x.y`. Listens to: none.",
        )
        self.assertEqual(scaffold.readme_item("**Tabs:** one.", "Tabs:", "`t`", only_none=True), "**Tabs:** one.")

    def test_templates_keep_literal_braces(self):
        self.assertIn("{ echo? }", scaffold.render("rpc", "contract.md.tmpl", rpc="x", name="f", RPC="X"))

    def test_names(self):
        self.assertEqual(scaffold.pascal("side-panel"), "SidePanel")
        self.assertEqual(scaffold.const("side-panel"), "SIDE_PANEL")
        self.assertEqual(scaffold.camel("side-panel"), "sidePanel")


if __name__ == "__main__":
    unittest.main()
