"""The trial rounds' regressions for this area (RoundSevenNew, RoundSixNew), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_rpc_module
"""

import ast
import re
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.hand_edits import line_of
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

load_tests = parallel


def rpcs_parts(line: str) -> tuple[str, str, str]:
    """(files, names, trailing text) of a README's '- RPCs (`rpcs.py`, ...): `a`, `b`. ...' line."""
    parts = RPCS_LINE.match(line)
    assert parts, f"not an RPCs line naming its files: {line}"
    return parts.group(1), parts.group(2), parts.group(3)


def module_added(before: str, module: str, name: str) -> str:
    """The README RPCs line ``before`` with ``module`` appended to its files and ``name`` to its RPCs, the files
    and names it held and its trailing text kept (derived from the line read before new ran, never pinned)."""
    files, names, tail = rpcs_parts(before)
    return f"- RPCs ({files}, `{module}.py`): {names}, `{name}`{tail}"


def rpc_names():
    """tools/bundle/rpc_names.py: the generator of the page's RPC names, which reads @rpc in rpcs.py only."""
    spec = importlib.util.spec_from_file_location("rpc_names_probe", ROOT / "tools/bundle/rpc_names.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_in_copy(case, code: str) -> str:
    """``code`` run by Python in the scaffolded copy (the rest of the real backend copied in, never over what new
    wrote), with a throwaway home."""
    for path in (ROOT / "backend").rglob("*.py"):
        mine = case.tree / path.relative_to(ROOT)
        if not mine.exists():
            mine.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, mine)
    home = tempfile.mkdtemp(dir=case.tree.parent)
    env = {**os.environ, "HOME": home, "HERMRETRO_HOME": home, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=case.tree, env=env, capture_output=True, text=True, check=False
    )
    case.assertEqual(done.returncode, 0, done.stderr)
    return done.stdout


RPCS_LINE = re.compile(r"^- RPCs \(([^)]*)\): (.*?)(\.(?:\s.*)?)$")


class RpcRoundSevenNew(ScaffoldCase):
    def test_module_keeps_the_rpc_modules_and_the_text_the_line_holds_already(self):  # review 1, 2
        readme = self.read("backend/history/README.md")
        files, names, tail = rpcs_parts(line_of(readme, "- RPCs"))
        grown = f"- RPCs ({files}, `rdprobe_old_rpcs.py`): {names}, `rdprobe_old`{tail} (x)"
        write(self.tree, "backend/history/README.md", readme.replace(line_of(readme, "- RPCs"), grown, 1))
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "An RPC sibling module listed already")
        self.new("rpc", "history", "rdprobe_pong", "--module", "rdprobe_pong_rpcs")
        after = line_of(self.read("backend/history/README.md"), "- RPCs")
        self.assertEqual(after, module_added(grown, "rdprobe_pong_rpcs", "rdprobe_pong"))
        self.assertIn("`rdprobe_old_rpcs.py`, `rdprobe_pong_rpcs.py`): ", after)
        self.assertTrue(after.endswith(" (x)"), after)


class RpcRoundSixNew(ScaffoldCase):
    def test_module_puts_the_handler_in_its_own_file_and_keeps_the_declaration_in_rpcs_py(self):
        out = self.new("rpc", "history", "rdprobe_pong", "--module", "rdprobe_pong_rpcs")
        home = self.read("backend/history/rdprobe_pong_rpcs.py")
        self.assertIn("def rpc_rdprobe_pong(ctx):", home)
        self.assertNotIn("@rpc", home)
        self.assertIn("logger = host.logger", home)
        source = self.read("backend/history/rpcs.py")
        self.assertIn("from . import rdprobe_pong_rpcs as _rdprobe_pong_rpcs_mod", source)
        self.assertIn('@rpc("rdprobe_pong")\ndef rpc_rdprobe_pong(ctx):', source)
        self.assertIn("    return _rdprobe_pong_rpcs_mod.rpc_rdprobe_pong(ctx)", source)
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
        self.assertIn("give the next one its own module (python tools/retrodev new rpc history <name> --module", out)
        out = self.new("rpc", "history", "rdprobe_small", "--module", "rdprobe_small_rpcs", as_json=False)
        self.assertNotIn("note: backend/history/rpcs.py has", out)

    def test_module_never_shadows_the_wrapper_or_what_a_new_rpcs_py_binds(self):
        out = self.new("rpc", "history", "rdprobe_ping", "--module", "rpc_rdprobe_ping", code=1)
        self.assertIn("nothing was written", out["error"]["message"])
        self.assertIn("--module rdprobe_ping_rpcs", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
        self.new("feature", "rdprobe_fresh")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Probe feature")
        self.assertFalse((self.tree / "backend/rdprobe_fresh/rpcs.py").exists())
        for module in ("rpc", "host", "logger"):  # the template's bindings when rpcs.py is new
            out = self.new("rpc", "rdprobe_fresh", "rdprobe_ping", "--module", module, code=1)
            self.assertIn(f"binds {module} already", out["error"]["message"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", f"--module {module} wrote something")

    def test_a_new_rpc_never_rebinds_an_earlier_rpcs_module_and_both_factories_run(self):
        # Review round 2: the second wrapper (rpc_rdprobe_two) once replaced the first one's module import, so
        # rdprobe_one's factory raised AttributeError when the plugin registered it.
        self.new("rpc", "history", "rdprobe_one", "--module", "rpc_rdprobe_two")
        self.new("rpc", "history", "rdprobe_two", "--module", "rdprobe_two_rpcs")
        source = self.read("backend/history/rpcs.py")
        self.assertIn("from . import rpc_rdprobe_two as _rpc_rdprobe_two_mod", source)
        self.assertIn("from . import rdprobe_two_rpcs as _rdprobe_two_rpcs_mod", source)
        probe = (
            "from backend.history import rpcs\n"
            "for name in ('rdprobe_one', 'rdprobe_two'):\n"
            "    answer = getattr(rpcs, 'rpc_' + name)(None)({'echo': name})\n"
            "    assert answer == {'ok': True, 'echo': name}, answer\n"
            "print('both ran')\n"
        )
        self.assertIn("both ran", run_in_copy(self, probe))

    def test_a_generated_name_rpcs_py_binds_already_is_refused_before_writing(self):
        source = self.read("backend/history/rpcs.py")
        write(self.tree, "backend/history/rpcs.py", source + "\n\nrpc_rdprobe_taken = None\n_rdprobe_mine_mod = 1\n")
        git(self.tree, "commit", "-qam", "Names taken")
        taken = (
            ("rdprobe_taken",),
            ("rdprobe_taken", "--module", "rdprobe_taken_rpcs"),
            ("x", "--module", "rdprobe_mine"),
        )
        for args in taken:
            out = self.new("rpc", "history", *args, code=1)
            self.assertIn("binds", out["error"]["message"])
            self.assertIn("nothing was written", out["error"]["message"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", f"{args} wrote something")
