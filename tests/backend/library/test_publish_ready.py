"""What makes a game ready to publish (backend/library/layout.py, licence.py, publish_ready.py, publish_scan.py): the
folder's format, the built ROM's checksum and what built it, the licence and its LICENSE, readiness (an install of the
published files must pass), and the library's warning for two folders holding one game.

Run alone: python -m unittest tests.backend.library.test_publish_ready
"""

import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import (
    build_record,
    game_card,
    install_swap,
    installs,
    layout,
    licence,
    publish_ready,
    release,
    shelf,
)  # noqa: E402
from backend.library import tools as library_tools  # noqa: E402
from backend.library.freshness import source_digest  # noqa: E402
from backend.library.games import Registry  # noqa: E402
from backend.library.project import file_sha256  # noqa: E402
from backend.system import paths  # noqa: E402
from tests.backend.library.test_installs import Workers  # noqa: E402
from tests.support import commit_all, git, isolated_home, make_library_game, make_project, make_rom  # noqa: E402

PROFILE = "hermretro"
CLI = "out/cli/gb-studio-cli.js"


def codes(findings: list[dict]) -> list[str]:
    return [item["code"] for item in findings]


class Base(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.toolchain = self.home.base / "toolchain"
        self.vendor = self.toolchain / "vendor" / "gb-studio"
        (self.toolchain / "receipts").mkdir(parents=True)
        receipt = {
            "status": "ready",
            "version": "4.3.2",
            "destination": str(self.vendor),
            "provenance": {
                "sourceCommit": "c" * 40,
                "buildMetadataPatches": [{"path": build_record.SAVE_SIGNATURE_SOURCE, "purpose": "repeatable"}],
            },
        }
        (self.toolchain / "receipts" / "cli.json").write_text(json.dumps(receipt))
        (self.vendor / "out" / "cli").mkdir(parents=True)
        (self.vendor / CLI).write_text("cli")
        self.enterContext(mock.patch.object(paths, "setup_root", lambda: self.toolchain))
        self.root = make_project(self.home.base, "Ready Game")
        self.rom = self.root / "build" / "game.gbc"
        self.rom.write_bytes(make_rom())
        layout.ensure(self.root)

    def build(self, root=None) -> bool:
        """What the library records after a successful build of the game's ROM by the setup's CLI."""
        root = root or self.root
        rom = root / "build" / "game.gbc"
        return build_record.record_build(root, str(rom), file_sha256(rom), str(self.vendor / CLI))

    def last_build(self, root=None) -> dict:
        root = root or self.root
        return {"ok": True, "sha256": file_sha256(root / "build" / "game.gbc"), "sources": source_digest(root)}

    def ready(self, source=True, **fields) -> dict:
        game_card.set_fields(self.root, {"license": "MIT", **fields})
        layout.ensure(self.root)
        self.build()
        return publish_ready.readiness(self.root, source=source, last_build=self.last_build())


class Format(Base):
    def test_ensure_gives_a_game_its_format_and_never_lowers_a_newer_one(self):
        self.assertEqual(game_card.load(self.root)["format"], layout.FORMAT_VERSION)
        for wrong in ("one", True, 1.0, 0, None):
            game_card.set_fields(self.root, {"format": wrong})
            layout.ensure(self.root)
            stored = game_card.load(self.root)["format"]
            self.assertIs(type(stored), int, wrong)
            self.assertEqual(stored, layout.FORMAT_VERSION, wrong)
        game_card.set_fields(self.root, {"format": layout.FORMAT_VERSION + 1})
        layout.ensure(self.root)
        self.assertEqual(game_card.load(self.root)["format"], layout.FORMAT_VERSION + 1, "a newer one is kept")
        self.assertIn("FORMAT_NEWER", codes(layout.check(self.root)["problems"]))
        self.assertIn("FORMAT_NEWER", codes(publish_ready.readiness(self.root, source=False)["problems"]))


class BuildRecord(Base):
    def test_a_build_records_its_roms_checksum_and_its_compiler(self):
        self.assertTrue(self.build())
        card = game_card.load(self.root)
        self.assertEqual(card["romSha256"], file_sha256(self.rom))
        engine = json.loads((paths.ENGINE_ROOT / "package.json").read_text())["version"]
        built = {
            "engine": engine,
            "verified": True,
            "gbStudio": "4.3.2",
            "gbStudioCommit": "c" * 40,
            "repeatable": True,
        }
        self.assertEqual(card["builtWith"], built)
        self.assertFalse(self.build(), "the same ROM again writes nothing")

    def test_a_compiler_the_setup_did_not_install_names_no_version(self):
        other = self.home.base / "project-toolchain" / CLI
        other.parent.mkdir(parents=True)
        other.write_text("cli")
        build_record.record_build(self.root, str(self.rom), file_sha256(self.rom), str(other))
        built = game_card.load(self.root)["builtWith"]
        self.assertFalse(built["verified"])
        self.assertNotIn("gbStudio", built)
        build_record.record_build(self.root, str(self.rom), file_sha256(self.rom) + "", None)
        self.assertFalse(game_card.load(self.root)["builtWith"]["verified"], "no CLI named")

    def test_only_the_file_the_build_made_is_recorded(self):
        other = self.root / "build" / "other.gbc"
        other.write_bytes(make_rom(fill=4))
        self.assertFalse(
            build_record.record_build(self.root, str(other), file_sha256(other), None), "not the game's ROM"
        )
        self.assertFalse(build_record.record_build(self.root, str(self.rom), "0" * 64, None), "changed since the build")
        self.assertFalse(build_record.record_build(self.root, str(self.root / "missing.gbc"), "0" * 64, None))
        self.assertNotIn("romSha256", game_card.load(self.root))

    def test_a_game_without_its_card_is_stamped_on_its_first_build(self):
        registry = Registry(paths.library_dir())
        root = make_project(paths.games_dir(create=True), "Old Game", card=False)
        rom = root / "build" / "game.gbc"
        rom.write_bytes(make_rom(fill=9))
        (root / game_card.CARD_FILE).unlink(missing_ok=True)
        registry.observe("project_select", {}, {"projectRoot": str(root)}, False, lane_root=None, conversation_id="c")
        (root / game_card.CARD_FILE).unlink(missing_ok=True)  # made before every game had its card
        result = {"success": True, "outputPath": str(rom), "rom": {"sha256": file_sha256(rom)}}
        registry.observe("rom_build", {}, result, False, lane_root=str(root), conversation_id="c")
        self.assertEqual(game_card.load(root)["romSha256"], file_sha256(rom))


class InstalledEdits(Base):
    def record(self, version: int):
        rom = {"path": "build/game.gbc", "sha256": file_sha256(self.rom)}
        source = {"canonical": "https://github.com/a/b"}
        if version == 3:
            return release.record_install(self.root, source=source, commit="0" * 40, mode="game+source", rom=rom)
        record = {
            "source": source,
            "commit": "0" * 40,
            "mode": "game+source",
            "rom": rom,
            "fingerprint": release.installed_digest(self.root, mode="game+source", version=2),
            "installedAt": 1.0,
        }
        layout.write_state(self.root, layout.INSTALL_FILE, record)
        return record

    def test_what_hermretro_writes_into_an_installed_games_card_is_never_an_edit(self):
        self.record(3)
        self.build()
        game_card.set_fields(self.root, {"format": layout.FORMAT_VERSION})
        self.assertFalse(release.local_edits(self.root), "a build's romSha256 and builtWith, and the format")
        game_card.set_fields(self.root, {"license": "MIT"})
        layout.ensure(self.root)
        self.assertTrue(release.local_edits(self.root), "choosing a licence is the user's edit")

    def test_an_untouched_install_recorded_before_this_hermretro_stays_untouched(self):
        card = {key: value for key, value in game_card.load(self.root).items() if key not in layout.MANAGED_FIELDS}
        (self.root / game_card.CARD_FILE).write_text(game_card.card_text(card))
        self.record(2)
        layout.ensure(self.root)  # this hermretro adds the format
        self.build()
        self.assertIs(release.local_edits(self.root), False)
        self.assertEqual(release.installed(self.root)["fingerprintVersion"], release.FINGERPRINT_VERSION, "upgraded")
        self.assertIs(release.local_edits(self.root), False)

    def test_an_edited_install_recorded_before_this_hermretro_stays_edited(self):
        self.record(2)
        (self.root / "project" / "scene.gbsres").write_text('{"edited": true}')
        self.assertIs(release.local_edits(self.root), True)
        self.assertNotIn("fingerprintVersion", release.installed(self.root))


class Licence(Base):
    def test_the_card_takes_only_an_allowed_licence(self):
        for wrong in ("WTFPL", [], {"id": "MIT"}, 3):
            refused = game_card.update(self.root, {"license": wrong})
            self.assertFalse(refused["ok"], wrong)
            self.assertIn("license must be one of", refused["problems"][0])
        game_card.set_fields(self.root, {"license": ["MIT"]})  # a hand edit
        layout.ensure(self.root)
        self.assertIsNone(game_card.public(self.root)["license"])
        self.assertIn("NO_LICENSE", codes(publish_ready.readiness(self.root, source=True)["problems"]))
        self.assertTrue(game_card.update(self.root, {"license": "CC-BY-4.0"})["ok"])
        self.assertEqual(game_card.public(self.root)["license"], "CC-BY-4.0")

    def test_the_tool_refuses_a_licence_that_is_not_one(self):
        self.enterContext(mock.patch.object(host, "_profile_identity", lambda: PROFILE))
        self.enterContext(mock.patch.object(host, "try_connect", lambda _dir: (None, None)))
        game, root = make_library_game(self.home, "Tool Game")
        host._registry().bind(game, "chat", PROFILE)
        answer = json.loads(library_tools.game_info_handler({"license": []}, conversation_id="chat", session_id="chat"))
        self.assertEqual(answer["code"], "INVALID_GAME_INFO")
        answer = json.loads(
            library_tools.game_info_handler({"license": "MIT"}, conversation_id="chat", session_id="chat")
        )
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["card"]["license"], "MIT")
        self.assertTrue((root / "LICENSE").is_file())

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
        self.assertEqual(publish_ready.licence_problems(self.root, game_card.load(self.root)), [], "the user's own")

    def test_a_restored_licence_is_still_hermretros_and_readiness_sees_it_disagree(self):
        game_card.set_fields(self.root, {"license": "MIT"})
        layout.ensure(self.root)
        mit = (self.root / "LICENSE").read_text()
        game_card.set_fields(self.root, {"license": "CC0-1.0"})
        layout.ensure(self.root)
        (self.root / "LICENSE").write_text(mit)  # a history restore brings back the older LICENSE, not the card
        self.assertEqual(codes(publish_ready.licence_problems(self.root, game_card.load(self.root))), ["LICENSE_STALE"])
        layout.ensure(self.root)
        self.assertIn("CC0", (self.root / "LICENSE").read_text(), "it is hermretro's, so it is written again")
        (self.root / "LICENSE").unlink()
        self.assertEqual(
            codes(publish_ready.licence_problems(self.root, game_card.load(self.root))), ["NO_LICENSE_TEXT"]
        )

    def test_every_licence_has_its_text_and_a_year_whatever_the_card_says(self):
        for key in licence.LICENSES:
            written = licence.text(self.root, {"license": key, "title": "Space"})
            self.assertIn("Space" if key != "MIT" else "Copyright (c)", written, key)
        this_year = str(time.gmtime().tm_year)
        for created in (10**20, float("nan"), "yesterday", True, None):
            self.assertIn(this_year, licence.text(self.root, {"license": "MIT", "createdAt": created}), created)

    def test_an_update_never_carries_the_licence_record(self):
        old, new = self.home.base / "old", self.home.base / "new"
        (old / layout.STATE_DIR).mkdir(parents=True)
        (old / layout.STATE_DIR / layout.LICENCE_FILE).write_text('{"sha256": ["x"]}')
        new.mkdir()
        install_swap.carry(old, new, [], [])
        self.assertFalse((new / layout.STATE_DIR / layout.LICENCE_FILE).exists())


class Readiness(Base):
    def test_a_ready_game_needs_a_licence_and_its_own_fitting_current_rom(self):
        self.assertEqual(self.ready(), {"ok": True, "problems": [], "warnings": []})
        game_card.set_fields(self.root, {"license": None})
        self.assertIn("NO_LICENSE", codes(publish_ready.readiness(self.root, source=True)["problems"]))
        self.ready()
        self.rom.write_bytes(make_rom(fill=7))
        problems = codes(publish_ready.readiness(self.root, source=True, last_build=self.last_build())["problems"])
        self.assertIn("ROM_SHA_STALE", problems)
        self.rom.write_bytes(make_rom(kind=0xFF))
        self.build()
        problems = publish_ready.readiness(self.root, source=True, last_build=self.last_build())["problems"]
        self.assertEqual(codes(problems), ["ROM_UNFIT"])
        self.rom.write_bytes(make_rom(colour=False))
        self.build()
        problems = publish_ready.readiness(self.root, source=True, last_build=self.last_build())["problems"]
        self.assertEqual(codes(problems), ["ROM_UNFIT"], ".gbc says colour")

    def test_the_rom_is_judged_by_what_it_was_built_from_not_file_times(self):
        self.ready()
        self.assertIn("ROM_OLD", codes(publish_ready.readiness(self.root, source=True)["problems"]), "no build record")
        built = self.last_build()
        scene = self.root / "project" / "scene.gbsres"
        scene.write_text('{"changed": true}')
        os.utime(scene, (1, 1))  # older than the ROM, yet changed after its build
        self.assertIn("ROM_OLD", codes(publish_ready.readiness(self.root, source=True, last_build=built)["problems"]))

    def test_a_blocking_scan_finding_and_a_warning_reach_readiness(self):
        (self.root / "project" / "scene.gbsres").write_text(json.dumps({"path": "/home/u/games/space"}))
        (self.root / "plugins" / "fx").mkdir(parents=True)
        (self.root / "plugins" / "fx" / "engine.c").write_text("int x;")
        result = self.ready()
        self.assertFalse(result["ok"])
        self.assertEqual(codes(result["problems"]), ["HOME_PATH"])
        self.assertEqual(codes(result["warnings"]), ["PLUGIN_CODE"])
        self.assertTrue(self.ready(source=False)["ok"], "the game alone does not carry it")

    def test_a_linked_cover_is_what_an_install_would_refuse(self):
        self.ready()
        real = self.home.base / "cover.png"
        (self.root / "cover.png").rename(real)
        (self.root / "cover.png").symlink_to(real)
        problems = codes(publish_ready.readiness(self.root, source=False, last_build=self.last_build())["problems"])
        self.assertIn("INSTALL_NO_COVER", problems)

    def test_a_ready_game_installs_from_its_published_files_both_ways(self):
        self.assertTrue(self.ready()["ok"])
        for source in (False, True):
            self.assertTrue(self.ready(source=source)["ok"], source)
            repo = self.home.base / f"repo-{source}"
            repo.mkdir()
            git(repo, "init", "-q")
            for name in release.files(self.root, source=source):
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_bytes((self.root / name).read_bytes())
            commit_all(repo, "Publish")
            registry = Registry(paths.library_dir())
            found = installs.inspect(repo.resolve().as_uri(), registry=registry, allow_local=True)
            self.assertTrue(found["ok"], found["problems"])
            # One id is one game here: install each into a library of its own.
            games = self.home.base / f"games-{source}"
            games.mkdir()
            fresh = Registry(self.home.base / f"library-{source}")
            result = installs.install(
                found["source"],
                found["commit"],
                workers=Workers(),
                registry=fresh,
                games_dir=games,
                allow_local=True,
            )
            self.assertEqual(release.installed(Path(result["root"]))["mode"], "game+source" if source else "game")


class OneIdOneGame(Base):
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

    def test_one_folder_reached_two_ways_is_one_game(self):
        alias = self.home.base / "alias"
        alias.symlink_to(self.root)
        games = [{"projectRoot": str(self.root)}, {"projectRoot": str(alias)}]
        shelf.mark_duplicates(games)
        self.assertEqual([game["duplicateId"] for game in games], [None, None])


if __name__ == "__main__":
    unittest.main()
