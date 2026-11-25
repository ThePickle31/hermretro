"""tools/ci/prepare_toolchain.py never reaches a developer's own hermretro: outside CI it refuses without a named
destination, and it always installs through a broker of its own in a new private folder, which it stops."""

import contextlib
import io
import os
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
    """A connected broker whose install ends in ``outcome`` at once; records what it was asked."""

    def __init__(self, outcome: str):
        self.outcome, self.asked, self.closed = outcome, [], False

    def request(self, message):
        self.asked.append(message["op"])
        if message["op"] == "install_status":
            return {"ok": True, "install": {"state": self.outcome, "fraction": 1.0}}
        return {"ok": True}

    def close(self):
        self.closed = True


class PrepareToolchain(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        os.environ.pop("GITHUB_ACTIONS", None)  # CI's own unit job sets it; each test says where it runs
        parent = tempfile.TemporaryDirectory(prefix="hrt-", dir="/tmp")  # short, as the socket needs
        self.addCleanup(parent.cleanup)
        self.parent = Path(parent.name)
        patch = mock.patch.object(prepare_toolchain, "STATE_PARENT", self.parent)
        patch.start()
        self.addCleanup(patch.stop)
        self.started = []

    def run_main(self, outcome="done", **environ):
        broker = FakeBroker(outcome)

        def ensure_broker(state_dir=None, wait=20.0):
            self.started.append(Path(state_dir) if state_dir else None)
            return broker

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, environ),
            mock.patch.object(prepare_toolchain.client, "ensure_broker", ensure_broker),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = prepare_toolchain.main()
            deps_root = os.environ.get("HERMRETRO_DEPS_ROOT")
        return code, broker, err.getvalue(), deps_root

    def test_outside_ci_without_a_destination_it_refuses_before_any_broker(self):
        code, broker, err, _deps = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(self.started, [])
        self.assertEqual(broker.asked, [])
        self.assertIn(f"refusing to install into {paths.DEPS_ROOT}", err)
        self.assertIn("FIX: HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py", err)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_a_named_destination_installs_through_a_private_broker_it_stops_and_removes(self):
        code, broker, _err, deps = self.run_main(HERMRETRO_DEPS_ROOT="relative/toolchain")
        self.assertEqual(code, 0)
        [state] = self.started
        self.assertEqual(state.parent, self.parent)
        self.assertNotEqual(state, paths.default_runtime_dir())
        self.assertEqual(broker.asked, ["install_start", "install_status", "shutdown"])
        self.assertTrue(broker.closed)
        self.assertFalse(state.exists())
        # The broker runs from the plugin folder: it is handed the folder this process resolved, never the text.
        self.assertEqual(deps, str(paths.DEPS_ROOT))
        self.assertTrue(Path(deps).is_absolute())

    def test_in_github_actions_the_default_destination_is_kept_and_the_broker_is_still_its_own(self):
        code, broker, _err, deps = self.run_main(GITHUB_ACTIONS="true")
        self.assertEqual(code, 0)
        [state] = self.started
        self.assertEqual(state.parent, self.parent)
        self.assertIsNone(deps)
        self.assertEqual(broker.asked[-1], "shutdown")

    def test_a_failed_install_keeps_the_brokers_folder_and_names_it(self):
        code, broker, err, _deps = self.run_main("failed", HERMRETRO_DEPS_ROOT=str(self.home.base / "deps"))
        self.assertEqual(code, 1)
        [state] = self.started
        self.assertTrue(state.is_dir())
        self.assertIn(f"the broker's trace and logs: {state}", err)
        self.assertEqual(broker.asked[-1], "shutdown")


if __name__ == "__main__":
    unittest.main()
