"""Art import, sprite palettes and previews on project B (top-down, color) through the real engine."""

import json
import struct
from pathlib import Path

from tests.acceptance.fixture import OWNER_B, structured
from tests.support import encode_png

LIGHT, MIDDLE, DARK, CLEAR = (224, 248, 207, 255), (134, 192, 108, 255), (7, 24, 33, 255), (101, 255, 0, 255)
BACKGROUND = [(224, 248, 207, 255), (134, 192, 108, 255), (48, 104, 80, 255), (7, 24, 33, 255)]


def coin(x, y):
    return DARK if x in (0, 15) or y in (0, 15) else (MIDDLE if (x + y) % 2 else LIGHT)


def boss(x, y):
    """Two 32 x 32 frames whose top-left 8 x 16 tile is blank."""
    return CLEAR if x % 32 < 8 and y < 16 else (DARK if (x + y) % 3 == 0 else LIGHT)


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def sidecar(root: Path, asset: str) -> dict:
    return json.loads((root / f"{asset}.gbsres").read_text())


def tiles(metadata: dict) -> list[dict]:
    return [
        tile
        for state in metadata["states"]
        for animation in state["animations"]
        for frame in animation["frames"]
        for tile in frame["tiles"]
    ]


def call(client, tool, arguments):
    return structured(client.call(OWNER_B, tool, arguments))


def check_art_import(suite, client_b):
    root = suite.project_b
    art = root / "art"
    art.mkdir()
    (art / "coin.png").write_bytes(encode_png(16, 16, coin))
    (art / "boss.png").write_bytes(encode_png(64, 32, boss))
    (art / "field.png").write_bytes(encode_png(160, 144, lambda x, y: BACKGROUND[(x // 8 + y // 8) % 4]))
    (art / "wide.png").write_bytes(encode_png(24, 16, lambda x, y: LIGHT))
    scene_id = call(client_b, "project_inventory", {})["scenes"][0]["id"]

    grid = call(client_b, "engine_field_update", {"updates": [{"id": "topdown_grid", "value": 16}]})
    imported = call(
        client_b,
        "asset_import",
        {
            "assets": [
                {
                    "assetPath": "assets/sprites/coin.png",
                    "kind": "sprite",
                    "sourcePath": "art/coin.png",
                    "sprite": {"profile": "static", "paletteIndex": 3},
                },
                {
                    "assetPath": "assets/sprites/boss.png",
                    "kind": "sprite",
                    "sourcePath": "art/boss.png",
                    "sprite": {"profile": "metasprite", "frameWidth": 32, "frameHeight": 32},
                },
                {"assetPath": "assets/backgrounds/field.png", "kind": "background", "sourcePath": "art/field.png"},
            ]
        },
    )
    results = {item.get("name"): item for item in imported.get("imported", [])}
    coin_meta = sidecar(root, "assets/sprites/coin.png")
    boss_meta = sidecar(root, "assets/sprites/boss.png")
    boss_frames = boss_meta["states"][0]["animations"][0]["frames"]
    suite.check(
        "A1",
        "Several assets import in one call with their palette slot, collision box and graphics analysis",
        grid.get("count") == 1
        and imported.get("count") == 3
        and results["coin"]["bounds"] == {"x": 0, "y": -8, "width": 16, "height": 16}
        and {tile["paletteIndex"] for tile in tiles(coin_meta)} == {3}
        and results["boss"]["canvas"] == {"width": 32, "height": 32}
        and results["boss"]["bounds"] == {"x": -8, "y": -24, "width": 32, "height": 32}
        and [len(frame["tiles"]) for frame in boss_frames] == [7, 7]
        and all(item["analysis"]["status"] == "valid" for item in results.values())
        and "tileBudget" in results["field"]["analysis"],
        imported=imported,
        boss_frames=[
            [(tile["x"], tile["y"], tile["sliceX"], tile["sliceY"]) for tile in f["tiles"]] for f in boss_frames
        ],
    )

    refused = client_b.call(
        OWNER_B,
        "asset_import",
        {
            "assets": [
                {
                    "assetPath": "assets/sprites/coin2.png",
                    "kind": "sprite",
                    "sourcePath": "art/coin.png",
                    "sprite": {"profile": "static"},
                },
                {
                    "assetPath": "assets/sprites/wide.png",
                    "kind": "sprite",
                    "sourcePath": "art/wide.png",
                    "sprite": {"profile": "static"},
                },
            ]
        },
    )
    refusal = structured(refused)
    suite.check(
        "A2",
        "A batch with one unusable asset imports none of them and names the entry",
        refusal.get("code") == "INVALID_SPRITE_DIMENSIONS"
        and "assets[1]" in str(refusal.get("error"))
        and not (root / "assets/sprites/coin2.png").exists()
        and not (root / "assets/sprites/coin2.png.gbsres").exists(),
        refusal=refusal,
    )

    hero = call(client_b, "palette_create", {"name": "Hero", "colors": ["#F8F8F8", "#E08040", "#202020"]})
    hero_id = hero.get("palette", {}).get("id")
    assigned = call(
        client_b, "palette_assign", {"sceneId": scene_id, "target": "sprite", "slot": 3, "paletteId": hero_id}
    )
    four = call(client_b, "palette_create", {"name": "Four", "colors": ["#F8F8F8", "#E08040", "#00F000", "#202020"]})
    warned = call(
        client_b,
        "palette_assign",
        {"sceneId": scene_id, "target": "sprite", "slot": 4, "paletteId": four.get("palette", {}).get("id")},
    )
    suite.check(
        "A3",
        "A sprite palette takes three colors, and a sprite slot reports the colors sprites show",
        hero.get("palette", {}).get("colors") == ["F8F8F8", "E08040", "805030", "202020"]
        and assigned.get("spriteColors") == ["F8F8F8", "E08040", "202020"]
        and assigned.get("warnings") == []
        and len(warned.get("warnings", [])) == 1
        and "#00F000" in warned["warnings"][0],
        hero=hero,
        assigned=assigned,
        warned=warned,
    )

    plain = call(
        client_b, "sprite_preview", {"assetPath": "assets/sprites/coin.png", "outputPath": "artifacts/coin.png"}
    )
    painted = call(
        client_b,
        "sprite_preview",
        {
            "assetPath": "assets/sprites/coin.png",
            "outputPath": "artifacts/coin-hero.png",
            "paletteId": hero_id,
            "colorCorrection": "chromatic",
        },
    )
    sheet = call(
        client_b, "sprite_contact_sheet", {"assetPath": "assets/sprites/boss.png", "outputPath": "artifacts/boss.png"}
    )
    scene = call(
        client_b,
        "graphics_preview_scene",
        {"sceneId": scene_id, "outputPath": "artifacts/scene.png", "colorCorrection": "chromatic"},
    )
    suite.check(
        "A4",
        "Previews are enlarged by default and draw a palette's sprite colors and the Chromatic's display",
        (plain.get("scale"), plain.get("width")) == (8, 128)
        and painted.get("colorCorrection") == "chromatic"
        and painted.get("sha256") not in (None, plain.get("sha256"))
        and (sheet.get("scale"), sheet.get("frameCount")) == (2, 2)
        and (scene.get("magnification"), scene.get("colorCorrection")) == (2, "chromatic")
        and png_size(root / "artifacts/scene.png") == (320, 288),
        plain=plain,
        painted=painted,
        sheet=sheet,
        scene=scene,
    )

    placed = call(
        client_b,
        "scene_apply",
        {
            "sceneId": scene_id,
            "operations": [
                {"type": "actor.create", "name": "Boss", "x": 8, "y": 8, "spriteSheetId": results["boss"]["id"]},
                {"type": "actor.create", "name": "Coin", "x": 4, "y": 4, "spriteSheetId": results["coin"]["id"]},
            ],
        },
    )
    built = call(client_b, "rom_build", {})
    suite.check(
        "A5",
        "A scene with the imported metasprite and palette-slot sprite builds",
        len(placed.get("operationResults", [])) == 2 and built.get("success") is True,
        placed=placed.get("operationResults"),
        diagnostics=built.get("diagnostics"),
    )
