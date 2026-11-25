"""The broker pairs a build's ROM with the game's sources as they were before it started, and with nothing when a
file changed while it ran (backend/library/pipeline.py holds present and report to that record).

Run alone: python -m unittest tests.backend.broker.test_build_sources
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/studio"


class Builder(EngineStub):
    """A worker whose build writes the game's ROM and, with ``save``, a source file while it compiles."""

    pid, ready_seconds = 0, 0.0

    def __init__(self, root, save=None):
        super().__init__(root)
        self.save = save

    def call_tool(self, tool, arguments, timeout=None):
        if tool != "rom_build":
            return super().call_tool(tool, arguments, timeout)
        self.calls.append((tool, arguments))
        if self.save:
            self.save()
        rom = Path(self.root, "build", "game.gbc")
        rom.write_bytes(b"\2" * 512)
        content = {"success": True, "projectRoot": str(self.root), "outputPath": str(rom)}
        return {"content": [], "structuredContent": {**content, "rom": {"sha256": games.file_sha256(rom)}}}

    def alive(self):
        return True


class BuildSources(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base.resolve()  # macOS: /var is a link to /private/var
        self.registry = games.Registry(self.base / "lib")
        self.root = make_project(self.base, "Bolt")
        self.game = self.registry.upsert(str(self.root))["id"]
        self.registry.bind(self.game, "chat", PROFILE)
        self.broker = bare_broker(games=self.registry, tools={"rom_build"}, read_only=frozenset(), hardware_lock=None)
        self.broker.owner_of = lambda request: (PROFILE, request["conversation"])

    def build(self, save=None):
        lane = Lane((PROFILE, "chat"))
        lane.selected_root = os.path.realpath(self.root)
        lane.selected_project_path = str(games.project_file(self.root))
        lane.engine = Builder(self.root, save)
        lane.observer = self.broker.record_game
        self.broker.lanes[lane.owner] = lane
        self.broker.writer_leases[lane.selected_root] = lane.owner
        self.broker.call({"conversation": "chat", "tool": "rom_build", "arguments": {}})
        return self.registry.get(self.game)["lastBuild"]

    def test_the_rom_is_paired_with_the_sources_it_was_built_from(self):
        before = games.source_digest(self.root)
        last = self.build()
        self.assertEqual(last["sources"], before)
        self.assertEqual(last["sha256"], games.file_sha256(self.root / "build" / "game.gbc"))

    def test_a_save_while_it_compiles_leaves_the_rom_paired_with_nothing(self):
        scene = self.root / "project" / "scene.gbsres"
        last = self.build(save=lambda: scene.write_text('{"saved": "mid-build"}'))
        self.assertTrue(last["ok"])
        self.assertNotIn("sources", last)


if __name__ == "__main__":
    unittest.main()
