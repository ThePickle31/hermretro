"""Friction the seventeenth round of fresh-agent trials found: takeover with RETRODEV_AGENT set printed a plan approve
step without it, so the later plan approve wrote 'Made by an agent (Hermes)'; sync's per-hunk hint searched dev's
history for the branch's own new line (never on dev) instead of the merge base's; `new rpc` took a name the page test
harness reserves on `scenario`; `new event` wrote a docstring past 120 columns; `new listener` and `new tool` steps;
the README had no rename section; the body warning flagged code paths a docs-only branch describes; the unit budget.
Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_seventeen
"""

import io
import unittest
from pathlib import Path

from retrodev import body_names, config, gates, output, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]
AGENT = "Hermes, claude-opus-5-5"


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


class TakeoverRecordsTheAgent(RepoCase):
    def test_plan_approve_without_the_variable_names_the_agent_takeover_saw(self):
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        self.fakes["env"] = {"RETRODEV_AGENT": AGENT}
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        approve = next(step for step in steps(out) if "plan approve" in step)
        self.assertIn(f"when they say start: RETRODEV_AGENT='{AGENT}' python tools/retrodev plan approve", approve)
        self.assertEqual(state.load_branch(self.main, "feat/mate")["agent"], AGENT)
        self.fakes["env"] = {}  # plan approve: a new process without the variable
        tree = self.base / "hermretro-wt" / "mate"
        self.new_plan("mate")
        code, out = self.run_cli("plan", "approve", "mate", "--words", "go ahead", cwd=tree)
        self.assertEqual(code, 0, out)
        body = (self.main / "notes" / "pr" / "mate.md").read_text()
        self.assertIn(f"Made by an agent ({AGENT})", body)
        self.assertNotIn("Made by an agent (Hermes)", body)

    def test_start_records_it_too_and_the_body_names_it(self):
        self.fakes["env"] = {"RETRODEV_AGENT": AGENT}
        code, out = self.run_cli("start", "docs/words", "--no-plan", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertEqual(state.load_branch(self.main, "docs/words")["agent"], AGENT)
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()), fakes={"env": {}})
        record = state.load_branch(self.main, "docs/words")
        self.assertIn(f"({AGENT})", gates.made_by(ctx, record=record))
        self.assertEqual(gates.agent_hint("Made by an agent (Hermes) for @x.", {}, record), "")


SIZE = "page/pages/games/size.js"
FORMAT = "page/shared/format.js"
BASE_LINE = "const megabytes = Math.round(bytes / 1048576);"
SIZE_TEXT = (
    'import { log } from "./log.js";\n\nexport function size(bytes) {\n  log("size");\n  '
    + BASE_LINE
    + '\n  log("done");\n  return label(megabytes);\n}\n'
)


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


RATE = "page/shared/rate.js"
SPEED_LINE = "const megabytes = Math.round(bytes / 1048576 / 8);"
TWO_TEXT = (
    SIZE_TEXT
    + '\nexport function speed(bytes) {\n  log("speed");\n  '
    + SPEED_LINE
    + '\n  log("rate");\n  return label(megabytes);\n}\n'
)


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


STEP = '  log("step");'
NEW_LINE = "const megabytes = Math.round(bytes / 1000000);"


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


class RealFiles(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")


class ReservedScenarioKeys(RealFiles):
    def test_new_rpc_refuses_ambient_a_null_key_the_harness_reads(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs", "backend/setup/*.py", "backend/setup/*.md")
        out = self.new("rpc", "setup", "ambient", "--dry-run", code=1)
        self.assertIn("reserves scenario.ambient", out["error"]["message"])
        from retrodev import scaffold, scaffold_rpc

        reserved = scaffold_rpc.reserved_scenario(scaffold.Plan(self.tree))
        self.assertIn("ambient", reserved)
        self.assertFalse({"status", "doctor", "activity"} & reserved, reserved)

    def test_new_rpc_refuses_a_key_the_page_harness_keeps_on_scenario(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs", "backend/setup/*.py", "backend/setup/*.md")
        for name in ("storage", "calls", "queries"):
            with self.subTest(name=name):
                out = self.new("rpc", "setup", name, "--dry-run", code=1)
                self.assertIn(f"reserves scenario.{name}", out["error"]["message"])
                self.assertIn("pick another RPC name", out["error"]["fix"])
        self.assertIn("disk_usage", self.new("rpc", "setup", "storage", "--dry-run", code=1)["error"]["fix"])
        self.new("rpc", "setup", "disk_usage", "--dry-run")

    def test_query_answers_are_not_reserved(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs")
        from retrodev import scaffold, scaffold_rpc

        plan = scaffold.Plan(self.tree)
        reserved = scaffold_rpc.reserved_scenario(plan)
        self.assertTrue({"storage", "calls", "queries", "queryData", "byMethod", "revealed", "lastParams"} <= reserved)
        self.assertFalse({"status", "doctor", "activity", "games", "player"} & reserved, reserved)


class LongEventDocstring(ScaffoldCase):
    def test_the_emits_docstring_wraps_at_120_columns(self):
        payload = "game=<the library id of the game whose build finished>, rom=<the built ROM's path>, ok=<bool>"
        self.new("event", "history", "rdprobe_build_finished_everywhere", "--payload", payload)
        emits = self.read("backend/history/emits.py")
        self.assertIn("Tell other features that history.rdprobe_build_finished_everywhere happened", emits)
        self.assertEqual([line for line in emits.splitlines() if len(line) > 120], [])
        compile(emits, "emits.py", "exec")


class ListenerLogs(ScaffoldCase):
    def test_the_listener_steps_say_how_to_assert_a_log(self):
        said = " ".join(self.new("listener", "history", "history.build_kept")["next"])
        self.assertIn('with self.assertLogs(listeners.host.logger, "<LEVEL>"):`, the level the listener logs at', said)
        self.assertIn("from ..hermes import host", said)
        self.assertIn("logger = logging.getLogger(__name__)", (ROOT / "backend/hermes/host.py").read_text())


class ToolSelectedGame(RealFiles):
    def test_one_line_says_tool_project_first_and_library_game_for_only_for_the_id(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        steps = self.new("tool", "library", "rdprobe_pick", "--project")["next"]
        about = [step for step in steps if "library_game_for" in step]
        self.assertEqual(len(about), 1, about)
        self.assertIn(
            "the selected game is this chat's project (or the `project` argument): tool_project, as the stub does; "
            "call host.library_game_for([root]) -> (game id, root) or None (from ..hermes import host) only when you "
            "need the game's library id or entry (e.g. the id player.list_captures(root, game_id) takes)",
            about[0],
        )
        self.assertIn("def list_captures(root: Path, identifier: str)", (ROOT / "backend/player/server.py").read_text())


class RenameSection(unittest.TestCase):
    def test_the_readme_says_how_to_rename_a_module(self):
        section = retrodev_docs("README.md").split("### Rename or move a module")[1].split("\n## ")[0]
        for said in ("git grep -n <old>", "tests/retrodev", "tools/retrodev/", "docs/", "shadow", "check.py fix"):
            self.assertIn(said, section)
        self.assertLessEqual(len(section.strip().splitlines()), 7)


class DocsOnlyBody(RepoCase):
    def warning(self, tree, what: str) -> str:
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_a_docs_branch_describes_code_without_a_warning_and_others_still_warn(self):
        said = "- Explained how `tools/retrodev/sync.py` hints and where `backend/library/` keeps games."
        docs = self.worktree("docs/guide")
        self.commit(docs, "docs/dev/DEBUGGING.md", "# Debugging\n")
        self.commit(docs, "backend/library/README.md", "# Library\n")
        self.assertEqual(self.warning(docs, said), "")
        self.assertIn("`docs/dev/TESTING.md`", self.warning(docs, said + " Changed `docs/dev/TESTING.md`."))
        reference = self.worktree("docs/reference")  # review 3, 1: the CLI's own reference is documentation too
        self.commit(reference, "tools/retrodev/REFERENCE.md", "# Reference\n")
        self.assertEqual(self.warning(reference, said), "")
        code = self.worktree("fix/code")
        self.commit(code, "docs/dev/DEBUGGING.md", "# Debugging\n")
        self.commit(code, "tools/kept.py", "VALUE = 1\n")
        self.assertIn("`tools/retrodev/sync.py`", self.warning(code, said))


if __name__ == "__main__":
    unittest.main()
