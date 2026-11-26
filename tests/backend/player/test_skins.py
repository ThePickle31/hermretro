"""The device skins: player/skins/<id>/ with skin.webp|png and skin.json, the shipped ones and what a broken one does."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.player import skins  # noqa: E402 - the repository root goes on sys.path first

from tests.support import isolated_home  # noqa: E402 - repository root above

WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


class ShippedSkins(unittest.TestCase):
    def setUp(self):
        isolated_home(self)

    def test_the_hermes_skins_ship_in_order_and_the_first_is_the_default(self):
        ids = [skin["id"] for skin in skins.skins()]
        self.assertEqual(
            ids[:6], ["hermes-midnight", "hermes-blue", "hermes-white", "hermes-clear", "supply-co", "codex"]
        )
        self.assertEqual(skins.default_skin(), ids[0])
        self.assertIn({"id": "hermes-midnight", "name": "Nous Black", "swatch": "#15171c"}, skins.page_skins())

    def test_modretro_finishes_ship_as_skins_with_the_engine_colours(self):
        listed = {skin["id"]: skin for skin in skins.skins()}
        modretro = {"supply-co", "codex", "cloud", "midnight", "wave", "leaf", "inferno", "volt", "bubblegum"}
        modretro |= {f"transparent-{tint}" for tint in ("green", "red", "smoke", "purple")}
        self.assertLessEqual(modretro, set(listed))
        self.assertEqual((listed["midnight"]["name"], listed["midnight"]["background"]), ("Midnight", "#4e4f55"))
        self.assertEqual(listed["supply-co"]["image"].name, "skin.png")

    def test_the_engine_finds_every_finish_it_lists_in_the_skin_folders(self):
        # The engine's preview and live-feed window read chromatic-<id>.<ext> as player/skins/<id>/skin.<ext>.
        module = (skins.paths.ENGINE_ROOT / "dist" / "web-preview.js").read_text(encoding="utf-8")
        listed = re.search(r"const DEVICE_IMAGES = \[([^\]]+)\]", module).group(1)
        for skin_id in re.findall(r'"([a-z0-9-]+)"', listed):
            image = "skin.png" if skin_id == "supply-co" else "skin.webp"
            self.assertTrue((skins.SKINS_DIR / skin_id / image).is_file(), f"player/skins/{skin_id}/{image}")

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
        isolated_home(self)
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

    def test_personal_finish_overrides_its_bundled_id(self):
        self.add("sunset", {})
        before = skins.rail_entries()
        personal = skins.paths.hermretro_home() / "skins" / "sunset"
        personal.mkdir(parents=True)
        reference = (skins.paths.SKINS_DIR / "hermes-midnight" / "skin.webp").read_bytes()
        (personal / "skin.webp").write_bytes(reference)
        (personal / "skin.json").write_text('{"name":"Personal"}')
        self.assertNotEqual(skins.rail_entries(), before)
        self.assertEqual([skin["image"] for skin in skins.skins()], [personal / "skin.webp"])
        elsewhere = personal.rename(personal.parent.parent / "moved-personal-skin")
        self.addCleanup(elsewhere.rmdir)
        self.addCleanup((elsewhere / "skin.webp").unlink)
        self.addCleanup((elsewhere / "skin.json").unlink)
        personal.symlink_to(elsewhere, target_is_directory=True)
        with self.assertLogs(skins.logger, "WARNING"):
            self.assertEqual(skins.rail_entries(), before)
        bundled = self.folder / "sunset" / "skin.webp"
        with self.assertLogs(skins.logger, "WARNING"):
            self.assertEqual(skins.image_for("sunset"), bundled)
        personal.unlink()
        personal.mkdir()
        # A declared canvas without pixels cannot display a finish.
        empty_webp = b"WEBPVP8X" + (10).to_bytes(4, "little") + bytes(10)
        empty_webp = b"RIFF" + len(empty_webp).to_bytes(4, "little") + empty_webp
        png = (skins.paths.SKINS_DIR / "supply-co" / "skin.png").read_bytes()
        for name, data in (
            ("skin.webp", reference[:16]),
            ("skin.webp", empty_webp),
            ("skin.png", png[:33] + png[-12:]),
        ):
            with self.subTest(name=name, size=len(data)):
                file = personal / name
                file.write_bytes(data)
                with self.assertLogs(skins.logger, "WARNING"):
                    self.assertEqual(skins.image_for("sunset"), bundled)
                file.unlink()

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
        self.add("too-deep", "[" * 4000)
        self.add("good", {})
        with self.assertLogs(skins.logger, "WARNING") as logged:
            self.assertEqual([skin["id"] for skin in skins.skins()], ["good"])
        self.assertEqual(len(logged.output), 4)

    def test_engine_ids_are_skins_and_the_rail_lists_every_skin_in_order(self):
        self.add("cloud", {"order": 2, "background": "#e5e6e3", "ink": "#27272b"})
        self.add("transparent-green", {"order": 3})
        self.add("mine", {"name": "Mine", "edition": "Club", "background": "#112233", "ink": "#ffffff", "order": 1})
        self.assertEqual([skin["id"] for skin in skins.skins()], ["mine", "cloud", "transparent-green"])
        self.assertEqual(skins.image_for("cloud"), self.folder / "cloud" / "skin.webp")
        self.assertEqual(
            skins.rail_entries().splitlines()[:2],
            [
                '    { id: "mine", name: "Club · Mine", background: "#112233", ink: "#ffffff" },',
                '    { id: "cloud", name: "Cloud", background: "#e5e6e3", ink: "#27272b" },',
            ],
        )

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
        skins.rail_entries().encode("utf-8")

    def test_no_skins_or_no_folder_leaves_the_engine_default(self):
        self.assertEqual((skins.skins(), skins.default_skin(), skins.rail_entries()), ([], "", ""))
        with mock.patch.object(skins, "SKINS_DIR", self.folder / "gone"):
            self.assertEqual((skins.skins(), skins.rail_entries(), skins.page_skins()), ([], "", []))


if __name__ == "__main__":
    unittest.main()
