"""Client side of the broker. Stdlib only; safe to import from Hermes and from tests."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from ..system import host as host_os, paths


class BrokerUnavailable(RuntimeError):
    pass


class BrokerNotRunning(BrokerUnavailable):
    """The socket was missing or refused the connection."""


class OtherCopyBusy(BrokerUnavailable):
    """The running broker belongs to another copy of the plugin (another folder, or an older version that
    cannot say which), and it still has live game workers, so it is neither used nor replaced.
    ``plugin_root`` is that copy's folder when it said."""

    def __init__(self, message: str, plugin_root: str | None = None):
        super().__init__(message)
        self.plugin_root = plugin_root


CONTROL_TIMEOUT = 3.0
QUICK_OPS = frozenset({"hello", "stats", "activity", "install_start", "install_status", "install_cancel"})


def _remaining(deadline: float | None, maximum: float) -> float:
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Broker startup or request deadline expired")
    return min(maximum, remaining)


class BrokerClient:
    control_timeout = CONTROL_TIMEOUT

    def __init__(self, state_dir: Path, token: str | None = None, *, deadline: float | None = None):
        self.state_dir = Path(state_dir)
        self.startup_deadline = deadline
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.settimeout(_remaining(deadline, self.control_timeout))
            self.sock.connect(str(self.state_dir / "broker.sock"))
        except (FileNotFoundError, ConnectionRefusedError) as error:
            self.close()
            raise BrokerNotRunning(str(error)) from error
        except OSError as error:
            self.close()
            raise BrokerUnavailable(str(error)) from error
        try:
            if token is None:
                token = (self.state_dir / "broker.token").read_text()
            self.hello = self.request({"op": "hello", "protocol": paths.PROTOCOL, "token": token})
        except Exception:
            self.close()
            raise

    def request(self, obj: dict) -> dict:
        op = obj.get("op")
        if op in QUICK_OPS:
            budget = self.control_timeout
        elif op == "lane_status":
            # lane_status may spend up to 15 seconds asking an idle engine about its emulator.
            budget = 20.0
        elif op == "shutdown":
            # Setup removal allows longer for older brokers to answer. Replacement has the startup budget.
            budget = 15.0 if self.startup_deadline is None else self.control_timeout
        else:
            budget = None
        deadline = None
        if budget is not None:
            deadline = time.monotonic() + budget
            if self.startup_deadline is not None:
                deadline = min(deadline, self.startup_deadline)
        try:
            self.sock.settimeout(_remaining(deadline, budget) if budget is not None else None)
            self.sock.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())
            line = bytearray()
            while not line.endswith(b"\n"):
                if budget is not None:
                    self.sock.settimeout(_remaining(deadline, budget))
                part = self.sock.recv(65536)
                if not part:
                    self.close()
                    raise BrokerUnavailable("Broker closed the connection")
                line.extend(part)
        except TimeoutError as error:
            self.close()
            raise BrokerUnavailable(f"Broker did not answer {op} before its deadline") from error
        except OSError as error:
            self.close()
            raise BrokerUnavailable(str(error)) from error
        answer = json.loads(line)
        if not isinstance(answer, dict):
            raise ValueError(f"Invalid broker response to {op}")
        return answer

    def call(
        self,
        owner: dict | None,
        tool: str,
        arguments: dict | None = None,
        origin: dict | None = None,
        policy: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
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
        self.sock.close()

    def __enter__(self) -> BrokerClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


_SCOPE_RUNNER: str | None = None  # "" once probed and unavailable


def own_scope(env: dict, *, deadline: float | None = None) -> list[str]:
    """A command prefix that starts the broker in its own systemd scope, or ``[]``.

    Under systemd the gateway's unit owns every process it starts, broker and engine workers
    included, and stopping or restarting the gateway SIGKILLs them all (``KillMode=mixed``). A worker
    killed that way never releases its emulator lease, which then blocks that game's emulator. In its
    own scope the broker outlives gateway restarts as designed and still exits when idle. Used only
    when the caller runs inside a systemd unit and a probe proves ``systemd-run --user --scope``
    works; anywhere else (macOS, containers, no user bus) the broker starts as before."""
    global _SCOPE_RUNNER
    if _SCOPE_RUNNER is None:
        _SCOPE_RUNNER = _probe_scope(env, deadline=deadline)
    if not _SCOPE_RUNNER:
        return []
    unit = f"hermretro-broker-{os.getpid()}-{time.time_ns()}"  # one scope per broker
    return [_SCOPE_RUNNER, "--user", "--scope", "--quiet", "--collect", f"--unit={unit}"]


def _probe_scope(env: dict, *, deadline: float | None) -> str:
    # systemd sets INVOCATION_ID for every process of a unit it starts (the gateway service).
    inside_service = bool(os.environ.get("INVOCATION_ID"))
    runner = shutil.which("systemd-run", path=env.get("PATH"))
    if not inside_service or not runner:
        return ""
    timeout = _remaining(deadline, 10)
    try:
        probe = subprocess.run(
            [runner, "--user", "--scope", "--quiet", "--collect", "true"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        if timeout < 10:
            raise TimeoutError("Systemd scope probe timed out") from error
        return ""
    except (OSError, subprocess.SubprocessError):
        return ""
    return runner if probe.returncode == 0 else ""


def spawn_broker(state_dir: Path, node: str, *, deadline: float | None = None) -> subprocess.Popen:
    """Start a broker detached from the caller. It runs from the plugin root with a minimal environment."""
    env = {
        key: os.environ[key]
        for key in (
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "XDG_DATA_HOME",
            "XDG_RUNTIME_DIR",
            "XDG_STATE_HOME",
            "TMPDIR",
            "USER",
            "LOGNAME",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "GB_STUDIO_SETUP_ROOT",
            *host_os.NETWORK_ENV,
        )
        if key in os.environ
    }
    env.update({key: value for key, value in os.environ.items() if key.startswith("HERMRETRO_")})
    env["HERMRETRO_HOME"] = str(paths.hermretro_home())  # absolute; the broker cannot ask Hermes itself
    command = [sys.executable, "-m", "backend.broker", "--state-dir", str(state_dir), "--node", node]
    Path(state_dir).mkdir(mode=0o700, parents=True, exist_ok=True)  # a caller may name a folder not made yet
    log_path = Path(state_dir) / "broker.stderr.log"
    if log_path.is_file() and log_path.stat().st_size > 5 * 1024 * 1024:
        log_path.replace(log_path.with_suffix(".log.1"))  # the run folder survives reboots: keep it small
    with open(log_path, "ab") as log:
        launch = own_scope(env, deadline=deadline) + command
        _remaining(deadline, CONTROL_TIMEOUT)  # The scope probe may have used the rest of the startup budget.
        return subprocess.Popen(
            launch,
            cwd=str(paths.PLUGIN_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log,
            start_new_session=True,
        )


class BrokenBroker(BrokerUnavailable):
    """A broker failed inside its own handshake, so it cannot say which code it runs. ``stopping`` tells
    whether it agreed to stop."""

    def __init__(self, hello: dict, stopping: bool):
        super().__init__(json.dumps(hello))
        self.stopping = stopping


def request_shutdown(client: BrokerClient) -> bool:
    """Return whether the broker agreed to stop. Only an explicit busy reply returns False."""
    try:
        answer = client.request({"op": "shutdown"})
    except ValueError as error:
        raise BrokerUnavailable("Shutdown was unconfirmed.") from error
    if answer.get("ok") is True:
        return True
    denied = answer.get("denied")
    if not isinstance(denied, dict):
        denied = {}
    if answer.get("ok") is False and denied.get("code") == "BUSY":
        return False
    raise BrokerUnavailable(denied.get("message") or answer.get("error") or "Shutdown was unconfirmed.")


def _shutdown_for_replacement(client: BrokerClient) -> bool:
    try:
        return request_shutdown(client)
    except BrokerUnavailable as error:
        raise BrokerUnavailable(f"The previous hermretro broker did not confirm shutdown: {error}") from error


def try_connect(
    state_dir: Path, retire_broken: bool = False, *, deadline: float | None = None
) -> tuple[BrokerClient | None, Exception | None]:
    try:
        client = BrokerClient(state_dir, deadline=deadline)
    except (BrokerUnavailable, OSError, ValueError) as error:
        return None, error
    if client.hello.get("ok"):
        return client, None
    failure = BrokerUnavailable(json.dumps(client.hello))  # the token raced a restart
    if retire_broken and "error" in client.hello and "denied" not in client.hello:
        # The handshake failed inside the broker, after it had accepted the token. A broker of the releases
        # before the backend/ layout does this once an update has removed adapter/, the folder it reads its
        # fingerprint from: it can never be compared, and every attempt keeps it from idling out. Ask it to
        # stop, as a broker of another build is asked.
        try:
            failure = BrokenBroker(client.hello, _shutdown_for_replacement(client))
        except BrokerUnavailable as error:
            failure = error
    client.close()
    return None, failure


def _workers_cannot_start(hello: dict, node: str) -> bool:
    """The broker's Node was removed (a versioned install replaced at another path), or its temporary folder
    cannot work while the one a new broker would inherit (spawn_broker passes TMPDIR) can."""
    theirs = hello.get("node")
    if theirs and theirs != node and not paths.node_usable(theirs):
        return True
    return hello.get("temp_ok") is False and host_os.engine_temp_ready({"TMPDIR": os.environ.get("TMPDIR", "")})


def ensure_broker(state_dir: Path | None = None, wait: float = 20.0) -> BrokerClient:
    """Connect to the broker, starting it when needed. Racing callers converge on one winner.

    A broker left over from another build of this backend is replaced when it is idle."""
    state_dir = Path(state_dir) if state_dir else paths.runtime_dir()
    node = paths.find_node()
    if not node.get("ok"):
        raise BrokerUnavailable(
            f"Node.js {paths.NODE_REQUIRED_MAJOR} or newer is required but was not found"
            + (f" (found {node['version']})" if node.get("version") else "")
            + "."
        )
    deadline = time.monotonic() + wait
    last: Exception | None = None
    spawned: subprocess.Popen | None = None
    while time.monotonic() < deadline:
        client, last = try_connect(state_dir, retire_broken=True, deadline=deadline)
        delay = 0.05
        if isinstance(last, BrokenBroker):
            if not last.stopping:
                raise OtherCopyBusy(
                    "The previous version of hermretro is still running games. Finish or close those chats "
                    "(it stops by itself once they are idle), then try again."
                )
            spawned = None
            delay = 0.4
        elif client is not None:
            if not _retire_stale_broker(client, node["path"], deadline):
                return client
            spawned = None
            delay = 0.4
        elif isinstance(last, BrokerNotRunning) and (spawned is None or spawned.poll() == 3):
            # Retry a lost election (exit 3) once the broker that won is gone.
            try:
                _remaining(deadline, wait)
                spawned = spawn_broker(state_dir, node["path"], deadline=deadline)
            except TimeoutError as error:
                last = error
                break
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(delay, remaining))
    raise BrokerUnavailable(f"The hermretro broker did not start: {last}")


def _retire_stale_broker(client: BrokerClient, node: str, deadline: float) -> bool:
    """Close a broker that agreed to retire, or return it to the caller with the startup budget cleared."""
    try:
        # Compare real paths now: a plugin folder swapped for a link while this process ran must not look
        # like another install. Only loaded_fingerprint identifies the running code of an updated broker.
        theirs = client.hello.get("plugin_root")
        other_install = theirs is not None and os.path.realpath(theirs) != os.path.realpath(paths.PLUGIN_ROOT)
        loaded = client.hello.get("loaded_fingerprint")
        current = loaded is not None and loaded == paths.code_fingerprint() and not other_install
        if not current or _workers_cannot_start(client.hello, node):
            # A busy broker retires on its own. Its workers can keep serving this install's conversations.
            if _shutdown_for_replacement(client):
                client.close()
                return True
            if other_install:
                raise OtherCopyBusy(
                    "Another copy of hermretro (" + str(theirs) + ") is running games right now. Finish or "
                    "close those chats, then try again.",
                    theirs,
                )
        _remaining(deadline, CONTROL_TIMEOUT)
    except TimeoutError as error:
        client.close()
        raise BrokerUnavailable(str(error)) from error
    except Exception:
        client.close()
        raise
    client.startup_deadline = None
    return False
