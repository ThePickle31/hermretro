"""No placeholder text from `python tools/retrodev new` is left in what ships.

`retrodev new` writes stubs whose prose asks the author to fill it in (a CONTRACT section, a tool's entry, an event
row, a feature's purpose, a page's README and component). The stubs pass every other check on purpose, so a
pull request can still ship them unfilled; this test is what notices. It is not one of the structure tests the
scaffold check runs on its fresh, unfilled copy (tests/retrodev/test_scaffold_tree.py), and it skips itself in the
checks `retrodev new` runs right after writing the stubs (RETRODEV_SCAFFOLD_CHECK, set by tools/retrodev/scaffold.py,
which keeps no pass from that run, and by tests/retrodev/test_scaffold_tree.py for its RD_SCAFFOLD_FULL=nested run on
its throwaway copy).
"""

import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = ROOT / "tools" / "retrodev"

# Each placeholder, as tools/retrodev/templates/ and scaffold_*.py write it, and what the author writes instead.
PLACEHOLDERS = {
    "Describe what it does, its params and its result here.": "the RPC's section: what it does, params, result",
    "say what it does and when the agent calls it": "the tool's entry in CONTRACT: what it does, when the agent calls it",
    "| say when |": "the event row's 'when' column: when it is emitted",
    "key=<value> for each keyword argument": "the event's payload: the keyword arguments it carries",
    "say when it is emitted": "the event's EVENTS entry in the front door: when it is emitted",
    # A bare payload key (`--payload root`): its EVENTS entry says `root=<...>`, its CONTRACT cell `root` (<...>).
    "=<...>": "the payload key's EVENTS entry: what the key holds (key=<what it holds, type>)",
    "(<...>)": "the payload key's CONTRACT cell: what the key holds",
    "(say what it does here)": "the feature's purpose line",
    "describe what the page shows.": "the page README's **Shows:** line",
    "describe what this page shows.": "the page component's first content",
    "describe what this tab shows.": "the tab component's first content",
    "(say what it does)": "the CONTRACT event row's 'Heard by' entry: what the listening feature does then",
    "say what this listener does": "the listener's docstring: what the feature does when the event happens",
    # The tool's schema description (tools.py), which is what the agent reads to pick the tool.
    '"description": "Describe what': "the tool's schema description: what it does and when the agent should call it",
    # `new contribution`'s component stub (scaffold_contribution.py), which returns null until it is written.
    "shows from this page for these props": "the contribution component's docstring and what it returns for the slot",
    # `new slot` without --doc: the descriptor's slots entry and the README's **Slots:** line.
    "is on the page. Props: { ... }": "the slot's doc: where it is on the page and the props it passes",
}
# Placeholders the scaffolds compose at run time, so they are not literal in their sources (PLANNED proves them).
COMPOSED = {"(<...>)"}
# Where they end up: the docs, every README, the folder map, the feature list and the page.
SCANNED_SUFFIXES = {".md", ".toml", ".py", ".js"}
SKIPPED = ("tools/retrodev/", "tests/", "engine/", "tools/npm/", "player/web/", ".dev/", "notes/", ".git/")
GENERATED = {"desktop/plugin.js", "player/frame-shim.js"}


def scanned() -> list[Path]:
    found = []
    for folder, dirs, files in os.walk(ROOT):
        here = Path(folder)
        dirs[:] = sorted(
            name
            for name in dirs
            if name != "node_modules" and not f"{(here / name).relative_to(ROOT).as_posix()}/".startswith(SKIPPED)
        )
        for name in sorted(files):
            rel = (here / name).relative_to(ROOT).as_posix()
            if Path(name).suffix in SCANNED_SUFFIXES and rel not in GENERATED:
                found.append(here / name)
    return found


def left_in(line: str) -> list[str]:
    """The placeholders in one line."""
    return [text for text in PLACEHOLDERS if text in line]


class ScaffoldPlaceholderTests(unittest.TestCase):
    @unittest.skipIf(os.environ.get("RETRODEV_SCAFFOLD_CHECK"), "retrodev new's own run: the stubs are not filled yet")
    def test_no_scaffold_placeholder_is_left(self):
        found = []
        for path in scanned():
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                found += [
                    f"{path.relative_to(ROOT)}:{number}: '{text}' (write {PLACEHOLDERS[text]})"
                    for text in left_in(line)
                ]
        self.assertEqual(
            found,
            [],
            "\n`python tools/retrodev new` left placeholder text to fill in:\n  "
            + "\n  ".join(found)
            + "\nFIX: replace each with the real text it asks for",
        )

    def test_a_planned_listener_leaves_both_listener_placeholders(self):
        """`new listener` (planned in memory, nothing written) leaves the two texts the gate looks for: the listener
        docstring and the CONTRACT row's 'Heard by' entry, in files the gate scans. It listens from a throwaway
        feature planned first (as tests/retrodev/test_scaffold_tree.py does with rdtree), so a real feature that
        already listens to the event never makes it refuse."""
        sys.path.insert(0, str(SCAFFOLD.parent))
        from retrodev import scaffold, scaffold_backend, scaffold_listener

        plan = scaffold.Plan(ROOT)
        scaffold_backend.feature(plan, "rdplaceholder", "A throwaway feature this test plans and never writes")
        scaffold_listener.listener(plan, "rdplaceholder", "library.build_reported")
        planned = {rel: text for rel, text in {**plan.created, **plan.changed}.items() if not rel.startswith(SKIPPED)}
        for text in ("say what this listener does", "(say what it does)"):
            self.assertTrue(any(text in body for body in planned.values()), f"{text!r} not in {sorted(planned)}")

    def test_a_planned_contribution_stub_is_caught(self):
        """`new contribution` (planned in memory, nothing written) leaves in its component stub, in a file the gate
        scans, a placeholder the gate finds: an unfilled stub fails."""
        sys.path.insert(0, str(SCAFFOLD.parent))
        from retrodev import scaffold, scaffold_contribution

        plan = scaffold.Plan(ROOT)
        scaffold_contribution.contribution(plan, "build", "games.cardMenu", "RdplaceholderItem")
        stubs = {rel: text for rel, text in plan.created.items() if not rel.startswith(SKIPPED)}
        self.assertEqual(sorted(stubs), ["page/pages/build/rdplaceholder-item.js"])
        self.assertIn(Path(next(iter(stubs))).suffix, SCANNED_SUFFIXES)
        self.assertTrue(any(text in stubs["page/pages/build/rdplaceholder-item.js"] for text in PLACEHOLDERS))

    def test_each_placeholder_is_caught_in_a_line(self):
        """The gate's own line check (left_in) names every listed placeholder wherever it sits in a line."""
        for text in PLACEHOLDERS:
            self.assertIn(text, left_in(f"  before {text} after"), text)
        self.assertEqual(left_in("a filled line"), [])

    def test_a_new_tools_schema_description_is_caught(self):
        """Each tool template's schema description, with a tool name filled in, is a placeholder the gate finds."""
        for template in sorted(SCAFFOLD.glob("templates/tool/tool*.py.tmpl")):
            lines = [
                line for line in template.read_text(encoding="utf-8").splitlines() if '"description": "Describe' in line
            ]
            if not lines:
                continue
            line = lines[0].replace("{tool}", "chromatic_probe")
            self.assertTrue(any(text in line for text in PLACEHOLDERS), f"{template.name}: {line.strip()}")

    def test_every_placeholder_is_still_one_the_scaffolds_write(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [*SCAFFOLD.glob("scaffold*.py"), *SCAFFOLD.glob("templates/*/*.tmpl")]
        )
        stale = [text for text in PLACEHOLDERS if text not in sources and text not in COMPOSED]
        self.assertEqual(
            stale,
            [],
            "these placeholders are no longer in tools/retrodev/templates/ or scaffold_*.py\n"
            "FIX: update PLACEHOLDERS in tests/repo/test_placeholders.py to the texts the scaffolds write now",
        )


def _scaffold():
    sys.path.insert(0, str(SCAFFOLD.parent))
    from retrodev import scaffold

    return scaffold


def _added(before: str, after: str) -> str:
    """The lines `after` has that `before` does not (counted, so a moved line is not new): the plan's own text."""
    old = Counter(before.splitlines())
    added = []
    for line in after.splitlines():
        if old[line]:
            old[line] -= 1
        else:
            added.append(line)
    return "\n".join(added)


def _planned(*steps, top: Path = ROOT) -> dict[str, str]:
    """The text a throwaway feature (rdplaceholder) and then each `new` step would write into scanned files, planned
    in memory only (nothing is written): a step is (module name, function name, *arguments after the plan). Only the
    lines the plan adds are returned, never what the tree held before: a tree that already has filled or unfilled
    stubs (the scaffold check's grown copy, whose `new event --payload count` leaves `count` (<...>) in CONTRACT)
    changes nothing here."""
    import importlib

    plan = _scaffold().Plan(top)
    backend = importlib.import_module("retrodev.scaffold_backend")
    backend.feature(plan, "rdplaceholder", None)
    for module, function, *args in steps:
        getattr(importlib.import_module(f"retrodev.{module}"), function)(plan, *args)
    written = {rel: text for rel, text in plan.created.items()}
    written.update({rel: _added((top / rel).read_text(encoding="utf-8"), text) for rel, text in plan.changed.items()})
    return {
        rel: text
        for rel, text in written.items()
        if not rel.startswith(SKIPPED) and Path(rel).suffix in SCANNED_SUFFIXES and rel not in GENERATED
    }


# Each placeholder, and the unfilled `new` that writes it (after `new feature rdplaceholder` with no purpose).
PLANNED = {
    "Describe what it does, its params and its result here.": [
        ("scaffold_backend", "rpc_", "rdplaceholder", "rd_probe")
    ],
    "say what it does and when the agent calls it": [("scaffold_tool", "tool", "rdplaceholder", "rd_probe", None)],
    '"description": "Describe what': [("scaffold_tool", "tool", "rdplaceholder", "rd_probe", None)],
    "| say when |": [("scaffold_backend", "event", "rdplaceholder", "probed", None)],
    "key=<value> for each keyword argument": [("scaffold_backend", "event", "rdplaceholder", "probed", None)],
    "say when it is emitted": [("scaffold_backend", "event", "rdplaceholder", "probed", None)],
    "=<...>": [("scaffold_backend", "event", "rdplaceholder", "probed", "root", "a probe ran")],
    "(<...>)": [("scaffold_backend", "event", "rdplaceholder", "probed", "root", "a probe ran")],
    "(say what it does here)": [],
    "describe what the page shows.": [("scaffold_page", "page", "rdplaceholder", None)],
    "describe what this page shows.": [("scaffold_page", "page", "rdplaceholder", None)],
    "describe what this tab shows.": [("scaffold_page", "tab", "build", "rdprobe", None)],
    "(say what it does)": [("scaffold_listener", "listener", "rdplaceholder", "library.build_reported")],
    "say what this listener does": [("scaffold_listener", "listener", "rdplaceholder", "library.build_reported")],
    "shows from this page for these props": [
        ("scaffold_contribution", "contribution", "build", "games.cardMenu", "RdItem")
    ],
    "is on the page. Props: { ... }": [("scaffold_page", "slot", "build", "rdProbe", None)],
}


# The files `new feature` and `new event` read: enough of a tree to plan both in, copied into a throwaway folder.
EVENT_TREE = (
    "backend/features.py",
    "backend/system/events.py",
    "docs/dev/ARCHITECTURE.md",
    "docs/dev/CONTRACT.md",
    "tools/layout.toml",
)


def _event_tree(case: unittest.TestCase) -> Path:
    """A throwaway tree with the files an event plan reads, plus an unfilled event with a bare payload key
    (`new event rdother pinged --payload count`) written into it, so its CONTRACT already says `count` (<...>)."""
    folder = tempfile.TemporaryDirectory()
    case.addCleanup(folder.cleanup)
    top = Path(folder.name)
    for rel in [*EVENT_TREE, *(str(p.relative_to(ROOT)) for p in sorted(ROOT.glob("backend/*/__init__.py")))]:
        (top / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, top / rel)
    import importlib

    plan = _scaffold().Plan(top)
    backend = importlib.import_module("retrodev.scaffold_backend")
    backend.feature(plan, "rdother", "A throwaway feature with an unfilled event")
    backend.event(plan, "rdother", "pinged", "count", "the probe was pinged")
    for rel, text in {**plan.created, **plan.changed}.items():
        (top / rel).parent.mkdir(parents=True, exist_ok=True)
        (top / rel).write_text(text, encoding="utf-8")
    case.assertIn("(<...>)", (top / "docs/dev/CONTRACT.md").read_text(encoding="utf-8"))
    return top


class EachPlaceholderIsCaught(unittest.TestCase):
    """For every placeholder: the unfilled `new` that writes it leaves it, whole on one line, in a file the gate
    scans, and the gate's line check finds it there. A placeholder missing from PLACEHOLDERS fails here."""

    def test_every_placeholder_has_its_scaffold(self):
        self.assertEqual(sorted(PLANNED), sorted(PLACEHOLDERS))

    def test_each_unfilled_scaffold_leaves_its_placeholder_where_the_gate_finds_it(self):
        for text, steps in PLANNED.items():
            with self.subTest(placeholder=text):
                files = _planned(*steps)
                hits = [
                    f"{rel}:{number}"
                    for rel, body in files.items()
                    for number, line in enumerate(body.splitlines(), 1)
                    if text in left_in(line)
                ]
                self.assertTrue(hits, f"{text!r} is not left in a scanned line of {sorted(files)}")

    def test_a_filled_event_leaves_no_event_placeholder(self):
        """A `new event` with every payload key described and --when, planned in a throwaway tree that already holds
        another feature's unfilled bare-payload event (as the scaffold check's grown copy does), adds no event
        placeholder: only the plan's own lines are checked, never what the tree held."""
        top = _event_tree(self)
        files = _planned(
            ("scaffold_backend", "event", "rdplaceholder", "probed", "root=<project folder, str>", "a probe ran"),
            top=top,
        )
        left = {text for body in files.values() for line in body.splitlines() for text in left_in(line)}
        self.assertEqual(left & {"=<...>", "(<...>)", "say when it is emitted", "| say when |"}, set())


if __name__ == "__main__":
    unittest.main()
