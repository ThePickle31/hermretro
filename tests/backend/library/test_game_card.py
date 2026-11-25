"""The game card (game.json + cover.png), chromatic_game_info, and presenting only a finished card."""

import json
import os
import struct
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import game_card  # noqa: E402 - the repository root goes on sys.path first
from backend.library import game_cover  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, throwaway_profile  # noqa: E402 - the repository root goes on sys.path first
from tests.support import COVER, encode_png, make_project  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first

GOOD = {
    "title": "Space Game",
    "tagline": "Fly a tiny ship through a meteor field.",
    "description": "Dodge meteors, grab fuel cells and reach the space station before your tank runs dry.",
    "genres": ["Arcade", "Action"],
}


def with_rows(rows: bytes, level: int = 6) -> bytes:
    """COVER with these raw scanlines in its one IDAT chunk, compressed at ``level``."""
    body = zlib.compress(rows, level)
    idat = struct.pack(">I", len(body)) + b"IDAT" + body + struct.pack(">I", zlib.crc32(b"IDAT" + body))
    return COVER[:33] + idat + COVER[-12:]


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

    def test_display_status_and_url_share_validation_and_check_replacements(self):
        cover = self.png("cover.png", COVER)
        with mock.patch.object(game_cover, "decode_png", wraps=game_cover.decode_png) as decode:
            for _ in range(3):
                self.assertTrue(game_card.status(self.base, GOOD)["complete"])
                self.assertIsNotNone(game_card.cover_data_url(self.base))
            self.assertEqual(decode.call_count, 1)
            info = cover.stat()
            replacement = self.png("replacement", b"x" * info.st_size)
            os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
            replacement.replace(cover)
            self.assertFalse(game_card.status(self.base, GOOD)["complete"])
            self.assertIsNone(game_card.cover_data_url(self.base))
            self.assertEqual(decode.call_count, 2)

    def test_strict_status_checks_for_new_asset_copies_after_warming_the_display_cache(self):
        self.png("cover.png", COVER)
        self.assertTrue(game_card.status(self.base, GOOD)["complete"])
        self.assertTrue(game_card.status(self.base, GOOD, strict=True)["complete"])
        (self.base / "assets").mkdir()
        self.png("assets/copied.png", COVER)
        self.assertTrue(game_card.status(self.base, GOOD)["complete"])
        strict = game_card.status(self.base, GOOD, strict=True)
        self.assertFalse(strict["complete"])
        self.assertIn("unchanged copy of assets/copied.png", strict["problems"][0])

    def test_a_cover_with_an_assets_pixels_saved_again_is_a_copy_and_an_edited_one_is_not(self):
        self.png("cover.png", COVER)
        (self.base / "assets" / "backgrounds").mkdir(parents=True)
        rows = zlib.decompress(COVER[41:-16])  # COVER's one IDAT chunk
        title = self.png("assets/backgrounds/title.png", with_rows(rows, level=0))  # other bytes, same pixels
        self.assertNotEqual(title.read_bytes(), COVER)
        self.png("assets/backgrounds/small.png", encode_png(8, 8, lambda x, y: (0, 0, 0, 255)))
        self.png("assets/backgrounds/broken.png", COVER[:30])
        strict = game_card.status(self.base, GOOD, strict=True)
        self.assertIn("unchanged copy of assets/backgrounds/title.png", strict["problems"][0])
        edited = self.png("edited.png", with_rows(rows[:1] + bytes((250, 250, 240, 255)) + rows[5:]))
        self.assertTrue(game_card.update(self.base, {}, cover_source=str(edited))["ok"])

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

        def paeth(a, b, c):
            # The PNG spec's predictor, written out here: a change to the decoder's copy must not move
            # the bytes this test encodes, or a symmetric bug would compare the code with itself.
            p = a + b - c
            distances = (abs(p - a), abs(p - b), abs(p - c))
            return (a, b, c)[distances.index(min(distances))]

        width, height = 4, 3
        # Varied channels: a Paeth row over a flat picture picks the same byte under almost any
        # predictor, which would hide a change to the decoder's rule.
        source = [
            [((x * 37 + y * 91) % 256, (x * 53 + y * 17) % 256, (x * 11 + y * 71) % 256, 255) for x in range(width)]
            for y in range(height)
        ]
        # The Paeth row (y=2) must contain a byte where the three neighbours disagree and the spec picks the
        # upper-left: its red at x=1 has left 0, up 14 and upper-left 8. A decoder choosing only between left
        # and up decodes a different pixel here, which the comparison below sees.
        source[1][0] = (8, 60, 120, 255)
        source[1][1] = (14, 61, 121, 255)
        source[2][0] = (0, 62, 122, 255)
        left, up, corner = source[2][0][0], source[1][1][0], source[1][0][0]
        self.assertEqual((left, up, corner), (0, 14, 8))
        self.assertEqual(paeth(left, up, corner), 8, "the upper-left byte is the Paeth predictor here")
        rows = b""
        previous = bytes(width * 4)
        for y, filter_type in enumerate((1, 2, 4)):
            line = bytes(v for pixel in source[y] for v in pixel)
            out = bytearray()
            for i, value in enumerate(line):
                left = line[i - 4] if i >= 4 else 0
                up = previous[i]
                corner = previous[i - 4] if i >= 4 else 0
                predictor = {1: left, 2: up, 4: paeth(left, up, corner)}[filter_type]
                out.append((value - predictor) & 0xFF)
            rows += bytes([filter_type]) + bytes(out)
            previous = line

        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

        data = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b"")
        )
        _w, _h, pixels = game_cover.decode_png(data)
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
        good = game_card.update(
            self.root, {**GOOD, "controls": {"A": "boost"}}, cover_source=str(cover), build_sha="abc"
        )
        self.assertTrue(good["ok"], good)
        self.assertTrue(good["status"]["complete"])
        self.assertFalse(good["was_complete"], "the card became complete with this update")
        again = game_card.update(self.root, {"tags": ["space"]})
        self.assertTrue(again["was_complete"] and again["status"]["complete"], "already complete: no transition")
        stored = game_card.load(self.root)
        self.assertEqual((stored["rating"], stored["cover"], stored["coverForBuild"]), ("E", "cover.png", "abc"))
        self.assertEqual((self.root / "cover.png").read_bytes(), COVER)

    def test_a_damaged_cover_is_a_problem_and_a_new_cover_replaces_it(self):
        game_card.scaffold(self.root, "Space Game")
        damaged = COVER[:16] + b"\x00\x00\x00\x0dIHDR\x00\x00"  # IHDR says 13 bytes, holds 2
        (self.root / "cover.png").write_bytes(damaged)
        state = game_card.status(self.root, strict=True)
        self.assertIn("cover", state["missing"])
        self.assertIn("damaged", state["problems"][-1])
        cover = self.base / "drawn.png"
        cover.write_bytes(COVER)
        result = game_card.update(self.root, GOOD, cover_source=str(cover))
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["was_complete"])
        self.assertTrue(result["status"]["complete"], result)
        self.assertEqual((self.root / "cover.png").read_bytes(), COVER)

    def test_cover_problem_names_only_what_is_wrong_with_the_cover_by_the_present_rules(self):
        self.assertIn("no cover.png", game_card.cover_problem(self.root))
        (self.root / "cover.png").write_bytes(COVER)
        self.assertIsNone(game_card.cover_problem(self.root))
        (self.root / "assets" / "backgrounds").mkdir(parents=True)
        (self.root / "assets" / "backgrounds" / "field.png").write_bytes(COVER)
        problem = game_card.cover_problem(self.root)
        self.assertIn("unchanged copy of assets/backgrounds/field.png", problem)
        self.assertIsNone(game_card.cover_problem(self.root, strict=False))
        self.assertEqual(game_card.status(self.root, strict=True)["problems"], [problem])
        (self.root / "cover.png").write_bytes(encode_png(80, 72, lambda x, y: (x, y, 0, 255)))
        self.assertIn("must be exactly 160x144", game_card.cover_problem(self.root, strict=False))

    def test_placeholders_and_bad_lists_do_not_count(self):
        # Each row is refused through the public update, with the text the agent is told.
        rows = (
            ({"description": "Lorem ipsum " * 5}, "description still has placeholder text; write the real thing."),
            ({"tagline": "Short"}, "tagline is too short (at least 8 characters)."),
            ({"genres": ["Arcade"] * 4}, "At most 3 genres."),
            ({"tags": ["x" * 30]}, "Each tag is 1 to 24 characters."),
            (
                {"controls": {"A": ""}},
                "Each control is a button name (up to 20 characters) and what it does (up to 60 characters).",
            ),
        )
        for fields, problem in rows:
            with self.subTest(fields=fields):
                result = game_card.update(self.root, fields)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["problems"], [problem])

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
        isolated_home(self)  # it calls a real emitter, which reaches every feature's listeners.py
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.patches = [
            mock.patch.dict(
                os.environ,
                {"HERMRETRO_LIBRARY_DIR": str(self.base / "lib"), "HERMRETRO_RUNTIME_DIR": str(self.base / "run")},
            ),
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
        return json.loads(
            library_tools.game_info_handler(
                {"project": str(self.root), **args}, conversation_id="conv", session_id="run-1"
            )
        )

    def present(self):
        return json.loads(
            library_tools.present_game_handler({"project": str(self.root)}, conversation_id="conv", session_id="run-1")
        )

    def test_present_refuses_until_the_card_is_finished_then_shows_the_game(self):
        refused = self.present()
        self.assertEqual(refused["code"], "GAME_INFO_INCOMPLETE")
        self.assertEqual(refused["missing"], ["tagline", "description", "genres", "cover"])
        self.assertIn("chromatic_game_info", refused["nextStep"])
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
        old = time.time() - 900  # part of the game before its build, so the build stays current
        os.utime(self.root / "assets" / "backgrounds" / "field.png", (old, old))
        answer = self.info({**GOOD, "cover": str(self.root / "assets" / "backgrounds" / "field.png")})
        self.assertEqual(answer["code"], "INVALID_GAME_INFO")
        self.assertIn("unchanged copy of assets/backgrounds/field.png", answer["error"])
        (self.root / "cover.png").write_bytes(COVER)  # copied by hand instead
        self.info(GOOD)
        refused = self.present()
        self.assertEqual((refused["code"], refused["missing"]), ("GAME_INFO_INCOMPLETE", ["cover"]))

    def test_an_invalid_field_changes_nothing_and_says_why(self):
        self.info({})  # writes the starter card, so the next call has bytes to leave alone
        before = (self.root / "game.json").read_bytes()
        answer = self.info({"tagline": "x", "cover": str(self.root / "missing.png")})
        self.assertEqual(answer["code"], "INVALID_GAME_INFO")
        self.assertEqual(len(answer["problems"]), 2)
        self.assertEqual((self.root / "game.json").read_bytes(), before, "a refused update must write nothing")
        self.assertEqual(game_card.load(self.root)["tagline"], "")

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
        games.Registry(self.base / "lib").observe(
            "project_create", {}, {"projectRoot": str(fresh)}, False, lane_root=None, conversation_id=None
        )
        self.assertEqual(game_card.load(fresh)["title"], "Fresh Game")


if __name__ == "__main__":
    unittest.main()
