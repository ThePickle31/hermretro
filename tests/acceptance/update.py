"""An update or reload under a running broker: the first call of the newer code runs, and a broker from before
retirement gets nothing dispatched."""

import json
import subprocess
from unittest import mock

from backend.broker import client as client_module
from backend.broker.client import BrokerClient, BrokerRestarting, ensure_broker
from tests.acceptance.fixture import OWNER_A, alive, structured, wait_gone

NEWER_BUILD = "the files of a newer build"


def check_update_replaces_broker(suite, rom_a):
    """A broker whose only worker is idle with its emulator open (what kept the broker of the older code, and every
    new chat's calls failed with ENGINE_PIN_MISMATCH) makes way for the newer code at once: it closes that emulator
    cleanly, the newer code's first call runs on a new broker, and the chat is told on its next call."""
    old = ensure_broker(suite.state)
    old_pid, old_generation = old.hello["pid"], old.hello["broker_generation"]
    suite.brokers.add(old_pid)
    old.call(OWNER_A, "project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
    running = old.call(OWNER_A, "emulator_run", {"romPath": rom_a})
    old.close()
    lease_path = suite.project_a / "artifacts" / ".recording-access" / "lease.json"
    leased = lease_path.exists()

    disk = client_module.paths.code_fingerprint()
    looks = iter([NEWER_BUILD])  # what the newer code sees at its first handshake

    with mock.patch.object(client_module.paths, "code_fingerprint", lambda: next(looks, disk)):
        newer = ensure_broker(suite.state)
    suite.brokers.add(newer.hello["pid"])
    first = newer.call(OWNER_A, "session_status")
    gone = wait_gone([old_pid], 15)
    trace = [json.loads(line) for line in (suite.state / "trace.jsonl").read_text().splitlines()]
    retired = [r for r in trace if r.get("event") == "broker_retired" and r["broker_generation"] == old_generation]
    suite.check(
        "R7",
        "An update under a broker whose idle worker has its emulator open: the newer code's first call runs on a new "
        "broker, the old one released the emulator's lease, and the chat is told its worker restarted",
        not running["result"].get("isError")
        and leased
        and newer.hello["pid"] != old_pid
        and gone
        and first.get("ok")
        and not first["result"].get("isError")
        and structured(first).get("emulatorActive") is False
        and "hermretro was updated" in (first.get("notice") or "")
        and not lease_path.exists()
        and bool(retired)
        and retired[-1].get("workers") == 1,
        old_broker_pid=old_pid,
        new_broker_pid=newer.hello["pid"],
        leased_before=leased,
        notice=first.get("notice"),
        retired=retired[-1] if retired else None,
    )
    newer.request({"op": "shutdown", "force": True})
    newer.close()
    wait_gone([newer.hello["pid"]], 15)


def legacy_spawn(suite):
    """spawn_broker, starting a broker of the releases before retirement (tests/acceptance/legacy_broker.py)."""
    popen = subprocess.Popen

    def as_legacy(command, **kwargs):
        return popen(
            ["tests.acceptance.legacy_broker" if part == "backend.broker" else part for part in command], **kwargs
        )

    def spawn(state_dir, node, *, deadline=None):
        with mock.patch.object(client_module.subprocess, "Popen", as_legacy):
            return suite.spawn_broker(state_dir, node, deadline=deadline)

    return spawn


def check_legacy_broker_gets_nothing(suite, rom_a):
    """The upgrade from a release before retirement: its broker answers ``replace`` as a plain shutdown, busy while a
    worker lives (here idle with its emulator open). The newer code neither uses it (a worker it started would fail
    every call with ENGINE_PIN_MISMATCH) nor stops it: the call answers that the game tools restart later."""
    with mock.patch.object(client_module, "spawn_broker", legacy_spawn(suite)):
        legacy = ensure_broker(suite.state)
    pid, generation = legacy.hello["pid"], legacy.hello["broker_generation"]
    suite.brokers.add(pid)
    legacy.call(OWNER_A, "project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
    running = legacy.call(OWNER_A, "emulator_run", {"romPath": rom_a})
    legacy.close()

    def events(name):
        trace = [json.loads(line) for line in (suite.state / "trace.jsonl").read_text().splitlines()]
        return [r for r in trace if r.get("event") == name]

    dispatched, started = len(events("dispatch")), len(events("broker_started"))
    refused = None
    with mock.patch.object(client_module.paths, "code_fingerprint", lambda: NEWER_BUILD):
        try:
            ensure_broker(suite.state).close()
        except BrokerRestarting as error:
            refused = error
    suite.check(
        "R8",
        "An update over a broker from before retirement whose worker is idle with its emulator open: nothing is "
        "dispatched to it, it is not stopped, and the call is told the game tools restart later",
        not running["result"].get("isError")
        and refused is not None
        and refused.waits is False
        and alive(pid)
        and len(events("dispatch")) == dispatched
        and len(events("broker_started")) == started
        and all(r["broker_generation"] == generation for r in events("dispatch")[-2:]),
        legacy_broker_pid=pid,
        refused=str(refused) if refused else None,
        waits=getattr(refused, "waits", None),
    )
    with BrokerClient(suite.state) as last:
        last.request({"op": "shutdown", "force": True})
    wait_gone([pid], 15)
