"""`new feature|rpc|tool|event`: the backend kinds of scaffold.py, each filling a Plan (nothing is written here).

The places each kind touches are the ones tests/repo/test_lockstep.py's opening comment and docs/dev/ARCHITECTURE.md
("Adding things") list; the checks that then run (unit: boundaries, lock step, layout, docs, the registration
snapshot) prove the generated code is in step.
"""

from __future__ import annotations

import ast
import re

from . import scaffold_rpc
from .output import Failure
from .scaffold import (
    SNAKE,
    Plan,
    check_name,
    const,
    in_section,
    insert_after,
    insert_before,
    label,
    one_line,
    pascal,
    readme_item,
    render,
)
from .scaffold_payload import (
    contract_cell,
    emitter_values,
    events_payload,
    payload_keys,
    placeholders,
    refuse_reserved_keys,
    undescribed,
)
from .scaffold_source import add_event, event_entry, files_line

FEATURES = "backend/features.py"
CONTRACT = "docs/dev/CONTRACT.md"
ARCHITECTURE = "docs/dev/ARCHITECTURE.md"
MANIFEST = "plugin.yaml"
STEP_WORDS = "page/pages/build/transcript/step-words.js"
TOOL_PREFIX = "chromatic_"
BIG_MODULE = 400  # lines: tests/repo/test_layout.py warns above it (and fails above 600)


def features(plan: Plan) -> list[str]:
    tree = ast.parse(plan.read(FEATURES))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FEATURES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise Failure(f"{FEATURES} has no FEATURES list", f"restore {FEATURES} (git checkout -- {FEATURES})")


def known_feature(plan: Plan, name: str, kind: str = "") -> str:
    check_name(name, SNAKE, "feature", "history")
    if kind and name in plan.stdlib_only:
        raise Failure(
            f"backend/{name} stays stdlib-only (policy.toml [new] stdlib_only), and a generated {kind} module imports "
            "backend.hermes or backend.system.events; nothing was written",
            f"declare the gateway-side {kind} in another feature (setup, library, ...): python tools/retrodev new "
            f"{kind} <feature> <name>, and reach backend/{name} through its front door",
        )
    if name not in features(plan) or not plan.exists(f"backend/{name}/__init__.py"):
        raise Failure(
            f"backend/{name} is not a feature listed in {FEATURES}",
            f"python tools/retrodev new feature {name} first (or pick one of: {', '.join(features(plan))})",
        )
    return name


def feature(plan: Plan, name: str, purpose: str | None) -> str:
    check_name(name, SNAKE, "feature", "history")
    purpose = one_line(purpose or f"The {label(name).lower()} feature (say what it does here)", "purpose")
    purpose = purpose[:1].upper() + purpose[1:].rstrip(".")
    if plan.exists(f"backend/{name}") or name in features(plan) or name in ("features", "tests"):
        raise Failure(f"backend/{name} exists or is taken", "pick another feature name")
    plan.create(f"backend/{name}/__init__.py", render("feature", "__init__.py.tmpl", name=name, purpose=purpose + "."))
    plan.create(f"backend/{name}/README.md", render("feature", "README.md.tmpl", name=name, purpose=purpose + "."))
    plan.create(f"tests/backend/{name}/__init__.py", "")
    plan.create(f"tests/backend/{name}/test_{name}.py", render("feature", "test_feature.py.tmpl", name=name))
    plan.edit(FEATURES, lambda text: _add_feature_line(text, name, purpose))
    toml_purpose = purpose.replace("\\", "\\\\").replace('"', '\\"')
    plan.edit(
        "tools/layout.toml",
        lambda text: in_section(
            text,
            "[folders.backend]",
            lambda body: insert_after(body, re.compile(r"^areas\."), f'areas.{name} = "{toml_purpose}"', "layout"),
        ),
    )
    row = f"| `backend/{name}/` | {purpose} |"
    agent_row = f"| `backend/{name}/` | nothing yet | nothing; no events |"
    plan.edit(
        ARCHITECTURE,
        lambda text: in_section(
            in_section(text, "## Map", lambda body: insert_after(body, re.compile(r"^\| `backend/"), row, "Map")),
            "## The agent half",
            lambda body: table_row(body, "| Feature | Declares |", agent_row, "The agent half"),
        ),
    )
    if not any(line.startswith('"backend/*/README.md"') for line in plan.read("tools/layout.toml").splitlines()):
        plan.notes.append('tools/layout.toml [docs] has no "backend/*/README.md" line: list the README there')
    plan.next_steps += [
        f"say what it does in backend/{name}/README.md (its purpose line is in tools/layout.toml and the Map)",
        f"python tools/retrodev new rpc {name} <name> | new tool {name} <name> | new event {name} <name>",
    ]
    return f"feature {name}"


def table_row(body: str, header: str, row: str, where: str) -> str:
    """``row`` after the last row of the table whose header line starts with ``header`` (the table ends at its first
    blank line), whatever other tables the section holds."""
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
    if start is None:
        raise Failure(f"{where}: no table starting '{header}'", f"add this row to it by hand: {row}")
    end = next((i for i in range(start, len(lines)) if not lines[i].strip()), len(lines))
    return "\n".join(lines[:end] + [row] + lines[end:])


def _add_feature_line(text: str, name: str, purpose: str) -> str:
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("FEATURES = [")), None)
    end = next((i for i in range(start or 0, len(lines)) if lines[i] == "]"), None) if start is not None else None
    if end is None:
        raise Failure(f"{FEATURES}: no 'FEATURES = [' list ending in a ']' line", f'add "{name}", to it by hand')
    comment = purpose[:1].lower() + purpose[1:]
    return "\n".join(lines[:end] + [f'    "{name}",  # {comment}'[:120]] + lines[end:])


def agent_half(plan: Plan, feature_name: str, change) -> None:
    """Change the feature's row in ARCHITECTURE.md "The agent half" (a note when it has none)."""
    if not plan.exists(ARCHITECTURE):
        return
    start = f"| `backend/{feature_name}/` |"

    def edit(body: str) -> str:
        return "\n".join(change(line) if line.startswith(start) else line for line in body.split("\n"))

    before = plan.read(ARCHITECTURE)
    try:
        plan.edit(ARCHITECTURE, lambda text: in_section(text, "## The agent half", edit))
    except Failure:  # no such section: the note below says what to write
        pass
    if plan.read(ARCHITECTURE) == before:
        plan.notes.append(f"{ARCHITECTURE} \"The agent half\" has no row for backend/{feature_name}/ to change: add it")


def cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split(" | ")]


def joined(parts: list[str]) -> str:
    return "| " + " | ".join(parts) + " |"


DECLARED = {"RPC": "RPCs", "tool": "tools"}  # the Declares cell's groups, in its order


def declares(row: str, what: str, name: str) -> str:
    """The Declares cell names the RPC or tool: 'nothing yet' becomes 'RPC `x`'; else it goes after the group's last
    item ('RPCs `a`, `x`'), or a new group comes first (RPCs before tools, as the other rows have them)."""
    parts = cells(row)
    if len(parts) < 3:
        return row
    item, groups = f"`{name}`", [] if parts[1].startswith("nothing") else parts[1].split("; ")
    plural = DECLARED[what]
    at = next((i for i, group in enumerate(groups) if group.startswith((what + " ", plural + " "))), None)
    if at is not None:
        groups[at] = plural + groups[at].removeprefix(plural).removeprefix(what) + ", " + item
    else:
        rpcs = [i for i, group in enumerate(groups) if group.startswith(("RPC ", "RPCs "))]
        groups.insert(rpcs[-1] + 1 if what == "tool" and rpcs else 0, f"{what} {item}")
    parts[1] = "; ".join(groups)
    return joined(parts)


def emits_cell(row: str, full: str) -> str:
    """The 'Front door / events' cell names the event: 'no events' becomes it, else it follows the last one (before
    a '; listens to ...' part)."""
    parts = cells(row)
    if len(parts) < 3:
        return row
    groups = parts[2].split("; ")
    if len(groups) < 2 or groups[1].startswith("listens to"):
        groups.insert(1, f"`{full}`")
    elif groups[1] == "no events":
        groups[1] = f"`{full}`"
    else:
        groups[1] += f", `{full}`"
    parts[2] = "; ".join(groups)
    return joined(parts)


def rpc_names(plan: Plan) -> set[str]:
    found = set()
    for path in sorted(plan.top.glob("backend/*/rpcs.py")):
        found |= set(re.findall(r'@rpc\("(\w+)"\)', plan.read(str(path.relative_to(plan.top)))))
    for rel, text in plan.created.items():
        found |= set(re.findall(r'@rpc\("(\w+)"\)', text)) if rel.endswith("rpcs.py") else set()
    return found


def rpc_(plan: Plan, feature_name: str, name: str, module: str | None = None, game: bool = False) -> str:
    known_feature(plan, feature_name, "rpc")
    check_name(name, SNAKE, "RPC", "build_restore")
    documented = set(re.findall(r"^(?:### `(\w+)`|\| `(\w+)` \|)", plan.read(CONTRACT), re.M))
    if name in rpc_names(plan) or name in {a or b for a, b in documented}:
        raise Failure(f"an RPC named {name} exists (or CONTRACT.md documents one)", "pick another RPC name")
    values = {"name": feature_name, "Name": label(feature_name), "rpc": name, "Rpc": pascal(name), "RPC": const(name)}
    if game:  # about one library game: host._game_root finds it, else NO_GAME (as history's builds answers)
        values["handler"] = "rpc_game.py.tmpl"
    source = f"backend/{feature_name}/rpcs.py"
    if module:  # the handler in its own module; rpcs.py keeps the @rpc declaration (scaffold_rpc.py)
        source = scaffold_rpc.in_module(plan, feature_name, module, values)
    else:
        scaffold_rpc.big_note(plan, feature_name, name)
        source = scaffold_rpc.inline(plan, feature_name, values)
    if game:
        scaffold_rpc.needs_host(plan, source)
    scaffold_rpc.listed_in_docstring(plan, f"backend/{feature_name}/rpcs.py", name)
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    test = "test_rpc_game.py.tmpl" if game else "test_rpc.py.tmpl"
    plan.create(f"tests/backend/{feature_name}/test_rpc_{name}.py", render("rpc", test, **values))
    block = render("rpc", "contract_game.md.tmpl" if game else "contract.md.tmpl", **values)
    plan.edit(CONTRACT, lambda text: _before_heading(text, "## Studio pages", block))
    readme(plan, feature_name, "RPCs", f"`{name}`")
    if module and plan.exists(f"backend/{feature_name}/README.md"):  # as new tool --module names its module
        plan.edit(f"backend/{feature_name}/README.md", lambda text: files_line(text, "RPCs", "rpcs.py", module))
    agent_half(plan, feature_name, lambda row: declares(row, "RPC", name))
    plan.regenerate = True
    plan.next_steps += scaffold_rpc.page_steps(plan, feature_name, name, source, game)
    return f"RPC {name}"


def _before_heading(text: str, heading: str, block: str) -> str:
    if re.search(rf"^{re.escape(heading)}", text, re.M):
        return insert_before(text, re.compile(rf"^{re.escape(heading)}"), block.rstrip("\n") + "\n", CONTRACT)
    return text.rstrip("\n") + "\n\n" + block


def readme(plan: Plan, feature_name: str, what: str, item: str, only_none: bool = False) -> None:
    rel = f"backend/{feature_name}/README.md"
    if not plan.exists(rel):
        plan.notes.append(f"{rel} is missing: add it (python tools/retrodev new feature makes one)")
        return
    before = plan.read(rel)
    plan.edit(rel, lambda text: readme_item(text, what, item, only_none))
    if plan.read(rel) == before:
        plan.notes.append(f"name {item} under '{what}' in {rel} (its line did not have the usual shape)")


PAYLOAD_GUIDE = "tools/retrodev/REFERENCE.md \"Changing an event's payload\" lists every place"


def event_row(body: str, feature_name: str, row: str) -> str:
    """The CONTRACT events row after the owner feature's last row (after the table's last row when it has none)."""
    owned = re.compile(rf"^\| `{re.escape(feature_name)}\.")
    anchor = owned if any(owned.search(line) for line in body.split("\n")) else re.compile(r"^\| `")
    return insert_after(body, anchor, row, CONTRACT)


def event(plan: Plan, feature_name: str, name: str, payload: str | None, when: str | None = None) -> str:
    known_feature(plan, feature_name, "event")
    check_name(name, SNAKE, "event", "build_kept")
    if name in ("emit", "annotations"):
        raise Failure(f"'{name}' would shadow a name emits.py uses", "pick another event name, e.g. build_kept")
    full = f"{feature_name}.{name}"
    payload = one_line(payload or "key=<value> for each keyword argument", "payload")
    when = one_line(when, "when").rstrip(".") if when else None
    for door in plan.top.glob("backend/*/__init__.py"):
        if f'"{full}"' in plan.read(str(door.relative_to(plan.top))):
            raise Failure(f"the event {full} is declared already ({door.relative_to(plan.top)})", "pick another name")
    door = f"backend/{feature_name}/__init__.py"
    keys = payload_keys(payload) if payload != "key=<value> for each keyword argument" else []
    refuse_reserved_keys(plan, keys)
    plain = when.replace("`", "") if when else None  # backticks are Markdown: the CONTRACT row keeps them
    doc = f"{plain or 'say when it is emitted'}; {events_payload(payload) if keys else payload}"
    plan.edit(door, lambda text: add_event(text, event_entry(full, doc)))
    cell = contract_cell(payload) if keys else payload
    row = f"| `{full}` | {cell} | {when} | — |" if when else f"| `{full}` | {cell} | say when | — |"
    plan.edit(
        CONTRACT,
        lambda text: in_section(
            text, "## Events between backend features", lambda body: event_row(body, feature_name, row)
        ),
    )
    # tests/repo/test_boundaries.py fails on an event nothing emits: the feature gets the one function that does.
    values = {"name": feature_name, "Name": label(feature_name), "event": name, "Event": pascal(name)}
    values |= {"full": full, "payload": payload, **emitter_values(keys)}
    emits = f"backend/{feature_name}/emits.py"
    if re.search(rf"^def {name}\(", plan.read(emits) if plan.exists(emits) else "", re.M):
        raise Failure(f"{emits} has a function named {name} already", "pick another event name")
    plan.ensure(emits, render("event", "emits.py.tmpl", **values))
    plan.edit(emits, lambda text: text.rstrip("\n") + "\n" + render("event", "emit.py.tmpl", **values))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    plan.create(f"tests/backend/{feature_name}/test_event_{name}.py", render("event", "test_event.py.tmpl", **values))
    readme(plan, feature_name, "Events emitted", f"`{full}`")
    agent_half(plan, feature_name, lambda row: emits_cell(row, full))
    plan.next_steps += [
        f"call emits.{name}(...) in backend/{feature_name}/ where it happens (from .emits import {name}; it runs "
        f'emit("{full}", ...))' + ("" if when else f"; say when in its CONTRACT row and EVENTS entry ({door})"),
        f'react in another feature\'s listeners.py: @on("{full}") (backend/system/events.py)',
        f"assert the event in the test of the code that emits it (grep -rln <the function that calls emits.{name}> "
        f"tests/backend/{feature_name}): mock emits.{name} there, or listen with events.on as test_event_{name}.py does",
        f"changing {full}'s payload later: {PAYLOAD_GUIDE} ({emits}'s function {name}, its callers: grep -rn "
        f"'{name}(' backend/{feature_name}; the EVENTS entry in {door}, its {CONTRACT} row, "
        f"tests/backend/{feature_name}/test_event_{name}.py, and the tests that assert it: grep -rln '{full}' "
        f"tests/backend/{feature_name})",
    ]
    bare = undescribed(payload) if keys else []
    if bare:
        plan.next_steps.append(
            f"replace the <...> placeholders in {door} EVENTS ({placeholders(bare)}) and in its {CONTRACT} row "
            "with what each key holds "
            "(game=<id>, root=<project>); new listener copies that entry into its listener's docstring"
        )
    return f"event {full}"


def __getattr__(name: str):
    """The tool kind lives in scaffold_tool.py (it imports this module): scaffold_backend.tool still finds it."""
    if name in ("tool", "_contract_tool", "engine_tools"):
        from . import scaffold_tool

        return getattr(scaffold_tool, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
