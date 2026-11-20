"""`new contribution <page> <slot> <Component>`: a page fills another page's slot (a page kind of scaffold.py,
filling a Plan; nothing is written here).

The places are docs/dev/STUDIO-PAGES.md's "A contribution to a slot": the component in the contributing page's
folder, `contributes` in its index.js, its README **Slots:** line, and the `filled` assertion of
tests/page/registry.test.mjs (written here when its shape is the usual one, so the page check passes at once: the
import there takes the alias <Component>From<Page> when the test uses the name already, e.g. Text). A slot key is
matched in any quote style. The docs and the host's side stay the author's: the next steps name them.
"""

from __future__ import annotations

import re

from .output import Failure
from .scaffold import Plan, pascal
from .scaffold_imports import statements
from .scaffold_page import REGISTRY, REGISTRY_TEST, add_to_descriptor, descriptor, known_page, unique_exports

SLOT = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-zA-Z0-9]{0,39}$")
PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]{0,39}$")
EXPECTED = re.compile(r"^(\s*const expected = \{)(.*)(\}\s*)$", re.M)
TEST_IMPORT = re.compile(r"^const \{ ([\w,: ]+) \} = await import\('\.\./\.\./(page/pages/[^']+)'\)$", re.M)
IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def key(slot: str) -> str:
    """A pattern for ``slot`` as an object key: 'x', "x", or x unquoted when it is an identifier."""
    forms = [f"'{re.escape(slot)}'", f'"{re.escape(slot)}"'] + ([re.escape(slot)] if IDENTIFIER.match(slot) else [])
    return "(?:" + "|".join(forms) + ")"


def braced(text: str, start: int) -> str:
    """The text from the '{' at ``start`` to its matching '}', strings (quoted or template) skipped."""
    depth, at, quote = 0, start, None
    while at < len(text):
        char = text[at]
        if quote:
            at += 2 if char == "\\" else 1
            quote = None if char == quote else quote
            continue
        if char in "'\"`":
            quote = char
        depth += char == "{"
        depth -= char == "}"
        at += 1
        if depth == 0:
            return text[start:at]
    return text[start:]


def declared_slots(plan: Plan) -> dict[str, str]:
    """{slot: the page that declares it} from every page and tab index.js's `slots: { ... }`."""
    found = {}
    for path in sorted(plan.top.glob("page/pages/**/index.js")):
        rel = str(path.relative_to(plan.top))
        text = plan.read(rel)
        for match in re.finditer(r"^\s*slots:\s*\{", text, re.M):
            block = braced(text, match.end() - 1)
            for name in re.findall(r"""^\s*['"]([a-z][\w-]*\.\w+)['"]\s*:""", block[1:], re.M):
                found[name] = rel.split("/")[2]
    return found


def file_of(component: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", component).lower() + ".js"


def contribution(plan: Plan, page_id: str, slot: str, component: str) -> str:
    door = known_page(plan, page_id)
    declared = declared_slots(plan)
    if not SLOT.match(slot or "") or slot not in declared:
        listed = ", ".join(sorted(declared)) or "none yet"
        raise Failure(
            f"no page declares the slot '{slot}' (a contribution fills a declared <page>.<name>); nothing was written",
            f"pick a declared one: {listed}; or declare it first: python tools/retrodev new slot <page> <name>",
        )
    if not PASCAL.match(component or ""):
        raise Failure(
            f"'{component}' is not a usable component name: it becomes a JavaScript function and its file name",
            "use a PascalCase word, e.g. InstallButton",
        )
    rel = f"page/pages/{page_id}/{file_of(component)}"
    if plan.exists(rel) or re.search(rf"\b{component}\b", plan.read(door)):
        raise Failure(f"{rel} exists or {door} names {component} already; nothing was written", "pick another name")
    unique_exports(plan, [component])
    host = declared[slot]
    values = {"Component": component, "slot": slot, "host": host, "page": page_id}
    plan.create(rel, STUB.format(**values))
    statements(plan.read(door), door)  # an import it cannot read whole is refused before anything is written
    plan.edit(door, lambda text: wired(text, door, slot, component, file_of(component)))
    readme(plan, page_id, f"Contributes `{component}` to `{slot}`")
    expected = registry_expected(plan, slot, component, rel)
    plan.regenerate = True
    if not expected:
        plan.skip_checks.append("page")
        plan.notes.append(
            f"the page check is skipped now: the `filled` assertion of {REGISTRY_TEST} lists every contribution, and "
            "new could not add this one there (its shape is not the usual one); add it, then python tools/retrodev check"
        )
    plan.next_steps += [
        f"write {component} in {rel}: it gets {slot}'s props (the slot's doc in page/pages/{host}/index.js) and "
        "returns what the slot shows (null shows nothing)",
        f"docs/dev/STUDIO-PAGES.md 'Events and slots today': name {component} ({page_id}) under `{slot}`",
        f"page/pages/{host}/README.md **Slots:** line: say {page_id} fills `{slot}` with {component}",
        (
            f"{REGISTRY_TEST}: new added {component} to the `filled` assertion's `expected` (and its import)"
            + (f", as {expected}: the test names {component} already" if expected != component else "")
            if expected
            else f"{REGISTRY_TEST}: add {component} under '{slot}' to the `filled` assertion's `expected`, in PAGES "
            f"order ({REGISTRY}), imported from {rel}"
        ),
        f"tests/page/slots.test.mjs HOSTS: the recipe that renders `{slot}`'s host"
        + (
            " is there"
            if re.search(key(slot), read(plan, "tests/page/slots.test.mjs"))
            else " (add one once the host renders it)"
        ),
    ]
    return f"contribution {page_id} -> {slot}"


STUB = """// {Component}: what the {page} page puts into the {slot} slot of the {host} page (contributes in index.js). It
// gets the slot's props, as the slot's doc in page/pages/{host}/index.js names them.

/** What {slot} shows from this page for these props (null shows nothing). */
export function {Component}(props) {{
  return null
}}
"""


def read(plan: Plan, rel: str) -> str:
    return plan.read(rel) if plan.exists(rel) else ""


def wired(text: str, door: str, slot: str, component: str, file: str) -> str:
    """index.js importing the component and listing it in `contributes` (after a list the slot has already)."""
    line = f"import {{ {component} }} from './{file}'"
    found = statements(text, door)
    if found:  # after the last whole import statement
        at = text.find("\n", found[-1].end())
        text = text + "\n" + line if at < 0 else text[: at + 1] + line + "\n" + text[at + 1 :]
    else:
        text = line + "\n" + text
    _name, first, end = descriptor(text)
    lines = text.split("\n")
    listed = re.compile(rf"^(\s*{key(slot)}\s*:\s*\[)([^\]\n]*)(\].*)$")
    for index in range(first, end):
        hit = listed.match(lines[index])
        if hit:
            inner = hit.group(2).strip()
            lines[index] = hit.group(1) + (f"{inner}, {component}" if inner else component) + hit.group(3)
            return "\n".join(lines)
    body = "\n".join(lines[first:end])
    at = re.search(r"^\s*contributes:\s*\{", body, re.M)
    if at and re.search(rf"(?:^|[{{,])\s*{key(slot)}\s*:", braced(body, at.end() - 1)[1:], re.M):
        raise Failure(
            f"{door} lists '{slot}' in contributes in a shape new cannot extend (it appends only to a one-line "
            "array); nothing was written",
            f"add {component} to that list by hand",
        )
    return add_to_descriptor(text, "contributes", "{", "}", f"'{slot}': [{component}]")


def readme(plan: Plan, page_id: str, said: str) -> None:
    rel = f"page/pages/{page_id}/README.md"
    text = read(plan, rel)
    found = re.search(r"\*\*Slots:\*\*.*?(?=\n\n|\Z)", text, re.S)
    if not found:
        plan.notes.append(f"say '{said}' on the **Slots:** line of {rel}")
        return
    block = found.group(0)
    if re.search(r"\bcontributes none\b", block, re.I):
        changed = re.sub(r"\b([cC])ontributes none\b", lambda m: f"{m.group(1)}{said[1:]}", block, count=1)
    else:
        changed = block.rstrip() + f" {said}."
    plan.edit(rel, lambda current: current.replace(block, changed, 1))


def registry_expected(plan: Plan, slot: str, component: str, rel: str) -> str:
    """Add the contribution to the registry test's `filled` assertion (and import it there); False when its
    `expected` line or the order of the slot's contributions is not one new can write (else its name there). The import takes the alias
    <Component>From<Page> when the test names the component already (a binding of its own, e.g. Text or JSDOM, or
    any other use: a second top-level binding would not parse); refused when the alias is taken too."""
    text = read(plan, REGISTRY_TEST)
    found = EXPECTED.search(text)
    imports = list(TEST_IMPORT.finditer(text))
    if not found or not imports:
        return ""
    page_id = rel.split("/")[2]
    local = local_name(text, component, page_id)
    body = found.group(2)
    current = re.search(rf"{key(slot)}\s*:\s*\[([^\]]*)\]", body)
    if current:
        have = [name.strip() for name in current.group(1).split(",") if name.strip()]
        bound = test_imports(text)
        ordered = [
            local if (name, page) == (component, page_id) else bound.get((page, name), name)
            for name, page in contributors(plan, slot)
        ]
        if [name for name in ordered if name != local] != have:
            return ""  # a name the test imports differently, or a tab's: left to the author
        body = body[: current.start(1)] + ", ".join(ordered) + body[current.end(1) :]
    else:
        inner = body.strip()
        body = f" {inner + ', ' if inner else ''}'{slot}': [{local}] "
    names = component if local == component else f"{component}: {local}"
    line = f"const {{ {names} }} = await import('../../{rel}')"
    text = text[: found.start(2)] + body + text[found.end(2) :]
    last = list(TEST_IMPORT.finditer(text))[-1]
    plan.edit(REGISTRY_TEST, lambda _old: text[: last.end()] + "\n" + line + text[last.end() :])
    return local


def local_name(text: str, component: str, page_id: str) -> str:
    """The registry test's name for the component: itself when the test never names it, else <Component>From<Page>
    (a word the test never names either); refused before anything is written when both are taken."""
    words = set(re.findall(r"[A-Za-z_$][\w$]*", text))
    if component not in words:
        return component
    alias = f"{component}From{pascal(page_id)}"
    if alias in words:
        raise Failure(
            f"{REGISTRY_TEST} names {component} and {alias} already, and new imports the contribution there under "
            "one of them; nothing was written",
            "pick another component name",
        )
    return alias


def test_imports(text: str) -> dict[tuple[str, str], str]:
    """{(page id, exported name): the registry test's local name} for each one-line import of a page's file."""
    found = {}
    for match in TEST_IMPORT.finditer(text):
        page_id = match.group(2).split("/")[2]
        for part in match.group(1).split(","):
            exported, _, local = part.partition(":")
            if exported.strip():
                found[(page_id, exported.strip())] = (local or exported).strip()
    return found


def contributors(plan: Plan, slot: str) -> list[tuple[str, str]]:
    """(component, page id) each page's index.js contributes to ``slot`` (one-line lists, any key quotes), in PAGES
    order."""
    registry = plan.read(REGISTRY)
    order = re.search(r"^export const PAGES = \[([^\]]*)\]$", registry, re.M)
    names = [name.strip() for name in order.group(1).split(",")] if order else []
    folders = dict(re.findall(r"""^import \{ (\w+_PAGE) \} from ['"]\./([\w-]+)/index\.js['"]$""", registry, re.M))
    found = []
    for name in names:
        door = f"page/pages/{folders.get(name, '')}/index.js"
        listed = re.search(rf"{key(slot)}\s*:\s*\[([^\]\n]*)\]", read(plan, door)) if name in folders else None
        parts = [part.strip() for part in listed.group(1).split(",") if part.strip()] if listed else []
        found += [(part, folders[name]) for part in parts]
    return found
