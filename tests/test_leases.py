"""Stale recording-lease recovery (backend/broker/leases.py), with real processes and files."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.broker import leases  # noqa: E402


def write_lease(root: Path, pid: int, mtime: float | None = None, mode: int = 0o600, extra: dict | None = None) -> Path:
    path = root / leases.LEASE
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {"schemaVersion": 1, "pid": pid, "token": str(uuid.uuid4()), **(extra or {})}
    path.write_text(json.dumps(record, separators=(",", ":")) + "\n")
    os.chmod(path, mode)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class LeaseRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_conflict_detection_matches_the_engine_refusal(self):
        refusal = {"isError": True, "structuredContent": {"recordingAccessFailure": {
            "operation": "create-exclusive-lease", "category": "already-exists", "code": "EEXIST", "errno": -17}}}
        self.assertTrue(leases.is_lease_conflict(refusal))
        self.assertFalse(leases.is_lease_conflict({"isError": True, "structuredContent": {"error": "other"}}))
        self.assertFalse(leases.is_lease_conflict({"content": []}))

    def test_a_dead_owner_is_cleared(self):
        path = write_lease(self.root, dead_pid())
        answer = leases.reclaim_stale(self.root, set())
        self.assertTrue(answer["cleared"], answer)
        self.assertEqual(answer["owner"], "dead")
        self.assertFalse(path.exists())

    def test_a_reused_pid_is_cleared(self):
        # This test process is alive and started long before a lease written "now".
        # A lease written an hour BEFORE this process started could not have been written by it.
        started = leases.process_start(os.getpid())
        self.assertIsNotNone(started)
        path = write_lease(self.root, os.getpid(), mtime=started - 3600)
        answer = leases.reclaim_stale(self.root, set())
        self.assertTrue(answer["cleared"], answer)
        self.assertEqual(answer["owner"], "reused")
        self.assertFalse(path.exists())

    def test_a_live_possible_owner_is_kept(self):
        path = write_lease(self.root, os.getpid())  # written after this process started
        answer = leases.reclaim_stale(self.root, set())
        self.assertFalse(answer["cleared"])
        self.assertEqual(answer["owner"], "live")
        self.assertTrue(path.exists())

    def test_our_own_live_worker_is_kept(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            path = write_lease(self.root, child.pid, mtime=time.time() - 3600)  # even if it looks reused
            answer = leases.reclaim_stale(self.root, {child.pid})
            self.assertFalse(answer["cleared"])
            self.assertEqual(answer["owner"], "ours")
            self.assertTrue(path.exists())
        finally:
            child.kill()
            child.wait()

    def test_anything_that_is_not_exactly_an_engine_lease_is_left_alone(self):
        pid = dead_pid()
        for kwargs in ({"mode": 0o644}, {"extra": {"note": "x"}}):
            path = write_lease(self.root, pid, **kwargs)
            answer = leases.reclaim_stale(self.root, set())
            self.assertFalse(answer["cleared"], kwargs)
            self.assertIn("not recognised", answer["reason"])
            self.assertTrue(path.exists())
            path.unlink()
        path = self.root / leases.LEASE
        path.write_text("not json")
        os.chmod(path, 0o600)
        self.assertFalse(leases.reclaim_stale(self.root, set())["cleared"])
        self.assertTrue(path.exists())

    def test_a_lease_that_changes_during_the_check_is_kept(self):
        path = write_lease(self.root, dead_pid())
        real = leases.owner_state

        def swap(pid, mtime, groups):  # another client takes a fresh lease while we decide
            state = real(pid, mtime, groups)
            write_lease(self.root, os.getpid())
            return state
        with mock.patch.object(leases, "owner_state", swap):
            answer = leases.reclaim_stale(self.root, set())
        self.assertFalse(answer["cleared"])
        self.assertIn("changed", answer["reason"])
        self.assertEqual(json.loads(path.read_text())["pid"], os.getpid())

    def test_no_lease_is_a_quiet_no(self):
        self.assertEqual(leases.reclaim_stale(self.root, set()), {"cleared": False, "reason": "no lease"})


if __name__ == "__main__":
    unittest.main()
