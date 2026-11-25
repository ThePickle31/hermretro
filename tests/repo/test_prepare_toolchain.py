"""tools/ci/prepare_toolchain.py never reaches a developer's own hermretro: outside CI it refuses without a named
destination, and with an override that would move the toolchain out of it; it always installs through a broker of its
own in a new private folder, whose process it stops and sees exit on every way out, signals included."""

import contextlib
import io
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import prepare_toolchain  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


class FakeBroker:
    """A connected broker whose install ends in ``outcome`` at once; ``on_status`` runs on each status request (to
    raise or send a signal). Records what it was asked."""

    def __init__(self, outcome: str, on_status=None):
        self.outcome, self.on_status, self.asked, self.closed = outcome, on_status, [], False
        self.startup_deadline = 0.0  # what try_connect leaves from the connect deadline
        self.deadline_at_status = None

    def request(self, message):
        if message["op"] == "install_status":
            self.deadline_at_status = self.startup_deadline
        return self._answer(message)

    def _answer(self, message):
        self.asked.append(message["op"])
        if message["op"] == "install_status":
            if self.on_status:
                self.on_status()
            return {"ok": True, "install": {"state": self.outcome, "fraction": 1.0}}
        return {"ok": True}

    def close(self):
        self.closed = True


class FakeProcess:
    """The broker's process: exits on SIGTERM, or (``stubborn``) only on SIGKILL. Records the signals it got."""

    pid = -1

    def __init__(self, stubborn=False):
        self.stubborn, self.signals, self.returncode = stubborn, [], None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.signals.append("SIGTERM")
        if not self.stubborn:
            self.returncode = -signal.SIGTERM

    def kill(self):
        self.signals.append("SIGKILL")
        self.returncode = -signal.SIGKILL

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("broker", timeout)
        return self.returncode


class PrepareToolchain(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        # CI's own unit job sets GITHUB_ACTIONS, and a developer's shell may name either folder: each test says.
        for name in ("GITHUB_ACTIONS", "HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT"):
            os.environ.pop(name, None)
        parent = tempfile.TemporaryDirectory(prefix="hrt-", dir="/tmp")  # short, as the socket needs
        self.addCleanup(parent.cleanup)
        self.parent = Path(parent.name)
        for name, value in (("STATE_PARENT", self.parent), ("STOP_SECONDS", 0), ("KILL_SECONDS", 0)):
            patch = mock.patch.object(prepare_toolchain, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.started = []

    def run_main(self, outcome="done", *, on_status=None, on_spawn=None, stubborn=False, **environ):
        broker, process = FakeBroker(outcome, on_status), FakeProcess(stubborn)

        def spawn_broker(state_dir, node, *, deadline=None):
            self.started.append(Path(state_dir))
            if on_spawn:
                on_spawn()
            return process

        handlers = {signum: signal.getsignal(signum) for signum in prepare_toolchain.Signals.CAUGHT}
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, environ),
            mock.patch.object(prepare_toolchain.paths, "find_node", lambda: {"ok": True, "path": "node"}),
            mock.patch.object(prepare_toolchain.client, "spawn_broker", spawn_broker),
            mock.patch.object(prepare_toolchain.client, "try_connect", lambda state, **_: (broker, None)),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = prepare_toolchain.main()
            deps_root = os.environ.get("HERMRETRO_DEPS_ROOT")
        self.assertEqual({signum: signal.getsignal(signum) for signum in handlers}, handlers, "handlers restored")
        self.out = out.getvalue()
        return code, broker, process, err.getvalue(), deps_root

    def assert_stopped_and_kept(self, process, err):
        [state] = self.started
        self.assertEqual(process.signals, ["SIGTERM"])
        self.assertTrue(state.is_dir())
        self.assertIn(f"the broker's trace and logs: {state}", err)

    def test_outside_ci_without_a_destination_it_refuses_before_any_broker(self):
        code, broker, _process, err, _deps = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(self.started, [])
        self.assertEqual(broker.asked, [])
        self.assertIn(f"refusing to install into {paths.DEPS_ROOT}", err)
        self.assertIn("FIX: HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py", err)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_a_setup_root_override_is_refused_even_with_a_destination(self):
        setup = str(self.home.base / "elsewhere")
        code, broker, _process, err, _deps = self.run_main(
            HERMRETRO_DEPS_ROOT=str(self.home.base / "deps"), GB_STUDIO_SETUP_ROOT=setup
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.started, [])
        self.assertIn(f"refusing to install into {setup}", err)
        self.assertIn("FIX: unset GB_STUDIO_SETUP_ROOT", err)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_a_named_destination_installs_through_a_private_broker_it_stops_and_removes(self):
        code, broker, process, _err, deps = self.run_main(HERMRETRO_DEPS_ROOT="relative/toolchain")
        self.assertEqual(code, 0)
        [state] = self.started
        self.assertEqual(state.parent, self.parent)
        self.assertNotEqual(state, paths.default_runtime_dir())
        self.assertEqual(broker.asked, ["install_start", "install_status"])
        # The connect deadline must not cap the install's requests (a cold macOS install outlasts it).
        self.assertIsNone(broker.deadline_at_status)
        self.assertTrue(broker.closed)
        self.assertEqual(process.signals, ["SIGTERM"])
        self.assertFalse(state.exists())
        # The broker runs from the plugin folder: it is handed the folder this process resolved, never the text.
        resolved = Path("relative/toolchain").resolve()
        self.assertEqual(deps, str(resolved))
        self.assertIn(f"toolchain: {resolved / 'toolchain'}", self.out)

    def test_in_github_actions_the_default_destination_is_kept_and_the_broker_is_still_its_own(self):
        code, _broker, process, _err, deps = self.run_main(GITHUB_ACTIONS="true")
        self.assertEqual(code, 0)
        [state] = self.started
        self.assertEqual(state.parent, self.parent)
        self.assertIsNone(deps)
        self.assertIn(f"toolchain: {paths.DEPS_ROOT / 'toolchain'}", self.out)
        self.assertEqual(process.signals, ["SIGTERM"])

    def test_a_failed_install_keeps_the_brokers_folder_and_names_it(self):
        code, _broker, process, err, _deps = self.run_main("failed", HERMRETRO_DEPS_ROOT=str(self.home.base / "deps"))
        self.assertEqual(code, 1)
        self.assert_stopped_and_kept(process, err)

    def test_a_broker_that_does_not_stop_on_sigterm_is_killed_and_its_folder_kept(self):
        code, _broker, process, err, _deps = self.run_main(stubborn=True, HERMRETRO_DEPS_ROOT=str(self.home.base))
        self.assertEqual(code, 1)
        self.assertEqual(process.signals, ["SIGTERM", "SIGKILL"])
        self.assertIn("did not stop in 0 s and was killed", err)
        [state] = self.started
        self.assertTrue(state.is_dir())

    def test_a_signal_while_the_broker_starts_waits_until_its_process_is_kept_then_stops_it(self):
        code, broker, process, err, _deps = self.run_main(
            on_spawn=lambda: signal.raise_signal(signal.SIGTERM), HERMRETRO_DEPS_ROOT=str(self.home.base)
        )
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertEqual(broker.asked, [])
        self.assertIn("stopped by SIGTERM", err)
        self.assert_stopped_and_kept(process, err)

    def test_ctrl_c_or_sighup_during_the_install_stops_the_broker(self):
        for signum in (signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                self.started = []
                code, broker, process, err, _deps = self.run_main(
                    "running",
                    on_status=lambda s=signum: signal.raise_signal(s),
                    HERMRETRO_DEPS_ROOT=str(self.home.base),
                )
                self.assertEqual(code, 128 + signum)
                self.assertTrue(broker.closed)
                self.assert_stopped_and_kept(process, err)

    def test_a_request_that_fails_still_stops_the_broker(self):
        def lost():
            raise OSError("connection reset")

        code, _broker, process, err, _deps = self.run_main(
            "running", on_status=lost, HERMRETRO_DEPS_ROOT=str(self.home.base)
        )
        self.assertEqual(code, 1)
        self.assertIn("the install could not be followed: OSError: connection reset", err)
        self.assert_stopped_and_kept(process, err)


if __name__ == "__main__":
    unittest.main()
