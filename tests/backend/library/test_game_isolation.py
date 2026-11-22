"""Several games made at once, each in its own Build conversation: a game's chat acts on its own game only, and no
other chat can become the one that finds it.

Run alone: python -m unittest tests.backend.library.test_game_isolation
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.support import FakeBrokerClient, isolated_home, make_library_game  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/hermretro"


class TwoGamesAtOnce(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        for patch in (
            mock.patch.object(hermes_host, "_profile_identity", lambda: PROFILE),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.a, self.root_a = make_library_game(self.home, "Cat Field")
        self.b, self.root_b = make_library_game(self.home, "Sky Loop")
        registry = hermes_host._registry()
        registry.bind(self.a, "chat-a", PROFILE)
        registry.bind(self.b, "chat-b", PROFILE)

    def info(self, args, chat):
        return json.loads(library_tools.game_info_handler(args, conversation_id=chat, session_id=chat))

    def present(self, args, chat):
        return json.loads(library_tools.present_game_handler(args, conversation_id=chat, session_id=chat))

    def test_each_chat_finds_its_own_game(self):
        self.assertEqual(hermes_host._chat_project("chat-a", "chat-a"), str(self.root_a))
        self.assertEqual(hermes_host._chat_project("chat-b", "run-2"), str(self.root_b))

    def test_a_game_chat_cannot_touch_another_game(self):
        before = (self.root_a / "game.json").read_text()
        refused = self.info({"project": str(self.root_a), "tagline": "Someone else's tagline here"}, "chat-b")
        self.assertEqual(refused["code"], "ONE_GAME_PER_CONVERSATION")
        self.assertIn("Leave out project", refused["nextStep"])
        self.assertEqual((self.root_a / "game.json").read_text(), before)
        self.assertEqual(self.present({"project": str(self.root_a)}, "chat-b")["code"], "ONE_GAME_PER_CONVERSATION")
        self.assertEqual(hermes_host._registry().presentations(), [])

    def test_naming_its_own_game_is_fine(self):
        self.assertTrue(self.present({"project": str(self.root_b)}, "chat-b")["ok"])

    def test_the_lane_of_another_game_never_outranks_the_binding(self):
        client = FakeBrokerClient({"ok": True, "matched": "chat", "lane": {"project_root": str(self.root_a)}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            self.assertEqual(hermes_host._chat_project("chat-b", "chat-b"), str(self.root_b))

    def test_another_chat_never_becomes_a_bound_games_chat_link(self):
        registry = hermes_host._registry()
        stranger = {"conversationId": "side-chat", "sessionId": "side-run", "profile": PROFILE}
        registry.upsert(str(self.root_a), chat=stranger)
        registry.present(str(self.root_a), chat=stranger)
        self.assertNotEqual(registry.get(self.a).get("chat"), stranger)
        self.assertIsNone(hermes_host._chat_project("side-chat", "side-run"))
        own = {"conversationId": "chat-a", "sessionId": "chat-a", "profile": PROFILE}
        registry.upsert(str(self.root_a), chat=own)
        self.assertEqual(registry.get(self.a)["chat"], own)

    def test_the_build_report_takes_the_chats_own_game(self):
        answer = json.loads(
            library_tools.build_report_handler(
                {"title": "Sky", "summary": "Made the sky."}, conversation_id="chat-b", session_id="chat-b"
            )
        )
        self.assertEqual(answer["project"], str(self.root_b))
        refused = json.loads(
            library_tools.build_report_handler(
                {"title": "Sky", "summary": "Made the sky.", "project": str(self.root_a)},
                conversation_id="chat-b",
                session_id="chat-b",
            )
        )
        self.assertEqual(refused["code"], "ONE_GAME_PER_CONVERSATION")


if __name__ == "__main__":
    unittest.main()
