"""The device skins: player/skins/<id>.webp|png with <id>.json, the shipped ones and what a broken one does."""

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

    def test_every_file_in_the_folder_is_part_of_a_usable_skin(self):
        usable = {skin["id"] for skin in skins.skins()}
        for path in skins.SKINS_DIR.iterdir():
            self.assertIn(path.stem, usable, f"{path.name} is not part of a usable skin")


class AFolderOfSkins(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        patch = mock.patch.object(skins, "SKINS_DIR", self.folder)
        patch.start()
        self.addCleanup(patch.stop)

    def add(self, skin_id, data, image=".webp"):
        if image:
            (self.folder / f"{skin_id}{image}").write_bytes(WEBP)
        (self.folder / f"{skin_id}.json").write_text(data if isinstance(data, str) else json.dumps(data))

    def test_an_image_and_an_empty_json_make_a_skin_with_defaults(self):
        self.add("sunset-orange", {}, image=".png")
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
        self.assertEqual(skins.image_for("sunset-orange"), self.folder / "sunset-orange.png")

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

    def test_the_rail_lists_them_first_and_skips_an_engine_id(self):
        self.add("cloud", {"order": 1})
        self.add("mine", {"name": "Mine", "edition": "Club", "background": "#112233", "ink": "#ffffff"})
        with self.assertLogs(skins.logger, "WARNING"):
            entries, order = skins.rail_entries({"cloud", "codex"})
        self.assertEqual(entries, '    { id: "mine", name: "Club · Mine", background: "#112233", ink: "#ffffff" },\n')
        self.assertEqual(order, '.codex-game-view .cgv-color[data-device-color="mine"] { order: -4; }\n')

    def test_no_skins_leaves_the_engine_default(self):
        self.assertEqual((skins.skins(), skins.default_skin(), skins.rail_entries(set())), ([], "", ("", "")))


if __name__ == "__main__":
    unittest.main()
