"""Client side of the broker. Stdlib only; safe to import from Hermes and from tests."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import paths


class BrokerUnavailable(RuntimeError):
    pass


class BrokerClient:
    def __init__(self, state_dir: Path, token: str | None = None):
        self.state_dir = Path(state_dir)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(str(self.state_dir / "broker.sock"))
        except OSError as error:
            self.sock.close()
            raise BrokerUnavailable(str(error)) from error
        self.reader = self.sock.makefile("rb")
        try:
            if token is None:
                token = (self.state_dir / "broker.token").read_text()
            self.hello = self.request({"op": "hello", "protocol": paths.PROTOCOL, "token": token})
        except Exception:
            self.close()
            raise

    def request(self, obj: dict) -> dict:
        try:
            self.sock.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())
            line = self.reader.readline()
        except OSError as error:
            raise BrokerUnavailable(str(error)) from error
        if not line:
            raise BrokerUnavailable("Broker closed the connection")
        return json.loads(line)

    def call(self, owner: dict | None, tool: str, arguments: dict | None = None, origin: dict | None = None,
             policy: dict | None = None, timeout: float | None = None) -> dict:
        request: dict = {"op": "call", "tool": tool, "arguments": arguments or {}}
        if timeout is not None:
            request["timeout"] = timeout
        if owner is not None:
            request["owner"] = owner
        if origin is not None:
            request["origin"] = origin
        if policy is not None:
            request["policy"] = policy
        return self.request(request)

    def close(self) -> None:
        for closer in (getattr(self, "reader", None), self.sock):
            try:
                if closer is not None:
                    closer.close()
            except OSError:
                pass

    def __enter__(self) -> "BrokerClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def spawn_broker(state_dir: Path, node: str) -> subprocess.Popen:
    """Start a broker detached from the caller. It runs from the plugin root with a minimal environment."""
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "XDG_DATA_HOME", "XDG_RUNTIME_DIR",
                                            "XDG_STATE_HOME", "TMPDIR", "USER", "LOGNAME", "DISPLAY",
                                            "WAYLAND_DISPLAY", "GB_STUDIO_SETUP_ROOT") if key in os.environ}
    env.update({key: value for key, value in os.environ.items() if key.startswith("HERMRETRO_")})
    with open(Path(state_dir) / "broker.stderr.log", "ab") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "adapter.broker", "--state-dir", str(state_dir), "--node", node],
            cwd=str(paths.PLUGIN_ROOT), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=log, start_new_session=True)


def try_connect(state_dir: Path) -> tuple[BrokerClient | None, Exception | None]:
    try:
        client = BrokerClient(state_dir)
    except (BrokerUnavailable, FileNotFoundError, json.JSONDecodeError) as error:
        return None, error
    if client.hello.get("ok"):
        return client, None
    error = BrokerUnavailable(json.dumps(client.hello))  # the token raced a restart
    client.close()
    return None, error


def ensure_broker(state_dir: Path | None = None, wait: float = 20.0) -> BrokerClient:
    """Connect to the broker, starting it when needed. Racing callers converge on one winner.

    A broker left over from another build of this adapter is replaced when it is idle."""
    state_dir = Path(state_dir) if state_dir else paths.runtime_dir()
    node = paths.find_node()
    if not node.get("ok"):
        raise BrokerUnavailable(
            f"Node.js {paths.NODE_REQUIRED_MAJOR} or newer is required but was not found"
            + (f" (found {node['version']})" if node.get("version") else "") + ".")
    deadline = time.monotonic() + wait
    last: Exception | None = None
    spawned = False
    while time.monotonic() < deadline:
        client, last = try_connect(state_dir)
        if client is not None:
            other_install = client.hello.get("plugin_root") not in (None, str(paths.PLUGIN_ROOT))
            if client.hello.get("code_fingerprint") == paths.code_fingerprint() and not other_install:
                return client
            # A broker from another build of this adapter. Replace it only when no conversation
            # has a live worker; otherwise keep using it (same wire protocol) rather than kill
            # someone's running game. It retires itself once it is idle.
            answer = client.request({"op": "shutdown"})
            if not answer.get("ok"):
                if other_install:
                    # A second copy of the plugin (another profile's install) has its own engine and
                    # dependency folders; its broker must not serve this copy's conversations.
                    client.close()
                    raise BrokerUnavailable(
                        "Another copy of hermretro (" + str(client.hello.get("plugin_root")) + ") is "
                        "running games right now. Finish or close those chats, then try again.")
                return client
            client.close()
            time.sleep(0.4)
            spawned = False
            continue
        if not spawned:
            spawn_broker(state_dir, node["path"])
            spawned = True
        time.sleep(0.05)
    raise BrokerUnavailable(f"The hermretro broker did not start: {last}")
