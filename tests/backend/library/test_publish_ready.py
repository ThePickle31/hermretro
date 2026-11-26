"""What makes a game ready to publish (backend/library/layout.py, licence.py, release.py, publish_scan.py): the folder's
format, the built ROM's checksum and what built it, the licence and its LICENSE, the readiness codes, the pre-publish
scan, and the library's warning for two folders holding one game.

Run alone: python -m unittest tests.backend.library.test_publish_ready
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import game_card, layout, licence, publish_scan, release  # noqa: E402
from backend.library.project import file_sha256  # noqa: E402
from backend.system import paths  # noqa: E402
from tests.support import isolated_home, make_library_game, make_project, make_rom  # noqa: E402

# A fake token of each shape the scan knows, assembled so this file holds none whole.
GITHUB_TOKEN = "gh" + "p_" + "a1B2c3D4" * 5
AWS_KEY = "AK" + "IA" + "ABCDEFGHIJ234567"
KEY_BLOCK = "-----BEGIN RSA PRIVATE" + " KEY-----"


def codes(findings: list[dict]) -> list[str]:
    return [item["code"] for item in findings]


class Ready(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        toolchain = self.home.base / "toolchain"
        (toolchain / "receipts").mkdir(parents=True)
        receipt = {
            "status": "ready",
            "version": "4.3.2",
            "provenance": {
                "sourceCommit": "c" * 40,
                "buildMetadataPatches": [{"path": layout.SAVE_SIGNATURE_SOURCE, "purpose": "repeatable"}],
            },
        }
        (toolchain / "receipts" / "cli.json").write_text(json.dumps(receipt))
        self.enterContext(mock.patch.object(paths, "setup_root", lambda: toolchain))
        self.root = make_project(self.home.base, "Ready Game")
        (self.root / "build" / "game.gbc").write_bytes(make_rom())
        layout.ensure(self.root)

    def ready(self, **fields) -> dict:
        game_card.set_fields(self.root, {"license": "MIT", **fields})
        layout.ensure(self.root)
        layout.record_build(self.root)
        return release.readiness(self.root, source=True)

    # -- format ---------------------------------------------------------------------------

    def test_ensure_gives_an_older_game_its_format_and_never_lowers_a_newer_one(self):
        self.assertEqual(game_card.load(self.root)["format"], layout.FORMAT_VERSION)
        game_card.set_fields(self.root, {"format": "one"})
        layout.ensure(self.root)
        self.assertEqual(game_card.load(self.root)["format"], layout.FORMAT_VERSION, "a bad value is replaced")
        game_card.set_fields(self.root, {"format": layout.FORMAT_VERSION + 1})
        layout.ensure(self.root)
        self.assertEqual(game_card.load(self.root)["format"], layout.FORMAT_VERSION + 1, "a newer one is kept")
        self.assertIn("FORMAT_NEWER", codes(layout.check(self.root)["problems"]))
        self.assertIn("FORMAT_NEWER", codes(release.readiness(self.root, source=False)["problems"]))

    # -- what a build records ---------------------------------------------------------------

    def test_a_build_records_its_roms_checksum_and_what_built_it(self):
        self.assertTrue(layout.record_build(self.root))
        card = game_card.load(self.root)
        self.assertEqual(card["romSha256"], file_sha256(self.root / "build" / "game.gbc"))
        engine = json.loads((paths.ENGINE_ROOT / "package.json").read_text())["version"]
        self.assertEqual(
            card["builtWith"], {"engine": engine, "gbStudio": "4.3.2", "gbStudioCommit": "c" * 40, "repeatable": True}
        )
        self.assertFalse(layout.record_build(self.root), "the same ROM again writes nothing")

    def test_the_library_records_a_successful_build_of_the_game(self):
        _, root = make_library_game(self.home, "Built Game")
        (root / "build" / "game.gbc").write_bytes(make_rom(fill=3))
        rom = root / "build" / "game.gbc"
        registry = host._registry()
        registry.observe("rom_build", {}, {"success": False}, True, lane_root=str(root), conversation_id="c")
        self.assertNotIn("romSha256", game_card.load(root), "a failed build records nothing")
        registry.observe(
            "rom_build", {}, {"success": True, "outputPath": str(rom)}, False, lane_root=str(root), conversation_id="c"
        )
        self.assertEqual(game_card.load(root)["romSha256"], file_sha256(rom))

    def test_what_hermretro_writes_into_an_installed_games_card_is_never_an_edit(self):
        layout.write_state(self.root, layout.INSTALL_FILE, {})
        release.record_install(
            self.root,
            source={"canonical": "https://github.com/a/b"},
            commit="0" * 40,
            mode="game+source",
            rom={"path": "build/game.gbc", "sha256": file_sha256(self.root / "build" / "game.gbc")},
        )
        layout.record_build(self.root)
        game_card.set_fields(self.root, {"format": layout.FORMAT_VERSION})
        self.assertFalse(release.local_edits(self.root), "a build's romSha256 and builtWith, and the format")
        game_card.set_fields(self.root, {"license": "MIT"})
        layout.ensure(self.root)
        self.assertTrue(release.local_edits(self.root), "choosing a licence is the user's edit")

    # -- the licence ------------------------------------------------------------------------

    def test_the_card_takes_only_an_allowed_licence(self):
        refused = game_card.update(self.root, {"license": "WTFPL"})
        self.assertFalse(refused["ok"])
        self.assertIn("license must be one of", refused["problems"][0])
        self.assertTrue(game_card.update(self.root, {"license": "CC-BY-4.0"})["ok"])
        self.assertEqual(game_card.public(self.root)["license"], "CC-BY-4.0")

    def test_ensure_writes_the_licences_file_and_keeps_one_the_user_wrote(self):
        self.assertFalse((self.root / "LICENSE").exists(), "no licence is chosen for the user")
        game_card.set_fields(self.root, {"license": "MIT", "author": "Ada", "createdAt": 1767225600})
        layout.ensure(self.root)
        text = (self.root / "LICENSE").read_text()
        self.assertTrue(text.startswith("MIT License\n\nCopyright (c) 2026 Ada\n"))
        game_card.set_fields(self.root, {"license": "CC-BY-SA-4.0"})
        layout.ensure(self.root)
        self.assertIn("creativecommons.org/licenses/by-sa/4.0/", (self.root / "LICENSE").read_text())
        (self.root / "LICENSE").write_text("My own terms\n")
        game_card.set_fields(self.root, {"license": "MIT"})
        layout.ensure(self.root)
        self.assertEqual((self.root / "LICENSE").read_text(), "My own terms\n")

    def test_every_licence_has_its_text(self):
        for key in licence.LICENSES:
            written = licence.text(self.root, {"license": key, "title": "Space"})
            self.assertIn("Space" if key != "MIT" else "Copyright (c)", written, key)

    # -- readiness ----------------------------------------------------------------------------

    def test_a_ready_game_needs_a_licence_and_its_own_fitting_rom(self):
        self.assertEqual(self.ready(), {"ok": True, "problems": [], "warnings": []})
        game_card.set_fields(self.root, {"license": None})
        self.assertIn("NO_LICENSE", codes(release.readiness(self.root, source=True)["problems"]))
        self.ready()
        (self.root / "build" / "game.gbc").write_bytes(make_rom(fill=7))
        self.assertIn("ROM_SHA_STALE", codes(release.readiness(self.root, source=True)["problems"]))
        (self.root / "build" / "game.gbc").write_bytes(make_rom(kind=0xFF))
        layout.record_build(self.root)
        self.assertEqual(codes(release.readiness(self.root, source=True)["problems"]), ["ROM_UNFIT"])
        (self.root / "build" / "game.gbc").write_bytes(make_rom(colour=False))
        layout.record_build(self.root)
        self.assertEqual(
            codes(release.readiness(self.root, source=True)["problems"]), ["ROM_UNFIT"], ".gbc says colour"
        )

    def test_a_blocking_scan_finding_stops_the_publish(self):
        (self.root / "project" / "scene.gbsres").write_text(json.dumps({"path": "/home/u/games/space"}))
        result = self.ready()
        self.assertFalse(result["ok"])
        self.assertEqual(codes(result["problems"]), ["HOME_PATH"])
        self.assertTrue(release.readiness(self.root, source=False)["ok"], "the game alone does not carry it")

    # -- the scan ------------------------------------------------------------------------------

    def scanned(self, name: str, text: str) -> list[str]:
        path = self.root / "project" / name
        path.write_text(text)
        return codes(publish_scan.scan(self.root, [f"project/{name}"])["blocking"])

    def test_the_scan_finds_secrets_and_home_folders(self):
        self.assertEqual(self.scanned("a.gbsres", f'{{"note": "{GITHUB_TOKEN}"}}'), ["SECRET"])
        self.assertEqual(self.scanned("b.gbsres", f"aws = {AWS_KEY}"), ["SECRET"])
        self.assertEqual(self.scanned("c.txt", KEY_BLOCK), ["SECRET"])
        self.assertEqual(self.scanned("d.json", '{"apiKey": "Zq81xL0pW4mNc7Vb2Rt9"}'), ["SECRET"])
        self.assertEqual(self.scanned("e.gbsres", '{"token": "sceneTransitionFade"}'), [], "a word is not a secret")
        self.assertEqual(self.scanned("f.gbsres", '{"id": "9b7e6c2a-4f1d-4e8a-b3c5-1d2e3f4a5b6c"}'), [])
        self.assertEqual(self.scanned("g.gbsres", r'{"p": "C:\\Users\\ada\\x.png"}'), ["HOME_PATH"])
        self.assertEqual(self.scanned("h.gbsres", '{"p": "/Users/you/x.png"}'), [], "a placeholder names no one")

    def test_the_scan_refuses_what_an_install_would_and_lists_plugin_code(self):
        big = self.root / "assets" / "music.uge"
        big.parent.mkdir()
        with big.open("wb") as stream:
            stream.truncate(21 * 1024 * 1024)
        (self.root / "plugins" / "fx" / "events").mkdir(parents=True)
        (self.root / "plugins" / "fx" / "events" / "eventShake.js").write_text("module.exports = {};")
        found = release.scan(self.root, source=True)
        self.assertEqual(codes(found["blocking"]), ["FILE_TOO_LARGE"])
        self.assertEqual(found["warnings"][0]["code"], "PLUGIN_CODE")
        self.assertEqual(found["warnings"][0]["files"], ["plugins/fx/events/eventShake.js"])
        with mock.patch.object(publish_scan.install_check, "MAX_TOTAL_BYTES", 1024):
            self.assertIn("TOO_LARGE", codes(release.scan(self.root, source=False)["blocking"]))

    # -- one id, one game ------------------------------------------------------------------------

    def test_the_library_names_folders_that_hold_one_game(self):
        _, first = make_library_game(self.home, "First Game")
        _, second = make_library_game(self.home, "Second Game")
        _, third = make_library_game(self.home, "Third Game")
        layout.ensure(first)
        layout.write_state(second, layout.IDENTITY_FILE, layout.state(first, layout.IDENTITY_FILE))
        listed = {game["projectRoot"]: game for game in host._registry().library()}
        self.assertEqual(listed[str(first)]["duplicateId"], [str(second)])
        self.assertEqual(listed[str(second)]["duplicateId"], [str(first)])
        self.assertIsNone(listed[str(third)]["duplicateId"])


if __name__ == "__main__":
    unittest.main()
