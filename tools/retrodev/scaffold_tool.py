"""`new tool`: a Tool stub in backend/<feature>/tools.py (or a sibling module with its own TOOLS), its test,
plugin.yaml, the page's step words, CONTRACT and the README line. Nothing is written here: it fills scaffold.py's
Plan. scaffold_backend re-exports ``tool`` (the other backend kinds live there).
"""

from __future__ import annotations

import ast
import json
import re

from .count_words import count_text, count_value
from .output import Failure
from .scaffold import SNAKE, Plan, check_name, const, insert_after, insert_before, label, pascal, render
from .scaffold_backend import (
    BIG_MODULE,
    CONTRACT,
    MANIFEST,
    STEP_WORDS,
    TOOL_PREFIX,
    agent_half,
    declares,
    known_feature,
    readme,
)
from .scaffold_source import (
    add_tool,
    check_front_door_name,
    check_sibling_name,
    is_aggregator,
    js_str,
    module_names,
    py_str,
    take_in_module,
)


def engine_tools(plan: Plan) -> set[str]:
    found = set()
    for path in plan.top.glob("engine/pins/*/tools.json"):
        found |= {TOOL_PREFIX + tool["name"] for tool in json.loads(path.read_text(encoding="utf-8")).get("tools", [])}
    return found


MODULE_TAKEN = ("tools", "rpcs", "hooks", "prompt", "listeners", "emits")  # names a feature's own parts use


def tool_module(plan: Plan, feature_name: str, module: str) -> str:
    """Refuse a --module (or automatic <tool>_tools) name that would not end up as the new sibling module, before
    anything is planned: tools.py's ``from . import <module>`` must import exactly that module."""
    check_name(module, SNAKE, "module", "game_tools")
    if module in MODULE_TAKEN:
        raise Failure(
            f"--module {module} is a name every feature keeps for its own part (hermes/declare.py); nothing was written",
            "pick another module name, e.g. --module game_tools",
        )
    door, source, home = (f"backend/{feature_name}/{name}.py" for name in ("__init__", "tools", module))
    if plan.exists(door):
        check_front_door_name(plan.read(door), door, module)
    if plan.exists(source):
        check_sibling_name(plan.read(source), source, module)
    if plan.exists(home) and "TOOLS" not in module_names(plan.read(home)):
        raise Failure(
            f"{home} exists and has no TOOLS, so it is another module, not one of tools.py's; nothing was written",
            f"pick another module name, e.g. --module {module}_tools",
        )
    return module


TOOL_ARGS = "tool_args"  # backend/<feature>/tool_args.py: tool_error and tool_project (backend/library has it)
PROJECT_IMPORT = f"from .{TOOL_ARGS} import tool_error, tool_project"


def wants_project(plan: Plan, feature_name: str, project: bool | None) -> bool:
    """--project (default: on when the feature has tool_args.py, as library does; --no-project turns it off)."""
    has = plan.exists(f"backend/{feature_name}/{TOOL_ARGS}.py")
    if project and not has:
        raise Failure(
            f"--project needs backend/{feature_name}/{TOOL_ARGS}.py (tool_error, tool_project), which "
            f"{feature_name} does not have; nothing was written",
            f"declare the tool in library (it has them), or copy backend/library/{TOOL_ARGS}.py's helpers into "
            f"backend/{feature_name}/{TOOL_ARGS}.py first, or leave out --project",
        )
    return has if project is None else project


def with_import(text: str, line: str, names: tuple[str, ...]) -> str:
    """``line`` after the module's last top-level import, unless it binds ``names`` already."""
    if set(names) <= module_names(text):
        return text
    tree = ast.parse(text)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    lines = text.split("\n")
    at = imports[-1].end_lineno if imports else 0
    return "\n".join(lines[:at] + [line] + lines[at:])


def tools_line(text: str, module: str) -> str:
    """The README's Tools line names the sibling module the tool went into: 'Tools (`tools.py`, `<module>.py`)'."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        found = re.match(r"^(\s*[-*]\s*Tools)(?: \(([^)]*)\))?:", line)
        if not found or f"`{module}.py`" in (found.group(2) or ""):
            continue
        files = (found.group(2) or "`tools.py`") + f", `{module}.py`"
        lines[index] = f"{found.group(1)} ({files}):" + line[found.end() :]
        return "\n".join(lines)
    return text


def tool(
    plan: Plan,
    feature_name: str,
    name: str,
    step: list[str] | None,
    module: str | None = None,
    project: bool | None = None,
) -> str:
    known_feature(plan, feature_name, "tool")
    project = wants_project(plan, feature_name, project)
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
    index = plan.read(source) if plan.exists(source) else ""
    size = len(index.splitlines())
    if module is None and (size > BIG_MODULE or is_aggregator(index)):
        module = f"{short}_tools"
        why = (
            f"{source} has {size} lines, over {BIG_MODULE} (the layout test warns, and fails at 600)"
            if size > BIG_MODULE
            else f"{source} only takes in sibling modules' TOOLS (no Tool of its own)"
        )
        plan.notes.append(
            f"{why}: the tool goes in its own module backend/{feature_name}/{module}.py, with its own TOOLS, which "
            f"tools.py's TOOLS takes in (*{module}.TOOLS); --module <name> picks another name"
        )
    home = source if module is None else f"backend/{feature_name}/{tool_module(plan, feature_name, module)}.py"
    plan.ensure(home, render("tool", "tools.py.tmpl", **values))
    for where in dict.fromkeys(rel for rel in (source, home) if plan.exists(rel)):  # one name per tool, feature-wide
        taken = sorted({f"{const(short)}_TOOL", f"{short}_handler"} & module_names(plan.read(where)))
        if taken:  # a second binding would replace the first: the tool that uses it would lose its schema or handler
            raise Failure(
                f"{where} binds {' and '.join(taken)} already, which tool {full} would define; nothing was written",
                f"pick another tool name, e.g. python tools/retrodev new tool {feature_name} {short}_more",
            )
    entry = f"    Tool({const(short)}_TOOL, {short}_handler, step_words={words}),"
    block = render("tool", "tool_project.py.tmpl" if project else "tool.py.tmpl", **values)
    if project:
        plan.edit(home, lambda text: with_import(text, PROJECT_IMPORT, ("tool_error", "tool_project")))
    plan.edit(home, lambda text: add_tool(text, home, block, entry))
    if module is not None:
        plan.ensure(source, render("tool", "tools_index.py.tmpl", **values))
        plan.edit(source, lambda text: take_in_module(text, source, module))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    test = "test_tool_project.py.tmpl" if project else "test_tool.py.tmpl"
    plan.create(f"tests/backend/{feature_name}/test_tool_{short}.py", render("tool", test, **values))
    owned = [tool_name for tool_name in listed if tool_name not in engine_tools(plan)]
    anchor = re.compile(rf"^  - {owned[-1]}$" if owned else r"^provides_tools:")
    plan.edit(MANIFEST, lambda text: insert_after(text, anchor, f"  - {full}", MANIFEST, last=False))
    words_line = f"  {short}: [{js_str(running)}, {js_str(done)}],"
    plan.edit(STEP_WORDS, lambda text: insert_before(text, re.compile(r"^  skill_view: "), words_line, STEP_WORDS))
    plan.edit(CONTRACT, lambda text: _contract_tool(text, full, feature_name, home))
    readme(plan, feature_name, "Tools", f"`{full}`")
    agent_half(plan, feature_name, lambda row: declares(row, "tool", full))
    if module is not None and plan.exists(f"backend/{feature_name}/README.md"):
        plan.edit(f"backend/{feature_name}/README.md", lambda text: tools_line(text, module))
    plan.regenerate = True
    plan.next_steps += [
        f"write the schema and handler in {home}; describe {full} in {CONTRACT} (its line says what it does)"
        + (
            f"; it acts on a project: tool_project gives the `project` argument's folder, else this chat's ({TOOL_ARGS}.py)"
            if project
            else ""
        ),
        f"the Build page shows it as '{running}' / '{done}' ({STEP_WORDS}; change both sides together)",
    ]
    if project and feature_name == "library":
        plan.next_steps.append(
            'project files: backend/library/README.md "Project files"; title: games.project_title(root)'
        )
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
