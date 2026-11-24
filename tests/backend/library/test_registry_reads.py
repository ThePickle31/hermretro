"""Read failures must preserve the registry and leave other games usable."""

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from backend.hermes import host
from backend.library import games, game_card, project, rpcs, shelf
from tests.support import FakeBrokerClient, isolated_home, make_project


class RegistryReads(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.registry = host._registry()
        self.root = make_project(self.home.base, "First Game")
        self.game = self.registry.upsert(str(self.root))["id"]
        self.second = make_project(self.home.base, "Second Game")
        self.ctx = mock.Mock()
        self.ctx.get_config.return_value = True
        self.status = rpcs.rpc_game_build_status(self.ctx)

    def test_a_missing_index_initializes_but_a_dangling_link_does_not(self):
        self.registry.path.unlink()
        self.assertEqual(self.registry.load()["games"], {})
        self.registry.path.symlink_to(self.registry.directory / "missing.json")
        with self.assertRaises(games.RegistryError):
            self.registry.upsert(str(self.second))
        self.assertTrue(self.registry.path.is_symlink())

    def test_malformed_index_never_gets_replaced(self):
        for contents in (
            b"{",
            b"\xff",
            b"[]",
            b"{}",
            b'{"games": []}',
            b'{"version": 2, "games": {}}',
            b'{"games": {}, "pending": []}',
            b'{"games": {}, "presentations": {}}',
        ):
            with self.subTest(contents=contents):
                self.registry.path.write_bytes(contents)
                for mutate in (
                    lambda: self.registry.upsert(str(self.second)),
                    lambda: self.registry.build_start("pending-id", None),
                    lambda: self.registry.present(str(self.root)),
                ):
                    with self.assertRaises(games.RegistryError):
                        mutate()
                self.assertEqual(self.registry.path.read_bytes(), contents)

    def test_a_failed_read_leaves_the_original_games_bindings_and_pending_in_place(self):
        self.registry.bind(self.game, "stored-first", None)
        self.registry.build_start("stored-new", None)
        before = self.registry.path.read_bytes()
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("try again")):
            with self.assertRaisesRegex(games.RegistryError, "try again"):
                self.registry.upsert(str(self.second))
            self.assertEqual(self.status({"id": self.game})["code"], "UNAVAILABLE")
        self.assertEqual(self.registry.path.read_bytes(), before)
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "stored-first")
        self.assertEqual(self.registry.pending()[0]["storedId"], "stored-new")

    def test_bad_metadata_does_not_damage_the_shelf_or_other_records(self):
        data = self.registry.load()
        entry = data["games"][self.game]
        entry["lastBuild"] = {"ok": False, "t": ["bad time"]}
        entry["updatedAt"] = {"bad": "time"}
        entry["chat"] = {"sessionId": [], "conversationId": {}}
        entry["session"] = {"storedId": "first-chat", "aliases": [[], "alias"]}
        data["games"]["f" * 12] = {"projectRoot": ""}
        data["pending"]["bad"] = "unrecognized record"
        data["presentations"] = ["unrecognized presentation"]
        self.registry.path.write_text(json.dumps(data))
        descriptor = next(self.root.glob("*.gbsproj"))
        descriptor.write_text('{"name": ["bad title"]}')
        config = self.root / "build" / "web" / "gbstudio.json"
        config.write_text(json.dumps({**json.loads(config.read_text()), "project": "bad project"}))
        (self.root / "game.json").write_text('{"title": "A title", "genres": 42, "tags": {"bad": "tags"}}')

        second_id = self.registry.upsert(str(self.second))["id"]
        with mock.patch.object(host, "try_connect", return_value=(None, None)):
            answer = rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"], answer)
        second, first = answer["games"]
        self.assertEqual((second["id"], first["id"]), (second_id, self.game))
        self.assertEqual(first["title"], entry["title"])
        self.assertEqual(first["card"]["genres"], [])
        self.assertEqual(first["card"]["tags"], [])
        self.assertIsNone(first["chat"])
        stored = self.registry.load()
        self.assertEqual(stored["games"][self.game], entry)
        self.assertEqual(stored["pending"], data["pending"])
        self.assertEqual(stored["presentations"], data["presentations"])

    def test_status_distinguishes_an_unavailable_project_and_a_missing_game(self):
        real_stat = Path.stat

        def stat(path, **kwargs):
            if path == self.root:
                raise PermissionError("temporarily unavailable")
            return real_stat(path, **kwargs)

        second_id = self.registry.upsert(str(self.second))["id"]
        list_games = rpcs.rpc_games(self.ctx)
        with mock.patch.object(host, "try_connect", return_value=(None, None)):
            with mock.patch.object(Path, "stat", stat):
                self.assertEqual(self.status({"id": self.game})["code"], "UNAVAILABLE")
                answer = list_games({})
            self.assertTrue(answer["ok"])
            self.assertEqual([game["id"] for game in answer["games"]], [second_id])
            self.assertEqual(answer["unavailable"], [self.game])

            recovered = list_games({})
            self.assertEqual([game["id"] for game in recovered["games"]], [second_id, self.game])
            self.assertEqual(recovered["unavailable"], [])

            self.root.rename(self.root.with_name("Outside the library"))
            removed = list_games({})
            self.assertEqual([game["id"] for game in removed["games"]], [second_id])
            self.assertEqual(removed["unavailable"], [])
            self.assertEqual(self.status({"id": self.game})["code"], "NO_GAME")
            self.assertEqual(self.status({"id": "a" * 12})["code"], "NO_GAME")

    def test_status_does_not_report_a_native_rom_as_a_rebuild_after_a_failed_web_read(self):
        config = self.root / "build" / "web" / "gbstudio.json"
        read_text = Path.read_text

        def read(path, **kwargs):
            if path == config:
                raise PermissionError("cannot read the web config")
            return read_text(path, **kwargs)

        with mock.patch.object(Path, "read_text", read):
            self.assertEqual(self.status({"id": self.game})["code"], "UNAVAILABLE")
            [game] = self.registry.library()
        self.assertTrue(game["webExport"])
        self.assertIsNone(game["web"])
        self.assertEqual(game["rom"]["path"], str(self.root / "build" / "game.gbc"))

    def test_status_leaves_a_malformed_web_export_unavailable_until_it_can_be_read(self):
        config = self.root / "build" / "web" / "gbstudio.json"
        saved = config.read_bytes()
        first = self.status({"id": self.game})
        for contents in (b"{", b"[]", b'{"rom": ["wrong type"]}', b'{"rom": "rom/missing.gbc"}'):
            with self.subTest(contents=contents):
                config.write_bytes(contents)
                self.assertEqual(self.status({"id": self.game})["code"], "UNAVAILABLE")
                [game] = self.registry.library()
                self.assertTrue(game["webExport"])
                self.assertIsNone(game["web"])
        config.write_bytes(saved)
        self.assertEqual(self.status({"id": self.game}), first)

    def test_a_malformed_recorded_rom_does_not_hide_a_healthy_web_export(self):
        data = self.registry.load()
        data["games"][self.game]["lastBuild"] = {"ok": True, "rom": str(self.root / ("x" * 4096 + ".gb"))}
        self.registry.path.write_text(json.dumps(data))
        [game] = self.registry.library()
        self.assertEqual(game["id"], self.game)
        self.assertTrue(game["webExport"])
        self.assertEqual(game["web"]["sha256"], self.status({"id": self.game})["game"]["web"]["sha256"])

    def test_unusable_native_rom_candidates_do_not_hide_a_healthy_build(self):
        root = make_project(self.home.base, "Native Game", web=False)
        identifier = self.registry.upsert(str(root))["id"]
        rom = root / "build" / "game.gbc"
        loop = rom.with_name("loop.gb")
        loop.symlink_to(loop.name)
        unreadable = rom.with_name("unreadable.gbc")
        unreadable.touch()
        now = rom.stat().st_mtime + 10
        os.utime(unreadable, (now, now))
        file_sha256 = project.file_sha256

        def sha256(path):
            if path == unreadable:
                raise PermissionError("cannot read this ROM")
            return file_sha256(path)

        with mock.patch.object(project, "file_sha256", sha256):
            answer = self.status({"id": identifier})
            games_on_shelf = {game["id"]: game for game in self.registry.library()}
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["game"]["rom"]["path"], str(rom))
        self.assertEqual(games_on_shelf[identifier]["rom"], answer["game"]["rom"])

    def test_invalid_registry_key_cannot_claim_a_valid_games_chat(self):
        self.registry.bind(self.game, "stored-first", host._profile_identity())
        data = self.registry.load()
        data["games"]["invalid-id"] = data["games"][self.game]
        self.registry.path.write_text(json.dumps(data))
        with mock.patch.object(host, "try_connect", return_value=(None, None)):
            listed = rpcs.rpc_games(self.ctx)({})["games"]
        self.assertEqual([game["id"] for game in listed], [self.game])
        self.assertEqual(listed[0]["chat"]["sessionId"], "stored-first")
        self.assertEqual(self.status({"id": self.game})["game"]["chat"]["sessionId"], "stored-first")

    def test_public_game_timestamps_are_finite_without_rewriting_the_registry(self):
        self.registry.bind(self.game, "stored-first", host._profile_identity())
        data = self.registry.load()
        entry = data["games"][self.game]
        entry["session"]["createdAt"] = float("nan")
        entry["updatedAt"] = float("inf")
        original = json.dumps(data).encode()
        self.registry.path.write_bytes(original)
        [game] = self.registry.library()
        self.assertIsNone(game["updatedAt"])
        self.assertIsNone(game["session"]["createdAt"])
        with mock.patch.object(host, "try_connect", return_value=(None, None)):
            json.dumps(rpcs.rpc_games(self.ctx)({}), allow_nan=False)
        json.dumps(self.status({"id": self.game}), allow_nan=False)
        self.assertEqual(self.registry.path.read_bytes(), original)

    def test_games_rpc_uses_one_snapshot_and_routes_chat_using_the_registry_key(self):
        profile = host._profile_identity()
        self.registry.bind(self.game, "stored-first", profile)
        self.registry.build_start("stored-new", profile, "New game")
        data = self.registry.load()
        data["games"][self.game]["id"] = "f" * 12
        self.registry.path.write_text(json.dumps(data))
        read = self.registry.load
        with (
            mock.patch.object(host, "try_connect", return_value=(None, None)),
            mock.patch.object(host, "_registry", return_value=self.registry),
            mock.patch.object(self.registry, "load", wraps=read) as load,
        ):
            answer = rpcs.rpc_games(self.ctx)({})
        self.assertEqual(load.call_count, 1)
        self.assertTrue(answer["ok"], answer)
        [game] = answer["games"]
        self.assertEqual(game["id"], self.game)
        self.assertEqual(game["chat"]["sessionId"], "stored-first")
        self.assertEqual(answer["pending"][0]["storedId"], "stored-new")
        self.assertEqual(self.registry.binding_for(profile, ["stored-first"])[1]["id"], self.game)
        self.assertEqual(self.status({"id": self.game})["game"]["id"], self.game)
        self.assertEqual(self.registry.load(), data)

    def test_status_only_reads_the_requested_game_and_keeps_its_chat_route(self):
        self.registry.upsert(str(self.second))
        self.registry.bind(self.game, "stored-first", host._profile_identity())
        real_artifacts = project.build_artifacts
        with (
            mock.patch.object(project, "build_artifacts", wraps=real_artifacts) as artifacts,
            mock.patch.object(project, "sources_newer_than", side_effect=AssertionError("source walk")),
            mock.patch.object(game_card, "public", side_effect=AssertionError("card read")),
            mock.patch.object(shelf, "describe", side_effect=AssertionError("shelf description")),
            mock.patch.object(host, "try_connect", side_effect=AssertionError("broker request")),
        ):
            answer = self.status({"id": self.game})
        self.assertEqual(artifacts.call_count, 1)
        self.assertEqual(artifacts.call_args.args[0], self.root.resolve())
        self.assertTrue(answer["ok"], answer)
        self.assertTrue(answer["device"]["hardwareEnabled"])
        game = answer["game"]
        self.assertEqual(game["chat"]["sessionId"], "stored-first")
        self.assertEqual(game["session"]["storedId"], "stored-first")
        self.assertTrue(game["session"]["thisProfile"])
        self.assertNotIn("card", game)

    def test_shelf_cleans_pending_metadata_without_changing_the_registry(self):
        data = self.registry.load()
        data["pending"] = {
            "bad": {"storedId": "bad", "name": {"broken": True}, "createdAt": [1]},
            "infinite": {"storedId": "infinite", "name": "   ", "createdAt": float("inf")},
            "valid": {"storedId": "valid", "name": "  " + "x" * 150 + "  ", "createdAt": 123},
        }
        self.registry.path.write_text(json.dumps(data))
        original = self.registry.path.read_bytes()
        with mock.patch.object(host, "try_connect", return_value=(None, None)):
            answer = rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            answer["pending"],
            [
                {"storedId": "bad", "name": None, "createdAt": None, "exists": None},
                {"storedId": "infinite", "name": None, "createdAt": None, "exists": None},
                {"storedId": "valid", "name": "x" * 120, "createdAt": 123, "exists": None},
            ],
        )
        self.assertEqual(self.registry.path.read_bytes(), original)

    def test_shelf_seeding_skips_registered_lanes(self):
        lane = {"selected_root": str(self.root), "sessions_seen": ["other-chat"]}
        client = FakeBrokerClient({"ok": True, "lanes": [lane, lane]})
        with (
            mock.patch.object(host, "try_connect", return_value=(client, None)),
            mock.patch.object(host, "_registry", return_value=self.registry),
            mock.patch.object(self.registry, "load", wraps=self.registry.load) as load,
            mock.patch.object(self.registry, "upsert", wraps=self.registry.upsert) as upsert,
        ):
            answer = rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual([game["id"] for game in answer["games"]], [self.game])
        load.assert_called_once()
        upsert.assert_not_called()

    def test_shelf_seeding_rechecks_a_missing_game_under_the_registry_lock(self):
        lane = {"selected_root": str(self.second), "sessions_seen": ["seed-chat"]}
        client = FakeBrokerClient({"ok": True, "lanes": [lane, lane]})
        upsert = self.registry.upsert

        def register_before_seed(root, **kwargs):
            upsert(root, chat={"sessionId": "new-chat"})
            return upsert(root, **kwargs)

        with (
            mock.patch.object(host, "try_connect", return_value=(client, None)),
            mock.patch.object(host, "_registry", return_value=self.registry),
            mock.patch.object(self.registry, "upsert", side_effect=register_before_seed) as seed,
        ):
            answer = rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"], answer)
        new = next(game for game in answer["games"] if game["id"] != self.game)
        self.assertEqual(new["chat"]["sessionId"], "new-chat")
        seed.assert_called_once_with(str(self.second), chat={"sessionId": "seed-chat"}, only_if_missing=True)

    def test_status_detects_an_external_rom_replacement_with_the_same_size_and_mtime(self):
        rom = self.root / "build" / "web" / "rom" / "game.gbc"
        previous = self.status({"id": self.game})["game"]["web"]
        info = rom.stat()
        replacement = rom.with_suffix(".tmp")
        replacement.write_bytes(b"?" * info.st_size)
        os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
        replacement.replace(rom)
        current = self.status({"id": self.game})["game"]["web"]
        self.assertEqual(previous["builtAt"], current["builtAt"])
        self.assertNotEqual(previous["sha256"], current["sha256"])
