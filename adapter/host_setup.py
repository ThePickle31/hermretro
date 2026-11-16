"""The Setup page's RPCs: status, install, remove_tools, studio_profile, activity and doctor.
Re-exported by hermes_host."""
from __future__ import annotations

import contextlib
import time
from pathlib import Path

from . import hermes_host as host, host_os, onboarding, paths, provision, studio_profile
from .client import BrokerUnavailable

logger = host.logger   # one logger for the host adapter, as before the split

# Shared helpers (the data folder, the profile, the library, the broker client) stay in hermes_host and are
# looked up there at call time, so one patch of hermes_host.<name> reaches every module.

_COMPONENT_LABELS = {
    "node": "Node.js", "runtime": "Chromatic engine", "cli": "GB Studio CLI", "gbdk": "GBDK compiler",
    "python": "Python (emulator)", "pyboy": "PyBoy emulator", "pillow": "Pillow imaging", "uv": "uv installer",
    "desktop": "GB Studio desktop editor",
}
_OPTIONAL_COMPONENTS = {"desktop"}


def _platform_report() -> dict:
    found = host_os.describe()
    reported = provision._node_platform()   # cached per Node executable
    node_arch = reported[1] if reported else None
    return {**found, "node_arch": node_arch,
            "qualified": found["supported"] and not found["rosetta"] and found["machine"] in ("arm64", "x64")
            and node_arch in (None, found["machine"])}


# The adapter code this gateway process loaded. When the files on disk change (a plugin update), the running
# Hermes keeps the old code until it restarts: the page says so.
LOADED_FINGERPRINT = paths.code_fingerprint()


def rpc_status(ctx):
    def status(params, *, session_id=None, **_kwargs):
        try:
            node = paths.find_node()
            answer = {
                "ok": True,
                "plugin": {"id": paths.PLUGIN_ID, "version": paths.PLUGIN_VERSION},
                # Linux and macOS on arm64 or x64 are supported alike; Rosetta works but is slow.
                "platform": _platform_report(),
                "node": {"found": node["found"], "version": node["version"], "required": node["required"],
                         "ok": node["ok"]},
                "engine": paths.verify_engine(),
                "deps": provision.summary(),
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                "broker": {"running": False},
                "project": None,
                "profile": studio_profile.describe(host._data_dir().parents[1]),
                "restart_needed": paths.code_fingerprint() != LOADED_FINGERPRINT,
            }
            client, _error = host.try_connect(paths.runtime_dir())  # never starts the broker
            if client is not None:
                with client:
                    answer["broker"]["running"] = True
                    # The page names the focused chat as "chat": a "session_id" parameter would make the
                    # gateway authorize it as a live session and fail the call for a draft chat.
                    wanted = (params or {}).get("chat") or session_id or (params or {}).get("session_id")
                    lane = client.request({"op": "lane_status", "profile": host._profile_identity(),
                                           "session_id": wanted}).get("lane")
                    if lane and lane.get("selected_root"):
                        answer["project"] = {"root": lane["selected_root"], "name": Path(lane["selected_root"]).name,
                                             "emulator_active": bool(lane.get("emulator_active")),
                                             "writer": bool(lane.get("writer"))}
            return answer
        except Exception as error:
            logger.exception("hermretro status failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return status


def rpc_install(ctx):
    """The page's own toolchain install: ``{"action": "status"}`` (passive, never starts the broker)
    or ``{"action": "start"}``. Always returns the download list, so the page can show it first."""
    def install(params, **_kwargs):
        try:
            action = (params or {}).get("action") or "status"
            answer = {"ok": True, "manifest": onboarding.manifest(), "root": str(paths.setup_root()),
                      "install": {"state": "idle"}}
            if action == "start":
                with host.ensure_broker() as client:
                    reply = client.request({"op": "install_start"})
            elif action == "status":
                client, _error = host.try_connect(paths.runtime_dir())
                if client is None:
                    return answer
                with client:
                    reply = client.request({"op": "install_status"})
            else:
                return {"ok": False, "error": f"Unknown action {action!r}."}
            if not reply.get("ok"):
                denied = reply.get("denied") or {}
                if denied.get("code") == "UNKNOWN_OP":
                    # An older broker kept alive by a running game; it retires once that game is closed.
                    return {**answer, "ok": False, "code": "BROKER_OUTDATED",
                            "error": "hermretro is still running an older session for a game in a chat. Close "
                                     "that game's chat (or wait a few minutes), then try again."}
                return {**answer, "ok": False, "code": denied.get("code"),
                        "error": denied.get("message") or reply.get("error") or "The install could not start."}
            answer["install"] = reply.get("install") or {"state": "idle"}
            return answer
        except BrokerUnavailable as error:
            return {"ok": False, "code": "UNAVAILABLE", "error": str(error)}
        except Exception as error:
            logger.exception("hermretro install failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return install


def rpc_remove_tools(ctx):
    """Delete the downloaded tools (Setup's "Remove downloaded tools"). Stops an idle broker first; refused while
    a game's chat has a live worker or an install runs. Games and the library are not touched."""
    def remove(params, **_kwargs):
        try:
            run = paths.runtime_dir()
            client, _error = host.try_connect(run)   # never starts the broker
            if client is not None:
                with client:
                    reply = client.request({"op": "shutdown"})
                if not reply.get("ok"):
                    return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
            # The broker's election lock: held by a running broker until it exits, and while we hold it any
            # broker another call starts loses the election and exits, so nothing runs from the folder.
            with _broker_lock(run) as held:
                if not held:
                    return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
                return provision.remove_downloads()
        except provision.ProvisionError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro remove_tools failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return remove


BROKER_STOP_WAIT = 15.0  # seconds a stopping broker gets to close its workers
_REMOVE_BUSY = ("A game is open in a chat or an install is running. Close those chats (or wait for the install), "
                "then try again.")


@contextlib.contextmanager
def _broker_lock(run: Path, seconds: float | None = None):
    """Hold the broker election lock, waiting for a stopping broker to let go of it. Yields False on timeout."""
    import fcntl
    with open(run / "broker.lock", "a+") as handle:
        deadline = time.monotonic() + (BROKER_STOP_WAIT if seconds is None else seconds)
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.1)
        try:
            time.sleep(0.5)  # workers exit when the broker's pipe closes; give them a moment
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def rpc_studio_profile(ctx):
    """Finish the dedicated profile after the page has created it with Hermes's profiles.create."""
    def finish(params, **_kwargs):
        try:
            return studio_profile.finish(host._data_dir().parents[1])
        except studio_profile.StudioProfileError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro studio profile setup failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return finish


def rpc_activity(ctx):
    """Live development view for one chat: project, last build, the latest emulator frame and a
    short log. Read from the broker's memory; never starts the broker or a worker."""
    def activity(params, *, session_id=None, **_kwargs):
        try:
            params = params or {}
            ids = [value for value in (params.get("chat"), params.get("stored"), session_id) if value]
            client, _error = host.try_connect(paths.runtime_dir())
            if client is None:
                return {"ok": True, "lane": None, "matched": None, "running": False}
            with client:
                answer = client.request({"op": "activity", "profile": host._profile_identity(), "ids": ids,
                                         "limit": params.get("limit")})
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            frame = answer.get("frame")
            if frame:
                answer["frame"] = {"t": frame["t"], "tool": frame["tool"], "frame": frame.get("frame"),
                                   "src": f"data:{frame['mimeType']};base64,{frame['data']}"}
            answer["running"] = True
            return answer
        except Exception as error:
            logger.exception("hermretro activity failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return activity


def rpc_doctor(ctx):
    def doctor(params, *, session_id=None, **_kwargs):
        try:
            with host.ensure_broker() as client:
                answer = client.request({"op": "doctor", "probe": bool((params or {}).get("probe"))})
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            data = (answer["result"].get("structuredContent") or {})
            components = []
            for item in data.get("components") or []:
                components.append({
                    "id": item.get("id"), "label": _COMPONENT_LABELS.get(item.get("id"), item.get("id")),
                    "status": item.get("status") if item.get("status") in ("ready", "missing", "incompatible") else "unknown",
                    "required": item.get("requiredVersion"), "detected": item.get("detectedVersion"),
                    "optional": item.get("id") in _OPTIONAL_COMPONENTS,
                    "probe": item.get("probeStatus"),
                    # An optional part that is simply absent needs no diagnostics on the page.
                    "detail": "" if item.get("status") == "ready"
                    or (item.get("id") in _OPTIONAL_COMPONENTS and item.get("status") == "missing")
                    else "; ".join(item.get("detectionEvidence") or [])[:300],
                })
            ready = {task: bool(info.get("ready")) for task, info in (data.get("tasks") or {}).items()}
            return {"ok": True, "ready": ready, "components": components,
                    "missing_required": [c["id"] for c in components if c["status"] != "ready" and not c["optional"]],
                    "setup_root": (data.get("roots") or {}).get("setupRoot")}
        except BrokerUnavailable as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro doctor failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return doctor
