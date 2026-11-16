"""Game images for the Build page: the asset, asset_info, asset_restore and assets RPCs, the kept
versions of each image and the hooks that keep them. Re-exported by hermes_host."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from . import game_card, hermes_host as host

logger = host.logger   # one logger for the host adapter, as before the split

# Shared helpers (the data folder, the profile, the library, the broker client) stay in hermes_host and are
# looked up there at call time, so one patch of hermes_host.<name> reaches every module.

ASSET_SUFFIXES = {".png": "image/png", ".gif": "image/gif", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
ASSET_MAX_BYTES = 6 * 1024 * 1024


def _image_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG, GIF or JPEG header; (0, 0) when unknown."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                break
            marker, length = data[index + 1], int.from_bytes(data[index + 2:index + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(data[index + 7:index + 9], "big"), int.from_bytes(data[index + 5:index + 7], "big")
            index += 2 + length
    return 0, 0


def _asset_kind(relative: str | None) -> str:
    parts = (relative or "").split("/")
    if parts[:2] == ["assets", "sprites"]:
        return "sprite"
    if parts[:2] == ["assets", "backgrounds"]:
        return "background"
    if parts[:2] == ["assets", "ui"] or parts[:2] == ["assets", "fonts"]:
        return "ui"
    if "playtests" in parts or "frames" in parts:
        return "frame"
    if "captures" in parts:
        return "capture"
    return "image"


ASSET_KEEP_VERSIONS = 40
# A line of a reply that delivers a file (``MEDIA:/path``), quotes or backticks allowed around the path.
_MEDIA_LINE = re.compile(r"^[ \t]*MEDIA:[ \t]*([`\"']?)(.+?\.(?:png|gif|jpe?g|webp))\1[ \t]*$", re.IGNORECASE | re.MULTILINE)


def _asset_roots() -> list[Path]:
    roots = [(host._data_dir() / "frames").resolve()]
    for game in host._registry().library():
        try:
            roots.append(Path(game["projectRoot"]).resolve())
        except (KeyError, OSError, RuntimeError):
            continue
    return roots


def _asset_file(raw) -> tuple[Path, Path] | None:
    """The real file and the root it is shown from, for an image inside a library game or the saved
    frames; None for anything else."""
    raw = str(raw or "")
    if raw.startswith("file://"):
        raw = raw[len("file://"):]
    candidate = Path(raw).expanduser()
    # Cheap checks first: this runs after every tool call.
    if not raw or not candidate.is_absolute() or candidate.suffix.lower() not in ASSET_SUFFIXES:
        return None
    try:
        real = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if real.suffix.lower() not in ASSET_SUFFIXES or not real.is_file():
        return None
    root = next((base for base in _asset_roots() if real == base or base in real.parents), None)
    return (real, root) if root is not None else None


def _versions_dir(real: Path) -> Path:
    return host._data_dir() / "asset-versions" / hashlib.sha256(str(real).encode("utf-8")).hexdigest()[:24]


def _keep_version(real: Path) -> None:
    """Keep this version of a game image (named by its modification time), so a later rewrite of the
    same file (cover.png made again) does not change what an earlier reply showed."""
    try:
        stat = real.stat()
        if stat.st_size > ASSET_MAX_BYTES:
            return
        folder = _versions_dir(real)
        target = folder / f"{stat.st_mtime_ns}{real.suffix.lower()}"
        if target.exists():
            return
        folder.mkdir(parents=True, exist_ok=True)
        data = real.read_bytes()
        kept = sorted(folder.iterdir(), key=lambda item: item.name)
        if kept and kept[-1].read_bytes() == data:
            return
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        for old in kept[: max(0, len(kept) + 1 - ASSET_KEEP_VERSIONS)]:
            old.unlink(missing_ok=True)
    except OSError:
        logger.debug("hermretro could not keep an image version", exc_info=True)


def _version_at(real: Path, at_ms) -> Path | None:
    """The kept version of ``real`` that was current at ``at_ms`` (a reply's time), when the file has
    been rewritten since; None when the file on disk is still that version (or nothing older was kept)."""
    try:
        at_ns = int(float(at_ms) * 1_000_000)
    except (TypeError, ValueError):
        return None
    if at_ns <= 0 or real.stat().st_mtime_ns <= at_ns:
        return None
    folder = _versions_dir(real)
    if not folder.is_dir():
        return None
    older = [item for item in folder.iterdir() if item.suffix != ".part" and item.stem.isdigit() and int(item.stem) <= at_ns]
    return max(older, key=lambda item: int(item.stem)) if older else None


def _keep_paths(values) -> None:
    for value in values:
        if isinstance(value, str) and value:
            found = _asset_file(value)
            if found:
                _keep_version(found[0])


def keep_delivered_images(assistant_response=None, **_kwargs):
    """``post_llm_call``: keep the images a reply delivered (``MEDIA:`` lines), as they are right now."""
    try:
        if isinstance(assistant_response, str) and "MEDIA:" in assistant_response:
            _keep_paths(match.group(2).strip() for match in _MEDIA_LINE.finditer(assistant_response))
    except Exception:
        logger.debug("hermretro keep_delivered_images failed", exc_info=True)


def keep_inspected_images(tool_name=None, args=None, **_kwargs):
    """``post_tool_call``: keep the images a step looked at or wrote, as they are right after it."""
    try:
        if isinstance(args, dict):
            _keep_paths(args.get(key) for key in ("image_url", "image", "assetPath", "outputPath", "path"))
    except Exception:
        logger.debug("hermretro keep_inspected_images failed", exc_info=True)



def rpc_asset(ctx):
    """One image for the Build page (a thumbnail, the asset viewer): only from a library game's folder
    or the frames Hermes saved from tool results. Answers a data URL, its size and, for a sprite, the
    frame size and speed from its sidecar, so the page can animate it. With ``at`` (a reply's time, in
    ms) it answers the version the file had then, when it was kept and the file has changed since."""
    def asset(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            raw = str(params.get("path") or "")
            if raw.startswith("file://"):
                raw = raw[len("file://"):]
            candidate = Path(raw).expanduser()
            if not raw or not candidate.is_absolute():
                return {"ok": False, "code": "INVALID", "error": "An absolute image path is required."}
            real = candidate.resolve(strict=True)
            mime = ASSET_SUFFIXES.get(real.suffix.lower())
            if mime is None or not real.is_file():
                return {"ok": False, "code": "NOT_IMAGE", "error": "Not an image."}
            roots = _asset_roots()
            root = next((base for base in roots if real == base or base in real.parents), None)
            if root is None:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in your games are shown here."}
            size = real.stat().st_size
            if size > ASSET_MAX_BYTES:
                return {"ok": False, "code": "TOO_LARGE", "error": "The image is too large to preview."}
            _keep_version(real)
            earlier = None
            wanted = str(params.get("version") or "")
            if wanted:
                # One kept version by its id (the file's modification time in ns), as the viewer lists them.
                if not wanted.isdigit():
                    return {"ok": False, "code": "INVALID", "error": "Unknown version."}
                if int(wanted) != real.stat().st_mtime_ns:
                    kept = _versions_dir(real) / f"{wanted}{real.suffix.lower()}"
                    if not kept.is_file():
                        return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
                    earlier = kept
            elif params.get("at") is not None:
                earlier = _version_at(real, params.get("at"))
            source = earlier or real
            data = source.read_bytes()
            width, height = _image_size(data)
            relative = real.relative_to(root).as_posix() if root != (host._data_dir() / "frames").resolve() else None
            answer = {"ok": True, "path": str(real), "relative": relative, "name": real.name, "kind": _asset_kind(relative)
                      if relative else "frame", "width": width, "height": height, "bytes": len(data),
                      "modifiedAt": (int(earlier.stem) / 1e9) if earlier else real.stat().st_mtime,
                      "earlier": earlier is not None,
                      "versionId": earlier.stem if earlier else str(real.stat().st_mtime_ns),
                      "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"}
            sidecar = real.with_name(real.name + ".gbsres")
            if answer["kind"] == "sprite" and sidecar.is_file() and sidecar.stat().st_size < 2 * 1024 * 1024:
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                    frame_width, frame_height = int(meta.get("canvasWidth") or 0), int(meta.get("canvasHeight") or 0)
                    if frame_width > 0 and frame_height > 0:
                        answer["sprite"] = {"name": meta.get("name"), "frameWidth": frame_width, "frameHeight": frame_height,
                                            "animSpeed": meta.get("animSpeed")}
                        if isinstance(meta, dict) and meta.get("id"):
                            answer["sprite"].update(_sprite_look(root, meta))
                except (ValueError, TypeError, OSError):
                    pass
            return answer
        except FileNotFoundError:
            return {"ok": False, "code": "MISSING", "error": "The image is gone."}
        except Exception as error:
            logger.exception("hermretro asset failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset


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


def _versions(real: Path) -> list[dict]:
    """Every kept version of a file, oldest first, with the current one marked."""
    folder = _versions_dir(real)
    kept = sorted((item for item in folder.iterdir() if item.stem.isdigit() and item.suffix != ".part"), key=lambda item: int(item.stem)) \
        if folder.is_dir() else []
    current = real.stat().st_mtime_ns
    data = real.read_bytes()
    versions = [{"id": item.stem, "at": int(item.stem) // 1_000_000, "file": str(item), "current": False} for item in kept]
    match = next((entry for entry in reversed(versions) if int(entry["id"]) == current), None)
    if match is None and kept and kept[-1].read_bytes() == data:
        match = versions[-1]
    if match is None:
        versions.append({"id": str(current), "at": current // 1_000_000, "file": str(real), "current": True})
    else:
        match["current"] = True
    return versions


def rpc_asset_info(ctx):
    """What the asset viewer shows beside an image: its kind, every kept version, and for a sprite or
    background its animations, the palette the game paints it with, and the scenes that use it (drawn
    by the page as the game would)."""
    def asset_info(params, **_kwargs):
        try:
            found = _asset_file((params or {}).get("path") if isinstance(params, dict) else None)
            if not found:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in your games are shown here."}
            real, root = found
            _keep_version(real)
            frames = root == (host._data_dir() / "frames").resolve()
            relative = None if frames else real.relative_to(root).as_posix()
            kind = "frame" if frames else _asset_kind(relative)
            answer = {"ok": True, "path": str(real), "relative": relative, "kind": kind, "versions": _versions(real)}
            if not frames and real == game_card.cover_path(root).resolve():
                answer["kind"] = "cover"
            if frames or kind not in ("sprite", "background"):
                return answer
            meta = _read_json(real.with_name(real.name + ".gbsres"))
            if not meta or not meta.get("id"):
                return answer
            index = _project_index(root)
            sprites_cache = {}
            uses, scenes = [], []
            if kind == "sprite":
                sprite = _sprite_animations(meta)
                sprites_cache[meta["id"]] = sprite
                answer["sprite"] = sprite
                palette = None
                for scene in index["scenes"]:
                    view = _scene_view(index, scene, sprites_cache)
                    mine = [actor for actor in view["actors"] if actor["spriteId"] == meta["id"]]
                    if mine:
                        palette = palette or mine[0]["palette"]
                        uses.append({"scene": view["name"], "sceneId": view["id"],
                                     "as": [actor["name"] for actor in mine][:6], "count": len(mine)})
                        if len(scenes) < _ASSET_INFO_SCENES:
                            scenes.append(view)
                answer["palette"] = palette or _actor_palette(index, {}, None)
            else:
                for scene in index["scenes"]:
                    if scene.get("backgroundId") == meta["id"]:
                        view = _scene_view(index, scene, sprites_cache)
                        uses.append({"scene": view["name"], "sceneId": view["id"], "as": ["Background"], "count": 1})
                        if len(scenes) < _ASSET_INFO_SCENES:
                            scenes.append(view)
                answer["background"] = {"name": meta.get("name"), "autoColor": bool(meta.get("autoColor"))}
            answer["usedIn"] = uses
            answer["scenes"] = scenes
            answer["sprites"] = {sprite_id: {key: sprite[key] for key in ("canvasWidth", "canvasHeight")}
                                 for sprite_id, sprite in sprites_cache.items()}
            return answer
        except FileNotFoundError:
            return {"ok": False, "code": "MISSING", "error": "The image is gone."}
        except Exception as error:
            logger.exception("hermretro asset_info failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset_info


def rpc_asset_restore(ctx):
    """Put a kept version of a game image back in place (the one there now is kept first, so this can
    be undone the same way)."""
    def asset_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            found = _asset_file(params.get("path"))
            wanted = str(params.get("version") or "")
            if not found or not wanted.isdigit():
                return {"ok": False, "code": "INVALID", "error": "Only a kept version of an image in your games can be restored."}
            real, root = found
            if root == (host._data_dir() / "frames").resolve():
                return {"ok": False, "code": "INVALID", "error": "Playtest frames are not restored."}
            kept = _versions_dir(real) / f"{wanted}{real.suffix.lower()}"
            if not kept.is_file():
                return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
            _keep_version(real)
            partial = real.with_name(f".{real.name}.restore")
            partial.write_bytes(kept.read_bytes())
            partial.replace(real)
            _keep_version(real)
            return {"ok": True, "path": str(real), "versions": _versions(real)}
        except Exception as error:
            logger.exception("hermretro asset_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset_restore


_ASSET_LIST_FOLDERS = (("sprites", "sprite"), ("backgrounds", "background"), ("ui", "ui"), ("fonts", "ui"))
ASSET_LIST_LIMIT = 400


def _list_root(params) -> Path | None:
    """The library game a list is for, by id or by its folder (never a folder outside the library)."""
    root = host._game_root(str(params.get("game") or "")) if params.get("game") else None
    if root is None and params.get("root"):
        try:
            wanted = Path(str(params["root"])).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        frames = (host._data_dir() / "frames").resolve()
        root = next((base for base in _asset_roots() if base == wanted and base != frames), None)
    return root


def rpc_assets(ctx):
    """Every picture of one game, for the Build page's Assets panel: the game card's cover, then its
    sprites, backgrounds and interface art, each with the name its sidecar gives it. Lists files only
    (no image data); the page fetches each one through ``asset``."""
    def assets(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            root = _list_root(params)
            if root is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library can be listed."}
            items = []
            cover = game_card.cover_path(root)
            if cover.is_file():
                stat = cover.stat()
                items.append({"path": str(cover.resolve()), "relative": cover.relative_to(root).as_posix(), "name": "Cover",
                              "file": cover.name, "kind": "cover", "modifiedAt": stat.st_mtime, "bytes": stat.st_size})
            for folder, kind in _ASSET_LIST_FOLDERS:
                base = root / "assets" / folder
                if not base.is_dir():
                    continue
                for image in sorted(base.rglob("*")):
                    if len(items) >= ASSET_LIST_LIMIT:
                        break
                    if image.suffix.lower() not in ASSET_SUFFIXES or not image.is_file():
                        continue
                    try:
                        real = image.resolve(strict=True)
                    except (OSError, RuntimeError):
                        continue
                    if real != root and root not in real.parents:
                        continue
                    meta = _read_json(image.with_name(image.name + ".gbsres"), 2 * 1024 * 1024) or {}
                    stat = real.stat()
                    items.append({"path": str(real), "relative": real.relative_to(root).as_posix(),
                                  "name": str(meta.get("name") or image.stem), "file": image.name, "kind": kind,
                                  "modifiedAt": stat.st_mtime, "bytes": stat.st_size})
            return {"ok": True, "root": str(root), "assets": items, "truncated": len(items) >= ASSET_LIST_LIMIT}
        except Exception as error:
            logger.exception("hermretro assets failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return assets
