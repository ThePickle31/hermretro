"""Installing a game from a link and updating it (backend/library/installs.py), against real git repositories in a
temporary folder (``file://`` links; nothing reaches the network).

Run alone: python -m unittest tests.backend.library.test_installs
"""

import json
import os
import sys
import threading
import unittest
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import install_build, installs, layout, ownership, release  # noqa: E402 - the repository root goes on sys.path first
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


class Workers:
    """The broker's side, faked: which games were held, and a game that is open somewhere."""

    def __init__(self):
        self.held, self.busy, self.built = [], set(), []

    def test_build(self, root):
        self.built.append(str(root))
        return {"built": True, "sha256": None, "matches": None, "commit": None, "error": None}

    def hold(self, root):
        if str(root) in self.busy:
            raise InstallError("GAME_BUSY", "This game is open in a conversation.")
        self.held.append(str(root))

    def release(self, root):
        self.held.remove(str(root))


class Base(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.registry = Registry(paths.library_dir())
        self.games = paths.games_dir(create=True)
        self.repos = self.home.base / "repos"
        self.workers = Workers()

    def inspect(self, link):
        return installs.inspect(link, registry=self.registry, allow_local=True)

    def install(self, link, commit=None, **options):
        found = self.inspect(link)
        options = {"workers": self.workers, "registry": self.registry, "games_dir": self.games, **options}
        return installs.install(found["source"], commit or found["commit"], allow_local=True, **options)

    def update(self, root, **options):
        options = {"workers": self.workers, "registry": self.registry, **options}
        return installs.update(root, allow_local=True, **options)

    def card(self, root):
        return json.loads((Path(root) / "game.json").read_text())

    def write_card(self, repo, **change):
        (repo / "game.json").write_text(json.dumps({**self.card(repo), **change}))

    def refused(self, code, step):
        with self.assertRaises(InstallError) as caught:
            step()
        self.assertEqual(caught.exception.code, code, caught.exception.details)
        return caught.exception

    def problems(self, link):
        return [
            problem["code"]
            for problem in self.refused("NOT_INSTALLABLE", lambda: self.install(link)).details["problems"]
        ]

    def visible(self):
        return sorted(name for name in os.listdir(self.games) if not name.startswith("."))


class Installing(Base):
    def test_inspect_reads_the_game_and_its_branch_without_installing_it(self):
        repo, link = make_game_repo(self.repos, source=True)
        found = self.inspect(link)
        self.assertTrue(found["ok"], found["problems"])
        self.assertEqual((found["title"], found["mode"], found["id"]), ("Space Game", "game+source", "ab" * 16))
        self.assertEqual(found["commit"], git(repo, "rev-parse", "HEAD"))
        self.assertEqual(found["source"]["ref"], "main")
        self.assertTrue(found["cover"].startswith("data:image/png;base64,"))
        self.assertEqual(self.visible(), [])

    def test_a_game_alone_installs_with_its_checked_rom(self):
        repo, link = make_game_repo(self.repos)
        (repo / "build" / "web").mkdir()
        (repo / "build" / "web" / "index.html").write_text("<script>steal()</script>")
        (repo / "build" / "game.sym").write_text("symbols")
        (repo / "docs").mkdir()
        (repo / "docs" / "notes.md").write_text("notes")
        commit_all(repo, "extras")
        result = self.install(link)
        root = Path(result["root"])
        self.assertEqual((result["mode"], result["changed"], result["testBuildDue"]), ("game", True, False))
        self.assertEqual(root, self.games / "Space Game")
        self.assertEqual(sorted(os.listdir(root / "build")), ["game.gbc"])  # no fetched browser code, no extras
        self.assertFalse((root / "docs").exists() or (root / ".git").exists())
        record = release.installed(root)
        rom_sha = self.card(root)["romSha256"]
        self.assertEqual(record["rom"], {"path": "build/game.gbc", "sha256": rom_sha})
        self.assertEqual(record["source"]["ref"], "main")
        checked = release.installed_rom(root)
        self.assertEqual((checked["romPath"], checked["sha256"]), (str(root / "build" / "game.gbc"), rom_sha))
        (root / "build" / "game.gb").write_bytes(make_rom(colour=False))  # newer, but not the checked ROM
        [game] = self.registry.library()
        self.assertEqual((game["rom"]["path"], game["install"]["mode"]), (str(root / "build" / "game.gbc"), "game"))

    def test_only_a_game_with_its_source_is_editable(self):
        _, alone = make_game_repo(self.repos, name="alone")
        _, source = make_game_repo(self.repos, name="source", source=True, identifier="cd" * 16)
        self.assertFalse(ownership.editable(Path(self.install(alone)["root"])))
        self.assertTrue(ownership.editable(Path(self.install(source)["root"])))

    def test_a_game_with_its_source_installs_and_wants_a_test_build(self):
        repo, link = make_game_repo(self.repos, source=True)
        (repo / "assets" / ".hidden").mkdir(parents=True)
        (repo / "assets" / ".hidden" / "keep.txt").write_text("kept")
        commit_all(repo, "hidden source file")
        result = self.install(link)
        self.assertEqual((result["mode"], result["testBuildDue"]), ("game+source", True))
        root = Path(result["root"])
        self.assertTrue((root / "assets" / ".hidden" / "keep.txt").is_file())
        self.assertTrue(layout.check(root)["ok"], layout.check(root))
        self.assertIsNone(release.installed_rom(root))  # it plays what it builds

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
        self.refused("BAD_FOLDER", lambda: self.inspect(repo.resolve().as_uri() + "#games/none"))

    def test_the_commit_installed_is_the_one_read(self):
        repo, link = make_game_repo(self.repos)
        read = self.inspect(link)["commit"]
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.2.0\n")
        moved = commit_all(repo, "Second")
        self.assertEqual(self.refused("SOURCE_MOVED", lambda: self.install(link, read)).details["commit"], moved)
        self.assertEqual(self.visible(), [])
        self.refused("BAD_COMMIT", lambda: self.install(link, "abc"))

    def test_a_bad_rom_is_refused(self):
        damaged = bytearray(make_rom())
        damaged[0x14D] ^= 1  # the header checksum alone
        cases = {
            "ROM_CHECKSUM": bytes(damaged),
            "ROM_CARTRIDGE": make_rom(kind=0x22),
            "ROM_SIZE": make_rom(48 * 1024),
            "ROM_COLOUR": make_rom(colour=False),
        }
        for index, (code, rom) in enumerate(cases.items()):
            with self.subTest(code):
                _, link = make_game_repo(self.repos, name=f"bad-{index}", rom=rom)
                self.assertIn(code, self.problems(link))

    def test_an_unsafe_tree_is_refused_before_checkout(self):
        repo, link = make_game_repo(self.repos, name="links")
        os.symlink("/etc/passwd", repo / "cover-link.png")
        commit_all(repo, "link")
        self.assertIn("LINK", self.problems(link))
        repo, link = make_game_repo(self.repos, name="big")
        (repo / "art").mkdir()
        (repo / "art" / "huge.bin").write_bytes(b"\1" * (21 * 1024 * 1024))
        commit_all(repo, "big")
        self.assertIn("TOO_BIG", self.problems(link))
        _, link = make_game_repo(self.repos, name="many")
        with mock.patch.object(installs.install_check, "MAX_FILES", 3):
            self.assertIn("TOO_MANY", self.problems(link))
        with mock.patch.object(installs.install_check, "take_payload") as checked_out:
            self.problems(self.repos.joinpath("links").resolve().as_uri())
        checked_out.assert_not_called()

    def test_a_card_that_is_not_a_hermretro_game_or_is_newer_is_refused(self):
        variants = {
            "NEWER_FORMAT": {"format": layout.FORMAT_VERSION + 1},
            "NO_ID": {"id": "not-an-id"},
            "ROM_CHANGED": {"romSha256": "0" * 64},
            "NO_ROM_SHA": {"romSha256": None},
            "NO_ROM": {"rom": "game.gbc"},
        }
        for index, (code, change) in enumerate(variants.items()):
            with self.subTest(code):
                repo, link = make_game_repo(self.repos, name=f"card-{index}")
                card = {key: value for key, value in {**self.card(repo), **change}.items() if value is not None}
                (repo / "game.json").write_text(json.dumps(card))
                commit_all(repo, "card")
                self.assertIn(code, self.problems(link))
        for name, damage in (("no-card", "unlink"), ("bad-card", "{not json"), ("list-card", "[1, 2]")):
            with self.subTest(name):
                repo, link = make_game_repo(self.repos, name=name)
                (repo / "game.json").unlink() if damage == "unlink" else (repo / "game.json").write_text(damage)
                commit_all(repo, name)
                self.assertTrue({"NO_CARD", "CARD_UNREADABLE"} & set(self.problems(link)))

    def test_the_cover_is_checked(self):
        repo, link = make_game_repo(self.repos, name="no-cover")
        (repo / "cover.png").unlink()
        commit_all(repo, "no cover")
        self.assertIn("NO_COVER", self.problems(link))
        repo, link = make_game_repo(self.repos, name="bomb")
        header = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + bytes.fromhex("000000a00000009008060000000000000000")
        bomb = (
            header
            + len(body := zlib.compress(b"\0" * (64 * 1024 * 1024))).to_bytes(4, "big")
            + b"IDAT"
            + body
            + b"\0" * 4
        )
        (repo / "cover.png").write_bytes(bomb)  # 160x144 by its header, 64 MB of rows inside
        commit_all(repo, "bomb")
        self.assertIn("COVER", self.problems(link))

    def test_each_mode_takes_only_its_own_files(self):
        repo, link = make_game_repo(self.repos, name="orphan-source")
        (repo / "project").mkdir()
        (repo / "project" / "scene.gbsres").write_text("{}")
        commit_all(repo, "source without a project")
        self.assertIn("SOURCE_WITHOUT_PROJECT", self.problems(link))
        repo, link = make_game_repo(self.repos, name="folder-project")
        (repo / "space.gbsproj").mkdir()
        (repo / "space.gbsproj" / "x").write_text("x")
        commit_all(repo, "a folder named like a project")
        self.assertIn("BAD_PROJECT", self.problems(link))

    def test_a_game_with_its_source_is_built_only_with_the_users_consent(self):
        repo, link = make_game_repo(self.repos, source=True)
        (repo / "plugins" / "fx").mkdir(parents=True)
        (repo / "plugins" / "fx" / "engine.c").write_text("void run(void) {}")
        commit_all(repo, "plugin")
        found = self.inspect(link)
        self.assertTrue(found["needsBuildConsent"])
        self.assertEqual(found["plugins"], ["plugins/fx/engine.c"])  # shown to the user, not a refusal
        installed = self.install(link)
        root = Path(installed["root"])
        self.assertFalse(install_build.allowed(root))  # installed, playing the ROM it came with, never built
        self.assertTrue(installed["testBuildDue"])
        self.assertNotIn("testBuild", installed)
        self.assertEqual(self.workers.built, [])
        again = self.install(link, allow_build=True)  # the same commit, now allowed: built once
        self.assertTrue(install_build.allowed(root))
        self.assertEqual(self.workers.built, [str(root)])
        self.assertEqual(again["testBuild"]["built"], True)
        consent = release.installed(root)["buildConsent"]
        self.assertEqual(consent["commit"], release.installed(root)["commit"])
        self.assertEqual(consent["digest"], release.installed(root)["sourceDigest"])

    def test_a_game_alone_needs_no_consent_and_is_never_built(self):
        _, link = make_game_repo(self.repos)
        self.assertFalse(self.inspect(link)["needsBuildConsent"])
        root = Path(self.install(link, allow_build=True)["root"])
        self.assertFalse(install_build.allowed(root))
        self.assertEqual(self.workers.built, [])

    def test_one_game_id_per_machine(self):
        _, link = make_game_repo(self.repos)
        first = self.install(link)
        again = self.install(link)  # the same game from the same source is an update
        self.assertEqual((again["root"], again["changed"]), (first["root"], False))
        _, elsewhere = make_game_repo(self.repos, name="copy")
        self.assertEqual(self.inspect(elsewhere)["alreadyInstalled"][0]["sameSource"], False)
        self.assertEqual(
            self.refused("ALREADY_HAVE", lambda: self.install(elsewhere)).details["alreadyInstalled"][0]["root"],
            first["root"],
        )
        _, other = make_game_repo(self.repos, name="other", identifier="cd" * 16)
        self.assertEqual(Path(self.install(other)["root"]).name, "Space Game 2")

    def test_an_install_that_stopped_before_registering_is_recovered_not_copied(self):
        _, link = make_game_repo(self.repos)
        with mock.patch.object(Registry, "upsert", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.install(link)
        self.assertEqual(self.visible(), ["Space Game"])
        result = self.install(link)
        self.assertEqual((result["root"], self.visible()), (str(self.games / "Space Game"), ["Space Game"]))
        self.assertEqual(len(self.registry.library()), 1)


class Updating(Base):
    def new_version(self, repo):
        rom = make_rom(fill=1)
        (repo / "build" / "game.gbc").write_bytes(rom)
        self.write_card(repo, romSha256=__import__("hashlib").sha256(rom).hexdigest())
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.2.0\n")
        return commit_all(repo, "0.2.0")

    def test_check_update_reads_the_branch(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.assertFalse(installs.check_update(root, allow_local=True)["available"])
        moved = self.new_version(repo)
        self.assertEqual(installs.check_update(root, allow_local=True)["remoteCommit"], moved)
        self.refused("NOT_INSTALLED", lambda: installs.check_update(self.home.base))

    def test_an_untouched_game_updates_and_keeps_the_users_files(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "captures").mkdir()
        (root / "captures" / "shot.png").write_bytes(b"png")
        (root / "build" / "game.sym").write_text("symbols")
        (root / "build" / "web").mkdir()
        (root / ".hermretro" / "notes.json").write_text("{}")
        self.registry.upsert(str(root), build={"t": 1, "ok": True, "rom": str(root / "build/game.gbc")})
        moved = self.new_version(repo)
        result = self.update(root)
        self.assertEqual((result["changed"], result["commit"], result["testBuildDue"]), (True, moved, True))
        self.assertEqual((root / "build" / "game.gbc").read_bytes(), make_rom(fill=1))
        self.assertEqual((root / "captures" / "shot.png").read_bytes(), b"png")
        self.assertEqual((root / "build" / "game.sym").read_text(), "symbols")
        self.assertFalse((root / "build" / "web").exists())  # made again from the new version
        self.assertTrue((root / ".hermretro" / "notes.json").is_file())
        self.assertEqual(release.installed(root)["commit"], moved)
        self.assertNotIn("lastBuild", self.registry.load()["games"][self.registry.library()[0]["id"]])
        self.assertEqual(self.update(root)["changed"], False)
        self.assertEqual((self.workers.held, self.visible()), ([], ["Space Game"]))

    def test_a_rebuild_is_not_an_edit_but_a_source_file_is(self):
        _, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "build" / "game.gbc").write_bytes(make_rom(fill=7))  # a test build from the source
        (root / "build" / "web").mkdir()
        self.assertIs(release.local_edits(root), False)
        (root / "assets" / ".palette").parent.mkdir(exist_ok=True)
        (root / "assets" / ".palette").write_text("edited")
        self.assertIs(release.local_edits(root), True)

    def test_a_game_alone_that_gains_a_project_is_edited(self):
        _, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.assertIs(release.local_edits(root), False)
        (root / "mine.gbsproj").write_text("{}")
        self.assertIs(release.local_edits(root), True)

    def test_an_edited_game_asks_first(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        self.new_version(repo)
        asked = self.update(root)
        self.assertEqual((asked["ok"], asked["needsChoice"]), (False, True))
        self.assertFalse(self.update(root, choice="keep_mine")["changed"])
        self.assertEqual((root / "project" / "scene.gbsres").read_text(), '{"mine": true}')
        self.refused("BAD_CHOICE", lambda: self.update(root, choice="merge"))

    def test_take_theirs_replaces_the_edits(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        self.new_version(repo)
        self.assertTrue(self.update(root, choice="take_theirs")["changed"])
        self.assertEqual((root / "project" / "scene.gbsres").read_text(), "{}")
        self.assertIs(release.local_edits(root), False)

    def test_keep_both_makes_the_edited_copy_a_remix_with_its_chat_and_changelog(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link)["root"])
        self.registry.upsert(str(root), chat={"sessionId": "s1", "conversationId": "c1", "profile": "p"})
        self.registry.bind(self.registry.library()[0]["id"], "st-1", "p")
        (root / "project" / "scene.gbsres").write_text('{"mine": true}')
        (root / "CHANGELOG.md").write_text("# Changelog\n\n## Mine\n\nMy levels.\n")
        (root / "docs").mkdir()
        (root / "docs" / "plan.md").write_text("plan")
        self.new_version(repo)
        with mock.patch("backend.library.install_swap.emit") as emitted:
            result = self.update(root, choice="keep_both")
        remix = Path(result["remix"])
        self.assertEqual(remix.name, "Space Game (edited)")
        self.assertEqual((remix / "project" / "scene.gbsres").read_text(), '{"mine": true}')
        self.assertIn("My levels.", (remix / "CHANGELOG.md").read_text())
        self.assertTrue((remix / "docs" / "plan.md").is_file())
        self.assertIsNone(release.installed(remix))
        self.assertEqual(self.card(remix)["remixOf"]["id"], "ab" * 16)
        self.assertNotEqual(layout.game_identity(remix), "ab" * 16)
        self.assertEqual(
            ((root / "project" / "scene.gbsres").read_text(), layout.game_identity(root)), ("{}", "ab" * 16)
        )
        listed = {game["projectRoot"]: game for game in self.registry.library()}
        self.assertEqual(listed[str(remix)]["session"]["storedId"], "st-1")
        kind, bound = self.registry.binding_for("p", ["st-1"])
        self.assertEqual((kind, bound["projectRoot"]), ("game", str(remix)))  # the chat is the remix's now
        self.assertIsNone(listed[str(root)]["chat"] or listed[str(root)]["session"])
        self.assertEqual(emitted.call_args.args[0], "library.game_moved")

    def test_a_source_that_now_holds_another_game_is_not_installed_over_it(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.write_card(repo, id="ef" * 16)
        commit_all(repo, "another game")
        self.refused("ANOTHER_GAME", lambda: self.update(root))
        self.assertEqual(layout.game_identity(root), "ab" * 16)

    def test_a_game_open_in_a_conversation_is_not_updated(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.new_version(repo)
        self.workers.busy.add(str(root))
        self.refused("GAME_BUSY", lambda: self.update(root))
        self.assertEqual(release.installed(root)["commit"], git(repo, "rev-parse", "HEAD~1"))

    def test_an_update_asks_for_consent_to_build_again(self):
        repo, link = make_game_repo(self.repos, source=True)
        root = Path(self.install(link, allow_build=True)["root"])
        self.assertTrue(install_build.allowed(root))
        (repo / "plugins").mkdir()
        (repo / "plugins" / "engine.c").write_text("void x(void) {}")
        commit_all(repo, "plugin")
        updated = self.update(root)
        self.assertTrue(updated["changed"])
        self.assertFalse(install_build.allowed(root))  # consent was for the commit before
        self.assertEqual(self.workers.built, [str(root)])  # built for the first commit only
        self.assertNotIn("testBuild", updated)

    def test_the_branch_is_kept_through_inspect_install_and_update(self):
        repo, link = make_game_repo(self.repos)
        git(repo, "checkout", "-q", "-b", "dev")
        dev = self.new_version(repo)
        git(repo, "checkout", "-q", "main")
        found = self.inspect(link + "#")
        self.assertEqual(found["source"]["ref"], "main")
        root = Path(
            installs.install(
                {**found["source"], "ref": "dev"},
                dev,
                workers=self.workers,
                registry=self.registry,
                games_dir=self.games,
                allow_local=True,
            )["root"]
        )
        self.assertEqual((release.installed(root)["source"]["ref"], release.installed(root)["commit"]), ("dev", dev))
        git(repo, "checkout", "-q", "dev")
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.3.0\n")
        newer = commit_all(repo, "0.3.0 on dev")
        self.assertEqual(self.update(root)["commit"], newer)
        git(repo, "checkout", "-q", "main")  # the repository's default branch again
        main = git(repo, "rev-parse", "main")
        moved = self.install(link)  # the same game reinstalled from main: the reviewed branch wins
        self.assertEqual(
            (moved["root"], release.installed(root)["source"]["ref"], moved["commit"]), (str(root), "main", main)
        )

    def test_a_tampered_record_is_refused_at_the_git_boundary(self):
        _, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        record = json.loads((root / ".hermretro" / "install.json").read_text())
        record["source"]["url"] = "https://evil.example/game.git"
        (root / ".hermretro" / "install.json").write_text(json.dumps(record))
        self.refused("BAD_LINK", lambda: self.update(root))
        self.refused("BAD_LINK", lambda: installs.check_update(root, allow_local=True))
        record["source"]["url"] = link
        (root / ".hermretro" / "install.json").write_text(json.dumps(record))
        self.refused("BAD_LINK", lambda: installs.check_update(root))  # local sources only where allowed

    def test_two_updates_at_once_install_once(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.new_version(repo)
        results, errors = [], []

        def run():
            try:
                results.append(self.update(root)["changed"])
            except Exception as error:  # noqa: BLE001 - reported below
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual((errors, sorted(results)), ([], [False, True]))

    def test_an_install_waits_while_an_update_has_the_name_free(self):
        repo, link = make_game_repo(self.repos)
        root = Path(self.install(link)["root"])
        self.new_version(repo)
        _, other = make_game_repo(self.repos, name="other", identifier="cd" * 16)
        other_found = self.inspect(other)
        installed = {}
        real_carry = installs.install_swap.carry

        def carry(old, new, moved, kept):  # the game's name is free right now
            thread = threading.Thread(
                target=lambda: installed.update(
                    installs.install(other_found["source"], other_found["commit"], workers=self.workers,
                                     registry=self.registry, games_dir=self.games, allow_local=True)
                )
            )  # fmt: skip
            thread.start()
            thread.join(0.5)
            self.assertTrue(thread.is_alive(), "the other install must wait for the games folder")
            installed["thread"] = thread
            real_carry(old, new, moved, kept)

        with mock.patch.object(installs.install_swap, "carry", side_effect=carry):
            self.update(root)
        installed["thread"].join()
        self.assertEqual(
            (Path(installed["root"]).name, self.visible()), ("Space Game 2", ["Space Game", "Space Game 2"])
        )


if __name__ == "__main__":
    unittest.main()
