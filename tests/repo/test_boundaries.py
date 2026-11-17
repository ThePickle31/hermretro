"""How backend features connect, checked from the source alone (AST, no imports, fast).

A feature lives in backend/<feature>/ and connects to others only through what they expose, so a change
inside one feature cannot quietly break another:

- A module may import the standard library, its own feature, backend.system and backend.hermes (the shared
  layers), and another feature only through its front door: ``from .. import library`` or
  ``from ..library import Registry``, using names in that front door's ``__all__``.
- backend.system imports nothing of ours outside itself; only backend.hermes imports backend.features.
- A front door (``backend/<feature>/__init__.py``) has a literal ``__all__`` of names it binds, and never
  imports a private name except under a public alias listed in ``__all__``.
- Events: each name is declared once, in its owner's front door ``EVENTS`` (``<owner>.<what happened>``),
  emitted only by the owner, listened to only from a feature's listeners.py, and always a literal.
- backend/features.py lists every feature folder once.

A line may break a rule on purpose with ``# retrodev: allow <rule> — <reason>`` (tests/repo/allowances.py).
Run alone: python -m unittest tests.repo.test_boundaries
"""

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo import allowances  # noqa: E402

SHARED = ("system", "hermes")


def features(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "backend").iterdir() if p.is_dir() and (p / "__init__.py").is_file())


def module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(root: Path, path: Path):
    """(line, target module, imported names or None) for every import in the file, relative ones resolved."""
    name = module_name(root, path)
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, None, alias.asname
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                source = ".".join(base + ([node.module] if node.module else []))
            else:
                source = node.module or ""
            yield node.lineno, source, [(a.name, a.asname) for a in node.names], None


def front_door(root: Path, feature: str) -> dict:
    """``__all__`` and ``EVENTS`` of a front door, read as literals."""
    tree = ast.parse((root / "backend" / feature / "__init__.py").read_text(encoding="utf-8"))
    found = {"__all__": None, "EVENTS": None, "bound": set(), "tree": tree}
    for node in tree.body:
        targets = [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        for target in targets:
            if isinstance(target, ast.Name) and target.id in ("__all__", "EVENTS"):
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    found[target.id] = "not a literal"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found["bound"] |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found["bound"].add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            found["bound"] |= {t.id for t in targets if isinstance(t, ast.Name)}
    return found


def event_uses(path: Path):
    """(line, "emit" | "on", event name or None when not a literal) for every emit()/on() call."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if called in ("emit", "on"):
                first = node.args[0] if node.args else None
                literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
                yield node.lineno, called, literal


def check(root: Path) -> list[tuple[str, str, int, str]]:
    """Every broken rule as (rule, file, line, message). Allowances are applied by the caller."""
    problems = []
    names = features(root)
    doors = {feature: front_door(root, feature) for feature in names}
    exported = {feature: set(door["__all__"] or []) for feature, door in doors.items()}
    for feature, door in doors.items():
        where = f"backend/{feature}/__init__.py"
        if not isinstance(door["__all__"], list):
            problems.append(
                ("front-door-export", where, 1, "has no literal __all__ list (what other features may use)")
            )
            continue
        for missing in sorted(set(door["__all__"]) - door["bound"]):
            problems.append(("front-door-export", where, 1, f"__all__ names {missing!r}, which it does not define"))
        if feature not in SHARED and not isinstance(door["EVENTS"], dict):
            problems.append(("event", where, 1, "has no literal EVENTS dict (the events it emits; {} for none)"))
        for node in door["tree"].body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (
                        alias.name.startswith("_")
                        and (alias.asname or alias.name) not in door["__all__"]
                        and not (alias.asname or "").startswith("_")
                    ):
                        problems.append(
                            (
                                "front-door-export",
                                where,
                                node.lineno,
                                f"re-exports the private {alias.name!r} without listing a public alias in __all__",
                            )
                        )
    declared: dict[str, list[str]] = {}
    for feature, door in doors.items():
        for event in door["EVENTS"] if isinstance(door["EVENTS"], dict) else {}:
            declared.setdefault(event, []).append(feature)
            if event.split(".")[0] != feature:
                problems.append(
                    (
                        "event",
                        f"backend/{feature}/__init__.py",
                        1,
                        f"declares {event!r}; a feature declares only its own events ({feature}.<what happened>)",
                    )
                )
    for event, owners in declared.items():
        if len(owners) > 1:
            problems.append(("event", f"backend/{owners[1]}/__init__.py", 1, f"{event!r} is declared by {owners}"))
    emitted = set()
    for path in sorted((root / "backend").rglob("*.py")):
        rel = str(path.relative_to(root))
        parts = path.relative_to(root / "backend").parts
        feature = parts[0] if len(parts) > 1 else None
        checked = []
        for line, target, imported, _asname in imports(root, path):
            if target == "backend" and imported:
                # `from backend import library` / `from .. import features` import modules: judge each as
                # `import backend.<name>`, so the layer rules apply to them too.
                for name, _alias in imported:
                    checked.append((line, f"backend.{name}", None))
                continue
            checked.append((line, target, imported))
        for line, target, imported in checked:
            pieces = target.split(".")
            if pieces[0] != "backend":
                continue
            other = pieces[1] if len(pieces) > 1 else None
            if other == "features":
                if feature != "hermes":
                    problems.append(
                        ("layer", rel, line, "imports backend.features; only the Hermes layer registers features")
                    )
                continue
            if feature == "system" and other is not None and other != "system":
                problems.append(
                    ("layer", rel, line, f"backend.system imports backend.{other}; system is the bottom layer")
                )
                continue
            if other is None:  # `import backend`
                continue
            if other == feature or other in SHARED or feature is None:
                continue
            if len(pieces) > 2:
                problems.append(("front-door", rel, line, f"imports {target}, inside the {other} feature"))
            for name, _alias in imported or []:
                if name not in exported.get(other, set()):
                    problems.append(
                        (
                            "front-door",
                            rel,
                            line,
                            f"imports {name!r} from backend.{other}, which its front door does not export (__all__)",
                        )
                    )
        problems += attribute_uses(root, path, rel, feature, names, exported)
        for line, kind, event in event_uses(path):
            if event is None:
                problems.append(("event", rel, line, f"{kind}() with a name that is not a string literal"))
            elif event not in declared:
                problems.append(("event", rel, line, f"{kind}({event!r}): no front door declares it in EVENTS"))
            elif kind == "emit" and feature not in declared[event]:
                problems.append(
                    ("event", rel, line, f"emits {event!r}, owned by {declared[event][0]}; only the owner emits")
                )
            elif kind == "on" and path.name != "listeners.py":
                problems.append(("event", rel, line, f"listens to {event!r} outside a listeners.py"))
            if kind == "emit":
                emitted.add(event)
    for event in sorted(set(declared) - emitted):
        problems.append(
            ("event", f"backend/{declared[event][0]}/__init__.py", 1, f"declares {event!r}, which nothing emits")
        )
    listed = feature_list(root)
    expected = [name for name in names if name != "system"]
    if sorted(listed) != expected or len(listed) != len(set(listed)):
        problems.append(
            ("layer", "backend/features.py", 1, f"FEATURES lists {listed}; every feature folder once: {expected}")
        )
    return problems


def attribute_uses(root, path, rel, feature, names, exported):
    """``alias.name`` (or ``backend.<feature>.name``) where alias is another feature's front door: the name must
    be exported. Covers `from backend import library [as x]`, `from .. import library`, `import backend.library
    as x` and plain `import backend.library`."""
    aliases = {}
    qualified = False
    for _line, target, imported, asname in imports(root, path):
        if target == "backend" and imported:
            for name, alias in imported:
                if name in names and name not in SHARED and name != feature:
                    aliases[alias or name] = name
        elif imported is None and target.startswith("backend."):
            other = target.split(".")[1]
            if len(target.split(".")) == 2 and other in names and other not in SHARED and other != feature:
                if asname:
                    aliases[asname] = other
                else:
                    qualified = True
    found = []
    if not aliases and not qualified:
        return found
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Attribute):
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id in aliases:
            other, shown = aliases[value.id], value.id
        elif (
            qualified
            and isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "backend"
            and value.attr in names
            and value.attr not in SHARED
            and value.attr != feature
        ):
            other, shown = value.attr, f"backend.{value.attr}"
        else:
            continue
        if node.attr not in exported.get(other, set()):
            found.append(
                (
                    "front-door",
                    rel,
                    node.lineno,
                    f"uses {shown}.{node.attr}, which backend.{other}'s front door does not export (__all__)",
                )
            )
    return found


def feature_list(root: Path) -> list[str]:
    tree = ast.parse((root / "backend" / "features.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FEATURES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    return []


FIXES = {
    "front-door": "import the feature's front door (from .. import <feature>) and use only names in its __all__; if "
    "you need more, export it there (backend/<feature>/__init__.py) or connect through an event",
    "layer": "move the code to the layer that may know about it (backend/hermes registers features; backend/system "
    "receives what it needs, as system/hermes_home.py does)",
    "front-door-export": "list the public name in __all__ (import a private one under a public alias)",
    "event": "declare the event once in its owner's front door EVENTS ('<owner>.<what happened>': 'payload'), emit it "
    "only there, listen from backend/<feature>/listeners.py, and use string literals",
}


def report(problems, allowed) -> str:
    lines = [
        f"{file}:{line}: [{rule}] {message}"
        for rule, file, line, message in problems
        if not allowances.allows(allowed, file, line, rule)
    ]
    if not lines:
        return ""
    rules = sorted({rule for rule, file, line, _ in problems if not allowances.allows(allowed, file, line, rule)})
    return (
        "\nBackend features connect only through what they expose, so changing one cannot quietly break another:\n  "
        + "\n  ".join(lines)
        + "\n"
        + "\n".join(f"FIX ({rule}): {FIXES[rule]}" for rule in rules)
        + "\n(A deliberate exception: end the line with '# retrodev: allow <rule> — <reason>'.)"
    )


def tracked(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "backend"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return [name for name in out.split("\0") if name]


class Boundaries(unittest.TestCase):
    def test_backend_features_connect_only_through_front_doors_and_declared_events(self):
        allowed = allowances.in_files(ROOT, tracked(ROOT))
        self.assertEqual(
            [a.problem() for a in allowed if a.problem()],
            [],
            "malformed allowances\nFIX: name a known rule and give the reason after '—'",
        )
        message = report(check(ROOT), allowed)
        self.assertFalse(message, message)

    def test_the_check_bites(self):
        """Plant one break of each kind in a copy of backend/ and see each reported (and an allowance honoured)."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            shutil.copytree(ROOT / "backend", copy / "backend", ignore=shutil.ignore_patterns("__pycache__"))
            assets = copy / "backend" / "assets" / "planted.py"
            reason = "# retrodev" + ": allow front-door — "
            assets.write_text(
                "from ..library.games import _json\n"
                "from .. import player\n"
                "from ..system.events import emit, on\n"
                "player.server\n"
                "emit('assets.not_declared')\n"
                "emit('library.build_reported')\n"
                "from ..library.games import Registry  " + reason + "planted on purpose\n"
                "from ..library.games import game_id  " + reason + "\n"
            )
            (copy / "backend" / "system" / "planted.py").write_text(
                "from ..hermes import api\nfrom .. import library\n"
            )
            (copy / "backend" / "library" / "planted_registry.py").write_text("from .. import features\n")
            (copy / "backend" / "setup" / "planted_alias.py").write_text(
                "import backend.library as lib\nimport backend.library\n\nlib.games\nbackend.library.games\n"
            )
            problems = check(copy)
            allowed = allowances.in_text(assets.read_text(), "backend/assets/planted.py")
            text = report(problems, allowed)
            for expected in (
                "planted.py:1: [front-door] imports backend.library.games",
                "planted.py:4: [front-door] uses player.server",
                "planted.py:5: [event] emit('assets.not_declared')",
                "planted.py:6: [event] emits 'library.build_reported', owned by library",
                "planted.py:8: [front-door]",
                "backend/system/planted.py:1: [layer]",
                "backend/system/planted.py:2: [layer] backend.system imports backend.library",
                "backend/library/planted_registry.py:1: [layer] imports backend.features",
                "backend/setup/planted_alias.py:4: [front-door] uses lib.games",
                "backend/setup/planted_alias.py:5: [front-door] uses backend.library.games",
            ):
                self.assertIn(expected, text)
            self.assertNotIn("planted.py:7:", text)  # allowed, with a reason
            self.assertIn("no reason", allowed[1].problem())  # the allowance without a reason is refused


if __name__ == "__main__":
    unittest.main()
