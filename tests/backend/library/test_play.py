"""What an installed game plays (backend/library/play.py): its ROM in the player's shell, never a web export.

Run alone: python -m unittest tests.backend.library.test_play
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend import library  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host  # noqa: E402
from backend.library import layout, play  # noqa: E402
from tests.support import isolated_home, make_installed_game, make_library_game, make_rom  # noqa: E402


class ShellRom(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def game(self, identifier):
        [game] = [g for g in host._registry().library() if g["id"] == identifier]
        return game

    def test_a_game_without_its_source_plays_the_rom_its_install_checked(self):
        identifier, root = make_installed_game(self.home)
        checked = library.installed_rom(root)
        self.assertTrue(play.plays_in_shell(root))
        self.assertEqual(play.shell_rom(root), Path(checked["romPath"]))
        game = self.game(identifier)
        self.assertTrue(game["webExport"])
        self.assertEqual(game["web"]["sha256"], checked["sha256"])
        self.assertEqual(game["state"], "ready")
        self.assertTrue(game["shell"])

    def test_a_changed_rom_plays_nothing_and_says_why(self):
        identifier, root = make_installed_game(self.home)
        (root / "build" / "game.gbc").write_bytes(make_rom(fill=7))
        self.assertIsNone(play.shell_rom(root))
        self.assertIn("installed with", play.no_shell_rom(root))
        game = self.game(identifier)
        self.assertEqual((game["state"], game["rom"], game["webExport"]), ("romChanged", None, False))

    def test_a_game_alone_never_offers_another_rom_or_a_build(self):
        identifier, root = make_installed_game(self.home)
        (root / "build" / "game.gb").write_bytes(make_rom(colour=False, fill=2))  # some other, newer file
        (root / "notes.txt").write_text("newer than the ROM")
        game = self.game(identifier)
        self.assertEqual(game["state"], "ready")
        self.assertEqual(game["rom"]["path"], str(root / "build" / "game.gbc"))
        self.assertEqual(game["rom"]["sha256"], game["install"]["romSha256"])

    def test_the_edited_copy_an_update_kept_still_plays_its_checked_rom(self):
        _identifier, root = make_installed_game(self.home)
        kept = play.rom_only_record(root)
        layout.new_identity(root, fresh_changelog=False)  # what keep_both makes of the edited copy
        self.assertFalse(play.is_installed(root))
        play.keep_rom(root, kept)
        self.assertTrue(play.plays_in_shell(root))
        self.assertEqual(play.verified(root)["sha256"], kept["sha256"])
        (root / "build" / "game.gbc").write_bytes(make_rom(fill=8))
        self.assertIsNone(play.verified(root))

    def test_a_game_with_its_source_plays_its_own_rom_not_a_web_export(self):
        _identifier, root = make_installed_game(self.home, source=True)
        (root / "build" / "web").mkdir()
        (root / "build" / "web" / "index.html").write_text("<script>author()</script>")
        self.assertTrue(play.plays_in_shell(root))
        self.assertEqual(play.shell_rom(root), root / "build" / "game.gbc")

    def test_an_installed_game_is_current_without_a_web_copy(self):
        _identifier, root = make_installed_game(self.home)
        self.assertEqual(play.playable_freshness(root), (True, None, None))
        (root / "build" / "game.gbc").write_bytes(make_rom(fill=7))
        fresh, why, _next = play.playable_freshness(root)
        self.assertFalse(fresh)
        self.assertIn("installed with", why)
        self.assertFalse(play.playable_intact(root))

    def test_an_installed_game_with_its_source_wants_a_build_after_an_edit(self):
        _identifier, root = make_installed_game(self.home, source=True)
        self.assertTrue(play.playable_freshness(root)[0])
        rom = root / "build" / "game.gbc"
        scene = root / "project" / "scene.gbsres"
        scene.write_text("{}")
        os.utime(scene, (rom.stat().st_mtime + 10, rom.stat().st_mtime + 10))
        fresh, _why, next_step = play.playable_freshness(root)
        self.assertFalse(fresh)
        self.assertEqual(next_step, play.ROM_BUILD)

    def test_present_shows_a_game_alone_without_asking_for_a_build(self):
        from backend.library import tools as library_tools

        identifier, root = make_installed_game(self.home, chat="c1")
        with (
            mock.patch.object(host, "_chat_project", lambda *_ids: str(root)),
            mock.patch.object(
                library_tools.player_server, "get_server", **{"return_value.play_url.return_value": "http://x/"}
            ),
        ):
            shown = json.loads(library_tools.present_game_handler({}, conversation_id="c1", session_id="s1"))
        self.assertTrue(shown["ok"], shown)
        self.assertEqual(shown["studio"]["gameId"], identifier)

    def test_the_beside_chat_status_carries_the_same_provenance(self):
        from backend.library import rpcs as library_rpcs

        identifier, root = make_installed_game(self.home)
        ctx = mock.Mock()
        ctx.get_config.return_value = False
        status = library_rpcs.rpc_game_build_status(ctx)({"id": identifier})
        self.assertTrue(status["ok"], status)
        game = status["game"]
        self.assertTrue(game["shell"])
        self.assertEqual(game["install"]["romSha256"], game["rom"]["sha256"])

    def test_a_game_made_here_plays_its_web_export(self):
        identifier, root = make_library_game(self.home)
        self.assertFalse(play.plays_in_shell(root))
        self.assertNotIn("shell", self.game(identifier))


if __name__ == "__main__":
    unittest.main()
