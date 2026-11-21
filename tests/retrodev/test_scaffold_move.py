"""`new tab --from-page` moving a Page that index.js defines, from a real JavaScript parse (scaffold_move.py), and
the grown-tree guard's preparation (review round 2 of #47): a dependency imported under another name from the file
the Page moves into is refused, as is one that file binds to another value; a matching import with a trailing comma
is rebuilt from its parsed names; a block comment above the Page moves whole (a JSDoc one too); without acorn the
move is refused with the npm FIX. Every refusal leaves the tree byte for byte as it was; each success parses.
The slow half (the moved pages pass lint and the bundle) is test_scaffold_tree.py's moved_pages_bundle.

Run alone: python -m unittest tests.retrodev.test_scaffold_move
"""

import tempfile
import unittest
from pathlib import Path

from retrodev import scaffold_move

from tests.retrodev import test_scaffold_tree as tree_test
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.scaffold_moves import BLOCK, COMMA, JSDOC, ROOT, door, needs_acorn, snapshot
from tests.retrodev.test_scaffold import ScaffoldCase
import re

load_tests = parallel
OWN = "page/pages/rdprobe-own"
FILE = f"{OWN}/rdprobe-own-page.js"
BODY = "import { jsx } from '#sdk'\n\nexport function Body() {\n  return jsx('div', {})\n}\n"


class Move(ScaffoldCase):
    def probe(self, comment: str = "", imports: str = "", uses: str = "Lede", own: str | None = None) -> None:
        write(self.tree, f"{OWN}/index.js", door("rdprobe-own", comment, imports, uses))
        write(self.tree, f"{OWN}/README.md", "# Own\n\n**Tabs:** none.\n\n**Slots:** declares none.\n")
        if own is not None:
            write(self.tree, FILE, own)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe page")

    def refused(self, *words: str) -> dict:
        before = snapshot(self.tree)
        out = self.new("tab", "rdprobe-own", "first", "--from-page", code=1)
        self.assertIn("nothing was written", out["error"]["message"])
        for said in words:
            self.assertIn(said, out["error"]["message"] + " FIX: " + out["error"]["fix"])
        self.assertEqual(snapshot(self.tree), before, "the tree is byte for byte unchanged")
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
        return out

    def moved(self) -> tuple[str, str]:
        self.new("tab", "rdprobe-own", "first", "--from-page")
        page, index = self.read(FILE), self.read(f"{OWN}/index.js")
        for where, text in ((FILE, page), ("index.js", index)):
            scaffold_move.parse(self.tree, text, where)  # both still parse (a Failure otherwise)
        return page, index

    @needs_acorn
    def test_an_aliased_dependency_from_the_destination_file_is_refused(self):  # review 2, 1
        self.probe(imports="import { Body as Panel } from './rdprobe-own-page.js'\n", uses="Panel", own=BODY)
        self.refused("uses Panel", "imports as { Body }", "import it as { Body }")

    @needs_acorn
    def test_a_destination_local_name_of_another_value_is_refused(self):  # review 2, 1
        self.probe(
            imports="import { Body as Panel } from './rdprobe-own-page.js'\n",
            uses="Panel",
            own=BODY + "\nconst Panel = () => null\nexport const OTHER = Panel\n",
        )
        self.refused("uses Panel", "the name Body there")
        own = "function Inner() {\n  return null\n}\nconst Panel = 1\nexport const OTHER = Panel\nexport { Inner as Panel }\n"
        write(self.tree, FILE, own)  # exported as Panel, but Panel there is another value
        git(self.tree, "commit", "-qam", "Exported under another name")
        write(
            self.tree,
            f"{OWN}/index.js",
            door("rdprobe-own", "", "import { Panel } from './rdprobe-own-page.js'\n", "Panel"),
        )
        git(self.tree, "commit", "-qam", "Imported by that name")
        self.refused("uses Panel", "the name Inner there")

    @needs_acorn
    def test_a_dependency_the_destination_declares_by_the_same_name_moves(self):
        self.probe(imports="import { Body } from './rdprobe-own-page.js'\n", uses="Body", own=BODY)
        page, index = self.moved()
        self.assertNotIn("import { Body }", page, "the moved code reads the file's own Body")
        self.assertIn("export function RdprobeOwn() {\n  return jsx('div', { children: jsx(Body,", page)
        self.assertNotIn("Body", index)

    @needs_acorn
    def test_a_matching_import_with_a_trailing_comma_is_rebuilt(self):  # review 2, 2
        self.probe(own=COMMA.replace("{NOTE}", "OTHER"))
        page, _index = self.moved()
        self.assertIn("import { Small, Lede } from '#shared/ui/text.js'\n", page)
        self.assertNotIn(",,", page)

    @needs_acorn
    def test_a_block_comment_above_the_page_moves_whole(self):  # review 2, 3
        self.probe(BLOCK)
        page, index = self.moved()
        self.assertIn(BLOCK + "export function RdprobeOwn() {", page)
        for part in ("/*", "*/", "in detail"):
            self.assertNotIn(part, index)

    @needs_acorn
    def test_a_jsdoc_block_moves_and_a_comment_a_blank_line_above_it_stays(self):
        self.probe(JSDOC)
        page, index = self.moved()
        self.assertIn("/**\n * Its own Page.\n */\nexport function RdprobeOwn() {", page)
        self.assertNotIn("stays in index.js", page)
        self.assertIn("// stays in index.js (a blank line parts it from the Page)\n", index)
        self.assertNotIn("Its own Page", index)

    @needs_acorn
    def test_a_destination_binding_of_the_page_name_is_refused(self):  # review 3, 0
        own = "import { Small as RdprobeOwn } from '#shared/ui/text.js'\n\nexport const OTHER = RdprobeOwn\n"
        self.probe(own=own)
        self.refused("binds RdprobeOwn", "rename")
        for own in (
            "const B = 1\nexport { B as RdprobeOwn }\n",
            "export { Small as RdprobeOwn } from '#shared/ui/text.js'\n",
        ):
            write(self.tree, FILE, own)  # exported under the Page's name
            git(self.tree, "commit", "-qam", "Exported as the Page's name")
            self.refused("binds RdprobeOwn")

    @needs_acorn
    def test_the_move_edits_only_the_page_range_and_its_boundary(self):  # review 3, 1
        note = "export const NOTE = `one\n\n\n\ntwo`\n"
        self.probe(imports=note)
        before = self.read(f"{OWN}/index.js")
        later = "\nexport const LATER = `three\n\n\n\nfour`\n"
        write(self.tree, f"{OWN}/index.js", before + later)
        git(self.tree, "commit", "-qam", "Another template literal")
        _page, index = self.moved()
        self.assertIn(note, index, "a template literal before the Page is byte for byte the same")
        self.assertTrue(index.endswith("\n  ]\n}\n" + later), "and the text after it too")
        self.assertIn(note + "\nexport const RDPROBE_OWN_PAGE", index, "one blank line where the Page was")

    def test_without_acorn_an_inline_page_is_refused_with_the_npm_fix(self):
        self.probe(BLOCK)
        (self.tree / "tools/npm/node_modules").mkdir(parents=True)  # the tree's npm tools, without acorn
        out = self.refused("the pinned npm tools are not installed")
        self.assertIn("npm ci --prefix tools/npm --ignore-scripts", out["error"]["fix"])

    def test_without_acorn_a_page_in_its_own_file_still_becomes_a_tab(self):  # the separate-file case parses nothing
        self.new("page", "rdprobe-notes")
        (self.tree / "tools/npm/node_modules").mkdir(parents=True)
        self.new("tab", "rdprobe-notes", "first", "--from-page")
        self.assertIn("RdprobeNotesPage", self.read("page/pages/rdprobe-notes/first/index.js"))


class GrownTree(unittest.TestCase):
    def test_the_grown_tree_is_made_only_where_the_copy_lacks_it(self):  # review 2, 0
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp)
            for name in [*ROOT.glob("backend/*/__init__.py"), *ROOT.glob("backend/*/listeners.py")]:
                write(tree, str(name.relative_to(ROOT)), name.read_text())
            own = "// Setup.\nimport { SetupPage } from './setup-page.js'\n\nexport const SETUP_PAGE = {\n  Page: SetupPage\n}\n"
            write(tree, "page/pages/setup/index.js", own)
            write(tree, "backend/history/listeners.py", "")
            write(tree, "backend/history/README.md", "# history\n\n- RPCs (`rpcs.py`): `builds`.\n")
            steps = tree_test.grown_steps(tree)
            self.assertIn(["rpc", "history", "rdgrown_pong", "--module", "rdgrown_pong_rpcs"], steps)  # review 1, 2
            self.assertIn(["tab", "setup", "rdgrown-first", "--from-page"], steps)
            self.assertIn(["listener", "history", "library.game_presented"], steps)
            tabbed = "// Setup.\nimport { SETUP_MAIN_TAB } from './main/index.js'\n\nexport const SETUP_PAGE = {\n  tabs: [SETUP_MAIN_TAB]\n}\n"
            write(tree, "page/pages/setup/index.js", tabbed)  # a branch gave setup tabs and history the listener
            heard = '@on("library.game_presented")\ndef on_library_game_presented(**_payload):\n    pass\n'
            write(tree, "backend/history/listeners.py", heard)
            write(tree, "backend/history/README.md", "# history\n\n- RPCs (`rpcs.py`, `x_rpcs.py`): `builds`, `x`.\n")
            self.assertEqual(tree_test.grown_steps(tree), [], "nothing is made twice")


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


class New(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_from_page_moves_a_page_defined_in_index_js_into_its_own_file(self):
        inline_page(self)
        out = self.new("tab", "rdprobe-own", "first", "--from-page")
        moved = self.read(f"{OWN}/rdprobe-own-page.js")
        self.assertIn("/** Its own Page. */\nexport function RdprobeOwn({ shell }) {", moved)
        self.assertIn("import { jsx } from '#sdk'\nimport { Lede } from '#shared/ui/text.js'\n", moved)
        door = self.read(f"{OWN}/index.js")
        self.assertNotIn("function RdprobeOwn", door)
        self.assertNotIn("import { RdprobeOwn }", door)
        self.assertNotIn("Page:", door)
        self.assertNotIn("#sdk", door, "the imports only the moved Page used go")
        self.assertIn("import { PROBE_CSS } from './probe.css.js'", door)
        tab = self.read(f"{OWN}/first/index.js")
        self.assertIn("import { RdprobeOwn } from '#pages/rdprobe-own/rdprobe-own-page.js'", tab)
        steps = " ".join(out["next"])
        self.assertIn("a single tab shows a tab bar of one", steps)
        self.assertNotIn("still renders between the tab bar and the tab", steps, "the descriptor has no Page now")

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_from_page_appends_to_an_existing_page_file_with_the_imports_it_lacks(self):
        inline_page(self)
        write(self.tree, f"{OWN}/rdprobe-own-page.js", "import { jsx } from '#sdk'\n\nexport const OTHER = 1\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Page file")
        self.new("tab", "rdprobe-own", "first", "--from-page")
        moved = self.read(f"{OWN}/rdprobe-own-page.js")
        self.assertEqual(moved.count("import { jsx } from '#sdk'"), 1)
        self.assertIn("import { jsx } from '#sdk'\nimport { Lede } from '#shared/ui/text.js'\n", moved)
        self.assertTrue(moved.rstrip().endswith("return jsx(Lede, { children: shell.label })\n}"), moved)
        self.assertIn("export const OTHER = 1", moved)

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_from_page_refuses_a_page_file_that_binds_a_used_name_to_another_value(self):  # review 1, 1
        inline_page(self)
        for clash in (
            "import { Small as Lede } from '#shared/ui/text.js'\n\nexport const OTHER = Lede\n",
            "import { Lede } from '#shared/ui/other.js'\n\nexport const OTHER = Lede\n",
            "import { jsx } from '#sdk'\n\nconst Lede = () => null\nexport const OTHER = Lede\n",
        ):
            write(self.tree, f"{OWN}/rdprobe-own-page.js", clash)
            git(self.tree, "add", "-A")
            git(self.tree, "commit", "-q", "-m", "Page file")
            out = self.new("tab", "rdprobe-own", "first", "--from-page", code=1)
            self.assertIn("binds Lede to", out["error"]["message"])
            self.assertIn("nothing was written", out["error"]["message"])
            self.assertIn("rename one of the two Lede bindings", out["error"]["fix"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", "the tree is unchanged")
        write(
            self.tree,
            f"{OWN}/rdprobe-own-page.js",
            "import { Lede } from '#shared/ui/text.js'\n\nexport const OTHER = Lede\n",
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The same import")
        self.new("tab", "rdprobe-own", "first", "--from-page")
        moved = self.read(f"{OWN}/rdprobe-own-page.js")
        self.assertEqual(moved.count("Lede }"), 1, "the identical import is reused")
        self.assertIn("export function RdprobeOwn", moved)

    @needs_acorn  # the move parses index.js (scaffold_move.py)
    def test_from_page_keeps_an_exported_page_exported_from_index_js(self):  # review 1, 2
        inline_page(self, exported=True)
        self.new("tab", "rdprobe-own", "first", "--from-page")
        door = self.read(f"{OWN}/index.js")
        self.assertIn("export { RdprobeOwn } from './rdprobe-own-page.js'", door)
        self.assertNotIn("import { RdprobeOwn }", door, "the descriptor no longer uses it: only the re-export stays")
        self.assertIn("export function RdprobeOwn", self.read(f"{OWN}/rdprobe-own-page.js"))
        inline_page(self, "rdprobe-mine")  # not exported before: index.js does not start exporting it
        self.new("tab", "rdprobe-mine", "first", "--from-page")
        self.assertNotIn("export { RdprobeMine }", self.read("page/pages/rdprobe-mine/index.js"))


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

    def test_tab_from_page_turns_the_page_s_page_into_its_first_tab(self):
        self.new("page", "rdprobe-notes")
        out = self.new("tab", "rdprobe-notes", "first", "--from-page", as_json=False)
        self.assertNotIn("the page check is skipped", out)  # review round 1, finding 1: the page check runs
        tab = self.read("page/pages/rdprobe-notes/first/index.js")
        self.assertIn("import { RdprobeNotesPage } from '#pages/rdprobe-notes/rdprobe-notes-page.js'", tab)
        self.assertIn("  Page: RdprobeNotesPage\n", tab)
        self.assertNotIn("from '../", tab)
        self.assertIn("as #pages/rdprobe-notes/<file>.js (an import\n// that climbs a folder is refused)", tab)
        door = self.read("page/pages/rdprobe-notes/index.js")
        self.assertNotIn("Page: ", door)
        self.assertNotIn("rdprobe-notes-page.js", door)
        self.assertIn("  tabs: [\n    RDPROBE_NOTES_FIRST_TAB\n  ]", door)
        out = self.new("tab", "rdprobe-notes", "again", "--from-page", code=1)  # it has tabs now
        self.assertIn("has tabs already", out["error"]["message"])

    def test_tab_from_page_keeps_an_aliased_import_s_exported_name(self):  # review round 1, finding 2
        self.new("page", "rdprobe-notes")
        self.alias("{ RdprobeNotesPage as NotesPanel }", "Page: NotesPanel")
        self.new("tab", "rdprobe-notes", "first", "--from-page")
        tab = self.read("page/pages/rdprobe-notes/first/index.js")
        self.assertIn(
            "import { RdprobeNotesPage as NotesPanel } from '#pages/rdprobe-notes/rdprobe-notes-page.js'", tab
        )
        self.assertIn("  Page: NotesPanel\n", tab)
        door = self.read("page/pages/rdprobe-notes/index.js")
        self.assertNotIn("rdprobe-notes-page.js", door)
        self.assertNotIn("NotesPanel", door)

    def test_tab_from_page_reads_a_multiline_import_whole(self):  # review round 2, finding 1
        self.new("page", "rdprobe-notes")
        self.alias("{\n  RdprobeNotesPage\n}", "Page: RdprobeNotesPage")
        self.new("tab", "rdprobe-notes", "first", "--from-page")
        tab = self.read("page/pages/rdprobe-notes/first/index.js")
        self.assertIn("import { RdprobeNotesPage } from '#pages/rdprobe-notes/rdprobe-notes-page.js'", tab)
        door = self.read("page/pages/rdprobe-notes/index.js")
        self.assertNotIn("rdprobe-notes-page.js", door)
        self.assertNotIn("RdprobeNotesPage", door)
        self.assertNotIn("import {\n", door)
        self.assertIn("import { RDPROBE_NOTES_FIRST_TAB } from './first/index.js'\n", door)

    def test_a_new_tab_goes_after_a_multiline_import_never_inside_it(self):  # review round 2, finding 1
        self.new("page", "rdprobe-notes")
        self.alias("{\n  RdprobeNotesPage\n}", "Page: RdprobeNotesPage")
        self.new("tab", "rdprobe-notes", "first")
        door = self.read("page/pages/rdprobe-notes/index.js")
        self.assertIn(
            "import {\n  RdprobeNotesPage\n} from './rdprobe-notes-page.js'\n"
            "import { RDPROBE_NOTES_FIRST_TAB } from './first/index.js'\n",
            door,
        )

    def test_an_import_new_cannot_read_whole_is_refused_before_anything_is_written(self):  # round 2, finding 1
        self.new("page", "rdprobe-notes")
        self.alias("{\n  RdprobeNotesPage", "Page: RdprobeNotesPage")  # never closed: no '} from' after it

        def files():
            return {p: p.read_bytes() for p in sorted(self.tree.rglob("*")) if p.is_file() and ".git" not in p.parts}

        before = files()
        for extra in ([], ["--from-page"]):
            out = self.new("tab", "rdprobe-notes", "first", *extra, code=1)
            self.assertIn("cannot read the import statement starting 'import {'", out["error"]["message"])
            self.assertEqual(files(), before)

    def test_tab_from_page_refuses_a_default_namespace_or_unresolvable_page_and_writes_nothing(self):
        def snapshot():
            files = (p for p in sorted(self.tree.rglob("*")) if p.is_file() and ".git" not in p.parts)
            return {str(p.relative_to(self.tree)): p.read_bytes() for p in files}

        self.new("page", "rdprobe-notes")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Page")
        for clause, says in (
            ("RdprobeNotesPage", "a default import"),
            ("* as RdprobeNotesPage", "a namespace import"),
            ("{ Other }", "neither imports nor defines RdprobeNotesPage"),
        ):
            self.alias(clause, "Page: RdprobeNotesPage")
            before = snapshot()
            out = self.new("tab", "rdprobe-notes", "first", "--from-page", code=1)
            self.assertIn(says, out["error"]["message"])
            self.assertEqual(snapshot(), before, f"{clause} changed the tree")
            git(self.tree, "checkout", "-q", "HEAD~1", "--", ".")
            git(self.tree, "commit", "-q", "-m", "Back")


class FromPageShows(ScaffoldCase):
    PAGE = "rdprobe-shows"

    def page_with(self, shows: str) -> str:
        """A probe page (never a live one: those change) whose README Shows paragraph reads ``shows``."""
        self.new("page", self.PAGE)
        rel = f"page/pages/{self.PAGE}/README.md"
        text = self.read(rel)
        write(self.tree, rel, re.sub(r"^\*\*Shows:\*\*[^\n]*", f"**Shows:** {shows}", text, count=1, flags=re.M))
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The probe page")
        return rel

    def test_a_shows_line_that_explains_the_page_level_page_gets_a_step_with_the_tab_s_real_import(self):
        rel = self.page_with("the notes. The page's `Page` is `RdprobeShowsPage`; the descriptor imports it.")
        preview = self.new("tab", self.PAGE, "main", "--from-page", "--dry-run")
        self.assertEqual(git(self.tree, "status", "--porcelain"), "", "the dry run wrote nothing")
        out = self.new("tab", self.PAGE, "main", "--from-page")
        tab = self.read(f"page/pages/{self.PAGE}/main/index.js")
        source = f"#pages/{self.PAGE}/{self.PAGE}-page.js"
        imported = f"import {{ RdprobeShowsPage }} from '{source}'"
        self.assertIn(imported, tab, "the step quotes the import the tab really has")
        line = next(n for n, row in enumerate(self.read(rel).split("\n"), 1) if row.startswith("**Shows:**"))
        step = (
            f"{rel}:{line} (**Shows:**) still explains the page's own Page, which the descriptor no longer has: say "
            f"the main tab shows it now; its Page is RdprobeShowsPage from page/pages/{self.PAGE}/{self.PAGE}-page.js, "
            f"which page/pages/{self.PAGE}/main/index.js imports as {imported}"
        )
        self.assertIn(step, out["next"])
        self.assertIn(step, preview["next"], "the preview names the same step")

    def test_a_shows_line_that_does_not_explain_it_gets_no_such_step(self):
        self.page_with("the notes, newest first.")
        out = self.new("tab", self.PAGE, "main", "--from-page")
        self.assertFalse([step for step in out["next"] if "still explains the page's own Page" in step], out)
        self.assertIn(
            f"the page's own Page (#pages/{self.PAGE}/{self.PAGE}-page.js) is now the main tab, and the descriptor "
            "has no Page",
            out["next"],
        )


if __name__ == "__main__":
    unittest.main()
