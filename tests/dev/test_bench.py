"""tools/dev/bench.py: the report counts from a fixture state.db and errors.log what Hermes's own session columns get
wrong, each message once however many compactions copied it, and finds each game's session (`run` itself:
test_bench_run.py)."""

import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

TOP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOP / "tools" / "dev"))

import bench  # noqa: E402 - tools/dev, put on the path just above (a dataclass needs its module importable)

SESSION = "local-aaaa"
RESTORE = json.dumps({"action": "restore"})
PROMPT = "Make a new Game Boy Color game called \"Test\".\n"
# The columns of Hermes's state.db the report reads.
SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT,
    api_call_count INTEGER DEFAULT 0, estimated_cost_usd REAL);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT, tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL NOT NULL, finish_reason TEXT,
    _compressed_summary INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
    compacted INTEGER NOT NULL DEFAULT 0, message_uid TEXT, tool_call_uid TEXT);
CREATE TABLE session_model_usage (session_id TEXT NOT NULL, task TEXT NOT NULL DEFAULT '',
    api_call_count INTEGER NOT NULL DEFAULT 0, estimated_cost_usd REAL NOT NULL DEFAULT 0);
"""


def call(name: str, arguments: dict) -> dict:
    return {"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


class Fixture(unittest.TestCase):
    """A profile home with a state.db and logs/errors.log, in a temp folder (never the real Hermes home)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve() / "profile"
        (self.home / "logs").mkdir(parents=True)
        (self.home / "logs" / "errors.log").write_text("", encoding="utf-8")
        self.db = sqlite3.connect(self.home / "state.db")
        self.addCleanup(self.db.close)
        self.db.executescript(SCHEMA)
        self.clock = 1000.0

    def session(self, session=SESSION, started=1000.0, ended=None, reason=None, calls=0, cost=None):
        self.db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)", (session, started, ended, reason, calls, cost)
        )
        self.db.commit()

    def message(self, role, session=SESSION, **columns):
        self.clock += 1
        columns = {"session_id": session, "role": role, "timestamp": self.clock, **columns}
        self.db.execute(
            f"INSERT INTO messages ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
            tuple(columns.values()),
        )
        self.db.commit()

    def tool(self, name, result, **columns):
        self.message("tool", tool_name=name, content=json.dumps(result), **columns)


class ReportTest(Fixture):
    def setUp(self):
        super().setUp()
        self.session(ended=1125.0, reason="cli_close", calls=7, cost=1.0)
        self.db.executemany(
            "INSERT INTO session_model_usage VALUES (?, ?, ?, ?)",
            [(SESSION, "", 7, 1.0), (SESSION, "compression", 2, 0.25)],
        )
        self.message("user", content=PROMPT, active=0, compacted=1)
        source = {"command": "grep -n EVENT_TEXT ~/.cache/toolchain/vendor/gb-studio/src/lib/events/eventText.js"}
        self.message(
            "assistant",
            active=0,
            compacted=1,
            tool_calls=json.dumps(
                [
                    call("terminal", source),
                    call("read_file", {"path": "games/Test/project/scenes/title.gbsres"}),
                    call("read_file", {"path": "engine/modretro-chromatic/dist/server.js"}),
                    call("chromatic_emulator_checkpoint", {"action": "save", "label": "start"}),
                    call(
                        "tool_call",
                        {"calls": [{"name": "chromatic_emulator_checkpoint", "arguments": {"action": "restore"}}]},
                    ),
                    # Hermes takes the envelope's calls and their arguments as JSON text too.
                    call(
                        "tool_call",
                        {"calls": json.dumps([{"name": "chromatic_emulator_checkpoint", "arguments": RESTORE}])},
                    ),
                    call("tool_call", {"calls": [None, "text", {"name": "terminal", "arguments": "not json"}]}),
                    {"function": None},
                    None,
                ]
            ),
        )
        # Results from before a compaction (inactive) count too: the session's own column leaves them out.
        self.tool("chromatic_emulator_step", {"result": "Completed"}, active=0, compacted=1)
        self.tool("terminal", {"output": "", "exit_code": 0, "error": None}, active=0)
        self.tool("terminal", {"output": "", "exit_code": -1, "error": "BLOCKED: script execution"})
        self.tool("chromatic_rom_build", {"result": "Completed"})
        self.tool("chromatic_rom_build", {"isError": True, "error": "compile failed", "code": "BUILD_FAILED"})
        # A compiler failure: no error flag, only its structured content's `success: false`.
        failed = {"result": "Operation failed (exit 1; diagnostics: 5).", "structuredContent": {"success": False}}
        self.tool("chromatic_rom_build", failed)
        self.tool(
            "chromatic_scene_apply",
            {"isError": True, "error": "Operation 0 failed", "structuredContent": {"code": "INVALID_EVENT"}},
        )
        self.message("tool", tool_name="chromatic_emulator_step", content="[tool_call] pruned: full result at ...")
        self.message("user", content="[CONTEXT COMPACTION] summary", _compressed_summary=1)
        self.message("assistant", content="The game is finished.", finish_reason="stop")
        (self.home / "logs" / "errors.log").write_text(
            f"2026-11-24 21:13:05,282 WARNING [{SESSION}] run_agent: Removed duplicate tool call: tool_call\n"
            f"2026-11-24 21:13:05,283 WARNING [{SESSION}] run_agent: Removed duplicate tool call: tool_call\n"
            "2026-11-24 21:13:06,000 WARNING [local-other] run_agent: Removed duplicate tool call: tool_call\n"
            f"2026-11-24 21:13:07,000 ERROR [{SESSION}] run_agent: something else\n",
            encoding="utf-8",
        )
        (self.home / "logs" / "errors.log.1").write_text(
            f"2026-11-24 20:00:00,000 WARNING [{SESSION}] run_agent: Removed duplicate tool call: terminal\n",
            encoding="utf-8",
        )

    def test_counts_what_the_session_did(self):
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertEqual(found.wall, 125.0)
        self.assertFalse(found.running)
        self.assertEqual(found.cost, 1.25)
        self.assertEqual((found.model_calls, found.auxiliary_calls), (9, 2))
        self.assertEqual(found.tool_calls, 8)
        self.assertEqual((found.builds, found.failed_builds), (3, 2))
        self.assertEqual(found.compactions, 1)
        self.assertEqual(found.duplicate_drops, 3)
        self.assertEqual((found.source_commands, found.source_reads), (1, 1))
        self.assertEqual(found.restores, 2)
        self.assertEqual(found.ended, "yes")
        self.assertEqual(
            found.errors,
            Counter(
                {"terminal (no code)": 1, "BUILD_FAILED": 1, "chromatic_rom_build (no code)": 1, "INVALID_EVENT": 1}
            ),
        )

    def test_table_has_a_column_per_game_and_each_games_errors(self):
        text = bench.table(bench.reports(self.home, ids=[SESSION]))
        lines = text.splitlines()
        self.assertEqual(lines[0].split(), [SESSION[:14]])
        self.assertIn("model calls          9 (2 auxiliary)", text)
        self.assertIn("builds               3 (2 failed)", text)
        self.assertIn("tool errors          4", text)
        self.assertIn("ended normally       yes", text)
        self.assertIn(f"{SESSION[:14]}: {SESSION}", text)
        self.assertIn("  BUILD_FAILED x1", text)

    def test_the_session_is_only_read(self):
        before = (self.home / "state.db").read_bytes()
        bench.reports(self.home, ids=[SESSION])
        self.assertEqual((self.home / "state.db").read_bytes(), before)


class CompactionCopiesTest(Fixture):
    """A compaction stores copies of the messages before it (same `message_uid`, `compacted` 1, a tool result's
    copy Hermes's summary of it); every count takes each message once."""

    def test_copies_count_once(self):
        self.session(ended=1100.0, reason="cli_close")
        stepping = [call("chromatic_emulator_step", {"buttons": ["a"]}), call("chromatic_rom_build", {})]
        restoring = [
            call("chromatic_emulator_checkpoint", {"action": "restore"}),
            call("terminal", {"command": "cat vendor/gb-studio/src/lib/compiler/compileData.ts"}),
        ]
        failed = {"isError": True, "error": "compile failed", "code": "BUILD_FAILED"}
        for copy in range(3):  # the originals, then two compactions' copies
            stored = {"active": 0, "compacted": int(copy > 0)}
            self.message("user", content=PROMPT, message_uid="u-prompt", **stored)
            self.message("assistant", tool_calls=json.dumps(stepping), message_uid="u-a1", **stored)
            self.tool("chromatic_emulator_step", {"result": "Completed"}, tool_call_id="c1", message_uid="u-t1")
            if copy == 0:
                self.tool("chromatic_rom_build", failed, tool_call_id="c2", message_uid="u-t2", **stored)
            else:  # Hermes's summary of the call, longer than the result it stands for
                summary = f"[chromatic_rom_build] calls={'x' * 200} (61 chars result) FAILED: compile failed"
                self.message("tool", tool_name="chromatic_rom_build", content=summary, tool_call_id="c2", **stored)
            self.message("assistant", tool_calls=json.dumps(restoring), message_uid="u-a2", **stored)
            self.tool("chromatic_emulator_checkpoint", {"result": "Restored"}, tool_call_id="c3", **stored)
            self.tool("terminal", {"output": ""}, tool_call_id="c4", message_uid=f"u-t4-{copy}", **stored)
            if copy:
                self.message("user", content="[CONTEXT COMPACTION] summary", _compressed_summary=1, message_uid="u-s")
        self.message("assistant", content="Done.", finish_reason="stop", message_uid="u-end")
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertEqual(found.tool_calls, 4)
        self.assertEqual(found.steps, 1)
        self.assertEqual((found.builds, found.failed_builds), (1, 1))  # the original's result, not the summary's
        self.assertEqual(found.errors, Counter({"BUILD_FAILED": 1}))
        self.assertEqual((found.restores, found.source_commands), (1, 1))
        self.assertEqual(found.compactions, 1)
        self.assertEqual(found.ended, "yes")


class PrunedAndReusedTest(Fixture):
    """A prune keeps a stub in the original row and puts the full message in a later one; a provider can reuse a
    tool call id later, each occurrence with its own `tool_call_uid`."""

    def setUp(self):
        super().setUp()
        self.session(ended=1100.0, reason="cli_close")

    def test_the_full_result_counts_wherever_it_sits(self):
        build = [call("chromatic_rom_build", {})]
        self.message("assistant", tool_calls=json.dumps(build), message_uid="u-a1")
        failed = {"isError": True, "error": "compile failed", "code": "BUILD_FAILED"}
        # The stub at the original row, the full result in the prune's later row.
        stub = "[chromatic_rom_build] pruned: full result at ..."
        self.message("tool", tool_name="chromatic_rom_build", content=stub, tool_call_id="c1", message_uid="u-t1")
        self.tool("chromatic_rom_build", failed, tool_call_id="c1", message_uid="u-t1", active=0, compacted=1)
        # Arguments cut to a stub too: the call with its arguments counts.
        restore = [call("chromatic_emulator_checkpoint", {"action": "restore", "label": "start"})]
        stub = [call("chromatic_emulator_checkpoint", {})]
        self.message("assistant", tool_calls=json.dumps(stub), message_uid="u-a2")
        self.message("assistant", tool_calls=json.dumps(restore), message_uid="u-a2", active=0, compacted=1)
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertEqual((found.tool_calls, found.builds, found.failed_builds), (1, 1, 1))
        self.assertEqual(found.errors, Counter({"BUILD_FAILED": 1}))
        self.assertEqual(found.restores, 1)

    def test_a_reused_call_id_counts_each_occurrence(self):
        for occurrence in ("uid-1", "uid-2"):
            for copy in range(2):  # each occurrence and a compaction's copy of it
                self.message(
                    "tool",
                    tool_name="chromatic_emulator_step",
                    content='{"result": "Completed"}' if copy == 0 else "[chromatic_emulator_step] (23 chars)",
                    tool_call_id="call_0",
                    tool_call_uid=occurrence,
                    compacted=copy,
                )
        self.assertEqual(bench.reports(self.home, ids=[SESSION])[SESSION[:14]].tool_calls, 2)

    def test_a_database_without_occurrence_ids_groups_on_the_call_id(self):
        self.db.execute("ALTER TABLE messages DROP COLUMN tool_call_uid")
        self.tool("chromatic_emulator_step", {"result": "Completed"}, tool_call_id="c1")
        self.message("tool", tool_name="chromatic_emulator_step", content="[cut]", tool_call_id="c1", compacted=1)
        self.assertEqual(bench.reports(self.home, ids=[SESSION])[SESSION[:14]].tool_calls, 1)


class EndingTest(Fixture):
    def test_a_session_still_open_runs_until_its_last_message(self):
        self.session()
        self.message("user", content=PROMPT)
        self.message("assistant", tool_calls="[]", finish_reason="tool_calls")
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertTrue(found.running)
        self.assertEqual(found.wall, 2.0)
        self.assertEqual(found.ended, "no (still open)")
        self.assertEqual(bench.ROWS[0][1](found), "0m02s (running)")

    def test_a_session_its_stopped_chat_left_open_ends_when_the_chat_exited(self):
        self.session()
        self.message("assistant", tool_calls="[]", finish_reason="tool_calls")
        with bench.closing(bench.connect(self.home / "state.db")) as db:
            found = bench.report(db, SESSION, Counter(), exited=1090.0)
        self.assertFalse(found.running)
        self.assertEqual(found.wall, 90.0)
        self.assertEqual(found.ended, "no (chat exited, session left open)")

    def test_a_reaped_session_without_an_answer_is_not_a_normal_end(self):
        self.session(ended=1600.0, reason="startup_orphan_reap", calls=7, cost=2.5)
        self.message("assistant", tool_calls="[]", finish_reason="tool_calls")
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertEqual(found.ended, "no (startup_orphan_reap, no final answer)")
        self.assertEqual((found.cost, found.model_calls), (2.5, 7))  # no usage rows: the session's own columns

    def test_an_unknown_session(self):
        self.assertEqual(bench.reports(self.home, ids=["local-missing"])["local-missing"].ended, "no such session")


class RunSessionsTest(Fixture):
    def test_each_game_finds_its_session(self):
        folder = self.home / "run"
        folder.mkdir()
        (folder / "2-printed.log").write_text("The game is done.\n\nsession_id: local-printed\n", encoding="utf-8")
        (folder / "3-stopped.log").write_text("Traceback ...\n", encoding="utf-8")
        record = {
            "started": 2000.0,
            "games": {
                "1-recorded": {"prompt": "one", "log": "1-recorded.log", "session": "local-recorded"},
                "2-printed": {"prompt": "two", "log": "2-printed.log", "session": None, "ended": 2400.0},
                "3-stopped": {"prompt": PROMPT, "log": "3-stopped.log", "session": None, "ended": 2500.0},
                "4-never": {"prompt": "four", "log": "4-never.log", "session": None},
            },
        }
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        # The same prompt in a session from before the chat started, or after it exited, is not this run's.
        for session, started in (("local-earlier", 1000.0), ("local-stopped", 2100.0), ("local-later", 3000.0)):
            self.session(session, started=started)
            self.message("user", session=session, content=PROMPT.strip())
        self.message("user", session="local-stopped", content="a later turn")
        with bench.closing(bench.connect(self.home / "state.db")) as db:
            sessions = bench.run_sessions(folder, db)
        self.assertEqual(
            sessions,
            {
                "1-recorded": bench.Game("local-recorded"),
                "2-printed": bench.Game("local-printed", 2400.0),
                "3-stopped": bench.Game("local-stopped", 2500.0),
                "4-never": bench.Game(None),
            },
        )
        reports = bench.reports(self.home, folder)
        self.assertEqual(reports["4-never"].ended, "no session")
        self.assertEqual(reports["3-stopped"].wall, 400.0)  # to the chat's exit: its session was left open

    def test_two_sessions_with_the_prompt_leave_the_game_unresolved(self):
        folder = self.home / "run"
        folder.mkdir()
        # A stopped run (no exit recorded) and a later run of the same game: neither session is surely this one's.
        record = {"started": 2000.0, "games": {"1-test": {"prompt": PROMPT, "log": "1-test.log", "session": None}}}
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        for session, started in (("local-this", 2100.0), ("local-next", 5000.0)):
            self.session(session, started=started)
            self.message("user", session=session, content=PROMPT)
        with bench.closing(bench.connect(self.home / "state.db")) as db:
            self.assertEqual(bench.run_sessions(folder, db), {"1-test": bench.Game(None)})

    def test_the_newest_run_and_no_run(self):
        runs = self.home / "runs"
        with self.assertRaises(bench.BenchError):
            bench.latest_run(runs)
        for name in ("20261124-204700", "20261125-090000", "20261126-000000"):
            (runs / name).mkdir(parents=True)
        for name in ("20261124-204700", "20261125-090000"):
            (runs / name / "run.json").write_text("{}", encoding="utf-8")
        self.assertEqual(bench.latest_run(runs).name, "20261125-090000")


class CommandTest(Fixture):
    """`python tools/dev bench report` against a profile home of its own."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("dev_cli", TOP / "tools" / "dev" / "__main__.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        root = self.home.parent / "hermes"
        (root / "profiles").mkdir(parents=True)
        (root / "profiles" / "hermretro").symlink_to(self.home)
        patcher = mock.patch.object(self.cli.hermes, "hermes_root", return_value=root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_of_a_run_folder(self):
        self.session(ended=1060.0, reason="cli_close")
        self.message("assistant", content="Done.", finish_reason="stop")
        folder = self.home.parent / "run"
        folder.mkdir()
        record = {"started": 0, "games": {"1-test": {"prompt": PROMPT, "log": "1-test.log", "session": SESSION}}}
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(self.cli.main(["bench", "report", "--run", str(folder)]), 0)
        self.assertIn("wall time            1m00s", output.getvalue())

    def test_run_takes_no_report_flags_and_report_no_games(self):
        for argv in (
            ["bench", "run", "--run", str(self.home)],
            ["bench", "run", "--sessions", SESSION],
            ["bench", "report", "bolt"],
        ):
            error = io.StringIO()
            with mock.patch.object(self.cli.bench, "run") as run, redirect_stderr(error):
                self.assertEqual(self.cli.main(argv), 1)
            run.assert_not_called()
            self.assertIn("bench report", error.getvalue())

    def test_a_failed_report_after_a_run_keeps_the_run(self):
        folder = self.home.parent / "run"
        folder.mkdir()
        error = io.StringIO()
        with (
            mock.patch.object(self.cli.shutil, "which", return_value="/bin/hermes"),
            mock.patch.object(self.cli.bench, "current_gateway"),
            mock.patch.object(self.cli.bench, "run", return_value=folder),
            mock.patch.object(self.cli.bench, "reports", side_effect=sqlite3.OperationalError("no such column")),
            redirect_stderr(error),
        ):
            self.assertEqual(self.cli.main(["bench", "run"]), 1)
        self.assertIn(f"no such column; the run is kept in {folder}", error.getvalue())

    def test_a_folder_that_is_not_a_run(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(self.cli.main(["bench", "report", "--run", str(self.home)]), 1)
        self.assertIn("is not a run folder", error.getvalue())


class GamesTest(unittest.TestCase):
    def test_the_committed_games(self):
        prompts = bench.games([])
        self.assertEqual(
            [prompt.stem for prompt in prompts], ["1-lantern", "2-bolt", "3-starling", "4-burrow", "5-tidepool"]
        )
        for prompt in prompts:
            self.assertIn("Make a new Game Boy Color game", prompt.read_text(encoding="utf-8"))

    def test_choosing_games_by_name(self):
        self.assertEqual([prompt.stem for prompt in bench.games(["bolt", "tide"])], ["2-bolt", "5-tidepool"])
        with self.assertRaises(bench.BenchError):
            bench.games(["nothing"])


if __name__ == "__main__":
    unittest.main()
