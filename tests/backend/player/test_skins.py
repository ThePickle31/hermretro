"""The device skins: player/skins/<id>/ with skin.webp|png and skin.json, the shipped ones and what a broken one does."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.player import skins  # noqa: E402 - the repository root goes on sys.path first

WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


class ShippedSkins(unittest.TestCase):
    def test_the_hermes_skins_ship_in_order_and_the_first_is_the_default(self):
        ids = [skin["id"] for skin in skins.skins()]
        hermes = [skin_id for skin_id in ids if skin_id.startswith("hermes-")]
        self.assertEqual(hermes, ["hermes-midnight", "hermes-blue", "hermes-white", "hermes-clear"])
        self.assertEqual(skins.default_skin(), ids[0])
        self.assertIn({"id": "hermes-midnight", "name": "Midnight", "swatch": "#15171c"}, skins.page_skins())

    def test_every_shipped_skin_image_is_a_webp_or_png(self):
        for skin in skins.skins():
            head = skin["image"].read_bytes()[:12]
            self.assertTrue(head[8:12] == b"WEBP" or head[:8] == b"\x89PNG\r\n\x1a\n", skin["id"])

    def test_every_folder_is_a_usable_skin_of_only_its_two_files(self):
        usable = {skin["id"] for skin in skins.skins()}
        for folder in skins.SKINS_DIR.iterdir():
            self.assertIn(folder.name, usable, f"player/skins/{folder.name} is not a usable skin")
            extra = {path.name for path in folder.iterdir()} - {"skin.webp", "skin.png", "skin.json"}
            self.assertEqual(extra, set(), f"player/skins/{folder.name} holds files no skin uses")


class AFolderOfSkins(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        patch = mock.patch.object(skins, "SKINS_DIR", self.folder)
        patch.start()
        self.addCleanup(patch.stop)

    def add(self, skin_id, data, image=".webp"):
        folder = self.folder / skin_id
        folder.mkdir()
        if image:
            (folder / f"skin{image}").write_bytes(WEBP)
        if data is not None:
            (folder / "skin.json").write_text(data if isinstance(data, str) else json.dumps(data))

    def test_a_folder_with_only_its_image_is_a_skin_with_defaults(self):
        self.add("sunset-orange", None, image=".png")
        (skin,) = skins.skins()
        self.assertEqual(
            {key: skin[key] for key in ("id", "name", "edition", "background", "ink", "order")},
            {
                "id": "sunset-orange",
                "name": "Sunset Orange",
                "edition": "",
                "background": "#15171c",
                "ink": "#e6edf3",
                "order": 100,
            },
        )
        self.assertEqual(skins.image_for("sunset-orange"), self.folder / "sunset-orange" / "skin.png")

    def test_order_then_id_and_bad_values_fall_back(self):
        self.add("b-skin", {"order": 2, "name": "  Bee  ", "background": "red", "ink": "#ABCDEF"})
        self.add("a-skin", {"order": 2})
        self.add("first", {"order": 1, "edition": "Club"})
        self.assertEqual([skin["id"] for skin in skins.skins()], ["first", "a-skin", "b-skin"])
        bee = skins.skins()[2]
        self.assertEqual((bee["name"], bee["background"], bee["ink"]), ("Bee", "#15171c", "#ABCDEF"))

    def test_a_skin_that_cannot_be_used_is_left_out(self):
        self.add("no-image", {}, image=None)
        self.add("Bad_Id", {})
        self.add("broken", "{not json")
        self.add("good", {})
        with self.assertLogs(skins.logger, "WARNING") as logged:
            self.assertEqual([skin["id"] for skin in skins.skins()], ["good"])
        self.assertEqual(len(logged.output), 3)

    def test_an_engine_finish_id_is_left_out_everywhere(self):
        self.assertIn("cloud", skins.engine_ids())
        self.add("cloud", {"order": 1})
        self.add("transparent-sunset", {"order": 1})
        self.add("mine", {"name": "Mine", "edition": "Club", "background": "#112233", "ink": "#ffffff"})
        with self.assertLogs(skins.logger, "WARNING") as logged:
            self.assertEqual([skin["id"] for skin in skins.skins()], ["mine"])
            self.assertEqual((skins.default_skin(), skins.image_for("cloud")), ("mine", None))
            entries, order = skins.rail_entries()
        self.assertTrue(all("the engine has a finish" in line for line in logged.output))
        self.assertEqual(entries, '    { id: "mine", name: "Club · Mine", background: "#112233", ink: "#ffffff" },\n')
        self.assertEqual(order, '.codex-game-view .cgv-color[data-device-color="mine"] { order: -4; }\n')

    def test_links_and_text_the_player_cannot_serve_are_kept_out(self):
        outside = self.folder.parent / f"{self.folder.name}-outside"
        outside.mkdir()
        self.addCleanup(lambda: [path.unlink() for path in outside.iterdir()] and None or outside.rmdir())
        (outside / "skin.webp").write_bytes(WEBP)
        (self.folder / "linked").symlink_to(outside)
        self.add("file-link", None, image=None)
        (self.folder / "file-link" / "skin.webp").symlink_to(outside / "skin.webp")
        self.add("odd-name", '{"name": "\\ud800", "edition": "Club"}')
        with self.assertLogs(skins.logger, "WARNING") as logged:
            listed = skins.skins()
        self.assertEqual([skin["id"] for skin in listed], ["odd-name"])
        self.assertEqual(listed[0]["name"], "Odd Name", "a name that cannot be served falls back to the folder's")
        self.assertEqual(len(logged.output), 2)
        skins.rail_entries()[0].encode("utf-8")

    def test_no_skins_or_no_folder_leaves_the_engine_default(self):
        self.assertEqual((skins.skins(), skins.default_skin(), skins.rail_entries()), ([], "", ("", "")))
        with mock.patch.object(skins, "SKINS_DIR", self.folder / "gone"):
            self.assertEqual((skins.skins(), skins.signature(), skins.page_skins()), ([], (), []))


if __name__ == "__main__":
    unittest.main()
