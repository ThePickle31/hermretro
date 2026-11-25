"""``chromatic_scene_apply`` takes its operations from a JSON file (``operationsPath``) inside the game's project or
Hermes's scratch folder: the broker reads it into ``operations`` before the engine sees the call.

Run alone: python -m unittest tests.backend.broker.test_operations_file
"""

import contextlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import Denied  # noqa: E402 - the repository root goes on sys.path first
from backend.broker import operations_file  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.operations_file import scene_apply_arguments  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

OPERATIONS = [{"type": "actor.create", "clientId": "coin", "name": "Coin", "x": 4, "y": 5}]


class OperationsFile(unittest.TestCase):
    def setUp(self):
        base = isolated_home(self).base
        self.root = make_project(base, "Ops Game")
        self.scratch = base / "profiles" / "hermretro" / "cache" / "scratch"
        self.scratch.mkdir(parents=True)
        self.outside = base / "elsewhere"
        self.outside.mkdir()

    def read(self, asked, root=None, scratch=None, **extra):
        root = str(self.root) if root is None else root or None
        return scene_apply_arguments(root, {"sceneId": "s", "operationsPath": asked, **extra}, scratch)

    def refused(self, asked, **options):
        with self.assertRaises(Denied) as refused:
            self.read(asked, **options)
        self.assertEqual(refused.exception.code, "OPERATIONS_FILE")
        return str(refused.exception)

    def test_inline_operations_pass_through_untouched(self):
        arguments = {"sceneId": "s", "operations": OPERATIONS}
        self.assertIs(scene_apply_arguments(str(self.root), arguments, None), arguments)

    def test_a_list_in_the_project_relative_or_absolute(self):
        (self.root / "ops.json").write_text(json.dumps(OPERATIONS))
        for asked in ("ops.json", str(self.root / "ops.json"), "project/../ops.json"):
            with self.subTest(asked=asked):
                self.assertEqual(self.read(asked), {"sceneId": "s", "operations": OPERATIONS})

    def test_an_object_in_the_scratch_folder(self):
        (self.scratch / "room").mkdir()
        (self.scratch / "room" / "ops.json").write_text(json.dumps({"operations": OPERATIONS, "note": "kept out"}))
        answer = self.read(str(self.scratch / "room" / "ops.json"), scratch=str(self.scratch), dryRun=True)
        self.assertEqual(answer, {"sceneId": "s", "dryRun": True, "operations": OPERATIONS})

    def test_a_file_anywhere_else_is_refused(self):
        (self.outside / "ops.json").write_text(json.dumps(OPERATIONS))
        message = self.refused(str(self.outside / "ops.json"), scratch=str(self.scratch))
        self.assertIn(str(self.scratch), message)
        self.refused("../elsewhere/ops.json")
        # A link inside the project to a file outside it is judged by where it leads.
        (self.root / "link.json").symlink_to(self.outside / "ops.json")
        self.refused("link.json")
        # Without a scratch folder, only the project counts.
        (self.scratch / "ops.json").write_text(json.dumps(OPERATIONS))
        self.refused(str(self.scratch / "ops.json"))

    def test_a_relative_path_needs_a_selected_project(self):
        (self.scratch / "ops.json").write_text(json.dumps(OPERATIONS))
        self.refused("ops.json", root="", scratch=str(self.scratch))
        self.assertEqual(
            self.read(str(self.scratch / "ops.json"), root="", scratch=str(self.scratch))["operations"], OPERATIONS
        )

    def test_unusable_files_and_arguments_are_refused_with_the_reason(self):
        (self.root / "bad.json").write_text("[{")
        (self.root / "shape.json").write_text(json.dumps({"ops": OPERATIONS}))
        (self.root / "big.json").write_text(" " * (1024 * 1024 + 1))
        (self.root / "folder.json").mkdir()
        self.assertIn("could not be read as JSON", self.refused("bad.json"))
        self.assertIn("a JSON list of operations", self.refused("shape.json"))
        self.assertIn("larger than 1 MiB", self.refused("big.json"))
        self.assertIn("not a file", self.refused("folder.json"))
        self.assertIn("not a file", self.refused("missing.json"))
        self.assertIn("not both", self.refused("ops.json", operations=OPERATIONS))
        for asked in ("", 7, None):
            self.assertIn("must be the path of a JSON file", self.refused(asked))
        self.assertIn("cannot be used", self.refused("ops\x00.json"))

    def test_the_folder_is_matched_by_identity_not_spelling(self):
        # A link to the project names the same folder: its files count as inside.
        (self.root / "ops.json").write_text(json.dumps(OPERATIONS))
        alias = self.outside / "alias"
        alias.symlink_to(self.root)
        self.assertEqual(self.read(str(self.root / "ops.json"), root=str(alias))["operations"], OPERATIONS)
        # A folder spelled the same but for letter case is another folder wherever the volume keeps case.
        twin = self.root.parent / self.root.name.upper()
        if twin.exists():
            self.skipTest("this volume ignores letter case")
        twin.mkdir()
        (twin / "ops.json").write_text(json.dumps(OPERATIONS))
        self.refused(str(twin / "ops.json"))

    def test_a_component_replaced_after_the_check_is_never_followed(self):
        (self.root / "room").mkdir()
        (self.root / "room" / "ops.json").write_text(json.dumps(OPERATIONS))
        (self.outside / "ops.json").write_text(json.dumps(OPERATIONS))
        checked = operations_file._parts_below

        def swap(replace, target):
            def check_then_swap(path, folder):
                parts = checked(path, folder)
                if parts is not None:
                    (shutil.rmtree if replace.is_dir() else Path.unlink)(replace)
                    replace.symlink_to(target)
                return parts

            return mock.patch.object(operations_file, "_parts_below", check_then_swap)

        with swap(self.root / "room", self.outside):
            self.refused("room/ops.json")
        (self.root / "room").unlink()
        (self.root / "ops.json").write_text(json.dumps(OPERATIONS))
        with swap(self.root / "ops.json", self.outside / "ops.json"):
            self.refused("ops.json")

    def test_a_pipe_is_refused_without_waiting_for_a_writer(self):
        os.mkfifo(self.root / "pipe.json")
        self.assertIn("not a file", self.refused("pipe.json"))

    def test_at_most_one_byte_past_the_limit_is_read(self):
        (self.root / "big.json").write_text(" " * (4 * operations_file.MAX_BYTES))
        read = []
        real_read = os.read

        def counted(descriptor, size):
            read.append(len(chunk := real_read(descriptor, size)))
            return chunk

        with mock.patch.object(operations_file.os, "read", counted):
            self.assertIn("larger than 1 MiB", self.refused("big.json"))
        self.assertEqual(sum(read), operations_file.MAX_BYTES + 1)

    def test_non_finite_numbers_are_refused(self):
        for number in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(number=number):
                (self.root / "ops.json").write_text(f'[{{"type": "actor.update", "x": {number}}}]')
                self.assertIn("could not be read as JSON", self.refused("ops.json"))

    def test_nesting_past_the_limit_is_refused_before_the_engine(self):
        def nested(levels):
            return "[" * levels + "]" * levels

        limit = operations_file.MAX_DEPTH
        for levels in (limit + 1, 200_000):
            with self.subTest(levels=levels):
                (self.root / "ops.json").write_text(nested(levels))
                self.assertIn(f"deeper than {limit} levels", self.refused("ops.json"))
        (self.root / "ops.json").write_text(nested(limit))
        self.assertEqual(len(self.read("ops.json")["operations"]), 1)


class BrokerAndGateway(unittest.TestCase):
    def setUp(self):
        base = isolated_home(self).base
        self.root = make_project(base, "Ops Game")
        (self.root / "ops.json").write_text(json.dumps(OPERATIONS))

    def test_the_engine_gets_the_files_operations_and_never_the_path(self):
        engine = EngineStub(self.root)
        engine.pid = 0
        lane = Lane(("/profiles/studio", "chat"))
        lane.selected_root, lane.engine = str(self.root), engine
        broker = bare_broker(
            games=games.Registry(self.root.parent / "lib"), tools={"scene_apply"}, read_only=frozenset()
        )
        broker.hardware_lock = None
        broker.lanes[lane.owner] = lane
        broker.owner_of = lambda _request: lane.owner
        broker.ensure_engine = lambda _lane: engine
        broker.select_bound_game = lambda _lane, _engine: None
        broker.acquire_writer = lambda _lane: None
        broker.release_writer = lambda _lane: None
        call = {"tool": "scene_apply", "arguments": {"sceneId": "s", "operationsPath": "ops.json"}}
        broker.call(call)
        self.assertEqual(engine.calls, [("scene_apply", {"sceneId": "s", "operations": OPERATIONS})])
        with self.assertRaises(Denied):
            broker.call({**call, "arguments": {"sceneId": "s", "operationsPath": "/etc/hosts"}})
        self.assertEqual(len(engine.calls), 1, "a refused file never reaches the engine")

    def test_the_gateway_sends_the_scratch_folder_only_with_an_operations_file(self):
        sent = []
        client = mock.Mock()
        client.call = lambda owner, tool, args, origin, policy: sent.append((tool, policy)) or {"ok": True}
        ctx = mock.Mock()
        ctx.get_config = lambda key, default=None: default
        with (
            mock.patch.object(hermes_host, "ensure_broker", lambda: contextlib.nullcontext(client)),
            mock.patch.object(hermes_host, "_profile_identity", lambda: "/profiles/hermretro"),
            mock.patch.object(hermes_host.hermes_api, "scratch_dir", lambda: Path("/h/cache/scratch")),
            mock.patch.object(hermes_host, "_deliver", lambda response, name: response),
        ):
            for args in ({"sceneId": "s", "operationsPath": "ops.json"}, {"sceneId": "s", "operations": []}):
                hermes_host.make_tool_handler(ctx, {"name": "scene_apply"})(args, conversation_id="c", session_id="c")
        self.assertEqual(sent[0][1]["scratch_dir"], "/h/cache/scratch")
        self.assertNotIn("scratch_dir", sent[1][1])


if __name__ == "__main__":
    unittest.main()
