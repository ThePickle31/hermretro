"""tools/dev/bench.py: the benchmark starts each game's one-shot chat with the right command and records its session,
and the report counts from a fixture state.db and errors.log what Hermes's own session columns get wrong."""

import importlib.util
import io
import json
import os
import shutil
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
PROMPT = "Make a new Game Boy Color game called \"Test\".\n"
# The columns of Hermes's state.db the report reads.
SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT,
    api_call_count INTEGER DEFAULT 0, estimated_cost_usd REAL);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL NOT NULL, finish_reason TEXT,
    _compressed_summary INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
    compacted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE session_model_usage (session_id TEXT NOT NULL, task TEXT NOT NULL DEFAULT '',
    estimated_cost_usd REAL NOT NULL DEFAULT 0);
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
            "INSERT INTO session_model_usage VALUES (?, ?, ?)", [(SESSION, "", 1.0), (SESSION, "compression", 0.25)]
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
                ]
            ),
        )
        # Results from before a compaction (inactive) count too: the session's own column leaves them out.
        self.tool("chromatic_emulator_step", {"result": "Completed"}, active=0, compacted=1)
        self.tool("terminal", {"output": "", "exit_code": 0, "error": None}, active=0)
        self.tool("terminal", {"output": "", "exit_code": -1, "error": "BLOCKED: script execution"})
        self.tool("chromatic_rom_build", {"result": "Completed"})
        self.tool("chromatic_rom_build", {"isError": True, "error": "compile failed", "code": "BUILD_FAILED"})
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
        self.assertEqual(found.model_calls, 7)
        self.assertEqual(found.tool_calls, 7)
        self.assertEqual((found.builds, found.failed_builds), (2, 1))
        self.assertEqual(found.compactions, 1)
        self.assertEqual(found.duplicate_drops, 3)
        self.assertEqual(found.source_reads, 2)
        self.assertEqual(found.restores, 1)
        self.assertEqual(found.ended, "yes")
        self.assertEqual(found.errors, Counter({"terminal (no code)": 1, "BUILD_FAILED": 1, "INVALID_EVENT": 1}))

    def test_table_has_a_column_per_game_and_each_games_errors(self):
        text = bench.table(bench.reports(self.home, ids=[SESSION]))
        lines = text.splitlines()
        self.assertEqual(lines[0].split(), [SESSION[:14]])
        self.assertIn("builds               2 (1 failed)", text)
        self.assertIn("ended normally       yes", text)
        self.assertIn(f"{SESSION[:14]}: {SESSION}", text)
        self.assertIn("  BUILD_FAILED x1", text)

    def test_the_session_is_only_read(self):
        before = (self.home / "state.db").read_bytes()
        bench.reports(self.home, ids=[SESSION])
        self.assertEqual((self.home / "state.db").read_bytes(), before)


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

    def test_a_reaped_session_without_an_answer_is_not_a_normal_end(self):
        self.session(ended=1600.0, reason="startup_orphan_reap", cost=2.5)
        self.message("assistant", tool_calls="[]", finish_reason="tool_calls")
        found = bench.reports(self.home, ids=[SESSION])[SESSION[:14]]
        self.assertEqual(found.ended, "no (startup_orphan_reap, no final answer)")
        self.assertEqual(found.cost, 2.5)  # no usage rows: the session's own estimate

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
                "2-printed": {"prompt": "two", "log": "2-printed.log", "session": None},
                "3-stopped": {"prompt": PROMPT, "log": "3-stopped.log", "session": None},
                "4-never": {"prompt": "four", "log": "4-never.log", "session": None},
            },
        }
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        # The same prompt in a session from before the run is not this run's.
        self.session("local-earlier", started=1000.0)
        self.message("user", session="local-earlier", content=PROMPT)
        self.session("local-stopped", started=2100.0)
        self.message("user", session="local-stopped", content=PROMPT.strip())
        self.message("user", session="local-stopped", content="a later turn")
        with bench.closing(bench.connect(self.home / "state.db")) as db:
            sessions = bench.run_sessions(folder, db)
        self.assertEqual(
            sessions,
            {
                "1-recorded": "local-recorded",
                "2-printed": "local-printed",
                "3-stopped": "local-stopped",
                "4-never": None,
            },
        )
        reports = bench.reports(self.home, folder)
        self.assertEqual(reports["4-never"].ended, "no session")

    def test_the_newest_run_and_no_run(self):
        runs = self.home / "runs"
        with self.assertRaises(bench.BenchError):
            bench.latest_run(runs)
        for name in ("20261124-204700", "20261125-090000", "20261126-000000"):
            (runs / name).mkdir(parents=True)
        for name in ("20261124-204700", "20261125-090000"):
            (runs / name / "run.json").write_text("{}", encoding="utf-8")
        self.assertEqual(bench.latest_run(runs).name, "20261125-090000")


class RunTest(unittest.TestCase):
    """`run` with a stand-in `hermes` on PATH that prints its arguments and a session id, as a quiet chat does."""

    def setUp(self):
        folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.folder = folder
        bin_ = folder / "bin"
        bin_.mkdir()
        hermes = bin_ / "hermes"
        hermes.write_text(
            '#!/bin/sh\necho "$@"\npwd\nprompt="$5"\nname=$(basename "$prompt" .txt)\n'
            'if [ "$name" = "2-fails" ]; then echo boom >&2; exit 3; fi\n'
            'echo "Done."\necho\necho "session_id: local-$name"\n',
            encoding="utf-8",
        )
        hermes.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prompts = []
        for name in ("1-works", "2-fails"):
            prompt = folder / f"{name}.txt"
            prompt.write_text(f"Make {name}.\n", encoding="utf-8")
            self.prompts.append(prompt)

    def test_runs_every_game_at_once_and_records_each_session(self):
        with mock.patch("sys.stdout"):
            folder = bench.run(self.prompts, "hermretro", self.folder / "runs", None)
        record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        works, fails = record["games"]["1-works"], record["games"]["2-fails"]
        self.assertEqual((works["exit"], works["session"]), (0, "local-1-works"))
        self.assertEqual((fails["exit"], fails["session"]), (3, None))
        self.assertEqual(works["prompt"], "Make 1-works.\n")
        self.assertIsNotNone(works["ended"])
        log = (folder / "1-works.log").read_text(encoding="utf-8").splitlines()
        prompt = self.prompts[0]
        self.assertEqual(log[0], f"-p hermretro chat --query-file {prompt} --oneshot -Q --reasoning high")
        self.assertEqual(Path(log[1]).resolve(), folder)  # each chat starts in the run folder
        self.assertIn("boom", (folder / "2-fails.log").read_text(encoding="utf-8"))


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
