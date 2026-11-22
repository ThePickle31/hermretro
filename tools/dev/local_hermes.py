"""The parts of Hermes the development loop touches: each profile's link to a hermretro checkout, the gateway's
control socket (to reload the plugin without a restart) and Hermes Desktop's copy of the page.

Standard library only; development only (nothing here runs inside Hermes).
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

PLUGIN = "hermretro"
STUDIO = "hermretro"


class GatewayError(Exception):
    """The gateway is not running, or refused or failed a control request."""


def hermes_root(given: str | None = None) -> Path:
    """The Hermes home that holds every profile (`~/.hermes` unless named)."""
    return Path(given).expanduser() if given else Path.home() / ".hermes"


def profile_homes(root: Path) -> dict[str, Path]:
    """Every profile's home, by name: `default` is the root itself."""
    homes = {"default": root}
    profiles = root / "profiles"
    if profiles.is_dir():
        homes.update((home.name, home) for home in sorted(profiles.iterdir()) if home.is_dir())
    return homes


def plugin_links(root: Path) -> dict[str, Path]:
    """The profiles that load hermretro through a symlink (a development checkout), and that link."""
    links = {name: home / "plugins" / PLUGIN for name, home in profile_homes(root).items()}
    return {name: link for name, link in links.items() if link.is_symlink()}


def loading_profiles(root: Path) -> list[str]:
    """The profiles with hermretro in their plugins folder, linked or installed."""
    homes = profile_homes(root)
    return [
        name
        for name, home in homes.items()
        if (home / "plugins" / PLUGIN).is_symlink() or (home / "plugins" / PLUGIN).is_dir()
    ]


def live_checkout(root: Path) -> Path | None:
    """The checkout the studio profile loads, when it loads one through a link."""
    link = plugin_links(root).get(STUDIO)
    return link.resolve() if link else None


def point(link: Path, target: Path) -> bool:
    """Point the symlink at ``target`` in one rename; False when it already does."""
    if link.resolve() == target.resolve():
        return False
    temporary = link.with_name(f".{link.name}.dev-link")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)
    return True


def control_socket(home: Path, root: Path) -> Path | None:
    """The control socket of the gateway serving ``home``: its own, else the one that serves every profile.
    A home whose path is too long for a socket names it in `gateway.sock.path` (Hermes's
    gateway/control_socket.py)."""
    for base in (home, root):
        direct = base / "gateway.sock"
        if direct.exists():
            return direct
        pointer = base / "gateway.sock.path"
        if pointer.is_file():
            target = Path(pointer.read_text(encoding="utf-8-sig").strip())
            if target.exists():
                return target
    return None


def control(path: Path, verb: str, params: dict | None = None, timeout: float = 60.0) -> dict:
    """One control request: a JSON line out, a JSON line back; its ``result``."""
    request = {"verb": verb, "id": 1, "protocol": 1, **({"params": params} if params else {})}
    data = b""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(path))
            connection.sendall(json.dumps(request).encode("utf-8") + b"\n")
            while b"\n" not in data:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                data += chunk
    except OSError as error:
        raise GatewayError(f"the gateway did not answer on {path}: {error}") from error
    try:
        answer = json.loads(data.partition(b"\n")[0] or b"null")
    except ValueError as error:
        raise GatewayError(f"the gateway answered {verb} with something that is not JSON") from error
    if not isinstance(answer, dict) or answer.get("ok") is not True or not isinstance(answer.get("result"), dict):
        said = answer.get("error") if isinstance(answer, dict) else None
        raise GatewayError(f"the gateway refused {verb}: {said or 'no answer'}")
    return answer["result"]


def reload(root: Path, profile: str) -> dict:
    """Re-import every plugin of ``profile`` in its running gateway: RPCs answer from the new code at once, tools and
    the prompt from the next chat."""
    home = profile_homes(root).get(profile)
    if home is None:
        raise GatewayError(f"there is no profile {profile!r} in {root}")
    path = control_socket(home, root)
    if path is None:
        raise GatewayError("no gateway is running (hermes gateway start, or open Hermes Desktop)")
    result = control(path, "reload-plugins", {"home": str(home)})
    if not result.get("reloaded"):
        raise GatewayError(f"the gateway did not reload {profile}: {result.get('error') or result}")
    return result


def refresh_desktop(root: Path, checkout: Path) -> bool:
    """Put ``checkout``'s page bundle in Hermes Desktop's copy of it, which the app reloads on change; False when there
    is no copy (the page is not installed) or it is already current. Desktop re-copies a linked plugin by itself when
    its source changes, but only from the folder it was watching at start, so after `live` points the link elsewhere
    this keeps the app on the new checkout."""
    copy = root / "desktop-plugins" / PLUGIN / "plugin.js"
    source = checkout / "desktop" / "plugin.js"
    if not copy.parent.is_dir() or not source.is_file():
        return False
    data = source.read_bytes()
    if copy.is_file() and copy.read_bytes() == data:
        return False
    temporary = copy.with_name(".plugin.js.dev-copy")
    temporary.write_bytes(data)
    os.replace(temporary, copy)
    return True
