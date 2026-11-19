"""`new rpc --module <name>`: the RPC's handler factory in backend/<feature>/<name>.py, declared in rpcs.py.

tools/bundle/rpc_names.py (the page's generated RPC names) and tests/repo/test_lockstep.py read the @rpc
declarations in backend/*/rpcs.py only, and backend/hermes/declare.py collects what rpcs.py declares: so the
@rpc stays in rpcs.py, as a short function that calls the factory in the module (``from . import <name>``), and the
handler's code lives in the module. Without --module, an rpcs.py over BIG_RPCS lines gets a note suggesting it.
Nothing is written here: it fills scaffold.py's Plan.
"""

from __future__ import annotations

import ast

from .output import Failure
from .scaffold import SNAKE, Plan, check_name, render
from .scaffold_source import MODULE_TAKEN, bindings, check_front_door_name, imports_sibling, module_names

BIG_RPCS = 350  # lines: past this, new rpc suggests --module (the layout test warns above 400, fails above 600)


def rpc_module(plan: Plan, feature_name: str, module: str) -> str:
    """Refuse a --module name that would not end up as the RPC's own module, before anything is planned."""
    check_name(module, SNAKE, "module", "game_rpcs")
    if module in MODULE_TAKEN:
        raise Failure(
            f"--module {module} is a name every feature keeps for its own part (hermes/declare.py); nothing was written",
            "pick another module name, e.g. --module game_rpcs",
        )
    door, source, home = (f"backend/{feature_name}/{name}.py" for name in ("__init__", "rpcs", module))
    if plan.exists(door):
        check_front_door_name(plan.read(door), door, module)
    if plan.exists(source):
        text = plan.read(source)
        if bindings(text, module) and not imports_sibling(text, module):
            raise Failure(
                f"{source} binds {module} already (not as `from . import {module}`), so the declaration would call "
                "into that instead of the new module; nothing was written",
                f"pick another module name, e.g. --module {module}_rpcs",
            )
    if plan.exists(home) and "logger" not in module_names(plan.read(home)):
        raise Failure(
            f"{home} exists and is not an RPC module new wrote (it binds no logger); nothing was written",
            f"pick another module name, e.g. --module {module}_rpcs",
        )
    return module


def with_sibling(text: str, module: str) -> str:
    """``from . import <module>`` after rpcs.py's last top-level import (unchanged when it is there)."""
    if imports_sibling(text, module):
        return text
    tree = ast.parse(text)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    lines = text.split("\n")
    at = imports[-1].end_lineno if imports else 0
    return "\n".join(lines[:at] + [f"from . import {module}"] + lines[at:])


def in_module(plan: Plan, feature_name: str, module: str, values: dict) -> str:
    """Plan the factory in backend/<feature>/<module>.py and its @rpc declaration in rpcs.py; the module's path."""
    home = f"backend/{feature_name}/{rpc_module(plan, feature_name, module)}.py"
    source = f"backend/{feature_name}/rpcs.py"
    values = {**values, "module": module}
    plan.ensure(home, render("rpc", "rpc_module.py.tmpl", **values))
    factory = render("rpc", "rpc.py.tmpl", **values).lstrip("\n").split("\n", 1)[1]  # no @rpc: rpcs.py declares it
    if f"def rpc_{values['rpc']}(" in plan.read(home):
        raise Failure(f"{home} defines rpc_{values['rpc']} already; nothing was written", "pick another RPC name")
    plan.edit(home, lambda text: text.rstrip("\n") + "\n\n\n" + factory)
    plan.ensure(source, render("rpc", "rpcs.py.tmpl", **values))
    plan.edit(source, lambda text: with_sibling(text, module))
    plan.edit(source, lambda text: text.rstrip("\n") + "\n" + render("rpc", "rpc_declared.py.tmpl", **values))
    return home


def big_note(plan: Plan, feature_name: str, name: str) -> None:
    """Without --module: a note when rpcs.py is long already."""
    source = f"backend/{feature_name}/rpcs.py"
    size = len(plan.read(source).splitlines()) if plan.exists(source) else 0
    if size > BIG_RPCS:
        plan.notes.append(
            f"{source} has {size} lines: python tools/retrodev new rpc {feature_name} {name} --module {name}_rpcs puts "
            "the handler in its own module (rpcs.py keeps a short @rpc declaration that calls it)"
        )
