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
HELPER = re.compile(r"^\s*const (\w+) = async\b[^\n]*\n((?:[^\n]*\n){0,6})", re.M)
CLASS = re.compile(r"\bcs-[\w-]+")


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
        count = len(opens.findall(plan.read(rel))) if opens else 0
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
    for match in HELPER.finditer(read(plan, test)):
        if classes & set(CLASS.findall(match.group(0))) and match.group(1) not in found:
            found.append(match.group(1))
    return found


def doubles(plan: Plan) -> str:
    """What a component's effects land in: the harness ctx.os doubles and the sdk stub's scenario.notices."""
    harness = read(plan, HARNESS)
    found = re.search(r"\bos:\s*\{([^}\n]*)\}", harness)
    names = re.findall(r"(\w+):", found.group(1)) if found else []
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
