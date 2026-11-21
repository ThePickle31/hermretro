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
  ``<imported name>.x = ...`` (sys.stdout, sys.stderr and sys.path included); a patch's target counts whether it
  is the first argument or the keyword (target=, in_dict= for patch.dict), whatever name mock or patch is imported
  under, and whether the patch is a context manager, a decorator or started with .start();
- redirect sys.stdout or sys.stderr (contextlib.redirect_stdout/redirect_stderr);
- write os.environ (item assignment, del, update/pop/setdefault/clear, os.putenv, os.unsetenv; also through
  ``from os import environ``, as sys.path below through ``from sys import path``);
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


def _imported(tree: ast.Module) -> dict[str, str]:
    """Every name an import binds anywhere in the module, with the dotted name it stands for: `import os as o` binds
    o to os, `from unittest import mock as m` m to unittest.mock, `from os import environ` environ to os.environ."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            for alias in node.names:
                names[alias.asname or alias.name] = f"{prefix}.{alias.name}" if node.module else prefix + alias.name
    return names


def _qualified(node: ast.AST, imported: dict[str, str]) -> str:
    """A dotted expression with the import its first name stands for spelled out (m.patch -> unittest.mock.patch)."""
    text, base = ast.unparse(node), node
    while isinstance(base, ast.Attribute):
        base = base.value
    if isinstance(base, ast.Name) and base.id in imported:
        return imported[base.id] + text[len(base.id) :]
    return text


def _patch_kind(func: ast.AST, imported: dict[str, str]) -> str | None:
    text = _qualified(func, imported)
    for prefix in ("unittest.mock.", "mock."):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text if text in PATCHES else None


def _patch_target(call: ast.Call, kind: str) -> ast.AST | None:
    """What a patch call changes: its first argument, or the keyword that names it (in_dict= for patch.dict, target=
    for the others); None for a patch given neither."""
    if call.args:
        return call.args[0]
    key = "in_dict" if kind == "patch.dict" else "target"
    return next((keyword.value for keyword in call.keywords if keyword.arg == key), None)


def _call_problem(call: ast.Call, imported: dict[str, str]) -> str | None:
    func, text = call.func, ast.unparse(call.func)
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    full = _qualified(func, imported)
    first = call.args[0] if call.args else None
    kind = _patch_kind(func, imported)
    target = _patch_target(call, kind) if kind else None
    if kind == "patch" and target is not None:
        return f"{text}({ast.unparse(target)}) patches a module attribute"
    if kind and target is not None and (isinstance(target, ast.Constant) or _root(target) in imported):
        return f"{text}({ast.unparse(target)}, ...) patches state every thread shares"
    if name == "setattr" and first is not None and _root(first) in imported:
        return f"setattr({ast.unparse(first)}, ...) changes a module attribute"
    if name in REDIRECTS:
        return f"{text}(...) redirects a stream every thread writes to"
    if full in ("os.chdir", "contextlib.chdir"):
        return f"{text}(...) changes the working folder of every thread"
    if full in ("os.putenv", "os.unsetenv"):
        return f"{text}(...) writes the process environment"
    if full.endswith(("events.on", "events.emit")) and (full.startswith("events.") or _root(func) in imported):
        return f"{text}(...) uses the event dispatcher's process-wide table"
    if isinstance(func, ast.Attribute):
        owner = _qualified(func.value, imported)
        if owner == "os.environ" and name in ENVIRON_WRITES:
            return f"{text}(...) writes the process environment"
        if owner == "sys.path" and name in PATH_WRITES:
            return f"{text}(...) changes sys.path"
    if name == "isolated_home":
        return "isolated_home(...) moves the environment and the host's data folder"
    return None


def _target_problem(target: ast.AST, imported: dict[str, str], verb: str) -> str | None:
    if isinstance(target, (ast.Tuple, ast.List)):
        return next((p for p in (_target_problem(t, imported, verb) for t in target.elts) if p), None)
    if isinstance(target, (ast.Attribute, ast.Subscript)) and _root(target) in imported:
        return f"{verb} {ast.unparse(target)} changes state every thread shares"
    return None


def _node_problem(node: ast.AST, imported: dict[str, str]) -> str | None:
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
    # review 2, 0: the target given by keyword, an aliased mock or patch, .start(), names imported from os and sys
    "mock.patch(target='platform.system', return_value='Darwin')": "mock.patch('platform.system') patches",
    "mock.patch.object(target=cli, attribute='run')": "mock.patch.object(cli, ...)",
    "mock.patch.dict(in_dict=os.environ, values={'A': '1'})": "mock.patch.dict(os.environ, ...)",
    "patch.dict(in_dict='os.environ', values={'A': '1'})": "patch.dict('os.environ', ...)",
    "mock.patch.multiple(target=cli, run=None)": "mock.patch.multiple(cli, ...)",
    "mock.patch(target='retrodev.cli.run').start()": "mock.patch('retrodev.cli.run') patches",
    "um.patch('retrodev.cli.run')": "um.patch('retrodev.cli.run') patches",
    "um.patch.object(target=cli, attribute='run')": "um.patch.object(cli, ...)",
    "mk.patch.dict(os.environ)": "mk.patch.dict(os.environ, ...)",
    "p(target='retrodev.cli.run')": "p('retrodev.cli.run') patches",
    "p.object(cli, 'run')": "p.object(cli, ...)",
    "environ['A'] = '1'": "setting environ['A']",
    "environ.update(A='1')": "environ.update(...)",
    "putenv('A', '1')": "putenv(...)",
    "path.insert(0, 'x')": "path.insert(...)",
    "events.on('x', print)": "events.on(...)",
}
HEADER = (
    "import contextlib, io, os, sys\nfrom unittest import mock\nfrom unittest.mock import patch\nfrom retrodev import cli\n"
    "import unittest.mock as um\nfrom unittest import mock as mk\nfrom unittest.mock import patch as p\n"
    "from os import environ, putenv\nfrom sys import path\nfrom backend.system import events\n"
)
LINE = HEADER.count("\n") + 3  # the line of the planted code: the header, `class T:`, `def test(self):`


class Rules(unittest.TestCase):
    """The guard bites on each kind of change, and leaves alone what the test owns and what runs at import."""

    def test_each_planted_change_is_named_with_its_line(self):
        for code, words in PLANTED.items():
            with self.subTest(code=code):
                source = HEADER + f"class T:\n    def test(self):\n        {code}\n"
                self.assertEqual(len(found := problems(source, "tests/x.py")), 1, found)
                self.assertTrue(found[0].startswith(f"tests/x.py:{LINE}: "), found)
                self.assertIn(words, found[0])

    def test_a_keyword_target_in_a_decorator_counts_on_a_test_and_on_a_class(self):  # review 2, 0
        for decorator, words in (
            ("@mock.patch.object(cli, 'run')", "mock.patch.object(cli, ...)"),
            ("@mock.patch(target='platform.system', return_value='Darwin')", "mock.patch('platform.system') patches"),
            ("@um.patch.object(target=cli, attribute='run')", "um.patch.object(cli, ...)"),
            ("@p.dict(in_dict=os.environ, values={'A': '1'})", "p.dict(os.environ, ...)"),
        ):
            with self.subTest(decorator=decorator):
                on_test = HEADER + f"class T:\n    {decorator}\n    def test(self, *mocks):\n        pass\n"
                on_class = HEADER + f"{decorator}\nclass T:\n    def test(self, *mocks):\n        pass\n"
                for source, line in ((on_test, LINE - 1), (on_class, LINE - 2)):
                    found = problems(source, "tests/x.py")
                    self.assertEqual(len(found), 1, found)
                    self.assertTrue(found[0].startswith(f"tests/x.py:{line}: "), found)
                    self.assertIn(words, found[0])

    def test_objects_the_test_owns_and_import_time_code_pass(self):
        source = HEADER + (
            "sys.path.insert(0, 'tools')\nload_tests = None\n"
            "class T:\n    def test(self):\n        box = {}\n"
            "        mock.patch.dict(box, {'a': 1}).start()\n        mock.patch.object(self.stub, 'x').start()\n"
            "        self.out = io.StringIO()\n        env = dict(os.environ)\n        env['A'] = '1'\n"
            "        fake = object()\n        mock.patch.object(fake, 'x')\n"
            "        mock.patch.object(target=self.stub, attribute='x').start()\n        mock.patch.dict(in_dict=box)\n"
            "        um.patch.object(target=fake, attribute='x')\n        self.events.emit('x')\n"
            "        mock.patch(new=1)\n"
        )
        self.assertEqual(problems(source, "tests/x.py"), [])

    def test_an_allowance_with_a_reason_lets_one_line_through(self):
        line = "        os.chdir('/')  # retrodev" + ": allow pool — the test runs alone when called directly\n"
        source = HEADER + "class T:\n    def test(self):\n" + line
        self.assertEqual(problems(source, "tests/x.py"), [])
        self.assertTrue(problems(source.replace(" — the test runs alone when called directly", ""), "tests/x.py"))


if __name__ == "__main__":
    unittest.main()
