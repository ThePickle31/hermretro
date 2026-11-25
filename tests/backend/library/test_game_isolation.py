"""Several games made at once, each in its own Build conversation: a game's chat acts on its own game only, and no
other chat can become the one that finds it.

Run alone: python -m unittest tests.backend.library.test_game_isolation
"""

import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.library import report_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.support import FakeBrokerClient, isolated_home, make_library_game, make_project  # noqa: E402 - the repository root goes on sys.path first

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

    def test_a_new_game_chat_cannot_name_an_existing_game_either(self):
        hermes_host._registry().build_start("chat-new", PROFILE)
        refused = self.info({"project": str(self.root_a), "tagline": "Someone else's tagline here"}, "chat-new")
        self.assertEqual(refused["code"], "NEW_GAME_ONLY")
        self.assertEqual(self.present({"project": str(self.root_a)}, "chat-new")["code"], "NEW_GAME_ONLY")

    def test_the_shelf_drops_a_link_to_another_games_conversation(self):
        registry = hermes_host._registry()
        # An old link: game A's chat is the conversation that has since become game B's.
        data = registry.load()
        data["games"][self.a]["chat"] = {"conversationId": "chat-b", "sessionId": "chat-b", "profile": PROFILE}
        registry._save(data)
        listed = library_rpcs.rpc_games(mock.Mock())({})
        self.assertTrue(listed["ok"], listed)
        shown = {game["id"]: game for game in listed["games"]}
        self.assertIsNone(shown[self.a]["chat"])
        self.assertEqual(shown[self.b]["chat"]["sessionId"], "chat-b")

    def test_naming_its_own_game_is_fine(self):
        self.assertTrue(self.present({"project": str(self.root_b)}, "chat-b")["ok"])

    def test_a_presentation_says_whether_the_games_own_build_conversation_made_it(self):
        own = self.present({}, "chat-b")
        self.assertIs(own["studio"]["buildConversation"], True)
        hermes_host._registry().unbind(self.a, "chat-a", PROFILE)
        # A game is presented only from its own conversation, even once it has none: it is opened on the Build page.
        self.assertEqual(self.present({"project": str(self.root_a)}, "side-chat")["code"], "GAME_CHAT_ONLY")
        # A project the library does not have yet can be presented from any chat, and that chat is not its own.
        outside = make_project(self.home.base / "elsewhere", "Loose")
        side = self.present({"project": str(outside)}, "side-chat")
        self.assertIs(side["studio"]["buildConversation"], False)
        with mock.patch.object(hermes_host, "_profile_identity", lambda: PROFILE):
            listed = library_rpcs.rpc_presentations(mock.Mock())({})["presentations"]
        self.assertEqual([item["buildConversation"] for item in listed], [True, False])

    def test_the_lane_of_another_game_never_outranks_the_binding(self):
        client = FakeBrokerClient({"ok": True, "matched": "chat", "lane": {"project_root": str(self.root_a)}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            self.assertEqual(hermes_host._chat_project("chat-b", "chat-b"), str(self.root_b))

    def test_a_silent_broker_leaves_the_project_lookup_to_the_library(self):
        registry = hermes_host._registry()
        data = registry.load()
        data["games"][self.a]["chat"] = {"conversationId": "legacy-chat", "profile": PROFILE}
        registry._save(data)
        connected = FakeBrokerClient({})
        with (
            mock.patch.object(hermes_host, "try_connect", return_value=(connected, None)),
            mock.patch.object(
                connected, "request", side_effect=hermes_host.BrokerUnavailable("Broker did not answer activity")
            ) as ask,
        ):
            self.assertEqual(hermes_host._chat_project("legacy-chat", "legacy-run"), str(self.root_a))
        ask.assert_called_once_with(
            {"op": "activity", "profile": PROFILE, "ids": ["legacy-chat", "legacy-run"], "limit": 1}
        )

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
            report_tools.build_report_handler(
                {"title": "Sky", "summary": "Made the sky."}, conversation_id="chat-b", session_id="chat-b"
            )
        )
        self.assertEqual(answer["project"], str(self.root_b))
        refused = json.loads(
            report_tools.build_report_handler(
                {"title": "Sky", "summary": "Made the sky.", "project": str(self.root_a)},
                conversation_id="chat-b",
                session_id="chat-b",
            )
        )
        self.assertEqual(refused["code"], "ONE_GAME_PER_CONVERSATION")

    def test_binding_links_the_game_to_its_build_conversation(self):
        self.assertEqual(hermes_host._registry().get(self.a)["chat"]["sessionId"], "chat-a")

    def test_a_link_to_the_games_folder_is_the_same_game(self):
        link = self.root_b.parent / "sky-link"
        os.symlink(self.root_b, link)
        self.assertTrue(self.present({"project": str(link)}, "chat-b")["ok"])

    def test_a_build_card_without_the_chats_game_shows_no_other_games_pictures(self):
        picture = self.root_a / "assets" / "sprites" / "cat.png"
        picture.parent.mkdir(parents=True)
        picture.write_bytes(b"png")
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            answer = json.loads(
                report_tools.build_report_handler(
                    {
                        "title": "Sky",
                        "summary": "Made the sky.",
                        "changes": [{"kind": "added", "text": "a cat", "asset": str(picture)}],
                    },
                    conversation_id="side-chat",
                    session_id="side-chat",
                )
            )
        self.assertTrue(answer["ok"])
        self.assertNotIn("asset", answer["report"]["changes"][0])
        self.assertIn("no game project", answer["warnings"][0])


class OneGameInItsOwnFolder(unittest.TestCase):
    """The broker keeps each conversation's work in its own game's folder."""

    def setUp(self):
        self.home = isolated_home(self)
        self.registry = hermes_host._registry()
        self.a, self.root_a = make_library_game(self.home, "Cat Field")
        self.b, self.root_b = make_library_game(self.home, "Sky Loop")
        self.registry.bind(self.b, "chat-b", PROFILE)
        self.broker = bare_broker(games=self.registry)

    def guard(self, conversation, tool, arguments):
        lane = Lane((PROFILE, conversation))
        self.broker.guard_selection(lane.owner, lane, tool, arguments)

    def refused(self, conversation, tool, arguments):
        with self.assertRaises(Denied) as refused:
            self.guard(conversation, tool, arguments)
        return refused.exception

    def test_no_chat_makes_a_new_game_inside_another_games_folder(self):
        for destination in (self.root_a / "mini", self.root_a / "deep" / "er"):
            refused = self.refused(
                "side-chat", "project_create_blank", {"name": "Mini", "destinationPath": str(destination)}
            )
            self.assertEqual(refused.code, "INSIDE_ANOTHER_GAME")
            self.assertIn("Leave destinationPath out", str(refused))
        self.guard(
            "side-chat", "project_create_blank", {"name": "Free", "destinationPath": str(self.home.base / "free")}
        )
        # The same folder is the engine's to refuse, so a new game racing for a name still moves to the next number.
        self.guard("side-chat", "project_create_blank", {"name": "Cat Field", "destinationPath": str(self.root_a)})

    def test_a_project_another_chat_is_making_right_now_counts_too(self):
        making = self.home.base / "making"
        making.mkdir()
        (making / "making.gbsproj").write_text("{}")  # on disk, not in the library yet
        refused = self.refused(
            "side-chat", "project_create_blank", {"name": "In", "destinationPath": str(making / "in")}
        )
        self.assertEqual(refused.code, "INSIDE_ANOTHER_GAME")

    def test_paths_are_read_as_the_engine_reads_them(self):
        self.registry.build_start("chat-new", PROFILE)
        refused = self.refused("chat-new", "project_select", {"projectPath": f"  {self.root_a}  "})
        self.assertEqual(refused.code, "NEW_GAME_ONLY")
        refused = self.refused("chat-new", "project_select", {"projectPath": "cat-field"})
        self.assertEqual(refused.code, "INVALID_ARGUMENTS")

    def test_a_games_chat_whose_worker_cannot_switch_runs_nothing(self):
        lane = Lane((PROFILE, "chat-b"))
        lane.selected_root = str(self.root_a)
        engine = lane.engine = EngineStub(self.root_b)
        engine.call_tool = lambda tool, arguments, timeout=None: {"isError": True}  # PATH_OUTSIDE_PROJECT
        for _attempt in range(2):  # not only the first call: the failure is remembered, the refusal is not
            with self.assertRaises(Denied) as refused:
                self.broker.select_bound_game(lane, engine)
            self.assertEqual(refused.exception.code, "ONE_GAME_PER_CONVERSATION")

    def test_a_deleted_games_folder_is_free_again(self):
        shutil.rmtree(self.root_a)
        self.guard("side-chat", "project_create_blank", {"name": "Cat Field", "destinationPath": str(self.root_a)})

    def test_a_games_chat_with_another_project_open_is_moved_back_to_its_game(self):
        lane = Lane((PROFILE, "chat-b"))
        lane.selected_root = str(self.root_a)  # opened before its new project claimed the conversation
        engine = lane.engine = EngineStub(self.root_b)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls[0][0], "project_select")
        self.assertIn(str(self.root_b), engine.calls[0][1]["projectPath"])
        self.assertEqual(os.path.realpath(lane.selected_root), os.path.realpath(self.root_b))

    def test_a_project_inside_a_games_folder_is_its_own_game(self):
        inner = self.root_a / "mini"
        inner.mkdir()
        self.registry.upsert(str(inner))
        found = hermes_host.library_game_for([str(inner / "project" / "scene.gbsres")])
        self.assertEqual(found[1], Path(os.path.realpath(inner)))

    def test_the_activity_view_never_shows_another_chats_game(self):
        busy = Lane((PROFILE, "chat-b"))
        busy.last_activity = 1.0
        self.broker.lanes[busy.owner] = busy
        self.assertEqual(self.broker.view_lane(PROFILE, ["side-chat"]), (None, None))
        self.assertEqual(self.broker.view_lane(PROFILE, ["chat-b"]), (busy, "chat"))


if __name__ == "__main__":
    unittest.main()
