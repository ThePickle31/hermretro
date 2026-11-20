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
from .scaffold_payload import emitter_values, payload_keys, placeholders, split_parts, undescribed
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
MOCKED = re.compile(r"mock\.patch\.object\(hermes_host,\s*[\"'](\w+)[\"']")


def payload_of(plan: Plan, event: str, doc: str) -> list[str]:
    """The event's payload keys: the leading backticked name of each top-level entry of its CONTRACT row's Payload
    cell ('`game` (the game's id, `null` without a project), `assets`' -> game, assets: a name inside an entry's
    description is not a key), else its EVENTS doc after '; '."""
    for line in plan.read(CONTRACT).splitlines() if plan.exists(CONTRACT) else []:
        if line.startswith(f"| `{event}` |"):
            cells = line.strip().strip("|").split(" | ")
            parts = split_parts(cells[1]) if len(cells) > 1 else []
            keys = [found.group(1) for part in parts if (found := re.match(r"\s*`([A-Za-z_]\w*)`", part))]
            if keys:
                return list(dict.fromkeys(keys))
    return payload_keys(doc.partition("; ")[2]) if "; " in doc else []


def mocked_helpers(plan: Plan, owner: str) -> list[str]:
    """The emitting feature's tests that patch backend.hermes.host helpers ('file (helper, ...)'): an emitter they
    call now runs the new listener against those mocks."""
    found = []
    for path in sorted(plan.top.glob(f"tests/backend/{owner}/*.py")):
        names = list(dict.fromkeys(MOCKED.findall(path.read_text(encoding="utf-8", errors="replace"))))
        if names:
            found.append(f"{path.relative_to(plan.top)} ({', '.join(names)})")
    return found


def test_template(plan: Plan) -> str:
    """The listener test calls tests/support.py's isolated_home(self) where that helper exists; otherwise it makes
    the same temp HERMRETRO_HOME and plugin data folder itself."""
    has = plan.exists(SUPPORT) and re.search(r"^def isolated_home\(", plan.read(SUPPORT), re.M)
    return "test_listener_isolated.py.tmpl" if has else "test_listener.py.tmpl"


LISTENS = "say what this listener does"  # the README entry's placeholder (tests/repo/test_placeholders.py)


FILE = "(`listeners.py`)"  # the README names the file, as assets' line does: 'Listens to (`listeners.py`): ...'


def listens_line(text: str, item: str) -> str:
    """The README's 'Listens to' sentence (mid-line, after 'Events emitted'), naming listeners.py: each listened
    event is an entry of its own, '`event` — what it does'; the new one says '— say what this listener does' (the
    placeholder gate refuses it until it is written). 'none' becomes the entry, else it goes after the last one."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if "Listens to" not in line:
            continue
        head, sep, rest = line.partition("Listens to")
        if rest.startswith(":"):
            rest = f" {FILE}{rest}"
        end = re.search(r"\.(?=\s|$)", rest)
        segment, tail = (rest[: end.start()], rest[end.start() :]) if end else (rest, "")
        entry = f"{item} — {LISTENS}"
        if re.search(r"\bnone\b", segment):
            segment = re.sub(r"\bnone\b", lambda _match, entry=entry: entry, segment, count=1)
        else:
            segment = segment.rstrip() + f"; {entry}"
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


def catch_all(keys: list[str]) -> str:
    """The listener's **name for keys the event gains later: _payload, else _rest, _rest2, ... (the first that is
    not a payload key, so the signature never names one argument twice)."""
    for name in ("_payload", "_rest", *(f"_rest{n}" for n in range(2, len(keys) + 3))):
        if name not in keys:
            return name
    raise AssertionError("unreachable: more candidate names than keys")


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
    keys = payload_of(plan, event, declared[event])
    values["call"] = emitter_values(keys)["sample"]  # the test calls it with the declared payload's keys
    named = emitter_values(keys)["params"]  # keyword-only, one per payload key; later keys still arrive in **_payload
    rest = catch_all(keys)  # never one of the keys: a key named _payload would be bound twice
    values["params"] = f"**{rest}" if named == "**payload" else f"{named}, **{rest}"
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
    on_readme = False
    if plan.exists(readme):
        before = plan.read(readme)
        plan.edit(readme, lambda body: listens_line(body, f"`{event}`"))
        if plan.read(readme) == before:
            plan.notes.append(f"name `{event}` under 'Listens to' in {readme} (its line did not have the usual shape)")
        on_readme = LISTENS in plan.read(readme) and LISTENS not in before
    for rel, change in ((CONTRACT, heard_by), (ARCHITECTURE, agent_half)):
        before = plan.read(rel)
        try:
            plan.edit(rel, lambda body, change=change: change(body, event, feature_name))
        except Failure:  # the section is not there: say so instead of refusing the listener
            pass
        if plan.read(rel) == before:
            plan.notes.append(f"{rel} has no row to name it in: say there that {feature_name} listens to {event}")
    readme_step = (
        f", and '{LISTENS}' in {readme}'s 'Listens to' entry for `{event}`"
        if on_readme
        else "; say it on the README's 'Listens to' line too"
    )
    plan.next_steps += [
        f"write what {feature_name} does in {source} ({func}; it gets the payload: {values['payload']})",
        f"replace the placeholders new wrote: '{feature_name} (say what it does)' in the 'Heard by' cell of "
        f"{event} in {CONTRACT}, '{LISTENS}' in {func}'s docstring" + readme_step,
        f'tests that call the emitter (grep -rn \'emit("{event}"\' backend tests) now run your listener: give them '
        "isolated_home(self) (tests/support.py) in setUp, so it never touches the real home",
        f"if other code reads what the listener keeps, export the reader in backend/{feature_name}/__init__.py "
        f"__all__ and name it on the README Front door line ({readme}); state other processes must read goes in a "
        "file under backend.system.paths.hermretro_home(), written atomically, not module state",
        f"test what the listener does, not only that it runs: in {test}, call {func} with a real payload and "
        "assert what it changed",
    ]
    entry = declared[event] or ""
    bare = [key for key in undescribed(entry.partition("; ")[2]) if f"{key}=<...>" in entry]
    if bare:
        owner = event.partition(".")[0]
        plan.next_steps.append(
            f"{func}'s docstring copies {event}'s EVENTS entry, whose placeholders {placeholders(bare)} say nothing "
            f"yet: replace them there and in backend/{owner}/__init__.py EVENTS with what each key holds"
        )
    if {"path", "root"} & set(keys) and "game" not in keys:
        plan.next_steps.append(
            "find the library game with host.library_game_for([path]); in tests register one with "
            "tests.support.make_library_game(home, name) -> (game_id, root)"
        )
    mocked = mocked_helpers(plan, event.partition(".")[0])
    if mocked:
        plan.next_steps.append(
            "these emitter tests mock backend.hermes.host helpers, and the listener now runs against those mocks "
            "when they emit: " + "; ".join(mocked)
        )
    return f"listener {feature_name} <- {event}"
