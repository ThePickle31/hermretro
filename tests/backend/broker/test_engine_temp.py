"""The worker owns any compiler temp directory it allocates, even if startup fails."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.broker import engine
from backend.system import paths


class EngineTempLifetime(unittest.TestCase):
    def test_failed_spawn_removes_the_owned_fallback_and_preserves_inherited_environment(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = tempfile.TemporaryDirectory(dir=parent)
            self.addCleanup(directory.cleanup)
            inherited = {"TMPDIR": parent}
            worker = engine.EngineProcess(paths.ENGINE_ROOT, env=inherited)
            with (
                mock.patch.object(engine.host_os, "engine_tempdir", return_value=directory),
                mock.patch.object(engine.subprocess, "Popen", side_effect=FileNotFoundError("node missing")) as spawn,
            ):
                with self.assertRaisesRegex(FileNotFoundError, "node missing"):
                    worker.start()
            passed = spawn.call_args.kwargs["env"]
            self.assertEqual(
                {key: passed[key] for key in ("TMPDIR", "TMP", "TEMP")},
                dict.fromkeys(("TMPDIR", "TMP", "TEMP"), directory.name),
            )
            self.assertEqual(inherited, {"TMPDIR": parent})
            self.assertTrue(Path(parent).is_dir())
            self.assertFalse(Path(directory.name).exists())
            self.assertIsNone(worker.close())
