"""No placeholder text from `python tools/retrodev new` is left in what ships.

`retrodev new` writes stubs whose prose asks the author to fill it in (a CONTRACT section, a tool's line, an event
row, a feature's purpose, a page's README and component). The stubs pass every other check on purpose, so a
pull request can still ship them unfilled; this test is what notices. It is not one of the structure tests the
scaffold check runs on its fresh, unfilled copy (tests/retrodev/test_scaffold_tree.py), and it skips itself in the
checks `retrodev new` runs right after writing the stubs (RETRODEV_SCAFFOLD_CHECK, set by tools/retrodev/scaffold.py,
which keeps no pass from that run, and by tests/retrodev/test_scaffold_tree.py for its RD_SCAFFOLD_FULL=nested run on
its throwaway copy).
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = ROOT / "tools" / "retrodev"

# Each placeholder, as tools/retrodev/templates/ and scaffold_*.py write it, and what the author writes instead.
PLACEHOLDERS = {
    "Describe what it does, its params and its result here.": "the RPC's section: what it does, params, result",
    "say what it does and when the agent calls it.": "the tool's line: what it does and when the agent calls it",
    "| say when |": "the event row's 'when' column: when it is emitted",
    "key=<value> for each keyword argument": "the event's payload: the keyword arguments it carries",
    "(say what it does here)": "the feature's purpose line",
    "describe what the page shows.": "the page README's **Shows:** line",
    "describe what this page shows.": "the page component's first content",
    "describe what this tab shows.": "the tab component's first content",
    "(say what it does)": "the CONTRACT event row's 'Heard by' entry: what the listening feature does then",
    "say what this listener does": "the listener's docstring: what the feature does when the event happens",
    # The tool's schema description (tools.py), which is what the agent reads to pick the tool.
    '"description": "Describe what': "the tool's schema description: what it does and when the agent should call it",
}
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


class ScaffoldPlaceholderTests(unittest.TestCase):
    @unittest.skipIf(os.environ.get("RETRODEV_SCAFFOLD_CHECK"), "retrodev new's own run: the stubs are not filled yet")
    def test_no_scaffold_placeholder_is_left(self):
        found = []
        for path in scanned():
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                found += [
                    f"{path.relative_to(ROOT)}:{number}: '{text}' (write {what})"
                    for text, what in PLACEHOLDERS.items()
                    if text in line
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
        stale = [text for text in PLACEHOLDERS if text not in sources]
        self.assertEqual(
            stale,
            [],
            "these placeholders are no longer in tools/retrodev/templates/ or scaffold_*.py\n"
            "FIX: update PLACEHOLDERS in tests/repo/test_placeholders.py to the texts the scaffolds write now",
        )


if __name__ == "__main__":
    unittest.main()
