"""tools/debug/broker_stats.py: reads a running broker's stats, and never starts one or writes anything."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
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
        self.assertEqual(report["engine_groups"], {})
        self.assertFalse(self.running.broker.stopping.is_set(), "a read-only tool stopped the broker")


class GroupMembers(unittest.TestCase):
    PS = """  101   101    01:02 node /x/engine/launcher.mjs
  102   101       05 /x/rgbds/rgbasm -o out.o main.asm
  103   900 1-02:03:04 bash
  bad line
"""

    def test_lists_only_the_group(self):
        members = broker_stats.group_members(101, self.PS)
        self.assertEqual([m["pid"] for m in members], [101, 102])
        self.assertEqual(members[1]["command"], "/x/rgbds/rgbasm -o out.o main.asm")
        self.assertEqual(members[0]["etime"], "01:02")

    @unittest.skipUnless(POSIX, "Linux and macOS only")
    def test_real_ps_finds_this_process_group(self):
        mine = broker_stats.group_members(os.getpgid(0))
        self.assertIn(os.getpid(), [m.get("pid") for m in mine])


if __name__ == "__main__":
    unittest.main()
