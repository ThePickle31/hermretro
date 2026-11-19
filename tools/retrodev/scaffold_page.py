"""`new page|tab|slot`: the page kinds of scaffold.py, each filling a Plan (nothing is written here).

The steps are docs/dev/STUDIO-PAGES.md's "Adding to the page": a folder plus at most one registry line. The page
registry test (tests/page/registry.test.mjs) pins the pages in nav order and the declared slots, so those
lists gain the new name too.
"""

from __future__ import annotations

import re

from .output import Failure
from .scaffold import (
    CAMEL,
    KEBAB,
    Plan,
    check_name,
    const,
    insert_after,
    js_label,
    label,
    pascal,
    readme_item,
    render,
)
from .scaffold import camel as to_camel

REGISTRY = "page/pages/index.js"
REGISTRY_TEST = "tests/page/registry.test.mjs"
PAGES_LIST = re.compile(r"(assert\.deepEqual\(PAGES\.map\(page => page\.id\), \[)([^\]]*)(\]\))")
SLOTS_LIST = re.compile(
    r"(assert\.deepEqual\(\[\.\.\.PAGE_SLOTS\.declared\(\)\.keys\(\)\]\.sort\(\), \[)([^\]]*)(\]\))"
)


def page(plan: Plan, page_id: str, page_label: str | None) -> str:
    check_name(page_id, KEBAB, "page", "games")
    page_label = js_label(page_label, label(page_id))
    folder = f"page/pages/{page_id}"
    if plan.exists(folder) or f"'./{page_id}/index.js'" in plan.read(REGISTRY):
        raise Failure(f"{folder} exists or the registry lists it", "pick another page id")
    values = {"id": page_id, "Label": page_label, "Component": pascal(page_id) + "Page", "CONST": const(page_id)}
    unique_exports(plan, [values["Component"], f"{const(page_id)}_PAGE"])
    plan.create(f"{folder}/index.js", render("page", "index.js.tmpl", **values))
    plan.create(f"{folder}/{page_id}-page.js", render("page", "page.js.tmpl", **values))
    plan.create(f"{folder}/README.md", render("page", "README.md.tmpl", **values))
    name = f"{const(page_id)}_PAGE"

    def register(text: str) -> str:
        line = f"import {{ {name} }} from './{page_id}/index.js'"
        text = insert_after(text, re.compile(r"^import \{ \w+_PAGE \} from '\./[\w-]+/index\.js'$"), line, REGISTRY)
        found = re.search(r"^export const PAGES = \[([^\]]*)\]$", text, re.M)
        if not found:
            raise Failure(f"{REGISTRY}: no one-line 'export const PAGES = [...]'", f"add {name} to PAGES by hand")
        listed = found.group(1).strip()
        return text[: found.start(1)] + (f"{listed}, {name}" if listed else name) + text[found.end(1) :]

    plan.edit(REGISTRY, register)
    plan.edit(REGISTRY_TEST, lambda text: _append_to(text, PAGES_LIST, page_id, "the pages in nav order"))
    plan.regenerate = True
    plan.next_steps += [
        f"build the page in {folder}/{page_id}-page.js (Page gets {{ shell }}: app/studio-page.js) and say what "
        f"it shows in {folder}/README.md",
        f"it is last in the nav: move it in PAGES ({REGISTRY}) and in {REGISTRY_TEST} together",
        f"python tools/retrodev new tab {page_id} <tab> | new slot {page_id} <name>",
    ]
    return f"page {page_id}"


def _append_to(text: str, pattern: re.Pattern, item: str, what: str, sort: bool = False) -> str:
    found = pattern.search(text)
    if not found:
        raise Failure(f"{REGISTRY_TEST}: the list of {what} is not where it was", f"add '{item}' to it by hand")
    items = re.findall(r"'([^']*)'", found.group(2)) + [item]
    items = sorted(items) if sort else items
    return text[: found.start(2)] + ", ".join(f"'{entry}'" for entry in items) + text[found.end(2) :]


def unique_exports(plan: Plan, names: list[str]) -> None:
    """The page is one bundle, which refuses two modules exporting the same name: refuse such a name first."""
    exported = re.compile(r"^export\s+(?:const|function|class|let)\s+(\w+)", re.M)
    for path in sorted(plan.top.glob("page/**/*.js")):
        taken = set(exported.findall(plan.read(str(path.relative_to(plan.top)))))
        for name in names:
            if name in taken:
                raise Failure(
                    f"{path.relative_to(plan.top)} exports {name} already, and the page bundle needs unique names",
                    "pick another id",
                )


def descriptor(text: str, suffix: str = "_PAGE") -> tuple[str, int, int]:
    """(constant, first line index, closing line index) of the page's ``export const X_PAGE = {`` block."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        found = re.match(rf"^export const (\w+{suffix}) = \{{$", line)
        if found:
            end = next((i for i in range(index + 1, len(lines)) if lines[i] == "}"), None)
            if end is not None:
                return found.group(1), index, end
    raise Failure(
        f"no 'export const <PAGE>{suffix} = {{' descriptor ending in a '}}' line", "edit the descriptor by hand"
    )


def add_to_descriptor(text: str, field_name: str, opening: str, closing: str, entry: str) -> str:
    """Add ``entry`` to the descriptor's ``field_name`` (an array or object), making the field when it is missing."""
    _name, first, end = descriptor(text)
    lines = text.split("\n")
    body = lines[first + 1 : end]
    start = next((i for i, line in enumerate(body) if line.startswith(f"  {field_name}: {opening}")), None)
    if start is None:
        if body and not body[-1].rstrip().endswith((",", "{")):
            body[-1] += ","
        body += [f"  {field_name}: {opening}", f"    {entry}", f"  {closing}"]
    else:
        line = body[start]
        if line.rstrip().endswith(closing) and line.strip() != f"{field_name}: {opening}":  # all on one line
            inner = line[line.index(opening) + 1 : line.rindex(closing)].strip()
            tail = line[line.rindex(closing) :]
            body[start] = f"  {field_name}: {opening}{inner + ', ' if inner else ''}{entry}{tail}"
        else:
            stop = next((i for i in range(start + 1, len(body)) if body[i].startswith(f"  {closing}")), None)
            if stop is None:
                raise Failure(f"the descriptor's {field_name} does not end in a '  {closing}' line", "add it by hand")
            if not body[stop - 1].rstrip().endswith((",", opening)):
                body[stop - 1] += ","
            body.insert(stop, f"    {entry}")
    return "\n".join(lines[: first + 1] + body + lines[end:])


def known_page(plan: Plan, page_id: str) -> str:
    check_name(page_id, KEBAB, "page", "games")
    if not plan.exists(f"page/pages/{page_id}/index.js"):
        raise Failure(
            f"page/pages/{page_id}/index.js does not exist", f"python tools/retrodev new page {page_id} first"
        )
    return f"page/pages/{page_id}/index.js"


def tab(plan: Plan, page_id: str, tab_id: str, tab_label: str | None, from_page: bool = False) -> str:
    door = known_page(plan, page_id)
    check_name(tab_id, KEBAB, "tab", "history")
    tab_label = js_label(tab_label, label(tab_id))
    name = f"{const(page_id)}_{const(tab_id)}_TAB"  # one bundle: every exported name is unique across pages
    if plan.exists(f"page/pages/{page_id}/{tab_id}"):
        raise Failure(f"page/pages/{page_id}/{tab_id} exists", "pick another tab id")
    unique_exports(plan, [name])
    values = {"page": page_id, "tab": tab_id, "Label": tab_label, "Component": pascal(tab_id) + "Tab"}
    values["CONST"] = f"{const(page_id)}_{const(tab_id)}"
    tabless, component = own_page(plan.read(door))
    if from_page:
        values |= moved_page(plan, door, page_id, tabless, component)
    template = "from_page.js.tmpl" if from_page else "index.js.tmpl"
    plan.create(f"page/pages/{page_id}/{tab_id}/index.js", render("tab", template, **values))

    def wire(text: str) -> str:
        if from_page:
            text = drop_page(text, component)
        line = f"import {{ {name} }} from './{tab_id}/index.js'"
        text = (
            insert_after(text, re.compile(r"^import "), line, door)
            if re.search(r"^import ", text, re.M)
            else (line + "\n" + text)
        )
        return add_to_descriptor(text, "tabs", "[", "]", name)

    plan.edit(door, wire)
    _readme(plan, page_id, "Tabs:", f"`{tab_id}` (`{tab_id}/index.js`)", append=True)
    plan.regenerate = True
    if from_page:
        plan.skip_checks.append("page")
        plan.notes.append(
            f"the page check is skipped now: tests/page/registry.test.mjs still expects every page to have a Page "
            f"(app/registry.js takes tabs instead), and {page_id} has none now; make that test accept a page with tabs"
        )
        plan.next_steps += [
            f"the page's own Page ({values['source']}) is now the {tab_id} tab, and the descriptor has no Page: "
            f"add the second tab (python tools/retrodev new tab {page_id} <tab>); a single tab still shows a tab bar",
        ]
        return f"tab {page_id}/{tab_id} (from the page's Page)"
    if tabless and component:
        plan.skip_checks.append("page")
        plan.notes.append(
            f"the page check is skipped now: {page_id} gets its first tab and keeps its own Page ({component}), which "
            "still renders above the tab bar and the tab, so its page tests may no longer hold; turn the Page into "
            f"this tab instead with --from-page, or run python tools/retrodev check once the page is as it should be"
        )
    plan.next_steps += [
        f"build the tab in page/pages/{page_id}/{tab_id}/index.js (Page gets the page's {{ shell }})",
        f"with tabs, the page's own Page component ({page_file(plan, door)}) still renders, between the tab bar and "
        "the chosen tab, with a { tab } prop (app/page-view.js): keep only what every tab shares there, or drop "
        f"Page from the descriptor (new tab {page_id} <id> --from-page makes a tabless page's Page its first tab)",
        "a single tab still shows a tab bar (one button): add a second tab, or keep a page without tabs",
    ]
    return f"tab {page_id}/{tab_id}"


PAGE_FIELD = re.compile(r"^  Page: (\w+),?$")


def own_page(text: str) -> tuple[bool, str | None]:
    """(the descriptor has no tabs yet, the name of its own Page component or None)."""
    _name, first, end = descriptor(text)
    body = text.split("\n")[first + 1 : end]
    found = next((m.group(1) for line in body if (m := PAGE_FIELD.match(line))), None)
    return not any(line.startswith("  tabs:") for line in body), found


def moved_page(plan: Plan, door: str, page_id: str, tabless: bool, component: str | None) -> dict:
    """--from-page: the tab template's values (the Page's file as #pages/<page>/<file>.js), once it may move."""
    if not tabless or not component:
        raise Failure(
            f"--from-page turns the page's own Page into its first tab, and {door} "
            + ("has tabs already" if not tabless else "has no Page field")
            + "; nothing was written",
            f"leave out --from-page: python tools/retrodev new tab {page_id} <id>",
        )
    source = page_file(plan, door)
    if source == door:
        raise Failure(
            f"{door} defines {component} itself, and a tab may import it only from its own file (importing the page's "
            "index.js from its tab would be a cycle); nothing was written",
            f"move {component} into page/pages/{page_id}/{page_id}-page.js (export it, import it in index.js), "
            "then run new tab again",
        )
    return {"Component": component, "source": "#pages/" + source.removeprefix("page/pages/")}


def drop_page(text: str, component: str) -> str:
    """The descriptor without its Page field, and without the component's import once nothing else uses it."""
    lines = [line for line in text.split("\n") if not PAGE_FIELD.match(line)]
    _name, first, end = descriptor("\n".join(lines))
    body = lines[first + 1 : end]
    if body and body[-1].endswith(","):
        lines[end - 1] = body[-1][:-1]
    text = "\n".join(lines)
    uses = re.compile(rf"\b{re.escape(component)}\b")
    rest = [line for line in text.split("\n") if uses.search(line) and not line.startswith("import ")]
    if rest:
        return text
    for match in re.finditer(r"^import \{([^}]*)\} from '[^']*'\n", text, re.M):
        names = [part.strip() for part in match.group(1).split(",") if part.strip()]
        if component in names:
            kept = [part for part in names if part != component]
            line = match.group(0).replace(match.group(1), " " + ", ".join(kept) + " ") if kept else ""
            return text[: match.start()] + line + text[match.end() :]
    return text


def page_file(plan: Plan, door: str) -> str:
    """The file that defines the descriptor's Page component: the module its import names, else the descriptor
    itself (a page may define Page in its index.js)."""
    text = plan.read(door)
    found = re.search(r"^\s*Page:\s*(\w+)", text, re.M)
    if not found:
        return door
    source = re.search(rf"^import \{{[^}}]*\b{found.group(1)}\b[^}}]*\}} from '\./([\w./-]+)'", text, re.M)
    return f"{door.rsplit('/', 1)[0]}/{source.group(1)}" if source else door


def slot(plan: Plan, page_id: str, name: str, doc: str | None) -> str:
    door = known_page(plan, page_id)
    name = name if CAMEL.match(name) else to_camel(name)
    check_name(name, CAMEL, "slot", "cardMenu")
    full = f"{page_id}.{name}"
    doc = js_label(doc, "Where it is on the page. Props: { ... }", "doc")
    for index in plan.top.glob("page/pages/**/index.js"):
        if f"'{full}'" in plan.read(str(index.relative_to(plan.top))):
            raise Failure(f"the slot {full} is declared already ({index.relative_to(plan.top)})", "pick another name")
    plan.edit(door, lambda text: add_to_descriptor(text, "slots", "{", "}", f"'{full}': '{doc}'"))
    plan.edit(REGISTRY_TEST, lambda text: _append_to(text, SLOTS_LIST, full, "declared slots", sort=True))
    _readme(plan, page_id, "Slots:", f"declares `{full}` ({doc.rstrip('.')})", "declares none")
    plan.regenerate = True
    plan.next_steps += [
        f"render it where the contributions go: import {{ Slot }} from '#app/slots.js'; "
        f"jsx(Slot, {{ name: '{full}', props: {{ ... }} }})",
        f"another page fills it from its index.js: contributes: {{ '{full}': [Component] }}",
    ]
    return f"slot {full}"


def _readme(plan: Plan, page_id: str, what: str, item: str, replaces: str = "none", append: bool = False) -> None:
    rel = f"page/pages/{page_id}/README.md"
    if not plan.exists(rel):
        plan.notes.append(f"{rel} is missing: every page has one (python tools/retrodev new page makes it)")
        return
    before = plan.read(rel)
    if replaces == "none":
        plan.edit(rel, lambda text: readme_item(text, what, item, only_none=not append))
    else:
        plan.edit(rel, lambda text: text.replace(f"**{what}** {replaces}", f"**{what}** {item}", 1))
    if plan.read(rel) == before:
        plan.notes.append(f"mention {item} under **{what}** in {rel}")
