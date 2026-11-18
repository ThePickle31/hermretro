"""Edits of Python source for scaffold_backend.py, made from its syntax tree (ast): a declaration is extended
only when its shape is known, and every other shape is refused before anything is written.

    add_tool(text, rel, block, entry)   the schema and handler before TOOLS, the Tool(...) entry inside it
    add_event(text, entry, comment)     a "feature.event": "payload" entry at the end of EVENTS
    module_names(text)                  every top-level name a module binds
    py_str(text), js_str(text)          string literals for Python and for the page's JavaScript
"""

from __future__ import annotations

import ast
import json

from .output import Failure

HANDLER_NEEDS = ("json", "logger", "Tool")  # what templates/tool/tool.py.tmpl uses


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


def add_tool(text: str, rel: str, block: str, entry: str) -> str:
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
    names = set().union(*(bound(statement) for statement in tree.body))
    missing = [name for name in HANDLER_NEEDS if name not in names]
    if missing:
        raise Failure(
            f"{rel} has no {', '.join(missing)}, which the new handler uses; nothing was changed",
            f"add them to {rel} as the other features' tools.py do (import json; from ..hermes import host; "
            "from ..hermes.declare import Tool; logger = host.logger), then run new again",
        )
    if node is None:  # one entry: ruff keeps a one-element tuple on one line
        return text.rstrip("\n") + "\n" + block + "\n\nTOOLS = (" + entry.strip() + ")\n"
    assert isinstance(node, ast.Assign) and isinstance(node.value, (ast.Tuple, ast.List))
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
    head = "\n".join(lines[:first]).rstrip("\n")
    return head + "\n" + block + "\n\n" + "\n".join(lines[first:])


def add_event(text: str, comment: str, entry: str) -> str:
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
            rest = [opening, *items, comment, entry, "}" + line[value.end_col_offset :]]
            return "\n".join(lines[:first] + rest + lines[first + 1 :])
        last = value.end_lineno - 1
        if lines[last][: value.end_col_offset].strip() != "}":
            raise Failure("EVENTS does not end in a '}' line; nothing was changed", "add the entry by hand:\n" + entry)
        if value.values:
            _comma_after(lines, value.values[-1])
        return "\n".join(lines[:last] + [comment, entry] + lines[last:])
    raise Failure("the front door has no EVENTS dict", "add EVENTS = {} to it (backend/system/events.py)")
