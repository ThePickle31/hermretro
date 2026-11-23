"""Build page asset requests, saved frames and ownership of nested games' images."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.assets import rpcs as assets_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

SPRITE_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000020000000100806000000"
    "1f15c4890000000d49444154789c636001000000050001a5f645400000000049454e44ae426082"
)


class AssetRpc(unittest.TestCase):
    def setUp(self):
        isolated = isolated_home(self)
        self.base, self.home = isolated.base, isolated.data  # self.home: the plugin data folder
        (self.home / "frames").mkdir(parents=True)
        self.frog = make_project(self.base, "Frog Post")
        hermes_host._registry().upsert(str(self.frog))
        rpc_asset = assets_rpcs.rpc_asset(mock.Mock())
        self.asset = lambda params: rpc_asset({"root": str(self.frog), **params})  # Frog Post's own Build page

    def test_a_sprite_in_a_game_comes_with_its_size_and_frames(self):
        sprite = self.frog / "assets" / "sprites" / "frog.png"
        sprite.parent.mkdir(parents=True, exist_ok=True)
        sprite.write_bytes(SPRITE_PNG)
        (sprite.parent / "frog.png.gbsres").write_text(
            json.dumps({"name": "Frog", "canvasWidth": 16, "canvasHeight": 16, "animSpeed": 15})
        )
        answer = self.asset({"path": str(sprite)})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            (answer["width"], answer["height"], answer["kind"], answer["relative"]),
            (32, 16, "sprite", "assets/sprites/frog.png"),
        )
        self.assertEqual(answer["sprite"], {"name": "Frog", "frameWidth": 16, "frameHeight": 16, "animSpeed": 15})
        self.assertTrue(answer["dataUrl"].startswith("data:image/png;base64,"))

    def test_saved_frames_are_served_and_everything_else_is_refused(self):
        frame = self.home / "frames" / "f.png"
        frame.write_bytes(SPRITE_PNG)
        self.assertEqual(self.asset({"path": "file://" + str(frame)})["kind"], "frame")
        outside = self.base / "secret.png"
        outside.write_bytes(SPRITE_PNG)
        self.assertEqual(self.asset({"path": str(outside)})["code"], "OUTSIDE")
        link = self.frog / "escape.png"
        link.symlink_to(outside)
        self.assertEqual(
            self.asset({"path": str(link)})["code"], "OUTSIDE", "a link out of the game is followed, then refused"
        )
        text = self.frog / "notes.txt"
        text.write_text("hi")
        self.assertEqual(self.asset({"path": str(text)})["code"], "NOT_IMAGE")
        self.assertEqual(self.asset({"path": "assets/frog.png"})["code"], "INVALID")
        self.assertEqual(self.asset({"path": str(self.frog / "gone.png")})["code"], "MISSING")

    def test_another_games_images_are_never_shown_on_this_games_page(self):
        cat = make_project(self.base, "Cat Field")
        hermes_host._registry().upsert(str(cat))
        theirs = cat / "cover.png"
        theirs.write_bytes(SPRITE_PNG)
        refused = self.asset({"path": str(theirs)})
        self.assertEqual(refused["code"], "OTHER_GAME", "Frog Post's page asked for Cat Field's cover")
        self.assertEqual(self.asset({"root": str(cat), "path": str(theirs)})["kind"], "image")  # on its own page
        for params in ({}, {"root": ""}, {"root": "Cat Field"}, {"root": str(self.base)}):
            answer = assets_rpcs.rpc_asset(mock.Mock())({**params, "path": str(theirs)})
            self.assertEqual(answer["code"], "OTHER_GAME", f"no game's page, or not a library game: {params}")
        info = assets_rpcs.rpc_asset_info(mock.Mock())({"root": str(self.frog), "path": str(theirs)})
        self.assertEqual(info["code"], "OUTSIDE")
        restore = assets_rpcs.rpc_asset_restore(mock.Mock())(
            {"root": str(self.frog), "path": str(theirs), "version": "1"}
        )
        self.assertEqual(restore["code"], "INVALID")
        frame = self.home / "frames" / "f.png"
        frame.write_bytes(SPRITE_PNG)
        self.assertEqual(assets_rpcs.rpc_asset(mock.Mock())({"path": str(frame)})["kind"], "frame")  # any page

    def test_a_game_inside_another_games_folder_keeps_its_own_images(self):
        inner = self.frog / "Pond"
        (inner / "assets" / "sprites").mkdir(parents=True)
        (inner / "Pond.gbsproj").write_text("{}")
        hermes_host._registry().upsert(str(inner))
        sprite = inner / "assets" / "sprites" / "lily.png"
        sprite.write_bytes(SPRITE_PNG)
        self.assertEqual(self.asset({"path": str(sprite)})["code"], "OTHER_GAME", "Pond's sprite on Frog Post's page")
        answer = self.asset({"root": str(inner), "path": str(sprite)})
        self.assertEqual((answer["kind"], answer["relative"]), ("sprite", "assets/sprites/lily.png"))

    def test_a_game_whose_details_cannot_be_read_still_owns_its_images(self):
        inner = self.frog / "Pond"
        inner.mkdir()
        hermes_host._registry().upsert(str(inner))
        sprite = inner / "lily.png"
        sprite.write_bytes(SPRITE_PNG)
        with mock.patch.object(type(hermes_host._registry()), "library", return_value=[]):
            self.assertEqual(self.asset({"path": str(sprite)})["code"], "OTHER_GAME")

    def test_a_nested_games_pictures_are_not_in_the_outer_games_list(self):
        sprites = self.frog / "assets" / "sprites"
        (sprites / "Pond").mkdir(parents=True)
        (sprites / "frog.png").write_bytes(SPRITE_PNG)
        (sprites / "Pond" / "lily.png").write_bytes(SPRITE_PNG)
        hermes_host._registry().upsert(str(sprites / "Pond"))
        listed = assets_rpcs.rpc_assets(mock.Mock())({"root": str(self.frog)})
        self.assertEqual([item["file"] for item in listed["assets"]], ["cover.png", "frog.png"])

    def test_a_restore_never_writes_through_a_temporary_file_already_there(self):
        cover = self.frog / "cover.png"
        cover.write_bytes(SPRITE_PNG)
        os.utime(cover, ns=(10**18, 10**18))
        version = assets_rpcs.rpc_asset_info(mock.Mock())({"root": str(self.frog), "path": str(cover)})["versions"][0]
        cover.write_bytes(SPRITE_PNG + b"later")
        outside = self.base / "outside.png"
        outside.write_bytes(b"theirs")
        (self.frog / ".cover.png.restore").symlink_to(outside)
        restored = assets_rpcs.rpc_asset_restore(mock.Mock())(
            {"root": str(self.frog), "path": str(cover), "version": version["id"]}
        )
        self.assertTrue(restored["ok"], restored)
        self.assertEqual((cover.read_bytes(), outside.read_bytes()), (SPRITE_PNG, b"theirs"))


if __name__ == "__main__":
    unittest.main()
