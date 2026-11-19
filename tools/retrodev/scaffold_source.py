"""Edits of Python source for scaffold_backend.py, made from its syntax tree (ast): a declaration is extended
only when its shape is known, and every other shape is refused before anything is written.

    add_tool(text, rel, block, entry)   the schema and handler before TOOLS, the Tool(...) entry inside it
    take_in_module(text, rel, module)   tools.py's TOOLS takes in a sibling module's (*module.TOOLS)
    check_sibling_name(text, rel, m)    refuses a --module name tools.py binds to anything but `from . import m`
    check_front_door_name(text, rel, m) refuses a --module name the feature's __init__.py binds at all
    is_aggregator(text)                 tools.py only takes in sibling modules (no Tool of its own)
    add_event(text, entry)              a "feature.event": "doc" entry at the end of EVENTS
    module_names(text)                  every top-level name a module binds
    py_str(text), js_str(text)          string literals for Python and for the page's JavaScript
"""

from __future__ import annotations

import ast
import json

from .output import Failure

HANDLER_NEEDS = ("json", "logger", "Tool")  # what templates/tool/tool.py.tmpl uses


MODULE_TAKEN = ("tools", "rpcs", "hooks", "prompt", "listeners", "emits")  # names a feature's own parts use


def py_str(text: str) -> str:
    """A Python string literal of ``text`` (double quotes unless the text has them, as ruff format writes it)."""
    return repr(text) if '"' in text and "'" not in text else json.dumps(text, ensure_ascii=False)


def js_str(text: str) -> str:
    """A single-quoted JavaScript literal (the page's style; tests/repo/test_lockstep.py reads it back)."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def bound(node: ast.stmt) -> set[str]:
    """The module-level names one statement binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(alias.asname or alias.name).split(".")[0] for alias in node.names}
    targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
    return {
        name.id for target in targets if target is not None for name in ast.walk(target) if isinstance(name, ast.Name)
    }


def module_names(text: str) -> set[str]:
    """Every name the module binds at its top level (assignments, functions, classes, imports)."""
    return set().union(*(bound(statement) for statement in ast.parse(text).body))


def shape(node: ast.stmt) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "a function"
    if isinstance(node, ast.AnnAssign):
        return "an annotated assignment"
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "an import"
    if isinstance(node, ast.AugAssign):
        return "extended with +="
    return f"a {type(getattr(node, 'value', node)).__name__} expression"


def _comma_after(lines: list[str], node: ast.expr) -> None:
    """A comma right after ``node`` unless one follows it already (comments after it stay where they are)."""
    line = lines[node.end_lineno - 1]
    if not line[node.end_col_offset :].lstrip().startswith(","):
        lines[node.end_lineno - 1] = line[: node.end_col_offset] + "," + line[node.end_col_offset :]


def _tools_node(text: str, rel: str, entry: str) -> ast.Assign | None:
    """The module's plain ``TOOLS = (...)`` / ``[...]`` assignment (None: it has no TOOLS); any other shape is
    refused, as extending it could drop the tools it declares."""
    tree = ast.parse(text)
    found = [node for node in tree.body if "TOOLS" in bound(node)]
    node = found[0] if found else None
    plain = isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.value, (ast.Tuple, ast.List))
    if node is not None and (len(found) > 1 or not plain):
        what = "bound more than once" if len(found) > 1 else shape(node)
        raise Failure(
            f"TOOLS in {rel} is {what}, not a plain tuple or list: new extends only `TOOLS = (Tool(...), ...)` "
            "(anything else could drop the tools it declares); nothing was changed",
            f"add the tool by hand in {rel} (a schema, a handler and this entry where its tools are made), or put "
            "it in another feature (python tools/retrodev new tool <feature> <name>):\n" + entry.strip(),
        )
    return node if isinstance(node, ast.Assign) else None


def append_entry(text: str, rel: str, entry: str) -> str:
    """``entry`` (one ``    Tool(...),`` or ``    *module.TOOLS,`` line) last in TOOLS, made when it is missing."""
    node = _tools_node(text, rel, entry)
    if node is None:  # one entry: ruff keeps a one-element tuple on one line
        return text.rstrip("\n") + "\n\n\nTOOLS = (" + entry.strip() + ")\n"
    assert isinstance(node.value, (ast.Tuple, ast.List))
    value, lines = node.value, text.split("\n")
    first, close = node.lineno - 1, ")" if isinstance(value, ast.Tuple) else "]"
    if node.lineno == value.end_lineno:  # TOOLS = (Tool(...),) on one line: one entry per line from here on
        line = lines[first]
        items = [f"    {ast.get_source_segment(text, item)}," for item in value.elts]
        opening = line[: value.col_offset] + ("(" if close == ")" else "[")
        lines[first : first + 1] = [opening, *items, entry, close + line[value.end_col_offset :]]
    else:
        last = value.end_lineno - 1
        if lines[last][: value.end_col_offset].strip() != close:
            raise Failure(
                f"TOOLS in {rel} does not end in a '{close}' line; nothing was changed", "add by hand:\n" + entry
            )
        if value.elts:
            _comma_after(lines, value.elts[-1])
        lines[last:last] = [entry]
    return "\n".join(lines)


def add_tool(text: str, rel: str, block: str, entry: str) -> str:
    """The schema and handler (``block``) before TOOLS, and the Tool(...) ``entry`` last inside it."""
    node = _tools_node(text, rel, entry)
    names = module_names(text)
    missing = [name for name in HANDLER_NEEDS if name not in names]
    if missing:
        raise Failure(
            f"{rel} has no {', '.join(missing)}, which the new handler uses; nothing was changed",
            f"add them to {rel} as the other features' tools.py do (import json; from ..hermes import host; "
            "from ..hermes.declare import Tool; logger = host.logger), then run new again",
        )
    if node is None:
        return text.rstrip("\n") + "\n" + block + "\n\nTOOLS = (" + entry.strip() + ")\n"
    lines = text.split("\n")
    head = "\n".join(lines[: node.lineno - 1]).rstrip("\n")
    return head + "\n" + block + "\n\n" + append_entry("\n".join(lines[node.lineno - 1 :]), rel, entry)


def imports_sibling(text: str, module: str) -> bool:
    """Whether the module has a top-level ``from . import <module>`` (no alias): the one binding of that name
    take_in_module can build on."""
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is None
        and any(alias.name == module and alias.asname in (None, module) for alias in node.names)
        for node in ast.parse(text).body
    )


def _statements(body: list[ast.stmt]):
    """The module-level statements, including those inside if/try/with/for/while blocks (not def or class
    bodies): each one runs when the module is imported."""
    for node in body:
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for field in ("body", "orelse", "finalbody"):
                yield from _statements(getattr(node, field, None) or [])
            for handler in getattr(node, "handlers", None) or []:
                yield from _statements(handler.body)
            for case in getattr(node, "cases", None) or []:
                yield from _statements(case.body)


def _exported(node: ast.stmt) -> set[str]:
    """The strings an ``__all__ = [...]`` / ``__all__ += [...]`` statement lists."""
    if "__all__" not in bound(node) or not isinstance(getattr(node, "value", None), (ast.List, ast.Tuple, ast.Set)):
        return set()
    return {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}


def bindings(text: str, name: str) -> list[ast.stmt]:
    """Every module-level statement that binds ``name`` (an import, assignment, def or class, in a block or not)
    or lists it in ``__all__``."""
    return [node for node in _statements(ast.parse(text).body) if name in bound(node) | _exported(node)]


def _is_sibling_import(node: ast.stmt, module: str) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is None
        and all(alias.name != module or alias.asname in (None, module) for alias in node.names)
        and all(alias.asname != module or alias.name == module for alias in node.names)
    )


def check_sibling_name(text: str, rel: str, module: str) -> None:
    """Refuse ``module`` when ``rel`` binds that name to anything but ``from . import <module>`` (an import of
    another module, an assignment, a function or a class): ``*<module>.TOOLS`` would read the wrong object."""
    if any(not _is_sibling_import(node, module) for node in bindings(text, module)):
        raise Failure(
            f"{rel} binds {module} already (not as `from . import {module}`), so *{module}.TOOLS would read that "
            "instead of the new module; nothing was written",
            f"pick another module name, e.g. --module {module}_tools",
        )


def check_front_door_name(text: str, rel: str, module: str) -> None:
    """Refuse ``module`` when the feature's front door binds it at all: ``from . import <module>`` in tools.py
    returns the package attribute the front door set, not the new sibling module."""
    if bindings(text, module):
        raise Failure(
            f"{rel} binds {module} already (an import, assignment, function, class or __all__ entry), so "
            f"`from . import {module}` would import that instead of the new module; nothing was written",
            f"pick another module name, e.g. --module {module}_tools",
        )


def is_aggregator(text: str) -> bool:
    """A tools.py that only takes in sibling modules (``TOOLS = (*a.TOOLS, ...)``, no Tool of its own): a new
    inline tool there has no json, logger or Tool to use."""
    names = module_names(text)
    if "Tool" in names:
        return False
    tools = [node for node in ast.parse(text).body if isinstance(node, ast.Assign) and "TOOLS" in bound(node)]
    value = tools[0].value if len(tools) == 1 else None
    if not isinstance(value, (ast.Tuple, ast.List)) or not value.elts:
        return False
    return all(isinstance(elt, ast.Starred) for elt in value.elts)


def take_in_module(text: str, rel: str, module: str) -> str:
    """tools.py's TOOLS takes in a sibling module's: ``from . import <module>`` after its last top-level import
    and ``*<module>.TOOLS,`` last in TOOLS (unchanged when it does both already)."""
    entry = f"    *{module}.TOOLS,"
    check_sibling_name(text, rel, module)
    if not imports_sibling(text, module):
        tree = ast.parse(text)
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        lines = text.split("\n")
        at = imports[-1].end_lineno if imports else (tree.body[0].end_lineno if tree.body else 0)
        lines[at:at] = [f"from . import {module}"] if imports else ["", f"from . import {module}"]
        text = "\n".join(lines)
    if f"*{module}.TOOLS" in text:
        return text
    return append_entry(text, rel, entry)


def add_event(text: str, entry: str) -> str:
    for node in ast.parse(text).body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else (node.targets[0] if isinstance(node, ast.Assign) else None)
        )
        if getattr(target, "id", "") != "EVENTS":
            continue
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Dict):
            raise Failure("EVENTS is not a dict literal; nothing was changed", "add the entry by hand:\n" + entry)
        lines, first = text.split("\n"), node.lineno - 1
        if node.lineno == value.end_lineno:  # EVENTS = {...} on one line: keep its entries, one per line
            line = lines[first]
            items = [
                f"    {ast.get_source_segment(text, key)}: {ast.get_source_segment(text, val)},"
                if key is not None
                else f"    **{ast.get_source_segment(text, val)},"
                for key, val in zip(value.keys, value.values, strict=True)
            ]
            opening = line[: value.col_offset] + "{"
            rest = [opening, *items, entry, "}" + line[value.end_col_offset :]]
            return "\n".join(lines[:first] + rest + lines[first + 1 :])
        last = value.end_lineno - 1
        if lines[last][: value.end_col_offset].strip() != "}":
            raise Failure("EVENTS does not end in a '}' line; nothing was changed", "add the entry by hand:\n" + entry)
        if value.values:
            _comma_after(lines, value.values[-1])
        return "\n".join(lines[:last] + [entry] + lines[last:])
    raise Failure("the front door has no EVENTS dict", "add EVENTS = {} to it (backend/system/events.py)")
