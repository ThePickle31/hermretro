"""`new`: what each kind writes, the names it refuses, --dry-run, and where it may run. Fast: the real files it
edits are copied into a test repository (no rebuild, no checks; test_scaffold_tree.py runs the real checks).

Run alone: python -m unittest tests.retrodev.test_scaffold
"""

import ast
import codecs
import re
import shutil
import unittest
from pathlib import Path

import retrodev
from retrodev import repo, scaffold

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]
REAL = [
    "backend/features.py",
    "backend/history/__init__.py",
    "backend/history/README.md",
    "backend/history/rpcs.py",
    "docs/dev/ARCHITECTURE.md",
    "docs/dev/CONTRACT.md",
    "plugin.yaml",
    "page/pages/build/transcript/step-words.js",
    "page/pages/index.js",
    "page/pages/home/index.js",
    "page/pages/home/README.md",
    "tests/page/registry.test.mjs",
    "tests/backend/history/__init__.py",
]


class New(RepoCase):
    def setUp(self):
        super().setUp()
        self.tree = self.worktree("feat/grow")
        for name in REAL + [str(path.relative_to(ROOT)) for path in ROOT.glob("engine/pins/*/tools.json")]:
            (self.tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, self.tree / name)
        layout = (ROOT / "tools/layout.toml").read_text()
        write(self.tree, "tools/layout.toml", layout)
        policy = (self.tree / "tools/retrodev/policy.toml").read_text()
        policy = re.sub(r'regenerate = \[\[[^\n]*\]\]', "regenerate = []", policy)
        write(self.tree, "tools/retrodev/policy.toml", policy)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Real files")

    def new(self, *argv, code=0, as_json=True):
        done, out = self.run_cli("new", *argv, "--no-check", cwd=self.tree, as_json=as_json)
        self.assertEqual(done, code, out)
        return out

    def read(self, name):
        return (self.tree / name).read_text()

    def test_a_feature_gets_its_folder_tests_and_every_registry_line(self):
        out = self.new("feature", "rdprobe", "--purpose", "Demonstrates new.")
        self.assertEqual(
            out["created"],
            [
                "backend/rdprobe/README.md",
                "backend/rdprobe/__init__.py",
                "tests/backend/rdprobe/__init__.py",
                "tests/backend/rdprobe/test_rdprobe.py",
            ],
        )
        self.assertEqual(out["changed"], ["backend/features.py", "docs/dev/ARCHITECTURE.md", "tools/layout.toml"])
        self.assertIn('    "rdprobe",  # demonstrates new\n]', self.read("backend/features.py"))
        self.assertIn('areas.rdprobe = "Demonstrates new"', self.read("tools/layout.toml"))
        self.assertIn("| `backend/rdprobe/` | Demonstrates new |", self.read("docs/dev/ARCHITECTURE.md"))
        door = self.read("backend/rdprobe/__init__.py")
        self.assertIn("__all__: list[str] = []", door)
        self.assertIn("EVENTS: dict[str, str] = {}", door)
        self.assertIn("next", out)

    def test_dry_run_lists_and_writes_nothing(self):
        before = git(self.tree, "status", "--porcelain")
        out = self.new("feature", "rdprobe", "--dry-run")
        self.assertTrue(out["dry_run"])
        self.assertIn("backend/rdprobe/__init__.py", out["created"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)
        self.assertFalse((self.tree / "backend/rdprobe").exists())

    def test_names_that_exist_or_break_the_rules_are_refused(self):
        for argv in (
            ["feature", "history"],
            ["feature", "Demo"],
            ["feature", "class"],
            ["feature", "a-b"],
            ["rpc", "history", "builds"],
            ["rpc", "nowhere", "x"],
            ["tool", "history", "present_game"],
            ["page", "home"],
            ["page", "Bad_Id"],
            ["tab", "nowhere", "x"],
            ["event", "history", "build_kept"],
        ):
            out = self.new(*argv, code=1)
            self.assertIn("fix", out["error"], argv)
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_only_on_a_work_branch(self):
        done, out = self.run_cli("new", "feature", "rdprobe", cwd=self.main)
        self.assertEqual(done, 1, out)
        self.assertIn("only on a work branch", out)
        self.assertIn("FIX: python tools/retrodev start feat/<topic>", out)

    def test_an_rpc_lands_in_the_feature_with_a_test_and_its_contract_section(self):
        out = self.new("rpc", "history", "rdprobe_ping")
        self.assertEqual(out["created"], ["tests/backend/history/test_rpc_rdprobe_ping.py"])
        self.assertIn('@rpc("rdprobe_ping")\ndef rpc_rdprobe_ping(ctx):', self.read("backend/history/rpcs.py"))
        self.assertIn("### `rdprobe_ping` — params `{ echo? }`", self.read("docs/dev/CONTRACT.md"))
        self.assertIn(
            "- RPCs (`rpcs.py`): `builds`, `build_restore`, `rdprobe_ping`.", self.read("backend/history/README.md")
        )
        self.new("rpc", "history", "rdprobe_ping", code=1)

    def test_a_tool_moves_the_manifest_the_step_words_and_the_counts_together(self):
        contract = self.read("docs/dev/CONTRACT.md")
        found = re.search(r"(\d+) in total", contract)
        assert found
        total = int(found.group(1))
        out = self.new("tool", "history", "chromatic_snap", "--step", "Taking a snapshot", "Took a snapshot")
        self.assertEqual(out["created"], ["backend/history/tools.py", "tests/backend/history/test_tool_snap.py"])
        self.assertIn("  - chromatic_build_report\n  - chromatic_snap\n", self.read("plugin.yaml"))
        self.assertIn("  snap: ['Taking a snapshot', 'Took a snapshot'],", self.read(scaffold_words()))
        contract = self.read("docs/dev/CONTRACT.md")
        self.assertIn(f"{total + 1} in total", contract)
        self.assertIn("81 tools, plus five", contract)
        self.assertIn("`chromatic_snap`", contract)
        tools = self.read("backend/history/tools.py")
        self.assertIn(
            'TOOLS = (Tool(SNAP_TOOL, snap_handler, step_words=("Taking a snapshot", "Took a snapshot")),)', tools
        )
        self.new("tool", "history", "second")
        self.assertIn("TOOLS = (\n    Tool(SNAP_TOOL", self.read("backend/history/tools.py"))
        self.assertIn("    Tool(SECOND_TOOL, second_handler", self.read("backend/history/tools.py"))
        self.assertIn("81 tools, plus six", self.read("docs/dev/CONTRACT.md"))

    def test_a_tool_on_a_feature_whose_tools_are_not_a_plain_tuple_is_refused_and_nothing_changes(self):
        for name in ("backend/hermes/__init__.py", "backend/hermes/tools.py"):  # TOOLS is a function there
            write(self.tree, name, (ROOT / name).read_text())
        annotated = "from ..hermes.declare import Tool\n\nTOOLS: tuple[Tool, ...] = ()\n"
        write(self.tree, "backend/history/tools.py", annotated)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Shapes")
        for feature in ("hermes", "history"):
            out = self.new("tool", feature, "snap", code=1)
            self.assertIn("not a plain tuple or list", out["error"]["message"], feature)
            self.assertIn("fix", out["error"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", f"{feature}: no file may change")

    def test_a_tool_extends_a_list_and_keeps_its_entries(self):
        tools = (
            '"""Tools."""\n\nimport json\n\nfrom ..hermes import host\nfrom ..hermes.declare import Tool\n\n'
            "logger = host.logger\nA_TOOL = {}\n\n\ndef a_handler(args, **_kwargs):\n    return json.dumps({})\n\n\n"
            'TOOLS = [Tool(A_TOOL, a_handler, step_words=("Aing", "Aed"))]  # the one\n'
        )
        write(self.tree, "backend/history/tools.py", tools)
        self.new("tool", "history", "snap")
        source = self.read("backend/history/tools.py")
        found = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)]
        listed = [ast.unparse(e.func) + " " + ast.unparse(e.args[0]) for e in found[-1].value.elts]
        self.assertEqual(listed, ["Tool A_TOOL", "Tool SNAP_TOOL"])
        self.assertIn("]  # the one", source)

    def test_quoted_step_words_make_valid_python_and_javascript(self):
        (self.tree / ".dev").mkdir(exist_ok=True)
        if (ROOT / ".dev/py/bin/ruff").is_file():  # apply formats with it, as in a real worktree
            (self.tree / ".dev/py").symlink_to(ROOT / ".dev/py")
        words = {"quoted": ('Reading "ROM"', 'Read "ROM"'), "apostrophe": ("Reading the cart's header", "Read it's")}
        for short, (running, done) in words.items():
            self.new("tool", "history", short, "--step", running, done)
            test = self.read(f"tests/backend/history/test_tool_{short}.py")
            expected = [n for n in ast.walk(ast.parse(test)) if isinstance(n, ast.Tuple) and len(n.elts) == 2]
            self.assertIn((running, done), [ast.literal_eval(n) for n in expected])
            page = re.search(
                rf"^  {short}: \[('(?:[^'\\]|\\.)*'), ('(?:[^'\\]|\\.)*')\],$", self.read(scaffold_words()), re.M
            )
            assert page, short
            self.assertEqual([codecs.decode(t[1:-1], "unicode_escape") for t in page.groups()], [running, done])
        source = self.read("backend/history/tools.py")
        declared = [
            ast.literal_eval(k.value)
            for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Call)
            for k in n.keywords
            if k.arg == "step_words"
        ]
        self.assertEqual(declared, list(words.values()))
        ruff = ROOT / ".dev/py/bin/ruff"
        if ruff.is_file():
            files = ["backend/history/tools.py", *(f"tests/backend/history/test_tool_{s}.py" for s in words)]
            config = ["--config", str(ROOT / "tools/py/ruff.toml")]
            for command in (["check", "-q", *config], ["format", "--check", "-q", *config]):
                code, out, err = repo.run([str(ruff), *command, *files], self.tree, timeout=60)
                self.assertEqual(code, 0, out + err)

    def test_an_event_keeps_the_entries_of_a_one_line_events_dict(self):
        door = self.read("backend/history/__init__.py")
        door = re.sub(
            r"EVENTS = \{\n(.*?)\n\}", lambda m: "EVENTS = {" + m.group(1).strip().rstrip(",") + "}", door, flags=re.S
        )
        self.assertIn('EVENTS = {"history.build_kept": ', door)
        write(self.tree, "backend/history/__init__.py", door)
        self.new("event", "history", "pruned", "--payload", "game")
        declared = next(
            n.value
            for n in ast.parse(self.read("backend/history/__init__.py")).body
            if getattr(n, "targets", [None])[0] is not None and getattr(n.targets[0], "id", "") == "EVENTS"
        )
        self.assertEqual(sorted(ast.literal_eval(declared)), ["history.build_kept", "history.pruned"])

    def test_an_event_is_declared_emitted_once_and_documented(self):
        self.new("event", "history", "pruned", "--payload", "game")
        door = self.read("backend/history/__init__.py")
        self.assertRegex(
            door, r'"history.build_kept": [^\n]*,\n    # emits\.pruned[^\n]*\n    "history.pruned": "game",\n}'
        )
        self.assertIn('emit("history.pruned", **payload)', self.read("backend/history/emits.py"))
        self.assertIn("| `history.pruned` | game |", self.read("docs/dev/CONTRACT.md"))
        self.assertIn("Events emitted: `history.build_kept`, `history.pruned`.", self.read("backend/history/README.md"))
        self.new("event", "history", "pruned", code=1)

    def test_a_page_a_tab_and_a_slot(self):
        self.new("page", "rdprobe-notes", "--label", "Notes")
        self.assertIn("import { RDPROBE_NOTES_PAGE } from './rdprobe-notes/index.js'", self.read("page/pages/index.js"))
        self.assertRegex(
            self.read("page/pages/index.js"), r"export const PAGES = \[[^\]]*EMULATOR_PAGE, [^\]]*RDPROBE_NOTES_PAGE\]"
        )
        self.assertRegex(self.read("tests/page/registry.test.mjs"), r"'emulator', [^\]]*'rdprobe-notes'\]")
        self.new("tab", "rdprobe-notes", "extra")
        self.new("tab", "rdprobe-notes", "more")
        index = self.read("page/pages/rdprobe-notes/index.js")
        self.assertIn("  tabs: [\n    RDPROBE_NOTES_EXTRA_TAB,\n    RDPROBE_NOTES_MORE_TAB\n  ]", index)
        self.assertIn("**Tabs:** `extra` (`extra/index.js`).", self.read("page/pages/rdprobe-notes/README.md"))
        self.new("slot", "home", "side-panel", "--doc", "Beside the hero. Props: { ctx }")
        self.assertIn(
            "  slots: {\n    'home.sidePanel': 'Beside the hero. Props: { ctx }'\n  }",
            self.read("page/pages/home/index.js"),
        )
        self.assertRegex(self.read("tests/page/registry.test.mjs"), r"keys\(\)\]\.sort\(\), \[[^\]]*'home\.sidePanel'")
        self.new("slot", "home", "sidePanel", code=1)
        write(self.tree, "page/pages/home/other.js", "export function RdprobeTwoPage() {}\n")
        self.new("page", "rdprobe-two", code=1)  # the bundle needs unique export names

    def test_the_text_output_names_each_file_and_the_next_step(self):
        out = self.new("rpc", "history", "rdprobe_ping", as_json=False)
        self.assertIn("create  tests/backend/history/test_rpc_rdprobe_ping.py", out)
        self.assertIn("change  backend/history/rpcs.py", out)
        self.assertIn("next: write the handler in backend/history/rpcs.py", out)


def scaffold_words():
    return "page/pages/build/transcript/step-words.js"


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
