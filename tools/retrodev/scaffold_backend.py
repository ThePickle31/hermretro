"""`new feature|rpc|tool|event`: the backend kinds of scaffold.py, each filling a Plan (nothing is written here).

The places each kind touches are the ones tests/repo/test_lockstep.py's opening comment and docs/dev/ARCHITECTURE.md
("Adding things") list; the checks that then run (unit: boundaries, lock step, layout, docs, the registration
snapshot) prove the generated code is in step.
"""

from __future__ import annotations

import ast
import json
import re

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

FEATURES = "backend/features.py"
CONTRACT = "docs/dev/CONTRACT.md"
ARCHITECTURE = "docs/dev/ARCHITECTURE.md"
MANIFEST = "plugin.yaml"
STEP_WORDS = "page/pages/build/transcript/step-words.js"
TOOL_PREFIX = "chromatic_"
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def features(plan: Plan) -> list[str]:
    tree = ast.parse(plan.read(FEATURES))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FEATURES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise Failure(f"{FEATURES} has no FEATURES list", f"restore {FEATURES} (git checkout -- {FEATURES})")


def known_feature(plan: Plan, name: str) -> str:
    check_name(name, SNAKE, "feature", "history")
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
    known_feature(plan, feature_name)
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
        f"call it from the page as RPC_{const(name)} (import it from '#app/rpc.js')",
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


def tool(plan: Plan, feature_name: str, name: str, step: list[str] | None) -> str:
    known_feature(plan, feature_name)
    short = check_name(name.removeprefix(TOOL_PREFIX), SNAKE, "tool", "game_info")
    full = TOOL_PREFIX + short
    manifest = plan.read(MANIFEST)
    listed = re.findall(r"^  - (\w+)$", manifest.split("provides_tools:")[-1], re.M)
    if full in listed or full in engine_tools(plan) or re.search(rf"^  {short}: ", plan.read(STEP_WORDS), re.M):
        raise Failure(f"a tool named {full} exists (plugin.yaml, the engine or step-words.js)", "pick another name")
    running, done = step or (f"Running {short.replace('_', ' ')}", f"Ran {short.replace('_', ' ')}")
    for text in (running, done):
        if "'" in text or "\\" in text or "\n" in text:
            raise Failure("step words go into a quoted JavaScript string", "use words without quotes or backslashes")
    values = {"name": feature_name, "Name": label(feature_name), "tool": full, "short": short, "Short": pascal(short)}
    values |= {"TOOL": const(short), "words": repr((running, done)).replace("'", '"')}
    source = f"backend/{feature_name}/tools.py"
    plan.ensure(source, render("tool", "tools.py.tmpl", **values))
    entry = f"    Tool({const(short)}_TOOL, {short}_handler, step_words=({running!r}, {done!r})),".replace("'", '"')
    plan.edit(source, lambda text: _add_tool(text, render("tool", "tool.py.tmpl", **values), entry))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    plan.create(f"tests/backend/{feature_name}/test_tool_{short}.py", render("tool", "test_tool.py.tmpl", **values))
    owned = [tool_name for tool_name in listed if tool_name not in engine_tools(plan)]
    anchor = re.compile(rf"^  - {owned[-1]}$" if owned else r"^provides_tools:")
    plan.edit(MANIFEST, lambda text: insert_after(text, anchor, f"  - {full}", MANIFEST, last=False))
    words_line = f"  {short}: ['{running}', '{done}'],"
    plan.edit(STEP_WORDS, lambda text: insert_before(text, re.compile(r"^  skill_view: "), words_line, STEP_WORDS))
    plan.edit(CONTRACT, lambda text: _contract_tool(text, full, feature_name))
    readme(plan, feature_name, "Tools", f"`{full}`")
    plan.regenerate = True
    plan.next_steps += [
        f"write the schema and handler in {source}; describe {full} in {CONTRACT} (its line says what it does)",
        f"the Build page shows it as '{running}' / '{done}' ({STEP_WORDS}; change both sides together)",
    ]
    return f"tool {full}"


def _add_tool(text: str, block: str, entry: str) -> str:
    tree = ast.parse(text)
    found = next(
        (n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "TOOLS" for t in n.targets)),
        None,
    )
    if found is None:  # one entry: ruff keeps a one-element tuple on one line
        return text.rstrip("\n") + "\n" + block + "\n\nTOOLS = (" + entry.strip() + ")\n"
    lines = text.split("\n")
    if isinstance(found.value, ast.Tuple) and found.lineno == found.end_lineno:  # TOOLS = (Tool(...),)
        inner = lines[found.lineno - 1].split("=", 1)[1].strip()[1:-1].strip()
        lines[found.lineno - 1 : found.lineno] = ["TOOLS = (", "    " + inner, ")"]
        text = "\n".join(lines)
        found = next(
            n for n in ast.parse(text).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "TOOLS"
        )
        lines = text.split("\n")
    if not isinstance(found.value, ast.Tuple) or lines[found.end_lineno - 1].strip() != ")":
        raise Failure(
            "TOOLS is not a tuple ending in a ')' line", "add the Tool(...) entry to TOOLS by hand:\n" + entry
        )
    head, tools_lines, rest = (
        lines[: found.lineno - 1],
        lines[found.lineno - 1 : found.end_lineno - 1],
        lines[found.end_lineno - 1 :],
    )
    if tools_lines and not tools_lines[-1].rstrip().endswith((",", "(")):
        tools_lines[-1] += ","
    return "\n".join(head).rstrip("\n") + "\n" + block + "\n\n" + "\n".join(tools_lines + [entry] + rest)


def _contract_tool(text: str, full: str, feature_name: str) -> str:
    def bump(match: re.Match) -> str:
        return match.group(1) + str(int(match.group(2)) + 1) + match.group(3)

    text, total = re.subn(r"(the )(\d+)( tools,)", bump, text, count=1)
    text, sum_ = re.subn(r"()(\d+)( in total)", bump, text, count=1)
    words = {word: number for number, word in NUMBER_WORDS.items()}

    def plus(match: re.Match) -> str:
        current = words.get(match.group(2), int(match.group(2)) if match.group(2).isdigit() else None)
        if current is None:
            raise Failure(f"{CONTRACT}: cannot read '{match.group(0)}'", "update the tool counts there by hand")
        return match.group(1) + NUMBER_WORDS.get(current + 1, str(current + 1))

    text, extra = re.subn(r"(\d+ tools, plus\s+)(\w+)", plus, text, count=1)
    if not (total and sum_ and extra):
        raise Failure(f"{CONTRACT}: the tool counts are not where they were", "update them by hand, then run check")
    line = f"- `{full}` (`backend/{feature_name}/tools.py`): say what it does and when the agent calls it."
    return insert_after(text, re.compile(r"in total\.$"), line, CONTRACT, last=False)


def event(plan: Plan, feature_name: str, name: str, payload: str | None) -> str:
    known_feature(plan, feature_name)
    check_name(name, SNAKE, "event", "build_kept")
    if name in ("emit", "annotations"):
        raise Failure(f"'{name}' would shadow a name emits.py uses", "pick another event name, e.g. build_kept")
    full = f"{feature_name}.{name}"
    payload = one_line(payload or "what happened; key=<value> for each keyword argument", "payload")
    for door in plan.top.glob("backend/*/__init__.py"):
        if f'"{full}"' in plan.read(str(door.relative_to(plan.top))):
            raise Failure(f"the event {full} is declared already ({door.relative_to(plan.top)})", "pick another name")
    door = f"backend/{feature_name}/__init__.py"
    comment = f'    # emits.{name}(...) where it happens (emit("{full}", ...)); others: @on("{full}") in listeners.py'
    plan.edit(door, lambda text: _add_event(text, comment, f"    {json.dumps(full)}: {json.dumps(payload)},"))
    row = f"| `{full}` | {payload} | say when | — |"
    plan.edit(
        CONTRACT,
        lambda text: in_section(
            text,
            "## Events between backend features",
            lambda body: insert_after(body, re.compile(r"^\| `"), row, CONTRACT),
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
        f"call emits.{name}(...) in backend/{feature_name}/ where it happens (from .emits import {name}); "
        f"fill its CONTRACT row",
        f'react in another feature\'s listeners.py: @on("{full}") (backend/system/events.py)',
    ]
    return f"event {full}"


def _add_event(text: str, comment: str, entry: str) -> str:
    tree = ast.parse(text)
    for node in tree.body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else (node.targets[0] if isinstance(node, ast.Assign) else None)
        )
        if getattr(target, "id", "") != "EVENTS" or not isinstance(node.value, ast.Dict):
            continue
        lines = text.split("\n")
        first, last = node.lineno - 1, node.end_lineno - 1
        if first == last:  # EVENTS = {} on one line
            opening = lines[first][: lines[first].rindex("{") + 1]
            return "\n".join(lines[:first] + [opening, comment, entry, "}"] + lines[first + 1 :])
        if lines[last].strip() != "}":
            raise Failure("EVENTS does not end in a '}' line", "add the entry by hand:\n" + entry)
        if not lines[last - 1].rstrip().endswith((",", "{")):
            lines[last - 1] += ","
        return "\n".join(lines[:last] + [comment, entry] + lines[last:])
    raise Failure("the front door has no EVENTS dict", "add EVENTS = {} to it (backend/system/events.py)")
