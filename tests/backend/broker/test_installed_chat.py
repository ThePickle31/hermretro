"""Conversations of games installed from a link (backend/broker/installed.py): without its source, a game's worker has
its folder as its workspace and runs only reads, the emulator and the hardware tools on its checked ROM; no installed
game gets a browser copy of its project; one with its source is built only with the user's consent, once, held.
Hardware is never run: the engine here is a stub.

Run alone: python -m unittest tests.backend.broker.test_installed_chat
"""

import json
import os
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import HARDWARE, Broker, Denied  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.installed import ROM_ONLY_TOOLS  # noqa: E402
from backend.broker.lane import canonical_hash  # noqa: E402
from backend.hermes import host  # noqa: E402
from backend.library import game_card, install_build, release  # noqa: E402
from backend.system import paths  # noqa: E402
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402
from tests.support import isolated_home, make_installed_game, make_library_game, make_rom  # noqa: E402

PINNED = json.loads(paths.PINNED_TOOLS.read_text())["tools"]
READ_ONLY = frozenset(t["name"] for t in PINNED if t.get("annotations", {}).get("readOnlyHint"))


class Engine(EngineStub):
    pid, ready_seconds = 0, 0.0

    def __init__(self, root, workspace):
        super().__init__(root)
        self.workspace, self.closed = workspace, False

    def call_tool(self, tool, arguments, timeout=None):
        if tool == "project_select":
            self.root = Path(arguments["projectPath"]).parent
        return super().call_tool(tool, arguments, timeout)

    def list_tools(self):
        return [], []

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


class Base(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.started = []
        self.broker = bare_broker(
            games=host._registry(),
            tools={t["name"] for t in PINNED},
            read_only=READ_ONLY,
            hardware_lock=threading.Lock(),
            prepare_lock=threading.Lock(),
            pinned_hash=canonical_hash([]),
        )
        self.broker.owner_of = lambda request: (host._profile_identity(), request["conversation"])
        self.broker.new_engine = self.new_engine
        self.broker.install_worker_left = lambda: False

    def new_engine(self, _name, workspace=None):
        self.started.append(workspace)
        return Engine(workspace or self.home.base, workspace)

    def call(self, conversation, tool, arguments=None, origin=None, **policy):
        request = {
            "conversation": conversation,
            "tool": tool,
            "arguments": arguments or {},
            "policy": policy,
            "origin": origin or {},
        }
        return self.broker.call(request)

    def refused(self, code, *args, **policy):
        with self.assertRaises(Denied) as refusal:
            self.call(*args, **policy)
        self.assertEqual(refusal.exception.code, code)


class WithoutSource(Base):
    def setUp(self):
        super().setUp()
        self.game_id, self.root = make_installed_game(self.home, chat="st-rom")
        self.real = os.path.realpath(self.root)
        self.rom = str(Path(self.real) / "build" / "game.gbc")
        self.sha = release.installed(self.root)["rom"]["sha256"]

    def test_only_reads_the_emulator_and_the_hardware_tools_run_there(self):
        allowed = {name for name in self.broker.tools if self.broker.rom_only_allows(name)}
        self.assertEqual(allowed, READ_ONLY | ROM_ONLY_TOOLS | HARDWARE)
        self.assertNotIn("emulator_recording", allowed)
        self.assertFalse(self.broker.rom_only_allows("a_tool_added_later"))  # a new tool is refused by default
        for tool in ("variable_set", "rom_build", "asset_import", "toolchain_prepare", "emulator_recording"):
            self.refused("INSTALLED_WITHOUT_SOURCE", "st-rom", tool)

    def test_its_own_chat_inspects_its_checked_rom_with_the_games_folder_as_the_workspace(self):
        self.assertTrue(self.call("st-rom", "rom_inspect", {"romPath": self.rom})["ok"])
        self.assertTrue(self.call("st-rom", "emulator_run", {"romPath": self.rom})["ok"])
        self.assertEqual(self.started, [self.real])  # one worker, with the game's folder

    def test_only_its_checked_rom_and_only_while_it_is_those_bytes(self):
        other = Path(self.real) / "build" / "other.gbc"
        other.write_bytes(make_rom())
        for path in (str(other), "../other.gbc", str(self.home.base / "x.gbc")):
            self.refused("ROM_OUTSIDE_GAME", "st-rom", "rom_inspect", {"romPath": path})
        self.refused(
            "ROM_CHANGED", "st-rom", "flash", {"romPath": self.rom, "expectedSha256": "0" * 64}, hardware_enabled=True
        )
        self.assertTrue(
            self.call("st-rom", "flash", {"romPath": self.rom, "expectedSha256": self.sha}, hardware_enabled=True)["ok"]
        )
        Path(self.rom).write_bytes(make_rom(fill=9))
        self.refused("ROM_CHANGED", "st-rom", "rom_inspect", {"romPath": self.rom})

    def test_no_browser_copy(self):
        self.refused("INSTALLED_PLAYS_ROM", "st-rom", "web_preview")
        self.refused("INSTALLED_PLAYS_ROM", "st-rom", "web_build")

    def test_another_chat_gets_no_workspace(self):
        self.call("st-general", "rom_inspect", {"romPath": self.rom})  # the engine, given no workspace, refuses it
        self.assertEqual(self.started, [None])

    def test_the_binding_is_checked_on_every_call_delegated_ones_too(self):
        owner = (host._profile_identity(), "st-rom")
        self.call("st-rom", "rom_inspect", {"romPath": self.rom})
        host._registry().unbind(self.game_id, "st-rom", host._profile_identity())
        self.call("st-rom", "rom_inspect", {"romPath": self.rom}, origin={"delegated": True, "task_id": "t"})
        self.assertIsNone(self.broker.lanes[owner].rom_workspace)
        self.assertEqual(self.started, [self.real, None])

    def test_stop_editing_does_not_keep_the_game_busy(self):
        self.call("st-rom", "rom_inspect", {"romPath": self.rom})
        host._registry().unbind(self.game_id, "st-rom", host._profile_identity())
        self.broker._take_hold(self.real)  # the detached worker is closed, not waited for
        self.assertTrue(self.broker.lanes[(host._profile_identity(), "st-rom")].engine.closed)

    def test_an_open_workspace_and_a_held_game_refuse_each_other(self):
        self.call("st-rom", "rom_inspect", {"romPath": self.rom})
        with self.assertRaises(Denied) as busy:
            self.broker._take_hold(self.real)
        self.assertEqual(busy.exception.code, "GAME_BUSY")
        self.broker.lanes[(host._profile_identity(), "st-rom")].engine.closed = True
        self.broker._take_hold(self.real)
        self.refused("GAME_BUSY", "st-rom", "rom_inspect", {"romPath": self.rom})

    def test_holds_are_exclusive(self):
        self.broker._take_hold(self.real)
        with self.assertRaises(Denied) as second:
            self.broker._take_hold(self.real)
        self.assertEqual(second.exception.code, "GAME_BUSY")


class WithSource(Base):
    def setUp(self):
        super().setUp()
        self.game_id, self.root = make_installed_game(self.home, source=True, chat="st-src")
        self.real = os.path.realpath(self.root)

    def test_the_first_call_of_its_chat_gets_no_browser_copy(self):
        self.refused("INSTALLED_PLAYS_ROM", "st-src", "web_build")  # refused once its game is selected for it
        self.refused("INSTALLED_PLAYS_ROM", "st-src", "web_preview")

    def test_its_chat_builds_it_only_with_consent(self):
        self.refused("BUILD_NOT_ALLOWED", "st-src", "rom_build")
        install_build.allow(self.root)
        self.assertTrue(self.call("st-src", "rom_build")["ok"])

    def test_a_game_made_here_builds_its_browser_copy(self):
        made, _root = make_library_game(self.home, "Made Here", chat="st-made")
        self.assertTrue(self.call("st-made", "web_build")["ok"])
        self.assertTrue(made)

    def test_the_test_build_needs_consent_and_records_under_its_hold(self):
        with self.assertRaises(Denied) as refused:
            self.broker.test_build({"root": self.real})
        self.assertEqual(refused.exception.code, "BUILD_NOT_ALLOWED")
        install_build.allow(self.root)
        built = self.broker.test_build({"root": self.real})  # the stub builds nothing new: the shipped ROM stays
        record = release.installed(self.root)
        self.assertEqual(built["sha256"], record["rom"]["sha256"])
        self.assertTrue(built["matches"])
        self.assertEqual(record["testBuild"]["commit"], record["commit"])
        last = host._registry().get(self.game_id)["lastBuild"]
        self.assertEqual((last["ok"], last["sha256"]), (True, built["sha256"]))
        # stamped like any build (build_record), and that is not the user's edit of the installed game
        self.assertEqual(game_card.load(self.root)["romSha256"], built["sha256"])
        self.assertIn("builtWith", game_card.load(self.root))
        self.assertIsNot(release.local_edits(self.root), True)
        self.assertEqual(self.broker._live_holds(), {})  # released

    def test_the_test_build_waits_for_nothing_else_to_hold_the_game(self):
        install_build.allow(self.root)
        self.broker._take_hold(self.real)
        with self.assertRaises(Denied) as busy:
            self.broker.test_build({"root": self.real})
        self.assertEqual(busy.exception.code, "GAME_BUSY")

    def test_the_test_build_is_work_retirement_waits_for(self):
        from backend.broker.lifecycle import WORK_OPS

        self.assertIn("test_build", WORK_OPS)
        self.assertTrue(issubclass(Broker, type(self.broker)) or isinstance(self.broker, Broker))


if __name__ == "__main__":
    unittest.main()
