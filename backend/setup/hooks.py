"""Setup's Hermes hook: downloading ModRetro's CLI (``chromatic_studio_device_cli`` install) goes through
Hermes's approval prompt. Chained after the Hermes layer's own ``pre_tool_call`` (hardware approvals)."""
from __future__ import annotations

from ..hermes.declare import hook
from . import provision
from .tools import DEVICE_CLI_TOOL


@hook("pre_tool_call")
def approve_device_cli_install(tool_name=None, args=None, **_kwargs):
    """Ask before the vendor download; denial, timeout or nobody to ask leave the tool unrun."""
    if tool_name == DEVICE_CLI_TOOL["name"]:
        if not isinstance(args, dict) or args.get("action") != "install":
            return None  # status is passive
        try:
            host = provision.host_target()
            pins = provision._pins(host["target"]) if host["target"] else None
        except Exception:
            pins = None
        if pins is None:
            return None  # nothing can be installed here; the tool explains why
        megabytes = pins["package"]["bytes"] / 1_000_000
        return {"action": "approve",
                "message": (f"Download ModRetro's Chromatic CLI {pins['version']} ({megabytes:.1f} MB) from "
                            f"{pins['package']['url']} into hermretro's folder in the Hermes home. It is proprietary "
                            f"ModRetro software; approving means you agree to ModRetro's terms "
                            f"({provision.VENDOR_TERMS_URL}). Nothing is sent to a device."),
                # One key per CLI release: "always" covers a reinstall, never a different version.
                "rule_key": f"hermretro:device-cli-install:{pins['version']}"}
    return None
