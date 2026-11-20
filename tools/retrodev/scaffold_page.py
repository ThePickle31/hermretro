"""`new page|tab|slot`: the page kinds of scaffold.py, each filling a Plan (nothing is written here).

The steps are docs/dev/STUDIO-PAGES.md's "Adding to the page": a folder plus at most one registry line. The page
registry test (tests/page/registry.test.mjs) pins the pages in nav order and the declared slots, so those
lists gain the new name too.
"""

from __future__ import annotations

import re

from .output import Failure, cmd
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
from .scaffold_imports import PAGE_FIELD, binding, drop_page, statements
from .scaffold_move import move_out

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
    if plan.exists(folder) or re.search(rf"""['"]\./{re.escape(page_id)}/index\.js['"]""", plan.read(REGISTRY)):
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
        f"name {page_label} wherever the pages are listed or counted: README.md 'What works today' (the page list), "
        "docs/dev/CONTRACT.md 'Studio pages (desktop) and their RPCs' (its first sentence) and the Pages table of docs/dev/STUDIO-PAGES.md",
    ]
    return f"page {page_id}"


def _append_to(text: str, pattern: re.Pattern, item: str, what: str, sort: bool = False) -> str:
    found = pattern.search(text)
    if not found:
        raise Failure(f"{REGISTRY_TEST}: the list of {what} is not where it was", f"add '{item}' to it by hand")
    items = [entry for _quote, entry in re.findall(r"""(['"])(.*?)\1""", found.group(2))] + [item]  # either quote
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
    named = re.compile(rf"""^  (?:{field_name}|'{field_name}'|"{field_name}")\s*:""")
    if start is None and any(named.match(line) for line in body):  # quoted, or not a literal: a second would win
        raise Failure(
            f"the descriptor has {field_name} in a shape new cannot extend (it extends only '  {field_name}: "
            f"{opening}...'); nothing was written",
            f"add {entry} to its {field_name} by hand",
        )
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


def folder_is(plan: Plan, folder: str) -> str:
    """What an existing folder is: the first line of its index.js's opening comment, else 'an existing folder'."""
    door = f"{folder}/index.js"
    first = plan.read(door).lstrip().split("\n", 1)[0] if plan.exists(door) else ""
    said = re.sub(r"^(//+|/\*+)\s*|\s*\*/$", "", first).strip() if first.startswith(("//", "/*")) else ""
    return said or "an existing folder"


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
        other = f"{tab_id}-tab" if not plan.exists(f"page/pages/{page_id}/{tab_id}-tab") else f"{tab_id}-view"
        raise Failure(
            f"page/pages/{page_id}/{tab_id} exists: {folder_is(plan, f'page/pages/{page_id}/{tab_id}')}; a tab needs a "
            "folder of its own, and its id names that folder (the label is what the tab bar shows)",
            f"pick another id and keep the label: python tools/retrodev new tab {page_id} {other} --label "
            + cmd(tab_label),
        )
    unique_exports(plan, [name])
    values = {"page": page_id, "tab": tab_id, "Label": tab_label, "Component": pascal(tab_id) + "Tab"}
    values["CONST"] = f"{const(page_id)}_{const(tab_id)}"
    statements(plan.read(door), door)  # an import it cannot read whole is refused before anything is written
    tabless, component = own_page(plan.read(door))
    page_shown = page_file(plan, door)  # before --from-page moves it
    if from_page:
        values |= moved_page(plan, door, page_id, tabless, component)
    template = "from_page.js.tmpl" if from_page else "index.js.tmpl"
    plan.create(f"page/pages/{page_id}/{tab_id}/index.js", render("tab", template, **values))

    def wire(text: str) -> str:
        if from_page:
            text = drop_page(text, component, descriptor)
        line = f"import {{ {name} }} from './{tab_id}/index.js'"
        found = statements(text, door)
        if not found:
            text = line + "\n" + text
        else:  # after the last whole import statement (its closing line), never inside one
            at = text.find("\n", found[-1].end())
            text = text + "\n" + line if at < 0 else text[: at + 1] + line + "\n" + text[at + 1 :]
        return add_to_descriptor(text, "tabs", "[", "]", name)

    plan.edit(door, wire)
    _readme(plan, page_id, "Tabs:", f"`{tab_id}` (`{tab_id}/index.js`)", append=True)
    plan.regenerate = True
    still_page, tabs = own_page(plan.read(door))[1], tab_count(plan.read(door))
    if from_page:
        moved = f", moved from index.js into {values['moved']}" if values.get("moved") else ""
        plan.next_steps.append(
            f"the page's own Page ({values['source']}{moved}) is now the {tab_id} tab, and the descriptor has no Page"
        )
    else:
        if tabless and component:
            plan.skip_checks.append("page")
            plan.notes.append(
                f"the page check is skipped now: {page_id} gets its first tab and keeps its own Page ({component}), "
                "which still renders above the tab bar and the tab, so its page tests may no longer hold; turn the "
                "Page into this tab instead with --from-page, or run python tools/retrodev check once the page is as "
                "it should be"
            )
        plan.next_steps.append(
            f"build the tab in page/pages/{page_id}/{tab_id}/index.js (Page gets the page's {{ shell }})"
        )
    if still_page:
        plan.next_steps.append(
            f"the page's own Page still renders between the tab bar and the tab: {still_page} ({page_shown}) gets a "
            "{ tab } prop (app/page-view.js): keep only what every tab shares there, or drop Page from the "
            f"descriptor (new tab {page_id} <id> --from-page makes a tabless page's Page its first tab)"
        )
    plan.next_steps.append(
        f"describe the tab in page/pages/{page_id}/README.md **Shows:** and in the page's row of docs/dev/STUDIO-PAGES.md"
    )
    if from_page and values.get("moved") and page_in_index(plan, page_id):
        plan.next_steps.append(
            f"remove '{page_id}' from PAGE_IN_INDEX in {REGISTRY_TEST}: its Page is no longer defined in index.js "
            "(new leaves tests/page to you)"
        )
    under = shell_below(plan.read(door))
    if under:
        plan.next_steps.append(
            f"the shell's player and BelowPlayer stay under every tab: page/app/studio-page.js draws them after the "
            f"page's body (tab bar and tab), as {page_id}'s descriptor asks ({under})"
        )
    if tabs == 1:
        plan.next_steps.append(
            f"a single tab shows a tab bar of one: add a second tab (python tools/retrodev new tab {page_id} <tab>), "
            "or keep a page without tabs"
        )
    for test in rendering_tests(plan, page_id):
        plan.next_steps.append(
            f"{test} renders pageOf('{page_id}').Page"
            + (
                ", which is gone now: render the tab's Page there, or the shell (new leaves tests/page to you)"
                if not still_page
                else ": it renders that Page alone, without the tab bar or the tab; check it still tests what it means to"
            )
        )
    return f"tab {page_id}/{tab_id}" + (" (from the page's Page)" if from_page else "")


def shell_below(text: str) -> str:
    """The descriptor's fields that make the shell draw something below the page's body ('pad', 'BelowPlayer')."""
    _name, first, end = descriptor(text)
    body = text.split("\n")[first + 1 : end]
    return ", ".join(f for f in ("pad", "BelowPlayer") if any(re.match(rf"^  {f}\b", line) for line in body))


def page_in_index(plan: Plan, page_id: str) -> bool:
    """tests/page/registry.test.mjs names the page in PAGE_IN_INDEX (pages allowed to define their Page in index.js)."""
    text = plan.read(REGISTRY_TEST) if plan.exists(REGISTRY_TEST) else ""
    found = re.search(r"PAGE_IN_INDEX\s*=\s*new Set\(\[([^\]]*)\]\)", text)
    return bool(found and re.search(rf"['\"]{re.escape(page_id)}['\"]", found.group(1)))


def tab_count(text: str) -> int:
    """How many entries the descriptor's tabs list holds (0 without one)."""
    _name, first, end = descriptor(text)
    body = "\n".join(text.split("\n")[first + 1 : end])
    found = re.search(r"^  tabs: \[(.*?)\]", body, re.M | re.S)
    return len([part for part in found.group(1).split(",") if part.strip()]) if found else 0


def rendering_tests(plan: Plan, page_id: str) -> list[str]:
    """The page tests that render the page's own Page directly (pageOf('<page>').Page)."""
    pattern = re.compile(rf"pageOf\(\s*['\"]{re.escape(page_id)}['\"]\s*\)\.Page\b")
    found = []
    for path in sorted(plan.top.glob("tests/page/*.mjs")):
        rel = str(path.relative_to(plan.top))
        if pattern.search(plan.read(rel)):
            found.append(rel)
    return found


def own_page(text: str) -> tuple[bool, str | None]:
    """(the descriptor has no tabs yet, the name of its own Page component or None)."""
    _name, first, end = descriptor(text)
    body = text.split("\n")[first + 1 : end]
    found = next((m.group(1) for line in body if (m := PAGE_FIELD.match(line))), None)
    return not any(line.startswith("  tabs:") for line in body), found


def moved_page(plan: Plan, door: str, page_id: str, tabless: bool, component: str | None) -> dict:
    """--from-page: the tab template's values (the Page's file as #pages/<page>/<file>.js), once it may move. A Page
    index.js defines itself moves into <page>-page.js first (scaffold_imports.move_out)."""
    if not tabless or not component:
        raise Failure(
            f"--from-page turns the page's own Page into its first tab, and {door} "
            + ("has tabs already" if not tabless else "has no Page field")
            + "; nothing was written",
            f"leave out --from-page: python tools/retrodev new tab {page_id} <id>",
        )
    kind, exported, module = binding(plan.read(door), component)
    if kind is None:
        defined = re.search(rf"^(?:export\s+)?(?:const|let|function|class)\s+{component}\b", plan.read(door), re.M)
        if defined:
            return move_out(plan, door, page_id, component)
        raise Failure(
            f"{door} neither imports nor defines {component}, so the tab cannot import it; nothing was written",
            f"import {component} by name in {door} (import {{ {component} }} from './<file>.js'), then run new tab again",
        )
    module = module or ""
    if kind != "named" or not module.startswith("./"):
        what = {"default": "a default import", "namespace": "a namespace import"}.get(kind, f"an import from {module}")
        raise Failure(
            f"{door} gets {component} through {what}, and --from-page moves only a named import of one of the "
            "page's own files; nothing was written",
            f"export {component} by name from its file and import it as {{ {component} }} from './<file>.js', "
            "then run new tab again",
        )
    source = f"{door.rsplit('/', 1)[0]}/{module.removeprefix('./')}"
    imported = component if exported == component else f"{exported} as {component}"
    return {"Component": component, "Imported": imported, "source": "#pages/" + source.removeprefix("page/pages/")}


def page_file(plan: Plan, door: str) -> str:
    """The file that defines the descriptor's Page component: the module its import names, else the descriptor
    itself (a page may define Page in its index.js)."""
    text = plan.read(door)
    found = re.search(r"^\s*Page:\s*(\w+)", text, re.M)
    if not found:
        return door
    _kind, _exported, module = binding(text, found.group(1))
    return f"{door.rsplit('/', 1)[0]}/{module.removeprefix('./')}" if module and module.startswith("./") else door


def slot(plan: Plan, page_id: str, name: str, doc: str | None) -> str:
    door = known_page(plan, page_id)
    name = name if CAMEL.match(name) else to_camel(name)
    check_name(name, CAMEL, "slot", "cardMenu")
    full = f"{page_id}.{name}"
    doc = js_label(doc, "Where it is on the page. Props: { ... }", "doc")
    for index in plan.top.glob("page/pages/**/index.js"):
        if re.search(rf"""['"]{re.escape(full)}['"]""", plan.read(str(index.relative_to(plan.top)))):
            raise Failure(f"the slot {full} is declared already ({index.relative_to(plan.top)})", "pick another name")
    plan.edit(door, lambda text: add_to_descriptor(text, "slots", "{", "}", f"'{full}': '{doc}'"))
    plan.edit(REGISTRY_TEST, lambda text: _append_to(text, SLOTS_LIST, full, "declared slots", sort=True))
    said = f"declares `{full}` ({doc[:1].lower() + doc[1:].rstrip('.')})"  # a sentence of its own: never runs on
    rel = f"page/pages/{page_id}/README.md"
    before = plan.read(rel) if plan.exists(rel) else None
    if before is not None:
        plan.edit(rel, lambda text: slots_line(text, said))
    if before is None or plan.read(rel) == before:
        plan.notes.append(f"mention {said} under **Slots:** in {rel}")
    plan.regenerate = True
    plan.next_steps += [
        f"render it where the contributions go: import {{ Slot }} from '#app/slots.js'; "
        f"jsx(Slot, {{ name: '{full}', props: {{ ... }} }})",
        f"render it in the tests: add a HOSTS recipe for '{full}' in tests/page/slots.test.mjs (it checks the host "
        "passes exactly the props the doc names)",
        f"another page fills it from its index.js: contributes: {{ '{full}': [Component] }}; a contribution changes "
        "the `filled` assertion in tests/page/registry.test.mjs, the contributing page's README **Slots:** line "
        "(Contributes ...) and the 'Events and slots today' line of docs/dev/STUDIO-PAGES.md",
    ]
    return f"slot {full}"


def slots_line(text: str, said: str) -> str:
    """The README's '**Slots:** declares none, contributes X.' as '**Slots:** <said>. Contributes X.' (the doc in
    brackets, so the line never runs on after it); unchanged when the page declares a slot already."""
    found = re.search(r"\*\*Slots:\*\* declares none(?:[,.;]\s*([cC])ontributes)?", text)
    if not found:
        return text
    rest = ". Contributes" if found.group(1) else ""
    return text[: found.start()] + f"**Slots:** {said}{rest}" + text[found.end() :]


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
