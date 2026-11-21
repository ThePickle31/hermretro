"""The trial rounds' regressions for this area (RoundFifteen, RoundFive, RoundFour, RoundFourteen, RoundNineNew, RoundNineteen, RoundSevenNew, RoundSixNew, RoundTenNew), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_tab
"""

import re
from retrodev import scaffold, scaffold_readme
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase
from tests.retrodev.scaffold_moves import needs_acorn
import shutil
from retrodev import (
    scaffold_page_tests,
)
from tests.retrodev.test_scaffold import ROOT

load_tests = parallel

# A small doc in the real shape: what design_heading reads, with no real-tree content pinned (round fifteen).
PAGES_DOC = (
    "## Pages\n\nA page.\n\n### Games\n\nThe games page.\n\n"
    "## Build: one game, one conversation\n\nThe build page.\n\n### Page\n\nThe page.\n"
)


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


OWN = "page/pages/rdprobe-own"


def inline_page(case, page_id: str = "rdprobe-own", exported: bool = False) -> None:
    """A probe page whose index.js defines its own Page (as a page may), committed."""
    name = "".join(part.title() for part in page_id.split("-"))
    export = "export " if exported else ""
    write(
        case.tree,
        f"page/pages/{page_id}/index.js",
        f"// {name}: a probe page.\nimport {{ jsx }} from '#sdk'\nimport {{ Lede }} from '#shared/ui/text.js'\n"
        f"import {{ PROBE_CSS }} from './probe.css.js'\n\n/** Its own Page. */\n{export}function {name}({{ shell }}) {{\n"
        f"  return jsx(Lede, {{ children: shell.label }})\n}}\n\nexport const {page_id.upper().replace('-', '_')}_PAGE = {{\n"
        f"  id: '{page_id}',\n  label: '{name}',\n  Page: {name},\n  css: [PROBE_CSS]\n}}\n",
    )
    write(case.tree, f"page/pages/{page_id}/probe.css.js", "export const PROBE_CSS = ''\n")
    write(case.tree, f"page/pages/{page_id}/README.md", "# Own\n\n**Tabs:** none.\n\n**Slots:** declares none.\n")
    git(case.tree, "add", "-A")
    git(case.tree, "commit", "-q", "-m", "Probe page")


def agent_row(text: str, feature: str) -> str:
    rows = text.split("## The agent half", 1)[1].splitlines()
    return next(line for line in rows if line.startswith(f"| `backend/{feature}/` |"))


README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""


def joined(out) -> str:
    return " ".join(out["next"])


PAGES = "docs/dev/STUDIO-PAGES.md"

PAGES_TEXT = (
    "# Pages\n\n## Pages (one control)\n\n### Home\n\n- hero\n\n## Rdbuild: one game\n\n### Binding\n\n### Page\n\n"
    "- chat\n\n## Adding to the page\n\n### A tab\n\nTesting a tab:\n\n```js\nawait runScenario(async () => {})\n```\n\n"
    "### An event\n"
)


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


HARNESS = "  ctx = { os: { writeClipboard: async () => true, openExternal: async () => true } }\n  const pageTab = 1\n"


def label_of(door: str) -> str:
    found = scaffold_page_tests.LABEL.search(door)
    assert found, door
    return found.group(2)


class TabDesignHeadingRoundFifteen(ScaffoldCase):
    def test_the_hint_names_the_page_s_real_heading(self):
        self.assertEqual(
            scaffold_readme.design_heading(PAGES_DOC, "Build"),
            "its `### Page` subsection under `## Build: one game, one conversation` of docs/dev/STUDIO-PAGES.md",
        )
        self.assertEqual(
            scaffold_readme.design_heading(PAGES_DOC, "Games"),
            "its `### Games` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md",
        )
        self.assertIn("it has none yet: add one", scaffold_readme.design_heading(PAGES_DOC, "Rdprobe"))
        self.assertEqual(
            scaffold_readme.design_heading("## Rdpage tools\n\nText.\n", "Rdpage"),
            "its `## Rdpage tools` section of docs/dev/STUDIO-PAGES.md",
        )

    def test_new_tab_says_it(self):
        write(self.tree, "docs/dev/STUDIO-PAGES.md", PAGES_DOC)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "the pages doc")
        said = " ".join(self.new("tab", "build", "extra")["next"])
        self.assertIn(
            "as a bullet in its `### Page` subsection under `## Build: one game, one conversation` of "
            "docs/dev/STUDIO-PAGES.md",
            said,
        )
        self.assertNotIn("`### <Page>`", said)


class TabsNoneLineRoundFifteen(ScaffoldCase):
    def test_a_none_line_s_parenthetical_goes_with_it(self):
        line = "**Tabs:** none (its areas are subfolders, not tabs)."
        self.assertEqual(
            scaffold.readme_item(line, "Tabs:", "`main` (`main/index.js`)"), "**Tabs:** `main` (`main/index.js`)."
        )
        readme = self.read("page/pages/build/README.md")
        self.assertRegex(readme, r"(?m)^\*\*Tabs:\*\* none\b")  # the real line, whatever its reason says
        write(
            self.tree, "page/pages/build/README.md", re.sub(r"(?m)^\*\*Tabs:\*\* none\b[^\n]*", lambda _m: line, readme)
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "--allow-empty", "-m", "a none with a reason")  # Build has one already
        self.new("tab", "build", "main", "--from-page")
        self.new("tab", "build", "history")
        tabs = next(row for row in self.read("page/pages/build/README.md").splitlines() if "**Tabs:**" in row)
        self.assertEqual(tabs, "**Tabs:** `main` (`main/index.js`), `history` (`history/index.js`).")


class TabTestsRoundFifteen(ScaffoldCase):
    def test_the_step_names_the_page_s_own_files_or_a_new_one_for_the_tab(self):
        write(self.tree, "tests/page/page-build-shelf.test.mjs", "await tab('Build')\n")
        write(self.tree, "tests/page/page-build.test.mjs", "await tab('Build')\n")
        write(self.tree, "tests/page/page-buildly.test.mjs", "await tab('Build')\n")  # another page's
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "build tests")
        said = " ".join(self.new("tab", "build", "extra")["next"])
        self.assertIn(
            "the tab's checks: add a check to the existing tests/page/page-build*.test.mjs that covers this tab "
            "(tests/page/page-build-shelf.test.mjs, tests/page/page-build.test.mjs), or a new "
            "tests/page/page-build-extra.test.mjs (tests/page/*.test.mjs are picked up automatically; name a new one "
            "on the **Tests:** line of page/pages/build/README.md)",
            said,
        )
        self.assertNotIn("page-buildly", said)
        self.assertNotIn("the page's checks are in", said)


class NewRoundFive(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_tab_next_steps_follow_the_descriptor(self):
        inline_page(self)
        write(self.tree, "tests/page/own.test.mjs", "render(jsx(pageOf('rdprobe-own').Page, {}))\n")
        steps = " ".join(self.new("tab", "rdprobe-own", "extra")["next"])
        self.assertIn("the page's own Page still renders between the tab bar and the tab: RdprobeOwn", steps)
        self.assertIn(f"({OWN}/index.js)", steps)
        self.assertIn("a single tab shows a tab bar of one", steps)
        self.assertIn("tests/page/own.test.mjs renders pageOf('rdprobe-own').Page", steps)
        steps = " ".join(self.new("tab", "rdprobe-own", "more")["next"])
        self.assertNotIn("a tab bar of one", steps, "two tabs")
        self.assertEqual(
            git(self.tree, "status", "--porcelain", "tests/page/own.test.mjs"), "?? tests/page/own.test.mjs\n"
        )


class NewRoundFour(ScaffoldCase):
    def row(self, feature: str) -> str:
        return agent_row(self.read("docs/dev/ARCHITECTURE.md"), feature)

    def alias(self, clause: str, page_field: str) -> None:
        """The rdprobe-notes page's index.js importing its Page through ``clause``, committed."""
        door = "page/pages/rdprobe-notes/index.js"
        text = self.read(door).replace("{ RdprobeNotesPage }", clause).replace("Page: RdprobeNotesPage", page_field)
        write(self.tree, door, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Alias")

    def test_a_first_tab_beside_the_page_s_own_page_skips_the_page_check_with_a_note(self):
        self.new("page", "rdprobe-notes")  # a probe page: whether build has tabs is the real tree's business
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe page")
        code, out = self.run_cli("new", "tab", "rdprobe-notes", "extra", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("note: the page check is skipped now", out)
        ran = [name for entry in self.check_log() for name in entry["names"]]
        self.assertIn("bundle", ran)
        self.assertNotIn("page", ran)
        self.clear_log()
        self.run_cli("new", "tab", "rdprobe-notes", "more", cwd=self.tree)  # it has a tab: its page check runs
        self.assertIn("page", [name for entry in self.check_log() for name in entry["names"]])


class ScaffoldsRoundFourteen(ScaffoldCase):
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

    def test_new_tab_on_a_tabless_page_says_to_make_its_page_a_tab_first(self):
        out = self.new("tab", "build", "extra")
        self.assertTrue(
            out["next"][0].startswith(
                "this page has no tabs yet: `python tools/retrodev new tab build main --from-page` makes its current "
                "content a tab"
            ),
            out["next"],
        )
        out = self.new("tab", "build", "more")
        self.assertFalse(any(step.startswith("this page has no tabs yet") for step in out["next"]), out["next"])

    def test_new_tab_adds_its_id_to_the_readme_s_taken_ones(self):
        self.readmes()
        out = self.new("tab", "setup", "extra")
        self.assertIn(
            "(`install`, `onboarding` and `extra` are taken: pick another id)", self.read("page/pages/setup/README.md")
        )
        self.assertIn(
            "added `extra` to the taken tab ids in page/pages/setup/README.md 'Adding a tab here'", out["done"]
        )


class TabRoundNineNew(ScaffoldCase):
    def test_a_page_with_a_player_under_it_says_it_stays_under_every_tab(self):
        self.new("page", "rdprobe-play")
        door = self.tree / "page/pages/rdprobe-play/index.js"
        text = door.read_text().replace("  Page: RdprobePlayPage\n", "  Page: RdprobePlayPage,\n  pad: 'flush',\n")
        write(self.tree, "page/pages/rdprobe-play/index.js", text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "pad")
        steps = joined(self.new("tab", "rdprobe-play", "extra"))
        self.assertIn("the shell's player and BelowPlayer stay under every tab", steps)
        self.new("page", "rdprobe-flat")
        self.assertNotIn("BelowPlayer", joined(self.new("tab", "rdprobe-flat", "extra")))
        shell = (ROOT / "page/app/studio-page.js").read_text()  # body, then the stage, then BelowPlayer
        order = [shell.index("...body,"), shell.index("              stage,"), shell.index("currentPage.BelowPlayer ?")]
        self.assertEqual(order, sorted(order))


class TabExampleRoundNineteen(ScaffoldCase):
    def test_new_tab_points_at_the_runnable_example_when_the_doc_has_it(self):
        self.commit(self.tree, PAGES, PAGES_TEXT, "A pages doc")
        said = " ".join(self.new("tab", "build", "extra", "--dry-run")["next"])
        self.assertIn("a runnable example to start from: docs/dev/STUDIO-PAGES.md 'A tab' (Testing a tab)", said)
        self.commit(self.tree, PAGES, PAGES_TEXT.replace("```js", "```text"), "No example")
        said = " ".join(self.new("tab", "build", "extra", "--dry-run")["next"])
        self.assertNotIn("a runnable example", said)


class TabRoundSevenNew(ScaffoldCase):
    def test_a_taken_id_says_what_the_folder_is_and_how_to_keep_the_label(self):
        write(self.tree, "page/pages/build/rdprobe-x/index.js", "// The probe's own background.\nexport const X = 1\n")
        write(self.tree, "page/pages/build/rdprobe-y/notes.txt", "x\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Folders")
        out = self.new("tab", "build", "rdprobe-x", "--label", "Probe", code=1)
        self.assertIn("page/pages/build/rdprobe-x exists: The probe's own background.", out["error"]["message"])
        self.assertIn("python tools/retrodev new tab build rdprobe-x-tab --label Probe", out["error"]["fix"])
        out = self.new("tab", "build", "rdprobe-y", code=1)
        self.assertIn("page/pages/build/rdprobe-y exists: an existing folder", out["error"]["message"])
        self.assertIn("--label 'Rdprobe y'", out["error"]["fix"])


class TabRoundSixNew(ScaffoldCase):
    def test_every_tab_says_to_describe_it_in_the_readme_and_studio_pages(self):
        self.new("page", "rdprobe-notes")
        steps = self.new("tab", "rdprobe-notes", "extra")["next"]
        self.assertIn(
            "describe the tab in page/pages/rdprobe-notes/README.md **Shows:** and as a bullet in its `### <Page>` "
            "subsection under `## Pages` of docs/dev/STUDIO-PAGES.md (the table row stays short)",
            steps,
        )

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_a_page_moved_out_of_index_js_names_its_page_in_index_entry(self):
        inline_page(self)
        registry = self.read("tests/page/registry.test.mjs")
        # dev's registry test dropped PAGE_IN_INDEX (#49): a branch's registry that still has one gets the step
        registry += "\nconst PAGE_IN_INDEX = new Set(['home', 'rdprobe-own'])\n"
        write(self.tree, "tests/page/registry.test.mjs", registry)
        git(self.tree, "commit", "-qam", "Allowed in index.js")
        steps = " ".join(self.new("tab", "rdprobe-own", "first", "--from-page")["next"])
        self.assertIn("remove 'rdprobe-own' from PAGE_IN_INDEX in tests/page/registry.test.mjs", steps)
        self.assertIn("'rdprobe-own'])", self.read("tests/page/registry.test.mjs"), "new never edits tests/page")
        self.assertTrue((self.tree / f"{OWN}/rdprobe-own-page.js").is_file())


class TabRoundTenNew(ScaffoldCase):
    def test_the_next_steps_name_the_test_that_renders_the_page_s_checks(self):
        self.new("page", "rdprobe-tabbed")
        label = label_of(self.read("page/pages/rdprobe-tabbed/index.js"))
        write(self.tree, "tests/page/page-rdprobe-tabbed.test.mjs", f"await tab('{label}')\n")
        write(self.tree, "tests/page/harness.mjs", HARNESS)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe test")
        steps = joined(self.new("tab", "rdprobe-tabbed", "extra"))
        self.assertIn(  # round 15: the page's own files, or a new one for the tab
            "add a check to the existing tests/page/page-rdprobe-tabbed*.test.mjs that covers this tab "
            "(tests/page/page-rdprobe-tabbed.test.mjs), or a new tests/page/page-rdprobe-tabbed-extra.test.mjs",
            steps,
        )
        self.assertIn(f"tab('{label}') opens the page, then pageTab('Extra') opens the tab", steps)
        self.new("page", "rdprobe-untested")
        steps = joined(self.new("tab", "rdprobe-untested", "extra"))
        self.assertIn("the tab's checks: add tests/page/page-rdprobe-untested-extra.test.mjs", steps)
