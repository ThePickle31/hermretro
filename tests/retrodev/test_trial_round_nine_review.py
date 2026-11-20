"""Review round 1 of the ninth round's fixes: `new contribution` imported a component the registry test binds
already (Text, JSDOM) under the same name, and did not see a slot key in double quotes; the scaffold guard failed,
instead of skipping, on a page failure the grown copy inherits. Siblings: `new slot` and the descriptor and registry
test lists, in either quote style. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_nine_review
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from retrodev import scaffold_move
from retrodev.output import Failure
from retrodev.scaffold_page import SLOTS_LIST, add_to_descriptor

from tests.retrodev import test_scaffold_tree as tree_test
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
REGISTRY_TEST = "tests/page/registry.test.mjs"
SLOT = "rdprobe-host.extra"


class ContributionNames(ScaffoldCase):
    def host(self) -> None:
        self.new("page", "rdprobe-host")
        self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")

    def parses(self) -> None:
        """The registry test still parses (acorn refuses a second top-level binding of one name)."""
        if shutil.which("node") and scaffold_move.acorn(self.tree):
            scaffold_move.parse(self.tree, self.read(REGISTRY_TEST), REGISTRY_TEST)

    def test_a_name_the_registry_test_binds_already_is_imported_under_an_alias(self):
        self.host()
        self.assertIn("const Text = ", self.read(REGISTRY_TEST))
        self.assertIn("const { JSDOM } = ", self.read(REGISTRY_TEST))
        out = self.new("contribution", "home", SLOT, "Text")
        registry = self.read(REGISTRY_TEST)
        self.assertIn("const { Text: TextFromHome } = await import('../../page/pages/home/text.js')", registry)
        self.assertIn(f"'{SLOT}': [TextFromHome]", registry)
        self.assertIn("as TextFromHome: the test names Text already", " ".join(out["next"]))
        self.parses()
        self.new("contribution", "rdprobe-host", SLOT, "JSDOM")  # a later page: joins the list, aliased too
        registry = self.read(REGISTRY_TEST)
        self.assertIn("const { JSDOM: JSDOMFromRdprobeHost } = await import(", registry)
        self.assertIn(f"'{SLOT}': [TextFromHome, JSDOMFromRdprobeHost]", registry)
        self.assertIn("import { Text } from './text.js'", self.read("page/pages/home/index.js"))
        self.parses()

    def test_an_alias_the_registry_test_names_too_is_refused_before_anything_is_written(self):
        self.host()
        write(self.tree, REGISTRY_TEST, self.read(REGISTRY_TEST) + "// TextFromHome\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "taken")
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "home", SLOT, "Text", code=1)
        self.assertIn("TextFromHome", out["error"]["message"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)

    def test_a_double_quoted_existing_contribution_is_extended_not_listed_twice(self):
        self.host()
        self.new("contribution", "home", SLOT, "RdprobeFirst")
        door = "page/pages/home/index.js"
        write(self.tree, door, self.read(door).replace(f"'{SLOT}'", f'"{SLOT}"'))
        self.new("contribution", "home", SLOT, "RdprobeSecond")
        text = self.read(door)
        self.assertIn(f'"{SLOT}": [RdprobeFirst, RdprobeSecond]', text)
        self.assertEqual(text.count(SLOT), 1, text)
        self.assertIn(f"'{SLOT}': [RdprobeFirst, RdprobeSecond]", self.read(REGISTRY_TEST))

    def test_a_double_quoted_contribution_in_another_shape_is_refused_before_anything_is_written(self):
        self.host()
        self.new("contribution", "home", SLOT, "RdprobeFirst")
        door = "page/pages/home/index.js"
        write(
            self.tree, door, self.read(door).replace(f"'{SLOT}': [RdprobeFirst]", f'"{SLOT}": [\n    RdprobeFirst\n  ]')
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "multi-line")
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "home", SLOT, "RdprobeSecond", code=1)
        self.assertIn("a shape new cannot extend", out["error"]["message"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)


class QuotedSiblings(ScaffoldCase):
    def test_new_slot_sees_a_double_quoted_declaration_and_keeps_double_quoted_list_entries(self):
        self.new("page", "rdprobe-host")
        door = "page/pages/rdprobe-host/index.js"
        slots = '  Page: RdprobeHostPage,\n  slots: {\n    "rdprobe-host.extra": \'Doc.\'\n  }\n'
        text = self.read(door).replace("  Page: RdprobeHostPage\n", slots)
        write(self.tree, door, text)
        registry = self.read(REGISTRY_TEST)
        declared = re.findall(r"'([^']*)'", SLOTS_LIST.search(registry).group(2))  # the tree's, never pinned here
        registry = registry.replace(f"['{declared[0]}'", f'["{declared[0]}"')  # its first in double quotes
        write(self.tree, REGISTRY_TEST, registry)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "quoted")
        before = git(self.tree, "status", "--porcelain")
        self.new("slot", "rdprobe-host", "extra", code=1)  # declared already, in double quotes
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)
        self.new("slot", "rdprobe-host", "more")
        listed = ", ".join(f"'{slot}'" for slot in sorted([*declared, "rdprobe-host.more"]))
        self.assertIn(f"[{listed}]", self.read(REGISTRY_TEST))

    def test_a_descriptor_field_new_cannot_extend_is_refused_never_added_twice(self):
        base = "export const RD_PAGE = {\n  id: 'rd',\n  %s\n}\n"
        for field in ("'slots': { 'rd.a': 'Doc.' }", '"slots": {}', "slots: SLOTS"):
            with self.subTest(field), self.assertRaises(Failure):
                add_to_descriptor(base % field, "slots", "{", "}", "'rd.b': 'Doc.'")
        grown = add_to_descriptor(base % "slots: { 'rd.a': 'Doc.' }", "slots", "{", "}", "'rd.b': 'Doc.'")
        self.assertEqual(grown.count("slots"), 1, grown)
        self.assertIn("'rd.a': 'Doc.', 'rd.b': 'Doc.'", grown)


class GuardBaselines(unittest.TestCase):
    """The scaffold guard's own logic, on fake suites: an unrelated page failure the copy has already skips both
    guards (the plain one and the grown one); a failure the grown copy's preparation brings fails."""

    def case(self, failing: set[str]) -> tuple[unittest.TestCase, list[str]]:
        """A guard whose copies are empty folders and whose suites fail for the (state, suite) pairs ``failing``
        names, state 'original' or 'grown' (after the preparation). Returns it and the log of what ran."""
        case = tree_test.GeneratedCodePassesTheRealChecks(
            "test_new_writes_code_that_passes_lint_bundle_page_and_the_structure_tests"
        )
        temp = tempfile.TemporaryDirectory(prefix="rd-guard-")
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        log, made = [], []

        def make_tree():
            tree = folder / f"copy{len(made)}"
            tree.mkdir()
            made.append(tree)
            return folder, tree, {}

        def suite(command, tree, env):
            state = "grown" if (tree / "grown").exists() else "original"
            name = "unit" if "unit" in command else "page"
            log.append(f"{state} {name}")
            return subprocess.CompletedProcess(command, int(f"{state} {name}" in failing), "suite output\n", "")

        case.make_tree, case.suite = make_tree, suite
        return case, log

    @staticmethod
    def grow(tree: Path, env: dict) -> None:
        (tree / "grown").write_text("")

    def test_a_page_failure_the_original_copy_has_skips_both_guards(self):
        for prepare in (None, self.grow):
            with self.subTest(grown=bool(prepare)):
                case, log = self.case({"original page", "grown page"})
                with self.assertRaises(unittest.SkipTest) as said:
                    case.guard(prepare, mode="nested")
                self.assertIn(tree_test.PAGE_FIRST, str(said.exception))
                self.assertEqual(log[0], "original page" if prepare else "original unit")

    def test_a_page_failure_the_preparation_brings_fails(self):
        case, log = self.case({"grown page"})
        with self.assertRaises(AssertionError) as said:
            case.guard(self.grow, mode="nested")
        self.assertIn("the grown copy fails page", str(said.exception))
        self.assertEqual(log, ["original page", "grown unit", "grown page"])

    def test_a_unit_failure_is_inherited_only_when_a_fresh_copy_fails_it_too(self):
        case, log = self.case({"original unit", "grown unit"})
        with self.assertRaises(unittest.SkipTest) as said:
            case.guard(self.grow, mode="nested")
        self.assertIn(tree_test.UNIT_FIRST, str(said.exception))
        case, log = self.case({"grown unit"})
        with self.assertRaises(AssertionError) as said:
            case.guard(self.grow, mode="nested")
        self.assertIn("the grown copy fails unit", str(said.exception))
        self.assertEqual(log, ["original page", "grown unit", "original unit"])


if __name__ == "__main__":
    unittest.main()
