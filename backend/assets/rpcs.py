"""Game images for the Build page: the asset, asset_info, asset_restore and assets RPCs. Kept versions
live in versions.py, sprite and scene reading in sprites.py, the project image walk in project_files.py. Declared
with @rpc."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from ..hermes import host
from ..hermes.declare import rpc
from ..library import cover_path
from ..system.events import emit
from .project_files import project_images
from .sprites import (
    _ASSET_INFO_SCENES,
    _actor_palette,
    _project_index,
    _read_json,
    _scene_view,
    _sprite_animations,
    _sprite_look,
)
from .versions import (
    ASSET_MAX_BYTES,
    ASSET_SUFFIXES,
    _asset_file,
    _asset_kind,
    _asset_roots,
    _image_size,
    _keep_version,
    _version_at,
    _versions,
    _versions_dir,
    size_text,
)

logger = host.logger  # one logger for the Hermes side of the backend,


@rpc("asset")
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
                raw = raw[len("file://") :]
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
                limit = size_text(ASSET_MAX_BYTES)
                return {
                    "ok": False,
                    "code": "TOO_LARGE",
                    "error": f"The image is larger than {limit}, too large to preview.",
                }
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
            answer = {
                "ok": True,
                "path": str(real),
                "relative": relative,
                "name": real.name,
                "kind": _asset_kind(relative) if relative else "frame",
                "width": width,
                "height": height,
                "bytes": len(data),
                "modifiedAt": (int(earlier.stem) / 1e9) if earlier else real.stat().st_mtime,
                "earlier": earlier is not None,
                "versionId": earlier.stem if earlier else str(real.stat().st_mtime_ns),
                "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
            }
            sidecar = real.with_name(real.name + ".gbsres")
            if answer["kind"] == "sprite" and sidecar.is_file() and sidecar.stat().st_size < 2 * 1024 * 1024:
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                    frame_width, frame_height = int(meta.get("canvasWidth") or 0), int(meta.get("canvasHeight") or 0)
                    if frame_width > 0 and frame_height > 0:
                        answer["sprite"] = {
                            "name": meta.get("name"),
                            "frameWidth": frame_width,
                            "frameHeight": frame_height,
                            "animSpeed": meta.get("animSpeed"),
                        }
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


@rpc("asset_info")
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
            if not frames and real == cover_path(root).resolve():
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
                        uses.append(
                            {
                                "scene": view["name"],
                                "sceneId": view["id"],
                                "as": [actor["name"] for actor in mine][:6],
                                "count": len(mine),
                            }
                        )
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
            answer["sprites"] = {
                sprite_id: {key: sprite[key] for key in ("canvasWidth", "canvasHeight")}
                for sprite_id, sprite in sprites_cache.items()
            }
            return answer
        except FileNotFoundError:
            return {"ok": False, "code": "MISSING", "error": "The image is gone."}
        except Exception as error:
            logger.exception("hermretro asset_info failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return asset_info


@rpc("asset_restore")
def rpc_asset_restore(ctx):
    """Put a kept version of a game image back in place (the one there now is kept first, so this can
    be undone the same way)."""

    def asset_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            found = _asset_file(params.get("path"))
            wanted = str(params.get("version") or "")
            if not found or not wanted.isdigit():
                return {
                    "ok": False,
                    "code": "INVALID",
                    "error": "Only a kept version of an image in your games can be restored.",
                }
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
            emit("assets.image_restored", path=str(real))
            return {"ok": True, "path": str(real), "versions": _versions(real)}
        except Exception as error:
            logger.exception("hermretro asset_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return asset_restore


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


@rpc("assets")
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
            truncated = False
            cover = cover_path(root)
            if cover.is_file():
                stat = cover.stat()
                items.append(
                    {
                        "path": str(cover.resolve()),
                        "relative": cover.relative_to(root).as_posix(),
                        "name": "Cover",
                        "file": cover.name,
                        "kind": "cover",
                        "modifiedAt": stat.st_mtime,
                        "bytes": stat.st_size,
                    }
                )
            for image, real, kind in project_images(root):
                if len(items) >= ASSET_LIST_LIMIT:
                    truncated = True  # a picture is left out; at exactly the cap there is none
                    break
                meta = _read_json(image.with_name(image.name + ".gbsres"), 2 * 1024 * 1024) or {}
                stat = real.stat()
                items.append(
                    {
                        "path": str(real),
                        "relative": real.relative_to(root).as_posix(),
                        "name": str(meta.get("name") or image.stem),
                        "file": image.name,
                        "kind": kind,
                        "modifiedAt": stat.st_mtime,
                        "bytes": stat.st_size,
                    }
                )
            return {"ok": True, "root": str(root), "assets": items, "truncated": truncated}
        except Exception as error:
            logger.exception("hermretro assets failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return assets
