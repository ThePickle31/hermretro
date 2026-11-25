"""Installing a game from a link and updating it (backend/library/installs.py), against real git repositories in a
temporary folder (``file://`` links; nothing reaches the network).

Run alone: python -m unittest tests.backend.library.test_installs
"""

import hashlib
import json
import os
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import installs, layout, release  # noqa: E402 - the repository root goes on sys.path first
from backend.library.games import Registry  # noqa: E402
from backend.library.installs import InstallError  # noqa: E402
from backend.system import paths  # noqa: E402
from tests.support import (  # noqa: E402 - the repository root goes on sys.path first
    commit_all,
    git,
    isolated_home,
    make_game_folder,
    make_game_repo,
    make_rom,
)


class Installs(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.registry = Registry(paths.library_dir())
        self.games = paths.games_dir(create=True)
        self.repos = self.home.base / "repos"

    def install(self, link, commit=None, **options):
        commit = commit or installs.inspect(link, registry=self.registry)["commit"]
        return installs.install(link, commit, registry=self.registry, games_dir=self.games, **options)

    def card(self, root):
        return json.loads((Path(root) / "game.json").read_text())

    def refused(self, code, step):
        with self.assertRaises(InstallError) as caught:
            step()
        self.assertEqual(caught.exception.code, code, caught.exception.details)
        return caught.exception

    def problems(self, step):
        return [problem["code"] for problem in self.refused("NOT_INSTALLABLE", step).details["problems"]]

    # -- installing -------------------------------------------------------------------------

    def test_inspect_reads_the_game_without_installing_it(self):
        repo, link = make_game_repo(self.repos, source=True)
        found = installs.inspect(link, registry=self.registry)
        self.assertTrue(found["ok"], found["problems"])
        self.assertEqual((found["title"], found["mode"], found["id"]), ("Space Game", "game+source", "ab" * 16))
        self.assertEqual(found["commit"], git(repo, "rev-parse", "HEAD"))
        self.assertTrue(found["cover"].startswith("data:image/png;base64,"))
        self.assertEqual(found["rom"]["sizeBytes"], 32 * 1024)
        self.assertEqual(found["alreadyInstalled"], [])
        self.assertEqual(os.listdir(self.games), [])

    def test_a_game_alone_installs_and_is_recorded(self):
        repo, link = make_game_repo(self.repos)
        result = self.install(link)
        root = Path(result["root"])
        self.assertEqual((result["mode"], result["changed"], result["testBuildDue"]), ("game", True, False))
        self.assertEqual(root, self.games / "Space Game")
        self.assertFalse((root / ".git").exists())
        self.assertEqual(layout.game_identity(root), "ab" * 16)
        record = release.installed(root)
        self.assertEqual(record["commit"], git(repo, "rev-parse", "HEAD"))
        self.assertEqual(record["source"]["canonical"], link)
        self.assertIs(release.local_edits(root), False)
        listed = self.registry.library()
        self.assertEqual([game["install"]["mode"] for game in listed], ["game"])
        self.assertEqual([name for name in os.listdir(self.games) if name.startswith(".install-")], [])

    def test_a_record_folder_that_came_with_the_game_is_dropped(self):
        repo, link = make_game_repo(self.repos)
        (repo / ".hermretro").mkdir()
        (repo / ".hermretro" / "identity.json").write_text(json.dumps({"id": "ff" * 16}))
        (repo / ".hermretro" / "install.json").write_text(json.dumps({"commit": "forged"}))
        commit_all(repo, "forged records")
        root = Path(self.install(link)["root"])
        self.assertEqual(layout.game_identity(root), "ab" * 16)
        self.assertEqual(release.installed(root)["commit"], git(repo, "rev-parse", "HEAD"))

    def test_a_game_with_its_source_installs_and_wants_a_test_build(self):
        _, link = make_game_repo(self.repos, source=True)
        result = self.install(link)
        self.assertEqual((result["mode"], result["testBuildDue"]), ("game+source", True))
        root = Path(result["root"])
        self.assertTrue(layout.check(root)["ok"], layout.check(root))
        self.assertIs(release.local_edits(root), False)

    def test_a_game_from_a_subfolder(self):
        repo = self.repos / "collection"
        (repo / "games").mkdir(parents=True)
        git(repo, "init", "-q")
        make_game_folder(repo / "games" / "space")
        (repo / "README.md").write_text("Many games")
        commit_all(repo, "games")
        result = self.install(repo.resolve().as_uri() + "#games/space")
        self.assertTrue((Path(result["root"]) / "build" / "game.gbc").is_file())
        self.assertFalse((Path(result["root"]) / "games").exists())
        self.refused("BAD_FOLDER", lambda: installs.inspect(repo.resolve().as_uri() + "#games/none"))

    def test_the_commit_installed_is_the_one_read(self):
        repo, link = make_game_repo(self.repos)
        read = installs.inspect(link, registry=self.registry)["commit"]
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.2.0\n")
        moved = commit_all(repo, "Second")
        error = self.refused("SOURCE_MOVED", lambda: self.install(link, read))
        self.assertEqual(error.details["commit"], moved)
        self.assertEqual([name for name in os.listdir(self.games) if not name.startswith(".install.lock")], [])
        self.refused("BAD_COMMIT", lambda: self.install(link, "abc"))

    def test_a_bad_rom_is_refused(self):
        cases = {
            "ROM_CHECKSUM": lambda rom: rom.write_bytes(make_rom()[:-1] + b"\x42"),
            "ROM_CARTRIDGE": lambda rom: rom.write_bytes(make_rom(kind=0x22)),
            "ROM_SIZE": lambda rom: rom.write_bytes(make_rom(48 * 1024)),
            "ROM_COLOUR": lambda rom: rom.write_bytes(make_rom(colour=False)),
            "NO_ROM": lambda rom: rom.unlink(),
        }
        for index, (code, damage) in enumerate(cases.items()):
            with self.subTest(code):
                repo, link = make_game_repo(self.repos, name=f"bad-{index}")
                damage(repo / "build" / "game.gbc")
                commit_all(repo, "damage")
                self.assertIn(code, self.problems(lambda link=link: self.install(link)))

    def test_what_would_reach_outside_or_is_too_big_is_refused(self):
        repo, link = make_game_repo(self.repos, name="links")
        (repo / "docs").mkdir()
        (repo / "docs" / "secrets").symlink_to("/etc/passwd")
        commit_all(repo, "link")
        self.assertIn("LINK", self.problems(lambda: self.install(link)))
        repo, link = make_game_repo(self.repos, name="big")
        (repo / "art").mkdir()
        (repo / "art" / "huge.bin").write_bytes(b"\0" * (21 * 1024 * 1024))
        commit_all(repo, "big")
        self.assertIn("TOO_BIG", self.problems(lambda: self.install(link)))

    def test_a_card_that_is_not_a_hermretro_game_or_is_newer_is_refused(self):
        variants = {
            "NEWER_FORMAT": {"format": layout.FORMAT_VERSION + 1},
            "NO_ID": {"id": "not-an-id"},
            "ROM_CHANGED": {"romSha256": "0" * 64},
            "NO_ROM": {"rom": "game.gbc"},
        }
        for index, (code, change) in enumerate(variants.items()):
            with self.subTest(code):
                repo, link = make_game_repo(self.repos, name=f"card-{index}")
                card = {**self.card(repo), **change}
                (repo / "game.json").write_text(json.dumps(card))
                commit_all(repo, "card")
                self.assertIn(code, self.problems(lambda link=link: self.install(link)))
        repo, link = make_game_repo(self.repos, name="no-card")
        (repo / "game.json").unlink()
        commit_all(repo, "no card")
        self.assertIn("NO_CARD", self.problems(lambda: self.install(link)))

    def test_a_good_rom_sha_is_accepted(self):
        repo, link = make_game_repo(self.repos)
        card = {**self.card(repo), "romSha256": hashlib.sha256((repo / "build" / "game.gbc").read_bytes()).hexdigest()}
        (repo / "game.json").write_text(json.dumps(card))
        commit_all(repo, "sha")
        self.assertTrue(self.install(link)["ok"])

    def test_plugins_need_the_users_consent(self):
        repo, link = make_game_repo(self.repos, source=True)
        (repo / "plugins" / "fx").mkdir(parents=True)
        (repo / "plugins" / "fx" / "engine.c").write_text("void run(void) {}")
        commit_all(repo, "plugin")
        self.assertTrue(installs.inspect(link, registry=self.registry)["needsPluginConsent"])
        self.refused("PLUGINS", lambda: self.install(link))
        self.assertEqual(self.install(link, allow_plugins=True)["mode"], "game+source")

    def test_one_game_id_per_machine(self):
        _, link = make_game_repo(self.repos)
        first = self.install(link)
        again = self.install(link)  # the same game from the same source is an update
        self.assertEqual((again["root"], again["changed"]), (first["root"], False))
        _, elsewhere = make_game_repo(self.repos, name="copy")
        self.assertEqual(
            installs.inspect(elsewhere, registry=self.registry)["alreadyInstalled"][0]["sameSource"], False
        )
        error = self.refused("ALREADY_HAVE", lambda: self.install(elsewhere))
        self.assertEqual(error.details["alreadyInstalled"][0]["root"], first["root"])
        _, other = make_game_repo(self.repos, name="other", identifier="cd" * 16)
        self.assertEqual(Path(self.install(other)["root"]).name, "Space Game 2")

    # -- updating ---------------------------------------------------------------------------

    def new_version(self, repo):
        (repo / "build" / "game.gbc").write_bytes(make_rom(fill=1))
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.2.0\n")
        return commit_all(repo, "0.2.0")

    def test_check_update_reads_the_branch(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.assertFalse(installs.check_update(root)["available"])
        moved = self.new_version(repo)
        self.assertEqual(installs.check_update(root), {"available": True, "commit": release.installed(root)["commit"],
                                                       "remoteCommit": moved})  # fmt: skip
        self.refused("NOT_INSTALLED", lambda: installs.check_update(self.home.base))

    def test_an_untouched_game_updates_and_keeps_the_users_files(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "captures").mkdir()
        (root / "captures" / "shot.png").write_bytes(b"png")
        (root / "build" / "game.sym").write_text("symbols")
        (root / "build" / "web").mkdir()
        (root / ".hermretro" / "notes.json").write_text("{}")
        moved = self.new_version(repo)
        result = installs.update(root, registry=self.registry)
        self.assertEqual((result["changed"], result["commit"], result["testBuildDue"]), (True, moved, True))
        self.assertEqual((root / "build" / "game.gbc").read_bytes(), make_rom(fill=1))
        self.assertEqual((root / "captures" / "shot.png").read_bytes(), b"png")
        self.assertEqual((root / "build" / "game.sym").read_text(), "symbols")
        self.assertFalse((root / "build" / "web").exists())  # made again from the new version
        self.assertTrue((root / ".hermretro" / "notes.json").is_file())
        self.assertEqual(release.installed(root)["commit"], moved)
        self.assertEqual(installs.update(root, registry=self.registry)["changed"], False)
        self.assertEqual(len(self.registry.library()), 1)

    def test_an_edited_game_asks_first(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        self.new_version(repo)
        asked = installs.update(root, registry=self.registry)
        self.assertEqual((asked["ok"], asked["needsChoice"]), (False, True))
        kept = installs.update(root, choice="keep_mine", registry=self.registry)
        self.assertFalse(kept["changed"])
        self.assertEqual((root / "project" / "scene.gbsres").read_text(), '{"mine": true}')
        self.refused("BAD_CHOICE", lambda: installs.update(root, choice="merge", registry=self.registry))

    def test_take_theirs_replaces_the_edits(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        self.new_version(repo)
        result = installs.update(root, choice="take_theirs", registry=self.registry)
        self.assertTrue(result["changed"])
        self.assertEqual((root / "project" / "scene.gbsres").read_text(), "{}")
        self.assertIs(release.local_edits(root), False)

    def test_keep_both_turns_the_edited_copy_into_a_remix(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        (root / "docs").mkdir()
        (root / "docs" / "plan.md").write_text("plan")
        self.new_version(repo)
        result = installs.update(root, choice="keep_both", registry=self.registry)
        remix = Path(result["remix"])
        self.assertEqual(remix.name, "Space Game (edited)")
        self.assertEqual((remix / "project" / "scene.gbsres").read_text(), '{"mine": true}')
        self.assertTrue((remix / "docs" / "plan.md").is_file())
        self.assertIsNone(release.installed(remix))
        self.assertEqual(self.card(remix)["remixOf"]["id"], "ab" * 16)
        self.assertNotEqual(layout.game_identity(remix), "ab" * 16)
        self.assertEqual((root / "project" / "scene.gbsres").read_text(), "{}")
        self.assertEqual(layout.game_identity(root), "ab" * 16)
        self.assertEqual(
            sorted(game["projectRoot"] for game in self.registry.library()), sorted([str(root), str(remix)])
        )

    def test_a_source_that_now_holds_another_game_is_not_installed_over_it(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        (repo / "game.json").write_text(json.dumps({**self.card(repo), "id": "ef" * 16}))
        commit_all(repo, "another game")
        self.refused("ANOTHER_GAME", lambda: installs.update(root, registry=self.registry))
        self.assertEqual(layout.game_identity(root), "ab" * 16)

    def test_two_updates_at_once_install_once(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.new_version(repo)
        results, errors = [], []

        def run():
            try:
                results.append(installs.update(root, registry=self.registry)["changed"])
            except Exception as error:  # noqa: BLE001 - reported below
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), [False, True])

    def test_records_never_hold_credentials(self):
        _, link = make_game_repo(self.repos)
        source = installs._resolve(link)
        secret = installs.Source("https://user:pw@example.invalid/r.git", None, None)
        self.assertNotIn("pw", json.dumps({"canonical": secret.canonical, **secret.record()}))
        root = Path(self.install(link)["root"])
        self.assertEqual(release.installed(root)["source"]["url"], source.public_url)


if __name__ == "__main__":
    unittest.main()
