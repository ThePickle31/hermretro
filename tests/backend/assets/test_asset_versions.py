"""Build page images: a file rewritten later (cover.png made again) still shows each reply the version
it delivered, and the viewer's ``asset`` call answers that version for a reply's time."""

import base64
import hashlib
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.assets import rpcs as assets_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import versions as assets_versions  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_library_game  # noqa: E402 - the repository root goes on sys.path first

PNG_A = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (160).to_bytes(4, "big") + (144).to_bytes(4, "big") + b"A" * 20
PNG_B = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (160).to_bytes(4, "big") + (144).to_bytes(4, "big") + b"B" * 20


def path_digest(real: Path) -> str:
    """The folder name earlier releases kept an image's versions under: its resolved path alone."""
    return hashlib.sha256(str(real).encode("utf-8")).hexdigest()[:24]


class AssetVersions(unittest.TestCase):
    def setUp(self):
        # A real library game, not a mocked registry: the emitter reaches every feature's listeners.py, and a
        # listener reading the library from a Mock would fail silently.
        home = isolated_home(self)
        self.outside = home.base / "outside"
        self.outside.mkdir()
        _game, self.game = make_library_game(home, "Cat Field")
        self.cover = self.game / "cover.png"
        rpc_asset = assets_rpcs.rpc_asset(None)
        self.asset = lambda params: rpc_asset({"root": str(self.game), **params})  # this game's own Build page
        self.data = home.data

    def write(self, data, seconds):
        self.cover.write_bytes(data)
        os.utime(self.cover, ns=(seconds * 10**9, seconds * 10**9))

    def shown(self, **params):
        answer = self.asset({"path": str(self.cover), **params})
        self.assertTrue(answer["ok"], answer)
        return base64.b64decode(answer["dataUrl"].split(",", 1)[1]), answer

    def test_an_earlier_reply_keeps_the_version_it_delivered(self):
        self.write(PNG_A, 1000)
        assets_versions.keep_delivered_images(assistant_response=f"New cover.\n\nMEDIA:{self.cover}\n\nDone.")
        self.write(PNG_B, 2000)
        assets_versions.keep_delivered_images(assistant_response=f"MEDIA:`{self.cover}`")

        first, answer = self.shown(at=1500 * 1000)
        self.assertEqual(first, PNG_A)
        self.assertTrue(answer["earlier"])
        self.assertEqual(answer["modifiedAt"], 1000)
        self.assertEqual(self.shown(at=2500 * 1000)[0], PNG_B)
        self.assertEqual(self.shown()[0], PNG_B)  # no time: the file as it is now

    def test_a_step_that_looked_at_an_image_keeps_it(self):
        self.write(PNG_A, 1000)
        assets_versions.keep_inspected_images(
            tool_name="vision_analyze", args={"image_url": str(self.cover), "question": "?"}
        )
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_A)

    def test_each_image_a_several_asset_import_wrote_is_kept(self):
        """The import names its images relative to the project, as the agent wrote them: they resolve against the
        chat's game."""
        self.write(PNG_A, 1000)
        result = json.dumps(
            {"structuredContent": {"imported": [{"assetPath": "cover.png", "kind": "sprite"}, "x"], "count": 2}}
        )
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.game)):
            assets_versions.keep_inspected_images(
                tool_name="chromatic_asset_import",
                args={"assets": [{"assetPath": "cover.png", "kind": "sprite"}]},
                result=result,
                conversation_id="c",
                session_id="s",
            )
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_A)

    def test_a_single_import_with_a_relative_path_is_kept(self):
        self.write(PNG_A, 1000)
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.game)):
            assets_versions.keep_inspected_images(
                tool_name="chromatic_asset_import",
                args={"assetPath": "cover.png", "kind": "sprite"},
                result=json.dumps({"structuredContent": {"assetPath": "cover.png", "kind": "sprite"}}),
            )
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_A)

    def test_a_failed_import_keeps_nothing(self):
        self.write(PNG_A, 1000)
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.game)):
            assets_versions.keep_inspected_images(
                tool_name="chromatic_asset_import",
                args={"assetPath": "cover.png", "kind": "sprite"},
                result=json.dumps({"error": "INVALID_SPRITE_DIMENSIONS", "isError": True}),
            )
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_B)

    def test_an_unkept_older_version_falls_back_to_the_file(self):
        self.write(PNG_B, 2000)
        data, answer = self.shown(at=1500 * 1000)
        self.assertEqual(data, PNG_B)
        self.assertFalse(answer["earlier"])

    def test_identical_rewrites_are_kept_once_and_outside_images_never(self):
        self.write(PNG_A, 1000)
        self.shown()
        self.write(PNG_A, 2000)
        self.shown()
        folder = assets_versions._versions_dir(self.cover.resolve(), self.game.resolve())
        self.assertEqual(len(list(folder.iterdir())), 1)
        outside = self.outside / "elsewhere.png"
        outside.write_bytes(PNG_A)
        assets_versions.keep_delivered_images(assistant_response=f"MEDIA:{outside}")
        self.assertEqual(list(folder.parent.iterdir()), [folder])  # nothing kept for the image outside every game

    def test_versions_are_listed_picked_by_id_and_restored(self):
        self.write(PNG_A, 1000)
        self.shown()
        self.write(PNG_B, 2000)
        info = assets_rpcs.rpc_asset_info(None)({"root": str(self.game), "path": str(self.cover)})
        self.assertTrue(info["ok"], info)
        self.assertEqual(info["kind"], "cover")
        self.assertEqual([entry["current"] for entry in info["versions"]], [False, True])
        first = info["versions"][0]["id"]
        data, answer = self.shown(version=first)
        self.assertEqual(data, PNG_A)
        self.assertEqual(answer["versionId"], first)
        self.assertFalse(self.asset({"path": str(self.cover), "version": "../x"})["ok"])

        restored = assets_rpcs.rpc_asset_restore(None)(
            {"root": str(self.game), "path": str(self.cover), "version": first}
        )
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes(), PNG_A)
        self.assertEqual(sum(entry["current"] for entry in restored["versions"]), 1)
        # The version that was replaced is still kept.
        kept = [
            assets_versions._versions_dir(self.cover.resolve(), self.game.resolve()) / f"{entry['id']}.png"
            for entry in restored["versions"]
        ]
        self.assertIn(PNG_B, [path.read_bytes() for path in kept if path.is_file()])

    def test_a_sprite_knows_its_animations_palette_and_scenes(self):
        import json

        sprites = self.game / "assets" / "sprites"
        backgrounds = self.game / "assets" / "backgrounds"
        scene_dir = self.game / "project" / "scenes" / "start"
        for folder in (sprites, backgrounds, scene_dir / "actors", self.game / "project" / "palettes"):
            folder.mkdir(parents=True, exist_ok=True)
        (sprites / "cat.png").write_bytes(PNG_A)
        tiles = lambda x: {
            "tiles": [{"x": 0, "y": 0, "sliceX": x, "sliceY": 0}, {"x": 8, "y": 0, "sliceX": x + 8, "sliceY": 0}]
        }
        (sprites / "cat.png.gbsres").write_text(
            json.dumps(
                {
                    "id": "cat",
                    "name": "Cat",
                    "canvasWidth": 16,
                    "canvasHeight": 16,
                    "animSpeed": 15,
                    "numTiles": 4,
                    "states": [
                        {
                            "name": "",
                            "animationType": "multi_movement",
                            "flipLeft": True,
                            "animations": [
                                {"frames": [tiles(32)]},
                                {"frames": [{"tiles": []}]},
                                {"frames": [tiles(16)]},
                                {"frames": [tiles(0)]},
                                {"frames": [tiles(32), tiles(48)]},
                                {"frames": [{"tiles": []}]},
                                {"frames": [tiles(16)]},
                                {"frames": [tiles(0)]},
                            ],
                        }
                    ],
                }
            )
        )
        (backgrounds / "field.png").write_bytes(PNG_B)
        (backgrounds / "field.png.gbsres").write_text(json.dumps({"id": "field", "name": "Field"}))
        (self.game / "project" / "palettes" / "tabby.gbsres").write_text(
            json.dumps({"id": "tabby", "name": "Tabby", "colors": ["F8E0B0", "E87820", "B05010", "402010"]})
        )
        (self.game / "project" / "settings.gbsres").write_text(
            json.dumps(
                {
                    "startSceneId": "s1",
                    "startX": 9,
                    "startY": 12,
                    "startDirection": "left",
                    "playerSpriteSheetId": "cat",
                    "defaultSpritePaletteId": "tabby",
                }
            )
        )
        (scene_dir / "scene.gbsres").write_text(
            json.dumps(
                {
                    "id": "s1",
                    "name": "Grassy Field",
                    "type": "TOPDOWN",
                    "backgroundId": "field",
                    "width": 20,
                    "height": 18,
                }
            )
        )
        (scene_dir / "actors" / "friend.gbsres").write_text(
            json.dumps({"name": "Friend", "spriteSheetId": "cat", "x": 3, "y": 4, "direction": "down", "paletteId": ""})
        )

        info = assets_rpcs.rpc_asset_info(None)({"root": str(self.game), "path": str(sprites / "cat.png")})
        self.assertTrue(info["ok"], info)
        self.assertEqual(info["kind"], "sprite")
        self.assertEqual([animation["name"] for animation in info["sprite"]["animations"]][4], "Walk right")
        self.assertEqual(info["palette"]["colors"][1], "#E87820")
        self.assertEqual(
            info["usedIn"], [{"scene": "Grassy Field", "sceneId": "s1", "as": ["Player", "Friend"], "count": 2}]
        )
        player, friend = info["scenes"][0]["actors"]
        self.assertEqual((player["x"], player["y"], player["flip"]), (9, 12, True))  # left mirrors the right slot
        self.assertEqual(player["tiles"][0]["sliceX"], 32)
        self.assertEqual((friend["flip"], friend["tiles"][0]["sliceX"]), (False, 0))
        self.assertTrue(info["scenes"][0]["background"].endswith("field.png"))

        background = assets_rpcs.rpc_asset_info(None)({"root": str(self.game), "path": str(backgrounds / "field.png")})
        self.assertEqual((background["kind"], background["usedIn"][0]["scene"]), ("background", "Grassy Field"))

        # Thumbnails draw a sprite the way the game does: the asset call carries its palette, the frame
        # its first use stands in (the player faces left: the right frame mirrored) and its moving frames.
        sprite = self.asset({"path": str(sprites / "cat.png")})["sprite"]
        self.assertEqual(sprite["palette"], ["#F8E0B0", "#E87820", "#B05010", "#402010"])
        self.assertEqual((sprite["standing"]["flip"], sprite["standing"]["tiles"][0]["sliceX"]), (True, 32))
        self.assertEqual([frame[0]["sliceX"] for frame in sprite["moving"]["frames"]], [32, 48])
        self.assertTrue(sprite["moving"]["flip"])
        # A changed palette is seen at once (the cache follows the project files).
        palette_file = self.game / "project" / "palettes" / "tabby.gbsres"
        palette_file.write_text(
            json.dumps({"id": "tabby", "name": "Tabby", "colors": ["FFFFFF", "AAAAAA", "555555", "000000"]})
        )
        os.utime(palette_file, ns=(10**18, 10**18))
        self.assertEqual(self.asset({"path": str(sprites / "cat.png")})["sprite"]["palette"][0], "#FFFFFF")

    def test_the_assets_panel_lists_a_games_pictures_and_nothing_outside(self):
        sprites = self.game / "assets" / "sprites"
        sprites.mkdir(parents=True)
        (sprites / "bird.png").write_bytes(PNG_A)
        (sprites / "bird.png.gbsres").write_text('{"id": "bird", "name": "Robin"}')
        (sprites / "notes.txt").write_text("not a picture")
        self.write(PNG_B, 1000)
        outside = self.outside / "secret.png"
        outside.write_bytes(PNG_A)
        (sprites / "link.png").symlink_to(outside)

        listed = assets_rpcs.rpc_assets(None)({"root": str(self.game)})
        self.assertTrue(listed["ok"], listed)
        self.assertEqual(
            [(item["kind"], item["name"]) for item in listed["assets"]], [("cover", "Cover"), ("sprite", "Robin")]
        )
        self.assertEqual(listed["assets"][1]["relative"], "assets/sprites/bird.png")
        self.assertFalse(assets_rpcs.rpc_assets(None)({"root": str(self.outside)})["ok"])  # not a library game
        self.assertFalse(assets_rpcs.rpc_assets(None)({})["ok"])

    def test_older_versions_counts_the_kept_versions_but_not_the_current_one(self):
        self.assertEqual(assets_versions.older_versions(self.cover.resolve(), self.game.resolve()), 0)  # no file yet
        self.write(PNG_A, 1000)
        self.shown()
        self.assertEqual(
            assets_versions.older_versions(self.cover.resolve(), self.game.resolve()), 0
        )  # only the current one
        self.write(PNG_B, 2000)
        self.shown()
        self.write(PNG_A, 3000)
        self.shown()
        self.assertEqual(assets_versions.older_versions(self.cover.resolve(), self.game.resolve()), 2)

    def test_a_folder_that_becomes_a_game_starts_with_none_of_the_outer_games_versions(self):
        pond = self.game / "pond"
        (pond / "assets").mkdir(parents=True)
        lily = pond / "assets" / "lily.png"
        for data, seconds in ((PNG_A, 1000), (PNG_B, 2000)):
            lily.write_bytes(data)
            os.utime(lily, ns=(seconds * 10**9, seconds * 10**9))
            self.asset({"path": str(lily)})  # Cat Field's picture, shown on its page: both versions kept
        (pond / "pond.gbsproj").write_text("{}")
        hermes_host._registry().upsert(str(pond))  # the folder is a game of its own now

        pond_page = {"root": str(pond), "path": str(lily)}
        info = assets_rpcs.rpc_asset_info(None)(pond_page)
        self.assertEqual([entry["current"] for entry in info["versions"]], [True], "only the file as it is now")
        self.assertFalse(assets_rpcs.rpc_asset(None)({**pond_page, "at": 1500 * 1000})["earlier"])
        outer_history = assets_versions._versions_dir(lily.resolve(), self.game.resolve())
        older = assets_versions._versions(lily, outer_history)[0]["id"]
        self.assertEqual(assets_rpcs.rpc_asset(None)({**pond_page, "version": older})["code"], "MISSING")
        self.assertEqual(assets_rpcs.rpc_asset_restore(None)({**pond_page, "version": older})["code"], "MISSING")
        self.assertEqual(lily.read_bytes(), PNG_B)

    def test_versions_kept_by_path_alone_move_to_their_game(self):
        self.write(PNG_A, 1000)
        old = self.data / "asset-versions" / path_digest(self.cover.resolve())
        old.mkdir(parents=True)
        (old / f"{1000 * 10**9}.png").write_bytes(PNG_A)
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_A)
        self.assertFalse(old.exists())

    def test_versions_kept_by_path_alone_never_move_to_a_game_that_no_longer_holds_the_image(self):
        self.write(PNG_A, 1000)
        old = self.data / "asset-versions" / path_digest(self.cover.resolve())
        old.mkdir(parents=True)
        (old / f"{1000 * 10**9}.png").write_bytes(PNG_A)
        stale = self.outside.resolve()  # an owner picked a moment ago that holds the image no more
        self.assertFalse(assets_versions._versions_dir(self.cover.resolve(), stale).exists())
        self.assertTrue(old.is_dir())

    def test_versions_kept_by_path_alone_stay_put_when_two_games_hold_the_image(self):
        pond = self.game / "pond"
        pond.mkdir()
        (pond / "pond.gbsproj").write_text("{}")
        hermes_host._registry().upsert(str(pond))
        lily = pond / "lily.png"
        lily.write_bytes(PNG_A)
        os.utime(lily, ns=(1000 * 10**9, 1000 * 10**9))
        old = self.data / "asset-versions" / path_digest(lily.resolve())  # Cat Field's or Pond's?
        old.mkdir(parents=True)
        (old / f"{500 * 10**9}.png").write_bytes(PNG_B)
        answer = assets_rpcs.rpc_asset(None)({"root": str(pond), "path": str(lily), "at": 700 * 1000})
        self.assertFalse(answer["earlier"])
        self.assertTrue(old.is_dir())

    def test_a_too_large_image_names_the_limit(self):
        self.assertEqual(assets_versions.size_text(6 * 1024 * 1024), "6 MB")
        self.assertEqual(assets_versions.size_text(512 * 1024), "512 KB")
        self.write(PNG_A, 1000)
        with mock.patch.object(assets_rpcs, "ASSET_MAX_BYTES", 16):
            answer = self.asset({"path": str(self.cover)})
        self.assertEqual(answer["code"], "TOO_LARGE")
        self.assertEqual(answer["error"], "The image is larger than 16 bytes, too large to preview.")

    def test_earlier_preview_uses_the_size_of_the_selected_file(self):
        self.write(PNG_A, 1000)
        path = str(self.cover)
        _, first = self.shown()
        selected = first["versionId"]
        limit = assets_versions.ASSET_MAX_BYTES
        with self.cover.open("wb") as image:
            image.truncate(limit + 1)
        os.utime(self.cover, ns=(2000 * 10**9, 2000 * 10**9))

        for params in ({"at": 1_500_000}, {"version": selected}):
            with self.subTest(params=params):
                data, answer = self.shown(**params)
                self.assertEqual(data, PNG_A)
                self.assertEqual(answer["versionId"], selected)
                self.assertTrue(answer["earlier"])
        self.assertEqual(self.asset({"path": path})["code"], "TOO_LARGE")
        info = assets_rpcs.rpc_asset_info(None)({"path": path, "root": str(self.game)})
        self.assertTrue(info["ok"], info)
        self.assertEqual(
            [(entry["id"], entry["current"]) for entry in info["versions"]],
            [(selected, False), (str(2000 * 10**9), True)],
        )

        self.write(PNG_B, 2000)
        kept = assets_versions._versions_dir(self.cover, self.game) / f"{selected}.png"
        with kept.open("wb") as image:
            image.truncate(limit + 1)
        for params in ({"at": 1_500_000}, {"version": selected}):
            with self.subTest(params=params):
                self.assertEqual(self.asset({"path": path, **params})["code"], "TOO_LARGE")
        self.assertEqual(self.shown()[0], PNG_B)


def documented_keep() -> int:
    """The per-file limit .agents/skills/hermretro-dev-page/references/build-page.md's "Versions" paragraph states ("up to 40 per file")."""
    text = (
        Path(__file__).resolve().parents[3] / ".agents/skills/hermretro-dev-page/references/build-page.md"
    ).read_text(encoding="utf-8")
    found = re.search(r"^Versions: the plugin keeps a copy of a game image \(up to (\d+) per file", text, re.MULTILINE)
    assert found, (
        ".agents/skills/hermretro-dev-page/references/build-page.md has no Versions paragraph stating the per-file limit"
    )
    return int(found.group(1))


class AssetRetention(unittest.TestCase):
    """The default limit end to end: rewrite one image past it through the real hook and read what is kept."""

    def setUp(self):
        home = isolated_home(self)
        _game, self.game = make_library_game(home, "Cat Field")
        self.cover = self.game / "cover.png"

    def rewrite(self, index):
        """Version ``index``: a small PNG of its own and a modification time of ``1000 + index`` seconds."""
        self.cover.write_bytes(PNG_A[:24] + index.to_bytes(2, "big"))
        seconds = (1000 + index) * 10**9
        os.utime(self.cover, ns=(seconds, seconds))
        assets_versions.keep_inspected_images(tool_name="vision_analyze", args={"image_url": str(self.cover)})

    def kept(self):
        folder = assets_versions._versions_dir(self.cover.resolve(), self.game.resolve())
        files = sorted(folder.iterdir(), key=lambda item: int(item.stem))
        return [int(item.stem) // 10**9 - 1000 for item in files], [
            int.from_bytes(f.read_bytes()[24:], "big") for f in files
        ]

    def test_the_newest_documented_number_are_kept_and_the_oldest_dropped(self):
        limit = documented_keep()
        for index in range(limit):
            self.rewrite(index)
        self.assertEqual(self.kept(), (list(range(limit)), list(range(limit))), f"all {limit} versions up to the limit")
        self.rewrite(limit)
        newest = list(range(1, limit + 1))
        self.assertEqual(
            self.kept(),
            (newest, newest),
            f"one past the limit: version 0 dropped, 1 to {limit} kept (ASSET_KEEP_VERSIONS must match the docs)",
        )
        info = assets_rpcs.rpc_asset_info(None)({"root": str(self.game), "path": str(self.cover)})
        self.assertEqual([int(entry["id"]) // 10**9 - 1000 for entry in info["versions"]], newest)  # oldest first
        self.assertEqual([entry["current"] for entry in info["versions"]], [False] * (limit - 1) + [True])


if __name__ == "__main__":
    unittest.main()
