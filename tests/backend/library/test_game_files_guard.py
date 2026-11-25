"""Hermes's file tools write into a library game's folder only from that game's own conversation.

Run alone: python -m unittest tests.backend.library.test_game_files_guard
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_library_game, make_project  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/hermretro"


class GameFilesGuard(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        patch = mock.patch.object(hermes_host, "_profile_identity", lambda: PROFILE)
        patch.start()
        self.addCleanup(patch.stop)
        self.a, self.root_a = make_library_game(self.home, "Cat Field", chat="chat-a")
        self.b, self.root_b = make_library_game(self.home, "Sky Loop")  # no conversation yet
        hermes_host._registry().build_start("chat-new", PROFILE)

    def write(self, path, chat, *, tool="write_file", session=None):
        args = {"path": str(path), "content": "x"} if tool == "write_file" else {"mode": "patch", "patch": path}
        return hooks.guard_game_record(tool_name=tool, args=args, conversation_id=chat, session_id=session or chat)

    def blocked(self, *args, **kwargs):
        answer = self.write(*args, **kwargs)
        return isinstance(answer, dict) and answer.get("action") == "block"

    def test_a_games_own_conversation_writes_its_files(self):
        for name in ("docs/game/GAME-BRIEF.md", "art/hero.png", "scratch/ops.json", "notes.txt"):
            with self.subTest(name=name):
                self.assertIsNone(self.write(self.root_a / name, "chat-a"))

    def test_a_rotated_session_id_is_still_the_games_conversation(self):
        hermes_host._registry().note_alias(PROFILE, "chat-a", "chat-a-2")
        self.assertIsNone(self.write(self.root_a / "notes.txt", "", session="chat-a-2"))

    def test_another_games_conversation_is_refused(self):
        hermes_host._registry().bind(self.b, "chat-b", PROFILE)
        answer = self.write(self.root_a / "notes.txt", "chat-b")
        self.assertEqual(answer["action"], "block")
        self.assertIn("Cat Field", answer["message"])
        self.assertIn("Sky Loop", answer["message"])

    def test_a_plain_chat_and_a_new_game_chat_are_refused(self):
        for chat in ("plain-chat", "chat-new", ""):
            with self.subTest(chat=chat):
                answer = self.write(self.root_a / "project" / "scene.gbsres", chat)
                self.assertEqual(answer["action"], "block")
                self.assertIn("Build page", answer["message"])

    def test_a_game_with_no_conversation_is_refused_to_every_chat(self):
        for chat in ("plain-chat", "chat-a", "chat-new"):
            with self.subTest(chat=chat):
                self.assertTrue(self.blocked(self.root_b / "notes.txt", chat))

    def test_a_link_into_another_game_is_followed(self):
        link = self.home.base / "shortcut"
        link.symlink_to(self.root_b, target_is_directory=True)
        self.assertTrue(self.blocked(link / "notes.txt", "chat-a"))
        own = self.home.base / "mine"
        own.symlink_to(self.root_a, target_is_directory=True)
        self.assertIsNone(self.write(own / "notes.txt", "chat-a"))

    def test_every_file_a_patch_names_is_checked(self):
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {self.root_a / 'notes.txt'}\n@@\n-a\n+b\n"
            f"*** Add File: {self.root_b / 'stolen.txt'}\n+x\n"
            "*** End Patch"
        )
        self.assertTrue(self.blocked(patch, "chat-a", tool="patch"))
        own = f"*** Begin Patch\n*** Update File: {self.root_a / 'notes.txt'}\n@@\n-a\n+b\n*** End Patch"
        self.assertFalse(self.blocked(own, "chat-a", tool="patch"))
        moved = (
            f"*** Begin Patch\n*** Update File: {self.root_a / 'notes.txt'}\n"
            f"*** Move to: {self.root_b / 'notes.txt'}\n@@\n-a\n+b\n*** End Patch"
        )
        self.assertTrue(self.blocked(moved, "chat-a", tool="patch"))

    def test_a_project_inside_a_games_folder_belongs_to_the_deepest_game(self):
        inner = make_project(self.root_a, "Inner")
        inner_id = hermes_host._registry().upsert(str(inner))["id"]
        hermes_host._registry().bind(inner_id, "chat-inner", PROFILE)
        self.assertIsNone(self.write(inner / "notes.txt", "chat-inner"))
        self.assertTrue(self.blocked(inner / "notes.txt", "chat-a"))
        self.assertTrue(self.blocked(self.root_a / "notes.txt", "chat-inner"))

    def test_a_relative_path_is_read_against_the_terminal_folder(self):
        with mock.patch.dict(os.environ, {"TERMINAL_CWD": str(self.root_b)}):
            self.assertTrue(self.blocked("notes.txt", "chat-a"))
        with mock.patch.dict(os.environ, {"TERMINAL_CWD": str(self.root_a)}):
            self.assertIsNone(self.write("notes.txt", "chat-a"))

    def test_writes_outside_every_game_and_other_tools_are_left_alone(self):
        elsewhere = self.home.base / "notes" / "plan.md"
        for chat in ("plain-chat", "chat-new", "chat-a"):
            with self.subTest(chat=chat):
                self.assertIsNone(self.write(elsewhere, chat))
        self.assertIsNone(
            hooks.guard_game_record(
                tool_name="read_file", args={"path": str(self.root_b / "game.json")}, conversation_id="plain-chat"
            )
        )

    def test_the_games_record_stays_closed_even_to_its_own_conversation(self):
        self.assertTrue(self.blocked(self.root_a / ".hermretro" / "identity.json", "chat-a"))

    @unittest.skipUnless(sys.platform == "darwin", "macOS file systems ignore letter case")
    def test_letter_case_does_not_hide_a_game_on_macos(self):
        self.assertTrue(self.blocked(Path(str(self.root_b).upper()) / "notes.txt", "chat-a"))


if __name__ == "__main__":
    unittest.main()
