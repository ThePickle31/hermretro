"""Project selection guards and automatic selection for a game's bound conversation."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/studio"


class Guards(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base
        self.registry = games.Registry(self.base / "lib")
        self.frog = make_project(self.base, "Frog Post")
        self.comet = make_project(self.base, "Comet Drift")
        self.registry.upsert(str(self.frog))
        self.registry.upsert(str(self.comet))
        self.registry.bind(games.game_id(self.frog), "st-frog", PROFILE)
        self.broker = bare_broker(games=self.registry)

    def guard(self, conversation, tool, arguments):
        lane = Lane((PROFILE, conversation))
        self.broker.guard_selection(lane.owner, lane, tool, arguments)

    def denied(self, *args, **kwargs):
        with self.assertRaises(Denied) as refused:
            self.guard(*args, **kwargs)
        return refused.exception

    def test_a_games_conversation_may_open_its_own_game(self):
        self.guard("st-frog", "project_select", {"projectPath": str(self.frog / "frog-post.gbsproj")})
        self.guard("st-frog", "project_select", {"projectPath": str(self.frog)})

    def test_a_games_conversation_cannot_open_or_make_another_project(self):
        refused = self.denied("st-frog", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "ONE_GAME_PER_CONVERSATION")
        self.assertIn("New Game", str(refused))
        refused = self.denied("st-frog", "project_create", {"name": "X", "destinationPath": str(self.base / "x")})
        self.assertEqual(refused.code, "ONE_GAME_PER_CONVERSATION")
        self.assertIn("create another project", str(refused))

    def test_no_other_chat_opens_a_game_that_has_its_own_conversation(self):
        refused = self.denied("plain-chat", "project_select", {"projectPath": str(self.frog)})
        self.assertEqual(refused.code, "GAME_CHAT_ONLY")
        self.assertIn("Build page", str(refused))
        # The old escape (continueInThisChat) is gone: the argument is not hermretro's any more.
        self.denied("plain-chat", "project_select", {"projectPath": str(self.frog), "continueInThisChat": True})

    def test_no_other_chat_opens_a_game_that_has_no_conversation_yet(self):
        refused = self.denied("plain-chat", "project_select", {"projectPath": str(self.comet / "comet-drift.gbsproj")})
        self.assertEqual(refused.code, "GAME_CHAT_ONLY")
        self.assertIn("Comet Drift", str(refused))

    def test_nor_a_project_inside_a_games_folder(self):
        nested = make_project(self.comet, "Nested")  # a project inside a game's folder is that game's files
        refused = self.denied("plain-chat", "project_select", {"projectPath": str(nested)})
        self.assertEqual(refused.code, "GAME_CHAT_ONLY")

    def test_a_chat_in_another_profile_is_refused_too(self):
        lane = Lane(("/profiles/other", "plain-chat"))
        with self.assertRaises(Denied) as refused:
            self.broker.guard_selection(lane.owner, lane, "project_select", {"projectPath": str(self.frog)})
        self.assertEqual(refused.exception.code, "GAME_CHAT_ONLY")

    def test_a_conversation_whose_game_folder_is_gone_is_told_so(self):
        import shutil

        shutil.rmtree(self.frog)
        refused = self.denied("st-frog", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "GAME_FOLDER_MISSING")

    def test_any_other_chat_may_make_a_new_project_or_open_one_the_library_does_not_have(self):
        self.guard("plain-chat", "project_create", {"name": "Y", "destinationPath": str(self.base / "y")})
        loose = make_project(self.base / "elsewhere", "Loose")
        self.guard("plain-chat", "project_select", {"projectPath": str(loose)})

    def test_a_new_game_conversation_makes_a_project_but_opens_no_project(self):
        self.registry.build_start("st-new", PROFILE)
        self.guard("st-new", "project_create", {"name": "Z", "destinationPath": str(self.base / "z")})
        # Not even one without a conversation, nor one outside the library: it would stay selected once the new
        # project claims this chat.
        loose = make_project(self.base / "elsewhere", "Loose")
        for target in (self.comet, self.frog, loose):
            refused = self.denied("st-new", "project_select", {"projectPath": str(target)})
            self.assertEqual(refused.code, "NEW_GAME_ONLY")
            self.assertIn("chromatic_project_create", str(refused))


class AutoSelect(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base.resolve()  # macOS: /var is a link to /private/var
        self.registry = games.Registry(self.base / "lib")
        self.frog = make_project(self.base, "Frog Post")
        self.registry.upsert(str(self.frog))
        self.registry.bind(games.game_id(self.frog), "st-frog", PROFILE)
        self.broker = bare_broker(games=self.registry)

    def test_a_games_conversation_starts_with_its_game_selected_and_is_told(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls[0], ("project_select", {"projectPath": str(self.frog / "frog-post.gbsproj")}))
        self.assertEqual(lane.selected_root, os.path.realpath(self.frog))
        self.assertIn("Frog Post", lane.pending_notice)
        engine.calls.clear()
        self.broker.select_bound_game(lane, engine)  # already selected: nothing more
        self.assertEqual(engine.calls, [])

    def test_a_failed_sync_after_a_good_select_still_records_the_game(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)

        def broken(_lane):
            raise RuntimeError("status timed out")

        self.broker._sync_selection = broken
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(lane.selected_root, os.path.realpath(self.frog))

    def test_a_failed_select_is_not_retried_on_every_call(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)

        def refuse(tool, arguments, timeout=None):
            engine.calls.append(tool)
            return {"isError": True}

        engine.call_tool = refuse
        self.broker.select_bound_game(lane, engine)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls, ["project_select"])

    def test_other_conversations_are_left_alone(self):
        lane = Lane((PROFILE, "plain-chat"))
        engine = EngineStub(self.frog)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls, [])
        self.assertIsNone(lane.selected_root)


if __name__ == "__main__":
    unittest.main()
