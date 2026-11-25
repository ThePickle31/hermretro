"""tools/engine/manifest.py: a checkout without the left-out files records the same release, and Python's bytecode is
never recorded."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "engine"))
_spec = importlib.util.spec_from_file_location("engine_manifest", ROOT / "tools" / "engine" / "manifest.py")
manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest)

ARCHIVE = "third-party/chromatic-cli/notices.br"
PINS = ROOT / "engine" / "pins"


class EngineManifestTests(unittest.TestCase):
    def engine(self, folder: Path, files: dict[str, str]) -> Path:
        (folder / "package.json").write_text('{"name": "modretro-chromatic", "version": "9.9.9"}')
        for rel, text in files.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text(text)
        return folder

    def test_a_left_out_file_keeps_its_recorded_entry(self):
        with tempfile.TemporaryDirectory() as full, tempfile.TemporaryDirectory() as checkout:
            recorded = manifest.build(
                self.engine(Path(full), {ARCHIVE: "packed", "dist/a-b.js": "1", "dist/a/b.js": "2"})
            )
            rebuilt = manifest.build(self.engine(Path(checkout), {"dist/a-b.js": "1", "dist/a/b.js": "2"}), recorded)
        self.assertEqual(rebuilt, {**recorded, "distribution_directory_name": rebuilt["distribution_directory_name"]})

    def test_only_left_out_files_are_kept(self):
        with tempfile.TemporaryDirectory() as full, tempfile.TemporaryDirectory() as checkout:
            recorded = manifest.build(self.engine(Path(full), {ARCHIVE: "packed", "dist/gone.js": "1"}))
            rebuilt = manifest.build(self.engine(Path(checkout), {}), recorded)
        self.assertEqual([e["path"] for e in rebuilt["entries"]], ["package.json", ARCHIVE])

    def test_a_left_out_file_that_is_present_is_hashed_as_it_is(self):
        with tempfile.TemporaryDirectory() as before, tempfile.TemporaryDirectory() as after:
            recorded = manifest.build(self.engine(Path(before), {ARCHIVE: "packed"}))
            rebuilt = manifest.build(self.engine(Path(after), {ARCHIVE: "repacked"}), recorded)
        entry = {e["path"]: e for e in rebuilt["entries"]}[ARCHIVE]
        self.assertEqual(entry["size"], len("repacked"))

    def test_an_edited_file_gets_its_new_hash(self):
        with tempfile.TemporaryDirectory() as before, tempfile.TemporaryDirectory() as after:
            recorded = manifest.build(self.engine(Path(before), {"dist/server.js": "old"}))
            rebuilt = manifest.build(self.engine(Path(after), {"dist/server.js": "new"}), recorded)
        self.assertNotEqual(rebuilt["aggregate_sha256"], recorded["aggregate_sha256"])

    def test_python_bytecode_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as clean, tempfile.TemporaryDirectory() as run:
            scripts = {"scripts/worker.py": "print(1)"}
            recorded = manifest.build(self.engine(Path(clean), scripts))
            cached = {
                "scripts/__pycache__/worker.cpython-314.pyc": "bytecode",
                "scripts/__pycache__/notes.txt": "kept with the cache",
                "scripts/old.pyc": "bytecode",
            }
            rebuilt = manifest.build(self.engine(Path(run), {**scripts, **cached}))
        self.assertEqual(rebuilt["aggregate_sha256"], recorded["aggregate_sha256"])

    def test_no_committed_manifest_lists_python_bytecode(self):
        for pin in sorted(PINS.glob("*/manifest.json")):
            listed = [
                e["path"]
                for e in json.loads(pin.read_text())["entries"]
                if any(manifest.paths.is_bytecode(name) for name in e["path"].split("/"))
            ]
            self.assertEqual(
                listed,
                [],
                f"{pin.relative_to(ROOT)} lists Python bytecode, which a clean checkout does not have. FIX: python "
                "tools/engine/manifest.py write (it skips __pycache__ and *.pyc) and commit the manifest",
            )


if __name__ == "__main__":
    unittest.main()
