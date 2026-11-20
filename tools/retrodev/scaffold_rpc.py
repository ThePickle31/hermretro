"""`new rpc --module <name>`: the RPC's handler factory in backend/<feature>/<name>.py, declared in rpcs.py.

tools/bundle/rpc_names.py (the page's generated RPC names) and tests/repo/test_lockstep.py read the @rpc
declarations in backend/*/rpcs.py only, and backend/hermes/declare.py collects what rpcs.py declares: so the
@rpc stays in rpcs.py, as a short function that calls the factory in the module (``from . import <name>``), and the
handler's code lives in the module. Without --module, an rpcs.py over big_rpcs() lines (tools/layout.toml [size] warn,
less MODULE_MARGIN) gets a note suggesting it.
Nothing is written here: it fills scaffold.py's Plan.
"""

from __future__ import annotations

import ast
import re
import textwrap
import tomllib
from pathlib import Path

from .output import Failure
from .scaffold import SNAKE, Plan, check_name, render
from .scaffold_source import MODULE_TAKEN, bindings, check_front_door_name, imports_sibling, module_names

RPCS = "backend/{feature}/rpcs.py"

LAYOUT = "tools/layout.toml"
OWN_LAYOUT = Path(__file__).resolve().parents[1] / "layout.toml"
MODULE_MARGIN = 50  # new rpc suggests --module this many lines before the layout's warning, so a handler lands first


def big_rpcs(layout: str | None = None) -> int:
    """The rpcs.py length past which new rpc suggests --module: the one size rule's `warn` (tools/layout.toml
    [size]) less MODULE_MARGIN. ``layout`` is that file's text (the tree new edits); else the one beside this code."""
    if layout is None:
        layout = OWN_LAYOUT.read_text(encoding="utf-8") if OWN_LAYOUT.is_file() else ""
    try:
        warn = int(tomllib.loads(layout).get("size", {}).get("warn", 400))
    except (tomllib.TOMLDecodeError, TypeError, ValueError):
        warn = 400  # the rule as the layout has always written it
    return warn - MODULE_MARGIN


def alias(module: str) -> str:
    """The private name rpcs.py imports ``module`` as: never an ``rpc_<x>`` wrapper or a public name."""
    return f"_{module}_mod"


def imports_aliased(text: str, module: str) -> bool:
    """Whether rpcs.py has a top-level ``from . import <module> as _<module>_mod`` already."""
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is None
        and any(name.name == module and name.asname == alias(module) for name in node.names)
        for node in ast.parse(text).body
    )


def rpcs_text(plan: Plan, source: str, values: dict) -> str:
    """rpcs.py as new finds it: the file, or the template's when it is new."""
    return plan.read(source) if plan.exists(source) else render("rpc", "rpcs.py.tmpl", **values)


def refuse_bound(text: str, source: str, names: list[str]) -> None:
    """Refuse, before anything is planned, a name new would add to rpcs.py that it binds already (an import, a def,
    an assignment): the new binding would replace it, and whatever used it would break."""
    for name in names:
        if bindings(text, name):
            raise Failure(
                f"{source} binds {name} already, so the RPC new adds would rebind it (and break what uses it); "
                "nothing was written",
                "pick another RPC name" + ("" if name.startswith("rpc_") else " or --module name"),
            )


def appended(text: str, block: str, source: str, names: list[str], imported: tuple[str, ...] = ()) -> str:
    """``text`` with ``block`` at its end: refused when ``text`` binds one of ``names`` already, or when the result
    (parsed) binds one of ``names`` or ``imported`` (the alias the edit before added) other than exactly once."""
    refuse_bound(text, source, names)
    result = text.rstrip("\n") + "\n" + block
    for name in (*names, *imported):
        if len(bindings(result, name)) != 1:
            raise Failure(
                f"{source} would bind {name} more than once after new's edit; nothing was written",
                "pick another RPC name, or add it by hand",
            )
    return result


def inline(plan: Plan, feature_name: str, values: dict) -> str:
    """Plan the RPC's factory (with its @rpc) at the end of rpcs.py; its path."""
    source = RPCS.format(feature=feature_name)
    names = [f"rpc_{values['rpc']}"]
    refuse_bound(rpcs_text(plan, source, values), source, names)
    plan.ensure(source, render("rpc", "rpcs.py.tmpl", **values))
    block = render("rpc", values.get("handler", "rpc.py.tmpl"), **values)
    plan.edit(source, lambda text: appended(text, block, source, names))
    return source


def rpc_module(plan: Plan, feature_name: str, module: str, values: dict) -> str:
    """Refuse a --module name that would not end up as the RPC's own module, before anything is planned: checked
    against rpcs.py as it will be (the template's when it is new) and the wrapper this RPC adds to it."""
    check_name(module, SNAKE, "module", "game_rpcs")
    if module in MODULE_TAKEN:
        raise Failure(
            f"--module {module} is a name every feature keeps for its own part (hermes/declare.py); nothing was written",
            "pick another module name, e.g. --module game_rpcs",
        )
    door, source, home = (f"backend/{feature_name}/{name}.py" for name in ("__init__", "rpcs", module))
    if plan.exists(door):
        check_front_door_name(plan.read(door), door, module)
    wrapper = f"rpc_{values['rpc']}"
    if module == wrapper:
        raise Failure(
            f"--module {module} is the name of the @rpc declaration new writes in {source}, so it would call into "
            "itself instead of the module; nothing was written",
            f"pick another module name, e.g. --module {values['rpc']}_rpcs",
        )
    text = rpcs_text(plan, source, values)
    refuse_bound(text, source, [wrapper] + ([] if imports_aliased(text, module) else [alias(module)]))
    if bindings(text, module) and not imports_sibling(text, module):
        raise Failure(
            f"{source} binds {module} already (not as `from . import {module}`), so the declaration would call "
            "into that instead of the new module; nothing was written",
            f"pick another module name, e.g. --module {module}_rpcs",
        )
    if plan.exists(home) and "logger" not in module_names(plan.read(home)):
        raise Failure(
            f"{home} exists and is not an RPC module new wrote (it binds no logger); nothing was written",
            f"pick another module name, e.g. --module {module}_rpcs",
        )
    return module


def with_sibling(text: str, module: str) -> str:
    """``from . import <module> as _<module>_mod`` after rpcs.py's last top-level import (unchanged when it is
    there); refused when the alias is bound some other way."""
    if imports_aliased(text, module):
        return text
    if bindings(text, alias(module)):
        raise Failure(f"rpcs.py binds {alias(module)} already; nothing was written", "pick another --module name")
    tree = ast.parse(text)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    lines = text.split("\n")
    at = imports[-1].end_lineno if imports else 0
    return "\n".join(lines[:at] + [f"from . import {module} as {alias(module)}"] + lines[at:])


def in_module(plan: Plan, feature_name: str, module: str, values: dict) -> str:
    """Plan the factory in backend/<feature>/<module>.py and its @rpc declaration in rpcs.py; the module's path."""
    home = f"backend/{feature_name}/{rpc_module(plan, feature_name, module, values)}.py"
    source = f"backend/{feature_name}/rpcs.py"
    values = {**values, "module": module, "alias": alias(module)}
    plan.ensure(home, render("rpc", "rpc_module.py.tmpl", **values))
    factory = (
        render("rpc", values.get("handler", "rpc.py.tmpl"), **values).lstrip("\n").split("\n", 1)[1]
    )  # no @rpc: rpcs.py declares it
    if f"def rpc_{values['rpc']}(" in plan.read(home):
        raise Failure(f"{home} defines rpc_{values['rpc']} already; nothing was written", "pick another RPC name")
    plan.edit(home, lambda text: text.rstrip("\n") + "\n\n\n" + factory)
    plan.ensure(source, render("rpc", "rpcs.py.tmpl", **values))
    plan.edit(source, lambda text: with_sibling(text, module))
    declared = render("rpc", "rpc_declared.py.tmpl", **values)
    plan.edit(source, lambda text: appended(text, declared, source, [f"rpc_{values['rpc']}"], (alias(module),)))
    return home


def needs_host(plan: Plan, source: str) -> None:
    """A --game handler calls host._game_root: the module it went into imports host (rpcs.py's template does)."""
    from .scaffold_tool import with_import  # scaffold_tool imports scaffold_backend, which imports this module

    plan.edit(source, lambda text: with_import(text, "from ..hermes import host", ("host",)))


def big_note(plan: Plan, feature_name: str, name: str) -> None:
    """Without --module: a note when rpcs.py is long already."""
    source = f"backend/{feature_name}/rpcs.py"
    size = len(plan.read(source).splitlines()) if plan.exists(source) else 0
    if size > big_rpcs(plan.read(LAYOUT) if plan.exists(LAYOUT) else None):
        plan.notes.append(
            f"{source} has {size} lines: python tools/retrodev new rpc {feature_name} {name} --module {name}_rpcs puts "
            "the handler in its own module (rpcs.py keeps a short @rpc declaration that calls it)"
        )


CONTRACT = "docs/dev/CONTRACT.md"
PAGE_RPCS = "## Studio pages (desktop) and their RPCs"  # its table lists RPCs the pages call
# Features whose RPCs usually read the hermretro profile's plugin data folder (host._data_dir()) or its Build chats:
# the suggested page code calls them with callStudioOnly (page/app/backend.js). The rule is what the handler reads,
# so the step says to check; any other feature's suggestion is callStudio.
STUDIO_ONLY = ("history", "assets")


def page_steps(plan: Plan, feature_name: str, name: str, source: str, game: bool) -> list[str]:
    """new rpc's next steps for the handler and the page: one rule for the call, the query key and where it runs."""
    constant, only = f"RPC_{name.upper()}", feature_name in STUDIO_ONLY
    call = "callStudioOnly" if only else "callStudio"
    steps = [
        f"write the handler in {source} and its section in {CONTRACT} (params, result)",
        f"call it from the page: import {{ {constant} }} from '#app/rpc.js' (re-exports the generated rpc-names.js)",
        "callStudioOnly (page/app/backend.js; the hermretro profile only) if the handler reads or binds a "
        "profile's Build conversations or its plugin data folder (host._data_dir(): snapshots, asset versions); "
        "otherwise callStudio (whichever profile answered status serves it, as for the library): what the handler "
        "reads decides, not the feature"
        + (
            f"; the code below uses callStudioOnly because {' and '.join(STUDIO_ONLY)} RPCs usually do: check what "
            "yours reads"
            if only
            else ""
        ),
        "callStudio and callStudioOnly resolve to the RPC's answer itself (data.ok, ...); callBackend resolves to "
        "{ data } (read .data): page/app/backend.js",
    ]
    imports = f"(useQuery from '#sdk', ID from '#app/ids.js', {call} from '#app/backend.js')"
    if game:
        steps += [
            "check what the `games` RPC already returns about a game (rom, state, web, ...) before adding a per-game "
            "query (its row in docs/dev/CONTRACT.md; backend/library/rpcs.py): the page may have it already",
            "its test registers a library game with tests.support.make_library_game(home, name) -> (game id, root), "
            "home being what isolated_home(self) returns; host._game_root(game) gives the project root",
            f"run the query in the component that has the game (as page/pages/emulator/emulator-bar.js runs "
            f"captures): useQuery({{ queryKey: [ID, '{name}', game.id], queryFn: () => {call}({constant}, "
            f"{{ game: game.id }}) }}) {imports}: the game's id in the key gives each game its own answer (no "
            "viaProfile there, as with captures and player; only the games list keys on it)",
        ]
    else:
        key = f"[ID, '{name}']" if only else f"[ID, '{name}', shell.viaProfile]"
        steps.append(
            f"in a page, put useQuery({{ queryKey: {key}, queryFn: () => {call}({constant}) }}) {imports} in the "
            "page's own Page component, or a hook it calls (as page/pages/setup/install/installer.js's useInstall "
            "does for the Setup page), and pass the result down as a prop"
            + ("" if only else " (viaProfile only with callStudio: the answer depends on the profile)")
        )
    steps += [
        f"keep the queryKey's second word '{name}': page tests answer by it, scenario.{name} = answered({{ ok: "
        "true, ... }) (tests/page/harness.mjs), set before the page renders; extend tests/page/page-<page>.test.mjs",
        f"a page test can assert the page asked for it: scenario.queries.some(q => q.key === '{name}') (the stub's "
        "useQuery records each query, tests/page/sdk-stub.mjs)",
        "a page that reads a new shell field adds it to its fixture in tests/page/shells.mjs (homeShell())",
        f"RPC names are global and flat: the page calls plugin.hermretro.{name}, whatever feature declares it",
        "if a page shows it, describe it in that page's README **Shows:** line and as a bullet in its `### <Page>` "
        "subsection under `## Pages` of docs/dev/STUDIO-PAGES.md (the table row stays short)",
    ]
    listed = page_rpcs(plan.read(CONTRACT) if plan.exists(CONTRACT) else "")
    if listed:
        steps.append(
            f"a page calls it: add its row to the RPC table under {CONTRACT} '{PAGE_RPCS[3:]}' (it lists "
            f"{', '.join(listed)}): | `{name}` | <params> | <result> |"
        )
    return steps


def page_rpcs(contract: str) -> list[str]:
    """The RPCs the table under CONTRACT.md's page section lists (none when that section or table is gone)."""
    start = contract.find(PAGE_RPCS + "\n")
    if start < 0:
        return []
    body = contract[start + len(PAGE_RPCS) :]
    body = body[: body.find("\n## ")] if "\n## " in body else body
    return re.findall(r"^\| `(\w+)` \|", body, re.M)


DOCSTRING = re.compile(r'\A(\s*)"""(.*?)"""', re.S)
WIDTH = 120  # the line length the Python lint allows


def docstring_listed(text: str, name: str) -> str | None:
    """rpcs.py with ``name`` added last to the list of its RPCs its module docstring gives (``status, doctor and
    install`` -> ``status, doctor, install and <name>``, the paragraph rewrapped at WIDTH when it grows past it), or
    None when the docstring lists none: every RPC the file declares (two at least), as `a, b and c`."""
    found = DOCSTRING.match(text)
    declared = [rpc for rpc in re.findall(r'@rpc\("(\w+)"\)', text) if rpc != name]
    if not found or len(declared) < 2:
        return None
    word = "(?:" + "|".join(re.escape(rpc) for rpc in sorted(declared, key=len, reverse=True)) + ")"
    listed = re.compile(rf"(?<![\w`])({word}(?:,\s+{word})*)(\s+and\s+)({word})(?![\w`])")
    doc = found.group(2)
    match = next(
        (m for m in listed.finditer(doc) if set(re.findall(r"\w+", m.group(1)) + [m.group(3)]) == set(declared)), None
    )
    if not match:  # a list of some of them is about something else (library's "the real player and captures")
        return None
    joined = match.group(1) + ", " + match.group(3) + match.group(2) + name
    doc = doc[: match.start()] + joined + doc[match.end() :]
    paragraphs = doc.split("\n\n")
    at = doc[: match.start()].count("\n\n")
    head, tail = ('"""' if at == 0 else ""), ('"""' if at == len(paragraphs) - 1 else "")
    whole = head + paragraphs[at] + tail
    if max(len(line) for line in whole.split("\n")) > WIDTH:  # the line the name went into grew too long: rewrap
        wrapped = textwrap.fill(" ".join(whole.split()), WIDTH, break_on_hyphens=False, break_long_words=False)
        paragraphs[at] = wrapped[len(head) : len(wrapped) - len(tail)]
    return text[: found.start(2)] + "\n\n".join(paragraphs) + text[found.end(2) :]


def listed_in_docstring(plan: Plan, source: str, name: str) -> None:
    """new rpc's edit of rpcs.py's docstring (docstring_listed), said on a done: line; nothing when it lists none."""
    if not plan.exists(source) or docstring_listed(plan.read(source), name) is None:
        return
    plan.edit(source, lambda text: docstring_listed(text, name) or text)
    plan.done.append(f"added `{name}` to the list of RPCs in {source}'s docstring")


HARNESS = ("tests/page/sdk-stub.mjs", "tests/page/harness.mjs")  # where the page test harness fills `scenario`


def reserved_scenario(plan: Plan) -> set[str]:
    """The keys the page test harness keeps on `scenario` for itself (the host storage stub, the call log, ...), read
    from its files: the scenario literal's keys and every `scenario.<key>` the code uses, less the query answers
    (a literal key defaulting to null, or one a helper sets to answered(...): status, doctor). A query key, which
    is the RPC name, must not be one of them: scenario[<name>] is what a query answers."""
    keys, answers = set(), set()
    for rel in HARNESS:
        if not plan.exists(rel):
            continue
        code = re.sub(r"(?m)^\s*//.*$|//[^\n'`]*$", "", plan.read(rel))
        literal = re.search(r"export const scenario = \{(.*?)\n\}", code, re.S)
        for key, value in re.findall(r"(\w+):\s*([^,\n]+)", literal.group(1) if literal else ""):
            (answers if value.strip() == "null" else keys).add(key)
        keys |= set(re.findall(r"\bscenario\.(\w+)", code))
        answers |= set(re.findall(r"\bscenario\.(\w+)\s*=\s*answered\(", code))
    return keys - answers


def refuse_reserved(plan: Plan, name: str) -> None:
    """new rpc NAME where the page test harness reserves scenario.NAME: a page test could never answer its query."""
    if name in reserved_scenario(plan):
        raise Failure(
            f"the page test harness reserves scenario.{name} ({' or '.join(HARNESS)}), and a page test answers a "
            f"query by its RPC name (scenario.<rpc>); nothing was written",
            f"pick another RPC name (for example {name}_info, or a more specific one such as disk_usage)",
        )
