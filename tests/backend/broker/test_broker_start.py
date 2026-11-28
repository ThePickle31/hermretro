"""A real broker's start: it removes earlier engines' copies in a thread of its own only once it has put back the umask
it lowered for its socket and token, so nothing that removal makes is private to its owner alone (#236 started it
under the socket's umask, and the integration run broke)."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"
UMASK = 0o022  # the broker's own umask, before it lowers it for the socket
# The broker's main(), with the removal swapped for a probe that writes down the umask it starts under.
PROBED = f"""
import os, sys
from pathlib import Path
from backend.broker import server

def probe():
    current = os.umask(0)
    os.umask(current)
    Path(os.environ["UMASK_PROBE"]).write_text(oct(current))

server.setup.prune_prepared_copies = probe
os.umask({UMASK:#o})
sys.exit(server.main())
"""


@unittest.skipUnless(POSIX, "Linux and macOS only")
class BrokerStart(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        node = paths.find_node()
        if not node.get("ok"):
            self.skipTest("Node.js 22 or newer is not installed")
        self.node = node["path"]
        self.state = Path(tempfile.mkdtemp(prefix="hbs-", dir="/tmp"))  # short: socket paths are capped
        self.addCleanup(shutil.rmtree, self.state, True)

    def test_earlier_copies_are_removed_under_the_brokers_own_umask(self):
        probe = self.home.base / "umask"
        broker = subprocess.Popen(
            [sys.executable, "-c", PROBED, "--state-dir", str(self.state), "--node", self.node],
            cwd=ROOT,
            env={**os.environ, "UMASK_PROBE": str(probe), "HERMRETRO_BROKER_IDLE_SECONDS": "20"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 30
            while not probe.exists() and broker.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(probe.exists(), "the broker never started removing earlier copies")
            self.assertEqual(probe.read_text(), oct(UMASK))
            for name in ("broker.sock", "broker.token"):
                self.assertEqual((self.state / name).stat().st_mode & 0o077, 0, f"{name} is its owner's alone")
        finally:
            broker.send_signal(signal.SIGTERM)
            try:
                broker.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.communicate()


if __name__ == "__main__":
    unittest.main()
