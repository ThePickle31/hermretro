"""Friction the eleventh round of fresh-agent trials found outside `new`: sync's moved-block hint searched history for
'The' and never named the file the block went to; start --no-plan wrote no pull request body, so a docs change
needed two ship dry runs; a body's What changed kept a name the code had renamed while building; the reference did
not say a taken-over branch's plan and body stay in the main checkout. Each test failed before its fix. `new`'s side
is in test_trial_round_eleven_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_eleven
"""

from pathlib import Path

from retrodev import body_names, sync

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]

# A prose block whose first word is 'The' (the old hint searched for it), then the block the branch edits.
DOC = (
    '"""The library\'s helpers."""\n\n\ndef keep():\n    return 1\n\n\n'
    "def rename_the_game_folder(root, title):\n"
    '    """The folder takes the title, as the card says."""\n'
    "    return root.with_name(title.replace(' ', '-'))\n\n\n"
    "def tail():\n    return 3\n"
)
BLOCK = DOC[DOC.index("def rename_the_game_folder") : DOC.index("def tail")]


class Sync(RepoCase):
    def moved(self, elsewhere: bool) -> tuple[Path, dict]:
        self.on_dev("backend/library/names.py", DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, "backend/library/names.py", DOC.replace("' ', '-'", "' ', '_'"))
        if elsewhere:
            self.on_dev("backend/library/folders.py", BLOCK, "The helper moves to folders.py")
        self.on_dev("backend/library/names.py", DOC.replace(BLOCK, ""), "Names loses the helper")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        return tree, out

    def test_a_moved_block_names_the_file_it_went_to_and_the_steps(self):
        tree, out = self.moved(elsewhere=True)
        fix = out["error"]["message"]
        self.assertRegex(
            fix,
            r"backend/library/names\.py:\d+-\d+: dev moved this block to backend/library/folders\.py \(or deleted "
            r"it\); first check whether dev's version there already does what your lines did; if it does, add only a "
            r"test that pins it; delete the HEAD side of this hunk, git add, sync again, then add your lines in "
            r"backend/library/folders\.py in a new commit",
        )
        self.assertNotIn("-SThe", fix)
        self.assertIn("'-S\"\"\"The folder takes the title, as the card says.\"\"\"'", fix)  # its longest line
        git(tree, "merge", "--abort")

    def test_a_deleted_block_says_so(self):
        tree, out = self.moved(elsewhere=False)
        self.assertRegex(
            out["error"]["message"],
            r"backend/library/names\.py:\d+-\d+: dev deleted this block \(no other file on origin/dev has its "
            r"lines; .*\); delete the HEAD side of this hunk, git add, sync again",
        )
        git(tree, "merge", "--abort")

    def test_the_lines_are_the_hunk_s_markers(self):
        text = "a\n<<<<<<< HEAD\nmine\n=======\n>>>>>>> origin/dev\nb\n"
        self.assertEqual(sync.conflict_hunks(text), [(2, 5, "mine", "")])
        self.assertEqual(
            sync.distinctive_lines("x = 1\n    return the_value_here\nx = 1\n)"), ["return the_value_here"]
        )


class StartNoPlan(RepoCase):
    def test_start_no_plan_writes_the_template_body_and_names_its_path(self):
        code, out = self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "tidy.md"
        self.assertTrue(body.is_file(), out)
        text = body.read_text()
        self.assertIn("Made by an agent (", text)
        self.assertIn("<!-- no plan: say why -->", text)
        self.assertIn("## How verified", text)
        step = next(line for line in out.splitlines() if line.startswith("next: "))
        self.assertIn(f"fill in {body} as you go", step)
        self.assertIn("with `--no-plan` too: the template with the `Made by` line", retrodev_docs("REFERENCE.md"))
        self.assertIn("with `--no-plan`, the template", retrodev_docs("README.md"))


class BodyNames(RepoCase):
    def ready(self, said: str) -> Path:
        tree = self.worktree("docs/tidy")
        self.commit(tree, "backend/library/games.py", "def built_rom(root):\n    return root / 'build.gb'\n", "Rom")
        write(self.main, "notes/pr/tidy.md", GOOD_BODY.replace("Things.", said))
        return tree

    def test_ship_warns_about_a_name_the_code_does_not_have(self):
        tree = self.ready("Adds `games.rom_path` (the built ROM) and `new event`.")
        code, out = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertIn("body_warning", out, out)
        self.assertIn("`games.rom_path`", out["body_warning"])
        self.assertIn("appear(s) nowhere in the branch's diff or tree", out["body_warning"])
        self.assertNotIn("new event", out["body_warning"])  # a quoted command, not an identifier
        failed = [gate["name"] for gate in out.get("gates", []) if not gate["ok"]]
        self.assertNotIn("body", failed)  # a warning, never a gate
        del code

    def test_a_name_the_branch_has_warns_nothing(self):
        tree = self.ready("Adds `games.built_rom` (the built ROM).")
        _code, out = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertNotIn("body_warning", out)

    def test_check_s_last_line_warns_too(self):
        tree = self.ready("Adds `games.rom_path` (the built ROM).")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("`games.rom_path`", out.rstrip().splitlines()[-1])

    def test_only_code_like_names_count(self):
        body = GOOD_BODY.replace("Things.", "`dev`, `new event`, `rom_path`, `useQuery`, `a.b()`, `x/y.py`")
        self.assertEqual(body_names.quoted_identifiers(body), ["rom_path", "useQuery", "a.b()"])
        self.assertIn("warns, never fails", retrodev_docs("REFERENCE.md"))


class Takeover(RepoCase):
    def test_the_reference_says_the_plan_and_body_stay_in_the_main_checkout(self):
        text = retrodev_docs("REFERENCE.md")
        section = text[text.index("**Taking over a teammate's branch**") :].split("\n\n")[0]
        self.assertIn("its plan and pull request body stay in the main checkout's `notes/`", section)
        self.assertIn("shared by every worktree", section)
