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


if __name__ == "__main__":
    unittest.main()
