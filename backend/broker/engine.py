"""Lossless stdio MCP client for one private hermretro engine worker.

Keeps the complete raw JSON-RPC result (`content[]`, `structuredContent`,
`isError`, `_meta`) instead of normalising it to text. Stdlib only, and no
Hermes imports: this module also runs inside the standalone broker process.
One instance owns exactly one engine process.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..system import host as host_os, paths

PROTOCOL_VERSION = "2024-11-05"

# Variables the engine launcher needs. Everything else from the parent
# environment (gateway credentials included) is deliberately not inherited.
_PASSTHROUGH = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_RUNTIME_DIR",
    "TMPDIR",
    "USER",
    "LOGNAME",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    *host_os.NETWORK_ENV,
)


class EngineError(RuntimeError):
    """Transport or JSON-RPC level failure (not a tool-level isError result)."""

    def __init__(self, message: str, payload: Any = None):
        super().__init__(message)
        self.payload = payload


class EngineCancelled(EngineError):
    """The caller cancelled a request: the engine was told with MCP's ``notifications/cancelled`` and sends no
    answer for it. The work may still be winding down; the caller waits for that before closing the worker."""


def sanitized_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASSTHROUGH if k in os.environ}
    env["GB_STUDIO_LOG_LEVEL"] = "info"
    env["CHROMATIC_DEVICE_SKINS"] = str(paths.SKINS_DIR)  # the device art its preview and live-feed window show
    if extra:
        env.update(extra)
    return env


class EngineProcess:
    """One private engine process speaking newline-delimited JSON-RPC."""

    def __init__(
        self,
        engine_root: Path,
        node: str = "node",
        client_name: str = "chromatic-studio-dev",
        env: dict[str, str] | None = None,
    ):
        self.engine_root = Path(engine_root).resolve(strict=True)
        launcher = self.engine_root / "scripts" / "start-mcp.mjs"
        if not launcher.is_file():
            raise EngineError(f"Engine launcher missing: {launcher}")
        self._launcher = launcher
        self._node = node
        self._client_name = client_name
        self._env = env if env is not None else sanitized_environment()
        self._compiler_temp = None
        self._proc: subprocess.Popen | None = None
        self._pending: dict[int, queue.Queue] = {}
        # Requests whose wait timed out: the engine may still be running them (a compiler, an export) until it
        # answers or exits.
        self._unanswered: set[int] = set()
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._seq = 0
        self.stderr_tail: list[str] = []
        self.output_lines = 0  # every line the worker has written so far: a sign of life during a long tool call
        self.notifications: list[dict] = []
        self.server_info: dict | None = None
        self.capabilities: dict | None = None
        self.started_monotonic: float | None = None
        self.ready_seconds: float | None = None

    # -- lifecycle -------------------------------------------------------
    def start(self, timeout: float = 60.0) -> dict:
        if self._proc is not None:
            raise EngineError("Engine already started")
        try:
            self._compiler_temp = host_os.engine_tempdir(self._env)
        except OSError as error:
            raise EngineError(str(error)) from error
        env = self._env
        if self._compiler_temp is not None:
            env = {**env, **dict.fromkeys(("TMPDIR", "TMP", "TEMP"), self._compiler_temp.name)}
        try:
            return self._start(timeout, env)
        except BaseException:
            with suppress(OSError, subprocess.TimeoutExpired):
                self.close(grace=0.25)
            raise

    def _start(self, timeout: float, env: dict[str, str]) -> dict:
        self.started_monotonic = time.monotonic()
        self._proc = subprocess.Popen(
            [self._node, str(self._launcher)],
            cwd=self.engine_root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        init = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": self._client_name, "version": "0"},
            },
            timeout=timeout,
        )
        self.notify("notifications/initialized")
        self.server_info = init.get("serverInfo")
        self.capabilities = init.get("capabilities")
        self.ready_seconds = time.monotonic() - self.started_monotonic
        return init

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def unconfirmed(self) -> bool:
        """A request timed out and the worker, still alive, has not answered it since: its outcome is unknown and
        it may still be running."""
        with self._lock:
            return bool(self._unanswered) and self.alive()

    def close(self, grace: float = 8.0) -> int | None:
        try:
            return self._stop(grace)
        finally:
            if not self.alive() and self._compiler_temp is not None:
                directory, self._compiler_temp = self._compiler_temp, None
                directory.cleanup()

    def _stop(self, grace: float) -> int | None:
        proc = self._proc
        if proc is None:
            return None
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._signal_group(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._signal_group(signal.SIGKILL)
                proc.wait(timeout=5)
        # The launcher can die while the server, compiler or emulator it started live on
        # (they share our pipe, so they never see end-of-file). Reap the whole session.
        if self._group_exists():
            self._signal_group(signal.SIGTERM)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and self._group_exists():
                time.sleep(0.05)
            if self._group_exists():
                self._signal_group(signal.SIGKILL)
        return proc.returncode

    def _group_exists(self) -> bool:
        try:
            os.killpg(self._proc.pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _signal_group(self, sig: int) -> None:
        try:
            os.killpg(self._proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    # -- wire ------------------------------------------------------------
    def _read_stdout(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self.output_lines += 1
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self.stderr_tail.append("[unparsed stdout] " + line)
                continue
            if "id" in message and ("result" in message or "error" in message):
                with self._lock:
                    waiter = self._pending.pop(message["id"], None)
                    self._unanswered.discard(message["id"])
                if waiter is not None:
                    waiter.put(message)
            elif "id" in message and "method" in message:
                # Server -> client request. We advertise no client capabilities,
                # so refuse explicitly instead of leaving the server waiting.
                self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {"code": -32601, "message": "Client capability not supported"},
                    }
                )
            else:
                self.notifications.append(message)
        with self._lock:
            waiters, self._pending = list(self._pending.values()), {}
        for waiter in waiters:
            waiter.put({"error": {"code": -32000, "message": "Engine process exited"}})

    def _read_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        for line in self._proc.stderr:
            self.output_lines += 1
            self.stderr_tail.append(line)
            del self.stderr_tail[:-400]

    def _send(self, obj: dict) -> None:
        if not self.alive():
            raise EngineError("Engine process is not running", "".join(self.stderr_tail[-20:]))
        with self._write_lock:
            self._proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
            self._proc.stdin.flush()

    def notify(self, method: str, params: dict | None = None) -> None:
        obj: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            obj["params"] = params
        self._send(obj)

    def request(
        self, method: str, params: dict | None = None, timeout: float = 60.0, cancel: threading.Event | None = None
    ) -> dict:
        """One JSON-RPC request. With ``cancel``, setting that event asks the engine to stop through MCP's own
        cancellation (``notifications/cancelled`` for this request id) and raises EngineCancelled at once."""
        waiter: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._seq += 1
            request_id = self._seq
            self._pending[request_id] = waiter
        obj: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            obj["params"] = params
        self._send(obj)
        try:
            message = self._wait(waiter, request_id, timeout, cancel)
        except queue.Empty:
            with self._lock:
                self._pending.pop(request_id, None)
                self._unanswered.add(request_id)
            # The engine may still complete the operation. Callers must treat
            # this as "outcome unknown", never as "did not happen".
            raise EngineError(f"Timed out waiting for {method} after {timeout}s (outcome unknown)")
        if "error" in message:
            raise EngineError(f"{method} failed: {message['error'].get('message')}", message["error"])
        return message["result"]

    def _wait(self, waiter: queue.Queue, request_id: int, timeout: float, cancel: threading.Event | None) -> dict:
        if cancel is None:
            return waiter.get(timeout=timeout)
        deadline = time.monotonic() + timeout
        while True:
            if cancel.is_set():
                with self._lock:
                    self._pending.pop(request_id, None)
                reason = getattr(cancel, "reason", None) or "Cancelled by the user."
                try:
                    self.notify("notifications/cancelled", {"requestId": request_id, "reason": reason})
                except (EngineError, OSError) as error:
                    raise EngineCancelled(f"Cancelled; the engine could not be told ({error})") from error
                raise EngineCancelled(reason)
            left = deadline - time.monotonic()
            if left <= 0:
                raise queue.Empty
            try:
                return waiter.get(timeout=min(0.25, left))
            except queue.Empty:
                continue

    # -- MCP conveniences -------------------------------------------------
    def list_tools(self) -> tuple[list[dict], int]:
        tools: list[dict] = []
        cursor, pages = None, 0
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(result.get("tools", []))
            pages += 1
            cursor = result.get("nextCursor")
            if not cursor:
                return tools, pages

    def call_tool(
        self, name: str, arguments: dict | None = None, timeout: float = 900.0, cancel: threading.Event | None = None
    ) -> dict:
        """Return the complete raw MCP tool result, unmodified."""
        return self.request("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout, cancel=cancel)

    def __enter__(self) -> EngineProcess:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()
