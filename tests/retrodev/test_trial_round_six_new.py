"""Friction the sixth round of fresh-agent trials found in `new`: a repeated --payload kept only its last value, a
tab's next steps forgot the README and STUDIO-PAGES and PAGE_IN_INDEX, rpc had no --module, the listener's README
entry and cross-process advice, and the --project tool's root stayed `str | None` for pyright. Each test failed
before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_six_new
"""

import ast
import importlib.util
import unittest
from pathlib import Path

import retrodev

from tests.repo.test_placeholders import PLACEHOLDERS
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.scaffold_moves import needs_acorn
from tests.retrodev.test_scaffold import ScaffoldCase
from tests.retrodev.test_trial_round_five import OWN, inline_page

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]


def rpc_names():
    """tools/bundle/rpc_names.py: the generator of the page's RPC names, which reads @rpc in rpcs.py only."""
    spec = importlib.util.spec_from_file_location("rpc_names_probe", ROOT / "tools/bundle/rpc_names.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Event(ScaffoldCase):
    def test_a_repeated_payload_keeps_every_value(self):
        self.new(
            "event", "history", "rdprobe_three", "--payload", "game", "--payload", "root=<project>",
            "--payload", "count", "--when", "it counted",
        )  # fmt: skip
        door = self.read("backend/history/__init__.py")
        self.assertIn('"history.rdprobe_three": "it counted; game=<...>, root=<project>, count=<...>",', door)
        self.assertIn(
            "| `history.rdprobe_three` | `game`, `root`, `count` | it counted |", self.read("docs/dev/CONTRACT.md")
        )
        self.assertIn("(game, root=<project>, count)", self.read("backend/history/emits.py"))
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        row = next(line for line in readme.splitlines() if line.startswith("| `new event "))
        self.assertIn("either way: comma-separated", row)
        self.assertIn("or repeated (`--payload game --payload root`)", row)


class Tab(ScaffoldCase):
    def test_every_tab_says_to_describe_it_in_the_readme_and_studio_pages(self):
        self.new("page", "rdprobe-notes")
        steps = self.new("tab", "rdprobe-notes", "extra")["next"]
        self.assertIn(
            "describe the tab in page/pages/rdprobe-notes/README.md **Shows:** and in the page's row of "
            "docs/dev/STUDIO-PAGES.md",
            steps,
        )

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_a_page_moved_out_of_index_js_names_its_page_in_index_entry(self):
        inline_page(self)
        registry = self.read("tests/page/registry.test.mjs")
        registry = registry.replace(
            "const PAGE_IN_INDEX = new Set(['home'])", "const PAGE_IN_INDEX = new Set(['home', 'rdprobe-own'])"
        )
        write(self.tree, "tests/page/registry.test.mjs", registry)
        git(self.tree, "commit", "-qam", "Allowed in index.js")
        steps = " ".join(self.new("tab", "rdprobe-own", "first", "--from-page")["next"])
        self.assertIn("remove 'rdprobe-own' from PAGE_IN_INDEX in tests/page/registry.test.mjs", steps)
        self.assertIn("'rdprobe-own'])", self.read("tests/page/registry.test.mjs"), "new never edits tests/page")
        self.assertTrue((self.tree / f"{OWN}/rdprobe-own-page.js").is_file())


class Rpc(ScaffoldCase):
    def test_module_puts_the_handler_in_its_own_file_and_keeps_the_declaration_in_rpcs_py(self):
        out = self.new("rpc", "history", "rdprobe_pong", "--module", "rdprobe_pong_rpcs")
        home = self.read("backend/history/rdprobe_pong_rpcs.py")
        self.assertIn("def rpc_rdprobe_pong(ctx):", home)
        self.assertNotIn("@rpc", home)
        self.assertIn("logger = host.logger", home)
        source = self.read("backend/history/rpcs.py")
        self.assertIn("from . import rdprobe_pong_rpcs", source)
        self.assertIn('@rpc("rdprobe_pong")\ndef rpc_rdprobe_pong(ctx):', source)
        self.assertIn("    return rdprobe_pong_rpcs.rpc_rdprobe_pong(ctx)", source)
        for text in (home, source):
            ast.parse(text)
        declared = rpc_names().declared(self.tree)  # what the generated names and the lock-step test read
        self.assertIn(("rdprobe_pong", "backend/history/rpcs.py"), declared)
        self.assertIn("write the handler in backend/history/rdprobe_pong_rpcs.py", " ".join(out["next"]))
        self.assertIn("rdprobe_pong", self.read("backend/history/README.md"))

    def test_a_long_rpcs_py_gets_a_note_suggesting_module(self):
        source = self.read("backend/history/rpcs.py")
        write(self.tree, "backend/history/rpcs.py", source + "".join(f"# line {n}\n" for n in range(360)))
        git(self.tree, "commit", "-qam", "A long rpcs.py")
        out = self.new("rpc", "history", "rdprobe_big", as_json=False)
        self.assertIn("python tools/retrodev new rpc history rdprobe_big --module rdprobe_big_rpcs", out)
        out = self.new("rpc", "history", "rdprobe_small", "--module", "rdprobe_small_rpcs", as_json=False)
        self.assertNotIn("note: backend/history/rpcs.py has", out)

    def test_module_refuses_the_names_a_feature_keeps(self):
        out = self.new("rpc", "history", "rdprobe_pong", "--module", "tools", code=1)
        self.assertIn("nothing was written", out["error"]["message"])


class Listener(ScaffoldCase):
    def setUp(self):
        super().setUp()
        self.new("feature", "rdprobe_ears")
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Probe feature")

    def listens(self) -> str:
        return next(row for row in self.read("backend/rdprobe_ears/README.md").splitlines() if "Listens to" in row)

    def test_none_becomes_an_entry_naming_the_file_that_the_placeholder_gate_catches(self):
        out = self.new("listener", "rdprobe_ears", "library.game_presented")
        line = self.listens()
        self.assertTrue(
            line.endswith("Listens to (`listeners.py`): `library.game_presented` — say what this listener does."), line
        )
        self.assertTrue(any(text in line for text in PLACEHOLDERS), line)
        steps = " ".join(out["next"])
        self.assertIn(
            "if other code reads what the listener keeps, export the reader in backend/rdprobe_ears/__init__.py "
            "__all__ and name it on the README Front door line",
            steps,
        )
        self.assertIn("goes in a file under backend.system.paths.hermretro_home(), written atomically", steps)
        said = " ".join(self.read("backend/rdprobe_ears/listeners.py").split())
        self.assertIn(
            "state other processes must read goes in a file under backend.system.paths.hermretro_home(),", said
        )

    def test_a_plain_listed_event_gets_the_new_one_as_an_entry_of_its_own(self):
        readme = self.read("backend/rdprobe_ears/README.md")
        write(
            self.tree,
            "backend/rdprobe_ears/README.md",
            readme.replace("Listens to: none.", "Listens to: `library.build_reported`."),
        )
        git(self.tree, "commit", "-qam", "Listed by hand")
        self.new("listener", "rdprobe_ears", "library.game_presented")
        self.assertTrue(
            self.listens().endswith(
                "Listens to (`listeners.py`): `library.build_reported`; `library.game_presented` — say what this "
                "listener does."
            ),
            self.listens(),
        )


class ToolProject(ScaffoldCase):
    def test_root_is_narrowed_and_the_codes_in_use_are_listed(self):
        self.new("feature", "rdprobe_lib")
        write(self.tree, "backend/rdprobe_lib/tool_args.py", (ROOT / "backend/library/tool_args.py").read_text())
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "A feature with tool_args")
        out = self.new("tool", "rdprobe_lib", "rdprobe_open")
        source = self.read("backend/rdprobe_lib/tools.py")
        self.assertIn(
            '        if error or root is None:  # narrows root to str for pyright: tool_project gives one or the other\n'
            '            return error or tool_error("chromatic_rdprobe_open: no project folder.", "NO_PROJECT")\n',
            source,
        )
        ast.parse(source)
        step = next(step for step in out["next"] if step.startswith("the tool error codes in use"))
        for code in ("ADAPTER_ERROR", "INVALID_ARGUMENTS", "NO_PROJECT", "PROJECT_NOT_FOUND"):
            self.assertIn(code, step)


if __name__ == "__main__":
    unittest.main()
