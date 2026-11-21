"""The plugin's version lives in plugin.yaml and nowhere else, so a release changes one line."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

# Where the version may legitimately appear as text: the manifest itself, the vendored engine (its own
# versions), lockfiles, generated bundles and the README's note about upgrading from older versions.
ALLOWED = ("plugin.yaml", "engine/", "tools/npm/package-lock.json", "desktop/plugin.js", "player/frame-shim.js")


class OneVersion(unittest.TestCase):
    def test_the_backend_reads_its_version_from_plugin_yaml(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^version:", manifest, re.MULTILINE)), 1, "one top-level version line")
        self.assertEqual(paths.PLUGIN_VERSION, paths._manifest_version(ROOT / "plugin.yaml"))

    def test_the_version_line_may_be_quoted_or_commented_but_must_be_x_y_z(self):
        for line, expected in (
            ("version: 0.0.5", "0.0.5"),
            ('version: "0.0.5"', "0.0.5"),
            ("version: 0.0.5  # next", "0.0.5"),
            ("version: 0.0.5\r", "0.0.5"),
            ("version: 1.0", None),
            ("version: v0.0.5", None),
        ):
            match = re.search(paths.VERSION_LINE, f"name: hermretro\n{line}\n", re.MULTILINE)
            self.assertEqual(match.group(1) if match else None, expected, line)

    def test_a_new_version_on_disk_changes_the_broker_fingerprint(self):
        # The fingerprint hashes plugin.yaml's bytes: two trees that differ only in the version must not agree,
        # or a gateway would keep talking to a broker started from the old files.
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "backend").mkdir()
            (base / "backend" / "one.py").write_bytes(b"x = 1\n")
            manifest = base / "plugin.yaml"
            manifest.write_text("name: hermretro\nversion: 0.0.5\n", encoding="utf-8")
            # Explicit, distinct stamps: the fingerprint is cached per file stamp, so a rewrite with the same
            # mtime and size could be served from the cache and say nothing about the manifest's bytes.
            os.utime(base / "backend" / "one.py", ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
            os.utime(manifest, ns=(1_600_000_100_000_000_000, 1_600_000_100_000_000_000))
            with mock.patch.object(paths, "BACKEND_ROOT", base / "backend"):
                paths._fingerprint_for.cache_clear()
                try:
                    # The gateway's own call, not the cache's key: if code_fingerprint stops including the
                    # manifest, this pair agrees although the version changed.
                    old = paths.code_fingerprint()
                    manifest.write_text("name: hermretro\nversion: 0.0.6\n", encoding="utf-8")
                    os.utime(manifest, ns=(1_600_000_200_000_000_000, 1_600_000_200_000_000_000))
                    new = paths.code_fingerprint()  # no cache clear: a new stamp is the miss
                finally:
                    paths._fingerprint_for.cache_clear()
        self.assertNotEqual(old, new)

    def test_no_other_file_repeats_the_version(self):
        try:
            listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
        except FileNotFoundError:
            self.skipTest("git is not installed")
        if listed.returncode:
            self.skipTest("not a git checkout")
        pattern = re.compile(rf"(?<![0-9.]){re.escape(paths.PLUGIN_VERSION)}(?![0-9])")
        found = []
        for name in listed.stdout.splitlines():
            # This file's own examples are versions too; it never ships a version.
            if name.startswith(ALLOWED) or name == "tests/repo/test_version.py" or not (ROOT / name).is_file():
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line) and not line.startswith("Upgrading from "):
                    found.append(f"{name}:{number}")
        self.assertEqual(
            found,
            [],
            f"the version {paths.PLUGIN_VERSION} is repeated; read it from plugin.yaml "
            "(backend: paths.PLUGIN_VERSION; page: status.plugin.version)",
        )


if __name__ == "__main__":
    unittest.main()
