"""Putting an updated installed game in place (backend/library/install_swap.py): carrying the user's files, merging
folders, conflicts, and putting everything back when a step fails.

Run alone: python -m unittest tests.backend.library.test_install_swap
"""

import contextlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import game_card, install_swap, layout  # noqa: E402 - the repository root goes on sys.path first
from backend.library.install_swap import SwapError  # noqa: E402
from backend.system import paths  # noqa: E402
from tests.support import isolated_home, make_game_folder  # noqa: E402


class FakeRegistry:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name, *args))
            if name == self.fail:
                raise OSError(f"{name} failed")
            return ("old-id", "new-id") if name == "move" else None

        return record


def tree(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): path.read_bytes().decode("latin-1")
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".hermretro" not in path.parts
    }


class Swap(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.games = self.home.base / "games"
        self.root = make_game_folder(self.games / "Space Game", source=True)
        layout.ensure(self.root)
        self.staging = self.games / ".install-x"
        self.new = make_game_folder(self.staging / "game", source=True)
        layout.ensure(self.new)
        (self.new / "project" / "scene.gbsres").write_text('{"v": 2}')
        self.lock = contextlib.nullcontext

    def test_the_users_folders_merge_and_conflicts_keep_both_copies(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "plan.md").write_text("plan")
        (self.root / "build" / "game.sym").write_text("symbols")
        (self.root / "build" / "game.gbc").write_text("the old ROM")  # never carried: the update brings its own
        theirs = (self.new / "build" / "game.gbc").read_bytes().decode("latin-1")
        (self.root / "build" / "web").mkdir()
        (self.root / "build" / "web" / "index.html").write_text("old export")
        (self.root / "captures").mkdir()
        (self.root / "captures" / "SHOT.png").write_text("mine")
        (self.new / "captures").mkdir()  # an update with a file of that name, letter case aside
        (self.new / "captures" / "shot.png").write_text("theirs")
        (self.new / "Docs").mkdir()  # an update that brings a folder of that name (letter case aside)
        (self.new / "Docs" / "plan.md").write_text("theirs")
        result = install_swap.replace(self.root, self.new, self.staging, self.lock, FakeRegistry())
        files = tree(self.root)
        self.assertEqual(files["Docs/plan.md"], "theirs")
        self.assertEqual(files["Docs/plan (yours).md"], "plan")
        self.assertEqual((files["build/game.sym"], files["build/game.gbc"]), ("symbols", theirs))
        self.assertEqual([name for name in files if name.lower().startswith("build/game (")], [])
        self.assertEqual((files["captures/shot.png"], files["captures/SHOT (yours).png"]), ("theirs", "mine"))
        self.assertNotIn("build/web/index.html", files)
        self.assertEqual(files["project/scene.gbsres"], '{"v": 2}')
        self.assertEqual(len(result["kept"]), 2)
        self.assertFalse((self.staging / "previous").exists())

    def test_the_lock_file_held_while_updating_carries_over(self):
        before = os.stat(self.root / ".hermretro" / "folder.lock").st_ino
        install_swap.replace(self.root, self.new, self.staging, self.lock, FakeRegistry())
        self.assertEqual(os.stat(self.root / ".hermretro" / "folder.lock").st_ino, before)

    def failing_at(self, step):
        """Run replace with ``step`` failing; the user's game must be exactly as it was."""
        (self.root / "docs").mkdir()
        (self.root / "docs" / "plan.md").write_text("plan")
        before = tree(self.root)
        real_rename = os.rename

        def rename(source, target):
            if step == "into_place" and Path(source) == self.new:
                raise OSError("disk error")
            return real_rename(source, target)

        carry = install_swap.carry
        if step == "carry":

            def carry(old, new, moved, kept):
                install_swap.carry.__wrapped__(old, new, moved, kept)
                raise OSError("disk error")

            carry.__wrapped__ = install_swap.carry
        with (
            mock.patch.object(install_swap.os, "rename", side_effect=rename),
            mock.patch.object(install_swap, "carry", side_effect=carry),
            self.assertRaises(SwapError) as failed,
        ):
            install_swap.replace(self.root, self.new, self.staging, self.lock, FakeRegistry())
        self.assertEqual(failed.exception.code, "SWAP_FAILED")
        self.assertEqual(tree(self.root), before)

    def test_a_failed_carry_puts_everything_back(self):
        self.failing_at("carry")

    def test_a_failed_move_into_place_puts_everything_back(self):
        self.failing_at("into_place")

    def test_when_even_putting_back_fails_the_old_copy_is_kept_safe(self):
        real_rename = os.rename

        def rename(source, target):
            if Path(source) == self.new or (Path(target) == self.root and "previous" in str(source)):
                raise OSError("disk error")
            return real_rename(source, target)

        with mock.patch.object(install_swap.os, "rename", side_effect=rename), self.assertRaises(SwapError) as failed:
            install_swap.replace(self.root, self.new, self.staging, self.lock, FakeRegistry())
        self.assertEqual(failed.exception.code, "RECOVERY_NEEDED")
        kept = Path(failed.exception.details["kept"])
        self.assertEqual(json.loads((kept / "game.json").read_text())["title"], "Space Game")
        self.assertIn(str(kept), failed.exception.message)

    def test_a_failed_registration_keeps_the_old_copy(self):
        with self.assertRaises(SwapError) as failed:
            install_swap.replace(self.root, self.new, self.staging, self.lock, FakeRegistry(fail="upsert"))
        self.assertEqual(failed.exception.code, "RECOVERY_NEEDED")
        self.assertTrue((Path(failed.exception.details["kept"]) / "game.json").is_file())
        self.assertEqual(json.loads((self.root / "project" / "scene.gbsres").read_text()), {"v": 2})

    def test_keep_both_puts_the_remix_identity_back_when_a_step_fails(self):
        template = (paths.ENGINE_ROOT / "examples" / "starter" / "LICENSE").read_bytes()
        (self.root / "LICENSE").write_bytes(template)  # the remix's ensure would write the card's licence over it
        game_card.set_fields(self.root, {"license": "MIT"})
        layout.write_state(self.root, layout.INSTALL_FILE, {"source": "x", "commit": "c" * 40, "mode": "game+source"})
        card = (self.root / "game.json").read_text()
        remix = self.games / "Space Game (edited)"
        real_rename = os.rename

        def rename(source, target):
            if Path(source) == self.new:
                raise OSError("disk error")
            return real_rename(source, target)

        with mock.patch.object(install_swap.os, "rename", side_effect=rename), self.assertRaises(SwapError):
            install_swap.keep_both(self.root, self.new, lambda: remix, self.lock, FakeRegistry())
        self.assertEqual((self.root / "game.json").read_text(), card)
        self.assertEqual((self.root / "LICENSE").read_bytes(), template, "the author's LICENSE is put back too")
        self.assertEqual(layout.game_identity(self.root), "ab" * 16)
        self.assertFalse(remix.exists())

    def test_keep_both_moves_the_library_entry_and_tells_history(self):
        remix = self.games / "Space Game (edited)"
        registry = FakeRegistry()
        with mock.patch.object(install_swap, "emit") as emitted:
            install_swap.keep_both(self.root, self.new, lambda: remix, self.lock, registry)
        self.assertEqual([call[0] for call in registry.calls], ["move", "upsert"])
        emitted.assert_called_once_with(
            "library.game_moved", old="old-id", new="new-id", old_root=str(self.root), new_root=str(remix)
        )
        self.assertNotEqual(layout.game_identity(remix), layout.game_identity(self.root))


if __name__ == "__main__":
    unittest.main()
