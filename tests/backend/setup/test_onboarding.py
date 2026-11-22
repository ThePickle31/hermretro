"""The desktop page's own toolchain install: download list, progress, and the broker's install op."""

import json
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.broker import broker as broker_module  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import progress as onboarding  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import bare_broker  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Denied  # noqa: E402 - the repository root goes on sys.path first

CATALOG = (ROOT / "engine/modretro-chromatic/scripts/dependency-catalog.mjs").read_text()


def pin(name: str) -> str:
    match = re.search(rf"\b{name}: \{{[^}}]*installVersion: \"([^\"]+)\"", CATALOG)
    assert match, name
    return match.group(1)


class Manifest(unittest.TestCase):
    def test_versions_match_the_engine_pins(self):
        items = {item["id"]: item for item in onboarding.MANIFEST}
        self.assertEqual(items["gbdk"]["version"], pin("gbdk"))
        self.assertEqual(items["gbstudio"]["version"], pin("cli"))
        self.assertEqual(items["uv"]["version"], pin("uv"))
        self.assertIn(re.search(r'gbvmCommit: "([0-9a-f]{7})', CATALOG).group(1), items["gbvm"]["version"])
        for part in (pin("python"), pin("pyboy"), pin("pillow")):
            self.assertIn(part, items["emulator"]["version"])

    def test_every_row_says_what_where_how_big_and_why(self):
        listed = onboarding.manifest()
        for item in listed["items"]:
            for field in ("name", "version", "source", "bytes", "purpose", "component"):
                self.assertTrue(item[field], (item["id"], field))
            self.assertIn(item["component"], onboarding.COMPONENTS)
        self.assertEqual(listed["bytes"], sum(item["bytes"] for item in onboarding.MANIFEST))
        self.assertEqual({item["component"] for item in listed["items"]}, set(onboarding.COMPONENTS))


def write_run(root: Path, components: list[dict], status="running"):
    (root / "last-run.json").write_text(json.dumps({"runId": "r1", "status": status, "components": components}))


class Progress(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "downloads").mkdir()

    def test_idle_reports_nothing_and_never_reads_an_old_run(self):
        write_run(self.root, [{"id": "gbdk", "status": "prepared"}], "complete")
        answer = onboarding.progress({"state": "idle"}, self.root)
        self.assertIsNone(answer["run"])
        self.assertEqual(answer["fraction"], 0)

    def test_running_component_progress_comes_from_bytes_on_disk(self):
        started = time.time()
        state = {"state": "running", "started_at": started, "baseline_bytes": 0}
        sizes = {
            name: sum(i["bytes"] for i in onboarding.MANIFEST if i["component"] == name)
            for name in onboarding.COMPONENTS
        }
        write_run(
            self.root,
            [
                {
                    "id": "gbdk",
                    "status": "prepared",
                    "version": "4.5.0",
                    "provenance": {"archive": "gbdk-linux64.tar.gz", "sha256": "d7857a5f" * 8, "cacheReused": False},
                },
                {"id": "cli", "status": "installing"},
            ],
        )
        (self.root / "downloads" / "blob").write_bytes(b"\0" * (sizes["gbdk"] + 1000))
        answer = onboarding.progress(state, self.root)
        components = answer["run"]["components"]
        self.assertEqual(components["gbdk"]["state"], "done")
        self.assertEqual(components["gbdk"]["checks"][0]["file"], "gbdk-linux64.tar.gz")
        self.assertEqual(components["cli"]["state"], "running")
        self.assertEqual(answer["current"], "cli")
        total = sum(sizes.values())
        self.assertAlmostEqual(answer["fraction"], (sizes["gbdk"] + 1000) / total, places=3)
        self.assertGreaterEqual(answer["downloaded_bytes"], sizes["gbdk"])

    def test_failed_component_carries_its_error_and_done_is_whole(self):
        state = {"state": "failed", "started_at": time.time(), "baseline_bytes": 0}
        write_run(
            self.root, [{"id": "gbdk", "status": "failed", "error": {"message": "ENOTFOUND github.com"}}], "incomplete"
        )
        answer = onboarding.progress(state, self.root)
        self.assertEqual(answer["run"]["components"]["gbdk"]["error"], "ENOTFOUND github.com")
        self.assertEqual(onboarding.progress({"state": "done", "started_at": time.time()}, self.root)["fraction"], 1.0)

    def test_python_checks_name_the_interpreter_and_pinned_packages(self):
        checks = onboarding._checks(
            {
                "id": "emulator",
                "provenance": {
                    "pythonVersion": "3.13.12",
                    "pythonExecutableSha256": "a" * 64,
                    "requirementsSha256": "b" * 64,
                    "resolvedPackages": [{"name": "pyboy"}, {"name": "pillow"}, {"name": "numpy"}],
                },
            }
        )
        self.assertEqual([check["file"] for check in checks], ["python 3.13.12", "3 pinned PyPI packages"])


class FakeEngine:
    def __init__(self, answer, gate=None):
        self.answer, self.gate, self.closed, self.calls = answer, gate, False, []

    def call_tool(self, tool, arguments, timeout, cancel=None):
        self.calls.append((tool, arguments))
        if self.gate:
            self.gate.wait(5)
        return self.answer

    def close(self, grace=None):
        self.closed = True


def install_broker(engine):
    return bare_broker(
        install={"state": "idle"},
        install_lock=threading.Lock(),
        prepare_lock=threading.Lock(),
        new_engine=lambda name: engine,
        install_engine=None,
        last_activity=0,
    )


class BrokerInstall(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "toolchain"
        self.addCleanup(shutil.rmtree, self.root.parent, ignore_errors=True)
        patches = [
            mock.patch.object(broker_module.paths, "setup_root", return_value=self.root),
            mock.patch.object(broker_module.setup, "seed_toolchain_cache", return_value={"seeded": False}),
            # The journal (recovery.py) goes beside the toolchain, in this test's folder; any disk has room.
            mock.patch.object(broker_module.paths, "DEPS_ROOT", self.root.parent / ".cache"),
            mock.patch.object(broker_module.setup, "free_space", return_value={"enough": True}),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def wait_finished(self, broker):
        for _ in range(200):
            if not broker.install_running():
                return
            time.sleep(0.01)
        self.fail("install did not finish")

    def test_runs_toolchain_prepare_for_build_and_emulator_without_a_chat(self):
        gate = threading.Event()
        engine = FakeEngine({"structuredContent": {"success": True, "stage": "ready"}}, gate)
        broker = install_broker(engine)
        self.assertEqual(broker.start_install()["state"], "running")
        self.assertTrue(broker.install_running())
        self.assertEqual(broker.start_install()["state"], "running", "a second start joins the running install")
        gate.set()
        self.wait_finished(broker)
        self.assertEqual(engine.calls, [("toolchain_prepare", {"components": ["build", "emulator"]})])
        self.assertTrue(engine.closed)
        self.assertEqual(broker.install["state"], "done")
        self.assertFalse(broker.prepare_lock.locked(), "the setup lock is released")

    def test_a_failed_prepare_reports_the_component_error(self):
        engine = FakeEngine(
            {
                "isError": False,
                "structuredContent": {
                    "success": False,
                    "stage": "incomplete",
                    "result": {
                        "components": [
                            {"id": "gbdk", "status": "prepared"},
                            {
                                "id": "cli",
                                "status": "failed",
                                "error": {"message": "yarn: ENOTFOUND registry.npmjs.org"},
                            },
                        ]
                    },
                },
            }
        )
        broker = install_broker(engine)
        broker.start_install()
        self.wait_finished(broker)
        self.assertEqual(broker.install["state"], "failed")
        # An unreachable download source is named as such, with what to do about it.
        self.assertEqual(broker.install["code"], "NETWORK")
        self.assertEqual(broker.install["error"], "cli: yarn: ENOTFOUND registry.npmjs.org")
        self.assertIn("internet connection", broker.install["hint"])

    def test_refused_while_a_chat_is_preparing(self):
        broker = install_broker(FakeEngine({}))
        broker.prepare_lock.acquire()
        with self.assertRaises(Denied) as refused:
            broker.start_install()
        self.assertEqual(refused.exception.code, "OPERATION_IN_PROGRESS")
        self.assertEqual(broker.install["state"], "idle")

    def test_a_thread_that_cannot_start_releases_the_lock(self):
        broker = install_broker(FakeEngine({}))
        with mock.patch.object(broker_module.threading, "Thread", side_effect=RuntimeError("can't start new thread")):
            with self.assertRaises(RuntimeError):
                broker.start_install()
        self.assertFalse(broker.prepare_lock.locked())
        self.assertFalse(broker.install_running())
        self.assertEqual(broker.install["state"], "failed")

    def test_a_stopping_broker_closes_the_install_worker(self):
        gate = threading.Event()
        engine = FakeEngine({"structuredContent": {"success": True}}, gate)
        broker = install_broker(engine)
        broker.lanes, broker.table_lock, broker.install_engine = {}, threading.RLock(), None
        broker.start_install()
        for _ in range(200):
            if broker.install_engine is not None:
                break
            time.sleep(0.01)
        broker.close_all()
        self.assertTrue(engine.closed)
        gate.set()
        self.wait_finished(broker)
        self.assertIsNone(broker.install_engine)

    def test_a_running_install_keeps_the_broker_alive(self):
        gate = threading.Event()
        broker = install_broker(FakeEngine({"structuredContent": {"success": True}}, gate))
        broker.lanes, broker.table_lock = {}, threading.RLock()
        broker.stopping = threading.Event()
        broker.start_install()
        with self.assertRaises(Denied):
            broker.control({"op": "shutdown"})
        self.assertFalse(broker.stopping.is_set())
        gate.set()
        self.wait_finished(broker)


if __name__ == "__main__":
    unittest.main()
