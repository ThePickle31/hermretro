"""The update check's own judgements (tools/ci/update_check.py and update_inside.py): which leftovers in the plugin
folder are fine, and that it refuses to call the old broker replaced once that broker has already exited by itself."""

import io
import json
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import update_check  # noqa: E402 - tools/ci goes on sys.path first
import update_inside  # noqa: E402 - tools/ci goes on sys.path first


# A throwaway repository: no identity, signing or hooks of whoever runs the tests.
ISOLATED = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *ISOLATED, *args], cwd=repo, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout


class Leftovers(unittest.TestCase):
    def test_bytecode_is_a_cache_folder_a_file_inside_one_or_a_compiled_module(self):
        for path in ("__pycache__/", "tools/x/__pycache__/", "tools/x/__pycache__/a.cpython-314.pyc", "a.pyc", "b.pyo"):
            self.assertTrue(update_check.is_bytecode(path), path)
        for path in ("tools/x/", "tools/x/.env", "pycache/a.txt", "a.py", "my__pycache__/a.txt"):
            self.assertFalse(update_check.is_bytecode(path), path)

    def test_a_folder_holding_only_bytecode_is_judged_by_its_files_not_by_its_folded_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "--quiet")
            (repo / ".gitignore").write_text("__pycache__/\n*.local\n")
            (repo / "tools" / "gone").mkdir(parents=True)
            (repo / "tools" / "gone" / "mod.py").write_text("")
            (repo / "kept").mkdir()
            (repo / "kept" / "keep.py").write_text("")
            git(repo, "add", "-A")
            git(repo, "commit", "--quiet", "-m", "release")
            # What an update leaves: the module's folder removed by git, its bytecode (ignored) kept.
            (repo / "tools" / "gone" / "__pycache__").mkdir()
            (repo / "tools" / "gone" / "__pycache__" / "mod.cpython-314.pyc").write_bytes(b"")
            git(repo, "rm", "--quiet", "tools/gone/mod.py")
            git(repo, "commit", "--quiet", "-m", "update")
            # And an ignored file that is not bytecode, alone in its folder too.
            (repo / "secrets").mkdir()
            (repo / "secrets" / "token.local").write_text("x")

            folded = git(repo, "status", "--porcelain", "--ignored")
            # Plain --ignored folds every folder holding only ignored files, up to `tools/`: no name to judge by.
            self.assertIn("!! tools/\n", folded)
            listing = git(repo, "status", "--porcelain", "-z", "--ignored=matching", "--untracked-files=all")
            problems = update_check.ignored_problems(listing, " --update-from v1")
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("secrets/token.local", problems[0])
            self.assertIn("FIX:", problems[0])
            self.assertTrue(problems[0].endswith(" --update-from v1"))
            self.assertEqual(update_check._leftovers(repo, ""), problems_without_fix(problems))


def problems_without_fix(problems: list[str]) -> list[str]:
    return [problem.removesuffix(" --update-from v1") for problem in problems]


class OldBroker(unittest.TestCase):
    def test_a_running_old_broker_lets_the_check_go_on(self):
        self.assertIsNone(update_inside.old_broker_gone(1234, True, " --update-from v1"))

    def test_an_old_broker_that_exited_by_itself_fails_the_check_with_a_fix(self):
        message = update_inside.old_broker_gone(1234, False, " --update-from v1")
        self.assertIn("pid 1234", message)
        self.assertIn("\nFIX:", message)
        self.assertTrue(message.endswith("clean_install_check.py --update-from v1"))

    def test_holding_a_broker_that_does_not_listen_fails_with_a_fix(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit) as raised:
            update_inside.hold_open(str(Path(tmp) / "broker.sock"))
        self.assertIn("FIX:", str(raised.exception))

    def test_holding_keeps_one_silent_connection_open_until_closed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:  # short: a Unix socket path is at most 104 bytes
            path = str(Path(tmp) / "b.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(path)
                server.listen(1)
                held = update_inside.hold_open(path)
                accepted, _ = server.accept()
                with accepted:
                    accepted.settimeout(0.2)
                    with self.assertRaises(TimeoutError):  # open and silent: no request, no close
                        accepted.recv(1)
                    held.close()
                    accepted.settimeout(2)
                    self.assertEqual(accepted.recv(1), b"")  # closed

    def test_the_old_broker_is_held_through_the_new_drive_past_its_idle_deadline(self):
        # The idle deadline has passed when the new client connects (Hermes starting, the plugin loading), but the
        # held connection keeps the old broker up: released first, it is gone and a fresh one looks replaced. The
        # broker judges idleness only when the test asks, and time moves only when the test says so: no sleep races.
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:  # short: a Unix socket path is at most 104 bytes
            broker = IdleBroker(str(Path(tmp) / "b.sock"), idle=0.1)
            self.addCleanup(broker.stop)  # registered at once: a failed wait below still stops the broker
            held = update_inside.hold_open(broker.path)
            self.addCleanup(held.close)
            broker.wait_for_connections(1)  # accepted, not just connected
            broker.advance(1.0)  # long past the deadline: only the held connection keeps the broker up

            def drive():
                # The broker notices what became of the hold first, then time passes before the new client
                # connects: a hold released too early exits on the idle judgement here, and the connect is refused.
                broker.connections()
                broker.advance(1.0)
                self.assertFalse(broker.check_idle_once(), "the old broker idled out as soon as the hold was released")
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as new_client:
                    new_client.connect(broker.path)  # refused when the old broker idled out
                    broker.wait_for_connections(2)  # count the new client before it can close
                return "driven"

            self.assertEqual(update_inside.drive_holding(held, 1234, lambda _: not broker.gone, drive, ""), "driven")
            self.assertFalse(broker.gone, "the old broker idled out during the new drive")
            self.assertEqual(held.fileno(), -1, "the held connection is released once the drive is done")
            broker.wait_for_connections(0)
            broker.advance(1.0)  # released, it idles out as before, on the same judgement
            self.assertTrue(broker.check_idle_once(), "released, the old broker idles out as before")
            self.assertTrue(broker.gone)

    def test_a_gone_old_broker_stops_before_the_new_drive_and_releases_the_hold(self):
        held = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with self.assertRaises(SystemExit) as raised:
            update_inside.drive_holding(held, 1234, lambda _: False, lambda: self.fail("drove a gone broker"), "")
        self.assertIn("pid 1234", str(raised.exception))
        self.assertEqual(held.fileno(), -1)


class KeptGateway(unittest.TestCase):
    """The old version's gateway, still running after the update: the broker it reached is remembered, so the check
    stops one it started in place of the new version's."""

    def gateway(self, folder: Path, found: dict):
        out = folder / "kept.json"
        out.write_text(json.dumps(found))
        gateway = object.__new__(update_inside.OldGateway)  # without the Hermes process it would start
        gateway.fix, gateway.out, gateway.broker_pid = "", out, None
        gateway.process = mock.Mock(stdin=io.StringIO())
        gateway.reader = mock.Mock()
        return gateway

    def test_a_broker_it_started_in_place_of_the_new_one_is_remembered_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            gateway = self.gateway(Path(tmp), {"broker_pid": 9})
            [problem] = gateway.problems({"broker_pid": 8})
        self.assertIn("replaced the new broker (pid 8) with pid 9", problem)
        self.assertEqual(gateway.broker_pid, 9)

    def test_the_new_broker_kept_is_remembered_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            gateway = self.gateway(Path(tmp), {"broker_pid": 8})
            self.assertEqual(gateway.problems({"broker_pid": 8}), [])
        self.assertEqual(gateway.broker_pid, 8)

    def test_its_doctor_call_failing_reports_and_names_the_broker_that_answered(self):
        # The kept phase as it runs inside Hermes writes its report, and the gateway reads it back.
        calls = iter([{"ok": True}, {"ok": True}, SystemExit("plugin.hermretro.doctor answered {}")])

        def rpc(_name):
            answer = next(calls)
            if isinstance(answer, BaseException):
                raise answer
            return answer

        with tempfile.TemporaryDirectory() as tmp:
            gateway = self.gateway(Path(tmp), {})
            with (
                mock.patch.object(update_inside, "rpc", side_effect=rpc),
                mock.patch.object(update_inside, "answering_broker", return_value=(9, "")),
                mock.patch.object(update_inside.sys, "stdin", io.StringIO(update_inside.GO + "\n")),
                mock.patch("builtins.print"),
            ):
                update_inside.inside("kept", str(gateway.out))
            [problem] = gateway.problems({"broker_pid": 8})
        self.assertIn("plugin.hermretro.doctor answered", problem)
        self.assertEqual(gateway.broker_pid, 9)


class FailedDrive(unittest.TestCase):
    """A drive's doctor call can fail after starting a broker: the drive names it, and the check stops it too."""

    def test_the_new_drives_doctor_call_failing_still_names_the_broker_that_answers(self):
        def rpc(name, _params=None):
            if name == "doctor":
                raise SystemExit("plugin.hermretro.doctor answered {}")
            return {"ok": True, "games": [], "pending": []}

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "thumbs").mkdir()
            (folder / "thumbs" / "a.png").write_bytes(b"")
            (folder / "update-check.txt").write_text("downloads stay")
            fake_paths = mock.Mock(DEPS_ROOT=folder, library_dir=lambda: folder, hermretro_home=lambda: folder)
            with (
                mock.patch.object(update_inside, "rpc", side_effect=rpc),
                mock.patch.object(update_inside, "module", lambda role: fake_paths if role == "paths" else mock.Mock()),
                mock.patch.object(update_inside, "answering_broker", return_value=(9, "")),
            ):
                found = update_inside._use_the_plugin("new", folder / "new.json")
        self.assertEqual(found, {"fatal": "plugin.hermretro.doctor answered {}", "broker_pid": 9})

    def test_the_broker_a_failed_drive_names_goes_to_the_cleanup(self):
        brokers = []
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new.json"

            def run(*_args, **_kwargs):
                out.write_text(json.dumps({"fatal": "plugin.hermretro.doctor answered {}", "broker_pid": 9}))
                return subprocess.CompletedProcess([], 0, "", "")

            args = mock.Mock(hermes_python="python3", update_from="v1")
            with mock.patch.object(update_check.subprocess, "run", side_effect=run), mock.patch("builtins.print"):
                with self.assertRaises(SystemExit):
                    update_check._drive(args, Path(tmp), Path(tmp), "new", brokers)
        self.assertEqual(brokers, [9])


class CleanUp(unittest.TestCase):
    def test_every_broker_is_stopped_once_the_kept_gateways_replacement_included(self):
        held, kept = mock.Mock(), mock.Mock(broker_pid=9)
        with mock.patch.object(update_check.os, "kill") as kill:
            update_check.clean_up(held, kept, [7, 8, 0])
        held.close.assert_called_once_with()
        kept.stop.assert_called_once_with()
        self.assertEqual(
            [call.args for call in kill.call_args_list], [(7, signal.SIGTERM), (8, signal.SIGTERM), (9, signal.SIGTERM)]
        )

    def test_the_new_broker_the_gateway_kept_is_stopped_once(self):
        with mock.patch.object(update_check.os, "kill") as kill:
            update_check.clean_up(None, mock.Mock(broker_pid=8), [7, 8])
        self.assertEqual([call.args[0] for call in kill.call_args_list], [7, 8])


class IdleBroker:
    """A stand-in for the broker's idle exit: it stops listening once no connection has been open for `idle`.

    The deadline is judged only when the test runs `check_idle_once` (the real broker loops it), and the clock
    moves only when the test advances it, so a test can put the broker past the deadline without sleeping.
    """

    def __init__(self, path: str, idle: float):
        self.path, self.idle, self.gone = path, idle, False
        self.conns: list[socket.socket] = []
        self.skew = 0.0
        self.last = time.monotonic()
        self.lock = threading.RLock()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen(8)
        threading.Thread(target=self._accept, daemon=True).start()

    def now(self) -> float:
        return time.monotonic() + self.skew

    def advance(self, seconds: float):
        """Move the broker's clock past the deadline, as waiting would."""
        with self.lock:
            self.skew += seconds

    def _accept(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            conn.setblocking(False)  # a silent, open client: peek would block, not end
            with self.lock:
                self.conns.append(conn)

    def _reap(self):
        """Drop the clients that have closed; a silent one that is still open stays (and counts)."""
        for conn in list(self.conns):
            try:
                closed = conn.recv(1, socket.MSG_PEEK) == b""
            except BlockingIOError:
                continue
            except OSError:
                closed = True
            if closed:
                self.conns.remove(conn)
                conn.close()
                self.last = self.now()

    def connections(self) -> int:
        with self.lock:
            self._reap()
            return len(self.conns)

    def check_idle_once(self) -> bool:
        """One pass of the broker's idle loop: exit (True) when nothing is open and the deadline has passed."""
        with self.lock:
            self._reap()
            if not self.conns and self.now() - self.last >= self.idle:
                self.stop()
                return True
            return False

    def wait_for_connections(self, count: int):
        deadline = time.monotonic() + 5
        while self.connections() != count:
            if time.monotonic() > deadline:
                raise AssertionError(f"the broker has {self.connections()} connection(s), not {count}")
            time.sleep(0.005)

    def stop(self):
        if self.gone:
            return
        self.gone = True  # as the broker does on its way out: the socket file goes, so a connect is refused
        Path(self.path).unlink(missing_ok=True)
        with self.lock:
            for conn in self.conns:
                conn.close()
            self.conns.clear()
        try:
            self.listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.listener.close()


if __name__ == "__main__":
    unittest.main()
