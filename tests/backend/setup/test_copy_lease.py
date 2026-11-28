"""A prepared copy's lease (backend/setup/copy_lease.py): a worker's process keeps it for as long as it runs, even
after the broker that started it has closed its own descriptor (or died), and a removal sees it held."""

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import copy_lease  # noqa: E402 - the repository root goes on sys.path first


class Lease(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.copy = Path(temp.name) / "engine-2.0.1-0123456789ab"
        self.copy.mkdir()
        copy_lease.create(self.copy)  # published with it

    def is_unused(self) -> bool:
        with copy_lease.unused(self.copy) as unused:
            return unused

    def test_a_free_copy_is_unused(self):
        self.assertTrue(self.is_unused())

    def test_a_copy_from_before_leases_is_in_use_unless_the_caller_knows_better(self):
        copy_lease.path_for(self.copy).unlink()
        self.assertFalse(self.is_unused())
        self.assertFalse(copy_lease.path_for(self.copy).exists())
        with copy_lease.unused(self.copy, unleased_is_unused=True) as unused:  # the broker is stopped
            self.assertTrue(unused)

    def test_a_copy_not_there_yet_is_unused(self):
        with copy_lease.unused(self.copy.with_name("engine-2.0.2-0123456789ab")) as unused:
            self.assertTrue(unused)

    def test_a_worker_waiting_on_a_removed_lease_learns_the_copy_went(self):
        # It opened the lease file and waits for its lock while a removal holds it, then deletes copy and lease.
        waiting, outcome = threading.Event(), []
        real_flock = copy_lease.fcntl.flock

        def flock(descriptor, operation):
            if operation == copy_lease.fcntl.LOCK_SH:
                waiting.set()
            return real_flock(descriptor, operation)

        def worker():
            try:
                outcome.append(copy_lease.hold(self.copy))
            except FileNotFoundError as error:
                outcome.append(error)

        with mock.patch.object(copy_lease.fcntl, "flock", flock), copy_lease.unused(self.copy) as unused:
            self.assertTrue(unused)
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(waiting.wait(10), "the worker never reached its lock")
            self.copy.rmdir()  # removed under the exclusive lease, the lease file with it
            copy_lease.path_for(self.copy).unlink()
        thread.join(10)
        self.assertIsInstance(outcome[0], FileNotFoundError, "it holds the old file's lock as if the copy were there")

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


LAUNCHER = Path(__file__).resolve().parents[3] / "engine" / "scripts" / "start-mcp.mjs"


@unittest.skipUnless(shutil.which("node"), "node is missing")
class Launcher(unittest.TestCase):
    """The engine's launcher gives the server the lease's descriptor under the same number (mcpServerStdio)."""

    def stdio(self, environment: dict, platform: str = "linux"):
        code = (
            "const { mcpServerStdio } = await import(process.argv[2]);"
            "process.stdout.write(JSON.stringify(mcpServerStdio(JSON.parse(process.argv[3]), process.argv[4])));"
        )
        # The launcher starts itself when argv[1] is its own path: here it is ".", never that.
        done = subprocess.run(
            ["node", "--input-type=module", "-e", code, ".", LAUNCHER.as_uri(), json.dumps(environment), platform],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_server_the_launcher_starts_has_the_lease(self):
        # As start-mcp.mjs does: spawn with mcpServerStdio, and the child (the server) looks at the descriptor.
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "engine-2.0.2-0123456789ab"
            copy.mkdir()
            held = copy_lease.hold(copy)
            # A broker with many descriptors open, under this system's limit (macOS starts a shell at 256).
            lease = os.dup2(held, min(1234, resource.getrlimit(resource.RLIMIT_NOFILE)[0] - 1))
            os.close(held)
            self.addCleanup(os.close, lease)
            code = (
                "const { spawn } = await import('node:child_process');"
                "const { mcpServerStdio } = await import(process.argv[2]);"
                "const child = spawn(process.execPath, ['-e', 'console.log(require(\\'node:fs\\').fstatSync(3).ino)'],"
                " { stdio: mcpServerStdio(process.env, process.platform) });"
                "child.on('exit', (code) => process.exit(code));"
            )
            done = subprocess.run(
                ["node", "--input-type=module", "-e", code, ".", LAUNCHER.as_uri()],
                env={**os.environ, copy_lease.DESCRIPTOR_VARIABLE: str(lease)},
                pass_fds=(lease,),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(int(done.stdout.strip()), os.fstat(lease).st_ino)

    def test_the_lease_is_the_servers_descriptor_3(self):
        self.assertEqual(self.stdio({copy_lease.DESCRIPTOR_VARIABLE: "1234"}), ["inherit"] * 3 + [1234])

    def test_without_a_lease_the_server_gets_its_streams_only(self):
        for environment in ({}, {copy_lease.DESCRIPTOR_VARIABLE: "1"}, {copy_lease.DESCRIPTOR_VARIABLE: "five"}):
            self.assertEqual(self.stdio(environment), "inherit", environment)
        self.assertEqual(self.stdio({copy_lease.DESCRIPTOR_VARIABLE: "5"}, "win32"), "inherit")


if __name__ == "__main__":
    unittest.main()
