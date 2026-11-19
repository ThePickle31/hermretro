"""`new feature|rpc|tool|event`: the backend kinds of scaffold.py, each filling a Plan (nothing is written here).

The places each kind touches are the ones tests/repo/test_lockstep.py's opening comment and docs/dev/ARCHITECTURE.md
("Adding things") list; the checks that then run (unit: boundaries, lock step, layout, docs, the registration
snapshot) prove the generated code is in step.
"""

from __future__ import annotations

import ast
import json
import re

from .count_words import count_text, count_value
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
from .scaffold_source import add_event, add_tool, js_str, module_names, py_str, take_in_module

FEATURES = "backend/features.py"
CONTRACT = "docs/dev/CONTRACT.md"
ARCHITECTURE = "docs/dev/ARCHITECTURE.md"
MANIFEST = "plugin.yaml"
STEP_WORDS = "page/pages/build/transcript/step-words.js"
TOOL_PREFIX = "chromatic_"
STUDIO_PAGE = "page/app/studio-page.js"  # where the shell asks for its RPCs (the games query is the model)
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
            lambda body: insert_after(body, re.compile(r"^\| `backend/"), agent_row, "The agent half"),
        ),
    )
    if not any(line.startswith('"backend/*/README.md"') for line in plan.read("tools/layout.toml").splitlines()):
        plan.notes.append('tools/layout.toml [docs] has no "backend/*/README.md" line: list the README there')
    plan.next_steps += [
        f"say what it does in backend/{name}/README.md (its purpose line is in tools/layout.toml and the Map)",
        f"python tools/retrodev new rpc {name} <name> | new tool {name} <name> | new event {name} <name>",
    ]
    return f"feature {name}"


def _add_feature_line(text: str, name: str, purpose: str) -> str:
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("FEATURES = [")), None)
    end = next((i for i in range(start or 0, len(lines)) if lines[i] == "]"), None) if start is not None else None
    if end is None:
        raise Failure(f"{FEATURES}: no 'FEATURES = [' list ending in a ']' line", f'add "{name}", to it by hand')
    comment = purpose[:1].lower() + purpose[1:]
    return "\n".join(lines[:end] + [f'    "{name}",  # {comment}'[:120]] + lines[end:])


def rpc_names(plan: Plan) -> set[str]:
    found = set()
    for path in sorted(plan.top.glob("backend/*/rpcs.py")):
        found |= set(re.findall(r'@rpc\("(\w+)"\)', plan.read(str(path.relative_to(plan.top)))))
    for rel, text in plan.created.items():
        found |= set(re.findall(r'@rpc\("(\w+)"\)', text)) if rel.endswith("rpcs.py") else set()
    return found


def rpc_(plan: Plan, feature_name: str, name: str) -> str:
    known_feature(plan, feature_name, "rpc")
    check_name(name, SNAKE, "RPC", "build_restore")
    documented = set(re.findall(r"^(?:### `(\w+)`|\| `(\w+)` \|)", plan.read(CONTRACT), re.M))
    if name in rpc_names(plan) or name in {a or b for a, b in documented}:
        raise Failure(f"an RPC named {name} exists (or CONTRACT.md documents one)", "pick another RPC name")
    values = {"name": feature_name, "Name": label(feature_name), "rpc": name, "Rpc": pascal(name), "RPC": const(name)}
    source = f"backend/{feature_name}/rpcs.py"
    plan.ensure(source, render("rpc", "rpcs.py.tmpl", **values))
    plan.edit(source, lambda text: text.rstrip("\n") + "\n" + render("rpc", "rpc.py.tmpl", **values))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    plan.create(f"tests/backend/{feature_name}/test_rpc_{name}.py", render("rpc", "test_rpc.py.tmpl", **values))
    block = render("rpc", "contract.md.tmpl", **values)
    plan.edit(CONTRACT, lambda text: _before_heading(text, "## Studio pages", block))
    readme(plan, feature_name, "RPCs", f"`{name}`")
    plan.regenerate = True
    plan.next_steps += [
        f"write the handler in {source} and its section in {CONTRACT} (params, result)",
        f"call it from the page: import {{ RPC_{const(name)} }} from '#app/rpc.js' (re-exports the generated "
        "rpc-names.js)",
        f"ask for it as {STUDIO_PAGE} asks for games: useQuery({{ queryKey: [ID, '{name}', viaProfile], queryFn: () "
        f"=> callStudio(RPC_{const(name)}), enabled }}) (useQuery from '#sdk', ID from '#app/ids.js', callStudio "
        "from '#app/backend.js'; viaProfile and enabled: running, as there)",
        f"page tests feed its answer by the query key's second word: scenario.{name} = answered({{ ok: true, ... }}) "
        "(tests/page/harness.mjs)",
        f"RPC names are global and flat: the page calls plugin.hermretro.{name}, whatever feature declares it",
    ]
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


def engine_tools(plan: Plan) -> set[str]:
    found = set()
    for path in plan.top.glob("engine/pins/*/tools.json"):
        found |= {TOOL_PREFIX + tool["name"] for tool in json.loads(path.read_text(encoding="utf-8")).get("tools", [])}
    return found


MODULE_TAKEN = ("tools", "rpcs", "hooks", "prompt", "listeners", "emits")  # names a feature's own parts use


def tool_module(module: str) -> str:
    check_name(module, SNAKE, "module", "game_tools")
    if module in MODULE_TAKEN:
        raise Failure(
            f"--module {module} is a name every feature keeps for its own part (hermes/declare.py); nothing was written",
            "pick another module name, e.g. --module game_tools",
        )
    return module


def tool(plan: Plan, feature_name: str, name: str, step: list[str] | None, module: str | None = None) -> str:
    known_feature(plan, feature_name, "tool")
    short = check_name(name.removeprefix(TOOL_PREFIX), SNAKE, "tool", "game_info")
    full = TOOL_PREFIX + short
    manifest = plan.read(MANIFEST)
    listed = re.findall(r"^  - (\w+)$", manifest.split("provides_tools:")[-1], re.M)
    if full in listed or full in engine_tools(plan) or re.search(rf"^  {short}: ", plan.read(STEP_WORDS), re.M):
        raise Failure(f"a tool named {full} exists (plugin.yaml, the engine or step-words.js)", "pick another name")
    running, done = step or (f"Running {short.replace('_', ' ')}", f"Ran {short.replace('_', ' ')}")
    for text in (running, done):
        if "\\" in text or not text.strip() or not all(" " <= char <= "~" for char in text):
            raise Failure(
                "step words are one line of plain ASCII without backslashes (tests/repo/test_lockstep.py reads them)",
                "pass --step '<while it runs>' '<once it is done>' in plain words",
            )
    words = f"({py_str(running)}, {py_str(done)})"
    values = {"name": feature_name, "Name": label(feature_name), "tool": full, "short": short, "Short": pascal(short)}
    values |= {"TOOL": const(short), "words": words}
    source = f"backend/{feature_name}/tools.py"
    size = len(plan.read(source).splitlines()) if plan.exists(source) else 0
    if module is None and size > BIG_MODULE:
        module = f"{short}_tools"
        plan.notes.append(
            f"{source} has {size} lines, over {BIG_MODULE} (the layout test warns, and fails at 600): the tool goes in "
            f"its own module backend/{feature_name}/{module}.py, with its own TOOLS, which tools.py's TOOLS takes in "
            f"(*{module}.TOOLS); --module <name> picks another name"
        )
    home = source if module is None else f"backend/{feature_name}/{tool_module(module)}.py"
    plan.ensure(home, render("tool", "tools.py.tmpl", **values))
    for where in dict.fromkeys(rel for rel in (source, home) if plan.exists(rel)):  # one name per tool, feature-wide
        taken = sorted({f"{const(short)}_TOOL", f"{short}_handler"} & module_names(plan.read(where)))
        if taken:  # a second binding would replace the first: the tool that uses it would lose its schema or handler
            raise Failure(
                f"{where} binds {' and '.join(taken)} already, which tool {full} would define; nothing was written",
                f"pick another tool name, e.g. python tools/retrodev new tool {feature_name} {short}_more",
            )
    entry = f"    Tool({const(short)}_TOOL, {short}_handler, step_words={words}),"
    plan.edit(home, lambda text: add_tool(text, home, render("tool", "tool.py.tmpl", **values), entry))
    if module is not None:
        plan.ensure(source, render("tool", "tools_index.py.tmpl", **values))
        plan.edit(source, lambda text: take_in_module(text, source, module))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    plan.create(f"tests/backend/{feature_name}/test_tool_{short}.py", render("tool", "test_tool.py.tmpl", **values))
    owned = [tool_name for tool_name in listed if tool_name not in engine_tools(plan)]
    anchor = re.compile(rf"^  - {owned[-1]}$" if owned else r"^provides_tools:")
    plan.edit(MANIFEST, lambda text: insert_after(text, anchor, f"  - {full}", MANIFEST, last=False))
    words_line = f"  {short}: [{js_str(running)}, {js_str(done)}],"
    plan.edit(STEP_WORDS, lambda text: insert_before(text, re.compile(r"^  skill_view: "), words_line, STEP_WORDS))
    plan.edit(CONTRACT, lambda text: _contract_tool(text, full, feature_name, home))
    readme(plan, feature_name, "Tools", f"`{full}`")
    plan.regenerate = True
    plan.next_steps += [
        f"write the schema and handler in {home}; describe {full} in {CONTRACT} (its line says what it does)",
        f"the Build page shows it as '{running}' / '{done}' ({STEP_WORDS}; change both sides together)",
    ]
    return f"tool {full}"


def _contract_tool(text: str, full: str, feature_name: str, home: str | None = None) -> str:
    def bump(match: re.Match) -> str:
        return match.group(1) + str(int(match.group(2)) + 1) + match.group(3)

    text, total = re.subn(r"(the )(\d+)( tools,)", bump, text, count=1)
    text, sum_ = re.subn(r"()(\d+)( in total)", bump, text, count=1)

    def plus(match: re.Match) -> str:
        current = count_value(match.group(2))
        if current is None:
            raise Failure(f"{CONTRACT}: cannot read '{match.group(0)}'", "update the tool counts there by hand")
        return match.group(1) + count_text(current + 1)

    text, extra = re.subn(r"(\d+ tools, plus\s+)(\w+)", plus, text, count=1)
    if not (total and sum_ and extra):
        raise Failure(f"{CONTRACT}: the tool counts are not where they were", "update them by hand, then run check")
    line = f"- `{full}` (`{home or f'backend/{feature_name}/tools.py'}`): say what it does and when the agent calls it."
    return insert_after(text, re.compile(r"in total\.$"), line, CONTRACT, last=False)


def payload_keys(payload: str) -> list[str]:
    """The keyword names a --payload line gives ('game=<id> (None without one), root=<project>' -> game, root):
    the leading name of each comma-separated part outside brackets."""
    parts, depth, current = [], 0, ""
    for char in payload:
        depth += char in "([{<"
        depth -= char in ")]}>"
        if char == "," and depth <= 0:
            parts.append(current)
            current = ""
        else:
            current += char
    keys = [found.group(1) for part in [*parts, current] if (found := re.match(r"\s*([A-Za-z_]\w*)\b", part))]
    return list(dict.fromkeys(keys))


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
    doc = f"{when or 'say when it is emitted'}; payload: {payload}"
    plan.edit(door, lambda text: add_event(text, f"    {json.dumps(full)}: {json.dumps(doc)},"))
    keys = payload_keys(payload) if payload != "key=<value> for each keyword argument" else []
    cell = ", ".join(f"`{key}`" for key in keys) or payload
    row = f"| `{full}` | {cell} | {when} | — |" if when else f"| `{full}` | {cell} | say when | — |"
    plan.edit(
        CONTRACT,
        lambda text: in_section(
            text, "## Events between backend features", lambda body: event_row(body, feature_name, row)
        ),
    )
    # tests/repo/test_boundaries.py fails on an event nothing emits: the feature gets the one function that does.
    values = {"name": feature_name, "Name": label(feature_name), "event": name, "Event": pascal(name)}
    values |= {"full": full, "payload": payload}
    emits = f"backend/{feature_name}/emits.py"
    if re.search(rf"^def {name}\(", plan.read(emits) if plan.exists(emits) else "", re.M):
        raise Failure(f"{emits} has a function named {name} already", "pick another event name")
    plan.ensure(emits, render("event", "emits.py.tmpl", **values))
    plan.edit(emits, lambda text: text.rstrip("\n") + "\n" + render("event", "emit.py.tmpl", **values))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    plan.create(f"tests/backend/{feature_name}/test_event_{name}.py", render("event", "test_event.py.tmpl", **values))
    readme(plan, feature_name, "Events emitted", f"`{full}`")
    plan.next_steps += [
        f"call emits.{name}(...) in backend/{feature_name}/ where it happens (from .emits import {name}; it runs "
        f'emit("{full}", ...))' + ("" if when else f"; say when in its CONTRACT row and EVENTS entry ({door})"),
        f'react in another feature\'s listeners.py: @on("{full}") (backend/system/events.py)',
    ]
    return f"event {full}"
