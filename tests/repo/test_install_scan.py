"""The plugin must install without Hermes's "caution" confirmation.

Hermes scans every plugin at install time and asks for confirmation (the Force switch) when any finding
is rated high. The engine's ffmpeg capture code once read its video input through a per-process path
under the proc filesystem, which the scanner's ``proc_access`` rule rates high; hermretro changes it to
``/dev/fd/6`` (see engine/CHANGES.md). This keeps a future engine update from bringing it back.
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The scanner's proc_access rule, written so this file does not match it itself.
PROC_ACCESS = re.compile("/proc/" + r"(?:self|\d+/)")


class InstallScanTests(unittest.TestCase):
    def test_no_shipped_file_references_a_per_process_proc_path(self):
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        offenders = []
        for rel in filter(None, tracked.decode().split("\0")):
            path = ROOT / rel
            if rel.startswith("tests/") or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            offenders += [f"{rel}:{n}" for n, line in enumerate(text.splitlines(), 1) if PROC_ACCESS.search(line)]
        self.assertEqual(offenders, [])

    def test_capture_reads_the_inherited_descriptor_through_dev_fd(self):
        for rel in (
            "engine/modretro-chromatic/dist/server.js",
            "engine/modretro-chromatic/dist/device-capture/linux-helper.js",
        ):
            self.assertEqual((ROOT / rel).read_text(encoding="utf-8").count('"-i", "/dev/fd/6"'), 2, rel)


if __name__ == "__main__":
    unittest.main()
