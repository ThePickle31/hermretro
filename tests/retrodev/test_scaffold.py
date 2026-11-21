"""`new`: what each kind writes, the names it refuses, --dry-run, and where it may run. Fast: the real files it
edits are copied into a test repository (no rebuild, no checks; test_scaffold_tree.py runs the real checks).

Run alone: python -m unittest tests.retrodev.test_scaffold
"""

import ast
import codecs
import json
import re
import shutil
from pathlib import Path

import retrodev
from retrodev import count_words, repo, scaffold, scaffold_listener, state

from tests.repo import test_lockstep
from tests.retrodev.fixture import RepoCase, git, parallel, write
from tests.retrodev.hand_edits import line_of, one_line_events

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
    "page/pages/build/index.js",
    "page/pages/build/README.md",
    "tests/page/registry.test.mjs",
    "tests/backend/history/__init__.py",
]


class ScaffoldCase(RepoCase):
    """A work branch holding the real files `new` edits (test_new_kinds.py uses it too)."""

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

    def own_exactly(self, owned: int):
        """Set the test repository's plugin.yaml and CONTRACT.md to exactly this many plugin-owned tools."""
        manifest, contract = self.read("plugin.yaml"), self.read("docs/dev/CONTRACT.md")
        names = owned_list(manifest)
        keep = names[:owned] + [f"chromatic_rdfake{n}" for n in range(owned - len(names))]
        head, _, tail = manifest.partition("provides_tools:")
        lines = [line for line in tail.split("\n") if line.removeprefix("  - ") not in names]
        at = 1  # after the list's last item (lines[0] is the rest of the 'provides_tools:' line)
        while at < len(lines) and lines[at].startswith("  - "):
            at += 1
        manifest = head + "provides_tools:" + "\n".join(lines[:at] + [f"  - {n}" for n in keep] + lines[at:])
        _total, engine = contract_counts(contract)
        contract = re.sub(
            r"(\d+ tools, plus\s+)\w+", lambda m: m.group(1) + count_words.count_text(owned), contract, count=1
        )
        contract = re.sub(r"\d+( in total)", lambda m: f"{engine + owned}{m.group(1)}", contract, count=1)
        write(self.tree, "plugin.yaml", manifest)
        write(self.tree, "docs/dev/CONTRACT.md", contract)
        self.assertEqual(owned_tools(manifest, contract)[1], owned)
        self.assertEqual(len(owned_list(manifest)), owned)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", f"{owned} plugin-owned tools")


class New(ScaffoldCase):
    def test_a_successful_listener_checks_unit_without_retaining_the_pass(self):
        self.new("feature", "rdcheck", "--purpose", "Tests checked scaffolds.")
        self.new("event", "history", "rdcheck_ready", "--when", "the wiring test is ready")
        branch = "feat/grow"
        before = state.load_branch(self.tree, branch)
        self.clear_log()
        code, said = self.run_cli("new", "listener", "rdcheck", "history.rdcheck_ready", cwd=self.tree)
        self.assertEqual(code, 0, said)
        self.assertIn("unit", [name for entry in self.check_log() for name in entry["names"]])
        self.assertEqual(state.load_branch(self.tree, branch), before)

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
            ["page", "build"],
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
        before = line_of(self.read("backend/history/README.md"), "- RPCs")  # whatever the real README says now
        out = self.new("rpc", "history", "rdprobe_ping")
        self.assertEqual(out["created"], ["tests/backend/history/test_rpc_rdprobe_ping.py"])
        self.assertIn('@rpc("rdprobe_ping")\ndef rpc_rdprobe_ping(ctx):', self.read("backend/history/rpcs.py"))
        # history's RPCs are rows of the 'Studio pages' table: the new one is a row after them (round 18)
        self.assertIn("| `rdprobe_ping` | `{ echo? }` | `{ ok, echo }`: ", self.read("docs/dev/CONTRACT.md"))
        head, tail = re.split(r"(?=\.(?:\s|$))", before, maxsplit=1)  # its list, then the sentence's end and after
        self.assertEqual(line_of(self.read("backend/history/README.md"), "- RPCs"), f"{head}, `rdprobe_ping`{tail}")
        self.new("rpc", "history", "rdprobe_ping", code=1)

    def test_a_tool_moves_the_manifest_the_step_words_and_the_counts_together(self):
        contract = self.read("docs/dev/CONTRACT.md")
        total, engine = contract_counts(contract)
        last, extra = owned_tools(self.read("plugin.yaml"), contract)  # read from the real files: tools get added
        out = self.new("tool", "history", "chromatic_snap", "--step", "Taking a snapshot", "Took a snapshot")
        self.assertEqual(out["created"], ["backend/history/tools.py", "tests/backend/history/test_tool_snap.py"])
        self.assertIn(f"  - {last}\n  - chromatic_snap\n", self.read("plugin.yaml"))
        self.assertIn("  snap: ['Taking a snapshot', 'Took a snapshot'],", self.read(scaffold_words()))
        contract = self.read("docs/dev/CONTRACT.md")
        self.assertIn(f"{total + 1} in total", contract)
        self.assertIn(f"tools, plus {count_words.count_text(extra + 1)}", contract)
        self.assertIn("`chromatic_snap`", contract)
        tools = self.read("backend/history/tools.py")
        self.assertIn(
            'TOOLS = (Tool(SNAP_TOOL, snap_handler, step_words=("Taking a snapshot", "Took a snapshot")),)', tools
        )
        self.new("tool", "history", "second")
        self.assertIn("TOOLS = (\n    Tool(SNAP_TOOL", self.read("backend/history/tools.py"))
        self.assertIn("    Tool(SECOND_TOOL, second_handler", self.read("backend/history/tools.py"))
        contract = self.read("docs/dev/CONTRACT.md")
        self.assertIn(f"{engine} tools, plus {count_words.count_text(extra + 2)}", contract)
        self.assertIn(f"{total + 2} in total", contract)

    def test_a_tool_on_a_feature_whose_tools_are_not_a_plain_tuple_is_refused_and_nothing_changes(self):
        write(self.tree, "backend/hermes/__init__.py", (ROOT / "backend/hermes/__init__.py").read_text())
        write(self.tree, "backend/hermes/tools.py", "def TOOLS():\n    return ()\n")  # a probe: TOOLS a function
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
        declared_now = scaffold_listener.declared_events(scaffold.Plan(self.tree))
        entries = {n: d for n, d in declared_now.items() if n.startswith("history.")} or {"history.rdprobe_was": "x"}
        kept = sorted(entries)  # whatever history declares now (a probe entry when it declares none)
        write(self.tree, "backend/history/__init__.py", one_line_events(door, entries))
        self.new("event", "history", "pruned", "--payload", "game")
        declared = next(
            n.value
            for n in ast.parse(self.read("backend/history/__init__.py")).body
            if getattr(n, "targets", [None])[0] is not None and getattr(n.targets[0], "id", "") == "EVENTS"
        )
        self.assertEqual(sorted(ast.literal_eval(declared)), sorted([*kept, "history.pruned"]))

    def test_an_event_is_declared_emitted_once_and_documented(self):
        emitted = next(line for line in self.read("backend/history/README.md").splitlines() if "Events emitted" in line)
        self.new("event", "history", "pruned", "--payload", "game")
        door = self.read("backend/history/__init__.py")
        self.assertRegex(  # the hint goes in the next steps, never as a comment inside EVENTS; last, after the others
            door, r'\n    "history.pruned": "say when it is emitted; game=<...>",\n}'
        )
        self.assertIn('emit("history.pruned", game=game)', self.read("backend/history/emits.py"))  # round seven
        self.assertIn("| `history.pruned` | `game` (<...>) | say when |", self.read("docs/dev/CONTRACT.md"))
        before = re.search(r"Events emitted: (.*?)\.(?=\s|$)", emitted).group(1)  # as the real README lists them
        self.assertIn(f"Events emitted: {before}, `history.pruned`.", self.read("backend/history/README.md"))
        self.new("event", "history", "pruned", code=1)

    def test_a_page_a_tab_and_a_slot(self):
        pages = re.search(r"export const PAGES = \[([^\]]*)\]", self.read("page/pages/index.js")).group(1)
        ids = re.search(r"page => page\.id\), \[([^\]]*)\]", self.read("tests/page/registry.test.mjs")).group(1)
        self.new("page", "rdprobe-notes", "--label", "Notes")  # last in both lists, whatever pages are there now
        self.assertIn("import { RDPROBE_NOTES_PAGE } from './rdprobe-notes/index.js'", self.read("page/pages/index.js"))
        self.assertIn(f"export const PAGES = [{pages}, RDPROBE_NOTES_PAGE]", self.read("page/pages/index.js"))
        self.assertIn(f"page => page.id), [{ids}, 'rdprobe-notes']", self.read("tests/page/registry.test.mjs"))
        self.new("tab", "rdprobe-notes", "extra")
        self.new("tab", "rdprobe-notes", "more")
        index = self.read("page/pages/rdprobe-notes/index.js")
        self.assertIn("  tabs: [\n    RDPROBE_NOTES_EXTRA_TAB,\n    RDPROBE_NOTES_MORE_TAB\n  ]", index)
        readme = self.read("page/pages/rdprobe-notes/README.md")
        self.assertIn("**Tabs:** `extra` (`extra/index.js`), `more` (`more/index.js`).", readme)  # every tab, not one
        self.new("slot", "build", "side-panel", "--doc", "Beside the transcript. Props: { ctx }")
        # last in build's slots, after whatever slots build declares already (a branch may have added one)
        self.assertRegex(
            self.read("page/pages/build/index.js"),
            r"\n  slots: \{\n(    '[\w.]+': '[^'\n]*',\n)*    'build\.sidePanel': 'Beside the transcript\. Props: \{ ctx \}'\n  \}",
        )
        self.assertRegex(self.read("tests/page/registry.test.mjs"), r"keys\(\)\]\.sort\(\), \[[^\]]*'build\.sidePanel'")
        self.new("slot", "build", "sidePanel", code=1)
        write(self.tree, "page/pages/build/other.js", "export function RdprobeTwoPage() {}\n")
        self.new("page", "rdprobe-two", code=1)  # the bundle needs unique export names

    def test_a_tool_whose_schema_or_handler_name_is_bound_already_is_refused_and_nothing_changes(self):
        for name in ("backend/library/__init__.py", "backend/library/README.md"):
            write(self.tree, name, (ROOT / name).read_text())
        write(self.tree, "backend/library/tools.py", "PRESENT_TOOL = {}\nTOOLS = ()\n")  # a probe binding the schema
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Library")
        before = self.read("backend/library/tools.py")
        out = self.new("tool", "library", "present", code=1)  # PRESENT_TOOL is bound already
        self.assertIn("binds PRESENT_TOOL already", out["error"]["message"])
        self.assertIn("pick another tool name", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
        self.assertEqual(self.read("backend/library/tools.py"), before)
        write(self.tree, "backend/history/tools.py", "from ..hermes.declare import Tool\n\n\ndef snap_handler(): ...\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Handler")
        out = self.new("tool", "history", "snap", code=1)
        self.assertIn("binds snap_handler already", out["error"]["message"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_labels_that_would_break_the_javascript_string_are_refused_and_nothing_changes(self):
        for label in ("Ends in \\", "Two\\nlines", "Line\u2028sep", "Para\u2029sep", "Car\rriage", "It's"):
            self.new("page", "rdprobe-odd", "--label", label, code=1)
            self.new("tab", "build", "odd", "--label", label, code=1)
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", repr(label))

    def test_slot_docs_that_would_break_the_javascript_string_are_refused_and_nothing_changes(self):
        for doc in ("Car\rriage", "Ends in \\", "Line\u2028sep", "Tab\there", "It's"):
            out = self.new("slot", "build", "oddSlot", "--doc", doc, code=1)
            self.assertIn("quoted JavaScript string", out["error"]["message"], repr(doc))
            self.assertIn("--doc", out["error"]["fix"], repr(doc))
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", repr(doc))

    def test_a_label_with_double_quotes_and_accents_makes_javascript_that_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not on this machine")
        self.new("page", "rdprobe-notes", "--label", 'Notes "beta" — ü')
        self.new("tab", "rdprobe-notes", "extra", "--label", 'Extra "one"')
        folder = self.tree / "page/pages/rdprobe-notes"
        for source in (folder / "index.js", folder / "rdprobe-notes-page.js", folder / "extra/index.js"):
            copy = source.with_suffix(".mjs")
            copy.write_text(source.read_text())
            code, out, err = repo.run([node, "--check", str(copy)], self.tree, timeout=60)
            self.assertEqual(code, 0, f"{source}: {out}{err}")

    def test_no_rpc_tool_or_event_goes_into_a_stdlib_only_feature(self):
        for name in ("backend/broker/__init__.py", "backend/broker/README.md"):
            write(self.tree, name, (ROOT / name).read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Broker")
        for argv in (["rpc", "broker", "probe"], ["tool", "broker", "probe"], ["event", "broker", "pinged"]):
            out = self.new(*argv, code=1)
            self.assertIn("stays stdlib-only", out["error"]["message"], argv)
            self.assertIn("another feature", out["error"]["fix"], argv)
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", argv)
        out = self.new("event", "system", "pinged", code=1)
        self.assertIn("stays stdlib-only", out["error"]["message"])

    def test_the_text_output_names_each_file_and_the_next_step(self):
        out = self.new("rpc", "history", "rdprobe_ping", as_json=False)
        self.assertIn("create  tests/backend/history/test_rpc_rdprobe_ping.py", out)
        self.assertIn("change  backend/history/rpcs.py", out)
        self.assertIn("next: write the handler in backend/history/rpcs.py", out)

    def test_the_seventh_tool_s_count_is_the_one_the_lockstep_check_expects(self):
        # The scaffold and tests/repo/test_lockstep.py share tools/retrodev/count_words.py: 'plus seven', not 'plus 7'.
        # The test repository is set to exactly six plugin-owned tools, whatever the real count is.
        self.own_exactly(6)
        _total, engine = contract_counts(self.read("docs/dev/CONTRACT.md"))
        self.new("tool", "history", "rdprobe")
        contract = self.read("docs/dev/CONTRACT.md")
        self.assertEqual(owned_tools(self.read("plugin.yaml"), contract)[1], 7)
        self.assertEqual(len(owned_list(self.read("plugin.yaml"))), 7)
        self.assertIn(test_lockstep.contract_count(engine, 7), test_lockstep.flat(contract))
        self.assertIn(f"{engine} tools, plus seven", contract)
        self.assertIn(f"{engine + 7} in total", contract)
        self.assertEqual((count_words.count_text(20), count_words.count_text(21)), ("twenty", "21"))
        self.assertEqual((count_words.count_value("seven"), count_words.count_value("21")), (7, 21))


def owned_list(manifest: str) -> list[str]:
    """The plugin-owned tools plugin.yaml lists (every listed tool the engine's pinned tools.json does not name)."""
    engine = set()
    for path in ROOT.glob("engine/pins/*/tools.json"):
        engine |= {"chromatic_" + tool["name"] for tool in json.loads(path.read_text()).get("tools", [])}
    listed = re.findall(r"^  - (\w+)$", manifest.split("provides_tools:")[-1], re.M)
    return [name for name in listed if name not in engine]


def owned_tools(manifest: str, contract: str) -> tuple[str, int]:
    """(the last plugin-owned tool in plugin.yaml, how many CONTRACT.md counts beside the engine's), from the files."""
    word = re.search(r"\d+ tools, plus\s+(\w+)", contract).group(1)
    return owned_list(manifest)[-1], count_words.count_value(word)


def contract_counts(contract: str) -> tuple[int, int]:
    """(CONTRACT.md's 'N in total', its engine count 'E tools, plus ...'), read from the file."""
    total = re.search(r"(\d+) in total", contract)
    engine = re.search(r"(\d+) tools, plus", contract)
    assert total and engine, "CONTRACT.md lost its tool counts"
    return int(total.group(1)), int(engine.group(1))


def scaffold_words():
    return "page/pages/build/transcript/step-words.js"
