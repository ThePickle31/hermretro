"""The import statements of a page's index.js as `new tab` reads them (`new tab --from-page` moving a Page that
index.js defines itself is scaffold_move.py, from a real JavaScript parse). Nothing is written here.
"""

from __future__ import annotations

import re

from .output import Failure

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
