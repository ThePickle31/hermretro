"""Restoring a version requires an intact backup and an exclusive lock across processes.

Run alone: python -m unittest tests.backend.assets.test_asset_restore
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from backend.assets import rpcs as assets_rpcs
from backend.assets import versions as assets_versions
from tests.backend.assets.test_asset_versions import PNG_A, PNG_B, documented_keep, path_digest
from tests.support import isolated_home, make_library_game


class AssetRestore(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        _game, self.game = make_library_game(home, "Cat Field")
        self.cover = self.game / "cover.png"
        self.data = home.data
        self.params = {"root": str(self.game), "path": str(self.cover)}
        self.asset = assets_rpcs.rpc_asset(None)
        self.restore = assets_rpcs.rpc_asset_restore(None)

    def write(self, data, seconds):
        self.cover.write_bytes(data)
        os.utime(self.cover, ns=(seconds * 10**9, seconds * 10**9))

    def test_restore_leaves_current_bytes_in_place_if_the_backup_cannot_be_written(self):
        self.write(PNG_A, 1000)
        old_id = self.asset(self.params)["versionId"]
        self.write(PNG_B, 2000)
        folder = assets_versions._versions_dir(self.cover, self.game)
        original_replace = os.replace

        def fail_backup(source, destination):
            if Path(destination).parent == folder:
                raise OSError("backup disk full")
            return original_replace(source, destination)

        with (
            mock.patch.object(os, "replace", side_effect=fail_backup),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            answer = self.restore({**self.params, "version": old_id})
        self.assertFalse(answer["ok"], answer)
        self.assertIn("backup disk full", answer["error"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        self.assertEqual([item.name for item in folder.iterdir()], [f"{old_id}.png"])
        emit.assert_not_called()

    def test_restore_keeps_an_exclusive_lock_until_the_live_file_is_replaced(self):
        self.write(PNG_A, 1000)
        old_id = self.asset(self.params)["versionId"]
        (lock,) = (self.data / "asset-version-locks").iterdir()
        self.write(PNG_B, 2000)
        original_replace = os.replace

        def check_before_replace(source, destination):
            if Path(destination) == self.cover:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import fcntl, sys\n"
                        "with open(sys.argv[1], 'ab') as lock:\n"
                        "    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                        "    except BlockingIOError: sys.exit(0)\n"
                        "    sys.exit('asset lock was available during restore')\n",
                        str(lock),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            return original_replace(source, destination)

        with mock.patch.object(os, "replace", side_effect=check_before_replace) as replace:
            answer = self.restore({**self.params, "version": old_id})
        self.assertTrue(answer["ok"], answer)
        self.assertTrue(any(Path(call.args[1]) == self.cover for call in replace.call_args_list))

    def test_restore_at_the_cap_keeps_the_selected_version_and_what_it_replaced(self):
        limit = documented_keep()
        for index in range(limit):
            self.write(PNG_A[:24] + index.to_bytes(2, "big"), 1000 + index)
            self.assertTrue(self.asset(self.params)["ok"])
        self.write(PNG_B, 1000 + limit)
        outgoing = self.cover.read_bytes()
        selected_id = str(1000 * 10**9)
        outgoing_id = str((1000 + limit) * 10**9)
        restored = self.restore({**self.params, "version": selected_id})
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes()[24:], b"\x00\x00")
        self.assertEqual(len(restored["versions"]), limit)
        self.assertIn(selected_id, [entry["id"] for entry in restored["versions"]])
        self.assertIn(outgoing_id, [entry["id"] for entry in restored["versions"]])
        self.assertEqual(sum(entry["current"] for entry in restored["versions"]), 1)

        for at, version in ((1000, selected_id), (1000 + limit, outgoing_id)):
            shown = self.asset({**self.params, "at": at * 1000 + 500})
            self.assertTrue(shown["earlier"], shown)
            self.assertEqual(shown["versionId"], version)
            self.assertEqual(self.asset({**self.params, "version": version})["dataUrl"], shown["dataUrl"])

        undone = self.restore({**self.params, "version": outgoing_id})
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.cover.read_bytes(), outgoing)

    def test_restore_accepts_a_version_kept_before_history_was_filed_by_game(self):
        old_id = str(1000 * 10**9)
        legacy = self.data / "asset-versions" / path_digest(self.cover)
        legacy.mkdir(parents=True)
        (legacy / f"{old_id}.png").write_bytes(PNG_A)
        self.write(PNG_B, 2000)

        restored = self.restore({**self.params, "version": old_id})
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes(), PNG_A)
        self.assertFalse(legacy.exists())
        self.assertIn(old_id, [entry["id"] for entry in restored["versions"]])
