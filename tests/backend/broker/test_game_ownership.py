"""The broker lets a chat change or run a library game only while it is that game's own conversation.

Run alone: python -m unittest tests.backend.broker.test_game_ownership
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import canonical_hash  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/studio"


class Engine(EngineStub):
    """A worker that answers calls, starts and stops."""

    pid, ready_seconds = 0, 0.0

    def __init__(self, root, selects=None):
        super().__init__(root)
        self.closed, self.selects = False, selects

    def call_tool(self, tool, arguments, timeout=None):
        if tool == "project_select" and self.selects is not None:
            self.root = self.selects
        return super().call_tool(tool, arguments, timeout)

    def list_tools(self):
        return [], []

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


class Ownership(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base.resolve()  # macOS: /var is a link to /private/var
        self.registry = games.Registry(self.base / "lib")
        self.frog = make_project(self.base, "Frog Post")
        self.frog_id = self.registry.upsert(str(self.frog))["id"]
        self.registry.bind(self.frog_id, "st-frog", PROFILE)
        self.broker = bare_broker(
            games=self.registry,
            tools={"variable_set", "variable_inspect", "project_select"},
            read_only=frozenset({"variable_inspect"}),
            hardware_lock=None,
        )
        self.broker.owner_of = lambda request: (PROFILE, request["conversation"])

    def lane(self, conversation, root=None, engine=None):
        lane = Lane((PROFILE, conversation))
        lane.selected_root = os.path.realpath(root) if root else None
        lane.selected_project_path = str(games.project_file(Path(root))) if root else None
        lane.engine = engine or Engine(root or self.base)
        lane.observer = self.broker.record_game  # as lane_for gives every lane: the library hears of selections
        self.broker.lanes[lane.owner] = lane
        return lane

    def call(self, conversation, tool, arguments=None):
        return self.broker.call({"conversation": conversation, "tool": tool, "arguments": arguments or {}})

    def test_stop_editing_leaves_the_old_chat_unable_to_change_the_game(self):
        lane = self.lane("st-frog", self.frog)
        self.broker.writer_leases[lane.selected_root] = lane.owner
        self.assertTrue(self.call("st-frog", "variable_set", {"name": "x"})["ok"])
        self.registry.unbind(self.frog_id, "st-frog", PROFILE)
        with self.assertRaises(Denied) as refused:
            self.call("st-frog", "variable_set", {"name": "y"})
        self.assertEqual(refused.exception.code, "GAME_CHAT_ONLY")
        self.assertNotIn(lane.selected_root, self.broker.writer_leases, "the old chat lets go of the game")
        self.assertEqual([call[0] for call in lane.engine.calls], ["variable_set"], "the refused write never ran")
        self.call("st-frog", "variable_inspect")  # reading is still fine

    def test_a_restarted_worker_does_not_reopen_a_game_the_chat_no_longer_owns(self):
        lane = self.lane("st-frog", self.frog)
        lane.engine.closed = True  # the worker died
        fresh = Engine(self.frog)
        self.broker.new_engine = lambda _name: fresh
        self.broker.pinned_hash = canonical_hash([])
        self.registry.unbind(self.frog_id, "st-frog", PROFILE)
        self.broker.ensure_engine(lane)
        self.assertEqual(fresh.calls, [], "nothing was reselected")
        self.assertIsNone(lane.selected_root)
        self.assertIn("no longer selected", lane.pending_notice)

    def test_a_restarted_worker_reopens_the_chats_own_game(self):
        lane = self.lane("st-frog", self.frog)
        lane.engine.closed = True
        fresh = Engine(self.frog)
        self.broker.new_engine = lambda _name: fresh
        self.broker.pinned_hash = canonical_hash([])
        self.broker.ensure_engine(lane)
        self.assertEqual(fresh.calls[0][0], "project_select")
        self.assertIn("restored", lane.pending_notice)

    def test_a_chat_that_lost_the_race_to_claim_a_project_has_it_closed_again(self):
        loose = make_project(self.base / "elsewhere", "Loose")
        # Another chat brought the same project into the library a moment earlier, so it is that chat's game.
        claimed = self.registry.upsert(str(loose), claim=(PROFILE, "first", ()))
        self.assertEqual(claimed["session"]["storedId"], "first")
        lane = self.lane("second", engine=Engine(self.base, selects=loose))
        self.broker.guard_selection = lambda *_args: None  # it passed the guard before the other chat claimed it
        with self.assertRaises(Denied) as refused:
            self.call("second", "project_select", {"projectPath": str(loose)})
        self.assertEqual(refused.exception.code, "GAME_CHAT_ONLY")
        self.assertIsNone(lane.selected_root)
        self.assertTrue(lane.engine.closed, "its worker, which had the project open, is replaced")

    def test_a_chat_that_brings_a_project_in_owns_it_at_once(self):
        loose = make_project(self.base / "elsewhere", "Loose")
        lane = self.lane("plain", engine=Engine(self.base, selects=loose))
        answer = self.call("plain", "project_select", {"projectPath": str(loose)})
        self.assertTrue(answer["ok"])
        self.assertEqual(lane.selected_root, os.path.realpath(loose))
        self.assertEqual(self.registry.binding_for(PROFILE, ["plain"])[0], "game")

    def test_a_path_argument_into_a_game_inside_this_one_is_refused(self):
        inner = make_project(self.frog, "Inner")
        inner_id = self.registry.upsert(str(inner))["id"]
        self.registry.bind(inner_id, "st-inner", PROFILE)
        self.lane("st-frog", self.frog)
        name = inner.name
        for key, value in (
            ("assetPath", f"{name}/assets/backgrounds/x.png"),
            ("outputPath", str(inner / "build" / "probe.gb")),
            ("recordingPath", f"artifacts/../{name}/run.json"),
        ):
            with self.subTest(key=key), self.assertRaises(Denied) as refused:
                self.call("st-frog", "variable_set", {key: value})
            self.assertEqual(refused.exception.code, "INSIDE_ANOTHER_GAME")
            self.assertIn("Inner", str(refused.exception))
        self.assertTrue(self.call("st-frog", "variable_set", {"assetPath": "assets/backgrounds/x.png"})["ok"])

    def test_selection_paths_collapse_dot_dot_before_links_as_the_engine_does(self):
        # <base>/hop -> <frog>/deep: "<base>/hop/../Loose" is <base>/Loose to the engine, not <frog>/Loose.
        (self.frog / "deep").mkdir()
        (self.base / "hop").symlink_to(self.frog / "deep", target_is_directory=True)
        target = self.broker._selection_target(
            Lane((PROFILE, "x")), "project_select", {"projectPath": f"{self.base}/hop/../Loose"}
        )
        self.assertEqual(target, str(self.base / "Loose"))
        # The other way round: by spelling it lands in the game, so it is refused even though the links lead out.
        (self.base / "out").mkdir()
        (self.frog / "away").symlink_to(self.base / "out", target_is_directory=True)
        with self.assertRaises(Denied) as refused:
            self.broker.guard_selection(
                (PROFILE, "x"), Lane((PROFILE, "x")), "project_select", {"projectPath": f"{self.frog}/away/../sub"}
            )
        self.assertEqual(refused.exception.code, "GAME_CHAT_ONLY")


if __name__ == "__main__":
    unittest.main()
