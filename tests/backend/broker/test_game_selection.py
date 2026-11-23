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

    def guard(self, conversation, tool, arguments, continue_here=False):
        lane = Lane((PROFILE, conversation))
        self.broker.guard_selection(lane.owner, lane, tool, arguments, continue_here)

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
        # continueInThisChat never lifts the hard block
        self.denied("st-frog", "project_select", {"projectPath": str(self.comet)}, continue_here=True)

    def test_another_chat_is_warned_and_may_continue_once_the_user_confirms(self):
        refused = self.denied("plain-chat", "project_select", {"projectPath": str(self.frog)})
        self.assertEqual(refused.code, "GAME_HAS_CONVERSATION")
        self.assertIn("continueInThisChat", str(refused))
        self.guard("plain-chat", "project_select", {"projectPath": str(self.frog)}, continue_here=True)
        self.assertEqual(self.broker.events[-1]["event"], "continued_outside_game_conversation")

    def test_a_chat_in_another_profile_is_warned_too(self):
        lane = Lane(("/profiles/other", "plain-chat"))
        with self.assertRaises(Denied) as refused:
            self.broker.guard_selection(lane.owner, lane, "project_select", {"projectPath": str(self.frog)}, False)
        self.assertEqual(refused.exception.code, "GAME_HAS_CONVERSATION")

    def test_a_conversation_whose_game_folder_is_gone_is_told_so(self):
        import shutil

        shutil.rmtree(self.frog)
        refused = self.denied("st-frog", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "GAME_FOLDER_MISSING")

    def test_games_without_a_conversation_and_new_projects_are_open_to_any_chat(self):
        self.guard("plain-chat", "project_select", {"projectPath": str(self.comet)})
        self.guard("plain-chat", "project_create", {"name": "Y", "destinationPath": str(self.base / "y")})

    def test_a_new_game_conversation_makes_a_project_but_opens_no_existing_game(self):
        self.registry.build_start("st-new", PROFILE)
        self.guard("st-new", "project_create", {"name": "Z", "destinationPath": str(self.base / "z")})
        # Even a game without a conversation: it would stay selected once the new project claims this chat.
        refused = self.denied("st-new", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "NEW_GAME_ONLY")
        self.assertIn("chromatic_project_create", str(refused))
        refused = self.denied("st-new", "project_select", {"projectPath": str(self.frog)}, continue_here=True)
        self.assertEqual(refused.code, "GAME_HAS_CONVERSATION")


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
