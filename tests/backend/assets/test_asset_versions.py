"""Build page images: a file rewritten later (cover.png made again) still shows each reply the version
it delivered, and the viewer's ``asset`` call answers that version for a reply's time."""
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402

PNG_A = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (160).to_bytes(4, "big") + (144).to_bytes(4, "big") + b"A" * 20
PNG_B = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (160).to_bytes(4, "big") + (144).to_bytes(4, "big") + b"B" * 20


class AssetVersions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.data = base / "data"
        self.game = base / "games" / "Cat Field"
        self.game.mkdir(parents=True)
        self.cover = self.game / "cover.png"
        registry = mock.Mock()
        registry.library.return_value = [{"projectRoot": str(self.game)}]
        self.patches = [mock.patch.object(hermes_host, "_data_dir", return_value=self.data),
                        mock.patch.object(hermes_host, "_registry", return_value=registry)]
        for patch in self.patches:
            patch.start()
        self.asset = hermes_host.rpc_asset(None)

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def write(self, data, seconds):
        self.cover.write_bytes(data)
        os.utime(self.cover, ns=(seconds * 10**9, seconds * 10**9))

    def shown(self, **params):
        answer = self.asset({"path": str(self.cover), **params})
        self.assertTrue(answer["ok"], answer)
        return base64.b64decode(answer["dataUrl"].split(",", 1)[1]), answer

    def test_an_earlier_reply_keeps_the_version_it_delivered(self):
        self.write(PNG_A, 1000)
        hermes_host.keep_delivered_images(assistant_response=f"New cover.\n\nMEDIA:{self.cover}\n\nDone.")
        self.write(PNG_B, 2000)
        hermes_host.keep_delivered_images(assistant_response=f"MEDIA:`{self.cover}`")

        first, answer = self.shown(at=1500 * 1000)
        self.assertEqual(first, PNG_A)
        self.assertTrue(answer["earlier"])
        self.assertEqual(answer["modifiedAt"], 1000)
        self.assertEqual(self.shown(at=2500 * 1000)[0], PNG_B)
        self.assertEqual(self.shown()[0], PNG_B)                 # no time: the file as it is now

    def test_a_step_that_looked_at_an_image_keeps_it(self):
        self.write(PNG_A, 1000)
        hermes_host.keep_inspected_images(tool_name="vision_analyze", args={"image_url": str(self.cover), "question": "?"})
        self.write(PNG_B, 2000)
        self.assertEqual(self.shown(at=1500 * 1000)[0], PNG_A)

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
        folder = hermes_host._versions_dir(self.cover.resolve())
        self.assertEqual(len(list(folder.iterdir())), 1)
        outside = Path(self.tmp.name) / "elsewhere.png"
        outside.write_bytes(PNG_A)
        hermes_host.keep_delivered_images(assistant_response=f"MEDIA:{outside}")
        self.assertFalse(hermes_host._versions_dir(outside.resolve()).exists())


    def test_versions_are_listed_picked_by_id_and_restored(self):
        self.write(PNG_A, 1000)
        self.shown()
        self.write(PNG_B, 2000)
        info = hermes_host.rpc_asset_info(None)({"path": str(self.cover)})
        self.assertTrue(info["ok"], info)
        self.assertEqual(info["kind"], "cover")
        self.assertEqual([entry["current"] for entry in info["versions"]], [False, True])
        first = info["versions"][0]["id"]
        data, answer = self.shown(version=first)
        self.assertEqual(data, PNG_A)
        self.assertEqual(answer["versionId"], first)
        self.assertFalse(self.asset({"path": str(self.cover), "version": "../x"})["ok"])

        restored = hermes_host.rpc_asset_restore(None)({"path": str(self.cover), "version": first})
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes(), PNG_A)
        self.assertEqual(sum(entry["current"] for entry in restored["versions"]), 1)
        # The version that was replaced is still kept.
        kept = [hermes_host._versions_dir(self.cover.resolve()) / f"{entry['id']}.png" for entry in restored["versions"]]
        self.assertIn(PNG_B, [path.read_bytes() for path in kept if path.is_file()])

    def test_a_sprite_knows_its_animations_palette_and_scenes(self):
        import json
        sprites = self.game / "assets" / "sprites"
        backgrounds = self.game / "assets" / "backgrounds"
        scene_dir = self.game / "project" / "scenes" / "start"
        for folder in (sprites, backgrounds, scene_dir / "actors", self.game / "project" / "palettes"):
            folder.mkdir(parents=True, exist_ok=True)
        (sprites / "cat.png").write_bytes(PNG_A)
        tiles = lambda x: {"tiles": [{"x": 0, "y": 0, "sliceX": x, "sliceY": 0}, {"x": 8, "y": 0, "sliceX": x + 8, "sliceY": 0}]}
        (sprites / "cat.png.gbsres").write_text(json.dumps({
            "id": "cat", "name": "Cat", "canvasWidth": 16, "canvasHeight": 16, "animSpeed": 15, "numTiles": 4,
            "states": [{"name": "", "animationType": "multi_movement", "flipLeft": True, "animations": [
                {"frames": [tiles(32)]}, {"frames": [{"tiles": []}]}, {"frames": [tiles(16)]}, {"frames": [tiles(0)]},
                {"frames": [tiles(32), tiles(48)]}, {"frames": [{"tiles": []}]}, {"frames": [tiles(16)]}, {"frames": [tiles(0)]}]}]}))
        (backgrounds / "field.png").write_bytes(PNG_B)
        (backgrounds / "field.png.gbsres").write_text(json.dumps({"id": "field", "name": "Field"}))
        (self.game / "project" / "palettes" / "tabby.gbsres").write_text(json.dumps({"id": "tabby", "name": "Tabby", "colors": ["F8E0B0", "E87820", "B05010", "402010"]}))
        (self.game / "project" / "settings.gbsres").write_text(json.dumps({
            "startSceneId": "s1", "startX": 9, "startY": 12, "startDirection": "left", "playerSpriteSheetId": "cat",
            "defaultSpritePaletteId": "tabby"}))
        (scene_dir / "scene.gbsres").write_text(json.dumps({"id": "s1", "name": "Grassy Field", "type": "TOPDOWN", "backgroundId": "field", "width": 20, "height": 18}))
        (scene_dir / "actors" / "friend.gbsres").write_text(json.dumps({"name": "Friend", "spriteSheetId": "cat", "x": 3, "y": 4, "direction": "down", "paletteId": ""}))

        info = hermes_host.rpc_asset_info(None)({"path": str(sprites / "cat.png")})
        self.assertTrue(info["ok"], info)
        self.assertEqual(info["kind"], "sprite")
        self.assertEqual([animation["name"] for animation in info["sprite"]["animations"]][4], "Walk right")
        self.assertEqual(info["palette"]["colors"][1], "#E87820")
        self.assertEqual(info["usedIn"], [{"scene": "Grassy Field", "sceneId": "s1", "as": ["Player", "Friend"], "count": 2}])
        player, friend = info["scenes"][0]["actors"]
        self.assertEqual((player["x"], player["y"], player["flip"]), (9, 12, True))     # left mirrors the right slot
        self.assertEqual(player["tiles"][0]["sliceX"], 32)
        self.assertEqual((friend["flip"], friend["tiles"][0]["sliceX"]), (False, 0))
        self.assertTrue(info["scenes"][0]["background"].endswith("field.png"))

        background = hermes_host.rpc_asset_info(None)({"path": str(backgrounds / "field.png")})
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
        palette_file.write_text(json.dumps({"id": "tabby", "name": "Tabby", "colors": ["FFFFFF", "AAAAAA", "555555", "000000"]}))
        os.utime(palette_file, ns=(10**18, 10**18))
        self.assertEqual(self.asset({"path": str(sprites / "cat.png")})["sprite"]["palette"][0], "#FFFFFF")

    def test_the_assets_panel_lists_a_games_pictures_and_nothing_outside(self):
        sprites = self.game / "assets" / "sprites"
        sprites.mkdir(parents=True)
        (sprites / "bird.png").write_bytes(PNG_A)
        (sprites / "bird.png.gbsres").write_text('{"id": "bird", "name": "Robin"}')
        (sprites / "notes.txt").write_text("not a picture")
        self.write(PNG_B, 1000)
        outside = Path(self.tmp.name) / "secret.png"
        outside.write_bytes(PNG_A)
        (sprites / "link.png").symlink_to(outside)

        listed = hermes_host.rpc_assets(None)({"root": str(self.game)})
        self.assertTrue(listed["ok"], listed)
        self.assertEqual([(item["kind"], item["name"]) for item in listed["assets"]], [("cover", "Cover"), ("sprite", "Robin")])
        self.assertEqual(listed["assets"][1]["relative"], "assets/sprites/bird.png")
        self.assertFalse(hermes_host.rpc_assets(None)({"root": self.tmp.name})["ok"])        # not a library game
        self.assertFalse(hermes_host.rpc_assets(None)({})["ok"])


if __name__ == "__main__":
    unittest.main()
