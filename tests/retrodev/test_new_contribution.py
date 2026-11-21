"""The trial rounds' regressions for this area (RoundElevenNew, RoundFourteen, RoundNineNew, RoundNineReview, RoundSixteen, RoundTenNew, RoundTenReview), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_contribution
"""

from __future__ import annotations
from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
import re
import shutil
from pathlib import Path
from retrodev import (
    scaffold,
    scaffold_page_tests,
)
import unittest
from retrodev import scaffold_move
from retrodev.output import Failure
from retrodev.scaffold_page import SLOTS_LIST, add_to_descriptor
from retrodev.scaffold import Plan

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""

REGISTRY_TEST = "tests/page/registry.test.mjs"

SLOT = "rdprobe-host.extra"

HARNESS = "  ctx = { os: { writeClipboard: async () => true, openExternal: async () => true } }\n  const pageTab = 1\n"

STUB = "  notify: notice => scenario.notices.push(notice),\n"


def label_of(door: str) -> str:
    found = scaffold_page_tests.LABEL.search(door)
    assert found, door
    return found.group(2)


def helpers_for(test: str, rendered: str) -> list[str]:
    plan = Plan(top=Path("/nonexistent"), created={"t.test.mjs": test, "menu.js": rendered})
    return scaffold_page_tests.slot_helpers(plan, "t.test.mjs", "menu.js")


class Contribution(ScaffoldCase):
    def host(self, declared: bool) -> None:
        self.new("page", "rdprobe-host")
        if declared:
            self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe host")

    def test_a_dry_run_previews_a_slot_not_declared_yet_and_the_real_run_refuses(self):
        self.host(declared=False)
        out = self.new("contribution", "build", "rdprobe-host.extra", "RdprobeItem", "--dry-run", as_json=False)
        self.assertIn(
            "note: slot not declared yet: preview it with python tools/retrodev new slot rdprobe-host extra --dry-run",
            out,
        )
        self.assertIn("dry run: nothing was written", out)
        out = self.new("contribution", "build", "rdprobe-host.extra", "RdprobeItem", code=1)
        self.assertIn("no page declares the slot 'rdprobe-host.extra'", out["error"]["message"])
        self.assertIn("with `--dry-run` only, a slot of an existing host page", retrodev_docs("REFERENCE.md"))

    def test_the_registry_edit_it_made_is_done_not_next(self):
        self.host(declared=True)
        out = self.new("contribution", "build", "rdprobe-host.extra", "RdprobeItem")
        self.assertTrue(any("added RdprobeItem to the `filled` assertion" in line for line in out["done"]), out)
        self.assertFalse([step for step in out["next"] if "added RdprobeItem" in step], out["next"])
        text = self.new("contribution", "build", "rdprobe-host.extra", "RdprobeOther", as_json=False)
        self.assertIn("done: tests/page/registry.test.mjs: added RdprobeOther", text)


class Scaffolds(ScaffoldCase):
    def real(self, *names: str) -> None:
        for name in names:
            (self.tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, self.tree / name)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def files(self, files: dict) -> None:
        for name, text in files.items():
            write(self.tree, name, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Known files")

    def readmes(self) -> None:
        taken = " (`install` and `onboarding` are taken: pick another id)"
        self.real("page/pages/setup/index.js")
        self.files(
            {
                "page/pages/build/README.md": README.format(Label="Build", page="build", taken=""),
                "page/pages/setup/README.md": README.format(Label="Setup", page="setup", taken=taken),
            }
        )

    def test_new_contribution_says_who_fills_the_slot_on_the_host_readme(self):
        self.readmes()
        self.new("slot", "build", "rdfourteenExtras", "--doc", "Below the hero. Props { ctx }")
        out = self.new("contribution", "setup", "build.rdfourteenExtras", "HeroNote")
        text = self.read("page/pages/build/README.md")
        block = " ".join(text[text.index("**Slots:**") :].split("\n\n")[0].split())
        self.assertIn("Props `{ ctx }`. Setup fills it with `HeroNote`.", block)
        self.assertFalse(any("**Slots:** line: say" in step for step in out["next"]), out["next"])
        self.assertTrue(any("page/pages/build/README.md **Slots:** line" in item for item in out["done"]), out)

    def test_a_build_slot_s_test_is_the_one_that_reaches_a_ready_build(self):
        self.files(
            {  # page-setup's shape: Build looked at during setup, more often; page-studio's: Build opened and used
                "tests/page/page-setup.test.mjs": "await tab('Build')\ncheck('a', () => {})\n" * 3,
                "tests/page/page-studio.test.mjs": "await tab('Build')\nscenario.calls.length = 0\nawait click('Send')\n",
                "tests/page/page-games.test.mjs": "await tab('Games')\n",
                "tests/page/page-other.test.mjs": "await tab('Games')\nawait click('Play')\n",
            }
        )
        plan = scaffold.Plan(self.tree)
        found = scaffold_page_tests.scenario_tests(plan, "build")
        self.assertEqual(found, ["tests/page/page-studio.test.mjs", "tests/page/page-setup.test.mjs"])
        self.assertEqual(scaffold_page_tests.scenario_tests(plan, "games")[0], "tests/page/page-games.test.mjs")


class ContributionRoundNineNew(ScaffoldCase):
    def host(self) -> None:
        self.new("page", "rdprobe-host")
        self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")

    def test_it_writes_the_stub_contributes_the_readme_and_the_filled_assertion(self):
        self.host()
        self.new("page", "rdprobe-giver")  # a page of its own: a real page may contribute already (the guard's)
        out = self.new("contribution", "rdprobe-giver", "rdprobe-host.extra", "RdprobeButton")
        folder = "page/pages/rdprobe-giver"
        self.assertEqual(out["created"], [f"{folder}/rdprobe-button.js"])
        self.assertIn("export function RdprobeButton(props) {", self.read(f"{folder}/rdprobe-button.js"))
        door = self.read(f"{folder}/index.js")
        self.assertIn("import { RdprobeButton } from './rdprobe-button.js'", door)
        self.assertIn("'rdprobe-host.extra': [RdprobeButton]", door)
        self.assertIn("contributes `RdprobeButton` to `rdprobe-host.extra`", self.read(f"{folder}/README.md"))
        registry = self.read("tests/page/registry.test.mjs")
        self.assertIn(f"const {{ RdprobeButton }} = await import('../../{folder}/rdprobe-button.js')", registry)
        self.assertRegex(registry, r"const expected = \{[^\n]*'rdprobe-host\.extra': \[RdprobeButton\]")
        steps = joined(out)
        for place in ("'Events and slots today'", "HOSTS"):
            self.assertIn(place, steps)
        # the host's Slots line is written, not left as a step (round 14)
        host = " ".join(self.read("page/pages/rdprobe-host/README.md").split())
        self.assertIn("Rdprobe giver fills it with `RdprobeButton`.", host)

    def test_a_second_contribution_joins_the_list_in_pages_order(self):
        self.host()
        self.new("contribution", "rdprobe-host", "rdprobe-host.extra", "RdprobeLater")  # the last page
        self.new("contribution", "build", "rdprobe-host.extra", "RdprobeFirst")  # the first page
        registry = self.read("tests/page/registry.test.mjs")
        self.assertIn("'rdprobe-host.extra': [RdprobeFirst, RdprobeLater]", registry)
        self.new("contribution", "build", "rdprobe-host.extra", "RdprobeSecond")
        self.assertIn("'rdprobe-host.extra': [RdprobeFirst, RdprobeSecond]", self.read("page/pages/build/index.js"))

    def test_an_undeclared_slot_is_refused_naming_the_declared_ones(self):
        self.host()
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "build", "nowhere.slot", "RdprobeX", code=1)
        self.assertIn("rdprobe-host.extra", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)


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
        out = self.new("contribution", "build", SLOT, "Text")
        registry = self.read(REGISTRY_TEST)
        self.assertIn("const { Text: TextFromBuild } = await import('../../page/pages/build/text.js')", registry)
        self.assertIn(f"'{SLOT}': [TextFromBuild]", registry)
        self.assertIn("as TextFromBuild: the test names Text already", " ".join(out["done"]))
        self.parses()
        self.new("contribution", "rdprobe-host", SLOT, "JSDOM")  # a later page: joins the list, aliased too
        registry = self.read(REGISTRY_TEST)
        self.assertIn("const { JSDOM: JSDOMFromRdprobeHost } = await import(", registry)
        self.assertIn(f"'{SLOT}': [TextFromBuild, JSDOMFromRdprobeHost]", registry)
        self.assertIn("import { Text } from './text.js'", self.read("page/pages/build/index.js"))
        self.parses()

    def test_an_alias_the_registry_test_names_too_is_refused_before_anything_is_written(self):
        self.host()
        write(self.tree, REGISTRY_TEST, self.read(REGISTRY_TEST) + "// TextFromBuild\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "taken")
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "build", SLOT, "Text", code=1)
        self.assertIn("TextFromBuild", out["error"]["message"])
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
        self.new("contribution", "build", SLOT, "RdprobeFirst")
        registry = self.read(REGISTRY_TEST)
        self.assertNotIn(",,", registry.replace(" ", ""))
        self.assertIn(f"'{SLOT}': [RdprobeFirst]", registry)
        self.parses()

    def test_a_double_quoted_existing_contribution_is_extended_not_listed_twice(self):
        self.host()
        self.new("contribution", "build", SLOT, "RdprobeFirst")
        door = "page/pages/build/index.js"
        write(self.tree, door, self.read(door).replace(f"'{SLOT}'", f'"{SLOT}"'))
        self.new("contribution", "build", SLOT, "RdprobeSecond")
        text = self.read(door)
        self.assertIn(f'"{SLOT}": [RdprobeFirst, RdprobeSecond]', text)
        self.assertEqual(text.count(SLOT), 1, text)
        self.assertIn(f"'{SLOT}': [RdprobeFirst, RdprobeSecond]", self.read(REGISTRY_TEST))

    def test_a_double_quoted_contribution_in_another_shape_is_refused_before_anything_is_written(self):
        self.host()
        self.new("contribution", "build", SLOT, "RdprobeFirst")
        door = "page/pages/build/index.js"
        write(
            self.tree, door, self.read(door).replace(f"'{SLOT}': [RdprobeFirst]", f'"{SLOT}": [\n    RdprobeFirst\n  ]')
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "multi-line")
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "build", SLOT, "RdprobeSecond", code=1)
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


class NewSteps(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_new_contribution_says_where_to_test_a_page_atom(self):
        self.real("page/pages/games/**/*.js", "page/pages/games/*.md")
        said = " ".join(self.new("contribution", "build", "games.cardMenu", "RdprobeItem")["next"])
        self.assertIn("test it in a direct-import test like tests/page/slots.test.mjs", said)
        self.assertIn("registerAliases() from tests/page/aliases.mjs", said)
        self.assertIn("export function registerAliases()", (ROOT / "tests/page/aliases.mjs").read_text())
        self.assertIn("registerAliases()", (ROOT / "tests/page/slots.test.mjs").read_text())


class ContributionRoundTenNew(ScaffoldCase):
    def probe_host(self) -> None:
        self.new("page", "rdprobe-host")
        self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")
        write(
            self.tree,
            "page/pages/rdprobe-host/extra-menu.js",
            "export const Menu = () => jsx('div', { className: 'cs-rdextra', children: "
            "jsx(Slot, { name: 'rdprobe-host.extra', props: {} }) })\n",
        )
        label = label_of(self.read("page/pages/rdprobe-host/index.js"))
        opening = "  const openExtra = async () => {\n    await click(dom.querySelector('.cs-rdextra'))\n  }\n"
        write(self.tree, "tests/page/page-rdprobe-host.test.mjs", f"await tab('{label}')\n{opening}")
        write(self.tree, "tests/page/page-other.test.mjs", f"await tab('{label}')\n")
        write(self.tree, "tests/page/harness.mjs", HARNESS)
        write(self.tree, "tests/page/sdk-stub.mjs", STUB)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe host")

    def test_the_next_steps_name_the_host_page_s_scenario_test_its_helper_and_the_doubles(self):
        self.probe_host()
        steps = joined(self.new("contribution", "build", "rdprobe-host.extra", "RdprobeItem"))
        self.assertIn("test what RdprobeItem does in the host page's scenario test tests/page/page-rdprobe-host", steps)
        self.assertIn("then openExtra shows `rdprobe-host.extra`", steps)
        self.assertIn("ctx.os (writeClipboard, openExternal: tests/page/harness.mjs)", steps)
        self.assertIn("scenario.notices (what notify() showed: tests/page/sdk-stub.mjs)", steps)
        self.assertIn("(also opening Rdprobe host: tests/page/page-other.test.mjs)", steps)

    def test_a_host_no_test_opens_says_so(self):
        self.new("page", "rdprobe-lone")
        self.new("slot", "rdprobe-lone", "extra", "--doc", "Buttons. Props: { ctx }")
        steps = joined(self.new("contribution", "build", "rdprobe-lone.extra", "RdprobeLoner"))
        self.assertIn("no tests/page/*.test.mjs opens it yet", steps)

    def test_games_card_menu_points_at_page_games_and_open_game_menu(self):
        # The case the trial hit, on the real files (read from the tree, as new reads them).
        for path in [*ROOT.glob("page/pages/games/**/*.js"), *ROOT.glob("page/pages/games/*.md")]:
            write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        for name in ("page-games.test.mjs", "harness.mjs", "sdk-stub.mjs"):
            write(self.tree, f"tests/page/{name}", (ROOT / "tests/page" / name).read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "games")
        steps = joined(self.new("contribution", "build", "games.cardMenu", "RdprobeCopy"))
        self.assertIn("tests/page/page-games.test.mjs: it opens Games with tab('Games'), then openGameMenu", steps)
        self.assertIn("writeClipboard", steps)
        self.assertIn("scenario.notices", steps)


class BoundedHelpers(unittest.TestCase):
    MENU = "jsx('div', { className: 'cs-menu', children: jsx(Slot, { name: 'games.cardMenu' }) })\n"

    def test_adjacent_short_helpers_are_each_their_own_function(self):
        test = (
            "  const openCard = async card => { await click(card.querySelector('.cs-card')) }\n"
            "  const openMenu = async card => {\n"
            "    await click(card.querySelector('.cs-menu'))\n"
            "  }\n"
        )
        self.assertEqual(helpers_for(test, self.MENU), ["openMenu"])
        expression = "  const a = async () => click('.cs-card')\n  const b = async () => click('.cs-menu')\n"
        self.assertEqual(helpers_for(expression, self.MENU), ["b"])

    def test_strings_comments_and_templates_do_not_end_or_extend_a_helper(self):
        test = (
            "  const openCard = async card => {\n"
            "    // } a brace in a comment, and .cs-menu named only here\n"
            "    await click(card.querySelector(`.cs-card-${'}'}`))\n"
            "    await click('}')\n"
            "  }\n"
            "  const openMenu = async () => { await click('.cs-menu') }\n"
        )
        self.assertEqual(helpers_for(test, self.MENU), ["openMenu"])

    def test_the_harness_doubles_are_its_os_object_s_own_keys(self):
        harness = (
            "    os: { writeClipboard: async () => true, revealPath: async path => { scenario.revealed = path; "
            "return true }, openExternal: async () => true },\n"
        )
        self.assertEqual(
            scaffold_page_tests.object_keys(harness, "os"), ["writeClipboard", "revealPath", "openExternal"]
        )
