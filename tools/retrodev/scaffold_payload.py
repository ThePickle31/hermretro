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
            held = code_type(re.sub(r"<([^<>]*)>", r"\1", held).strip())
        cells.append(f"`{found.group(1)}` ({held or '<...>'})")
    return ", ".join(cells)


def code_type(held: str) -> str:
    """What a key holds with its type in backticks when the type is a code name, as the CONTRACT rows write it ('the
    real project folder, pathlib.Path' -> 'the real project folder, `pathlib.Path`'): a dotted or capitalised name
    after the last comma (or the whole text); plain types (str, int, list of str) stay plain, as theirs do."""
    head, comma, kind = held.rpartition(",")
    found = re.fullmatch(r"(\s*)([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(\s*)", kind)
    if not found or not ("." in found.group(2) or re.search(r"[A-Z]", found.group(2))):
        return held
    return f"{head}{comma}{found.group(1)}`{found.group(2)}`{found.group(3)}"


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


def emitter_values(keys: list[str], payload: str = "") -> dict:
    """The emitter's parameters and emit arguments (keyword-only, one per payload key: a missing or misspelled key
    fails where it is called), and its test's call with sample values of the types ``payload`` hints (typed_values,
    as new listener's test samples them) and what a listener hears; **payload when --payload names no keys new can
    use."""
    if not keyword_names(keys):
        return {"params": "**payload", "args": "**payload", "sample": "example=1", "heard": '{"example": 1}'}
    samples = typed_values(keys, payload)
    return {
        "params": "*, " + ", ".join(keys),
        "args": ", ".join(f"{key}={key}" for key in keys),
        "sample": ", ".join(f"{key}={value}" for key, value in samples.items()),
        "heard": "{" + ", ".join(f'"{key}": {value}' for key, value in samples.items()) + "}",
    }


# A test's sample value for the type an EVENTS entry hints after the last comma of `key=<what it holds, type>`.
SAMPLES = {
    "int": "1",
    "float": "1.0",
    "str": '"probe"',
    "bool": "True",
    "pathlib.path": 'Path("/games/probe")',
    "path": 'Path("/games/probe")',
    "list of str": '["probe"]',
    "list": "[]",
    "dict": "{}",
}


SAMPLE = '"sample {}"'  # a key whose type the entry does not hint


def hinted_type(part: str) -> str | None:
    """The type a payload part hints ('game=<library id, str; None without one>' -> 'str'), None without one."""
    found = re.match(r"\s*[A-Za-z_]\w*\s*=\s*[<\[](.*)[>\]]", part.strip())
    inner = found.group(1).split(";")[0] if found else ""
    return inner.rsplit(",", 1)[1].strip().lower() if "," in inner else None


def typed_values(keys: list[str], entry: str) -> dict[str, str]:
    """{key: the sample expression of the type its payload part hints (int 1, str "probe", pathlib.Path
    Path("/games/probe"), bool True), else "sample <key>"}, from a --payload line or an EVENTS entry's payload."""
    hints = {}
    for part in split_parts(entry):
        if (found := re.match(r"\s*([A-Za-z_]\w*)\b", part)) and found.group(1) not in hints:
            hints[found.group(1)] = SAMPLES.get(hinted_type(part) or "")
    return {key: hints.get(key) or SAMPLE.format(key) for key in keys}


def typed_sample(keys: list[str], entry: str) -> str:
    """The call a listener's test makes: each key with the sample typed_values gives it."""
    if not keyword_names(keys):
        return "example=1"
    return ", ".join(f"{key}={value}" for key, value in typed_values(keys, entry).items())
