"""A page README's **Slots:** line as `new slot` and `new contribution` write it: a slot's doc with its props objects
and identifiers in backticks (`{ ctx, game }`, `hardwareOn`, `go(pageId)`), the paragraph wrapped at WIDTH columns,
and the sentence that says which page fills a slot (``Games fills it with `Install`.``); and the tab ids a page
README's "Adding a tab here" names as taken (`new tab`).
"""

from __future__ import annotations

import re
import textwrap

WIDTH = 120  # the docs' line length
# What --doc text marks as code: a `{ ... }` props object, a call (`go(pageId)`), or a name that only code has
# (camelCase, a dot or an underscore inside: `hardwareOn`, `shell.ctx`, `game_id`). Never the placeholder `{ ... }`
# of a slot made without --doc: tests/repo/test_placeholders.py finds it unfilled by its exact text.
CODE = re.compile(
    r"\{(?!\s*\.\.\.\s*\})[^{}`]*\}"
    r"|(?<![\w`])[A-Za-z_]\w*\([^()`]*\)"
    r"|(?<![\w`.])(?=[A-Za-z_]*(?:[a-z][A-Z]|_|\.\w))[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?![\w`(])"
)
SPANS = re.compile(r"`[^`]*`")
KEPT = ("is on the page. Props: { ... }",)  # new slot's placeholder doc (tests/repo/test_placeholders.py)


def code_spans(doc: str) -> str:
    """``doc`` with what looks like code in backticks; a part already in backticks stays as it is."""
    parts, at = [], 0
    for span in SPANS.finditer(doc):
        parts.append(CODE.sub(lambda m: f"`{m.group(0)}`", doc[at : span.start()]))
        parts.append(span.group(0))
        at = span.end()
    parts.append(CODE.sub(lambda m: f"`{m.group(0)}`", doc[at:]))
    return "".join(parts)


def rewrap(block: str, width: int = WIDTH) -> str:
    """A Markdown paragraph wrapped at ``width`` when a line is longer, never breaking inside a `code span`;
    unchanged otherwise (the lines its author broke stay)."""
    if all(len(line) <= width for line in block.split("\n")):
        return block
    glued = SPANS.sub(lambda m: m.group(0).replace(" ", "\0"), " ".join(block.split()))
    for kept in KEPT:  # a placeholder stays on one line, where the placeholder test finds it
        glued = glued.replace(kept, kept.replace(" ", "\0"))
    wrapped = textwrap.fill(glued, width, break_on_hyphens=False, break_long_words=False)
    return wrapped.replace("\0", " ")


def slots_block(text: str) -> re.Match | None:
    """The README's **Slots:** paragraph."""
    return re.search(r"\*\*Slots:\*\*.*?(?=\n\n|\Z)", text, re.S)


def with_block(text: str, block: str) -> str:
    """``text`` with its **Slots:** paragraph replaced by ``block``, rewrapped."""
    found = slots_block(text)
    return text if not found else text[: found.start()] + rewrap(block) + text[found.end() :]


def filled_by(text: str, slot: str, page: str, component: str) -> str | None:
    """The host README with ``<Page> fills it with `<Component>`.`` after what its **Slots:** line says of ``slot``
    (before the next slot it declares or its own Contributes sentence), or None when the line does not declare it."""
    found = slots_block(text)
    if not found:
        return None
    block = found.group(0)
    start = re.search(rf"declares\s+`{re.escape(slot)}`", block)
    if not start:
        return None
    after = re.search(r"(?:,\s*|\.\s+|;\s*)(?:(?:Also\s+)?declares\s+`|[cC]ontributes\b)", block[start.end() :])
    end = start.end() + after.start() if after else len(block.rstrip())
    said = block[start.end() : end].rstrip()
    sentence = f"{page} fills it with `{component}`."
    if sentence in said:
        return text
    tail = block[end:]
    if tail[:1] == ".":  # the slot's own sentence ended there: the new one follows it
        joined = block[:end] + ". " + sentence + tail[1:]
    else:
        joined = block[:end].rstrip(".,;") + ". " + sentence + (" " + tail.lstrip(",; ") if tail.strip() else "")
    return with_block(text, joined)


def slots_line(text: str, said: str) -> str:
    """The README's '**Slots:** declares none, contributes X.' as '**Slots:** <said>. Contributes X.' (said:
    'declares `<page>.<name>`: <doc>', a sentence of its own); unchanged when the page declares a slot already."""
    found = re.search(r"\*\*Slots:\*\* declares none(?:[,.;]\s*([cC])ontributes)?", text)
    if not found:
        return text
    rest = ". Contributes" if found.group(1) else ""
    return text[: found.start()] + f"**Slots:** {said}{rest}" + text[found.end() :]


def also_declares(text: str, said: str) -> str:
    """The README whose **Slots:** line declares a slot already with ``said`` ('declares `<page>.<name>`: <doc>')
    as a sentence of its own after the slots it declares: 'Also declares `<page>.<name>`: <doc>.', before its
    Contributes sentence (a lowercase ', contributes ...' becomes one); unchanged without such a line."""
    found = slots_block(text)
    if not found or "declares none" in found.group(0) or said.split(":")[0] in " ".join(found.group(0).split()):
        return text
    block = found.group(0).rstrip()
    sentence = f"Also {said}."
    tail = re.search(r"(?:[,;]\s*|\.\s+)([cC])ontributes\b", block)
    if tail:
        joined = block[: tail.start()].rstrip(".") + ". " + sentence + " Contributes" + block[tail.end() :]
    else:
        joined = block.rstrip(".") + ". " + sentence
    return text[: found.start()] + joined + text[found.start() + len(block) :]


def declares_line(text: str, said: str) -> str:
    """`new slot`'s edit of the page README: slots_line for a page that declares none, else also_declares."""
    return also_declares(slots_line(text, said), said)


TAKEN = re.compile(r"\(((?:`[\w-]+`(?:, | and ))*`[\w-]+`) (?:is|are) taken")


def taken_ids(text: str, tab_id: str) -> str | None:
    """The page README with ``tab_id`` added to its 'Adding a tab here' list of taken ids (```a` and `b` are
    taken`` -> ```a`, `b` and `<tab>` are taken``), or None when the section lists none."""
    start = text.find("## Adding a tab here")
    if start < 0:
        return None
    end = text.find("\n## ", start + 1)
    end = len(text) if end < 0 else end
    found = TAKEN.search(text, start, end)
    if not found:
        return None
    ids = re.findall(r"`([\w-]+)`", found.group(1))
    if tab_id in ids:
        return text
    ids.append(tab_id)
    listed = ", ".join(f"`{i}`" for i in ids[:-1]) + f" and `{ids[-1]}` are taken"
    return text[: found.start(1)] + listed + text[found.end() :]


def taken_readme(plan, page_id: str, tab_id: str) -> None:
    """new tab's edit of the page README's taken ids (taken_ids), said on a done: line."""
    rel = f"page/pages/{page_id}/README.md"
    if not plan.exists(rel) or taken_ids(plan.read(rel), tab_id) in (None, plan.read(rel)):
        return
    plan.edit(rel, lambda text: taken_ids(text, tab_id) or text)
    plan.done.append(f"added `{tab_id}` to the taken tab ids in {rel} 'Adding a tab here'")


def first_tab_step(page_id: str, tab_id: str, component: str, door: str, name: str) -> str:
    """new tab's first step on a page with no tabs that keeps its own Page: make the Page a tab first. Undoing this
    tab names only new's own edits, never a restore of a whole file or folder: the branch may hold other uncommitted
    work there."""
    return (
        f"this page has no tabs yet: `python tools/retrodev new tab {page_id} main --from-page` makes its current content "
        f"a tab, unless {component} is meant to stay above every tab; with --dry-run, run that first, then this one "
        f"again. To take this tab back first, undo only new's edits: rm -r page/pages/{page_id}/{tab_id}; in {door} "
        f"delete the line import {{ {name} }} from './{tab_id}/index.js' and the descriptor's three lines tabs: [ "
        f"{name} ] (and the comma it added to the line above them); in page/pages/{page_id}/README.md drop "
        f"`{tab_id}` from **Tabs:** and from the taken tab ids; then node tools/bundle/bundle.mjs"
    )


def moved_page_steps(plan, page_id: str, tab_id: str, values: dict) -> list[str]:
    """new tab --from-page's steps about the Page it moved: where it is now and, when the page README's **Shows:**
    still explains the page-level Page (it names `Page` or the component), that line with the tab's real import, so
    the author rewrites it from what the tab holds rather than from what the descriptor used to say. Read-only."""
    moved = f", moved from index.js into {values['moved']}" if values.get("moved") else ""
    steps = [f"the page's own Page ({values['source']}{moved}) is now the {tab_id} tab, and the descriptor has no Page"]
    rel = f"page/pages/{page_id}/README.md"
    lines = plan.read(rel).split("\n") if plan.exists(rel) else []
    start = next((n for n, line in enumerate(lines) if line.startswith("**Shows:**")), len(lines))
    names = ("`Page`", f"`{values['Component']}`")
    for number in range(start, len(lines)):
        if not lines[number].strip() or (number > start and lines[number].startswith("**")):
            break  # the end of the Shows paragraph
        if any(name in lines[number] for name in names):
            steps.append(
                f"{rel}:{number + 1} (**Shows:**) still explains the page's own Page, which the descriptor no longer "
                f"has: say the {tab_id} tab shows it now; its Page is {values['Component']} from "
                f"page/pages/{values['source'].removeprefix('#pages/')}, which page/pages/{page_id}/{tab_id}/index.js "
                f"imports as import {{ {values['Imported']} }} from '{values['source']}'"
            )
            break
    return steps


DESIGN_DOC = "docs/dev/STUDIO-PAGES.md"


def doc_sections(doc: str) -> list[tuple[str, list[str]]]:
    """Each `## ` heading of ``doc`` and the `### ` headings under it."""
    sections: list[tuple[str, list[str]]] = []
    for line in doc.split("\n"):
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif line.startswith("### ") and sections:
            sections[-1][1].append(line[4:].strip())
    return sections


def own_sections(doc: str) -> str:
    """For a step naming the `### <Page>` subsections under `## Pages`: the pages described in a top section of their
    own instead (one with a `### Page` subsection, as Build's `## Build: one game, one conversation`), as
    "; Build's is its `### Page` subsection under `## Build: ...`" ('' when there are none)."""
    own = [
        (re.split(r"\W", top)[0], top)
        for top, subs in doc_sections(doc)
        if not top.startswith("Pages") and "Page" in subs
    ]
    return "".join(f"; {page}'s is its `### Page` subsection under `## {top}`" for page, top in own)


def design_heading(doc: str, label: str) -> str:
    """Where docs/dev/STUDIO-PAGES.md describes the page labelled ``label``: its `### <Label>` subsection under
    `## Pages`, else a top `## <Label>...` section of its own (Build's `## Build: one game, one conversation`, with
    the design in its `### Page` subsection when it has one), else none yet: a subsection to add under `## Pages`.
    Without the doc (a partial tree), the usual place: its `### <Page>` subsection under `## Pages`."""
    if not doc.strip():
        return f"its `### <Page>` subsection under `## Pages` of {DESIGN_DOC}"
    sections = doc_sections(doc)
    named = re.compile(rf"{re.escape(label)}(?!\w)")
    for top, subs in sections:
        if top.startswith("Pages") and not named.match(top):
            pages = re.split(r"\W", top)[0]
            for sub in subs:
                if named.match(sub):
                    return f"its `### {sub}` subsection under `## {pages}` of {DESIGN_DOC}"
    for top, subs in sections:
        if named.match(top):
            if "Page" in subs:
                return f"its `### Page` subsection under `## {top}` of {DESIGN_DOC}"
            return f"its `## {top}` section of {DESIGN_DOC}"
    return f"a `### {label}` subsection under `## Pages` of {DESIGN_DOC} (it has none yet: add one)"


TEST_FILE = re.compile(r"`(?:[\w./-]*/)?test_\w+\.py`")


def tests_line(text: str, test: str, what: str) -> str:
    """A feature README's '## Tests' paragraph with the new test file added last, when it names test files already
    (history's '`tests/backend/history/`: `test_snapshots.py` (...), `test_event_build_kept.py` (the event).'):
    ``, `<file>` (<what>)`` before its final period, the file bare or as a path as the others are; unchanged when
    the paragraph names only the folder."""
    found = re.search(r"^## Tests[ \t]*\n\n?((?:[^\n#][^\n]*\n?)+)", text, re.M)
    if not found or not TEST_FILE.search(found.group(1)):
        return text
    block = found.group(1).rstrip("\n")
    named = TEST_FILE.findall(block)[-1]
    shown = test if "/" in named else test.rsplit("/", 1)[-1]
    if f"`{shown}`" in block:
        return text
    entry = f", `{shown}` ({what})"
    grown = block[:-1] + entry + "." if block.endswith(".") else block + entry
    return text[: found.start(1)] + grown + text[found.start(1) + len(block) :]  # its lines as they were


def add_test(plan, feature_name: str, test: str, what: str) -> None:
    """new event, listener and rpc: the feature README's Tests line names their test file when it names files."""
    rel = f"backend/{feature_name}/README.md"
    if plan.exists(rel):
        plan.edit(rel, lambda text: tests_line(text, test, what))
