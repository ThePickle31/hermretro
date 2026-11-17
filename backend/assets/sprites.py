"""How a GB Studio project shows its sprites and backgrounds: animations, palettes and the scenes that use
them, read from the project's sidecar files for the asset viewer and thumbnails. Re-exported by
backend.hermes.host."""
from __future__ import annotations

import json
from pathlib import Path

from ..hermes import host

logger = host.logger   # one logger for the Hermes side of the backend, as before the split

# GB Studio's animation slots, by sprite type (the compiler's order).
_ANIMATION_NAMES = {
    "fixed": ["Idle"],
    "fixed_movement": ["Idle", None, None, None, "Moving"],
    "multi": ["Right", "Left", "Up", "Down"],
    "multi_movement": ["Idle right", "Idle left", "Idle up", "Idle down", "Walk right", "Walk left", "Walk up", "Walk down"],
    "horizontal": ["Right", "Left"],
    "horizontal_movement": ["Idle right", "Idle left", None, None, "Walk right", "Walk left"],
    "platform_player": ["Idle right", "Idle left", "Run right", "Run left", "Jump right", "Jump left", "Climb", "Climb idle"],
    "cursor": ["Idle", "Hover"],
}
# The slot an actor facing each way shows when it stands still.
_FACING_SLOT = {"multi": {"right": 0, "left": 1, "up": 2, "down": 3},
                "multi_movement": {"right": 0, "left": 1, "up": 2, "down": 3},
                "horizontal": {"right": 0, "left": 1}, "horizontal_movement": {"right": 0, "left": 1},
                "platform_player": {"right": 0, "left": 1}}
_ASSET_INFO_SCENES = 6
_ASSET_INFO_ACTORS = 40


def _read_json(path: Path, limit: int = 4 * 1024 * 1024):
    try:
        if path.is_file() and path.stat().st_size <= limit:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        pass
    return None


def _tiles(frame) -> list[dict]:
    tiles = []
    for tile in (frame or {}).get("tiles") or []:
        if isinstance(tile, dict):
            tiles.append({key: tile.get(key) for key in ("x", "y", "sliceX", "sliceY", "flipX", "flipY")})
    return tiles


def _sprite_animations(meta: dict) -> dict:
    """The first sprite state's animations, named the way GB Studio names its slots. A left slot left
    empty with ``flipLeft`` is drawn as the right one mirrored."""
    states = [state for state in meta.get("states") or [] if isinstance(state, dict)]
    state = states[0] if states else {}
    kind = str(state.get("animationType") or "fixed")
    names = _ANIMATION_NAMES.get(kind, [])
    animations = []
    for index, animation in enumerate(state.get("animations") or []):
        frames = [_tiles(frame) for frame in (animation or {}).get("frames") or [] if isinstance(frame, dict)]
        name = names[index] if index < len(names) else None
        animations.append({"slot": index, "name": name or f"Animation {index + 1}", "frames": frames[:64]})
    return {"name": meta.get("name"), "id": meta.get("id"), "type": kind, "flipLeft": bool(state.get("flipLeft")),
            "states": [str(item.get("name") or "") for item in states],
            "canvasWidth": int(meta.get("canvasWidth") or 16), "canvasHeight": int(meta.get("canvasHeight") or 16),
            "animSpeed": meta.get("animSpeed"), "numTiles": meta.get("numTiles"), "animations": animations}


def _standing_frame(sprite: dict, direction: str) -> dict:
    """The tiles an actor shows standing still, facing ``direction``, and whether they are mirrored."""
    animations = sprite.get("animations") or []
    facing = _FACING_SLOT.get(str(sprite.get("type") or ""), {})
    slot = facing.get(direction or "down", 0)

    def first(index):
        frames = animations[index]["frames"] if 0 <= index < len(animations) else []
        return frames[0] if frames else []

    if not first(slot) and direction == "left" and sprite.get("flipLeft"):
        return {"tiles": first(facing.get("right", 0)), "flip": True}
    return {"tiles": first(slot) or first(0), "flip": False}


def _project_index(root: Path) -> dict:
    """Sprites, backgrounds, palettes, scenes and settings of a distributed GB Studio project."""
    resources = root / "project"
    index = {"sprites": {}, "backgrounds": {}, "palettes": {}, "scenes": [], "settings": _read_json(resources / "settings.gbsres") or {}}
    for folder, key in (("sprites", "sprites"), ("backgrounds", "backgrounds")):
        for sidecar in sorted((root / "assets" / folder).glob("*.gbsres")):
            meta = _read_json(sidecar)
            if meta and meta.get("id"):
                index[key][meta["id"]] = {"meta": meta, "path": sidecar.with_name(sidecar.name[: -len(".gbsres")])}
    for sidecar in sorted((resources / "palettes").glob("*.gbsres")):
        meta = _read_json(sidecar)
        if meta and meta.get("id") and isinstance(meta.get("colors"), list):
            index["palettes"][meta["id"]] = meta
    for scene_file in sorted((resources / "scenes").glob("*/scene.gbsres")):
        scene = _read_json(scene_file)
        if not scene:
            continue
        actors = [actor for actor in (_read_json(item) for item in sorted((scene_file.parent / "actors").glob("*.gbsres"))) if actor]
        scene["_actors"] = actors
        index["scenes"].append(scene)
    index["scenes"].sort(key=lambda scene: (scene.get("_index", 0) if isinstance(scene.get("_index"), int) else 0))
    return index


def _palette(index: dict, palette_id) -> dict | None:
    palette = index["palettes"].get(palette_id) if palette_id else None
    if not palette:
        return None
    colors = [f"#{str(color).lstrip('#')}" for color in palette.get("colors") or []][:4]
    return {"id": palette_id, "name": palette.get("name") or "", "colors": colors} if len(colors) == 4 else None


def _player_sprite_id(settings: dict, scene: dict):
    return scene.get("playerSpriteSheetId") or (settings.get("defaultPlayerSprites") or {}).get(scene.get("type")) \
        or settings.get("playerSpriteSheetId")


def _actor_palette(index: dict, scene: dict, palette_id) -> dict | None:
    settings = index["settings"]
    scene_palettes = [item for item in scene.get("spritePaletteIds") or [] if item]
    return _palette(index, palette_id) or _palette(index, scene_palettes[0] if scene_palettes else None) \
        or _palette(index, settings.get("defaultSpritePaletteId")) \
        or _palette(index, (settings.get("defaultSpritePaletteIds") or [None])[0])


def _scene_view(index: dict, scene: dict, sprites_cache: dict) -> dict:
    """What a scene draws: its background, and each actor's standing frame at its place (the player at
    the start position in the start scene)."""
    settings = index["settings"]
    background = index["backgrounds"].get(scene.get("backgroundId"))
    actors = []

    def add(name, sprite_id, x, y, direction, palette_id, player=False):
        entry = index["sprites"].get(sprite_id)
        if not entry or len(actors) >= _ASSET_INFO_ACTORS:
            return
        sprite = sprites_cache.setdefault(sprite_id, _sprite_animations(entry["meta"]))
        actors.append({"name": name, "spriteId": sprite_id, "sprite": str(entry["path"]), "x": x, "y": y, "player": player,
                       "canvasWidth": sprite["canvasWidth"], "canvasHeight": sprite["canvasHeight"],
                       **_standing_frame(sprite, direction), "palette": _actor_palette(index, scene, palette_id)})

    if scene.get("id") and scene.get("id") == settings.get("startSceneId"):
        add("Player", _player_sprite_id(settings, scene), settings.get("startX", 0), settings.get("startY", 0),
            settings.get("startDirection") or "down", settings.get("playerPaletteId"), player=True)
    for actor in scene.get("_actors") or []:
        add(actor.get("name") or "Actor", actor.get("spriteSheetId"), actor.get("x", 0), actor.get("y", 0),
            actor.get("direction") or "down", actor.get("paletteId"))
    return {"id": scene.get("id"), "name": scene.get("name") or "Scene", "width": scene.get("width"), "height": scene.get("height"),
            "background": str(background["path"]) if background else None, "actors": actors}


_SPRITE_USES: dict[str, tuple] = {}
_SPRITE_USES_ROOTS = 16
# The animation that plays while an actor moves, from the slot it stands in (GB Studio's slot order).
_MOVING_OFFSET = {"multi_movement": 4, "horizontal_movement": 4, "platform_player": 2}


def _project_stamp(root: Path) -> tuple:
    """What a sprite's look depends on besides its own sidecar: settings, palettes, scenes and actors."""
    resources = root / "project"
    files = [resources / "settings.gbsres", *resources.glob("palettes/*.gbsres"), *resources.glob("scenes/*/scene.gbsres"),
             *resources.glob("scenes/*/actors/*.gbsres"), *(root / "assets" / "sprites").glob("*.gbsres")]
    stamp = []
    for item in files:
        try:
            stamp.append((str(item), item.stat().st_mtime_ns))
        except OSError:
            continue
    return tuple(sorted(stamp))


def _sprite_uses(root: Path) -> dict:
    """For each sprite of a project: how its first use in the game shows it (facing, palette), and the
    palette a sprite nobody uses yet would get. Cached per project until one of its files changes."""
    stamp = _project_stamp(root)
    cached = _SPRITE_USES.get(str(root))
    if cached and cached[0] == stamp:
        return cached[1]
    index = _project_index(root)
    settings = index["settings"]
    uses = {}
    for scene in index["scenes"]:
        candidates = []
        if scene.get("id") and scene.get("id") == settings.get("startSceneId"):
            candidates.append((_player_sprite_id(settings, scene), settings.get("startDirection"), settings.get("playerPaletteId")))
        for actor in scene.get("_actors") or []:
            candidates.append((actor.get("spriteSheetId"), actor.get("direction"), actor.get("paletteId")))
        for sprite_id, direction, palette_id in candidates:
            if sprite_id and sprite_id not in uses:
                uses[sprite_id] = {"direction": direction or "down", "palette": _actor_palette(index, scene, palette_id)}
    result = {"uses": uses, "default": _actor_palette(index, {}, None)}
    if len(_SPRITE_USES) >= _SPRITE_USES_ROOTS:
        _SPRITE_USES.pop(next(iter(_SPRITE_USES)))
    _SPRITE_USES[str(root)] = (stamp, result)
    return result


def _sprite_look(root: Path, meta: dict) -> dict:
    """How the game shows a sprite, for thumbnails: the palette it is painted with, the tiles of the
    frame it stands in (facing the way its first use faces) and the frames it moves with."""
    try:
        sprite = _sprite_animations(meta)
        found = _sprite_uses(root)
        use = found["uses"].get(meta.get("id")) or {}
        palette = use.get("palette") or found["default"]
        direction = use.get("direction") or "down"
        standing = _standing_frame(sprite, direction)
        animations = sprite.get("animations") or []
        facing = _FACING_SLOT.get(sprite.get("type") or "", {})
        slot = facing.get(direction, 0) + _MOVING_OFFSET.get(sprite.get("type") or "", 0)
        if sprite.get("type") == "fixed_movement":
            slot = 4
        moving = animations[slot]["frames"] if 0 <= slot < len(animations) else []
        moving_flip = False
        if not any(moving) and direction == "left" and sprite.get("flipLeft"):
            right = facing.get("right", 0) + _MOVING_OFFSET.get(sprite.get("type") or "", 0)
            moving, moving_flip = (animations[right]["frames"] if 0 <= right < len(animations) else []), True
        return {"canvasWidth": sprite["canvasWidth"], "canvasHeight": sprite["canvasHeight"],
                "palette": palette["colors"] if palette else None,
                "standing": standing,
                "moving": {"frames": [frame for frame in moving if frame][:16], "flip": moving_flip}}
    except Exception:
        logger.debug("hermretro could not work out how a sprite looks", exc_info=True)
        return {}
