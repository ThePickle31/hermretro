"""`new tab --from-page` moving a Page that index.js defines itself into the page's own ``<page>-page.js`` (a tab may
import only from the page's files: its index.js would be a cycle). Every edit comes from a real JavaScript parse:
scaffold_move.mjs reads each file with acorn (the pinned npm tools) and says where its imports, declarations,
exports and the Page (with the whole comments directly above it) are. Nothing is written here: it fills
scaffold.py's Plan, and a refusal comes before anything is planned.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .output import Failure
from .scaffold import Plan
from .scaffold_imports import add_reexport

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scaffold_move.mjs"
NPM_FIX = "npm ci --prefix tools/npm --ignore-scripts (Node 22 or newer), then run new tab again"


def acorn(top: Path) -> Path | None:
    """acorn's folder in the tree's pinned npm tools (this checkout's when the tree has none installed), or None
    when they lack it."""
    modules = top / "tools/npm/node_modules"
    folder = (modules if modules.is_dir() else HERE.parent / "npm/node_modules") / "acorn"
    return folder if (folder / "dist/acorn.mjs").is_file() else None


def parse(top: Path, text: str, where: str, page: str | None = None) -> dict:
    """What scaffold_move.mjs reads in ``text``: imports (code point ranges, source, specifiers), declarations,
    exports ({exported: local or None}), the names used outside the imports, and ``page``'s statement."""
    node, folder = shutil.which("node"), acorn(top)
    if not node or not folder:
        raise Failure(
            f"--from-page moves the Page {where} defines by parsing the JavaScript with acorn, and "
            + ("node is not installed" if not node else "the pinned npm tools are not installed")
            + "; nothing was written",
            NPM_FIX,
        )
    done = subprocess.run(
        [node, str(SCRIPT), str(folder), *([page] if page else [])], input=text, capture_output=True, text=True
    )
    found = json.loads(done.stdout) if done.returncode == 0 and done.stdout.startswith("{") else None
    if found is None or "error" in found:
        why = found["error"] if found else (done.stderr.strip().splitlines() or ["no output"])[-1]
        raise Failure(f"cannot parse {where}: {why}; nothing was written", f"fix {where}, then run new tab again")
    return found


def spec(kind: str, imported: str | None, local: str) -> str:
    if kind != "named":
        return local if kind == "default" else f"* as {local}"
    return local if imported == local else f"{imported} as {local}"


def statement(found: dict, specifiers: list[dict]) -> str:
    """One import statement, rebuilt from its parsed specifiers (no stray commas), its quotes and semicolon kept."""
    parts = [spec(s["kind"], s["imported"], s["local"]) for s in specifiers if s["kind"] != "named"]
    named = [spec("named", s["imported"], s["local"]) for s in specifiers if s["kind"] == "named"]
    parts += [f"{{ {', '.join(named)} }}"] if named else []
    return f"import {', '.join(parts)} from {found['raw']}" + (";" if found["semicolon"] else "")


def describe(kind: str, exported: str | None, module: str) -> str:
    """One import binding as words: "{ Small } from '#shared/ui/text.js'"."""
    what = {"named": f"{{ {exported} }}", "default": "the default export", "namespace": "the namespace"}[kind]
    return f"{what} from '{module}'"


def edit(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


def add_imports(top: Path, text: str, needed: list[tuple[str, str, str | None, str]], where: str) -> str:
    """``text`` with an import for each (kind, local, exported, module) it does not bind yet: a named one joins a
    one-line import of the same module (its specifiers rebuilt), the rest go after the last import statement."""
    info = parse(top, text, where)
    bound = {s["local"]: (s["kind"], s["imported"], i["source"]) for i in info["imports"] for s in i["specifiers"]}
    edits, lines, joined = [], [], {}
    for kind, name, exported, module in needed:
        have = bound.get(name)
        if have == (kind, exported if kind == "named" else None, module):
            continue  # the same value, imported already
        if have or name in info["declarations"]:
            what = describe(*have) if have else "its own declaration"
            raise Failure(
                f"{where} binds {name} to {what}, and the moved Page uses {name} as {describe(kind, exported, module)}; "
                "nothing was written",
                f"rename one of the two {name} bindings (in {where} or the Page in index.js), then run new tab again",
            )
        bound[name] = (kind, exported, module)
        new = {"kind": kind, "imported": exported if kind == "named" else None, "local": name}
        same = next(
            (
                i
                for i in info["imports"]
                if i["source"] == module
                and "\n" not in text[i["start"] : i["end"]]
                and not any(s["kind"] == "namespace" for s in i["specifiers"])
            ),
            None,
        )
        if kind == "named" and same is not None:
            joined.setdefault(id(same), (same, list(same["specifiers"])))[1].append(new)
            continue
        clause = {"named": f"{{ {spec(kind, exported, name)} }}", "default": name, "namespace": f"* as {name}"}[kind]
        lines.append(f"import {clause} from '{module}'")
    edits += [(found["start"], found["end"], statement(found, specs)) for found, specs in joined.values()]
    if lines:
        if info["imports"]:
            end = info["imports"][-1]["end"]
            at = text.find("\n", end)
            at = len(text) if at < 0 else at
            edits.append((at, at, "".join("\n" + line for line in lines)))
        else:
            first = text.find("\n") + 1 if text.startswith("//") else 0  # after the file's opening comment line
            edits.append((first, first, "".join(line + "\n" for line in lines)))
    return edit(text, edits)


def drop_unused(top: Path, text: str, names: list[str], where: str) -> str:
    """``text`` without the import of each of ``names`` that nothing outside the imports uses any more (a statement
    left with no name goes with its line)."""
    info = parse(top, text, where)
    edits = []
    for found in info["imports"]:
        kept = [s for s in found["specifiers"] if s["local"] not in names or s["local"] in info["used"]]
        if len(kept) == len(found["specifiers"]):
            continue
        end = found["end"] + (1 if text[found["end"] : found["end"] + 1] == "\n" else 0)
        edits.append((found["start"], found["end"], statement(found, kept)) if kept else (found["start"], end, ""))
    return edit(text, edits)


def move_out(plan: Plan, door: str, page_id: str, component: str) -> dict:
    """Move the Page ``component`` out of index.js into ``<page>-page.js`` (made, or appended to with the imports it
    needs), exported; index.js imports it from there and drops the imports only it used. The tab template's
    values. Every refusal comes before anything is planned."""
    top, text = plan.top, plan.read(door)
    info = parse(top, text, door, component)
    page = info["page"]
    file = f"{page_id}-page.js"
    target = f"page/pages/{page_id}/{file}"
    first = text.rfind("\n", 0, page["start"]) + 1 if page else 0
    last = (text.find("\n", page["end"]) if page else 0) % (len(text) + 1)  # its line's end (-1: the text's)
    alone = (
        page
        and not text[first : page["start"]].strip()
        and not re.sub(r"//.*|/\*.*\*/", "", text[page["end"] : last]).strip()
    )
    if not page or not page["movable"] or not alone:  # alone on its lines: nothing else moves with it
        raise Failure(
            f"{door} defines {component} in a form new cannot move (only a top-level function {component}(...) or "
            f"const {component} = ...); nothing was written",
            f"move {component} into {target} (export it, import it in index.js), then run new tab again",
        )
    used = page["uses"]
    helpers = [name for name in used if name in info["declarations"] and name != component]
    if helpers:
        raise Failure(
            f"{door} defines {component} with {', '.join(helpers)} beside it in index.js, and new moves only the "
            "function; nothing was written",
            f"move {component} and {', '.join(helpers)} into {target} (export {component}, import it in index.js), "
            "then run new tab again",
        )
    existing = plan.read(target) if plan.exists(target) else None
    dest = parse(top, existing, target) if existing is not None else {"declarations": {}, "exports": {}}
    if component in dest["declarations"]:
        raise Failure(f"{target} defines {component} already; nothing was written", f"move {component} by hand")
    needed, bound = [], []  # (kind, local, exported, module) of each import the moved Page uses from elsewhere
    for found in info["imports"]:
        for s in found["specifiers"]:
            if s["local"] not in used:
                continue
            bound.append(s["local"])  # index.js drops it once nothing else there uses it
            if found["source"] == f"./{file}":
                own_binding(s, dest, door, target, component)
            else:
                needed.append((s["kind"], s["local"], s["imported"], found["source"]))
    block = text[page["start"] : last].rstrip()  # with a comment that ends its last line
    if not page["exported"]:
        at = page["keyword"] - page["start"]
        block = block[:at] + "export " + block[at:]
    head = f"// The {page_id} page's own Page, moved here from index.js by retrodev new tab --from-page.\n"
    merged = add_imports(top, existing if existing is not None else head, needed, target)
    merged = merged.rstrip("\n") + "\n\n" + block + "\n"
    rest = re.sub(r"\n{3,}", "\n\n", text[:first] + text[last + 1 :])
    after = add_imports(top, rest, [("named", component, component, f"./{file}")], door)
    after = drop_unused(top, after, bound, door)
    if page["exported"]:  # its front door export stays: other modules may import it through #pages/<page>/index.js
        after = add_reexport(after, component, f"./{file}", door)
    if existing is None:
        plan.create(target, merged)
    else:
        plan.edit(target, lambda _text: merged)
    plan.edit(door, lambda _t: after)
    kept = f"; index.js still exports it (export {{ {component} }} from './{file}')" if page["exported"] else ""
    plan.notes.append(f"moved {component} from {door} into {target} (exported; the tab imports it from there{kept})")
    return {"Component": component, "Imported": component, "source": f"#pages/{page_id}/{file}", "moved": target}


def own_binding(s: dict, dest: dict, door: str, target: str, component: str) -> None:
    """A name the Page imports from the very file it moves into must be that file's own declaration, under the same
    name: there the moved code reads the file's local binding, never an import."""
    local = dest["exports"].get(s["imported"]) if s["kind"] == "named" else None
    if local == s["local"] and local in dest["declarations"]:
        return
    imported = describe(s["kind"], s["imported"], f"./{target.rsplit('/', 1)[1]}")
    where = (
        f"the name {local} there"
        if local
        else "no declaration of that file's own"
        if s["kind"] == "named"
        else "not a name new can follow"
    )
    fix = (
        f"import it as {{ {local} }} in {door} and use {local} in {component}"
        if local and local in dest["declarations"]
        else f"declare and export {s['local']} by that name in {target}, import it as {{ {s['local']} }} in {door}"
    )
    raise Failure(
        f"{component} uses {s['local']}, which {door} imports as {imported}, the file the Page moves into, where it is "
        f"{where}: the moved code would read another binding; nothing was written",
        fix + ", then run new tab again",
    )
