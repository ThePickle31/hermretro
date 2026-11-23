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
    AssetOwners,
    _asset_file,
    _asset_kind,
    _image_root,
    _image_size,
    _is_frames,
    _restore_version,
    _same_folder,
    _shown_in,
    _try_keep_version,
    _version_at,
    _version_lock,
    _versions,
    _versions_dir,
    size_text,
)

logger = host.logger  # one logger for the Hermes side of the backend,


@rpc("asset")
def rpc_asset(ctx):
    """One image for the Build page (a thumbnail, the asset viewer): only from the folder of the library game the
    page shows (``root``, its project folder) or the frames Hermes saved from tool results. Answers a data URL, its size and, for a sprite, the
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
            root = _image_root(real)
            if root is None:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in your games are shown here."}
            if not _shown_in(root, params.get("root")):
                return {"ok": False, "code": "OTHER_GAME", "error": "That image belongs to another game."}
            with _version_lock(real):
                stat = real.stat()
                if stat.st_size > ASSET_MAX_BYTES:
                    limit = size_text(ASSET_MAX_BYTES)
                    return {
                        "ok": False,
                        "code": "TOO_LARGE",
                        "error": f"The image is larger than {limit}, too large to preview.",
                    }
                folder = _versions_dir(real, root)
                earlier = None
                wanted = str(params.get("version") or "")
                if wanted:
                    # One kept version by its id (the file's modification time in ns), as the viewer lists them.
                    if not wanted.isdigit():
                        return {"ok": False, "code": "INVALID", "error": "Unknown version."}
                    if int(wanted) != stat.st_mtime_ns:
                        earlier = folder / f"{wanted}{real.suffix.lower()}"
                        if not earlier.is_file():
                            return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
                elif params.get("at") is not None:
                    earlier = _version_at(real, folder, params.get("at"))
                _try_keep_version(real, folder, protect=(earlier,))
                data = (earlier or real).read_bytes()
            width, height = _image_size(data)
            relative = None if _is_frames(root) else real.relative_to(root).as_posix()
            answer = {
                "ok": True,
                "path": str(real),
                "relative": relative,
                "name": real.name,
                "kind": _asset_kind(relative) if relative else "frame",
                "width": width,
                "height": height,
                "bytes": len(data),
                "modifiedAt": (int(earlier.stem) / 1e9) if earlier else stat.st_mtime,
                "earlier": earlier is not None,
                "versionId": earlier.stem if earlier else str(stat.st_mtime_ns),
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
    """What the asset viewer shows beside an image of the game at ``root``: its kind, every kept version, and for a sprite or
    background its animations, the palette the game paints it with, and the scenes that use it (drawn
    by the page as the game would)."""

    def asset_info(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            found = _asset_file(params.get("path"), params.get("root"))
            if not found:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in this game are shown here."}
            real, root = found
            with _version_lock(real):
                folder = _versions_dir(real, root)
                _try_keep_version(real, folder)
                versions = _versions(real, folder)
            frames = _is_frames(root)
            relative = None if frames else real.relative_to(root).as_posix()
            kind = "frame" if frames else _asset_kind(relative)
            answer = {
                "ok": True,
                "path": str(real),
                "relative": relative,
                "kind": kind,
                "versions": versions,
            }
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
    """Put a kept version of an image of the game at ``root`` back in place (the one there now is kept first, so this can
    be undone the same way)."""

    def asset_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            found = _asset_file(params.get("path"), params.get("root"))
            wanted = str(params.get("version") or "")
            if not found or not wanted.isdigit():
                return {
                    "ok": False,
                    "code": "INVALID",
                    "error": "Only a kept version of an image in this game can be restored.",
                }
            real, root = found
            if _is_frames(root):
                return {"ok": False, "code": "INVALID", "error": "Playtest frames are not restored."}
            versions = _restore_version(real, root, wanted)
            if versions is None:
                return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
            emit("assets.image_restored", path=str(real))
            return {"ok": True, "path": str(real), "versions": versions}
        except Exception as error:
            logger.exception("hermretro asset_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return asset_restore


ASSET_LIST_LIMIT = 400


@rpc("assets")
def rpc_assets(ctx):
    """Every picture of one game, for the Build page's Assets panel: the game card's cover, then its
    sprites, backgrounds and interface art, each with the name its sidecar gives it. Lists files only
    (no image data); the page fetches each one through ``asset``."""

    def assets(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            owners = AssetOwners()
            root = owners.list_root(params.get("game"), params.get("root"))
            if root is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library can be listed."}
            items = []
            truncated = False
            cover = cover_path(root)
            if cover.is_file():
                real_cover = cover.resolve()
                cover_owner = owners.image_root(real_cover)
                if cover_owner == root or (cover_owner is not None and _same_folder(cover_owner, root)):
                    stat = real_cover.stat()
                    items.append(
                        {
                            "path": str(real_cover),
                            "relative": cover.relative_to(root).as_posix(),
                            "name": "Cover",
                            "file": cover.name,
                            "kind": "cover",
                            "modifiedAt": stat.st_mtime,
                            "bytes": stat.st_size,
                        }
                    )
            for image, real, kind in project_images(root):
                owner = owners.image_root(real)
                if owner is None or (owner != root and not _same_folder(owner, root)):
                    continue  # a game inside this one's art folders keeps its own pictures
                if len(items) >= ASSET_LIST_LIMIT:
                    truncated = True  # a picture is left out; at exactly the cap there is none
                    break
                meta = _read_json(image.with_name(image.name + ".gbsres"), 2 * 1024 * 1024) or {}
                stat = real.stat()
                items.append(
                    {
                        "path": str(real),
                        "relative": real.relative_to(owner).as_posix(),
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
