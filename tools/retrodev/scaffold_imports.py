"""The import statements of a page's index.js as `new tab` reads them, and `new tab --from-page` moving a Page that
index.js defines itself into the page's own `<page>-page.js` (a tab may import only from the page's files: its
index.js would be a cycle). Nothing is written here: it fills scaffold.py's Plan.
"""

from __future__ import annotations

import re

from .output import Failure
from .scaffold import Plan

IMPORT_START = re.compile(r"^import(?=[\s{*'\"])", re.M)  # not import(...) or import.meta
STATEMENT = re.compile(
    r"""import\s*(?:(?P<clause>[\w$*\s{},]+?)\s*from\s*)?(?P<q>['"])(?P<module>[^'"\n]*)(?P=q)[ \t]*;?"""
)
COMMENTS = re.compile(r"/\*.*?\*/|^[ \t]*//[^\n]*", re.S | re.M)
REEXPORT = re.compile(r"""^export\s*(?:\{[^}]*\}|\*(?:\s+as\s+[\w$]+)?)\s*from\s*['"][^'"\n]*['"][ \t]*;?""", re.M)
STRINGS = re.compile(r"'(?:[^'\\\n]|\\.)*'" + "|" + r'"(?:[^"\\\n]|\\.)*"')  # a name in a label is no use of it


def statements(text: str, where: str = "the page's index.js") -> list[re.Match]:
    """Every whole import statement at the start of a line, one or many lines long (``import {`` ... ``} from
    './x.js'``), in order; one that does not parse is refused (a tab must never be wired into the middle of one)."""
    found = []
    for start in IMPORT_START.finditer(text):
        whole = STATEMENT.match(text, start.start())
        clause = (whole.group("clause") or "") if whole else ""
        if not whole or clause.count("{") != clause.count("}") or clause.count("{") > 1:
            line = text[start.start() :].split("\n", 1)[0]
            raise Failure(
                f"{where}: cannot read the import statement starting '{line}' (new reads only plain static imports, "
                "on one or more lines); nothing was written",
                "write it as import { Name } from './file.js' (one or more lines), then run new again",
            )
        found.append(whole)
    return found


def bindings(found: re.Match) -> list[tuple[str, str, str | None]]:
    """(kind, local name, exported name) for each name one import statement binds: kind is "named", "default" or
    "namespace"."""
    clause = found.group("clause") or ""
    braces = re.search(r"\{([^}]*)\}", clause)
    named = []
    for part in braces.group(1).split(",") if braces else []:
        exported, _, alias = " ".join(part.split()).partition(" as ")
        if exported:
            named.append(("named", alias.strip() or exported, exported))
    rest = clause[: braces.start()] + clause[braces.end() :] if braces else clause
    for part in (part.strip() for part in rest.split(",")):
        star = re.fullmatch(r"\*\s+as\s+([\w$]+)", part)
        if star:
            named.append(("namespace", star.group(1), None))
        elif part:
            named.append(("default", part, None))
    return named


def binding(text: str, local: str) -> tuple[str | None, str | None, str | None]:
    """(kind, exported name, module) of the import that binds ``local``: kind is "named" (exported name its own, as
    in ``{ SetupPage as SetupPanel }``), "default" or "namespace"; (None, None, None) when no import binds it."""
    for found in statements(text):
        for kind, name, exported in bindings(found):
            if name == local:
                return kind, exported, found.group("module")
    return None, None, None


def outside_imports(text: str) -> str:
    """The code without its import statements, comments and string contents: where a name is used."""
    kept, at = [], 0
    for match in statements(text):
        kept.append(text[at : match.start()])
        at = match.end()
    code = REEXPORT.sub("", "".join(kept) + text[at:])  # export { X } from './x.js' uses no local binding
    return STRINGS.sub("''", COMMENTS.sub("", code))


def drop_import(text: str, local: str) -> str:
    """``text`` without the import of ``local`` once nothing outside the imports uses it (a statement left with no
    name goes with its line)."""
    if re.search(rf"(?<![\w$]){re.escape(local)}(?![\w$])", outside_imports(text)):
        return text
    for match in statements(text):
        names = bindings(match)
        if local not in [name for _kind, name, _exported in names]:
            continue
        kept = [(kind, name, exported) for kind, name, exported in names if name != local]
        quote, end = match.group("q"), match.end()
        semi = ";" if match.group(0).rstrip().endswith(";") else ""
        parts = [name if kind == "default" else f"* as {name}" for kind, name, _e in kept if kind != "named"]
        named = [exported if name == exported else f"{exported} as {name}" for kind, name, exported in kept if exported]
        parts += [f"{{ {', '.join(named)} }}"] if named else []
        line = f"import {', '.join(parts)} from {quote}{match.group('module')}{quote}{semi}" if parts else ""
        if not parts and text[end : end + 1] == "\n":
            end += 1  # the whole statement goes, with its line
        return text[: match.start()] + line + text[end:]
    return text


PAGE_FIELD = re.compile(r"^  Page: (\w+),?$")


def drop_page(text: str, component: str, descriptor) -> str:
    """The descriptor without its Page field, and without the component's import once nothing else uses it."""
    lines = [line for line in text.split("\n") if not PAGE_FIELD.match(line)]
    _name, first, end = descriptor("\n".join(lines))
    body = lines[first + 1 : end]
    if body and body[-1].endswith(","):
        lines[end - 1] = body[-1][:-1]
    return drop_import("\n".join(lines), component)


def definition(text: str, component: str) -> tuple[int, int] | None:
    """(first, last) line index of ``function <component>(`` ... ``}`` in index.js, its comment lines above it
    included; None when it is defined otherwise (an arrow function, a class) or not at all."""
    lines = text.split("\n")
    start = next(
        (i for i, line in enumerate(lines) if re.match(rf"^(?:export\s+)?function\s+{component}\s*\(", line)), None
    )
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i] == "}"), None)
    if end is None:
        return None
    while start > 0 and re.match(r"^\s*(/\*\*|\*|//)", lines[start - 1]):
        start -= 1
    return start, end


def move_out(plan: Plan, door: str, page_id: str, component: str) -> dict:
    """Move ``function <component>`` out of index.js into ``<page>-page.js`` (made, or appended to with the imports
    it needs), exported; index.js imports it from there and drops the imports only it used. The tab template's
    values."""
    text = plan.read(door)
    found = definition(text, component)
    if found is None:
        raise Failure(
            f"{door} defines {component} in a form new cannot move (only a top-level function {component}(...) "
            "ending in a '}' line); nothing was written",
            f"move {component} into page/pages/{page_id}/{page_id}-page.js (export it, import it in index.js), "
            "then run new tab again",
        )
    lines = text.split("\n")
    public = any(re.match(rf"^export\s+function\s+{component}\b", line) for line in lines[found[0] : found[1] + 1])
    block = "\n".join(lines[found[0] : found[1] + 1])
    block = re.sub(rf"^(?:export\s+)?function\s+{component}\b", f"export function {component}", block, flags=re.M)
    rest = "\n".join(lines[: found[0]] + lines[found[1] + 1 :])
    rest = re.sub(r"\n{3,}", "\n\n", rest)
    body = COMMENTS.sub("", block)
    used = sorted({word for word in re.findall(r"[A-Za-z_$][\w$]*", body)})
    file = f"{page_id}-page.js"
    target = f"page/pages/{page_id}/{file}"
    local = [m.group(1) for m in re.finditer(r"^(?:export\s+)?(?:const|let|var|function|class)\s+([\w$]+)", rest, re.M)]
    helpers = [name for name in local if name in used and name != component]
    if helpers:
        raise Failure(
            f"{door} defines {component} with {', '.join(helpers)} beside it in index.js, and new moves only the "
            "function; nothing was written",
            f"move {component} and {', '.join(helpers)} into {target} (export {component}, import it in index.js), "
            "then run new tab again",
        )
    needed, bound = [], []  # (kind, local, exported, module) of each import the moved function uses from elsewhere
    for statement in statements(text, door):
        for kind, name, exported in bindings(statement):
            if name in used:
                bound.append(name)  # index.js drops it once nothing else there uses it
                if statement.group("module") != f"./{file}":
                    needed.append((kind, name, exported, statement.group("module")))
    existing = plan.read(target) if plan.exists(target) else None
    if existing is not None and re.search(
        rf"^(?:export\s+)?(?:const|let|var|function|class)\s+{component}\b", existing, re.M
    ):
        raise Failure(f"{target} defines {component} already; nothing was written", f"move {component} by hand")
    head = f"// The {page_id} page's own Page, moved here from index.js by retrodev new tab --from-page.\n"
    merged = add_imports(existing if existing is not None else head, needed, target)
    merged = merged.rstrip("\n") + "\n\n" + block + "\n"
    if existing is None:
        plan.create(target, merged)
    else:
        plan.edit(target, lambda _text: merged)
    after = add_imports(rest, [("named", component, component, f"./{file}")], door)
    for name in bound:
        after = drop_import(after, name)
    if public:  # its front door export stays: other modules may import it through #pages/<page>/index.js
        after = add_reexport(after, component, f"./{file}", door)
    plan.edit(door, lambda _t: after)
    kept = f"; index.js still exports it (export {{ {component} }} from './{file}')" if public else ""
    plan.notes.append(f"moved {component} from {door} into {target} (exported; the tab imports it from there{kept})")
    return {"Component": component, "Imported": component, "source": f"#pages/{page_id}/{file}", "moved": target}


def add_imports(text: str, needed: list[tuple[str, str, str | None, str]], where: str) -> str:
    """``text`` with an import for each (kind, local, exported, module) it does not bind yet: a named one joins a
    one-line ``import { ... }`` of the same module, the rest go after the last import statement."""
    for kind, name, exported, module in needed:
        found = statements(text, where)
        have = [(k, e, s.group("module")) for s in found for k, bound, e in bindings(s) if bound == name]
        if have and have[0] == (kind, exported, module):
            continue  # the same value, imported already
        declared = re.search(
            rf"^(?:export\s+)?(?:async\s+)?(?:const|let|var|function\*?|class)\s+{re.escape(name)}\b", text, re.M
        )
        if have or declared:
            what = f"{describe(*have[0])}" if have else "its own declaration"
            raise Failure(
                f"{where} binds {name} to {what}, and the moved Page uses {name} as {describe(kind, exported, module)}; "
                "nothing was written",
                f"rename one of the two {name} bindings (in {where} or the Page in index.js), then run new tab again",
            )
        spec = exported if exported == name else f"{exported} as {name}"
        same = next((s for s in found if s.group("module") == module and "\n" not in s.group(0)), None)
        braces = re.search(r"\{([^}]*)\}", same.group("clause") or "") if same and kind == "named" else None
        if same is not None and braces:
            start = same.start("clause") + braces.start(1)
            inner = braces.group(1).strip()
            text = text[:start] + f" {inner}, {spec} " + text[same.start("clause") + braces.end(1) :]
            continue
        clause = {"named": f"{{ {spec} }}", "default": name, "namespace": f"* as {name}"}[kind]
        line = f"import {clause} from '{module}'"
        at = text.find("\n", found[-1].end()) if found else -1
        if not found:
            first = text.find("\n") + 1 if text.startswith("//") else 0  # after the file's opening comment line
            text = text[:first] + line + "\n" + text[first:]
        else:
            text = text + "\n" + line if at < 0 else text[: at + 1] + line + "\n" + text[at + 1 :]
    return text


def describe(kind: str, exported: str | None, module: str) -> str:
    """One import binding as words: "{ Small } from '#shared/ui/text.js'"."""
    return {"named": f"{{ {exported} }}", "default": "the default export", "namespace": "the namespace"}[kind] + (
        f" from '{module}'"
    )


def add_reexport(text: str, name: str, module: str, where: str) -> str:
    """``text`` with ``export { name } from 'module'`` after its import statements (beside the re-exports that
    follow them, when there are any)."""
    line = f"export {{ {name} }} from '{module}'"
    found = statements(text, where)
    rows = text.split("\n")
    at = text[: found[-1].end()].count("\n") + 1 if found else 0
    blank = at < len(rows) and rows[at] == ""
    probe = at + 1 if blank else at
    if probe < len(rows) and REEXPORT.match(rows[probe]):
        while probe < len(rows) and REEXPORT.match(rows[probe]):
            probe += 1
        rows.insert(probe, line)
    else:
        rows[at:at] = ["", line] if found else [line, ""]
    return "\n".join(rows)
