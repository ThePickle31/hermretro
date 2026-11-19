"""`new listener <feature> <event>`: an @on function in backend/<feature>/listeners.py (made when missing), its test,
the feature README's "Listens to", the CONTRACT events row's "Heard by" cell and the feature's row in
ARCHITECTURE.md "The agent half". Nothing is written here: it fills scaffold.py's Plan.

backend/system/events.py imports every listed feature's listeners.py on the first emit, so the file needs no
registration line. The event must be declared in its owner's front door EVENTS (tests/repo/test_boundaries.py
refuses a listened name nothing declares).
"""

from __future__ import annotations

import ast
import re

from .output import Failure
from .scaffold import Plan, in_section, label, pascal, render
from .scaffold_backend import ARCHITECTURE, CONTRACT, known_feature
from .scaffold_source import module_names

EVENT = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def declared_events(plan: Plan) -> dict[str, str]:
    """{event: payload} from every front door's EVENTS dict literal."""
    found = {}
    for door in sorted(plan.top.glob("backend/*/__init__.py")):
        tree = ast.parse(plan.read(str(door.relative_to(plan.top))))
        for node in tree.body:
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
            target = node.target if isinstance(node, ast.AnnAssign) else target
            if getattr(target, "id", "") == "EVENTS" and isinstance(getattr(node, "value", None), ast.Dict):
                for key, value in zip(node.value.keys, node.value.values, strict=True):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        found[key.value] = value.value if isinstance(value, ast.Constant) else ""
    return found


SUPPORT = "tests/support.py"


def test_template(plan: Plan) -> str:
    """The listener test calls tests/support.py's isolated_home(self) where that helper exists; otherwise it makes
    the same temp HERMRETRO_HOME and plugin data folder itself."""
    has = plan.exists(SUPPORT) and re.search(r"^def isolated_home\(", plan.read(SUPPORT), re.M)
    return "test_listener_isolated.py.tmpl" if has else "test_listener.py.tmpl"


def listens_line(text: str, item: str) -> str:
    """The README's 'Listens to' sentence (mid-line, after 'Events emitted'): 'none' becomes the item, else the item
    goes after the last event it names."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if "Listens to" not in line:
            continue
        head, sep, rest = line.partition("Listens to")
        end = re.search(r"\.(?=\s|$)", rest)
        segment, tail = (rest[: end.start()], rest[end.start() :]) if end else (rest, "")
        if re.search(r"\bnone\b", segment):
            segment = re.sub(r"\bnone\b", lambda _match: item, segment, count=1)
        else:
            names = list(re.finditer(r"`[a-z0-9_]+\.[a-z0-9_]+`", segment))
            at = names[-1].end() if names else len(segment.rstrip())
            segment = segment[:at] + ", " + item + segment[at:]
        lines[index] = head + sep + segment + tail
        return "\n".join(lines)
    return text


def heard_by(text: str, event: str, feature: str) -> str:
    """The CONTRACT events row's last cell ('Heard by') names the feature."""

    def change(body: str) -> str:
        lines = body.split("\n")
        for index, line in enumerate(lines):
            if line.startswith(f"| `{event}` |"):
                cells = line.strip().strip("|").split(" | ")
                heard = cells[-1].strip()
                mine = f"{feature} (say what it does)"
                cells[-1] = mine if heard in ("", "—", "-") else f"{heard}, {mine}"
                lines[index] = "| " + " | ".join(cell.strip() for cell in cells) + " |"
                return "\n".join(lines)
        return body

    return in_section(text, "## Events between backend features", change)


def agent_half(text: str, event: str, feature: str) -> str:
    """The feature's row in ARCHITECTURE.md "The agent half": its last cell says what it listens to."""

    def change(body: str) -> str:
        lines = body.split("\n")
        for index, line in enumerate(lines):
            if line.startswith(f"| `backend/{feature}/` |"):
                row = line.rstrip().removesuffix("|").rstrip()
                more = f", `{event}`" if "listens to" in row.rsplit("|", 1)[-1] else f"; listens to `{event}`"
                lines[index] = row + more + " |"
                return "\n".join(lines)
        return body

    return in_section(text, "## The agent half", change)


def listener(plan: Plan, feature_name: str, event: str) -> str:
    known_feature(plan, feature_name, "listener")
    declared = declared_events(plan)
    if not EVENT.match(event or "") or event not in declared:
        listed = ", ".join(sorted(declared)) or "none yet"
        raise Failure(
            f"no front door declares the event '{event}' (a listener hears only a declared <owner>.<what happened>); "
            "nothing was written",
            f"python tools/retrodev new event <owner> <name> first, or pick a declared one: {listed}",
        )
    func = "on_" + event.replace(".", "_")
    source = f"backend/{feature_name}/listeners.py"
    values = {"name": feature_name, "Name": label(feature_name), "event": event, "func": func, "Func": pascal(func)}
    values["payload"] = declared[event] or "its payload"
    plan.ensure(source, render("listener", "listeners.py.tmpl", **values))
    text = plan.read(source)
    if f'@on("{event}")' in text or func in module_names(text):
        raise Failure(f"{source} listens to {event} already (or binds {func}); nothing was written", f"edit {source}")
    if "on" not in module_names(text):
        raise Failure(
            f"{source} does not import on (from ..system.events import on); nothing was written",
            f"add that import to {source}, then run new again",
        )
    plan.edit(source, lambda body: body.rstrip("\n") + "\n" + render("listener", "listener.py.tmpl", **values))
    plan.ensure(f"tests/backend/{feature_name}/__init__.py", "")
    test = f"tests/backend/{feature_name}/test_listener_{func}.py"
    plan.create(test, render("listener", test_template(plan), **values))
    readme = f"backend/{feature_name}/README.md"
    if plan.exists(readme):
        before = plan.read(readme)
        plan.edit(readme, lambda body: listens_line(body, f"`{event}`"))
        if plan.read(readme) == before:
            plan.notes.append(f"name `{event}` under 'Listens to' in {readme} (its line did not have the usual shape)")
    for rel, change in ((CONTRACT, heard_by), (ARCHITECTURE, agent_half)):
        before = plan.read(rel)
        try:
            plan.edit(rel, lambda body, change=change: change(body, event, feature_name))
        except Failure:  # the section is not there: say so instead of refusing the listener
            pass
        if plan.read(rel) == before:
            plan.notes.append(f"{rel} has no row to name it in: say there that {feature_name} listens to {event}")
    plan.next_steps += [
        f"write what {feature_name} does in {source} ({func}; it gets the payload: {values['payload']})",
        f"replace the two placeholders new wrote: '{feature_name} (say what it does)' in the 'Heard by' cell of "
        f"{event} in {CONTRACT}, and 'say what this listener does' in {func}'s docstring; say it on the README's "
        "'Listens to' line too",
        f'tests that call the emitter (grep -rn \'emit("{event}"\' backend tests) now run your listener: give them '
        "isolated_home(self) (tests/support.py) in setUp, so it never touches the real home",
    ]
    return f"listener {feature_name} <- {event}"
