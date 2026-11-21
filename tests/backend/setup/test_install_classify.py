"""Why a page install stopped, read from the pinned engine's structured toolchain_prepare results (shapes from
engine/modretro-chromatic: scripts/setup.mjs serializedError, scripts/setup-io.mjs, dist/server.js
prepareToolchain and formatErrorResult), and whether the disk can hold an install before it starts."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.setup import recovery

ROOT = Path("/t/toolchain")
FINISHED_NOT = (
    "Game tool setup did not finish. Completed components are preserved; inspect the failure before any retry."
)


def incomplete(*components, **run):
    """A toolchain_prepare answer for an apply that ran and ended partial."""
    return {
        "content": [{"type": "text", "text": "Operation failed"}],
        "structuredContent": {
            "success": False,
            "stage": "incomplete",
            "message": FINISHED_NOT,
            "result": {"status": "partial", "components": list(components), **run},
        },
    }


# An archive request that never connected: undici's TypeError has no code, so setup-io.mjs names it
# DOWNLOAD_FAILED and keeps the bare "fetch failed" message.
FETCH_FAILED = {
    "id": "gbdk",
    "status": "failed",
    "error": {
        "message": "fetch failed",
        "code": "DOWNLOAD_FAILED",
        "details": {
            "source": "https://github.com/gbdk-2020/gbdk-2020/releases/x.tar.gz",
            "attempt": 3,
            "quarantined": [],
        },
    },
}
# yarn (runSetupCommand) exited 1: the DNS failure is only in its captured output.
YARN_DNS = {
    "id": "cli",
    "status": "failed",
    "error": {
        "message": "GB Studio packages exited with 1; cleanup failures: none",
        "code": "COMMAND_FAILED",
        "execution": {
            "exitObserved": True,
            "pid": 4242,
            "exitCode": 1,
            "cleanupErrors": [],
            "stdoutTail": "➤ YN0001: │ RequestError: getaddrinfo EAI_AGAIN registry.npmjs.org\n➤ YN0000: └ Completed",
            "stderrTail": "",
        },
    },
}
# The same exit with the disk full, said only on stderr.
PIP_FULL = {
    "id": "emulator",
    "status": "failed",
    "error": {
        "message": "PyBoy install exited with 1; cleanup failures: none",
        "code": "COMMAND_FAILED",
        "execution": {
            "exitObserved": True,
            "exitCode": 1,
            "stdoutTail": "",
            "stderrTail": "OSError: [Errno 28] No space left on device",
        },
    },
}


class Classify(unittest.TestCase):
    def test_a_fetch_failed_download_is_a_network_failure(self):
        found = recovery.classify(incomplete(FETCH_FAILED), ROOT)
        self.assertEqual(found["code"], "NETWORK")
        self.assertIn("internet connection", found["hint"])

    def test_a_timed_out_download_is_a_network_failure(self):
        timeout = {
            "id": "uv",
            "status": "failed",
            "error": {"message": "The official archive download exceeded its time limit.", "code": "DOWNLOAD_TIMEOUT"},
        }
        self.assertEqual(recovery.classify(incomplete(timeout), ROOT)["code"], "NETWORK")

    def test_a_package_manager_dns_failure_is_read_from_its_captured_output(self):
        self.assertEqual(recovery.classify(incomplete(YARN_DNS), ROOT)["code"], "NETWORK")

    def test_a_full_disk_in_captured_output_is_no_space_even_beside_a_network_failure(self):
        self.assertEqual(recovery.classify(incomplete(FETCH_FAILED, PIP_FULL), ROOT)["code"], "NO_SPACE")

    def test_a_node_enospc_code_is_no_space(self):
        written = {"id": "gbdk", "status": "failed", "error": {"message": "write failed", "code": "ENOSPC"}}
        self.assertEqual(recovery.classify(incomplete(written), ROOT)["code"], "NO_SPACE")

    def test_the_whole_run_error_counts_too(self):
        run_error = {"message": "getaddrinfo ENOTFOUND github.com", "code": "ENOTFOUND"}
        self.assertEqual(recovery.classify(incomplete(error=run_error), ROOT)["code"], "NETWORK")

    def test_an_unrelated_failure_stays_unclassified(self):
        broken = {
            "id": "cli",
            "status": "failed",
            "error": {"message": "Prepared cli failed its explicit cli-version probe."},
        }
        self.assertEqual(
            recovery.classify(incomplete(broken), ROOT), {"code": None, "hint": None, "foreign_lock": False}
        )

    def test_the_plan_lock_is_another_installers(self):
        blocked = {
            "structuredContent": {
                "success": False,
                "stage": "blocked",
                "plan": {
                    "rootIssue": "An installer lock exists.",
                    "lock": {"path": "/t/toolchain/.setup-lock", "owner": None},
                },
            }
        }
        found = recovery.classify(blocked, ROOT)
        self.assertEqual((found["code"], found["foreign_lock"]), ("SETUP_LOCKED", True))
        self.assertIn("owner.json", found["hint"])

    def test_a_blocked_plan_without_a_lock_is_not_a_lock(self):
        other = {
            "structuredContent": {
                "success": False,
                "stage": "blocked",
                "plan": {"rootIssue": "This dependency root belongs to another installer."},
            }
        }
        self.assertFalse(recovery.classify(other, ROOT)["foreign_lock"])

    def test_only_a_bounded_tail_of_captured_output_is_read(self):
        noisy = json.loads(json.dumps(YARN_DNS))
        noisy["error"]["execution"]["stdoutTail"] = "getaddrinfo EAI_AGAIN\n" + "x" * 9000
        self.assertIsNone(recovery.classify(incomplete(noisy), ROOT)["code"])


class FreeSpace(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name) / "toolchain"

    def measured(self, free):
        with mock.patch.object(recovery.shutil, "disk_usage", return_value=mock.Mock(free=free)):
            return recovery.free_space(self.root)

    def test_a_missing_folder_needs_the_full_install(self):
        self.assertEqual(self.measured(10**12)["needed_bytes"], recovery.FRESH_HEADROOM)

    def test_an_empty_or_metadata_only_folder_needs_the_full_install(self):
        self.root.mkdir()
        self.assertFalse(self.measured(600_000_000)["enough"], "an empty folder is a first install")
        (self.root / ".gb-studio-setup.json").write_text("{}")
        (self.root / "last-run.json").write_text('{"status": "cancelled"}')
        (self.root / "staging").mkdir()
        (self.root / "receipts").mkdir()
        (self.root / "receipts" / "gbdk.json").write_text('{"status": "cancelled"}')
        space = self.measured(600_000_000)
        self.assertEqual((space["enough"], space["needed_bytes"]), (False, recovery.FRESH_HEADROOM))

    def test_reusable_parts_lower_the_estimate_with_a_warning(self):
        (self.root / "receipts").mkdir(parents=True)
        (self.root / "receipts" / "gbdk.json").write_text('{"status": "ready"}')
        space = self.measured(600_000_000)
        self.assertTrue(space["enough"])
        self.assertEqual(space["needed_bytes"], recovery.REPAIR_HEADROOM)
        self.assertIn("may fit", space["warning"])
        self.assertNotIn("warning", self.measured(10**12), "plenty of room is not uncertain")

    def test_cached_downloads_are_evidence_too(self):
        (self.root / "downloads").mkdir(parents=True)
        (self.root / "downloads" / "gbdk.tar.gz").write_bytes(b"x" * 10)
        self.assertEqual(self.measured(600_000_000)["estimate"], "reuse")

    def test_an_unmeasured_disk_is_a_warning_not_a_promise(self):
        with mock.patch.object(recovery.shutil, "disk_usage", side_effect=OSError("no statvfs")):
            space = recovery.free_space(self.root)
        self.assertTrue(space["enough"])
        self.assertIn("could not be measured", space["warning"])


if __name__ == "__main__":
    unittest.main()
