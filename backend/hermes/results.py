"""Encode a broker response as a Hermes tool result without losing what the engine said.

Text is one JSON document: the engine's text, its complete structuredContent, its
error state, and the saved path and hash of every image. When the active model
route accepts images inside tool results, the same image bytes are attached so the
model sees the real pixels; otherwise the saved paths let it look with a vision tool.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from pathlib import Path
from uuid import uuid4


# What an agent does about an unexpected failure inside the plugin, whichever tool it came from.
ADAPTER_ERROR_NEXT_STEP = (
    "This is a fault in hermretro, not in the game. Tell the user what failed; do not retry the same call blindly, "
    "and do not work around it outside the chromatic tools."
)

# A build is a checkpoint: the agent keeps authoring until everything agreed with the user is in the game.
CHECKPOINT = (
    "A build is a checkpoint, not a hand-off: keep authoring until everything agreed with the user is in the game; "
    "only then "
)
# Handing the game to the user, in order, once everything agreed is built; the prompt section's steps end with it too.
DELIVER = (
    "playtest it yourself with the chromatic_emulator_* tools; fill in its game card with chromatic_game_info; "
    "show it with chromatic_present_game; end the turn with "
    "chromatic_build_report."
)


def save_images(result: dict, directory: Path) -> list[dict]:
    """Store each image block content-addressed and return its record (with the original base64)."""
    records = []
    for block in result.get("content") or []:
        if block.get("type") != "image" or not block.get("data"):
            continue
        data = base64.b64decode(block["data"])
        digest = hashlib.sha256(data).hexdigest()
        mime = block.get("mimeType") or "image/png"
        suffix = {"image/png": ".png", "image/gif": ".gif", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
            mime, ".bin"
        )
        path = directory / digest[:2] / f"{digest}{suffix}"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Its own temporary name: two chats can save the same picture at the same moment.
            temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
        records.append(
            {"path": str(path), "sha256": digest, "mimeType": mime, "bytes": len(data), "_data": block["data"]}
        )
    return records


def encode(response: dict, tool: str, image_dir: Path | None, attach_images: bool):
    """Return a JSON string, or the Hermes multimodal envelope when images are attached."""
    if response.get("denied"):
        denied = response["denied"]
        return json.dumps(
            {
                "error": denied["message"],
                "code": denied["code"],
                "dispatched": False,
                "nextStep": "Nothing ran. Do what the error says; do not repeat the same call unchanged.",
            }
        )
    if not response.get("ok"):
        if response.get("dispatched"):
            return json.dumps(
                {
                    "error": response.get("error") or "The engine did not answer.",
                    "code": "OUTCOME_UNKNOWN",
                    "dispatched": True,
                    "nextStep": "The operation may have run. Inspect current state before deciding what to do; "
                    "do not simply repeat it.",
                }
            )
        return json.dumps(
            {
                "error": response.get("error") or "hermretro is unavailable.",
                "code": "UNAVAILABLE",
                "dispatched": False,
                "nextStep": "Nothing ran. Try once more; if it fails again, tell the user what it said. Do not build, "
                "play or edit the game outside the chromatic tools.",
            }
        )

    result = response["result"]
    texts = [block.get("text", "") for block in result.get("content") or [] if block.get("type") == "text"]
    other = [block.get("type") for block in result.get("content") or [] if block.get("type") not in ("text", "image")]
    payload: dict = {}
    text = "\n".join(t for t in texts if t)
    structured = result.get("structuredContent")
    if result.get("isError"):
        payload["isError"] = True
        payload["error"] = (structured or {}).get("error") if isinstance(structured, dict) else None
        payload["error"] = payload["error"] or text or "The engine reported an error."
        if isinstance(structured, dict) and structured.get("code"):
            payload["code"] = structured["code"]
    if (
        tool == "chromatic_rom_build"
        and isinstance(structured, dict)
        and structured.get("success") is True
        and not result.get("isError")
    ):
        # Keep the reference ahead of verbose diagnostics in any leading preview.
        payload["buildRef"] = uuid4().hex
    if text and not (result.get("isError") and structured):
        payload["result"] = text
    if structured is not None:
        payload["structuredContent"] = structured
    if result.get("_meta"):
        payload["_meta"] = result["_meta"]
    if other:
        payload["unrenderedContentTypes"] = other
    if response.get("notice"):
        payload["notice"] = response["notice"]
    # Builds open nothing for the user: the agent shows the game with chromatic_present_game once everything
    # agreed is in it. The engine's own preview address is not offered; the user plays in the Studio emulator.
    present = (
        CHECKPOINT + DELIVER + " chromatic_present_game takes an optional short note on what to try and "
        "shows the game in the hermretro emulator beside the chat. Do not use desktop_preview or drive_preview for the game. Only if the user says they cannot see "
        "the emulator, open studio.playerUrl from chromatic_present_game with desktop_preview (action \"open\"); "
        "without desktop tools, give the user that url. Never press \"Install on Chromatic\" in a player for the "
        "user."
    )
    player = response.get("player")
    if isinstance(player, dict) and player.get("ready"):
        payload["player"] = {
            "ready": True,
            "showsThisBuild": "after chromatic_present_game, or when the user "
            "loads it in an emulator that is already open",
        }
        payload["nextStep"] = "Continue with your work: the playable copy of this build is ready. " + present
    elif isinstance(player, dict):
        payload["player"] = {"ready": False, "error": player.get("error")}
        if player.get("stale"):
            payload["player"]["showsThisBuild"] = False
            payload["nextStep"] = (
                "The build succeeded, but the engine's preview could NOT be updated and still belongs to an older "
                "build, so \"Install on Chromatic\" from it would be refused. Do not claim the new build is in a "
                "player. To recover, call chromatic_web_preview_close followed by chromatic_web_preview, then carry on. "
                + CHECKPOINT
                + DELIVER
                + " If closing fails again, say so and stop; a new chat starts a fresh player."
            )
    elif (
        tool == "chromatic_web_preview"
        and isinstance(structured, dict)
        and structured.get("success")
        and isinstance(structured.get("url"), str)
    ):
        payload["nextStep"] = "The playable copy is ready. " + present
    if (
        tool == "chromatic_rom_build"
        and "nextStep" not in payload
        and not result.get("isError")
        and (structured or {}).get("success") is not False
    ):
        # No playable copy was refreshed (the setting is off, or the export failed): still a checkpoint.
        payload["nextStep"] = "Continue with your work. " + CHECKPOINT + DELIVER

    images = save_images(result, image_dir) if image_dir is not None else []
    if images:
        payload["images"] = [
            {"file": "MEDIA:" + image["path"], "sha256": image["sha256"], "mimeType": image["mimeType"]}
            for image in images
        ]
        payload["imageDelivery"] = (
            "The real pixels were attached to this result when it was first delivered. A resumed or "
            "compacted transcript shows only a placeholder; that does not mean the image was missing. "
            "Open the listed file to look again."
            if attach_images
            else "saved to the listed files; open them with a vision tool to see them"
        )
    text_result = json.dumps(payload, ensure_ascii=False)
    if not images or not attach_images:
        return text_result
    content: list[dict] = [{"type": "text", "text": text_result}]
    content.extend(
        {"type": "image_url", "image_url": {"url": f"data:{image['mimeType']};base64,{image['_data']}"}}
        for image in images
    )
    return {
        "_multimodal": True,
        "content": content,
        "text_summary": text_result,
        "meta": {"tool": tool, "images": len(images)},
    }
