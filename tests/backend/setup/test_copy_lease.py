"""A prepared copy's lease (backend/setup/copy_lease.py): a worker's process keeps it for as long as it runs, even
after the broker that started it has closed its own descriptor (or died), and a removal sees it held."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import copy_lease  # noqa: E402 - the repository root goes on sys.path first


class Lease(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.copy = Path(temp.name) / "engine-2.0.1-0123456789ab"
        self.copy.mkdir()

    def is_unused(self) -> bool:
        with copy_lease.unused(self.copy) as unused:
            return unused

    def test_a_free_copy_is_unused(self):
        self.assertTrue(self.is_unused())
        self.assertTrue(copy_lease.path_for(self.copy).is_file())

    def test_a_worker_keeps_the_lease_after_its_starter_lets_go(self):
        lease = copy_lease.hold(self.copy)
        worker = subprocess.Popen(  # what EngineProcess starts, with the lease passed down (keep_fds)
            [sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE, pass_fds=(lease,)
        )
        self.addCleanup(worker.wait, 10)
        os.close(lease)  # the broker's own descriptor, closed once the worker runs (or the broker died)
        self.assertFalse(self.is_unused(), "the worker still runs in it")
        worker.stdin.close()  # the worker exits
        worker.wait(10)
        self.assertTrue(self.is_unused())

    def test_a_removal_holding_it_holds_it_alone(self):
        with copy_lease.unused(self.copy) as unused:
            self.assertTrue(unused)
            self.assertFalse(self.is_unused(), "a second removal or a replacement waits its turn")


if __name__ == "__main__":
    unittest.main()
