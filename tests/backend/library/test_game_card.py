"""The game card (game.json + cover.png), chromatic_game_info, and presenting only a finished card."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tests/, for support

from backend.library import game_card  # noqa: E402
from backend.library import games  # noqa: E402
from backend.hermes import host as hermes_host  # noqa: E402
from support import throwaway_profile  # noqa: E402
from tests.backend.library.test_games import COVER, encode_png, make_project  # noqa: E402

GOOD = {"title": "Space Game", "tagline": "Fly a tiny ship through a meteor field.",
        "description": "Dodge meteors, grab fuel cells and reach the space station before your tank runs dry.",
        "genres": ["Arcade", "Action"]}


class CoverCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def png(self, name, data):
        path = self.base / name
        path.write_bytes(data)
        return path

    def test_a_pixel_art_cover_passes(self):
        result = game_card.check_cover(self.png("ok.png", COVER))
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["width"], result["height"], result["colours"]), (160, 144, 4))

    def test_the_wrong_size_too_many_colours_transparency_and_blank_are_refused(self):
        small = encode_png(80, 72, lambda x, y: (x * 3, y * 3, 0, 255))
        self.assertIn("must be exactly 160x144", game_card.check_cover(self.png("small.png", small))["problem"])
        smooth = encode_png(160, 144, lambda x, y: (x, y, (x + y) % 256, 255))
        self.assertIn("pixel art uses at most 32", game_card.check_cover(self.png("smooth.png", smooth))["problem"])
        seethrough = encode_png(160, 144, lambda x, y: (10 * (x % 3), 0, 0, 128 if x == 0 else 255))
        self.assertIn("transparent", game_card.check_cover(self.png("alpha.png", seethrough))["problem"])
        blank = encode_png(160, 144, lambda x, y: (0, 0, 0, 255))
        self.assertIn("blank", game_card.check_cover(self.png("blank.png", blank))["problem"])
        self.assertIn("not a PNG", game_card.check_cover(self.png("fake.png", b"GIF89a..."))["problem"])
        self.assertIn("does not exist", game_card.check_cover(self.base / "none.png")["problem"])

    def test_png_row_filters_are_decoded(self):
        # Paeth/Up/Sub-filtered rows, as image editors write them, decode to the same pixels.
        import struct
        import zlib
        width, height = 4, 3
        source = [[(x * 10, y * 20, 5, 255) for x in range(width)] for y in range(height)]
        rows = b""
        previous = bytes(width * 4)
        for y, filter_type in enumerate((1, 2, 4)):
            line = bytes(v for pixel in source[y] for v in pixel)
            out = bytearray()
            for i, value in enumerate(line):
                left = line[i - 4] if i >= 4 else 0
                up = previous[i]
                corner = previous[i - 4] if i >= 4 else 0
                predictor = {1: left, 2: up, 4: game_card._paeth(left, up, corner)}[filter_type]
                out.append((value - predictor) & 0xFF)
            rows += bytes([filter_type]) + bytes(out)
            previous = line

        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
        _w, _h, pixels = game_card.decode_png(data)
        self.assertEqual(pixels, [pixel for row in source for pixel in row])


class CardFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = make_project(self.base, card=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scaffold_writes_a_starter_card_once_and_it_is_not_complete(self):
        data = game_card.scaffold(self.root, "Space Game")
        self.assertEqual(data["title"], "Space Game")
        state = game_card.status(self.root)
        self.assertFalse(state["complete"])
        self.assertEqual(state["missing"], ["tagline", "description", "genres", "cover"])
        (self.root / "game.json").write_text(json.dumps({**data, "tagline": "kept", "future": {"x": 1}}))
        game_card.scaffold(self.root, "Other")
        self.assertEqual(game_card.load(self.root)["tagline"], "kept")

    def test_update_is_all_or_nothing_and_keeps_unknown_keys(self):
        game_card.scaffold(self.root, "Space Game")
        card = json.loads((self.root / "game.json").read_text())
        (self.root / "game.json").write_text(json.dumps({**card, "rating": "E"}))
        bad = game_card.update(self.root, {**GOOD, "description": "TODO", "genres": ["Dance"]})
        self.assertFalse(bad["ok"])
        self.assertEqual(len(bad["problems"]), 2)
        self.assertEqual(game_card.load(self.root)["tagline"], "", "nothing changed")
        cover = self.base / "drawn.png"
        cover.write_bytes(COVER)
        good = game_card.update(self.root, {**GOOD, "controls": {"A": "boost"}}, cover_source=str(cover),
                                build_sha="abc")
        self.assertTrue(good["ok"], good)
        self.assertTrue(good["status"]["complete"])
        stored = game_card.load(self.root)
        self.assertEqual((stored["rating"], stored["cover"], stored["coverForBuild"]), ("E", "cover.png", "abc"))
        self.assertEqual((self.root / "cover.png").read_bytes(), COVER)

    def test_placeholders_and_bad_lists_do_not_count(self):
        for problem in (game_card._text_problem("description", "Lorem ipsum " * 5),
                        game_card._text_problem("tagline", "Short"),
                        game_card._list_problem("genres", ["Arcade"] * 4),
                        game_card._list_problem("tags", ["x" * 30]),
                        game_card._controls_problem({"A": ""})):
            self.assertTrue(problem)

    def test_the_card_files_never_mark_a_built_game_changed(self):
        built = time.time() - 100
        for path in self.root.rglob("*"):
            os.utime(path, (built - 50, built - 50))
        game_card.scaffold(self.root, "Space Game")
        (self.root / "cover.png").write_bytes(COVER)
        self.assertFalse(games.sources_newer_than(self.root, built))
        (self.root / "project" / "scene.gbsres").write_text("{\"changed\": true}")
        self.assertTrue(games.sources_newer_than(self.root, built))


class ToolsAndPresent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.patches = [
            mock.patch.dict(os.environ, {"HERMRETRO_LIBRARY_DIR": str(self.base / "lib"),
                                         "HERMRETRO_RUNTIME_DIR": str(self.base / "run")}),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
            throwaway_profile(self.base),
        ]
        for patch in self.patches:
            patch.start()
        self.root = make_project(self.base, card=False)

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def info(self, args):
        return json.loads(hermes_host.game_info_handler({"project": str(self.root), **args},
                                                        conversation_id="conv", session_id="run-1"))

    def present(self):
        return json.loads(hermes_host.present_game_handler({"project": str(self.root)},
                                                           conversation_id="conv", session_id="run-1"))

    def test_present_refuses_until_the_card_is_finished_then_shows_the_game(self):
        refused = self.present()
        self.assertEqual(refused["code"], "GAME_INFO_INCOMPLETE")
        self.assertEqual(refused["missing"], ["tagline", "description", "genres", "cover"])
        self.assertIn("chromatic_game_info", refused["guidance"])
        self.assertTrue((self.root / "game.json").is_file(), "the starter card exists for the agent to fill")
        status = self.info({})
        self.assertFalse(status["complete"])
        self.assertIn("pixel-art cover", status["nextStep"])
        cover = self.base / "drawn.png"
        cover.write_bytes(COVER)
        filled = self.info({**GOOD, "cover": str(cover)})
        self.assertTrue(filled["complete"], filled)
        self.assertIn("chromatic_present_game", filled["nextStep"])
        shown = self.present()
        self.assertTrue(shown["ok"], shown)

    def test_a_cover_that_is_just_a_game_background_is_refused(self):
        (self.root / "assets" / "backgrounds").mkdir(parents=True)
        (self.root / "assets" / "backgrounds" / "field.png").write_bytes(COVER)
        answer = self.info({**GOOD, "cover": str(self.root / "assets" / "backgrounds" / "field.png")})
        self.assertEqual(answer["code"], "INVALID_GAME_INFO")
        self.assertIn("unchanged copy of assets/backgrounds/field.png", answer["error"])
        (self.root / "cover.png").write_bytes(COVER)       # copied by hand instead
        self.info(GOOD)
        refused = self.present()
        self.assertEqual((refused["code"], refused["missing"]), ("GAME_INFO_INCOMPLETE", ["cover"]))

    def test_an_invalid_field_changes_nothing_and_says_why(self):
        answer = self.info({"tagline": "x", "cover": str(self.root / "missing.png")})
        self.assertEqual(answer["code"], "INVALID_GAME_INFO")
        self.assertEqual(len(answer["problems"]), 2)

    def test_a_cover_edited_by_hand_into_something_else_is_caught_at_present(self):
        cover = self.base / "drawn.png"
        cover.write_bytes(COVER)
        self.assertTrue(self.info({**GOOD, "cover": str(cover)})["complete"])
        (self.root / "cover.png").write_bytes(encode_png(160, 144, lambda x, y: (x, y, 0, 255)))
        refused = self.present()
        self.assertEqual((refused["code"], refused["missing"]), ("GAME_INFO_INCOMPLETE", ["cover"]))
        self.assertIn("colours", refused["problems"][0])

    def test_creating_a_project_writes_its_starter_card(self):
        fresh = make_project(self.base, name="Fresh Game", card=False)
        games.Registry(self.base / "lib").observe("project_create", {}, {"projectRoot": str(fresh)}, False,
                                                  lane_root=None, conversation_id=None)
        self.assertEqual(game_card.load(fresh)["title"], "Fresh Game")

    def test_the_schema_lists_the_genres_and_needs_nothing(self):
        schema = hermes_host.GAME_INFO_TOOL
        self.assertEqual(schema["name"], "chromatic_game_info")
        self.assertNotIn("required", schema["parameters"])
        self.assertEqual(schema["parameters"]["properties"]["genres"]["items"]["enum"], list(game_card.GENRES))


if __name__ == "__main__":
    unittest.main()
