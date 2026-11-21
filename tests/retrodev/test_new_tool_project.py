"""The trial rounds' regressions for this area (RoundEightNew, RoundNineteen, RoundSixNew, RoundTenNew, RoundThree, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_tool_project
"""

import ast
import re
import shutil
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
import subprocess
import sys
import textwrap
from retrodev.scaffold_backend import BIG_MODULE

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


SEEDED = """
import sys, time, unittest
sys.path.insert(0, {root!r})
from backend import library
from backend.hermes import host
from tests.support import isolated_home


class Seed(unittest.TestCase):
    def test_seed(self):
        home = isolated_home(self)
        project = home.base / "game"
        project.mkdir()
        {seed}
        root = str(project)
        self.assertEqual({read}["sha256"], "abc")


result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Seed))
sys.exit(0 if result.wasSuccessful() else 1)
"""


class Tool(ScaffoldCase):
    def test_project_outside_library_is_refused_without_the_shared_helpers(self):
        out = self.new("tool", "history", "rdprobe_proj", "--project", code=1)
        self.assertIn("backend/hermes/tool_args.py", out["error"]["message"])
        self.assertIn("python tools/retrodev sync", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_project_outside_library_imports_the_shared_helpers(self):
        write(self.tree, "backend/hermes/tool_args.py", (ROOT / "backend/hermes/tool_args.py").read_text())  # #60's
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The shared helpers")
        out = self.new("tool", "history", "rdprobe_proj", "--project")
        source = self.read("backend/history/tools.py")
        self.assertIn("from ..hermes.tool_args import tool_error, tool_project", source)
        self.assertIn('tool_project("chromatic_rdprobe_proj", args, kwargs)', source)
        self.assertIn("call host.library_game_for([root]) -> (game id, root) or None", joined(out))  # round 17
        self.assertNotIn("--project", joined(self.new("tool", "history", "rdprobe_flat")))


class ProjectTool(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_project_argument_has_the_library_tools_length_cap(self):
        self.real("backend/library/*.py", "backend/library/README.md")
        self.new("tool", "library", "rdprobe_proj", "--project")
        home = next(
            path for path in (self.tree / "backend/library").glob("*.py") if "RDPROBE_PROJ_TOOL" in path.read_text()
        )
        schema = next(
            node.value
            for node in ast.parse(home.read_text()).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "RDPROBE_PROJ_TOOL" for target in node.targets)
        )
        project = ast.literal_eval(schema)["parameters"]["properties"]["project"]
        # the cap the library's own project tools give the same argument
        library = (ROOT / "backend/library/tools.py").read_text()
        caps = set(re.findall(r'"project": \{\s*"type": "string",\s*"maxLength": (\d+)', library))
        self.assertEqual((project["type"], project.get("maxLength")), ("string", 4096))
        self.assertIn(str(project["maxLength"]), caps)


class ToolProject(ScaffoldCase):
    def test_root_is_narrowed_and_the_codes_in_use_are_listed(self):
        self.new("feature", "rdprobe_lib")
        write(self.tree, "backend/rdprobe_lib/tool_args.py", (ROOT / "backend/library/tool_args.py").read_text())
        # what it re-exports, where tool_project's own codes are written (as the real tree has it)
        write(self.tree, "backend/hermes/tool_args.py", (ROOT / "backend/hermes/tool_args.py").read_text())
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


class ToolRoundTenNew(ScaffoldCase):
    def test_a_library_project_tool_says_how_to_seed_the_last_build_and_that_call_works(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = joined(self.new("tool", "library", "rdprobe_built"))
        seed = re.search(r"host\._registry\(\)\.upsert\(str\(project\), build=\{[^}]*\}\)", steps)
        read = re.search(r"host\._registry\(\)\.get\(library\.game_id\(root\)\)\[\"lastBuild\"\]", steps)
        self.assertIsNotNone(seed, steps)
        self.assertIsNotNone(read, steps)
        script = SEEDED.format(root=str(ROOT), seed=seed and seed.group(0), read=read and read.group(0))
        done = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script)], cwd=ROOT, capture_output=True, text=True, timeout=120
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class ToolProjectRoundThree(ScaffoldCase):
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


class NewKinds(ScaffoldCase):
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
        self.assertIn(
            "`chromatic_rdprobe_mod` (`backend/history/rdprobe_extra.py`: ", self.read("docs/dev/CONTRACT.md")
        )
        self.new("tool", "history", "rdprobe_two", "--module", "rdprobe_extra")  # the same module again: once
        self.assertEqual(self.read("backend/history/tools.py").count("rdprobe_extra.TOOLS"), 1)
        self.assertEqual(self.read("backend/history/rdprobe_extra.py").count("Tool(RDPROBE_"), 2)
        out = self.new("tool", "history", "rdprobe_bad", "--module", "rpcs", code=1)
        self.assertIn("--module rpcs", out["error"]["message"])

    def test_module_refuses_a_name_tools_py_already_binds_and_nothing_changes(self):
        for name in ("__init__.py", "README.md"):
            shutil.copyfile(ROOT / "backend/library" / name, self.tree / "backend/library" / name)
        probe = "import json\n\nfrom ..hermes import host\nfrom . import games as library\n\nlogger = host.logger\nTOOLS = ()\n"
        write(self.tree, "backend/library/tools.py", probe)  # a probe: these bindings, whatever the real file holds
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Library tools")
        for module in ("json", "logger", "library"):  # a stdlib import, an assignment, `games as library`
            out = self.new("tool", "library", "rdprobe_ping", "--module", module, code=1)
            self.assertIn(f"backend/library/tools.py binds {module} already", out["error"]["message"])
            self.assertIn("--module", out["error"]["fix"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", f"--module {module} wrote something")
        self.new("tool", "library", "rdprobe_ping", "--module", "rdprobe_extra")  # a free name still works
        self.assertIn("from . import rdprobe_extra", self.read("backend/library/tools.py"))

    def test_module_refuses_a_name_the_front_door_binds_and_the_tree_is_unchanged(self):
        for name in ("__init__.py", "tools.py", "README.md", "game_card.py"):
            shutil.copyfile(ROOT / "backend/library" / name, self.tree / "backend/library" / name)
        index = self.read("backend/library/tools.py")  # the automatic <tool>_tools module needs tools.py over the
        pad = max(
            0, BIG_MODULE + 1 - len(index.splitlines())
        )  # limit: arrange it here, whatever the real file's length
        write(self.tree, "backend/library/tools.py", index + "# padding\n" * pad)
        self.assertGreater(len(self.read("backend/library/tools.py").splitlines()), BIG_MODULE)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Library front door")

        def snapshot():
            files = (p for p in sorted(self.tree.rglob("*")) if p.is_file() and ".git" not in p.parts)
            return {str(p.relative_to(self.tree)): p.read_bytes() for p in files}

        before = snapshot()
        for module, says in (
            ("read_json", "backend/library/__init__.py binds read_json"),  # `from .games import _json as read_json`
            ("cover_path", "backend/library/__init__.py binds cover_path"),  # a plain from-import
            ("EVENTS", "not a usable module name"),
            ("game_card", "backend/library/game_card.py exists and has no TOOLS"),  # `from . import game_card`
        ):
            out = self.new("tool", "library", "rdprobe_ping", "--module", module, code=1)
            self.assertIn(says, out["error"]["message"])
            self.assertEqual(snapshot(), before, f"--module {module} changed the tree")
        door = self.read("backend/library/__init__.py")  # the automatic <tool>_tools name is checked the same way
        write(self.tree, "backend/library/__init__.py", door + "\n__all__ += [\"rdprobe_ping_tools\"]\n")
        before = snapshot()
        out = self.new("tool", "library", "rdprobe_ping", code=1)
        self.assertIn("backend/library/__init__.py binds rdprobe_ping_tools", out["error"]["message"])
        self.assertEqual(snapshot(), before, "the automatic module name changed the tree")

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
