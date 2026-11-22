"""Every failure tells the agent what to do next (``nextStep``): a broker another copy of hermretro still runs,
an unexpected fault, and a new game whose folder name is taken.

Run alone: python -m unittest tests.backend.hermes.test_tool_failures
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import OtherCopyBusy  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes.tool_args import tool_error  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import FakeBrokerClient, isolated_home  # noqa: E402 - the repository root goes on sys.path first


class OtherCopyOfThePlugin(unittest.TestCase):
    def setUp(self):
        isolated_home(self)
        self.ctx = mock.Mock()
        self.ctx.get_config = lambda key, default=None: default

    def call(self, lane):
        """A chromatic tool call while another copy's broker runs games; ``lane`` is what it knows of this chat."""

        def busy():
            raise OtherCopyBusy("Another copy of hermretro (/old/copy) is running games right now.", "/old/copy")

        client = FakeBrokerClient(lane)
        with (
            mock.patch.object(hermes_host, "ensure_broker", busy),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)),
            mock.patch.object(hermes_host, "_profile_identity", lambda: "/profiles/hermretro"),
        ):
            handler = hermes_host.make_tool_handler(self.ctx, {"name": "rom_build"})
            return json.loads(handler({}, conversation_id="chat-a", session_id="chat-a"))

    def test_this_chats_own_game_in_the_old_copy_says_so(self):
        answer = self.call({"ok": True, "matched": "chat", "lane": {"alive": True, "project_root": "/g/a"}})
        self.assertEqual((answer["code"], answer["dispatched"]), ("UNAVAILABLE", False))
        self.assertIn("This chat's game is still open in another copy of hermretro (/old/copy)", answer["error"])
        self.assertIn("stop", answer["nextStep"])
        self.assertIn("outside the chromatic tools", answer["nextStep"])

    def test_other_chats_games_say_to_wait_for_them(self):
        answer = self.call({"ok": True, "lane": None, "matched": None})
        self.assertIn("/old/copy", answer["error"])
        self.assertIn("other chats", answer["nextStep"])
        self.assertIn("outside the chromatic tools", answer["nextStep"])

    def test_a_copy_that_cannot_be_asked_leaves_whose_games_open(self):
        def busy():
            raise OtherCopyBusy("The previous version of hermretro is still running games.")

        with (
            mock.patch.object(hermes_host, "ensure_broker", busy),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, ValueError("old handshake"))),
        ):
            handler = hermes_host.make_tool_handler(self.ctx, {"name": "rom_build"})
            answer = json.loads(handler({}, conversation_id="chat-a", session_id="chat-a"))
        self.assertIn("may be this chat's own game", answer["error"])
        self.assertIn("stop", answer["nextStep"])

    def test_a_broker_that_cannot_start_points_at_setup(self):
        def down():
            raise hermes_host.BrokerUnavailable("Node.js 22 or newer is required but was not found.")

        with mock.patch.object(hermes_host, "ensure_broker", down):
            answer = json.loads(hermes_host.make_tool_handler(self.ctx, {"name": "rom_build"})({}))
        self.assertIn("hermretro:setup", answer["nextStep"])


class FailureAnswers(unittest.TestCase):
    def test_an_unexpected_fault_says_not_to_work_around_it(self):
        answer = json.loads(tool_error("hermretro adapter error: KeyError: 'x'", "ADAPTER_ERROR"))
        self.assertIn("do not retry the same call blindly", answer["nextStep"])
        self.assertIn(
            "Fix the argument", json.loads(tool_error("project must be a path.", "INVALID_ARGUMENTS"))["nextStep"]
        )
        self.assertIn("nextStep", json.loads(tool_error("Something else.", "SOMETHING_NEW")))


class NewGameFolders(unittest.TestCase):
    def setUp(self):
        isolated_home(self)

    def test_a_name_another_chat_took_meanwhile_moves_to_the_next_number(self):
        games = paths.games_dir(create=True)

        def engine(_owner, _tool, args, **_options):
            if not Path(args["destinationPath"]).name.endswith(" 2"):
                Path(args["destinationPath"]).mkdir()  # the other chat won this folder first
                refused = {"code": "PROJECT_ALREADY_EXISTS", "error": "The project destination already exists."}
                return {"ok": True, "dispatched": True, "result": {"isError": True, "structuredContent": refused}}
            return {"ok": True, "dispatched": True, "result": {"structuredContent": {"success": True}}}

        client = FakeBrokerClient(engine)
        ctx = mock.Mock()
        ctx.get_config = lambda key, default=None: default
        with (
            mock.patch.object(hermes_host, "ensure_broker", lambda: client),
            mock.patch.object(hermes_host, "_attach_images", lambda: False),
        ):
            hermes_host.make_tool_handler(ctx, {"name": "project_create_blank"})({"name": "Cat Game"})
        self.assertEqual(
            [args["destinationPath"] for _owner, _tool, args in client.calls],
            [str(games / "Cat Game"), str(games / "Cat Game 2")],
        )

    def test_a_taken_name_gets_the_next_number(self):
        games = paths.games_dir(create=True)
        self.assertEqual(contracts.default_destination("Cat Game"), str(games / "Cat Game"))
        (games / "Cat Game").mkdir()
        self.assertEqual(contracts.default_destination("Cat Game!"), str(games / "Cat Game 2"))
        (games / "Cat Game 2").mkdir()
        os.symlink(games / "nowhere", games / "Cat Game 3")  # even a dangling link takes the name
        self.assertEqual(contracts.default_destination("Cat Game"), str(games / "Cat Game 4"))


if __name__ == "__main__":
    unittest.main()
