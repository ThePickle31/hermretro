"""tools/debug/broker_stats.py: reads a running broker's stats, and never starts one or writes anything."""

import contextlib
import importlib.util
import io
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.test_broker_fingerprint import Running  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

TOOL = ROOT / "tools" / "debug" / "broker_stats.py"
_spec = importlib.util.spec_from_file_location("broker_stats", TOOL)  # a script, not a package module
assert _spec and _spec.loader
broker_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker_stats)
POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"


def tree(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))


@unittest.skipUnless(POSIX, "Linux and macOS only")
class NoBroker(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.runtime = self.home.runtime / "run"  # not there yet: the tool must not make it

    def test_exits_2_without_starting_a_broker_or_writing(self):
        env = {**os.environ, "HERMRETRO_RUNTIME_DIR": str(self.runtime), "HOME": str(self.home.base)}
        env["TMPDIR"] = str(self.home.base)
        before = tree(self.home.base), tree(self.home.runtime)
        done = subprocess.run(
            [sys.executable, str(TOOL)], capture_output=True, text=True, env=env, cwd=self.home.base, timeout=60
        )
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("No hermretro broker is running", done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertFalse(self.runtime.exists(), "the tool created the run folder")
        self.assertEqual((tree(self.home.base), tree(self.home.runtime)), before, "the tool wrote files")

    def test_never_spawns_even_with_a_stale_socket_file(self):
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "broker.sock").write_text("")  # left by a broker that died
        with (
            mock.patch.dict(os.environ, {"HERMRETRO_RUNTIME_DIR": str(self.runtime)}),
            mock.patch.object(client, "spawn_broker", side_effect=AssertionError("started a broker")),
            mock.patch.object(client, "ensure_broker", side_effect=AssertionError("started a broker")),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(broker_stats.main([]), 2)
        self.assertIn("No hermretro broker answers", err.getvalue())
        self.assertEqual(tree(self.runtime), ["broker.sock"])


@unittest.skipUnless(POSIX, "Linux and macOS only")
class WithBroker(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        for patch in (
            mock.patch.object(paths, "verify_engine", lambda: {"verified": True}),
            mock.patch.object(paths, "find_node", lambda: {"ok": True, "path": "node"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.running = Running(self.home.runtime)
        self.addCleanup(self.running.close)

    def test_prints_stats_and_activity_as_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(broker_stats.main(["--activity", "hermretro", "chat-1"]), 0)
        report = json.loads(out.getvalue())
        self.assertTrue(report["stats"]["ok"])
        self.assertEqual(report["stats"]["pid"], os.getpid())
        self.assertEqual(report["hello"]["broker_generation"], self.running.broker.generation)
        self.assertEqual(report["activity"], {"ok": True, "lane": None, "matched": None})
        self.assertEqual(report["engine_processes"], {})
        self.assertFalse(self.running.broker.stopping.is_set(), "a read-only tool stopped the broker")


@unittest.skipUnless(POSIX, "Linux and macOS only")
class SilentBroker(unittest.TestCase):
    """A broker that accepts but never answers must not hold the tool: it exits 3 within --timeout."""

    TIMEOUT = 0.5

    def setUp(self):
        self.home = isolated_home(self)

    def run_tool(self) -> tuple[int, str, float]:
        err = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = broker_stats.main(["--timeout", str(self.TIMEOUT)])
        return code, err.getvalue(), time.monotonic() - started

    def test_a_listener_that_never_answers_hello_exits_3(self):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(str(self.home.runtime / "broker.sock"))
        listener.listen(1)
        (self.home.runtime / "broker.token").write_text("token")
        held: list[socket.socket] = []
        self.addCleanup(lambda: [peer.close() for peer in held])
        threading.Thread(target=lambda: held.append(listener.accept()[0]), daemon=True).start()
        code, err, took = self.run_tool()
        self.assertEqual(code, broker_stats.NOT_ANSWERING, err)
        self.assertIn("accepted but did not answer hello within 0.5 s", err)
        self.assertIn(str(self.home.runtime / "broker.sock"), err)
        self.assertLess(took, 5)

    def test_a_broker_that_never_answers_stats_exits_3(self):
        for patch in (
            mock.patch.object(paths, "verify_engine", lambda: {"verified": True}),
            mock.patch.object(paths, "find_node", lambda: {"ok": True, "path": "node"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        running = Running(self.home.runtime)  # the real socket server and framing: hello is answered
        self.addCleanup(running.close)
        release = threading.Event()
        self.addCleanup(release.set)  # runs before running.close: the stuck handler thread ends
        real_control = running.broker.control

        def stuck(request):
            if request.get("op") == "stats":
                release.wait(30)
            return real_control(request)

        running.broker.control = stuck
        code, err, took = self.run_tool()
        self.assertEqual(code, broker_stats.NOT_ANSWERING, err)
        self.assertIn("did not answer stats within 0.5 s", err)
        self.assertLess(took, 5)

    def test_a_broker_that_closes_mid_handshake_exits_3(self):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(str(self.home.runtime / "broker.sock"))
        listener.listen(1)
        (self.home.runtime / "broker.token").write_text("token")

        def hang_up():
            peer, _ = listener.accept()
            peer.makefile("rb").readline()
            peer.close()

        threading.Thread(target=hang_up, daemon=True).start()
        code, err, _ = self.run_tool()
        self.assertEqual(code, broker_stats.NOT_ANSWERING, err)
        self.assertIn("closed the connection before answering hello", err)


class ProcessTree(unittest.TestCase):
    # The worker (101) and, under it, a compiler that started its own session (group 205) and that one's child.
    PS = """  101     50   101    01:02 node /x/engine/launcher.mjs
  205    101   205       05 make -C /x/game
  206    205   205       03 /x/rgbds/rgbasm -o out.o main.asm
  102    101   101       04 node helper.mjs
  103      1   900 1-02:03:04 bash
  bad line
"""

    def test_walks_every_descendant_across_process_groups(self):
        found = broker_stats.descendants(101, broker_stats.process_table(self.PS))
        self.assertEqual(sorted(m["pid"] for m in found), [101, 102, 205, 206])
        self.assertEqual(found[0]["pid"], 101, "the worker comes first")
        by_pid = {m["pid"]: m for m in found}
        self.assertEqual(by_pid[205]["pgid"], 205)
        self.assertEqual(by_pid[206]["command"], "/x/rgbds/rgbasm -o out.o main.asm")
        self.assertEqual(by_pid[206]["ppid"], 205)
        self.assertEqual(by_pid[101]["etime"], "01:02")

    def test_ps_failure_is_reported(self):
        self.assertEqual(broker_stats.descendants(101, "ps failed: no ps"), [{"error": "ps failed: no ps"}])

    def test_report_lists_compiler_of_a_live_worker(self):
        connection = mock.Mock(state_dir=Path("/run"), hello={"ok": True})
        connection.ask.return_value = {"ok": True, "lanes": [{"engine_pid": 101, "alive": True}, {"engine_pid": 7}]}
        report = broker_stats.collect(connection, None, self.PS)
        self.assertEqual(list(report["engine_processes"]), ["101"])
        self.assertIn(205, [m["pid"] for m in report["engine_processes"]["101"]])

    @unittest.skipUnless(POSIX, "Linux and macOS only")
    def test_real_ps_finds_a_child_in_its_own_session(self):
        parent = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)\n"
                "print(child.pid, flush=True)\n"
                "time.sleep(60)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(parent.wait, 10)
        self.addCleanup(parent.kill)
        self.addCleanup(parent.stdout.close)
        child = int(parent.stdout.readline())
        self.addCleanup(lambda: _kill(child))
        found = {m["pid"]: m for m in broker_stats.descendants(parent.pid, broker_stats.process_table())}
        self.assertIn(child, found)
        self.assertNotEqual(found[child]["pgid"], found[parent.pid]["pgid"])
        self.assertEqual(found[child]["ppid"], parent.pid)


def _kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


if __name__ == "__main__":
    unittest.main()
