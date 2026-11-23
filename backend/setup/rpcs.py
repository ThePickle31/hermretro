"""The Setup page's RPCs: status, doctor, activity, studio_profile, install and remove_tools. Declared with
@rpc; registered in this order (backend/hermes/declare.py)."""

from __future__ import annotations

import contextlib
import math
import time
from pathlib import Path

from ..broker import (
    BrokerNotRunning,
    BrokerUnavailable,
    BrokenBroker,
    LegacyBrokerHello,
    OtherCopyBusy,
    request_shutdown,
)
from ..hermes import host
from ..hermes.declare import rpc
from ..system import host as host_os, paths
from ..system.events import emit
from . import progress as onboarding, provision, recovery, studio_profile

logger = host.logger  # one logger for the Hermes side of the backend,

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.

_COMPONENT_LABELS = {
    "node": "Node.js",
    "runtime": "Chromatic engine",
    "cli": "GB Studio CLI",
    "gbdk": "GBDK compiler",
    "python": "Python (emulator)",
    "pyboy": "PyBoy emulator",
    "pillow": "Pillow imaging",
    "uv": "uv installer",
    "desktop": "GB Studio desktop editor",
}


_OPTIONAL_COMPONENTS = {"desktop"}


def _platform_report() -> dict:
    found = host_os.describe()
    reported = provision._node_platform()  # cached per Node executable
    node_arch = reported[1] if reported else None
    return {
        **found,
        "node_arch": node_arch,
        "qualified": found["supported"]
        and not found["rosetta"]
        and found["machine"] in ("arm64", "x64")
        and node_arch in (None, found["machine"]),
    }


# The backend code this gateway process loaded. When the files on disk change (a plugin update), the running
# Hermes keeps the old code until it restarts: the page says so.
LOADED_FINGERPRINT = paths.code_fingerprint()


BROKER_STOP_WAIT = 15.0  # seconds a stopping broker gets to close its workers


_REMOVE_BUSY = (
    "A game is open in a chat or an install is running. Close those chats (or wait for the install), then try again."
)


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


@rpc("status")
def rpc_status(ctx):
    def status(params, *, session_id=None, **_kwargs):
        try:
            node = paths.find_node()
            answer = {
                "ok": True,
                "plugin": {
                    "id": paths.PLUGIN_ID,
                    "version": paths.PLUGIN_VERSION,
                    # The profile Hermes installed this copy into: updates run there.
                    "installed_in": studio_profile.installed_in(),
                },
                # Linux and macOS on arm64 or x64 are supported alike; Rosetta works but is slow.
                "platform": _platform_report(),
                "node": {
                    "found": node["found"],
                    "version": node["version"],
                    "required": node["required"],
                    "ok": node["ok"],
                },
                "engine": paths.verify_engine(),
                "deps": provision.summary(),
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                "broker": {"running": False},
                "project": None,
                "profile": studio_profile.describe(host._data_dir().parents[1]),
                "restart_needed": paths.code_fingerprint() != LOADED_FINGERPRINT,
            }
            client, error = host.try_connect(paths.runtime_dir())  # never starts the broker
            if client is None:
                if error is not None and not isinstance(error, BrokerNotRunning):
                    answer["broker"]["running"] = None
            else:
                with client:
                    answer["broker"]["running"] = True
                    # The page names the focused chat as "chat": a "session_id" parameter would make the
                    # gateway authorize it as a live session and fail the call for a draft chat.
                    wanted = (params or {}).get("chat") or session_id or (params or {}).get("session_id")
                    try:
                        lane = client.request(
                            {"op": "lane_status", "profile": host._profile_identity(), "session_id": wanted}
                        ).get("lane")
                    except (BrokerUnavailable, ValueError):
                        lane = None
                    if lane and lane.get("selected_root"):
                        answer["project"] = {
                            "root": lane["selected_root"],
                            "name": Path(lane["selected_root"]).name,
                            "emulator_active": bool(lane.get("emulator_active")),
                            "writer": bool(lane.get("writer")),
                        }
            return answer
        except Exception as error:
            logger.exception("hermretro status failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return status


@rpc("doctor")
def rpc_doctor(ctx):
    def doctor(params, *, session_id=None, **_kwargs):
        try:
            with host.ensure_broker() as client:
                answer = client.request({"op": "doctor", "probe": bool((params or {}).get("probe"))})
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            data = answer["result"].get("structuredContent") or {}
            components = []
            for item in data.get("components") or []:
                components.append(
                    {
                        "id": item.get("id"),
                        "label": _COMPONENT_LABELS.get(item.get("id"), item.get("id")),
                        "status": item.get("status")
                        if item.get("status") in ("ready", "missing", "incompatible")
                        else "unknown",
                        "required": item.get("requiredVersion"),
                        "detected": item.get("detectedVersion"),
                        "optional": item.get("id") in _OPTIONAL_COMPONENTS,
                        "probe": item.get("probeStatus"),
                        # An optional part that is simply absent needs no diagnostics on the page.
                        "detail": ""
                        if item.get("status") == "ready"
                        or (item.get("id") in _OPTIONAL_COMPONENTS and item.get("status") == "missing")
                        else "; ".join(item.get("detectionEvidence") or [])[:300],
                    }
                )
            ready = {task: bool(info.get("ready")) for task, info in (data.get("tasks") or {}).items()}
            return {
                "ok": True,
                "ready": ready,
                "components": components,
                "missing_required": [c["id"] for c in components if c["status"] != "ready" and not c["optional"]],
                "setup_root": (data.get("roots") or {}).get("setupRoot"),
            }
        except BrokerUnavailable as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro doctor failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return doctor


@rpc("activity")
def rpc_activity(ctx):
    """Live development view for one chat: project, last build, the latest emulator frame and a
    short log. Read from the broker's memory; never starts the broker or a worker."""

    def activity(params, *, session_id=None, **_kwargs):
        try:
            params = params or {}
            ids = [value for value in (params.get("chat"), params.get("stored"), session_id) if value]
            client, error = host.try_connect(paths.runtime_dir())
            if client is None:
                if error is not None and not isinstance(error, BrokerNotRunning):
                    return {"ok": False, "error": str(error)}
                return {"ok": True, "lane": None, "matched": None, "running": False}
            with client:
                answer = client.request(
                    {"op": "activity", "profile": host._profile_identity(), "ids": ids, "limit": params.get("limit")}
                )
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            frame = answer.get("frame")
            if frame:
                answer["frame"] = {
                    "t": frame["t"],
                    "tool": frame["tool"],
                    "frame": frame.get("frame"),
                    "src": f"data:{frame['mimeType']};base64,{frame['data']}",
                }
            answer["running"] = True
            return answer
        except BrokerUnavailable as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro activity failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return activity


@rpc("studio_profile")
def rpc_studio_profile(ctx):
    """Finish the dedicated profile after the page has created it with Hermes's profiles.create."""

    def finish(params, **_kwargs):
        try:
            finished = studio_profile.finish(host._data_dir().parents[1])
            if finished.get("ok"):
                emit("setup.studio_profile_ready", profile=finished.get("profile"))
            return finished
        except studio_profile.StudioProfileError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro studio profile setup failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return finish


# How a broker from before the install's cancel answers install_cancel: it has no such op, so the request falls
# through to the lane ops, which need a conversation owner the page never sends.
_NO_CANCEL = frozenset({"IDENTITY_REQUIRED", "UNKNOWN_OP"})
_NO_CANCEL_MESSAGE = (
    "This install is run by an older hermretro background process that cannot cancel it, so it is still running. "
    "Wait for it to finish: this page moves on when the tools are verified."
)
_REMOVE_WORKER = (
    "The last toolchain installer did not confirm it stopped, so the tools folder may still be in use. Quit and "
    "reopen Hermes, then try again."
)
_START_WINDOW = 60.0
_START_EXPIRED = "The install start expired. Check the install status and try again."
_LEGACY_BUSY = "The previous version of hermretro is still running games. Finish or close those chats, then try again."


def _numeric_deadline(value) -> bool:
    return type(value) in (int, float) and 0 < value < math.inf


def _install_connect(*, retire_legacy: bool):
    run = paths.runtime_dir()
    if not retire_legacy:
        return host.try_connect(run)
    deadline = time.monotonic() + BROKER_STOP_WAIT
    client, error = host.try_connect(run, retire_broken=True, deadline=deadline)
    if not isinstance(error, BrokenBroker):
        return client, error
    if not error.stopping:
        raise OtherCopyBusy(_LEGACY_BUSY) from error
    # An acknowledged shutdown can still be closing workers. Wait for election release, then read
    # the journal or the broker that replaced it. This action never starts a broker.
    with _broker_lock(run, seconds=max(0, deadline - time.monotonic())) as held:
        if not held:
            raise BrokerUnavailable("The previous hermretro broker is still stopping.") from error
    return host.try_connect(run, deadline=deadline)


def _valid_install(install, *, starting: bool = False) -> bool:
    if not isinstance(install, dict):
        return False
    state = install.get("state")
    if not isinstance(state, str):
        return False
    if state == "running" or (starting and state in recovery.TERMINAL):
        run_id = install.get("run_id")
        return isinstance(run_id, str) and bool(run_id.strip())
    return not starting and (state == "idle" or state in recovery.TERMINAL)


@rpc("install")
def rpc_install(ctx):
    """The page's own toolchain install: ``{"action": "status"}`` (passive, never starts the broker),
    ``prepare_start`` (issue an admission deadline), ``start_admitted`` or ``cancel`` for a named run.
    Status can confirm a named admission expired before the status was read."""

    def install(params, **_kwargs):
        answer = {}
        starting = False
        try:
            params = params or {}
            action = params.get("action") or "status"
            if action == "prepare_start":
                return {"ok": True, "admission": time.monotonic() + _START_WINDOW}
            starting = action in ("start", "start_fenced", "start_admitted")
            admission = params.get("admission")
            # Sample before reading status, so an idle snapshot cannot predate admission expiry.
            now = time.monotonic()
            expires_at = params.get("expires_at") if action == "start_fenced" else None
            root = paths.setup_root()
            answer = {
                "ok": True,
                "manifest": onboarding.manifest(),
                "root": str(root),
                "space": recovery.free_space(root),
            }
            if starting:
                if action == "start_admitted":
                    answer["admission"] = admission
                    now = time.monotonic()
                    valid = _numeric_deadline(admission) and now < admission <= now + _START_WINDOW
                else:
                    valid = action == "start" or (_numeric_deadline(expires_at) and expires_at > time.time() * 1000)
                if not valid:
                    return {
                        **answer,
                        "ok": False,
                        "code": "START_EXPIRED",
                        "error": _START_EXPIRED,
                    }
                broker = host.ensure_broker(deadline=admission) if action == "start_admitted" else host.ensure_broker()
                with broker as client:
                    if action == "start_admitted":
                        reply = client.request({"op": "install_start", "admit_until": admission})
                    else:
                        expires_at = min(expires_at or math.inf, (time.time() + client.control_timeout) * 1000)
                        answer["start_expires_at"] = expires_at
                        reply = client.request({"op": "install_start", "admit_before": expires_at})
            elif action in ("status", "cancel"):
                if action == "status" and _numeric_deadline(admission) and now >= admission:
                    answer["expired_admission"] = admission
                client, error = _install_connect(
                    retire_legacy=action == "status" and params.get("retire_legacy") is True
                )
                if client is None:
                    if action == "status" and isinstance(error, LegacyBrokerHello):
                        return {**answer, "ok": False, "code": "BROKER_LEGACY", "error": str(error)}
                    if error is not None and not isinstance(error, BrokerNotRunning):
                        raise BrokerUnavailable(str(error)) from error
                    if action == "cancel":
                        raise BrokerUnavailable("No broker is running to cancel the install.")
                    # No broker: nothing runs. The last install, as its journal tells it (``interrupted`` when its
                    # broker ended mid-run), so a reload shows what happened instead of a fresh start.
                    last = recovery.recovered(root, None)
                    answer["install"] = onboarding.progress(last, root) if last is not None else {"state": "idle"}
                    return answer
                with client:
                    if action == "status":
                        reply = client.request({"op": "install_status"})
                    else:
                        reply = client.request({"op": "install_cancel", "run_id": params.get("run_id")})
            else:
                return {"ok": False, "error": f"Unknown action {action!r}."}
            if reply.get("ok") is not True:
                denied = reply.get("denied")
                if (
                    reply.get("ok") is not False
                    or reply.get("dispatched") is not False
                    or not isinstance(denied, dict)
                    or not isinstance(denied.get("code"), str)
                    or not denied["code"]
                ):
                    raise BrokerUnavailable(
                        reply.get("error") or "The background process did not confirm the install status."
                    )
                if action == "cancel" and denied.get("code") in _NO_CANCEL:
                    # A broker from before cancel: it answers install_cancel as an ownerless lane op
                    # (IDENTITY_REQUIRED), and the install it runs goes on.
                    return {**answer, "ok": False, "code": "CANCEL_UNSUPPORTED", "error": _NO_CANCEL_MESSAGE}
                if denied.get("code") == "UNKNOWN_OP":
                    # An older broker kept alive by a running game; it retires once that game is closed.
                    return {
                        **answer,
                        "ok": False,
                        "code": "BROKER_OUTDATED",
                        "error": "hermretro is still running an older session for a game in a chat. Close "
                        "that game's chat (or wait a few minutes), then try again.",
                    }
                return {
                    **answer,
                    "ok": False,
                    "code": denied.get("code"),
                    "error": denied.get("message") or "The install request was refused.",
                }
            install_state = reply.get("install")
            if not _valid_install(install_state, starting=starting):
                raise BrokerUnavailable("The background process returned an invalid install status.")
            answer["install"] = install_state
            return answer
        except OtherCopyBusy as error:
            return {**answer, "ok": False, "code": "BUSY", "error": str(error)}
        except (BrokerUnavailable, ValueError) as error:
            message = f"Install start was unconfirmed. {error}" if starting else str(error)
            return {**answer, "ok": False, "code": "UNAVAILABLE", "error": message}
        except Exception as error:
            logger.exception("hermretro install failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return install


@rpc("remove_tools")
def rpc_remove_tools(ctx):
    """Delete the downloaded tools (Setup's "Remove downloaded tools"). Stops an idle broker first; refused while
    a game's chat has a live worker or an install runs. Games and the library are not touched."""

    def remove(params, **_kwargs):
        try:
            run = paths.runtime_dir()
            client, error = host.try_connect(run)  # never starts the broker
            if error is not None and not isinstance(error, BrokerNotRunning):
                raise BrokerUnavailable(str(error)) from error
            if client is not None:
                with client:
                    if not request_shutdown(client):
                        return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
            # The broker's election lock: held by a running broker until it exits, and while we hold it any
            # broker another call starts loses the election and exits, so nothing runs from the folder.
            with _broker_lock(run) as held:
                if not held:
                    return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
                if recovery.worker_left(recovery.read_journal()):
                    # The broker exited, but the installer worker it could not close may still use the folder.
                    return {"ok": False, "code": "WORKER_STILL_RUNNING", "error": _REMOVE_WORKER}
                removed = provision.remove_downloads()
            if removed.get("ok"):
                emit("setup.tools_removed", root=removed.get("root"))
            return removed
        except provision.ProvisionError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except BrokerUnavailable as error:
            return {"ok": False, "code": "UNAVAILABLE", "error": str(error)}
        except Exception as error:
            logger.exception("hermretro remove_tools failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return remove
