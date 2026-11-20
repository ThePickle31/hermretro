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
        self.assertIn("as TextFromHome: the test names Text already", " ".join(out["done"]))
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

    def test_a_trailing_comma_in_the_expected_object_stays_one_comma(self):
        self.host()
        registry = self.read(REGISTRY_TEST)
        found = re.search(r"(const expected = \{)([^\n]*?)(\s*\})", registry)
        self.assertIsNotNone(found, "the registry test's one-line expected object")
        write(
            self.tree, REGISTRY_TEST, registry.replace(found.group(0), found.group(1) + found.group(2).rstrip() + ", }")
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "trailing comma")
        self.new("contribution", "home", SLOT, "RdprobeFirst")
        registry = self.read(REGISTRY_TEST)
        self.assertNotIn(",,", registry.replace(" ", ""))
        self.assertIn(f"'{SLOT}': [RdprobeFirst]", registry)
        self.parses()

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


class WholeModuleFirst(unittest.TestCase):
    """Review round 2, 0 (it replaced the guard's own per-test baselines): the scaffold module looks at the copy's
    page suite (nested: and unit) once, before its first slow test; a failure skips every slow test, a suite
    check.py scaffold vouches for (RD_SCAFFOLD_BASE) is not run again."""

    def case(self, failing: set[str], log: list[str]) -> unittest.TestCase:
        """A slow test whose copies are empty folders and whose suites fail when named in ``failing``."""
        case = tree_test.GeneratedCodePassesTheRealChecks("test_tab_from_page_passes_its_own_checks_lint_and_bundle")
        temp = tempfile.TemporaryDirectory(prefix="rd-first-")
        self.addCleanup(temp.cleanup)

        def suite(command, tree, env):
            log.append(command[-1])
            return subprocess.CompletedProcess(command, int(command[-1] in failing), "suite output\n", "")

        case.copy, case.suite = (lambda: (Path(temp.name), Path(temp.name), {})), suite
        return case

    def test_a_tree_failing_page_skips_every_slow_test_after_one_run(self):
        cache, log = {}, []
        for _ in range(3):  # three slow tests of one process
            with self.assertRaises(unittest.SkipTest) as said:
                self.case({"page"}, log).first("1", "", cache)
            self.assertIn(tree_test.PAGE_FIRST, str(said.exception))
        self.assertEqual(log, ["page"], "the page suite ran once, not per test")

    def test_nested_a_failing_unit_suite_skips_as_unit_first(self):
        cache, log = {}, []
        with self.assertRaises(unittest.SkipTest) as said:
            self.case({"unit", "page"}, log).first("nested", "", cache)
        self.assertIn(tree_test.UNIT_FIRST, str(said.exception))
        self.assertEqual(log, ["unit"])

    def test_suites_check_py_ran_already_are_not_run_again(self):
        cache, log = {}, []
        self.case({"page"}, log).first("nested", "unit,page", cache)
        self.case(set(), log).first("1", "", cache)
        self.assertEqual(log, ["page"], "nested: none run; the plain mode's own page once")


if __name__ == "__main__":
    unittest.main()
