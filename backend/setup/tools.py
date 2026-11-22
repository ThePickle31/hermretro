"""Setup's plugin-owned tool: chromatic_studio_device_cli, checking or installing ModRetro's CLI.
Its download goes through Hermes's approval prompt (hooks.py)."""

from __future__ import annotations

import json

from ..hermes import host
from ..hermes.declare import Tool
from ..hermes.tool_args import tool_error
from . import provision

logger = host.logger  # one logger for the Hermes side of the backend


DEVICE_CLI_TOOL = {
    "name": "chromatic_studio_device_cli",
    "description": (
        "Check or install ModRetro's official Chromatic CLI for this computer. hermretro does not ship it: "
        "'install' downloads it from ModRetro's own npm package, verifies it against pinned SHA-256 digests and "
        "places it in hermretro's folder in the Hermes home. It is needed only for hardware features (device "
        "discovery, streaming, capture, cartridge flashing); creating, building and playtesting games never use it. "
        "This tool never touches USB, drivers or a device. The CLI is proprietary ModRetro software: install only "
        "after the user has agreed to ModRetro's terms, and pass acceptVendorTerms true to record that. "
        "'status' is passive and needs no consent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "install"]},
            "acceptVendorTerms": {
                "type": "boolean",
                "description": "Install only: true once the user has agreed to ModRetro's terms.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def device_cli_handler(args: dict, **_kwargs) -> str:
    try:
        args = args if isinstance(args, dict) else {}
        if args.get("action") == "install":
            answer = provision.install_device_cli(args.get("acceptVendorTerms") is True)
            answer["next"] = (
                "Hardware tools pick this up in a new chat. They also need 'Chromatic hardware tools' "
                "turned on in Settings > Plugins > hermretro."
            )
            return json.dumps(answer)
        return json.dumps(provision.summary())
    except provision.ProvisionError as error:
        return json.dumps({"error": str(error), "code": error.code, "installed": False})
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_studio_device_cli failed")
        return tool_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


TOOLS = (
    Tool(
        DEVICE_CLI_TOOL, device_cli_handler, step_words=("Setting up the Chromatic tools", "Set up the Chromatic tools")
    ),
)
