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


def scenario_tests(plan: Plan, page_id: str) -> list[str]:
    """The tests/page/*.test.mjs that open the page: those that press its nav tab (tab('<Label>')), and one named
    page-<page>*.test.mjs; named ones first, then by how often they open it."""
    label = page_label(plan, page_id)
    opens = re.compile(rf"""\btab\(\s*(['"]){re.escape(label)}\1\s*\)""") if label else None
    ranked = []
    for path in sorted(plan.top.glob("tests/page/*.test.mjs")):
        rel = str(path.relative_to(plan.top))
        count = len(opens.findall(lex(plan.read(rel))[0])) if opens else 0  # a commented-out tab() opens nothing
        named = path.name.startswith(f"page-{page_id}.") or path.name.startswith(f"page-{page_id}-")
        if count or named:
            ranked.append((not named, -count, rel))
    return [rel for _named, _count, rel in sorted(ranked)]


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


def tab_step(plan: Plan, page_id: str, tab_label: str) -> str:
    """new tab's step naming which tests/page file renders the page's checks."""
    tests, label = scenario_tests(plan, page_id), page_label(plan, page_id)
    switch = f", then pageTab('{tab_label}') opens the tab" if "const pageTab" in read(plan, HARNESS) else ""
    if not tests:
        return (
            f"the page's checks: no tests/page/*.test.mjs opens {label or page_id} yet; add a scenario test "
            f"(runScenario, {HARNESS}) that opens it with tab('{label or page_id}'){switch}"
        )
    return f"the page's checks are in {tests[0]}: add the tab's there (tab('{label}') opens the page{switch})" + (
        f" (also opening {label}: {', '.join(tests[1:])})" if tests[1:] else ""
    )
