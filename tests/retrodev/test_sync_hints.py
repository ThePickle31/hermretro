"""The trial rounds' regressions for this area (RoundEight, RoundEightBinary, RoundEleven, RoundFourteen, RoundNineteen, RoundSix, RoundSixteen, RoundThirteen, RoundTwelve, RoundTwentyOne), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_sync_hints
"""

from pathlib import Path
from tests.retrodev.fixture import RepoCase, git, parallel, write
from retrodev import repo
from retrodev import sync
import json
from retrodev import state

load_tests = parallel

HELPER = "def moving_helper():\n    return 2\n"

TESTS = "tests/backend/library/test_moving.py"

MOVING = "def keep():\n    return 1\n\n\ndef moving_block():\n    return 2\n\n\ndef tail():\n    return 3\n"

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))

ART = "player/art.png"

TEXT = "backend/library/both.py"

DOC = (
    '"""The library\'s helpers."""\n\n\ndef keep():\n    return 1\n\n\n'
    "def rename_the_game_folder(root, title):\n"
    '    """The folder takes the title, as the card says."""\n'
    "    return root.with_name(title.replace(' ', '-'))\n\n\n"
    "def tail():\n    return 3\n"
)

BLOCK = DOC[DOC.index("def rename_the_game_folder") : DOC.index("def tail")]


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


NAMES, FOLDERS = "backend/library/names.py", "backend/library/folders.py"

NAMES, FOLDERS = "backend/library/names.py", "backend/library/folders.py"

PAGES = "docs/dev/STUDIO-PAGES.md"

ROWS = (
    "# Pages\n\n## Pages\n\n| Page | Approved design |\n|---|---|\n"
    "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n\n"
    "## Next\n\nMore.\n"
)

MINE = ROWS.replace("buttons under it |", "buttons under it, and a news strip at the bottom |")

REWRITTEN = ROWS.replace(
    "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n",
    "| Home | Hero + band |\n\n### Home\n\n- Hero band with the title and the last game played\n"
    "- Quick start buttons under the band\n- The band keeps one line on a narrow window\n",
)

PARAGRAPH = (
    '"""The page shows the games you made and the ones you\n'
    "downloaded, newest first, with a cover for each, and the\n"
    'last time you played each one."""\n'
)

MOVING_RoundFourteen = "def moving_block():\n    return 2\n\n\nKEEP = 1\n"

MOVING_RoundSix = "def keep():\n    return 1\n\n\ndef moving_block():\n    return 2\n\n\ndef tail():\n    return 3\n"


class Sync(RepoCase):
    def conflicted(self) -> Path:
        self.on_dev("backend/library/both.py", "VALUE = 1\n", "Both")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/both")
        self.commit(tree, "backend/library/both.py", "VALUE = 2\n")
        self.on_dev("backend/library/both.py", "VALUE = 3\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        return tree

    def test_a_block_moved_into_tests_support_is_found_by_the_hint_s_command(self):
        test = '"""Moving."""\n\n\n{helper}\n\ndef test_it():\n    assert moving_helper() == {value}\n'
        self.on_dev(TESTS, test.format(helper=HELPER, value=2), "A test helper")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/helper")
        self.commit(tree, TESTS, test.format(helper=HELPER.replace("2", "22"), value=22))
        self.on_dev("tests/support.py", HELPER, "The helper moves to tests/support.py")
        self.on_dev(TESTS, test.format(helper="", value=2).replace("\n\n\n\n\n", "\n\n\n"))  # dev's side: empty
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        moved = (
            "dev moved this block to tests/support.py (or deleted it); first check whether dev's version there "
            "already does what your lines did; if it does, add only a test that pins it; delete the HEAD side of "
            "this hunk"  # rounds 11 and 18
        )
        self.assertIn(f"{TESTS}:4-10: {moved}", out["error"]["message"])

    def test_a_resolution_with_lines_neither_side_had_gets_the_own_commit_warning(self):
        tree = self.conflicted()
        write(tree, "backend/library/both.py", "VALUE = 3\nEXTRA = 4\n")
        git(tree, "add", "backend/library/both.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "warning: the resolution adds 1 line(s) neither side had (backend/library/both.py): new work belongs in "
            "its own commit after sync (a resolution over 20 lines needs a full review round at land)",
            out,
        )

    def test_a_resolution_made_of_the_two_sides_warns_nothing(self):
        tree = self.conflicted()
        write(tree, "backend/library/both.py", "VALUE = 2\n")
        git(tree, "add", "backend/library/both.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("neither side had", out)


class SyncBinary(RepoCase):
    def bytes_on_dev(self, name: str, data: bytes) -> None:
        other = self.base / "other"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "pull", "-q", "origin", "dev")
        self.commit_bytes(other, name, data, "Dev changes the art")
        git(other, "push", "-q", "origin", "dev")

    def commit_bytes(self, tree: Path, name: str, data: bytes, message: str = "Change the art") -> None:
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(data)
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", message)

    def conflicted(self, branch_art: bytes | None = None) -> Path:
        """dev changes a PNG and a text file; the branch conflicts on the text file (and on the PNG when given)."""
        self.on_dev(TEXT, "VALUE = 1\n", "Both")
        self.bytes_on_dev(ART, PNG)
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/art")
        self.commit(tree, TEXT, "VALUE = 2\n")
        if branch_art is not None:
            self.commit_bytes(tree, ART, branch_art)
        self.on_dev(TEXT, "VALUE = 3\n")
        self.bytes_on_dev(ART, PNG[::-1] + b"\xff\xfe")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        return tree

    def assert_merged(self, tree: Path) -> None:
        self.assertFalse(repo.ok(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree), "the merge is finished")
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-n1", "HEAD").split()), 3, "a merge commit")
        self.assertEqual(git(tree, "status", "--porcelain"), "")

    def test_a_png_merged_cleanly_from_dev_lets_sync_finish_and_still_warns_about_the_text_file(self):
        tree = self.conflicted()
        write(tree, TEXT, "VALUE = 3\nEXTRA = 4\n")
        git(tree, "add", TEXT)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assert_merged(tree)
        self.assertEqual((tree / ART).read_bytes(), PNG[::-1] + b"\xff\xfe", "dev's art came in")
        self.assertIn(f"warning: the resolution adds 1 line(s) neither side had ({TEXT}): ", out)

    def test_a_png_conflict_resolved_to_dev_s_art_is_never_read_as_text(self):
        """A binary file has no hunks: taking one side whole is its only resolution (here dev's, so it is staged)."""
        tree = self.conflicted(branch_art=PNG + b"\x80ours")
        git(tree, "checkout", "--theirs", "--", ART)
        write(tree, TEXT, "VALUE = 2\n")
        git(tree, "add", ART, TEXT)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assert_merged(tree)
        self.assertEqual((tree / ART).read_bytes(), PNG[::-1] + b"\xff\xfe")
        self.assertNotIn("neither side had", out)

    def test_only_conflicted_files_count_a_cleanly_merged_text_file_never_warns(self):
        """dev and the branch change different hunks of one file (git merges it); only the conflicted file counts."""
        self.on_dev("backend/library/wide.py", "A = 1\n\n\n\n\nB = 1\n", "Wide")
        tree_text = "A = 2\n\n\n\n\nB = 1\n"
        self.on_dev(TEXT, "VALUE = 1\n", "Both")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/wide")
        self.commit(tree, TEXT, "VALUE = 2\n")
        self.commit(tree, "backend/library/wide.py", tree_text)
        self.on_dev(TEXT, "VALUE = 3\n")
        self.on_dev("backend/library/wide.py", "A = 1\n\n\n\n\nB = 3\n")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 1)
        write(tree, TEXT, "VALUE = 2\n")
        write(tree, "backend/library/wide.py", "A = 2\n\n\n\n\nB = 3\nC = 9\n")  # work slipped into a clean file
        git(tree, "add", TEXT, "backend/library/wide.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("neither side had", out)


class SyncRoundEleven(RepoCase):
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

    def test_the_lines_are_the_hunk_s_markers(self):
        text = "a\n<<<<<<< HEAD\nmine\n=======\n>>>>>>> origin/dev\nb\n"
        self.assertEqual(sync.conflict_hunks(text), [(2, 5, "mine", "")])
        self.assertEqual(
            sync.distinctive_lines("x = 1\n    return the_value_here\nx = 1\n)"), ["return the_value_here"]
        )


class SyncHunkLines(RepoCase):
    def test_each_hunk_s_step_has_its_own_line_before_the_fix(self):
        name = "backend/library/moving.py"
        self.on_dev(name, MOVING_RoundFourteen, "A block")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/moved")
        self.commit(tree, name, MOVING_RoundFourteen.replace("return 2", "return 22"))
        self.on_dev(name, MOVING_RoundFourteen.replace("def moving_block():\n    return 2\n\n\n", ""))
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        lines = out.splitlines()
        hint = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
        fix = next(i for i, line in enumerate(lines) if line.startswith("FIX: "))
        self.assertLess(hint, fix, out)
        self.assertIn("dev deleted this block", lines[hint])
        self.assertNotIn("dev deleted this block", lines[fix])
        self.assertIn("first do what each hunk's line above says", lines[fix])
        git(tree, "merge", "--abort")


class SyncFollowUp(RepoCase):
    def conflicted(self, elsewhere: bool):
        """A branch edits the helper in names.py while dev moves it to folders.py (or deletes it); the first sync
        stops on the conflict."""
        self.on_dev(NAMES, DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, NAMES, DOC.replace("' ', '-'", "' ', '_'"))
        if elsewhere:
            self.on_dev(FOLDERS, BLOCK, "The helper moves to folders.py")
        self.on_dev(NAMES, DOC.replace(BLOCK, ""), "Names loses the helper")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        return tree

    def resolve(self, tree):
        """Delete the HEAD side of the hunk (dev's file as it is) and stage it, as the first sync's hint says."""
        write(tree, NAMES, git(tree, "show", f"MERGE_HEAD:{NAMES}"))
        git(tree, "add", NAMES)

    def record(self):
        return state.root(self.main) / "sync" / "fix" / "names.json"

    def test_the_finishing_sync_repeats_where_the_block_went_before_the_next_step(self):
        tree = self.conflicted(elsewhere=True)
        self.assertTrue(self.record().is_file())
        self.resolve(tree)
        code, text = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, text)
        lines = text.splitlines()
        follow = next(i for i, line in enumerate(lines) if line.startswith("follow up after the merge"))
        advice = lines[follow + 1]
        self.assertRegex(
            advice,
            rf"^  {NAMES} \(conflict lines \d+-\d+\): dev moved that block to {FOLDERS} \(or deleted it\); check ",
        )
        self.assertIn("add only a test that pins it", advice)
        step = next(i for i, line in enumerate(lines) if line.startswith("next: "))
        self.assertGreater(step, follow + 1)
        self.assertNotIn(FOLDERS, lines[step])
        self.assertNotIn("warning: the resolution adds", text)
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-1", "HEAD").split()), 3)  # the merge commit
        self.assertFalse(self.record().exists())

    def test_a_deleted_block_names_no_destination(self):
        tree = self.conflicted(elsewhere=False)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out["followup"]), 2, out["followup"])
        self.assertRegex(out["followup"][1], rf"^  {NAMES} \(conflict lines \d+-\d+\): dev deleted that block")
        self.assertNotIn("moved that block", out["followup"][1])
        self.assertTrue(out["next"].startswith("next: "), out["next"])

    def test_advice_from_an_aborted_merge_is_not_repeated_for_another(self):
        tree = self.conflicted(elsewhere=True)
        git(tree, "merge", "--abort")
        self.on_dev("docs/other.md", "more\n", "Dev moves on")
        git(tree, "fetch", "-q", "origin")
        # a merge started by hand: a different MERGE_HEAD than the one the kept advice is about
        git(tree, "merge", "--no-edit", "origin/dev", check=False)
        self.assertTrue(git(tree, "diff", "--name-only", "--diff-filter=U"))
        self.assertTrue(self.record().is_file())
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out["followup"]), 1, out["followup"])
        self.assertIn(f"it conflicted in {NAMES}; if dev moved or rewrote", out["followup"][0])
        self.assertNotIn(FOLDERS, out["followup"][0])

    def test_a_malformed_advice_record_falls_back_and_cannot_stop_a_merge(self):
        tree = self.conflicted(elsewhere=True)
        record = json.loads(self.record().read_text(encoding="utf-8"))
        record["hunks"] = [{}]
        self.record().write_text(json.dumps(record), encoding="utf-8")
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        assert isinstance(out, dict)
        self.assertIn(f"it conflicted in {NAMES}", out["followup"][0])
        self.assertNotIn(FOLDERS, "\n".join(out["followup"]))

    def test_an_unwritable_advice_record_cannot_stop_either_sync(self):
        self.record().mkdir(parents=True)  # a directory at the record path refuses both replacement and unlink
        tree = self.conflicted(elsewhere=True)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        assert isinstance(out, dict)
        self.assertIn(f"it conflicted in {NAMES}", out["followup"][0])
        self.assertNotIn(FOLDERS, "\n".join(out["followup"]))

    def test_no_follow_up_after_a_clean_merge_or_a_plain_conflict(self):
        self.on_dev(NAMES, DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, NAMES, DOC.replace("return 1", "return 10"))
        self.on_dev("docs/other.md", "more\n", "Unrelated")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out.get("followup", [])), (0, []), out)
        self.on_dev(NAMES, DOC.replace("return 1", "return 11"), "Both sides edit one line")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out.get("hunks")), (1, []), out)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out["followup"]), (0, []), out)
        self.assertNotIn("new_lines", out)


class SyncRoundSix(RepoCase):
    def test_a_hunk_dev_removed_gets_the_git_log_hint(self):
        self.on_dev("backend/library/moving.py", MOVING_RoundSix, "A block that will move")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/moved")
        self.commit(tree, "backend/library/moving.py", MOVING_RoundSix.replace("return 2", "return 22"))
        self.on_dev("backend/library/moving.py", MOVING_RoundSix.replace("def moving_block():\n    return 2\n\n\n", ""))
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "backend/library/moving.py:5-11: dev deleted this block (no other file on origin/dev has its lines; if it "
            "moved and changed, `git log -p origin/dev '-Sdef moving_block():'` finds where); delete the HEAD side of "
            "this hunk, git add, sync again",
            out["error"]["message"],
        )


class SyncNextStep(RepoCase):
    def merged(self, branch: str, record: dict | None = None) -> str:
        tree = self.worktree(branch)
        if record:
            state.save_branch(self.main, state.load_branch(self.main, branch) | record)
        self.commit(tree, "backend/library/mine.py", "VALUE = 1\n")
        self.on_dev(f"backend/library/theirs_{branch.partition('/')[2]}.py", "VALUE = 2\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        return steps(out)[-1]

    def test_a_branch_without_a_plan_gets_status_s_plan_step(self):
        said = self.merged("feat/taken", {"taken_over": True})
        self.assertTrue(said.startswith("python tools/retrodev plan new taken"), said)
        self.assertNotIn("ship again", said)

    def test_no_pull_request_says_ship_and_one_says_ship_again(self):
        self.assertEqual(self.merged("docs/tidy"), "python tools/retrodev check, then ship")
        said = self.merged("docs/shipped", {"pr": {"number": 7, "url": "u"}})
        self.assertEqual(said, "python tools/retrodev check, then ship again")


class SyncRewrite(RepoCase):
    def test_a_row_dev_rewrote_into_a_subsection_says_take_dev_s_side_and_where_to_redo_it(self):
        name = "docs/dev/STUDIO-PAGES.md"
        self.on_dev(name, ROWS, "Pages")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/news")
        self.commit(tree, name, MINE)
        self.on_dev(name, REWRITTEN, "The row becomes a subsection")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        fix = out["error"]["message"]
        self.assertRegex(
            fix,
            r"docs/dev/STUDIO-PAGES\.md:\d+-\d+: dev rewrote this block; take dev's side, then redo your change in "
            r"the `### Home` subsection at docs/dev/STUDIO-PAGES\.md:\d+ in its own commit after sync",
        )
        self.assertNotIn("dev moved this block", fix)
        git(tree, "merge", "--abort")

    def test_a_row_dev_rewrote_into_two_alike_subsections_names_no_place_but_the_diff(self):
        name = "docs/dev/STUDIO-PAGES.md"
        self.on_dev(name, ROWS, "Pages")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/news")
        self.commit(tree, name, MINE)
        twins = "- Hero band with the title, the last game played\n- Quick start buttons under the band\n"
        split = ROWS.replace(
            "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n",
            f"| Home | Hero + band |\n\n### Hero\n\n{twins}\n### Band\n\n{twins}",
        )
        self.on_dev(name, split, "The row becomes two subsections")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        fix = out["error"]["message"]
        self.assertIn(
            "dev rewrote this block (see git diff HEAD...origin/dev -- docs/dev/STUDIO-PAGES.md); take dev's side, "
            "then redo your change where it belongs now in its own commit after sync",
            fix,
        )
        self.assertNotRegex(fix, r"redo your change in docs/dev/STUDIO-PAGES\.md:\d+")
        git(tree, "merge", "--abort")

    def test_only_a_modified_copy_of_a_removed_line_in_a_much_longer_dev_side_counts(self):
        base = ["| Home | Hero band with the title and the buttons |", "x"]
        dev = ["| Home | Hero |", "", "### Home", "- Hero band", "- Buttons", "x"]
        theirs = "\n".join(dev[:5])
        mine = "| Home | Hero band with the title and the buttons, and news |"
        self.assertEqual(sync.rewritten_from(mine, theirs, base, dev), [mine])
        self.assertEqual(sync.rewritten_from("| Away | something else entirely here |", theirs, base, dev), [])
        self.assertEqual(sync.rewritten_from(mine, "| Home | Hero |", base, dev), [], "dev's side is not longer")

    def test_two_blocks_about_as_alike_or_two_named_headings_name_no_place(self):
        row = ["| Home | Hero band with the title and the buttons |", "x"]
        rewritten = ["| Home | Hero |", "", "### Home", "- Hero band", "- Buttons", "x"]
        mine_row = ["| Home | Hero band with the title and the buttons, and news |"]
        self.assertEqual(
            sync.new_location("docs/p.md", mine_row, rewritten, row), "the `### Home` subsection at docs/p.md:3"
        )  # round thirteen: the nearest named subsection, never the short row
        just_below = ["| Start | Hero band with the title |", "", "### Landing", "- Hero band with the title",
                      "- The buttons", "", "### Other", "- Unrelated words entirely", "x"]  # fmt: skip
        start_row = ["| Start | Hero band with the title and the buttons |", "x"]
        mine_start = ["| Start | Hero band with the title and the buttons, and news |"]
        self.assertEqual(
            sync.new_location("docs/p.md", mine_start, just_below, start_row),
            "the `### Landing` subsection at docs/p.md:3",
        )  # round thirteen: most alike, never a row
        base = ["| Start | Hero band with the title and the buttons |", "x"]
        twins = ["- Hero band with the title", "- The buttons"]
        dev = ["| Start | Hero |", "", "### Left", *twins, "", "### Right", *twins, "x"]
        mine = ["| Start | Hero band with the title and the buttons, and news |"]
        self.assertEqual(sync.new_location("docs/p.md", mine, dev, base), sync.AMBIGUOUS)
        named = ["| Start | Hero |", "## A", "### Start", "- one", "## B", "### Start", "- two", "x"]
        self.assertEqual(sync.new_location("docs/p.md", mine, named, base), sync.AMBIGUOUS)


class SyncRoundTwelve(RepoCase):
    def test_a_rewrapped_merge_of_two_one_line_edits_warns_nothing(self):
        name = "backend/library/words.py"
        self.on_dev(name, PARAGRAPH, "Words")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/words")
        self.commit(tree, name, PARAGRAPH.replace("you made", "you built"))
        self.on_dev(name, PARAGRAPH.replace("a cover", "a picture"))
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)  # adjacent lines: git leaves a conflict
        rewrapped = (
            '"""The page shows the games you built and the ones\nyou downloaded, newest first, with a picture for\n'
            'each, and the last time you played each one."""\n'
        )
        write(tree, name, rewrapped)
        git(tree, "add", name)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("neither side had", out)

    def test_a_new_word_in_a_rewrapped_merge_still_counts(self):
        ours, theirs = ["a b c", "d e f"], ["a b c", "d e g"]
        self.assertEqual(sync.unseen_lines(["a b", "c d e", "f g"], ours, theirs), 0)
        self.assertEqual(sync.unseen_lines(["a b", "c d e", "f g", "EXTRA = 4"], ours, theirs), 1)


class SyncProse(RepoCase):
    def test_a_reworded_prose_resolution_still_warns_and_says_it_needs_no_commit_of_its_own(self):
        doc = "docs/guide.md"
        self.on_dev(doc, "# Guide\n\nThe page shows games.\n", "Guide")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/guide")
        self.commit(tree, doc, "# Guide\n\nThe page shows every game.\n")
        self.on_dev(doc, "# Guide\n\nThe page shows the games you made.\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        write(tree, doc, "# Guide\n\nThe page shows every game you made.\n")  # both sides' words, reworded
        git(tree, "add", doc)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        flat = " ".join(out.split())
        self.assertIn(
            "warning: the resolution adds 1 line(s) neither side had (docs/guide.md): new work belongs in its own "
            "commit after sync (a resolution over 20 lines needs a full review round at land); prose reworded to "
            "join both sides' text counts too: if that is all they are, they need no commit of their own, and land "
            "still counts them toward the 20",
            flat,
        )
