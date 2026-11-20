"""The --payload line of `new event` (and the keys `new listener` reads from an EVENTS entry): its parts and keys,
the emitter's parameters and arguments, and the keys the real dispatcher reserves for itself."""

from __future__ import annotations

import ast
import keyword
import re

from .output import Failure
from .scaffold import Plan


def events_payload(payload: str) -> str:
    """The payload as the EVENTS entries write it, ``key=<...>`` for each keyword ('game=<id>, root' -> 'game=<id>,
    root=<...>'): a part that says what its key holds keeps it."""
    parts = []
    for part in split_parts(payload):
        part = part.strip()
        found = re.match(r"([A-Za-z_]\w*)\b(.*)$", part)
        if found and not found.group(2).strip():
            part = f"{found.group(1)}=<...>"
        parts.append(part)
    return ", ".join(part for part in parts if part)


def contract_cell(payload: str) -> str:
    """The CONTRACT events row's Payload cell, as its rows write it: `` `key` (what it holds)`` per part
    ('game=<library id, str>, root' -> `` `game` (library id, str), `root` (<...>)``); a part that says nothing of
    what its key holds keeps the ``<...>`` placeholder the EVENTS entry has."""
    cells = []
    for part in split_parts(payload):
        found = re.match(r"\s*([A-Za-z_]\w*)\b\s*(.*?)\s*$", part)
        if not found:
            continue
        held = found.group(2).removeprefix("=").strip()
        if held.startswith("(") and held.endswith(")"):
            held = held[1:-1].strip()
        if held != "<...>":
            held = re.sub(r"^<([^<>]*)>\s*\((.*)\)$", r"\1; \2", held)
            held = re.sub(r"<([^<>]*)>", r"\1", held).strip()
        cells.append(f"`{found.group(1)}` ({held or '<...>'})")
    return ", ".join(cells)


def undescribed(payload: str) -> list[str]:
    """The keys of a payload (a --payload line or an EVENTS entry's) that say nothing of what they hold: bare
    ('root') or still the placeholder ('root=<...>'), which events_payload writes as `key=<...>`."""
    keys = []
    for part in split_parts(payload):
        found = re.match(r"\s*([A-Za-z_]\w*)\b\s*(=\s*<\.\.\.>)?\s*$", part)
        if found:
            keys.append(found.group(1))
    return list(dict.fromkeys(keys))


def placeholders(keys: list[str]) -> str:
    return ", ".join(f"{key}=<...>" for key in keys)


def split_parts(payload: str) -> list[str]:
    """The comma-separated parts of a --payload line, a comma inside brackets kept in its part."""
    parts, depth, current = [], 0, ""
    for char in payload:
        depth += char in "([{<"
        depth -= char in ")]}>"
        if char == "," and depth <= 0:
            parts.append(current)
            current = ""
        else:
            current += char
    return [*parts, current]


def payload_keys(payload: str) -> list[str]:
    """The keyword names a --payload line gives ('game=<id> (None without one), root=<project>' -> game, root):
    the leading name of each comma-separated part outside brackets."""
    keys = [found.group(1) for part in split_parts(payload) if (found := re.match(r"\s*([A-Za-z_]\w*)\b", part))]
    return list(dict.fromkeys(keys))


def keyword_names(keys: list[str]) -> bool:
    """Whether every payload key can be a keyword-only parameter of the emitter (emit itself is its global)."""
    return bool(keys) and all(k.isidentifier() and not keyword.iskeyword(k) and k != "emit" for k in keys)


DISPATCHER = "backend/system/events.py"


def dispatcher_params(plan: Plan) -> list[str]:
    """The named parameters of the real dispatcher's emit(name, **payload) (read from the tree new edits): a payload
    key with one of these names would reach emit twice, so every emitter call would fail before any listener ran."""
    source = plan.read(DISPATCHER) if plan.exists(DISPATCHER) else ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = ast.Module(body=[], type_ignores=[])
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "emit":
            args = node.args
            return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    return ["name"]  # emit(name, **payload), as the dispatcher has always been


def refuse_reserved_keys(plan: Plan, keys: list[str]) -> None:
    """Refuse, before anything is written, payload keys the dispatcher's own parameters take."""
    reserved = dispatcher_params(plan)
    taken = [key for key in keys if key in reserved]
    if taken:
        words = ", ".join(f"'{word}'" for word in reserved)
        raise Failure(
            f"the payload key(s) {', '.join(repr(key) for key in taken)} collide with {DISPATCHER}'s "
            f"emit({', '.join(reserved)}, **payload): its reserved word(s) {words} cannot be payload keys (the call "
            "would pass them twice and fail before any listener ran); nothing was written",
            f"rename {', '.join(taken)} in --payload to a key that says what it holds (e.g. title or game_name "
            "instead of name), then run new again",
        )


def emitter_values(keys: list[str]) -> dict:
    """The emitter's parameters and emit arguments (keyword-only, one per payload key: a missing or misspelled key
    fails where it is called), and its test's call with sample values and what a listener hears; **payload when
    --payload names no keys new can use."""
    if not keyword_names(keys):
        return {"params": "**payload", "args": "**payload", "sample": "example=1", "heard": '{"example": 1}'}
    samples = {key: f"sample {key}" for key in keys}
    return {
        "params": "*, " + ", ".join(keys),
        "args": ", ".join(f"{key}={key}" for key in keys),
        "sample": ", ".join(f"{key}={value!r}" for key, value in samples.items()).replace("'", '"'),
        "heard": "{" + ", ".join(f'"{key}": "{value}"' for key, value in samples.items()) + "}",
    }
