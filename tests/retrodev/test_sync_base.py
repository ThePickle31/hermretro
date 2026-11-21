"""The trial rounds' regressions for this area (RoundSeventeen), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_sync_base
"""

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel

SIZE = "page/pages/games/size.js"

FORMAT = "page/shared/format.js"

BASE_LINE = "const megabytes = Math.round(bytes / 1048576);"

SIZE_TEXT = (
    'import { log } from "./log.js";\n\nexport function size(bytes) {\n  log("size");\n  '
    + BASE_LINE
    + '\n  log("done");\n  return label(megabytes);\n}\n'
)

RATE = "page/shared/rate.js"

SPEED_LINE = "const megabytes = Math.round(bytes / 1048576 / 8);"

TWO_TEXT = (
    SIZE_TEXT
    + '\nexport function speed(bytes) {\n  log("speed");\n  '
    + SPEED_LINE
    + '\n  log("rate");\n  return label(megabytes);\n}\n'
)

STEP = '  log("step");'

NEW_LINE = "const megabytes = Math.round(bytes / 1000000);"


class SyncPickaxeFromTheBase(RepoCase):
    def test_the_hint_searches_the_base_line_and_names_the_file_that_took_it(self):
        self.on_dev(SIZE, SIZE_TEXT, "Sizes")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/size")
        self.commit(tree, SIZE, SIZE_TEXT.replace("1048576", "1000000"))
        other = self.base / "other"
        write(
            other,
            FORMAT,
            "export function formatBytes(bytes) {\n  const megabytes = Math.round(bytes / 1024 / 1024);\n  return `${megabytes} MB`;\n}\n",
        )
        write(other, SIZE, SIZE_TEXT.replace("  " + BASE_LINE + "\n", ""))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "formatBytes takes the sizes over")
        git(other, "push", "-q", "origin", "dev")
        moved = git(other, "rev-parse", "--short=9", "HEAD").strip()
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hint = next(line for line in out["error"]["message"].splitlines() if line.startswith(SIZE + ":"))
        self.assertIn(f"-S{BASE_LINE}", hint)
        self.assertNotIn("1000000", hint)
        self.assertIn(FORMAT, hint)
        self.assertIn(moved[:7], hint)


class SyncHintPerHunk(RepoCase):
    def test_each_hunk_names_where_its_own_base_lines_went(self):
        self.on_dev(SIZE, TWO_TEXT, "Sizes and speeds")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/sizes")
        # the speed hunk's new line is an exact copy of size's base line: a whole-file search picks size's commit
        self.commit(
            tree,
            SIZE,
            TWO_TEXT.replace(BASE_LINE, BASE_LINE.replace("1048576", "1000000")).replace(SPEED_LINE, BASE_LINE),
        )
        other = self.base / "other"
        write(
            other,
            FORMAT,
            "export function formatBytes(bytes) {\n  const megabytes = Math.round(bytes / 1024 / 1024);\n}\n",
        )
        write(other, SIZE, TWO_TEXT.replace("  " + BASE_LINE + "\n", ""))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "formatBytes takes the sizes over")
        write(
            other, RATE, "export function rate(bytes) {\n  const megabytes = Math.round(bytes / 1024 / 1024 / 8);\n}\n"
        )
        write(other, SIZE, TWO_TEXT.replace("  " + BASE_LINE + "\n", "").replace("  " + SPEED_LINE + "\n", ""))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "rate takes the speeds over")
        git(other, "push", "-q", "origin", "dev")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hints = [line for line in out["error"]["message"].splitlines() if line.startswith(SIZE + ":")]
        self.assertEqual(len(hints), 2, hints)
        self.assertIn(FORMAT, hints[0])
        self.assertNotIn(RATE, hints[0])
        self.assertIn(RATE, hints[1])
        self.assertNotIn(FORMAT, hints[1])

    def test_a_hunk_whose_context_is_not_unique_gives_no_base_lines(self):
        from retrodev import sync_moved

        text = "x\n<<<<<<< HEAD\nnew\n=======\n>>>>>>> dev\nx\n"
        self.assertEqual(sync_moved._region(["x", "old", "x", "y", "x", "old2", "x"], text, 2, 5), [])
        self.assertEqual(
            sync_moved._region(["x", "y", "x", "old", "x", "z"], text.replace("x\n", "y\nx\n", 1) + "z\n", 3, 6),
            ["old"],
        )


class SyncHintNoGuess(RepoCase):
    def test_ambiguous_context_never_names_a_dev_file_holding_the_branch_s_own_line(self):
        around = "\n".join([STEP] * 3)
        self.on_dev(SIZE, f"{around}\n{BASE_LINE}\n{around}\n", "Sizes")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/guess")
        self.commit(tree, SIZE, f"{around}\n{NEW_LINE}\n{around}\n")
        self.on_dev(SIZE, f"{around}\n{around}\n", "Drop the size line")
        self.on_dev("page/shared/unrelated.js", f"{NEW_LINE}\n", "Unrelated")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hint = next(line for line in out["error"]["message"].splitlines() if line.startswith(SIZE + ":"))
        self.assertNotIn("unrelated.js", hint)
        self.assertIn("deleted this block", hint)

    def test_a_destination_dev_renamed_later_is_not_named(self):
        self.on_dev(SIZE, SIZE_TEXT, "Sizes")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/renamed")
        self.commit(tree, SIZE, SIZE_TEXT.replace("1048576", "1000000"))
        other = self.base / "other"
        write(
            other,
            FORMAT,
            "export function formatBytes(bytes) {\n  const megabytes = Math.round(bytes / 1024 / 1024);\n}\n",
        )
        write(other, SIZE, SIZE_TEXT.replace("  " + BASE_LINE + "\n", ""))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "formatBytes takes the sizes over")
        moved = git(other, "rev-parse", "--short=9", "HEAD").strip()
        git(other, "mv", FORMAT, "page/shared/bytes.js")
        git(other, "commit", "-q", "-m", "Rename format.js")
        git(other, "push", "-q", "origin", "dev")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hint = next(line for line in out["error"]["message"].splitlines() if line.startswith(SIZE + ":"))
        self.assertNotIn(FORMAT, hint)
        self.assertIn(f"dev removed these lines in {moved[:7]}", hint)
        self.assertIn("redo your change where it belongs now", hint)

    def test_two_files_taking_equally_close_lines_name_neither(self):  # review 3, 0
        self.on_dev(SIZE, SIZE_TEXT, "Sizes")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/tied")
        self.commit(tree, SIZE, SIZE_TEXT.replace("1048576", "1000000"))
        other = self.base / "other"
        moved_line = "  const megabytes = Math.round(bytes / 1024 / 1024);\n"
        write(other, FORMAT, "export function formatBytes(bytes) {\n" + moved_line + "}\n")
        write(other, RATE, "export function rate(bytes) {\n" + moved_line + "}\n")
        write(other, SIZE, SIZE_TEXT.replace("  " + BASE_LINE + "\n", ""))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "Two helpers take the sizes over")
        moved = git(other, "rev-parse", "--short=9", "HEAD").strip()
        git(other, "push", "-q", "origin", "dev")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hint = next(line for line in out["error"]["message"].splitlines() if line.startswith(SIZE + ":"))
        self.assertNotIn(FORMAT, hint)
        self.assertNotIn(RATE, hint)
        self.assertIn(f"dev removed these lines in {moved[:7]}", hint)
