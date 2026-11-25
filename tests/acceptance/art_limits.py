"""Art import as GB Studio compiles it, on project B (top-down, color, 16 px grid) after art.py: rollback,
sprite mode, tile accounting, scene types, palettes, native metadata and preview sizes, through the real engine."""

import hashlib
import json
import os

from tests.acceptance.art import BACKGROUND, CLEAR, DARK, LIGHT, MIDDLE, call, coin, sidecar
from tests.acceptance.fixture import OWNER_B, structured
from tests.support import encode_png


def mirrored(x, y):
    """One 32 x 16 frame, left-right symmetric: its right half is its left half flipped (two distinct tiles)."""
    x = min(x, 31 - x)
    return DARK if x == 0 or (x == 9 and y < 4) else (MIDDLE if x % 3 else LIGHT)


def sparse(x, y):
    """One 96 x 16 frame whose every third 8-pixel column is blank: 8 objects across, not 12."""
    return CLEAR if (x // 8) % 3 == 2 else LIGHT


def blink(x, y):
    """Three 16 x 16 frames, the middle one blank."""
    return CLEAR if 16 <= x < 32 else coin(x % 16, y)


def crowd(x, y):
    """Seven 64 x 64 frames whose 8 x 16 tiles all differ: more than a Color Only scene's 192."""
    return (LIGHT, MIDDLE, DARK)[hashlib.sha256(f"{x},{y}".encode()).digest()[0] % 3]


def sprite(path, profile, **options):
    return {"assetPath": f"assets/sprites/{path}.png", "kind": "sprite", "sourcePath": f"art/{path}.png",
            "sprite": {"profile": profile, **options}}  # fmt: skip


def check_art_limits(suite, client_b):
    root = suite.project_b
    art = root / "art"
    for name, size, draw in (
        ("mirrored", (32, 16), mirrored),
        ("sparse", (96, 16), sparse),
        ("blink", (48, 16), blink),
        ("crowd", (448, 64), crowd),
        ("walker", (96, 16), lambda x, y: coin(x % 16, y)),
        ("big", (1000, 1000), lambda x, y: BACKGROUND[0]),
    ):
        (art / f"{name}.png").write_bytes(encode_png(*size, draw))
    check_rollback(suite, client_b, root)

    coin_id = call(client_b, "asset_inspect", {"assetPath": "assets/sprites/coin.png"}).get("id")
    imported = call(
        client_b,
        "asset_import",
        {
            "assets": [
                sprite("mirrored", "metasprite", frameWidth=32, frameHeight=16),
                sprite("sparse", "metasprite", frameWidth=96, frameHeight=16),
                sprite("blink", "metasprite", frameWidth=16, frameHeight=16),
                {**sprite("walker", "directional_animated", sceneType="PLATFORM"), "background": {}},
                {
                    **sprite("walker", "directional_animated", templateAssetId=coin_id),
                    "assetPath": "assets/sprites/walker2.png",
                },
            ]
        },
    )
    results = {item.get("name"): item for item in imported.get("imported", [])}
    crowded = structured(
        client_b.call(OWNER_B, "asset_import", sprite("crowd", "metasprite", frameWidth=64, frameHeight=64))
    )
    sheet = call(
        client_b, "sprite_contact_sheet", {"assetPath": "assets/sprites/blink.png", "outputPath": "artifacts/blink.png"}
    )
    suite.check(
        "A7",
        "Imports count tiles as GB Studio compiles them, warn on full rows only, scope the grid box to top-down "
        "sprites, ignore options other profiles use, and the sheet keeps a blank frame",
        imported.get("count") == 5
        and results["mirrored"]["numTiles"] == sidecar(root, "assets/sprites/mirrored.png")["numTiles"] == 2
        and "diagnostics" not in results["sparse"]
        and results["mirrored"]["analysis"]["tileBudget"]["used"] == 4
        and results["walker"]["bounds"] == {"x": 0, "y": 0, "width": 16, "height": 8}
        and results["walker2"]["bounds"] == {"x": 0, "y": -8, "width": 16, "height": 16}
        and crowded.get("code") == "SPRITE_TILE_LIMIT"
        and not (root / "assets/sprites/crowd.png").exists()
        and sheet.get("frameCount") == 3,
        imported=imported,
        crowded=crowded,
        sheet=sheet,
    )

    check_sprite_mode(suite, client_b, root)
    check_palette_and_native_metadata(suite, client_b, root)
    check_scene_sheet(suite, client_b)


def check_rollback(suite, client_b, root):
    """A batch that fails while writing (a folder it cannot write into) removes what it already wrote."""
    if os.geteuid() == 0:
        return  # root writes into a read-only folder
    locked = root / "assets/sprites/locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        failed = structured(
            client_b.call(
                OWNER_B,
                "asset_import",
                {
                    "assets": [
                        sprite("kept", "static"),
                        {**sprite("kept", "static"), "assetPath": "assets/sprites/locked/kept.png"},
                    ]
                },
            )
        )
    finally:
        locked.chmod(0o755)
    suite.check(
        "A6",
        "A batch that fails while writing leaves none of its files behind",
        bool(failed.get("error") or failed.get("code"))
        and not (root / "assets/sprites/kept.png").exists()
        and not (root / "assets/sprites/kept.png.gbsres").exists()
        and not any(locked.iterdir()),
        failed=failed,
    )


def check_sprite_mode(suite, client_b, root):
    """A project in 8 x 8 sprite mode refuses generated profiles: GB Studio would compile half of each tile.
    The settings change behind the engine's back, so each edit is followed by a strong refresh, as an editor's
    change would be: the engine's file watcher reports it later on macOS, after the next calls have run."""
    settings = root / "project" / "settings.gbsres"
    original = settings.read_bytes()
    settings.write_text(json.dumps({**json.loads(original), "spriteMode": "8x8"}, indent=2) + "\n")
    try:
        call(client_b, "project_refresh", {"mode": "strong"})
        eight = {**sprite("coin", "static"), "assetPath": "assets/sprites/eight.png"}
        refused = structured(client_b.call(OWNER_B, "asset_import", eight))
    finally:
        settings.write_bytes(original)
        call(client_b, "project_refresh", {"mode": "strong"})
    suite.check(
        "A8",
        "Generated sprite profiles refuse a project in 8 x 8 sprite mode",
        refused.get("code") == "SPRITE_MODE_UNSUPPORTED",
        refused=refused,
    )


def check_palette_and_native_metadata(suite, client_b, root):
    shared = call(
        client_b, "palette_create", {"name": "Shared", "colors": ["#F8F8F8", "#E08040", "#00F000", "#202020"]}
    )
    updated = call(
        client_b,
        "palette_update",
        {"paletteId": shared.get("palette", {}).get("id"), "colors": ["#FFFFFF", "#808080", "#000000"]},
    )

    art = root / "art"
    (art / "native.png").write_bytes((root / "assets/sprites/coin.png").read_bytes())
    (art / "native.json").write_bytes((root / "assets/sprites/coin.png.gbsres").read_bytes())
    native = {
        "assetPath": "assets/sprites/native.png",
        "kind": "sprite",
        "sourcePath": "art/native.png",
        "sprite": {
            "profile": "native_metadata",
            "metadataPath": "art/native.json",
            "sourceSha256": hashlib.sha256((art / "native.png").read_bytes()).hexdigest(),
            "metadataSha256": hashlib.sha256((art / "native.json").read_bytes()).hexdigest(),
        },
    }
    revision = call(client_b, "project_inspect", {}).get("revision")
    dry = call(client_b, "asset_import", {**native, "expectedRevision": revision, "dryRun": True, "detail": "full"})
    real = call(client_b, "asset_import", {**native, "expectedRevision": revision})
    suite.check(
        "A9",
        "A three-color update keeps the palette's entry 2, and native_metadata imports return the analysis, with "
        "the ID map only in full",
        updated.get("palette", {}).get("colors") == ["FFFFFF", "808080", "00F000", "000000"]
        and dry.get("analysis", {}).get("status") == "valid"
        and real.get("analysis", {}).get("status") == "valid"
        and len(dry.get("idMap") or []) == dry.get("counts", {}).get("ids", 0) > 0
        and not {"idMap", "patternAccounting"} & set(real)
        and real.get("counts", {}).get("ids") == dry.get("counts", {}).get("ids"),
        updated=updated,
        dry=dry,
        real=real,
    )


def check_scene_sheet(suite, client_b):
    """A sheet whose 2x enlargement would pass the renderer's pixel limit (one 1000 x 1000 scene sets the size of
    all nine cards) is drawn at 1x by default instead of failing."""
    big = call(
        client_b,
        "asset_import",
        {"assetPath": "assets/backgrounds/big.png", "kind": "background", "sourcePath": "art/big.png"},
    )
    field = call(client_b, "asset_inspect", {"assetPath": "assets/backgrounds/field.png"}).get("id")
    scenes = [
        call(client_b, "scene_create", {"name": "Big", "width": 125, "height": 125, "backgroundId": big.get("id")})
    ]
    scenes += [call(client_b, "scene_create", {"name": f"Small {n}", "backgroundId": field}) for n in range(8)]
    sheet = call(
        client_b,
        "graphics_preview_scene",
        {"sceneIds": [scene.get("scene", {}).get("id") for scene in scenes], "outputPath": "artifacts/scenes.png"},
    )
    suite.check(
        "A10",
        "A scene sheet too large to enlarge is drawn at 1x by default",
        sheet.get("magnification") == 1 and sheet.get("sceneCount") == 9,
        sheet=sheet,
        scenes=[scene.get("scene", {}).get("id") for scene in scenes],
    )
