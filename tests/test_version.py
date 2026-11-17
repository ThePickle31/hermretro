"""The plugin's version lives in plugin.yaml and nowhere else, so a release changes one line."""
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapter import paths  # noqa: E402

# Where the version may legitimately appear as text: the manifest itself, the vendored engine (its own
# versions), lockfiles, generated bundles and the README's note about upgrading from older versions.
ALLOWED = ("plugin.yaml", "engine/", "release/", "tools/npm/package-lock.json", "desktop/plugin.js",
           "player/frame-shim.js")


class OneVersion(unittest.TestCase):
    def test_the_adapter_reads_its_version_from_plugin_yaml(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^version:", manifest, re.MULTILINE)), 1, "one top-level version line")
        self.assertEqual(paths.PLUGIN_VERSION, paths._manifest_version(ROOT / "plugin.yaml"))

    def test_the_version_line_may_be_quoted_or_commented_but_must_be_x_y_z(self):
        for line, expected in (("version: 0.0.5", "0.0.5"), ('version: "0.0.5"', "0.0.5"),
                               ("version: 0.0.5  # next", "0.0.5"), ("version: 0.0.5\r", "0.0.5"),
                               ("version: 1.0", None), ("version: v0.0.5", None)):
            match = re.search(paths.VERSION_LINE, f"name: hermretro\n{line}\n", re.MULTILINE)
            self.assertEqual(match.group(1) if match else None, expected, line)

    def test_a_new_version_on_disk_changes_the_broker_fingerprint(self):
        # A gateway that imported an older version must still agree with a broker started from the new files.
        with mock.patch.object(paths, "_fingerprint_for", return_value="x") as fingerprint:
            paths.code_fingerprint()
        stamp = fingerprint.call_args.args[0]
        self.assertIn("../plugin.yaml", [name for name, _mtime, _size in stamp])

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
            if name.startswith(ALLOWED) or name == "tests/test_version.py" or not (ROOT / name).is_file():
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line) and not line.startswith("Upgrading from "):
                    found.append(f"{name}:{number}")
        self.assertEqual(found, [], f"the version {paths.PLUGIN_VERSION} is repeated; read it from plugin.yaml "
                                    "(adapter: paths.PLUGIN_VERSION; page: status.plugin.version)")


if __name__ == "__main__":
    unittest.main()
