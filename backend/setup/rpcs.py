"""The Setup page's RPCs: status, doctor, activity, studio_profile, install, remove_tools, releases, and the factory
reset's reset_plan and reset (reset_rpcs.py). Declared with
@rpc; registered in this order (backend/hermes/declare.py)."""

from __future__ import annotations

import math
import time
from pathlib import Path

from ..broker import (
    BrokerNotRunning,
    BrokerUnavailable,
    BrokenBroker,
    LegacyBrokerHello,
    OtherCopyBusy,
)
from ..hermes import host
from ..hermes.declare import rpc
from ..system import flags, host as host_os, paths
from ..system.events import emit
from . import (
    claude_login,
    downloads,
    prepared_copies,
    progress as onboarding,
    provision,
    recovery,
    releases,
    studio_profile,
    studio_providers,
)
from . import reset_rpcs as _reset_rpcs_mod
from .broker_stop import BROKER_STOP_WAIT, broker_lock, broker_stopped

logger = host.logger  # one logger for the Hermes side of the backend,

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.

_COMPONENT_LABELS = {
    "node": "Node.js",
    "runtime": "hermretro engine",
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
                    # The folder this process loaded the plugin from: with restart_needed, whether it runs what a
                    # profile loads now.
                    "root": str(paths.PLUGIN_ROOT),
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
                "deps": prepared_copies.summary(),
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                # The feature flags that are on (page/app/flags.js): the page shows what they hide.
                "flags": flags.enabled(ctx.get_config),
                "broker": {"running": False},
                "project": None,
                "profile": studio_profile.describe(host._data_dir().parents[1]),
                # The files changed since it loaded them, or it loaded them across a change to the engine.
                "restart_needed": paths.code_fingerprint() != LOADED_FINGERPRINT
                or paths.engine_identity() != paths.ENGINE_IDENTITY,
            }
            # Each look at Setup brings the studio profile up to date with the installing profile's providers; a
            # caller that only reads (`sync: false`, the benchmark's check) writes nothing.
            if (params or {}).get("sync", True) is not False:
                studio_providers.sync_soon(host._data_dir().parents[1])
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
                    "src": f"data:{frame['mimeType']};base64,{frame['data']}" if frame.get("data") else None,
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
    """Create or repair the dedicated studio profile."""

    def finish(params, **_kwargs):
        try:
            finished = studio_profile.finish(host._data_dir().parents[1], create=(params or {}).get("create") is True)
            if finished.get("ok"):
                emit("setup.studio_profile_ready", profile=finished.get("profile"))
            return finished
        except studio_profile.StudioProfileError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro studio profile setup failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return finish


@rpc("studio_claude_sign_in")
def rpc_studio_claude_sign_in(ctx):
    """Sign the studio profile in to Claude with a login of its own, in the browser (DirectSDK only)."""

    def sign_in(params, **_kwargs):
        try:
            return studio_providers.sign_in_to_claude(host._data_dir().parents[1])
        except (studio_profile.StudioProfileError, claude_login.SignInError) as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro Claude sign-in failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return sign_in


# How a broker from before the install's cancel answers install_cancel: it has no such op, so the request falls
# through to the lane ops, which need a conversation owner the page never sends.
_NO_CANCEL = frozenset({"IDENTITY_REQUIRED", "UNKNOWN_OP"})
_NO_CANCEL_MESSAGE = (
    "This install is run by an older hermretro background process that cannot cancel it, so it is still running. "
    "Wait for it to finish: this page moves on when the tools are verified."
)
_START_WINDOW = 60.0
_START_EXPIRED = "The install start expired. Check the install status and try again."
_LEGACY_BUSY = "The previous version of hermretro is still running games. Finish or close those chats, then try again."
# The loaded fingerprint of the published v0.0.9 backend (protocol 2). It has install_status but no run_id.
_UNNAMED_INSTALL_BROKER = "2013a14d51f86e69d64a840a"


def _numeric_deadline(value) -> bool:
    return type(value) in (int, float) and 0 < value < math.inf


def _admission_pending(admission, boot_id: str | None, now: float) -> bool:
    if isinstance(admission, dict):
        if boot_id is not None and admission.get("boot_id") != boot_id:
            return False
        admission = admission.get("deadline")
    # A numeric grant saved by an older Desktop can still have a request in flight on this boot.
    return _numeric_deadline(admission) and now < admission <= now + _START_WINDOW


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
    with broker_lock(run, seconds=max(0, deadline - time.monotonic())) as held:
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
                boot_id = host_os.boot_id()
                if boot_id is None:
                    raise BrokerUnavailable("The gateway's boot identity could not be read.")
                return {"ok": True, "admission": {"boot_id": boot_id, "deadline": time.monotonic() + _START_WINDOW}}
            starting = action in ("start", "start_fenced", "start_admitted")
            admission = params.get("admission")
            boot_id = host_os.boot_id() if isinstance(admission, dict) else None
            # Sample before reading status, so an idle snapshot cannot predate admission expiry.
            now = time.monotonic()
            expired = (
                {"expired_admission": admission}
                if action == "status" and admission is not None and not _admission_pending(admission, boot_id, now)
                else {}
            )
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
                    valid = boot_id is not None and _admission_pending(admission, boot_id, time.monotonic())
                else:
                    valid = action == "start" or (_numeric_deadline(expires_at) and expires_at > time.time() * 1000)
                if not valid:
                    return {
                        **answer,
                        "ok": False,
                        "code": "START_EXPIRED",
                        "error": _START_EXPIRED,
                    }
                deadline = admission["deadline"] if action == "start_admitted" else None
                broker = host.ensure_broker(deadline=deadline) if deadline is not None else host.ensure_broker()
                with broker as client:
                    if deadline is not None:
                        reply = client.request({"op": "install_start", "admit_until": deadline})
                    else:
                        expires_at = min(expires_at or math.inf, (time.time() + client.control_timeout) * 1000)
                        answer["start_expires_at"] = expires_at
                        reply = client.request({"op": "install_start", "admit_before": expires_at})
            elif action in ("status", "cancel"):
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
                    # No broker: report the last install as its journal tells it (``interrupted`` when its
                    # broker ended mid-run), so a reload shows what happened instead of a fresh start.
                    last = recovery.recovered(root, None)
                    answer["install"] = onboarding.progress(last, root) if last is not None else {"state": "idle"}
                    if recovery.worker_left(last):
                        answer["install"]["worker_left"] = True
                    return {**answer, **expired}
                with client:
                    unnamed_broker = client.hello.get("loaded_fingerprint") == _UNNAMED_INSTALL_BROKER
                    if action == "status":
                        reply = client.request({"op": "install_status"})
                    elif unnamed_broker:
                        return {**answer, "ok": False, "code": "CANCEL_UNSUPPORTED", "error": _NO_CANCEL_MESSAGE}
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
            legacy_progress = (
                action == "status"
                and unnamed_broker
                and isinstance(install_state, dict)
                and install_state.get("state") == "running"
                and "run_id" not in install_state
            )
            if not legacy_progress and not _valid_install(install_state, starting=starting):
                raise BrokerUnavailable("The background process returned an invalid install status.")
            if "worker_left" in install_state and type(install_state["worker_left"]) is not bool:
                raise BrokerUnavailable("The background process returned an invalid install status.")
            if (
                action == "status"
                and "worker_left" not in install_state
                and recovery.worker_left(recovery.read_journal())
            ):
                install_state = {**install_state, "worker_left": True}
            if legacy_progress:
                answer["legacy_progress"] = True
            answer["install"] = install_state
            return {**answer, **expired}
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
            with broker_stopped() as refused:
                if refused:
                    return refused
                removed = downloads.remove_downloads()
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


@rpc("releases")
def rpc_releases(ctx):
    """hermretro's published releases and what each changed, for the page's update card (releases.py)."""

    def answer(params, **_kwargs):
        return releases.latest()

    return answer


@rpc("reset_plan")
def rpc_reset_plan(ctx):
    """What each part of hermretro's data holds, for the factory reset's choices (reset.py)."""
    return _reset_rpcs_mod.rpc_reset_plan(ctx)


@rpc("reset")
def rpc_reset(ctx):
    """One step of the factory reset: stop the broker (``part`` stop) or delete one part (reset.py)."""
    return _reset_rpcs_mod.rpc_reset(ctx)
