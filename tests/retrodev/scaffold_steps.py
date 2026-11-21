"""The steps the scaffold guard (tests/retrodev/test_scaffold_tree.py, RD_SCAFFOLD_FULL=nested) runs on REAL
features and pages, chosen from what the copy declares at run time, so the guard never pins the tree.

Run with: RD_SCAFFOLD_FULL=nested python -m unittest tests.retrodev.test_scaffold_tree
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from retrodev.scaffold_imports import binding
from retrodev.scaffold_page import own_page

# The guard (nested mode only, after STEPS on the same copy): each kind once more on a REAL feature or page, as a
# contributor's branch does, so a test that pins the real tree's current content (Prompts' slots, history without a
# listener, a page without tabs) fails here, in CI, instead of in that contributor's branch. feature, page and a
# library tool are in STEPS already. The steps follow what the copy holds (real_steps), so a branch that gives
# setup or games tabs, or history a listener, still passes: the tabless-page conversions have their own probe
# fixtures (tab_from_page below, tests/retrodev/test_trial_round_five.py).
REAL_PAGES = ("setup", "games")  # prompts stays tabless: the tab tests use it as their host
REAL_LISTENERS = ("history", "assets", "library", "setup", "hermes")  # the first that can take one more


def declared_events(tree: Path) -> dict[str, str]:
    """{event: owning feature} from every front door's EVENTS dict literal."""
    found = {}
    for door in sorted(tree.glob("backend/*/__init__.py")):
        for node in ast.parse(door.read_text()).body:
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
            target = node.target if isinstance(node, ast.AnnAssign) else target
            if getattr(target, "id", "") == "EVENTS" and isinstance(getattr(node, "value", None), ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        found[key.value] = door.parent.name
    return found


def listens(tree: Path, feature: str, event: str) -> bool:
    source = tree / "backend" / feature / "listeners.py"
    text = source.read_text() if source.is_file() else ""
    func = "on_" + event.replace(".", "_")
    return f'@on("{event}")' in text or re.search(rf"^(?:async\s+)?def {func}\b|^{func}\s*=", text, re.M) is not None


def page_steps(tree: Path, page: str, prefix: str) -> list[list[str]]:
    """Two tabs on a real page: the first --from-page when the page has no tabs and imports its Page by name from a
    file of its own (as setup does), else a plain one (a page with tabs, or one that defines its Page in index.js)."""
    text = (tree / "page" / "pages" / page / "index.js").read_text()
    tabless, component = own_page(text)
    kind, _exported, module = binding(text, component) if component else (None, None, None)
    convert = tabless and kind == "named" and (module or "").startswith("./")
    return [["tab", page, f"{prefix}-first", *(["--from-page"] if convert else [])], ["tab", page, f"{prefix}-second"]]


def real_steps(tree: Path) -> list[list[str]]:
    """The guard's steps, chosen from the copy's current declarations (before STEPS run): an event name history does
    not declare, a (feature, event) pair no listener takes yet, the tab kind each real page can take."""
    declared = declared_events(tree)
    pruned = next(f"rdreal_pruned{n or ''}" for n in range(100) if f"history.rdreal_pruned{n or ''}" not in declared)
    pairs = [(f, e) for f in REAL_LISTENERS for e, owner in declared.items() if owner != f and not listens(tree, f, e)]
    feature, event = pairs[0] if pairs else ("library", f"history.{pruned}")  # the new event: nobody hears it yet
    steps = [
        ["rpc", "library", "rdreal_ping"],
        ["rpc", "library", "rdreal_info", "--game"],  # its generated test runs make_library_game on the real tree
        ["event", "history", pruned, "--payload", "game", "--when", "the probe pruned a snapshot"],
        ["listener", feature, event],
    ]
    for page in REAL_PAGES:
        steps += page_steps(tree, page, f"rdreal-{page}")
    steps.append(["slot", "prompts", "rdrealSlot", "--doc", "After the Reader. Props: { ctx }"])
    return steps + contribution_steps(tree)


def declared_slots(tree: Path) -> dict[str, str]:
    """{slot: declaring page} as new contribution reads them (page and tab descriptors' `slots`)."""
    from retrodev.scaffold import Plan
    from retrodev.scaffold_contribution import declared_slots as read

    return read(Plan(tree))


def contribution_steps(tree: Path) -> list[list[str]]:
    """Prompts fills a real slot another page declares (the first, by name): filled or not, the registry test's
    `filled` assertion must take it."""
    sources = "\n".join(path.read_text() for path in sorted(tree.glob("page/**/*.js")))
    name = next(f"RdrealFill{n}" for n in range(1, 100) if not re.search(rf"\bRdrealFill{n}\b", sources))
    slots = sorted(slot for slot, page in declared_slots(tree).items() if page != "prompts")
    return [["contribution", "prompts", slots[0], name]] if slots else []


def grown_steps(tree: Path) -> list[list[str]]:
    """What makes the copy a grown tree (setup with tabs, history listening to library.game_presented, history's
    README naming an RPC module beside rpcs.py), only where it lacks that already: a branch that added any of them
    keeps it, and nothing is made twice."""
    tabless, _component = own_page((tree / "page/pages/setup/index.js").read_text())
    steps = page_steps(tree, "setup", "rdgrown") if tabless else []
    rpcs = next(
        (row for row in (tree / "backend/history/README.md").read_text().splitlines() if row.startswith("- RPCs")), ""
    )
    if not re.match(r"- RPCs \(`rpcs\.py`, `", rpcs):  # review 1, 2: a test pinning the module list fails here
        steps.append(["rpc", "history", "rdgrown_pong", "--module", "rdgrown_pong_rpcs"])
    event = "library.game_presented"
    heard = listens(tree, "history", event) or event not in declared_events(tree)
    return steps + ([] if heard else [["listener", "history", event]])
