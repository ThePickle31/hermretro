"""The update check's own judgements (tools/ci/update_check.py): which leftovers in the plugin folder are fine,
and that it refuses to call the old broker replaced once that broker has already exited by itself."""

import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import update_check  # noqa: E402 - the repository root goes on sys.path first


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
        self.assertIsNone(update_check.old_broker_gone(1234, True, " --update-from v1"))

    def test_an_old_broker_that_exited_by_itself_fails_the_check_with_a_fix(self):
        message = update_check.old_broker_gone(1234, False, " --update-from v1")
        self.assertIn("pid 1234", message)
        self.assertIn("\nFIX:", message)
        self.assertTrue(message.endswith("clean_install_check.py --update-from v1"))

    def test_holding_a_broker_that_does_not_listen_fails_with_a_fix(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit) as raised:
            update_check.hold_open(str(Path(tmp) / "broker.sock"))
        self.assertIn("FIX:", str(raised.exception))

    def test_holding_keeps_one_silent_connection_open_until_closed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:  # short: a Unix socket path is at most 104 bytes
            path = str(Path(tmp) / "b.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(path)
                server.listen(1)
                held = update_check.hold_open(path)
                accepted, _ = server.accept()
                with accepted:
                    accepted.settimeout(0.2)
                    with self.assertRaises(TimeoutError):  # open and silent: no request, no close
                        accepted.recv(1)
                    held.close()
                    accepted.settimeout(2)
                    self.assertEqual(accepted.recv(1), b"")  # closed

    def test_the_old_broker_is_held_through_the_new_drive_past_its_idle_deadline(self):
        # Idle deadline reached after the liveness check, before the new client connects (Hermes starting, the
        # plugin loading): with the hold released first, the old broker is gone and a fresh one looks replaced.
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:  # short: a Unix socket path is at most 104 bytes
            broker = IdleBroker(str(Path(tmp) / "b.sock"), idle=0.3)
            held = update_check.hold_open(broker.path)
            broker.wait_for_connections(1)

            def drive():
                time.sleep(1.0)  # well past the idle deadline
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as new_client:
                    new_client.connect(broker.path)  # refused when the old broker idled out
                return "driven"

            try:
                self.assertEqual(update_check.drive_holding(held, 1234, lambda _: not broker.gone, drive, ""), "driven")
                self.assertFalse(broker.gone, "the old broker idled out during the new drive")
                self.assertEqual(held.fileno(), -1, "the held connection is released once the drive is done")
                broker.wait_for_connections(0)
                time.sleep(0.6)
                self.assertTrue(broker.gone, "released, the old broker idles out as before")
            finally:
                held.close()
                broker.stop()

    def test_a_gone_old_broker_stops_before_the_new_drive_and_releases_the_hold(self):
        held = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with self.assertRaises(SystemExit) as raised:
            update_check.drive_holding(held, 1234, lambda _: False, lambda: self.fail("drove a gone broker"), "")
        self.assertIn("pid 1234", str(raised.exception))
        self.assertEqual(held.fileno(), -1)


class IdleBroker:
    """A stand-in for the broker's idle exit: it stops listening once no connection has been open for `idle`."""

    def __init__(self, path: str, idle: float):
        self.path, self.idle, self.gone = path, idle, False
        self.open = 0
        self.lock = threading.Condition()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen(8)
        self.last = time.monotonic()
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._idle, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            with self.lock:
                self.open += 1
                self.lock.notify_all()
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        with conn:
            while conn.recv(1024):
                pass
        with self.lock:
            self.open -= 1
            self.last = time.monotonic()
            self.lock.notify_all()

    def _idle(self):
        while not self.gone:
            time.sleep(0.02)
            with self.lock:
                if self.open == 0 and time.monotonic() - self.last >= self.idle:
                    self.stop()

    def wait_for_connections(self, count: int):
        with self.lock:
            self.lock.wait_for(lambda: self.open == count, timeout=5)

    def stop(self):
        if self.gone:
            return
        self.gone = True  # as the broker does on its way out: the socket file goes, so a connect is refused
        Path(self.path).unlink(missing_ok=True)
        try:
            self.listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.listener.close()


if __name__ == "__main__":
    unittest.main()
