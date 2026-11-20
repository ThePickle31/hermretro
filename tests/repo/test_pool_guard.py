"""The unit run's thread pool stays safe from tests that change process-wide state.

`python tools/check.py unit` is one `unittest discover` process. Most packages (tests/backend, tests/repo,
tests/page's Python) run on the main thread, one test after another, so a test there may patch a module or the
environment: nothing else runs until it has put it back. A package whose ``__init__.py`` load_tests calls
``one_pool`` (tests/retrodev, tests/retrodev/pool.py) runs its tests on threads instead, as does any module with
``load_tests = parallel``; a module marked ``load_tests = alone`` leaves the pool and runs after it, by itself.

A pooled test that changes state every thread shares makes another thread's test fail now and then, or pass for
the wrong reason. So in a pooled module (and the helpers beside it, which its tests call), no code that runs
during a test (a function body, or a decorator on a test) may:

- patch a module attribute: ``mock.patch("pkg.mod.name")``, ``mock.patch.object(<imported name>, ...)``,
  ``mock.patch.dict(<imported name>.x)`` (os.environ, sys.modules), ``setattr(<imported name>, ...)`` or
  ``<imported name>.x = ...`` (sys.stdout, sys.stderr and sys.path included);
- redirect sys.stdout or sys.stderr (contextlib.redirect_stdout/redirect_stderr);
- write os.environ (item assignment, del, update/pop/setdefault/clear, os.putenv, os.unsetenv);
- change the working folder (os.chdir, contextlib.chdir);
- change sys.path (insert/append/extend/remove/pop/clear, item assignment);
- call isolated_home (it moves the environment and the host's data folder) or the event dispatcher's own table
  (events.on, events.emit).

Patching an object the test made itself (``self.x``, a local) is fine, and so is module-level code (it runs at
import, before the pool starts). A deliberate exception ends its line with the allowance comment for
the rule ``pool`` and its reason (tests/repo/allowances.py).
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo import allowances  # noqa: E402 - the repository root goes on sys.path first

FIX = "FIX: mark the module load_tests = alone, or patch an object the test owns"
PATCHES = {"patch", "patch.object", "patch.dict", "patch.multiple"}
ENVIRON_WRITES = {"update", "pop", "popitem", "setdefault", "clear", "__setitem__", "__delitem__"}
PATH_WRITES = {"insert", "append", "extend", "remove", "pop", "clear", "__setitem__", "__delitem__"}
REDIRECTS = {"redirect_stdout", "redirect_stderr"}


def _root(node: ast.AST) -> str | None:
    """The name a dotted expression starts from (`a` for a.b[c].d), or None for anything else (self.x is `self`)."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _imported(tree: ast.Module) -> set[str]:
    """Every name an import binds anywhere in the module: modules, and whatever `from x import y` brings in."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.asname or alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {alias.asname or alias.name for alias in node.names}
    return names


def _patch_kind(func: ast.AST) -> str | None:
    text = ast.unparse(func)
    for prefix in ("unittest.mock.", "mock."):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text if text in PATCHES else None


def _call_problem(call: ast.Call, imported: set[str]) -> str | None:
    func, text = call.func, ast.unparse(call.func)
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    first = call.args[0] if call.args else None
    kind = _patch_kind(func)
    if kind == "patch" and first is not None:
        return f"{text}({ast.unparse(first)}) patches a module attribute"
    if kind and first is not None and (isinstance(first, ast.Constant) or _root(first) in imported):
        return f"{text}({ast.unparse(first)}, ...) patches state every thread shares"
    if name == "setattr" and first is not None and _root(first) in imported:
        return f"setattr({ast.unparse(first)}, ...) changes a module attribute"
    if name in REDIRECTS:
        return f"{text}(...) redirects a stream every thread writes to"
    if text in ("os.chdir", "contextlib.chdir") or (name == "chdir" and text == "chdir" and "chdir" in imported):
        return f"{text}(...) changes the working folder of every thread"
    if text in ("os.putenv", "os.unsetenv"):
        return f"{text}(...) writes the process environment"
    if isinstance(func, ast.Attribute):
        owner = ast.unparse(func.value)
        if owner == "os.environ" and name in ENVIRON_WRITES:
            return f"{text}(...) writes the process environment"
        if owner == "sys.path" and name in PATH_WRITES:
            return f"{text}(...) changes sys.path"
        if owner == "events" and name in ("on", "emit"):
            return f"{text}(...) uses the event dispatcher's process-wide table"
    if name == "isolated_home":
        return "isolated_home(...) moves the environment and the host's data folder"
    return None


def _target_problem(target: ast.AST, imported: set[str], verb: str) -> str | None:
    if isinstance(target, (ast.Tuple, ast.List)):
        return next((p for p in (_target_problem(t, imported, verb) for t in target.elts) if p), None)
    if isinstance(target, (ast.Attribute, ast.Subscript)) and _root(target) in imported:
        return f"{verb} {ast.unparse(target)} changes state every thread shares"
    return None


def _node_problem(node: ast.AST, imported: set[str]) -> str | None:
    if isinstance(node, ast.Call):
        return _call_problem(node, imported)
    if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return next((p for p in (_target_problem(t, imported, "setting") for t in targets) if p), None)
    if isinstance(node, ast.Delete):
        return next((p for p in (_target_problem(t, imported, "deleting") for t in node.targets) if p), None)
    return None


def problems(source: str, file: str) -> list[str]:
    """Each place in one module's source where a test changes process-wide state: 'file:line: what'."""
    tree = ast.parse(source)
    imported = _imported(tree)
    allowed = allowances.in_text(source, file)
    found: list[str] = []

    def check(node: ast.AST) -> None:
        problem = _node_problem(node, imported)
        line = getattr(node, "lineno", 0)
        lines = range(line, (getattr(node, "end_lineno", None) or line) + 1)  # the allowance on any of its lines
        if problem and not any(allowances.allows(allowed, file, n, "pool") for n in lines):
            found.append(f"{file}:{line}: {problem}")

    def visit(node: ast.AST, running: bool) -> None:
        if running:
            check(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:  # a decorator on a test applies while the test runs
                for inner in ast.walk(decorator):
                    check(inner)
            inside = running or not isinstance(node, ast.ClassDef)
            for child in node.body:
                visit(child, inside)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, running)

    visit(tree, False)
    return sorted(set(found), key=lambda item: int(item.split(":")[1]))


def _load_tests(tree: ast.Module) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and [ast.unparse(t) for t in node.targets] == ["load_tests"]:
            return ast.unparse(node.value)
    return None


def pooled_modules(root: Path = ROOT) -> list[Path]:
    """Every Python file whose code runs on the pool's threads: all of a package that pools (its load_tests calls
    one_pool) but its `alone` modules and the pool itself, and any module with load_tests = parallel."""
    pooling = [init.parent for init in (root / "tests").rglob("__init__.py") if "one_pool(" in init.read_text()]
    found = set()
    for path in sorted((root / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text())
        how = _load_tests(tree)
        in_pool = any(folder in path.parents for folder in pooling)
        if how == "alone" or path.name in ("__init__.py", "pool.py"):
            continue
        if how == "parallel" or in_pool:
            found.add(path)
    return sorted(found)


class Guard(unittest.TestCase):
    def test_no_pooled_test_changes_process_wide_state(self):
        found = []
        for path in pooled_modules():
            found += problems(path.read_text(), str(path.relative_to(ROOT)))
        if found:
            self.fail(
                "these run on the unit pool's threads and change state they all share:\n"
                + "\n".join(found)
                + "\n"
                + FIX
            )

    def test_the_pool_covers_retrodev_and_only_packages_that_pool(self):
        pooled = {str(path.relative_to(ROOT)) for path in pooled_modules()}
        self.assertIn("tests/retrodev/test_land.py", pooled)
        self.assertIn("tests/retrodev/fixture.py", pooled)
        self.assertNotIn("tests/retrodev/test_state_override.py", pooled)  # load_tests = alone
        self.assertFalse([p for p in pooled if not p.startswith("tests/retrodev/")], pooled)


PLANTED = {
    "mock.patch('retrodev.cli.run')": "patches a module attribute",
    "mock.patch.object(cli, 'run', None)": "mock.patch.object(cli, ...)",
    "patch.object(os.path, 'exists')": "patch.object(os.path, ...)",
    "mock.patch.dict(os.environ, {'A': '1'})": "mock.patch.dict(os.environ, ...)",
    "mock.patch('sys.stdout', io.StringIO())": "mock.patch('sys.stdout')",
    "mock.patch.object(sys, 'stderr', io.StringIO())": "mock.patch.object(sys, ...)",
    "contextlib.redirect_stdout(io.StringIO())": "redirects a stream",
    "sys.stdout = io.StringIO()": "setting sys.stdout",
    "os.environ['A'] = '1'": "setting os.environ['A']",
    "del os.environ['A']": "deleting os.environ['A']",
    "os.environ.update(A='1')": "os.environ.update(...)",
    "os.putenv('A', '1')": "os.putenv(...)",
    "os.chdir('/')": "os.chdir(...)",
    "sys.path.insert(0, 'x')": "sys.path.insert(...)",
    "sys.path[:] = []": "setting sys.path[:]",
    "setattr(cli, 'X', 1)": "setattr(cli, ...)",
    "cli.X = 1": "setting cli.X",
    "isolated_home(self)": "isolated_home(...)",
    "events.emit('x')": "events.emit(...)",
}
HEADER = "import contextlib, io, os, sys\nfrom unittest import mock\nfrom unittest.mock import patch\nfrom retrodev import cli\n"


class Rules(unittest.TestCase):
    """The guard bites on each kind of change, and leaves alone what the test owns and what runs at import."""

    def test_each_planted_change_is_named_with_its_line(self):
        for code, words in PLANTED.items():
            with self.subTest(code=code):
                source = HEADER + f"class T:\n    def test(self):\n        {code}\n"
                self.assertEqual(len(found := problems(source, "tests/x.py")), 1, found)
                self.assertTrue(found[0].startswith("tests/x.py:7: "), found)
                self.assertIn(words, found[0])

    def test_a_decorator_on_a_test_counts(self):
        source = HEADER + "class T:\n    @mock.patch.object(cli, 'run')\n    def test(self, run):\n        pass\n"
        found = problems(source, "tests/x.py")
        self.assertEqual(found, ["tests/x.py:6: mock.patch.object(cli, ...) patches state every thread shares"])

    def test_objects_the_test_owns_and_import_time_code_pass(self):
        source = HEADER + (
            "sys.path.insert(0, 'tools')\nload_tests = None\n"
            "class T:\n    def test(self):\n        box = {}\n"
            "        mock.patch.dict(box, {'a': 1}).start()\n        mock.patch.object(self.stub, 'x').start()\n"
            "        self.out = io.StringIO()\n        env = dict(os.environ)\n        env['A'] = '1'\n"
            "        fake = object()\n        mock.patch.object(fake, 'x')\n"
        )
        self.assertEqual(problems(source, "tests/x.py"), [])

    def test_an_allowance_with_a_reason_lets_one_line_through(self):
        line = "        os.chdir('/')  # retrodev" + ": allow pool — the test runs alone when called directly\n"
        source = HEADER + "class T:\n    def test(self):\n" + line
        self.assertEqual(problems(source, "tests/x.py"), [])
        self.assertTrue(problems(source.replace(" — the test runs alone when called directly", ""), "tests/x.py"))


if __name__ == "__main__":
    unittest.main()
