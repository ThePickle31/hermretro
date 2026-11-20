"""Where a page's behaviour is tested, read from the tree for `new tab` and `new contribution`'s next steps: the
tests/page scenario tests that open the page by its nav tab (tab('<Label>'), tests/page/harness.mjs), the helpers
there that open the part of the page a slot sits in, and the harness's doubles a component's effects land in.
Nothing is hard-coded per page or slot: a test, helper or double that is gone is not named.
"""

from __future__ import annotations

import re

from .scaffold import Plan

HARNESS = "tests/page/harness.mjs"
SDK_STUB = "tests/page/sdk-stub.mjs"
LABEL = re.compile(r"""^\s*label:\s*(['"])(.+?)\1""", re.M)
HELPER = re.compile(r"^[ \t]*const (\w+) = async\b", re.M)  # only the declaration: its body is bounded below
CLASS = re.compile(r"\bcs-[\w-]+")
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {""}  # a '/' after one of these starts a regular expression


def lex(text: str) -> tuple[str, str]:
    """(code, bare): the JavaScript with its comments blanked to spaces, and that text with the insides of strings,
    template literals and regular expressions blanked too (a ${...} inside a template stays code). Lengths and
    newlines are kept, so offsets match the source; a commented-out line names nothing, and a brace or newline
    inside a string is not counted as code."""
    code, bare = list(text), list(text)
    i, n, last = 0, len(text), ""
    stack = []  # '`' inside a template literal, '{' inside one of its ${...} expressions (counting nested braces)

    def blank(start: int, end: int, both: bool) -> None:
        for j in range(start, min(end, n)):
            if text[j] != "\n":
                bare[j] = " "
                if both:
                    code[j] = " "

    while i < n:
        c, nxt = text[i], text[i + 1 : i + 2]
        if stack and stack[-1] == "`":
            if c == "`":
                stack.pop()
                i, last = i + 1, "`"
            elif c == "$" and nxt == "{":
                stack.append("{")
                i, last = i + 2, "{"
            else:
                step = 2 if c == "\\" else 1
                blank(i, i + step, False)
                i += step
            continue
        if c == "/" and nxt in ("/", "*"):
            end = text.find("\n", i) if nxt == "/" else text.find("*/", i + 2)
            end = n if end < 0 else end + (0 if nxt == "/" else 2)
            blank(i, end, True)
            i = end
        elif c in "'\"" or (c == "/" and last in REGEX_AFTER):
            j, in_class = i + 1, False
            while j < n and (text[j] != c or in_class) and text[j] != "\n":
                if c == "/" and text[j] in "[]":
                    in_class = text[j] == "["
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, j, False)
            i, last = j + 1, c
        else:
            if c == "`":
                stack.append("`")
            elif stack and c == "{":
                stack.append("{")
            elif stack and c == "}":
                stack.pop()
            if not c.isspace():
                last = c
            i += 1
    return "".join(code), "".join(bare)


def statement_end(bare: str, start: int) -> int:
    """Where the statement starting at ``start`` ends in ``bare`` (lex's second text): its ';', or the newline
    with every bracket it opened closed (a body after '=>' on the next line counts), or the end of an enclosing
    block."""
    depth, i, n = 0, start, len(bare)
    while i < n:
        c = bare[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth < 0:
                return i
        elif depth == 0 and (c == ";" or (c == "\n" and not bare[start:i].rstrip().endswith(("=>", "=", ",")))):
            return i
        i += 1
    return n


def object_keys(text: str, key: str) -> list[str]:
    """The top-level keys of the object literal after the first ``<key>: {`` in the JavaScript (its own braces
    matched, so a function body inside it neither ends it early nor adds keys)."""
    _code, bare = lex(text)
    found = re.search(rf"\b{re.escape(key)}:\s*\{{", bare)
    if not found:
        return []
    flat, depth = [], 0  # the object's own level only: nested brackets' insides blanked
    for c in bare[found.end() :]:
        if c in ")]}" and depth == 0:
            break
        depth += c in "([{"
        flat.append(c if depth == 0 else " ")
        depth -= c in ")]}"
    return re.findall(r"(?:^|,)\s*(\w+)\s*:", "".join(flat))


def helpers(text: str) -> list[tuple[str, str]]:
    """The file's async helpers (const openX = async ...), each with only its own text: up to the end of its own
    statement, so the helper declared after it is neither swallowed nor credited to it."""
    code, bare = lex(text)
    return [(m.group(1), code[m.start() : statement_end(bare, m.start(1))]) for m in HELPER.finditer(bare)]


def read(plan: Plan, rel: str) -> str:
    return plan.read(rel) if plan.exists(rel) else ""


def page_label(plan: Plan, page_id: str) -> str | None:
    """The label the studio nav shows for the page (its descriptor's first `label:`)."""
    found = LABEL.search(read(plan, f"page/pages/{page_id}/index.js"))
    return found.group(2) if found else None


REACH_LINES = 3  # a click within this many lines after tab('<Label>') uses the page: it is shown ready to use


def reaches(code: str, opens: re.Pattern) -> bool:
    """The test uses the page after opening it: a click() within REACH_LINES lines of a tab('<Label>'), before
    another tab() or render(). A page shown while the studio is not ready (Home during setup) is only looked at."""
    for match in opens.finditer(code):
        after = "\n".join(code[match.end() :].split("\n")[: REACH_LINES + 1])
        after = re.split(r"\b(?:tab|render)\(", after, maxsplit=1)[0]
        if re.search(r"\bclick\(", after):
            return True
    return False


def scenario_tests(plan: Plan, page_id: str) -> list[str]:
    """The tests/page/*.test.mjs that open the page: those that press its nav tab (tab('<Label>')), and one named
    page-<page>*.test.mjs. Named ones first (the page's own test), then those that use the page once open (reaches:
    the page shown in a ready studio, e.g. page-studio.test.mjs's tab('Home') then a click, over
    page-setup.test.mjs's Home during setup), then by how often they open it."""
    label = page_label(plan, page_id)
    opens = re.compile(rf"""\btab\(\s*(['"]){re.escape(label)}\1\s*\)""") if label else None
    ranked = []
    for path in sorted(plan.top.glob("tests/page/*.test.mjs")):
        rel = str(path.relative_to(plan.top))
        code = lex(plan.read(rel))[0]  # a commented-out tab() opens nothing
        count = len(opens.findall(code)) if opens else 0
        named = path.name.startswith(f"page-{page_id}.") or path.name.startswith(f"page-{page_id}-")
        if count or named:
            ranked.append((not named, not (opens and reaches(code, opens)), -count, rel))
    return [rel for *_rank, rel in sorted(ranked)]


def slot_file(plan: Plan, host: str, slot: str) -> str | None:
    """The host page's file that renders the slot (jsx(Slot, { name: '<slot>' ... }))."""
    pattern = re.compile(rf"""\bSlot\b[^\n]*\bname:\s*(['"]){re.escape(slot)}\1""")
    for path in sorted(plan.top.glob(f"page/pages/{host}/**/*.js")):
        rel = str(path.relative_to(plan.top))
        if pattern.search(plan.read(rel)):
            return rel
    return None


def slot_helpers(plan: Plan, test: str, rendered_in: str | None) -> list[str]:
    """The test's own async helpers (const openX = async ...) that reach into the markup of the file that renders
    the slot (a cs- class they share), e.g. the one that opens a game's menu."""
    classes = set(CLASS.findall(read(plan, rendered_in))) if rendered_in else set()
    found = []
    for name, body in helpers(read(plan, test)):
        if classes & set(CLASS.findall(body)) and name not in found:
            found.append(name)
    return found


def doubles(plan: Plan) -> str:
    """What a component's effects land in: the harness ctx.os doubles and the sdk stub's scenario.notices."""
    names = object_keys(read(plan, HARNESS), "os")
    said = [f"ctx.os ({', '.join(names)}: {HARNESS})"] if names else []
    if "scenario.notices.push" in read(plan, SDK_STUB):
        said.append(f"scenario.notices (what notify() showed: {SDK_STUB})")
    return " and ".join(said)


def contribution_step(plan: Plan, host: str, slot: str, component: str) -> str:
    """new contribution's step naming where to test what the component does."""
    tests, label = scenario_tests(plan, host), page_label(plan, host)
    if not tests:
        return (
            f"test what {component} does in a scenario test that opens the {host} page (runScenario, {HARNESS}): no "
            f"tests/page/*.test.mjs opens it yet"
        )
    helpers = slot_helpers(plan, tests[0], slot_file(plan, host, slot))
    reach = f", then {' or '.join(helpers)} shows `{slot}`" if helpers else ""
    landed = doubles(plan)
    return (
        f"test what {component} does in the host page's scenario test {tests[0]}: it opens {label} with "
        f"tab('{label}'){reach}"
        + (f"; check its effects in {landed}" if landed else "")
        + (f" (also opening {label}: {', '.join(tests[1:])})" if tests[1:] else "")
    )


def tab_step(plan: Plan, page_id: str, tab_id: str, tab_label: str) -> str:
    """new tab's step naming where the tab's checks go: the page's own test files (page-<page>*.test.mjs) or a new
    one for the tab. Never another page's file, nor a sibling test of one corner of the page (the shelf's): only the
    author knows which of the page's files covers this tab."""
    label = page_label(plan, page_id) or page_id
    switch = f", then pageTab('{tab_label}') opens the tab" if "const pageTab" in read(plan, HARNESS) else ""
    own = sorted(
        str(path.relative_to(plan.top))
        for path in plan.top.glob(f"tests/page/page-{page_id}*.test.mjs")
        if path.name.startswith((f"page-{page_id}.", f"page-{page_id}-"))
    )
    new = f"tests/page/page-{page_id}-{tab_id}.test.mjs"
    where = (
        f"add a check to the existing tests/page/page-{page_id}*.test.mjs that covers this tab ({', '.join(own)}), "
        f"or a new {new}"
        if own
        else f"add {new} (a scenario test: runScenario, {HARNESS})"
    )
    return (
        f"the tab's checks: {where} (tests/page/*.test.mjs are picked up automatically; name a new one on the "
        f"**Tests:** line of page/pages/{page_id}/README.md); tab('{label}') opens the page{switch}"
    )
