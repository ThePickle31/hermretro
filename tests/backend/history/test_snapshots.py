"""Build history: a snapshot of a library game after each successful build, the ``builds`` and
``build_restore`` RPCs, and the post_tool_call hook that takes them."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import versions as host_assets  # noqa: E402 - the repository root goes on sys.path first
from backend.history import snapshots  # noqa: E402 - the repository root goes on sys.path first
from backend.history import hooks as history_hooks  # noqa: E402 - the repository root goes on sys.path first
from tests.support import make_project  # noqa: E402 - the repository root goes on sys.path first
from backend.system import events  # noqa: E402 - the repository root goes on sys.path first
from backend.history import rpcs as history_rpcs  # noqa: E402 - the repository root goes on sys.path first
from tests.support import FakeBrokerClient, isolated_home, make_library_game, registered_hook  # noqa: E402 - the repository root goes on sys.path first


def success(root: Path, **extra) -> str:
    """A delivered chromatic_rom_build result, as Hermes hands it to post_tool_call."""
    return json.dumps(
        {
            "result": "Build complete.",
            "structuredContent": {"success": True, "outputPath": str(root / "build" / "rom" / "game.gbc"), **extra},
        }
    )


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = make_project(self.base)
        self.store = self.base / "snapshots"
        (self.root / "assets" / "sprites").mkdir(parents=True)
        (self.root / "assets" / "sprites" / "robin.png").write_bytes(b"robin-1")
        for folder in ("artifacts", ".git", "node_modules", "captures"):
            (self.root / folder).mkdir(exist_ok=True)
            (self.root / folder / "junk.bin").write_bytes(b"x")
        (self.root / "assets" / "half.png.part").write_bytes(b"temp")

    def tearDown(self):
        self.tmp.cleanup()

    def files_of(self, identifier):
        return sorted(snapshots.walk(self.store / "g" / identifier / "files", stored=True))

    def test_a_snapshot_keeps_the_sources_and_leaves_out_output_tools_and_temp_files(self):
        os.symlink(self.base, self.root / "link-out")
        os.symlink(self.root / "project" / "scene.gbsres", self.root / "project" / "alias.gbsres")
        taken = snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertEqual(taken, {"id": "1000", "created": True})
        self.assertEqual(
            self.files_of("1000"),
            ["assets/sprites/robin.png", "cover.png", "game.json", "project/scene.gbsres", "space-game.gbsproj"],
        )
        meta = json.loads((self.store / "g" / "1000" / "snapshot.json").read_text())
        self.assertEqual(
            (meta["at"], meta["game"], meta["reason"], meta["files"], meta["builds"]), (1000, "g", "build", 5, [1000])
        )
        self.assertEqual(meta["root"], os.path.realpath(self.root))
        self.assertFalse(any(name.endswith(".part") for name in os.listdir(self.store / "g")))

    def test_an_unchanged_project_adds_its_build_to_the_newest_snapshot(self):
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertEqual(
            snapshots.take(self.store, "g", self.root, "build", now_ms=2000), {"id": "1000", "created": False}
        )
        (self.root / "build" / "project.gb").write_bytes(b"other rom")  # output does not count
        snapshots.take(self.store, "g", self.root, "build", now_ms=3000)
        self.assertEqual([item["builds"] for item in snapshots.list_snapshots(self.store, "g")], [[1000, 2000, 3000]])
        (self.root / "assets" / "sprites" / "robin.png").write_bytes(b"robin-2")
        self.assertEqual(snapshots.take(self.store, "g", self.root, "build", now_ms=4000)["created"], True)
        self.assertEqual([item["id"] for item in snapshots.list_snapshots(self.store, "g")], ["4000", "1000"])

    def test_only_the_newest_thirty_are_kept(self):
        for index in range(33):
            (self.root / "project" / "scene.gbsres").write_text(json.dumps({"n": index}))
            snapshots.take(self.store, "g", self.root, "build", now_ms=1000 + index)
        listed = [item["id"] for item in snapshots.list_snapshots(self.store, "g")]
        self.assertEqual(len(listed), snapshots.KEEP)
        self.assertEqual(listed[0], "1032")
        self.assertEqual(listed[-1], "1003")

    def test_a_project_over_the_size_cap_is_skipped(self):
        with mock.patch.object(snapshots, "MAX_BYTES", 10):
            self.assertIn("skipped", snapshots.take(self.store, "g", self.root, "build", now_ms=1000))
        self.assertEqual(snapshots.list_snapshots(self.store, "g"), [])

    def test_a_project_over_the_file_cap_is_skipped(self):
        count = len(snapshots.walk(self.root))
        with mock.patch.object(snapshots, "MAX_FILES", count - 1):
            answer = snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertEqual(answer, {"skipped": f"more than {count - 1} files"})
        self.assertEqual(snapshots.list_snapshots(self.store, "g"), [])

    def test_restore_brings_back_changed_files_removes_new_ones_and_keeps_a_backup(self):
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        (self.root / "assets" / "sprites" / "robin.png").write_bytes(b"robin-2")
        (self.root / "assets" / "sprites" / "hawk.png").write_bytes(b"hawk")
        (self.root / "project" / "new").mkdir()
        (self.root / "project" / "new" / "scene.gbsres").write_text("{}")
        (self.root / "space-game.gbsproj").unlink()
        os.symlink(self.base / "outside.txt", self.root / "assets" / "link.png")
        (self.base / "outside.txt").write_text("keep me")

        answer = snapshots.restore(self.store, "g", self.root, "1000", now_ms=5000)
        self.assertEqual(answer, {"restored": "1000", "backup": "5000", "changed": 2, "removed": 2})
        self.assertEqual((self.root / "assets" / "sprites" / "robin.png").read_bytes(), b"robin-1")
        self.assertTrue((self.root / "space-game.gbsproj").is_file())
        self.assertFalse((self.root / "assets" / "sprites" / "hawk.png").exists())
        self.assertFalse((self.root / "project" / "new").exists())  # emptied folder gone
        self.assertTrue(os.path.islink(self.root / "assets" / "link.png"))  # links untouched
        self.assertEqual((self.base / "outside.txt").read_text(), "keep me")
        for folder in ("artifacts", ".git", "node_modules", "captures", "build"):
            self.assertTrue((self.root / folder).is_dir(), folder)
        self.assertTrue((self.root / "captures" / "junk.bin").is_file())
        backup = json.loads((self.store / "g" / "5000" / "snapshot.json").read_text())
        self.assertEqual((backup["reason"], backup["from"], backup["builds"]), ("before-restore", "1000", []))
        self.assertIn("assets/sprites/hawk.png", self.files_of("5000"))

        # The backup is itself restorable: Restore can be undone.
        again = snapshots.restore(self.store, "g", self.root, "5000", now_ms=6000)
        self.assertEqual((again["changed"], again["removed"]), (3, 1))  # robin, hawk, new scene; gbsproj
        self.assertTrue((self.root / "project" / "new" / "scene.gbsres").is_file())
        self.assertEqual((self.root / "assets" / "sprites" / "hawk.png").read_bytes(), b"hawk")
        self.assertFalse((self.root / "space-game.gbsproj").exists())

    def test_restore_never_writes_through_a_link(self):
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        os.rename(self.root / "assets", self.base / "moved-assets")
        os.symlink(elsewhere, self.root / "assets")
        answer = snapshots.restore(self.store, "g", self.root, "1000", now_ms=2000)
        self.assertEqual(os.listdir(elsewhere), [])
        self.assertIn("a link or file is in the way", " ".join(answer["problems"]))

    def test_a_game_inside_this_games_folder_is_never_kept_or_restored(self):
        pond = make_project(self.root, "Pond", web=False, built=False)  # another game's project inside this one
        (pond / "project" / "scene.gbsres").write_text("pond-1")
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertFalse([name for name in self.files_of("1000") if name.startswith("pond/")])

        (pond / "project" / "scene.gbsres").write_text("pond-2")
        (pond / "project" / "new.gbsres").write_text("{}")
        (self.root / "assets" / "sprites" / "robin.png").write_bytes(b"robin-2")
        snapshots.restore(self.store, "g", self.root, "1000", now_ms=2000)
        self.assertEqual((self.root / "assets" / "sprites" / "robin.png").read_bytes(), b"robin-1")
        self.assertEqual((pond / "project" / "scene.gbsres").read_text(), "pond-2", "Pond's file was put back")
        self.assertTrue((pond / "project" / "new.gbsres").is_file(), "Pond's new file was removed")

    def test_a_nested_project_file_in_capitals_or_as_a_link_still_marks_another_game(self):
        for name, kind in (("caps", "file"), ("linked", "link")):
            folder = self.root / name
            folder.mkdir()
            (folder / "notes.txt").write_text("theirs")
            if kind == "file":
                (folder / "Caps.GBSPROJ").write_text("{}")
            else:
                (folder / "real.json").write_text("{}")
                (folder / "linked.gbsproj").symlink_to(folder / "real.json")
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertFalse([name for name in self.files_of("1000") if name.startswith(("caps/", "linked/"))])
        snapshots.restore(self.store, "g", self.root, "1000", now_ms=2000)
        self.assertEqual([(self.root / name / "notes.txt").read_text() for name in ("caps", "linked")], ["theirs"] * 2)

    def test_restore_never_writes_through_a_temporary_file_already_there(self):
        robin = self.root / "assets" / "sprites" / "robin.png"
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        robin.write_bytes(b"robin-2")
        outside = self.base / "outside.bin"
        outside.write_bytes(b"theirs")
        (robin.parent / ".robin.png.hr-restore").symlink_to(outside)
        snapshots.restore(self.store, "g", self.root, "1000", now_ms=2000)
        self.assertEqual((robin.read_bytes(), outside.read_bytes()), (b"robin-1", b"theirs"))

    def test_a_folder_that_became_a_game_since_the_snapshot_is_left_alone(self):
        later = self.root / "later"
        later.mkdir()
        (later / "notes.txt").write_text("old")
        snapshots.take(self.store, "g", self.root, "build", now_ms=1000)
        self.assertIn("later/notes.txt", self.files_of("1000"))

        (later / "later.gbsproj").write_text("{}")  # now its own game's project
        (later / "notes.txt").write_text("new")
        snapshots.restore(self.store, "g", self.root, "1000", now_ms=2000)
        self.assertEqual((later / "notes.txt").read_text(), "new")
        self.assertTrue((later / "later.gbsproj").is_file())

    def test_an_unknown_snapshot_is_refused(self):
        with self.assertRaises(snapshots.SnapshotError) as caught:
            snapshots.restore(self.store, "g", self.root, "123")
        self.assertEqual(caught.exception.code, "MISSING")
        with self.assertRaises(snapshots.SnapshotError):
            snapshots.restore(self.store, "g", self.root, "../g")

    def test_restoring_the_oldest_kept_snapshot_does_not_prune_it(self):
        for index in range(snapshots.KEEP):
            (self.root / "project" / "scene.gbsres").write_text(json.dumps({"n": index}))
            snapshots.take(self.store, "g", self.root, "build", now_ms=1000 + index)
        (self.root / "project" / "scene.gbsres").write_text("changed")
        answer = snapshots.restore(self.store, "g", self.root, "1000", now_ms=9000)
        self.assertEqual(answer["restored"], "1000")
        self.assertEqual(json.loads((self.root / "project" / "scene.gbsres").read_text()), {"n": 0})


class BuildHistoryHost(unittest.TestCase):
    """The hook and the RPCs, with a real library in a temporary folder."""

    def setUp(self):
        isolated = isolated_home(self)
        self.base = isolated.base
        connect = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        connect.start()
        self.addCleanup(connect.stop)
        self.store = isolated.data / "snapshots"
        self.game, self.root = make_library_game(isolated)
        self.outsider = make_project(self.base, name="Not Listed")

    def hook(self, **kwargs):
        registered_hook("post_tool_call")(
            **{"tool_name": "chromatic_rom_build", "args": {}, "result": success(self.root), "status": "ok", **kwargs}
        )

    def listed(self):
        return history_rpcs.rpc_builds(None)({"game": self.game})

    def test_only_a_successful_build_of_a_library_game_is_kept(self):
        self.hook(result=json.dumps({"error": "boom", "isError": True}), status="error")
        self.hook(result=json.dumps({"structuredContent": {"success": False}}))
        self.hook(result=json.dumps({"structuredContent": {"success": True}}), status="error")
        self.hook(tool_name="chromatic_web_build")
        self.hook(args={"sourcePath": "test.c"})
        self.hook(result="not json")
        self.hook(result=success(self.outsider))  # not in the library
        self.assertEqual(self.listed(), {"ok": True, "builds": []})
        self.assertFalse((self.store / games.game_id(self.outsider)).exists())
        self.hook()
        builds = self.listed()["builds"]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]["reason"], "build")
        self.assertEqual(builds[0]["builds"], [int(builds[0]["id"])])

    def test_a_kept_build_announces_history_build_kept_once(self):
        heard = []
        listener = events.on("history.build_kept")(lambda **payload: heard.append(payload))
        self.addCleanup(events._listeners["history.build_kept"].remove, listener)
        self.hook(result=json.dumps({"structuredContent": {"success": False}}))
        self.assertEqual(heard, [])
        self.hook()
        self.assertEqual(heard, [{"game": self.game, "root": self.root}])

    def test_the_project_comes_from_the_chat_when_the_result_does_not_name_it(self):
        bare = json.dumps({"structuredContent": {"success": True}})
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)):
            self.hook(result=bare, conversation_id="c1", session_id="s1")
        self.assertEqual(len(self.listed()["builds"]), 1)

    def test_a_multimodal_envelope_is_read_through_its_text(self):
        self.hook(result={"_multimodal": True, "content": [], "text_summary": success(self.root)})
        self.assertEqual(len(self.listed()["builds"]), 1)

    def test_the_normal_build_result_identifies_its_snapshot_even_when_files_are_reused(self):
        engine = FakeBrokerClient(
            {"ok": True, "result": {"structuredContent": {"success": True, "projectRoot": str(self.root)}}}
        )
        ctx = mock.Mock()
        ctx.get_config.side_effect = lambda _key, default: default
        with mock.patch.object(hermes_host, "ensure_broker", return_value=engine):
            handler = hermes_host.make_tool_handler(ctx, {"name": "rom_build"})
            first = handler({})
            self.hook(result=first)
            second = handler({})
            self.hook(result=second)

        refs = [json.loads(first)["buildRef"], json.loads(second)["buildRef"]]
        self.assertNotEqual(*refs)
        (saved,) = self.listed()["builds"]
        self.assertEqual(saved["buildRefs"], refs)
        self.assertEqual(saved["builds"], [])

        # The association lives on disk and identifies the old snapshot even after a different build.
        (self.root / "project" / "scene.gbsres").write_text("changed")
        with mock.patch.object(hermes_host, "ensure_broker", return_value=engine):
            third = handler({})
            self.hook(result=third)
        latest, earlier = self.listed()["builds"]
        self.assertEqual(latest["buildRefs"], [json.loads(third)["buildRef"]])
        self.assertEqual((earlier["id"], earlier["buildRefs"]), (saved["id"], refs))
        result = history_rpcs.rpc_build_restore(None)({"game": self.game, "id": earlier["id"], "buildRef": refs[0]})
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.root / "project" / "scene.gbsres").read_text(), "{}")

    def test_build_call_ids_are_only_exposed_for_the_bound_conversation(self):
        stored = "build-chat"
        hermes_host._registry().bind(self.game, stored, hermes_host._profile_identity())
        self.hook(
            result=json.dumps({**json.loads(success(self.root)), "buildRef": "before"}),
            conversation_id=stored,
            session_id="compressed-build-chat",
            tool_call_id="call_0",
        )
        (self.root / "project" / "scene.gbsres").write_text("other chat edited the game")
        self.hook(
            result=json.dumps({**json.loads(success(self.root)), "buildRef": "concurrent"}),
            conversation_id="other-chat",
            session_id="other-chat",
            tool_call_id="call_0",
        )
        list_builds = history_rpcs.rpc_builds(None)
        for selection in ({}, {"stored": "other-chat"}):
            self.assertTrue(
                all("buildCalls" not in item for item in list_builds({"game": self.game, **selection})["builds"])
            )
        newest, oldest = list_builds({"game": self.game, "stored": stored})["builds"]
        self.assertNotIn("buildCalls", newest)
        self.assertEqual(oldest["buildCalls"], [{"id": "call_0", "ref": "before"}])

    def test_the_hook_never_raises(self):
        with mock.patch.object(snapshots, "take", side_effect=OSError("disk full")) as take:
            self.hook()
        take.assert_called_once()  # the failed snapshot was reached, and swallowed
        registered_hook("post_tool_call")(tool_name=None)
        registered_hook("post_tool_call")()

    def test_assets_keep_inspected_images_before_the_snapshot(self):
        # post_tool_call is registered once and chains every feature's callback in backend/features.py order: only
        # assets' callback coming before build history's matters here, so a callback added later does not break it.
        chain = list(registered_hook("post_tool_call").callbacks)
        self.assertIn(host_assets.keep_inspected_images, chain)
        self.assertIn(history_hooks.snapshot_after_build, chain)
        self.assertLess(
            chain.index(host_assets.keep_inspected_images),
            chain.index(history_hooks.snapshot_after_build),
            "assets must keep the images a build looked at before history snapshots the game\n"
            "FIX: keep assets before history in backend/features.py",
        )

    def test_builds_and_restore_rpcs(self):
        restore = history_rpcs.rpc_build_restore(None)
        self.assertEqual(history_rpcs.rpc_builds(None)({"game": "nope"})["code"], "NO_GAME")
        self.assertEqual(history_rpcs.rpc_builds(None)({})["code"], "NO_GAME")
        self.assertEqual(restore({"game": games.game_id(self.outsider), "id": "1"})["code"], "NO_GAME")
        self.hook()
        first = self.listed()["builds"][0]["id"]
        self.assertEqual(restore({"game": self.game, "id": "999"})["code"], "MISSING")
        (self.root / "project" / "scene.gbsres").write_text('{"changed": true}')
        (self.root / "project" / "extra.gbsres").write_text("{}")
        answer = restore({"game": self.game, "id": first})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual((answer["restored"], answer["changed"], answer["removed"]), (first, 1, 1))
        self.assertEqual((self.root / "project" / "scene.gbsres").read_text(), "{}")
        listed = self.listed()["builds"]
        self.assertEqual([item["id"] for item in listed], [answer["backup"], first])
        self.assertEqual((listed[0]["reason"], listed[0]["from"]), ("before-restore", first))
        for item in listed:
            self.assertEqual(set(item) - {"from"}, {"id", "at", "builds", "files", "bytes", "reason"})


if __name__ == "__main__":
    unittest.main()
