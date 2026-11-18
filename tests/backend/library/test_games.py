"""The game library: registry file, build state, the broker hook and the desktop RPC."""

import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Broker, Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import tools as setup_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.support import registered_hook  # noqa: E402 - the repository root goes on sys.path first


def encode_png(width, height, pixel):
    """A plain 8-bit RGBA PNG whose pixel at (x, y) is ``pixel(x, y)``."""
    import struct
    import zlib

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    rows = b"".join(b"\0" + bytes(value for x in range(width) for value in pixel(x, y)) for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


# A 160x144 pixel-art cover: four colours in bands.
COVER = encode_png(
    160,
    144,
    lambda x, y: ((40, 120, 60, 255), (230, 160, 60, 255), (60, 90, 200, 255), (250, 250, 240, 255))[
        (x // 40 + y // 36) % 4
    ],
)


def complete_card(root: Path) -> None:
    """Give a test project a finished game card (game.json + cover.png)."""
    (root / "cover.png").write_bytes(COVER)
    (root / "game.json").write_text(
        json.dumps(
            {
                "version": 1,
                "title": "Space Game",
                "tagline": "Fly a tiny ship through a meteor field.",
                "description": "Dodge meteors, grab fuel cells and reach the space station before your tank runs dry.",
                "genres": ["Arcade"],
                "cover": "cover.png",
            }
        )
    )


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def make_project(base: Path, name="Space Game", web=True, built=True, card=True) -> Path:
    root = base / name.lower().replace(" ", "-")
    (root / "project").mkdir(parents=True)
    (root / f"{root.name}.gbsproj").write_text(json.dumps({"_resourceType": "project", "name": name}))
    (root / "project" / "scene.gbsres").write_text("{}")
    if built:
        (root / "build").mkdir()
        (root / "build" / "project.gb").write_bytes(b"\0" * 512)
    if web:
        web_dir = root / "build" / "web"
        (web_dir / "js").mkdir(parents=True)
        (web_dir / "rom").mkdir()
        (web_dir / "rom" / "game.gbc").write_bytes(b"\1" * 512)
        (web_dir / "js" / "binjgb.wasm").write_bytes(b"\0asm-test")
        (web_dir / "index.html").write_text("<html><head></head><body></body></html>")
        (web_dir / "gbstudio.json").write_text(json.dumps({"rom": "rom/game.gbc", "project": {"name": name}}))
    if card:
        complete_card(root)
    old = time.time() - 600
    for path in root.rglob("*"):
        os.utime(path, (old, old))
    for rom in root.glob("build/**/*.gb*"):
        os.utime(rom, (old + 300, old + 300))
    return root


class Registry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.registry = games.Registry(self.base / "lib")

    def tearDown(self):
        self.tmp.cleanup()

    def test_id_is_twelve_hex_of_the_canonical_root(self):
        root = make_project(self.base)
        self.assertRegex(games.game_id(root), r"^[0-9a-f]{12}$")
        self.assertEqual(games.game_id(root), games.game_id(str(root) + "/."))

    def test_a_selected_project_joins_the_library_with_its_chat(self):
        root = make_project(self.base)
        self.registry.observe(
            "project_select",
            {"projectPath": str(root)},
            {"projectRoot": str(root)},
            False,
            lane_root=str(root),
            conversation_id="conv-1",
            sessions_seen=["s1", "s2"],
            profile="/home/u/.hermes/profiles/studio/plugin-data/hermretro",
        )
        [game] = self.registry.library()
        self.assertEqual(game["id"], games.game_id(root))
        self.assertEqual(game["title"], "Space Game")
        self.assertEqual(game["kind"], "gbstudio")
        self.assertEqual(game["state"], "ready")
        self.assertTrue(game["webExport"])
        self.assertEqual(game["chat"]["sessionId"], "s2")
        self.assertEqual(game["rom"]["size"], 512)
        self.assertRegex(game["rom"]["sha256"], r"^[0-9a-f]{64}$")

    def test_the_web_exports_own_rom_is_reported_for_the_players_rebuilt_check(self):
        # The web export is its own compilation: its ROM is not the native build's bytes, and the page
        # must compare the player's loaded hash with this one, or every build looks "rebuilt".
        root = make_project(self.base)
        rom = root / "build" / "project.gb"
        self.registry.observe(
            "rom_build", {}, {"success": True, "outputPath": str(rom)}, False, lane_root=str(root), conversation_id="c"
        )
        [game] = self.registry.library()
        self.assertEqual(game["rom"]["path"], str(rom))
        self.assertEqual(game["web"]["sha256"], games.file_sha256(root / "build" / "web" / "rom" / "game.gbc"))
        self.assertNotEqual(game["web"]["sha256"], game["rom"]["sha256"])
        self.assertIsInstance(game["web"]["builtAt"], int)
        self.assertIsNone(
            games.Registry(self.base / "lib2").describe(
                {"projectRoot": str(make_project(self.base, "No Web", web=False))}
            )["web"]
        )

    def test_a_project_created_without_selecting_has_no_chat(self):
        root = make_project(self.base)
        self.registry.observe(
            "project_create",
            {"select": False},
            {"projectRoot": str(root)},
            False,
            lane_root=None,
            conversation_id="conv-1",
        )
        self.assertIsNone(self.registry.library()[0]["chat"])

    def test_states_follow_builds_and_source_edits(self):
        root = make_project(self.base, web=False, built=False)
        self.registry.upsert(str(root))
        self.assertEqual(self.registry.library()[0]["state"], "unbuilt")
        self.registry.observe(
            "rom_build",
            {},
            {"success": False, "error": "Compiler said no " * 40},
            True,
            lane_root=str(root),
            conversation_id="c",
        )
        game = self.registry.library()[0]
        self.assertEqual(game["state"], "failed")
        self.assertLessEqual(len(game["error"]), 240)
        (root / "build").mkdir()
        rom = root / "build" / "project.gb"
        rom.write_bytes(b"\2" * 256)
        self.registry.observe(
            "rom_build", {}, {"success": True, "outputPath": str(rom)}, False, lane_root=str(root), conversation_id="c"
        )
        game = self.registry.library()[0]
        self.assertEqual((game["state"], game["rom"]["path"], game["error"]), ("ready", str(rom), None))
        self.assertFalse(game["webExport"])
        future = time.time() + 30
        os.utime(root / "project" / "scene.gbsres", (future, future))
        self.assertEqual(self.registry.library()[0]["state"], "changed")

    def test_captures_and_build_output_are_not_source(self):
        root = make_project(self.base)
        self.registry.upsert(str(root))
        (root / "captures").mkdir()
        (root / "captures" / "shot.png").write_bytes(PNG)
        (root / "build" / "web" / "index.html").touch()
        self.assertEqual(self.registry.library()[0]["state"], "ready")

    def test_standalone_c_builds_inside_a_gb_studio_project_do_not_count(self):
        root = make_project(self.base)
        self.registry.upsert(str(root))
        self.registry.observe(
            "rom_build", {"sourcePath": "x.c"}, {"success": False}, True, lane_root=str(root), conversation_id="c"
        )
        self.assertEqual(self.registry.library()[0]["state"], "ready")

    def test_deleted_projects_drop_off_the_shelf(self):
        root = make_project(self.base)
        self.registry.upsert(str(root))
        for path in sorted(root.rglob("*"), reverse=True):
            path.rmdir() if path.is_dir() else path.unlink()
        root.rmdir()
        self.assertEqual(self.registry.library(), [])

    def test_thumbnails_are_bounded_pngs(self):
        root = make_project(self.base)
        identifier = self.registry.upsert(str(root))["id"]
        self.registry.save_thumb(
            identifier,
            games.decode_png("data:image/png;base64," + base64.b64encode(PNG).decode(), games.MAX_THUMB_BYTES),
        )
        self.assertTrue(self.registry.library()[0]["thumb"].startswith("data:image/png;base64,"))
        with self.assertRaises(ValueError):
            games.decode_png("data:image/jpeg;base64,AAAA", games.MAX_THUMB_BYTES)
        with self.assertRaises(ValueError):
            games.decode_png("data:image/png;base64," + base64.b64encode(b"GIF89a").decode(), games.MAX_THUMB_BYTES)
        with self.assertRaises(ValueError):
            games.decode_png(
                "data:image/png;base64," + base64.b64encode(PNG + b"\0" * 70000).decode(), games.MAX_THUMB_BYTES
            )
        with self.assertRaises(ValueError):
            self.registry.save_thumb("../../etc", PNG)

    def test_concurrent_writers_keep_every_game(self):
        roots = [make_project(self.base, name=f"Game {n}", web=False) for n in range(8)]
        threads = [threading.Thread(target=self.registry.upsert, args=(str(r),)) for r in roots]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(self.registry.load()["games"]), 8)


class BrokerHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lanes_record_builds_into_the_brokers_library(self):
        broker = Broker.__new__(Broker)
        broker.lanes, broker.table_lock = {}, threading.RLock()
        broker.games = games.Registry(self.base / "lib")
        broker.trace = lambda **record: None
        lane = broker.lane_for(("profile", "conv"), create=True)
        root = make_project(self.base)
        lane.selected_root = str(root)
        lane.remember("rom_build", "project-write", {"isError": True, "structuredContent": {"error": "boom"}}, 1.0, {})
        [game] = broker.games.library()
        self.assertEqual((game["state"], game["error"]), ("failed", "boom"))

    def test_a_failing_library_never_breaks_a_call(self):
        lane = Lane(("p", "c"))
        lane.observer = mock.Mock(side_effect=OSError("disk full"))
        lane.remember("rom_build", "project-write", {"structuredContent": {}}, 0.1, {})
        self.assertEqual(lane.activity[-1]["tool"], "rom_build")

    def test_only_the_real_broker_writes_the_users_library(self):
        with mock.patch.dict(
            os.environ,
            {"HERMRETRO_RUNTIME_DIR": str(self.base / "run"), "HERMRETRO_LIBRARY_DIR": str(self.base / "library")},
        ):
            self.assertEqual(paths.library_dir_for(self.base / "run"), self.base / "library")
            self.assertEqual(paths.library_dir_for(self.base / "acceptance"), self.base / "acceptance")


class GamesRpc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        home = self.base / "hermes" / "profiles" / "studio"
        (home / "plugin-data" / "hermretro").mkdir(parents=True)
        self.patches = [
            mock.patch.dict(
                os.environ,
                {
                    "HERMRETRO_LIBRARY_DIR": str(self.base / "lib"),
                    "HERMRETRO_GAMES_DIR": str(self.base / "games"),
                    "HERMRETRO_RUNTIME_DIR": str(self.base / "run"),
                },
            ),
            mock.patch.object(hermes_host, "_data_dir", lambda: home / "plugin-data" / "hermretro"),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
        ]
        for patch in self.patches:
            patch.start()
        self.identity = str((home / "plugin-data" / "hermretro").resolve())
        self.ctx = mock.Mock()
        self.ctx.get_config = lambda key, default=None: {"hardware_enabled": True}.get(key, default)

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_games_lists_the_library_in_the_contract_shape(self):
        root = make_project(self.base)
        games.Registry(paths.library_dir()).observe(
            "project_select",
            {},
            {"projectRoot": str(root)},
            False,
            lane_root=str(root),
            conversation_id="conv",
            sessions_seen=["run-1"],
            profile=self.identity,
        )
        answer = library_rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["device"], {"hardwareEnabled": True, "skipped": False})
        [game] = answer["games"]
        self.assertEqual(
            set(game) - {"chat"},
            {
                "id",
                "title",
                "projectRoot",
                "kind",
                "state",
                "rom",
                "webExport",
                "web",
                "thumb",
                "error",
                "session",
                "cover",
                "card",
                "displayTitle",
            },
        )
        self.assertTrue(game["cover"])
        self.assertTrue(game["thumb"].startswith("data:image/png;base64,"))
        self.assertEqual(game["card"]["tagline"], "Fly a tiny ship through a meteor field.")
        self.assertTrue(game["card"]["complete"])
        self.assertIsNone(game["session"])
        self.assertEqual(answer["pending"], [])
        self.assertEqual(game["chat"]["sessionId"], "run-1")
        self.assertEqual(game["chat"]["profile"], "studio")
        self.assertTrue(game["chat"]["thisProfile"])

    def build_response(self, root, **extra):
        response = {
            "ok": True,
            "dispatched": True,
            "result": {"content": [], "structuredContent": {"success": True}},
            "player": {"ready": True, "url": "http://127.0.0.1:9/engine/", "first": True},
            "lane": {"selected_root": str(root)},
        }
        response.update(extra)
        return response

    def test_the_tool_handler_adds_no_studio_player_to_a_build_result(self):
        root = make_project(self.base)
        games.Registry(paths.library_dir()).upsert(str(root))
        response = self.build_response(root)

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def call(self, *_args, **_kwargs):
                return response

        with (
            mock.patch.object(hermes_host, "ensure_broker", lambda: Client()),
            mock.patch.object(hermes_host, "_attach_images", lambda: False),
        ):
            handler = hermes_host.make_tool_handler(self.ctx, {"name": "rom_build"})
            payload = json.loads(handler({}, conversation_id="conv", session_id="s1"))
        for gone in ("studio", "studioPlayerUrl", "studioGameId"):
            self.assertNotIn(gone, payload)
        self.assertNotIn(games.game_id(root), json.dumps(payload))
        self.assertIn("chromatic_present_game", payload["nextStep"])

    def test_new_games_default_to_the_plugin_games_folder(self):
        seen = []

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def call(self, _owner, tool, args, **_kwargs):
                seen.append((tool, args))
                return {"ok": True, "dispatched": True, "result": {"structuredContent": {"success": True}}}

        folder = self.base / "studio-games"
        with (
            mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(folder)}),
            mock.patch.object(hermes_host, "ensure_broker", lambda: Client()),
            mock.patch.object(hermes_host, "_attach_images", lambda: False),
        ):
            for tool in ("project_create", "project_create_blank"):
                hermes_host.make_tool_handler(self.ctx, {"name": tool})(
                    {"name": "Star Garden: II", "template": "starter"}, conversation_id="conv", session_id="s1"
                )
            hermes_host.make_tool_handler(self.ctx, {"name": "project_create"})(
                {"name": "Mine", "template": "starter", "destinationPath": "/elsewhere/Mine"},
                conversation_id="conv",
                session_id="s1",
            )
            schema = next(s for s in contracts.hermes_schemas() if s["name"] == "chromatic_project_create")
        self.assertTrue(folder.is_dir(), "the games folder is created for the engine")
        self.assertEqual(
            [args["destinationPath"] for _tool, args in seen],
            [str(folder / "Star Garden II")] * 2 + ["/elsewhere/Mine"],
        )
        self.assertNotIn("destinationPath", schema["parameters"]["required"])
        self.assertIn("games folder", schema["description"])

    # -- chromatic_present_game ---------------------------------------------------------
    def present(self, args=None, **kwargs):
        kwargs.setdefault("conversation_id", "conv")
        kwargs.setdefault("session_id", "run-1")
        return json.loads(library_tools.present_game_handler(args or {}, **kwargs))

    def lane_client(self, root, matched="chat"):
        """A running broker that knows this chat's lane; records every request it gets."""
        seen = []

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def request(self, message):
                seen.append(message)
                return {"ok": True, "matched": matched, "lane": {"project_root": str(root)}}

        return seen, (lambda _dir: (Client(), None))

    def test_present_shows_the_chats_project_and_records_it(self):
        root = make_project(self.base)
        seen, connect = self.lane_client(root)
        with mock.patch.object(hermes_host, "try_connect", connect):
            payload = self.present({"note": "  Try the double jump  "})
        identifier = games.game_id(root)
        self.assertEqual(set(payload), {"ok", "studio", "message"})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"], "Shown to the user beside the chat.")
        studio = payload["studio"]
        self.assertEqual({"gameId", "playerUrl", "title", "note"} - set(studio), set())
        self.assertEqual(studio["gameId"], identifier)
        self.assertEqual(studio["title"], "Space Game")
        self.assertEqual(studio["note"], "Try the double jump")
        self.assertRegex(studio["playerUrl"], r"^http://127\.0\.0\.1:\d+/[^/]+/" + identifier + r"/index\.html$")
        # Memory-only lane lookup: the broker is asked nothing else and never started.
        self.assertEqual([message["op"] for message in seen], ["activity"])
        self.assertEqual(seen[0]["ids"], ["conv", "run-1"])
        entry = games.Registry(paths.library_dir()).get(identifier)
        self.assertEqual(entry["chat"], {"conversationId": "conv", "sessionId": "run-1", "profile": self.identity})
        self.assertEqual(entry["presented"]["note"], "Try the double jump")
        self.assertAlmostEqual(entry["presented"]["t"], studio["presentedAt"], places=3)
        [shown] = library_rpcs.rpc_presentations(self.ctx)({"since": time.time() - 60})["presentations"]
        self.assertEqual(
            (shown["gameId"], shown["note"], shown["sessionId"], shown["conversationId"]),
            (identifier, "Try the double jump", "run-1", "conv"),
        )
        self.assertEqual((shown["profile"], shown["thisProfile"], shown["title"]), ("studio", True, "Space Game"))

    def test_present_requires_a_fresh_web_export(self):
        root = make_project(self.base)
        rom = root / "build" / "project.gb"
        later = rom.stat().st_mtime + 60
        os.utime(rom, (later, later))  # a newer native build than the web copy
        seen, connect = self.lane_client(root)
        with mock.patch.object(hermes_host, "try_connect", connect):
            payload = self.present()
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "BUILD_FIRST")
            self.assertIn("chromatic_rom_build", payload["error"] + payload["guidance"])
            self.assertIsNone(games.Registry(paths.library_dir()).get(games.game_id(root)))
            self.assertEqual(library_rpcs.rpc_presentations(self.ctx)({})["presentations"], [])

            bare = make_project(self.base, name="Bare Game", web=False)
            seen[:] = []
            _seen, connect_bare = self.lane_client(bare)
        with mock.patch.object(hermes_host, "try_connect", connect_bare):
            payload = self.present()
        self.assertEqual(payload["code"], "BUILD_FIRST")
        self.assertIn("chromatic_rom_build", payload["error"])

    def test_a_failed_build_after_the_web_copy_makes_it_stale(self):
        root = make_project(self.base)
        registry = games.Registry(paths.library_dir())
        registry.upsert(str(root), build={"t": time.time(), "ok": False, "rom": None, "sha256": None, "error": "x"})
        self.assertFalse(games.export_freshness(root, registry.get(games.game_id(root))["lastBuild"])[0])
        registry.upsert(
            str(root), build={"t": time.time() - 1000, "ok": True, "rom": None, "sha256": None, "error": None}
        )
        self.assertEqual(games.export_freshness(root, registry.get(games.game_id(root))["lastBuild"]), (True, None))

    def test_an_unchanged_export_the_engine_reused_still_counts_as_fresh(self):
        # Seen for real: a rebuild without source changes rewrites build/*.gb but the engine reuses the
        # web export without touching its files. The broker's record of that web_preview proves it current.
        root = make_project(self.base)
        rom = root / "build" / "project.gb"
        later = rom.stat().st_mtime + 600
        os.utime(rom, (later, later))
        registry = games.Registry(paths.library_dir())
        registry.observe(
            "rom_build",
            {},
            {"success": True, "outputPath": str(rom)},
            False,
            lane_root=str(root),
            conversation_id="conv",
            sessions_seen=["run-1"],
            profile=self.identity,
        )
        entry = registry.get(games.game_id(root))
        self.assertFalse(games.export_freshness(root, entry["lastBuild"], entry.get("lastWebExport"))[0])
        registry.observe(
            "web_preview",
            {},
            {"success": True, "url": "http://e/"},
            False,
            lane_root=str(root),
            conversation_id="conv",
            sessions_seen=["run-1"],
            profile=self.identity,
        )
        entry = registry.get(games.game_id(root))
        self.assertIn("lastWebExport", entry)
        self.assertEqual(games.export_freshness(root, entry["lastBuild"], entry["lastWebExport"]), (True, None))
        seen, connect = self.lane_client(root)
        with mock.patch.object(hermes_host, "try_connect", connect):
            self.assertTrue(self.present()["ok"])
        # A later build without a refreshed web copy makes it stale again.
        time.sleep(0.01)
        registry.upsert(
            str(root), build={"t": time.time() + 10, "ok": True, "rom": str(rom), "sha256": None, "error": None}
        )
        with mock.patch.object(hermes_host, "try_connect", connect):
            self.assertEqual(self.present()["code"], "BUILD_FIRST")

    def test_present_falls_back_to_the_chat_link_then_needs_a_project(self):
        root = make_project(self.base)
        games.Registry(paths.library_dir()).upsert(
            str(root), chat={"conversationId": "conv", "sessionId": "old-run", "profile": self.identity}
        )
        payload = self.present()  # no broker running (setUp): the library's chat link
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["studio"]["gameId"], games.game_id(root))
        payload = self.present(conversation_id="other", session_id="other-run")
        self.assertEqual((payload["ok"], payload["code"]), (False, "NO_PROJECT"))

    def test_an_explicit_project_is_used_and_checked(self):
        root = make_project(self.base)
        payload = self.present({"project": str(root)}, conversation_id="", session_id="")
        self.assertTrue(payload["ok"], payload)
        self.assertIsNone(payload["studio"]["note"])
        self.assertEqual(self.present({"project": "relative/path"})["code"], "PROJECT_NOT_FOUND")
        self.assertEqual(self.present({"project": str(self.base / "missing")})["code"], "PROJECT_NOT_FOUND")
        self.assertEqual(self.present({"note": 5})["code"], "INVALID_ARGUMENTS")

    def test_present_never_reaches_the_engine_or_a_device(self):
        root = make_project(self.base)
        seen, connect = self.lane_client(root)

        def forbidden(*_args, **_kwargs):
            raise AssertionError("chromatic_present_game must not start the broker or call an engine tool")

        with (
            mock.patch.object(hermes_host, "try_connect", connect),
            mock.patch.object(hermes_host, "ensure_broker", forbidden),
            mock.patch.object(setup_tools.provision, "install_device_cli", forbidden),
        ):
            self.assertTrue(self.present()["ok"])
        self.assertTrue(all(message.get("op") == "activity" and "tool" not in message for message in seen))

    def test_a_subagent_cannot_present(self):
        root = make_project(self.base)
        hermes_host.on_subagent_start(child_session_id="child-1")
        try:
            payload = self.present({"project": str(root)}, session_id="child-1")
        finally:
            hermes_host.on_subagent_stop(child_session_id="child-1")
        self.assertEqual(payload["code"], "PARENT_ONLY")

    def test_the_approval_hook_lets_present_through_even_with_hardware_on(self):
        hook = registered_hook("pre_tool_call", self.ctx)  # hardware_enabled is True in this ctx
        self.assertIsNone(hook(tool_name="chromatic_present_game", args={"note": "try it"}))
        self.assertEqual(hook(tool_name="chromatic_flash", args={})["action"], "approve")

    def test_the_present_tool_is_plugin_owned_not_an_engine_tool(self):
        from backend.hermes import contracts

        names = {schema["name"] for schema in contracts.hermes_schemas()}
        self.assertNotIn("chromatic_present_game", names)
        self.assertNotIn("present_game", {tool["name"] for tool in contracts.pinned_tools()})
        schema = library_tools.PRESENT_TOOL
        self.assertEqual(schema["name"], "chromatic_present_game")
        self.assertEqual(set(schema["parameters"]["properties"]), {"note", "project"})
        self.assertNotIn("required", schema["parameters"])

    def test_presentations_since(self):
        root = make_project(self.base)
        registry = games.Registry(paths.library_dir())
        first = registry.present(str(root), note="one")["presentation"]
        second = registry.present(str(root), note=None)["presentation"]
        rpc = library_rpcs.rpc_presentations(self.ctx)
        answer = rpc({"since": first["t"]})
        self.assertEqual([item["t"] for item in answer["presentations"]], [second["t"]])
        self.assertGreaterEqual(answer["now"], second["t"])
        self.assertEqual(len(rpc({})["presentations"]), 2)
        self.assertEqual(len(rpc({"since": "bad"})["presentations"]), 2)
        registry.upsert(str(root))  # other writes keep the presentations
        self.assertEqual(len(registry.presentations()), 2)

    def test_thumb_rpc_stores_and_refuses(self):
        root = make_project(self.base)
        identifier = games.Registry(paths.library_dir()).upsert(str(root))["id"]
        thumb = library_rpcs.rpc_game_thumb(self.ctx)
        self.assertEqual(
            thumb({"id": identifier, "png": "data:image/png;base64," + base64.b64encode(PNG).decode()}), {"ok": True}
        )
        self.assertFalse(thumb({"id": "000000000000", "png": "x"})["ok"])
        self.assertFalse(thumb({"id": identifier, "png": "data:image/png;base64,!!"})["ok"])
        self.assertTrue(library_rpcs.rpc_games(self.ctx)({})["games"][0]["thumb"].startswith("data:image/png"))


if __name__ == "__main__":
    unittest.main()
