"""The broker runs as `python -m backend.broker` from the plugin folder, with a minimal environment and no
Hermes on the path. Everything it can import must therefore be the standard library or backend modules that
are themselves standard-library only: never backend.hermes, never a feature's Hermes-side modules (rpcs.py,
tools.py, hooks.py, listeners.py), and never events (listeners live in the gateway, not in the broker).
The feature front doors the broker uses (backend.library, backend.setup) therefore stay stdlib-only too.

There are no exceptions: backend.system learns the Hermes home from the Hermes layer (system/hermes_home.py)
instead of importing it."""

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

HERMES_SIDE = ("rpcs", "tools", "hooks", "listeners")


def module_file(name: str) -> Path | None:
    base = ROOT.joinpath(*name.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def imports(name: str) -> tuple[set[str], set[str]]:
    """Every module ``name`` imports anywhere in its file (top level or inside functions):
    (backend modules, top-level names of everything else)."""
    path = module_file(name)
    assert path is not None, f"no file for {name}"
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    inside, outside = set(), set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                (inside if alias.name.split(".")[0] == "backend" else outside).add(
                    alias.name if alias.name.startswith("backend") else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                source = ".".join(base + ([node.module] if node.module else []))
            else:
                source = node.module or ""
            if source.split(".")[0] != "backend":
                outside.add(source.split(".")[0])
                continue
            for alias in node.names:  # `from . import paths` names a module; `from .lane import Denied` does not
                submodule = f"{source}.{alias.name}"
                inside.add(submodule if module_file(submodule) else source)
    # A module's parent packages run first.
    parts = name.split(".")
    inside |= {".".join(parts[:index]) for index in range(1, len(parts))}
    return inside - {name}, outside


def reachable() -> tuple[set[str], set[str], set[tuple[str, str]]]:
    start = ["backend.broker"] + [
        f"backend.broker.{path.stem}" for path in (BACKEND / "broker").glob("*.py") if path.stem != "__init__"
    ]
    seen, external, edges, todo = set(), set(), set(), list(start)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        inside, outside = imports(name)
        external |= outside
        for target in inside:
            edges.add((name, target))
            todo.append(target)
    return seen, external, edges


class BrokerImports(unittest.TestCase):
    def test_the_broker_reaches_only_the_standard_library_and_stdlib_only_backend_modules(self):
        seen, external, edges = reachable()
        self.assertIn("backend.broker.server", seen)
        self.assertIn("backend.system.paths", seen)
        self.assertEqual(
            external - set(sys.stdlib_module_names) - {"__future__"},
            set(),
            "the broker imports something outside the standard library",
        )
        hermes = sorted(f"{a} -> {b}" for a, b in edges if b.startswith("backend.hermes"))
        self.assertEqual(
            hermes,
            [],
            "the broker must not import backend.hermes (it runs without Hermes)\nFIX: hand "
            "the value over from the Hermes side (as system/hermes_home.py does), or move the code out "
            "of the modules the broker imports",
        )
        self.assertEqual(
            sorted(name for name in seen if name.rpartition(".")[2] in HERMES_SIDE),
            [],
            "the broker must not import a feature's rpcs.py, tools.py, hooks.py or listeners.py\nFIX: "
            "import the feature's front door (backend.<feature>), and keep that front door stdlib-only",
        )
        self.assertNotIn(
            "backend.system.events",
            seen,
            "the broker must not emit events: their listeners live in the "
            "gateway\nFIX: emit from the Hermes side (an RPC, tool or hook) instead",
        )

    def test_importing_the_broker_loads_no_hermes_side_module(self):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); import backend.broker.server, backend.broker.client; "
            "print(' '.join(sorted(m for m in sys.modules if m.startswith('backend'))))"
        )
        env = {"PATH": os.environ.get("PATH", ""), "HERMRETRO_HOME": "/nonexistent-hermretro-home"}
        done = subprocess.run(
            [sys.executable, "-I", "-c", code, str(ROOT)],
            env=env,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        loaded = done.stdout.split()
        self.assertIn("backend.broker.server", loaded)
        self.assertEqual([name for name in loaded if name.startswith("backend.hermes")], [])


if __name__ == "__main__":
    unittest.main()
