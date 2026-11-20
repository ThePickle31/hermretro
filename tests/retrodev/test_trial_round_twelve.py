"""Friction the twelfth round of fresh-agent trials found outside `new`: check.py page (and so the scaffold check,
whose copy runs it) showed a failing page file only as node's 'test failed'; the lines `new` itself writes in
step-words.js and the page registry added the scaffold check, and a backend README the real-engine run; sync's
'neither side had' warning fired on a rewrapped merge of two edits; takeover wrote no pull request body; a body's
What changed could name a file the branch never touched. Each test failed before its fix. `new`'s side is in
test_trial_round_twelve_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_twelve
"""

import importlib.util
import io
from pathlib import Path

from retrodev import body_names, checks_triggers, config, output, repo, sync

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]


def check_py():
    spec = importlib.util.spec_from_file_location("check_py_round_twelve", ROOT / "tools" / "check.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACT = (
    "An update to BuildNewGame inside a test was not wrapped in act(...).\n\nWhen testing, code that causes React state "
    "updates should be wrapped into act(...):\n\nact(() => {\n  /* fire events that update state */\n});\n"
    "/* assert on the output */\n\nThis ensures that you're testing the behavior the user would see in the browser.\n"
)
# node --test --test-reporter=spec over two harness files (one failing) and a node:test file whose test timed out.
SPEC = (
    "page-build-shelf.test.mjs: 7 passed, 0 failed\n✔ tests/page/page-build-shelf.test.mjs (1319.8ms)\n"
    + ACT
    + "check failed: an approval seen both as an event and by the poll is one card\n"
    "AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:\n\n0 !== 1\n\n"
    "    at file:///x/tests/page/page-build.test.mjs:193:12\n"
    + ACT
    + "page-build.test.mjs: 13 passed, 1 failed\n✖ tests/page/page-build.test.mjs (2105.5ms)\n"
    "✔ clock() is minutes:seconds (0.7ms)\n✖ waits (201.2ms)\n  'test timed out after 200ms'\n"
    "ℹ tests 4\nℹ pass 2\nℹ fail 1\nℹ cancelled 1\n\n✖ failing tests:\n\n"
    "test at tests/page/page-build.test.mjs:1:1\n✖ tests/page/page-build.test.mjs (2105.5ms)\n  'test failed'\n\n"
    "test at tests/page/slow.test.mjs:1:31\n✖ waits (201.2ms)\n  'test timed out after 200ms'\n"
)


class PageFailure(RepoCase):
    def test_a_failing_page_file_shows_its_own_assertion_not_only_test_failed(self):
        said = check_py().page_failure(SPEC)
        self.assertIn("tests/page/page-build.test.mjs failed:", said)
        self.assertIn("check failed: an approval seen both as an event and by the poll is one card", said)
        self.assertIn("0 !== 1", said)
        self.assertIn("page-build.test.mjs: 13 passed, 1 failed", said)
        self.assertNotIn("not wrapped in act", said, "React's act() warnings are noise here")
        self.assertNotIn("page-build-shelf", said, "only the failing file's own output")
        fix = said.splitlines()[-1]
        self.assertTrue(fix.startswith("FIX: waits timed out (stopped for taking too long, not an assertion)"), fix)
        self.assertIn("node tests/page/page-build.test.mjs; node tests/page/slow.test.mjs", fix)

    def test_without_a_timeout_the_fix_says_nothing_of_one(self):
        spec = SPEC.replace("'test timed out after 200ms'", "'boom'")
        fix = check_py().page_failure(spec).splitlines()[-1]
        self.assertNotIn("timed out", fix)
        self.assertTrue(fix.startswith("FIX: run it alone: node tests/page/page-build.test.mjs"), fix)

    def test_the_scaffold_check_keeps_the_page_file_s_output_above_its_last_lines(self):
        module = check_py()
        block = module.page_failure(SPEC).replace("\n", "\n         ")
        stderr = "new tab rdtabs first:\n FAILED  page            3.8 s  " + block + "\n" + "more\n" * 60
        said = module.scaffold_said(stderr)
        self.assertIn("check failed: an approval seen both as an event and by the poll is one card", said)
        self.assertTrue(said.endswith("more"), "and the last lines still follow")


class Triggers(RepoCase):
    def triggered(self, files: dict[str, str]) -> dict[str, str]:
        self.made = getattr(self, "made", 0) + 1
        tree = self.worktree(f"feat/probe{self.made}")
        for name, text in files.items():
            write(tree, name, text)
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", "Probe")
        return checks_triggers.triggered(config.Context.make(tree, output.Out(stream=io.StringIO())))

    def on_base(self, name: str) -> str:
        text = (ROOT / name).read_text()
        self.on_dev(name, text, "The real file")
        git(self.main, "fetch", "-q", "origin")
        return text

    def test_the_step_words_entry_new_tool_writes_adds_no_scaffold_check(self):
        name = "page/pages/build/transcript/step-words.js"
        text = self.on_base(name)
        entry = "  rdprobe_ping: ['Pinging the probe', 'Pinged the probe'],\n"
        added = text.replace("  skill_view: ", entry + "  skill_view: ", 1)
        self.assertNotIn("scaffold", self.triggered({name: added}))

    def test_a_hand_edit_of_step_words_still_adds_it(self):
        name = "page/pages/build/transcript/step-words.js"
        text = self.on_base(name)
        changed = text.replace("const STEP_WORDS = {", "const STEP_WORDS = Object.freeze({", 1)
        self.assertIn("scaffold", self.triggered({name: changed}))

    def test_the_registry_line_new_page_writes_adds_no_scaffold_check(self):
        name = "page/pages/index.js"
        text = self.on_base(name)
        added = text.replace(
            "import { EMULATOR_PAGE } from './emulator/index.js'\n",
            "import { EMULATOR_PAGE } from './emulator/index.js'\nimport { RDPROBE_PAGE } from './rdprobe/index.js'\n",
        ).replace("EMULATOR_PAGE]", "EMULATOR_PAGE, RDPROBE_PAGE]")
        self.assertNotEqual(added, text)
        self.assertNotIn("scaffold", self.triggered({name: added}))
        self.assertIn("scaffold", self.triggered({name: added + "export const EXTRA = 1\n"}))

    def test_a_backend_readme_adds_no_acceptance_run_and_backend_code_does(self):
        found = self.triggered({"backend/library/README.md": "# Library\n\nMore words.\n"})
        self.assertNotIn("acceptance", found)
        self.assertIn("acceptance", self.triggered({"backend/library/core.py": "VALUE = 2\n"}))


PARAGRAPH = (
    '"""The page shows the games you made and the ones you\n'
    "downloaded, newest first, with a cover for each, and the\n"
    'last time you played each one."""\n'
)


class Sync(RepoCase):
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


class Takeover(RepoCase):
    def pushed(self, branch: str) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "docs/guide.md", "# Guide\n\nMore.\n")
        git(mate, "push", "-q", "origin", branch)

    def test_takeover_writes_the_body_from_the_template_and_names_its_absolute_path(self):
        self.pushed("docs/mate")
        code, out = self.run_cli("takeover", "docs/mate", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "mate.md"
        self.assertTrue(body.is_file(), out)
        self.assertIn("## What changed", body.read_text())
        self.assertIn(f"next: fill in {body} as you work", out)
        self.assertTrue(body.is_absolute())

    def test_a_branch_waiting_for_its_plan_gets_the_body_from_plan_approve(self):
        self.pushed("feat/mate")
        code, out = self.run_cli("takeover", "feat/mate", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "mate.md"
        self.assertFalse(body.exists(), "plan approve writes it, from the plan")
        self.assertIn(f"(it also writes the pull request body {body})", out)


class BodyPaths(RepoCase):
    def test_what_changed_naming_a_file_the_branch_did_not_touch_warns(self):
        tree = self.worktree("fix/core")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        text = GOOD_BODY.replace(
            "Things.", "`backend/library/core.py` and `core.py` change; `backend/hermes/glue.py` and `ship.py` too."
        )
        said = body_names.warning(ctx, text) or ""
        self.assertIn("names the file(s) `backend/hermes/glue.py`, `ship.py`, which the branch's diff does not", said)
        self.assertNotIn("`backend/library/core.py`", said)
        self.assertNotIn("`core.py`", said)
        self.assertIsNone(body_names.warning(ctx, GOOD_BODY.replace("Things.", "`backend/library/` changes.")))

    def test_a_renamed_file_counts_at_both_its_paths(self):  # review 1, 1
        self.on_dev("backend/library/old.py", "VALUE = 1\n" * 20)
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/rename")
        git(tree, "mv", "backend/library/old.py", "backend/library/new.py")
        git(tree, "commit", "-q", "-m", "Rename")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        self.assertEqual(repo.moved_or_deleted(tree, ctx.remote_base), ["backend/library/old.py"])
        text = GOOD_BODY.replace("Things.", "Renamed `backend/library/old.py` to `backend/library/new.py`.")
        self.assertIsNone(body_names.warning(ctx, text))


class RenamedTrigger(RepoCase):
    def test_moving_a_trigger_file_out_of_its_folder_still_triggers(self):  # review 1, 1
        self.on_dev("backend/library/moved.py", "VALUE = 1\n" * 20)
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("feat/move")
        git(tree, "mv", "backend/library/moved.py", "tools/moved.py")
        git(tree, "commit", "-q", "-m", "Move it out of backend/")
        found = checks_triggers.triggered(config.Context.make(tree, output.Out(stream=io.StringIO())))
        self.assertIn("acceptance", found, "a rename moving a trigger file away still changed it")
