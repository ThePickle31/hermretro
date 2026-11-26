"""Games installed from a link, on this run's broker and library (no hardware): B's game published twice to local git
repositories, without its source and with it, and installed through their ``file://`` links. A game without its
source is inspected from its own chat, whose worker has its folder as its workspace, with the size and SHA-256 the
flash tool takes, and plays its checked ROM in the bundled player; a game with its source is built once here and
gives its author's ROM (builds are repeatable), and is inspected from its own chat too."""

import hashlib
import json
import os
import shutil
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from tests.acceptance.fixture import structured
from tests.support import commit_all, git, home_isolation, make_game_folder

OWNER_G = {"profile": "s01-profile", "conversation_id": "conv-installed-game"}
OWNER_H = {"profile": "s01-profile", "conversation_id": "conv-installed-source"}
FLASH_SIZES = range(336, 8 * 1024 * 1024 + 1)  # the flash tool's expectedSizeBytes


def publish(suite, name: str, rom: bytes, *, source: bool) -> str:
    """B's game as its author would publish it, in a git repository of its own: its ``file://`` link."""
    repo = suite.work / "published" / name
    if source:
        shutil.copytree(
            suite.project_b, repo, ignore=shutil.ignore_patterns("build", "artifacts", "captures", "save-states", ".*")
        )
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    make_game_folder(repo, identifier=hashlib.sha256(name.encode()).hexdigest()[:32], title=name, rom=rom)
    commit_all(repo, "First version")
    return repo.resolve().as_uri()


def check_installed_games(suite, client, rom_b: str):
    from backend.library import game_workers, installs
    from backend.library import rpcs as library_rpcs
    from backend.hermes import host
    from backend.player import server as player_server
    from backend.system import paths

    rom = Path(rom_b).read_bytes()
    with ExitStack() as stack:
        stack.enter_context(home_isolation())
        stack.enter_context(
            mock.patch.dict(
                os.environ,
                {
                    "HERMRETRO_RUNTIME_DIR": str(suite.state),
                    "HERMRETRO_LIBRARY_DIR": str(suite.state),
                    "HERMRETRO_GAMES_DIR": str(suite.work / "installed-games"),
                },
            )
        )
        registry = host._registry()
        workers = game_workers.BrokerWorkers()

        def install(link, *, allow_build=False):
            found = installs.inspect(link, registry=registry, allow_local=True)
            done = installs.install(
                found["source"],
                found["commit"],
                workers=workers,
                registry=registry,
                games_dir=paths.games_dir(create=True),
                allow_local=True,
                allow_build=allow_build,  # the user's consent to build a game with its source here
            )
            root = Path(done["root"])
            return root, registry.game_for_root(str(root))["id"], done

        game_root, game_id, _done = install(publish(suite, "Installed Rom", rom, source=False))
        registry.bind(game_id, OWNER_G["conversation_id"], OWNER_G["profile"])
        source_root, source_id, source_done = install(
            publish(suite, "Installed Source", rom, source=True), allow_build=True
        )
        registry.bind(source_id, OWNER_H["conversation_id"], OWNER_H["profile"])

        checked = installs.release.installed_rom(game_root) or {}
        inspected = structured(client.call(OWNER_G, "rom_inspect", {"romPath": checked.get("romPath", "")}))
        suite.check(
            "IN1",
            "A game installed without its source is inspected from its own chat (its folder the worker's workspace), "
            "with the size and SHA-256 the flash tool takes, equal to its install's",
            inspected.get("sha256") == checked.get("sha256") == hashlib.sha256(rom).hexdigest()
            and inspected.get("sizeBytes") == len(rom)
            and len(rom) in FLASH_SIZES,
            inspected={k: inspected.get(k) for k in ("sha256", "sizeBytes", "error", "code")},
        )
        edit = client.call(OWNER_G, "variable_set", {"name": "x", "value": 1})
        suite.check(
            "IN2",
            "Nothing edits a game installed without its source, even from its own chat",
            (edit.get("denied") or {}).get("code") == "INSTALLED_WITHOUT_SOURCE",
            answer=edit.get("denied") or edit.get("error"),
        )

        ctx = mock.Mock()
        ctx.get_config.return_value = False
        played = library_rpcs.rpc_player(ctx)({"id": game_id})
        base = (played.get("url") or "")[: -len("index.html")]
        try:
            with urllib.request.urlopen(base + "gbstudio.json", timeout=10) as config:
                named = json.loads(config.read())["rom"]
            with urllib.request.urlopen(base + named, timeout=10) as served:
                served_sha = hashlib.sha256(served.read()).hexdigest()
        except Exception as error:  # noqa: BLE001 - the check reports what failed
            named, served_sha = None, str(error)
        finally:
            if player_server._server is not None:
                player_server._server.close()
                player_server._server = None
        suite.check(
            "IN3",
            "A game installed without its source plays its checked ROM in the bundled player",
            played.get("ok") is True and served_sha == checked.get("sha256"),
            player={k: played.get(k) for k in ("ok", "error", "romSha256")},
            rom=named,
        )

        # The install itself built it (the user allowed it): its receipt, as install.json keeps it.
        receipt = (installs.release.installed(source_root) or {}).get("testBuild") or {}
        record = installs.release.installed(source_root) or {}
        inspected = structured(
            client.call(OWNER_H, "rom_inspect", {"romPath": str(source_root / "build" / "game.gbc")})
        )
        suite.check(
            "IN4",
            "A game installed with its source, allowed to build, is built once by its install to the ROM it was "
            "installed with, recorded for that commit, and its own chat inspects it",
            (source_done.get("testBuild") or {}).get("built") is True
            and receipt.get("matches") is True
            and receipt.get("commit") == record.get("commit")
            and receipt.get("sha256") == hashlib.sha256(rom).hexdigest()
            and inspected.get("sha256") == hashlib.sha256(rom).hexdigest(),
            install=source_done.get("testBuild"),
            receipt=receipt,
            inspected=inspected.get("sha256") or inspected.get("error"),
        )
        client.call(OWNER_G, "emulator_close")
