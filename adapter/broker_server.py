"""The broker's Unix socket server and its entry point (`python -m adapter.broker` runs main()).

Stdlib only and no Hermes imports.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import signal
import socketserver
import sys
import threading
import time
from pathlib import Path

from . import host_os, paths
from .broker import Broker
from .broker_lane import Denied


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: Broker = self.server.broker  # type: ignore[attr-defined]
        # Kernel-reported; None when the system will not say (the run folder is private and the token secret).
        peer_pid, uid = host_os.peer_credentials(self.request)
        authenticated = False
        with broker.connections_lock:
            broker.connections += 1
        try:
            for raw in self.rfile:
                request = None
                broker.last_activity = time.monotonic()
                try:
                    request = json.loads(raw)
                    if uid is not None and uid != os.getuid():
                        raise Denied("FORBIDDEN", "Peer is not the broker's user.")
                    if not authenticated:
                        if request.get("op") != "hello" or request.get("protocol") != paths.PROTOCOL or \
                                not secrets.compare_digest(str(request.get("token", "")), broker.token):
                            raise Denied("UNAUTHENTICATED", "Handshake required.")
                        authenticated = True
                        response = {"ok": True, "protocol": paths.PROTOCOL, "broker_generation": broker.generation,
                                    "pid": os.getpid(), "code_fingerprint": paths.code_fingerprint(),
                                    "plugin_root": str(paths.PLUGIN_ROOT), "engine": broker.engine_check}
                    elif request.get("op") == "call":
                        request["_client_pid"] = peer_pid  # kernel-reported, for the trace only
                        response = broker.call(request)
                    else:
                        response = broker.control(request)
                except Denied as denial:
                    broker.trace(event="denied", code=denial.code,
                                 tool=request.get("tool") if isinstance(request, dict) else None)
                    response = {"ok": False, "dispatched": False,
                                "denied": {"code": denial.code, "message": str(denial)}}
                except Exception as error:  # surface, never hide
                    broker.trace(event="broker_error", error=f"{type(error).__name__}: {error}"[:300])
                    response = {"ok": False, "dispatched": None, "error": f"{type(error).__name__}: {error}"}
                self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
                self.wfile.flush()
                if not authenticated or broker.stopping.is_set():
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client went away; the engine may still finish its work
        finally:
            with broker.connections_lock:
                broker.connections -= 1
            broker.last_activity = time.monotonic()


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--node", required=True)
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)

    lock_handle = open(state_dir / "broker.lock", "a+")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("election lost: another broker holds this state directory", file=sys.stderr)
        return 3  # before any worker, socket or token is touched

    broker = Broker(state_dir, args.node)
    socket_path = state_dir / "broker.sock"
    socket_path.unlink(missing_ok=True)  # safe: we hold the election lock
    old_umask = os.umask(0o177)
    try:
        server = Server(str(socket_path), Handler)
        token_path = state_dir / "broker.token"
        token_path.unlink(missing_ok=True)
        token_path.write_text(broker.token)
    finally:
        os.umask(old_umask)
    server.broker = broker  # type: ignore[attr-defined]
    broker.trace(event="broker_started", pid=os.getpid(), engine_verified=broker.engine_check.get("verified"))
    # Stop cleanly on any polite signal, so workers close their emulators and release their leases.
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda *_: broker.stopping.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ticks = 0
        while not broker.stopping.wait(0.25):
            ticks += 1
            if ticks % 120 == 0:
                broker.housekeeping()
    finally:
        server.shutdown()
        broker.close_all()
        socket_path.unlink(missing_ok=True)
        (state_dir / "broker.token").unlink(missing_ok=True)
        broker.trace(event="broker_stopped", pid=os.getpid())
    return 0
