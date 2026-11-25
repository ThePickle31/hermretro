"""Hermes's file tools write into a library game's folder only from that game's own conversation.

Run alone: python -m unittest tests.backend.library.test_game_files_guard
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import file_guard, games, hooks, layout  # noqa: E402 - the repository root goes on sys.path first
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

    def test_another_games_conversation_is_refused_and_told_how_to_get_there(self):
        hermes_host._registry().bind(self.b, "chat-b", PROFILE)
        answer = self.write(self.root_a / "notes.txt", "chat-b")
        self.assertEqual(answer["action"], "block")
        self.assertIn("Cat Field", answer["message"])
        self.assertIn("Sky Loop", answer["message"])
        self.assertIn("open it on the hermretro Build page", answer["message"])

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

    def test_dot_dot_is_read_both_ways(self):
        # <base>/hop -> <root_b>/deep; "hop/../x" is <base>/x by spelling, but <root_b>/x through the link: whichever
        # reading the writer uses, it must not land in another game.
        (self.root_b / "deep").mkdir()
        (self.home.base / "hop").symlink_to(self.root_b / "deep", target_is_directory=True)
        self.assertTrue(self.blocked(f"{self.home.base}/hop/../outside.txt", "plain-chat"))
        (self.root_a.parent / "in-b").symlink_to(self.root_b, target_is_directory=True)
        self.assertTrue(self.blocked(f"{self.root_a}/../in-b/notes.txt", "chat-a"))
        self.assertIsNone(self.write(f"{self.root_a}/docs/../notes.txt", "chat-a"))

    def test_every_file_a_patch_names_is_checked_in_hermes_grammar(self):
        two = (
            "*** Begin Patch\n"
            f"*** Update File: {self.root_a / 'notes.txt'}\n@@\n-a\n+b\n"
            f"***  Add  File:   {self.root_b / 'stolen.txt'}\n+x\n"
            "*** End Patch"
        )
        self.assertTrue(self.blocked(two, "chat-a", tool="patch"))
        own = f"*** Begin Patch\n*** Update File: {self.root_a / 'notes.txt'}\n@@\n-a\n+b\n*** End Patch"
        self.assertFalse(self.blocked(own, "chat-a", tool="patch"))
        for move in (
            f"*** Move File: {self.root_a / 'notes.txt'} -> {self.root_b / 'notes.txt'}",
            f"***Move File:{self.root_b / 'notes.txt'}->{self.root_a / 'notes.txt'}",
        ):
            with self.subTest(move=move):
                self.assertTrue(self.blocked(f"*** Begin Patch\n{move}\n*** End Patch", "chat-a", tool="patch"))
        inside = f"*** Begin Patch\n*** Move File: {self.root_a / 'a.txt'} -> {self.root_a / 'b.txt'}\n*** End Patch"
        self.assertFalse(self.blocked(inside, "chat-a", tool="patch"))
        bare = f"*** Delete File: {self.root_b / 'notes.txt'}"  # no Begin marker: read from the top, as Hermes does
        self.assertTrue(self.blocked(bare, "chat-a", tool="patch"))
        after = f"*** Begin Patch\n*** End Patch\n*** Delete File: {self.root_b / 'notes.txt'}"
        self.assertFalse(self.blocked(after, "chat-a", tool="patch"))  # past End: Hermes ignores it too

    def test_a_delete_or_move_acts_on_the_link_itself_not_its_target(self):
        mine = self.root_a / "link-to-b"
        mine.symlink_to(self.root_b / "game.json")
        delete = f"*** Begin Patch\n*** Delete File: {mine}\n*** End Patch"
        self.assertFalse(self.blocked(delete, "chat-a", tool="patch"))  # removes A's own link, not B's file
        theirs = self.home.base / "link-to-a"
        theirs.symlink_to(self.root_a / "game.json")
        hermes_host._registry().bind(self.b, "chat-b", PROFILE)
        move = f"*** Begin Patch\n*** Move File: {self.root_b / 'x'} -> {theirs}\n*** End Patch"
        self.assertTrue(self.blocked(move, "chat-b", tool="patch"))  # writing through the link lands in A

    def test_a_record_folder_linked_elsewhere_stays_closed(self):
        elsewhere = self.home.base / "kept"
        elsewhere.mkdir()
        (elsewhere / "record").mkdir()
        (self.root_a / ".hermretro").symlink_to(elsewhere / "record", target_is_directory=True)
        self.assertTrue(self.blocked(elsewhere / "record" / "identity.json", "chat-a"))
        self.assertTrue(self.blocked(self.root_a / ".hermretro" / "identity.json", "chat-a"))

    def test_a_project_inside_a_games_folder_belongs_to_the_deepest_game(self):
        inner = make_project(self.root_a, "Inner")
        inner_id = hermes_host._registry().upsert(str(inner))["id"]
        hermes_host._registry().bind(inner_id, "chat-inner", PROFILE)
        self.assertIsNone(self.write(inner / "notes.txt", "chat-inner"))
        self.assertTrue(self.blocked(inner / "notes.txt", "chat-a"))
        self.assertTrue(self.blocked(self.root_a / "notes.txt", "chat-inner"))

    def test_folders_are_matched_by_identity_so_a_name_differing_by_case_is_another_folder(self):
        twin = self.root_b.with_name(self.root_b.name.upper())
        if os.path.exists(twin):
            self.skipTest("this volume ignores letter case")
        twin.mkdir()
        self.assertIsNone(self.write(twin / "notes.txt", "plain-chat"))

    @unittest.skipUnless(sys.platform == "darwin", "macOS volumes usually ignore letter case")
    def test_letter_case_does_not_hide_a_game_on_a_case_insensitive_volume(self):
        upper = Path(str(self.root_b).upper())
        if not upper.exists():
            self.skipTest("this volume keeps letter case apart")
        self.assertTrue(self.blocked(upper / "notes.txt", "chat-a"))

    def test_relative_and_home_paths_are_refused_whatever_the_working_folder(self):
        # Hermes reads them against the chat's own working folder (a terminal cd, a Desktop override), which a hook
        # cannot see: the agent is asked for the full path instead.
        outside = self.home.base / "outside"
        outside.mkdir()
        for cwd in (str(self.root_b), str(outside), str(self.root_a)):
            with self.subTest(cwd=cwd), mock.patch.dict(os.environ, {"TERMINAL_CWD": cwd}):
                for path in ("notes.txt", "../Sky Loop/notes.txt", "~/notes.txt"):
                    answer = self.write(path, "chat-a")
                    self.assertEqual(answer["action"], "block")
                    self.assertIn("absolute", answer["message"])
        patch = "*** Begin Patch\n*** Add File: notes.txt\n+x\n*** End Patch"
        self.assertTrue(self.blocked(patch, "chat-a", tool="patch"))

    def test_a_game_installed_without_its_source_is_never_edited(self):
        layout.write_state(self.root_a, layout.INSTALL_FILE, {"repo": "x/y", "commit": "0" * 40, "source": False})
        answer = self.write(self.root_a / "notes.txt", "chat-a")  # even from its own conversation
        self.assertEqual(answer["action"], "block")
        self.assertIn("without its source", answer["message"])

    def test_an_unreadable_library_refuses_file_writes(self):
        registry = hermes_host._registry()
        registry.path.write_text("{")
        answer = self.write(self.home.base / "anywhere.txt", "chat-a")
        self.assertEqual(answer["action"], "block")
        self.assertIn("could not be read", answer["message"])

    def test_a_missing_library_is_an_empty_one(self):
        hermes_host._registry().path.unlink()
        self.assertIsNone(self.write(self.root_a / "notes.txt", "plain-chat"))

    def test_one_registry_read_serves_a_whole_patch(self):
        patch = (
            "*** Begin Patch\n"
            + "".join(f"*** Update File: {self.root_a / f'n{index}.txt'}\n@@\n-a\n+b\n" for index in range(5))
            + "*** End Patch"
        )
        with mock.patch.object(games.Registry, "load", autospec=True, side_effect=games.Registry.load) as load:
            self.assertFalse(self.blocked(patch, "chat-a", tool="patch"))
        self.assertEqual(load.call_count, 1)

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


class PatchGrammar(unittest.TestCase):
    def test_targets_follow_hermes_v4a_markers(self):
        text = (
            "intro\n*** Begin Patch\r\n*** Update File: /a\n@@ hint @@\n-x\n+*** Add File: /not-an-op\n"
            "*** Delete File:   /b  \n*** Move File: /c -> /d\n*** End Patch\n*** Add File: /after"
        )
        self.assertEqual(
            file_guard.patch_targets(text), [("/a", False), ("/b", True), ("/c", True), ("/d", True), ("/d", False)]
        )
        self.assertEqual(json.loads(json.dumps(file_guard.patch_targets(""))), [])


if __name__ == "__main__":
    unittest.main()
