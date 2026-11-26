"""The factory reset's RPCs (declared in rpcs.py): `reset_plan` (what each part holds) and `reset` (stop the broker,
or delete one part). The page runs the parts one call at a time, so it can show each step."""

from __future__ import annotations

from pathlib import Path

from ..broker import BrokerUnavailable
from ..hermes import api as hermes_api
from ..hermes import host
from ..player import captures_paused
from ..system.events import emit
from . import provision, reset, studio_profile
from .broker_stop import broker_stopped

logger = host.logger


def _homes() -> list[Path]:
    """The profiles whose hermretro settings a reset clears: this one, and the one hermretro was installed into."""
    homes = [host._data_dir().parents[1]]
    installed = studio_profile.installed_in().get("profile")
    if installed:
        home = hermes_api.profile_dir(installed)
        if home.resolve() != homes[0].resolve():
            homes.append(home)
    return homes


def rpc_reset_plan(ctx):
    def answer(params, **_kwargs):
        try:
            return reset.plan(host._data_dir())
        except Exception as error:
            logger.exception("hermretro reset_plan failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return answer


def rpc_reset(ctx):
    def run(params, **_kwargs):
        part = (params or {}).get("part")
        if part != "stop" and part not in reset.PARTS:
            return {"ok": False, "code": "UNKNOWN_PART", "error": f"There is no part {part!r} to reset."}
        try:
            if part in ("settings", "links"):
                return reset.clear(part, host._data_dir(), _homes())
            # Idle workers close with the broker: a game left open in a chat does not hold the reset back. The player
            # saves no capture meanwhile (it runs in this process, apart from the broker).
            with broker_stopped(replace=True) as refused, captures_paused():
                if refused:
                    return refused
                if part == "stop":
                    return {"ok": True}
                done = reset.clear(part, host._data_dir(), [])
            if part == "toolchain" and done.get("ok"):
                emit("setup.tools_removed", root=done.get("root"))
            return done
        except provision.ProvisionError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except BrokerUnavailable as error:
            return {"ok": False, "code": "UNAVAILABLE", "error": str(error)}
        except Exception as error:
            logger.exception("hermretro reset failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return run
