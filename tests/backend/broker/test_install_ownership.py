"""What the page's install owns: Cancel stops only the run it names, a lock is blamed on this run only when this
run took it, and an installer worker whose exit is unconfirmed keeps every other setup path waiting."""

import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, UTC
from pathlib import Path
from unittest import mock

from backend.broker import broker as broker_module, install as control
from backend.broker.broker import Denied
from backend.setup import recovery
from tests.backend.broker import test_install_recovery as shared


class BlockedEngine:
    """A worker whose toolchain_prepare waits until released (or cancelled), then answers like the engine."""

    output_lines = 0

    def __init__(self, answer=None):
        self.answer = answer or {"structuredContent": {"success": True, "stage": "ready"}}
        self.release, self.calls, self.closed, self.cancels = threading.Event(), [], False, []

    def call_tool(self, tool, arguments, timeout, cancel=None):
        self.calls.append(tool)
        self.cancels.append(cancel)
        while not self.release.wait(0.02):
            if cancel.is_set():
                raise control.EngineCancelled(cancel.reason)
        return self.answer

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


class StuckEngine(shared.QuietEngine):
    """A worker that answers, then cannot be closed: its exit is never confirmed."""

    pid = os.getpgid(0)  # a process group that exists (this test's own); only ever probed with signal 0

    def call_tool(self, tool, arguments, timeout, cancel=None):
        return {"structuredContent": {"success": True, "stage": "ready"}}

    def close(self, grace=None):
        raise OSError("worker did not exit")


class Ownership(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name)
        self.root = self.base / ".cache" / "toolchain"
        for item in (
            mock.patch.object(broker_module.paths, "setup_root", return_value=self.root),
            mock.patch.object(broker_module.paths, "DEPS_ROOT", self.base / ".cache"),
            mock.patch.object(broker_module.setup, "seed_toolchain_cache", return_value={"seeded": False}),
            mock.patch.object(broker_module.setup, "free_space", return_value={"enough": True}),
            mock.patch.object(control, "CANCEL_SETTLE", 1.0),
            mock.patch.object(control, "WATCH_EVERY", 0.05),
            mock.patch.object(control, "SETTLE_QUIET", 0.1),
        ):
            item.start()
            self.addCleanup(item.stop)

    def finished(self, broker):
        for _ in range(400):
            if not broker.install_running():
                return
            time.sleep(0.02)
        self.fail("install did not finish")

    def called(self, engine, count=1):
        for _ in range(300):
            if len(engine.calls) >= count:
                return
            time.sleep(0.01)
        self.fail("toolchain_prepare was not called")

    # -- finding: a stale Cancel never stops a retry ---------------------------------------------------------
    def test_a_cancel_for_a_finished_run_leaves_the_retry_running(self):
        engine = BlockedEngine()
        broker = shared.bare_broker(engine)
        first = broker.start_install()["run_id"]
        self.called(engine)
        engine.release.set()
        self.finished(broker)
        self.assertEqual(broker.install["state"], "done")
        engine.release.clear()
        retry = broker.start_install()["run_id"]
        self.called(engine, 2)
        self.assertNotEqual(first, retry, "each run is named")
        answer = broker.control({"op": "install_cancel", "run_id": first})["install"]
        self.assertFalse(answer["cancelling"], "the stale cancel changes nothing")
        self.assertFalse(engine.cancels[1].is_set(), "the retry's own cancel token is untouched")
        self.assertTrue(broker.install_running())
        self.assertIsNone(broker.install.get("cancel_requested_at"))
        broker.cancel_install(None)
        self.assertFalse(engine.cancels[1].is_set(), "a cancel naming no run stops nothing")
        broker.cancel_install(retry)
        self.finished(broker)
        self.assertTrue(engine.cancels[1].is_set())
        self.assertEqual(broker.install["state"], "cancelled")
        self.assertEqual(recovery.read_journal()["run_id"], retry, "the journal names the run for a reload")

    # -- finding: a lock this run never took is not called this run's ---------------------------------------
    def test_a_lock_the_engine_plan_reports_is_another_installers(self):
        lock = recovery.lock_path(self.root)
        lock.mkdir(parents=True)
        (lock / "owner.json").write_text(json.dumps({"pid": 1, "startedAt": "2026-01-01T00:00:00.000Z"}))
        blocked = {  # toolchain_prepare when planSetup found the lock (dist/server.js prepareToolchain)
            "isError": False,
            "structuredContent": {
                "success": False,
                "stage": "blocked",
                "message": "Game tools could not be prepared. Keep the existing installation and inspect the setup result.",
                "plan": {
                    "canApply": False,
                    "rootIssue": "An installer lock exists. Inspect its recorded owner; do not retry or remove a live lock.",
                    "lock": {"path": str(lock), "owner": {"pid": 1}, "automaticRecovery": False},
                },
            },
        }
        broker = shared.bare_broker(BlockedEngine(blocked))
        broker.install_engine = None
        broker.new_engine = lambda name: _answered(blocked)
        broker.start_install()
        self.finished(broker)
        self.assertEqual(broker.install["code"], "SETUP_LOCKED")
        self.assertNotIn("kept its setup lock", broker.install["hint"])
        self.assertIn("checked that the recorded owner has stopped", broker.install["hint"])
        self.assertIn("An installer lock exists", broker.install["error"])
        self.assertTrue(lock.exists(), "never removed")

    def test_a_lock_taken_after_the_plan_by_someone_else_is_theirs(self):
        lock = recovery.lock_path(self.root)
        thrown = {  # acquireSetupLock's SETUP_LOCKED, thrown by applySetup and formatted by formatErrorResult
            "isError": True,
            "structuredContent": {
                "error": f"Another setup owns {lock}. Do not delete a live lock.",
                "code": "SETUP_LOCKED",
            },
        }

        def appears(name):
            lock.mkdir(parents=True)
            return _answered(thrown)

        broker = shared.bare_broker(None)
        broker.new_engine = appears
        broker.start_install()
        self.finished(broker)
        self.assertEqual(broker.install["code"], "SETUP_LOCKED")
        self.assertIn("recorded owner", broker.install["hint"])

    def test_a_lock_older_than_this_run_is_not_blamed_on_it_after_a_cancel(self):
        lock = recovery.lock_path(self.root)
        engine = shared.CancellableEngine(self.root, release_lock=False)
        older = datetime.fromtimestamp(time.time() - 3600, UTC).isoformat()

        def mark_old(tool, arguments, timeout, cancel=None):
            threading.Timer(0.05, lambda: (lock / "owner.json").write_text(json.dumps({"startedAt": older}))).start()
            return shared.CancellableEngine.call_tool(engine, tool, arguments, timeout, cancel)

        engine.call_tool = mark_old
        broker = shared.bare_broker(engine)
        with mock.patch.object(control, "CANCEL_SETTLE", 0.4):
            broker.start_install()
            for _ in range(200):
                if engine.calls:
                    break
                time.sleep(0.01)
            time.sleep(0.1)
            broker.cancel_install(broker.install["run_id"])
            self.finished(broker)
        self.assertEqual(broker.install["code"], "SETUP_LOCKED")

    def test_a_lock_this_run_took_and_kept_is_still_reported_as_kept(self):
        lock = recovery.lock_path(self.root)

        def kept(name):
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(json.dumps({"startedAt": datetime.now(UTC).isoformat()}))
            return _answered(
                {
                    "structuredContent": {
                        "success": False,
                        "stage": "incomplete",
                        "result": {
                            "status": "partial",
                            "unsafeToRetry": True,
                            "cleanupError": {
                                "message": "An owned process may still be running.",
                                "lockPath": str(lock),
                            },
                            "components": [
                                {
                                    "id": "cli",
                                    "status": "failed",
                                    "error": {"message": "cli exited", "code": "PROCESS_CLEANUP_UNCONFIRMED"},
                                }
                            ],
                        },
                    }
                }
            )

        broker = shared.bare_broker(None)
        broker.new_engine = kept
        broker.start_install()
        self.finished(broker)
        self.assertEqual(broker.install["code"], "SETUP_LOCK_KEPT")

    # -- finding: an unconfirmed worker exit keeps the broker and every setup path waiting --------------------
    def test_a_worker_that_did_not_exit_keeps_shutdown_retirement_and_setup_waiting(self):
        engine = StuckEngine()
        broker = shared.bare_broker(engine)
        broker.table_lock, broker.lanes = threading.RLock(), {}
        broker.stopping, broker.connections, broker.broker_idle, broker.lane_idle = threading.Event(), 0, 0, 60
        broker.start_install()
        self.finished(broker)
        self.assertEqual(broker.install["code"], "WORKER_STILL_RUNNING")
        snapshot = broker.control({"op": "install_status"})["install"]
        self.assertEqual((snapshot["state"], snapshot["elsewhere"]), ("failed", False))
        self.assertIs(snapshot["worker_left"], True)
        with self.assertRaises(Denied) as refused:
            broker.control({"op": "shutdown"})
        self.assertEqual(refused.exception.code, "BUSY", "an update must not replace this broker")
        broker.housekeeping()
        self.assertFalse(broker.stopping.is_set(), "the idle broker does not retire")
        broker.tools, broker.read_only = {"toolchain_prepare": {}}, set()
        owner = {"profile": "hermretro", "conversation_id": "c1"}
        with self.assertRaises(Denied) as chat:
            broker.call({"owner": owner, "tool": "toolchain_prepare", "arguments": {"components": ["build"]}})
        self.assertEqual(chat.exception.code, "WORKER_STILL_RUNNING", "a chat cannot start another setup")
        broker.close_install_worker()  # a forced stop: the second close fails too
        self.assertEqual(recovery.read_journal()["worker_pgid"], StuckEngine.pid, "recorded for the next broker")
        fresh = shared.bare_broker(shared.QuietEngine(), generation="next-broker")
        with self.assertRaises(Denied) as again:
            fresh.start_install()
        self.assertEqual(again.exception.code, "WORKER_STILL_RUNNING", "a new broker waits for it too")
        engine.alive = lambda: False
        engine._group_exists, engine._proc = (lambda: False), object()
        self.assertIs(broker.control({"op": "install_status"})["install"]["worker_left"], False)
        self.assertIsNone(broker.install_engine)
        broker.control({"op": "shutdown"})
        self.assertTrue(broker.stopping.is_set())

    def test_a_recorded_worker_whose_group_ended_does_not_block(self):
        recovery.write_journal({"state": "failed", "code": "WORKER_STILL_RUNNING", "worker_pgid": 2**22 + 12345})
        self.assertFalse(recovery.worker_left(recovery.read_journal()))
        self.assertFalse(recovery.worker_left({"worker_pgid": 1}), "never the init process group")


def _answered(answer):
    engine = BlockedEngine(answer)
    engine.release.set()
    return engine


if __name__ == "__main__":
    unittest.main()
