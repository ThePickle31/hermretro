#!/usr/bin/env python3
"""Broker acceptance run against the real engine, compiler and emulator. Nothing is mocked.

Covers election, identity, private workers, lossless results, art and audio import, source-mode live state,
authoring (symbols, scene transactions, script events), writer handoff, delegated children, hardware gating,
worker and broker crash recovery. It does not cover anything that needs Hermes itself (host-injected identity,
real compaction, pixels reaching a model).

    python tests/acceptance/broker_acceptance.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import traceback
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.broker.client import BrokerClient, ensure_broker  # noqa: E402 - direct script entry point
from tests.acceptance import (  # noqa: E402 - direct script entry point
    art,
    art_limits,
    audio,
    authoring,
    debugging,
    ownership,
    projects,
    recovery,
    replay,
    tool_friction,
)
from tests.acceptance.fixture import HANDOFF, BrokerRun  # noqa: E402 - direct script entry point


def check_election(suite, connections):
    clients: list[BrokerClient] = []
    errors: list[Exception] = []

    def racer():
        try:
            clients.append(ensure_broker(suite.state))
        except Exception as error:  # noqa: BLE001 - every racer's failure is collected and reported
            errors.append(error)

    # Give the workers a deep inherited TMPDIR while keeping the test socket path short.
    suite.observations["inherited_compiler_tmp_bytes"] = len(os.fsencode(suite.compiler_temp))
    with mock.patch.dict(os.environ, {"TMPDIR": str(suite.compiler_temp)}):
        threads = [threading.Thread(target=racer) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    pids = {c.hello.get("pid") for c in clients}
    gens = {c.hello.get("broker_generation") for c in clients}
    suite.brokers.update(pids)
    one_broker = len(pids) == 1 and len(gens) == 1
    suite.check(
        "E1",
        "Four racing lazy starts converge on one broker",
        not errors and len(clients) == 4 and one_broker,
        broker_pids=sorted(pids),
        errors=[repr(error) for error in errors],
    )
    if len(clients) < 2 or not one_broker:
        for client in clients:
            client.close()
        cause = errors[0] if errors else None
        raise RuntimeError("Startup did not provide two connections to the same broker (E1)") from cause
    loser = suite.spawn_broker(suite.state, suite.node)
    loser_code = loser.wait(timeout=10)
    suite.check(
        "E2",
        "A second broker loses the election and exits before starting workers",
        loser_code == 3,
        exit_code=loser_code,
    )
    with BrokerClient(suite.state, token="0" * 64) as bad:
        suite.check(
            "E3",
            "Wrong handshake token is refused",
            bad.hello.get("ok") is False and bad.hello.get("denied", {}).get("code") == "UNAUTHENTICATED",
            response=bad.hello,
        )
    for extra in clients[2:]:
        extra.close()
    control = connections.enter_context(BrokerClient(suite.state))
    return connections.enter_context(clients[0]), connections.enter_context(clients[1]), control


def check_missing_identity(suite, client_a, control):
    before_lanes = len(control.request({"op": "stats"})["lanes"])
    r_none = client_a.call(None, "session_status")
    r_empty = client_a.call({"profile": "s01-profile", "conversation_id": ""}, "session_status")
    r_noprofile = client_a.call({"conversation_id": "conv-A"}, "session_status")
    after_lanes = len(control.request({"op": "stats"})["lanes"])
    suite.check(
        "I1",
        "Missing or empty owner identity is denied without dispatch or worker start",
        all(
            r.get("dispatched") is False and r.get("denied", {}).get("code") == "IDENTITY_REQUIRED"
            for r in (r_none, r_empty, r_noprofile)
        )
        and before_lanes == after_lanes == 0,
        lanes_before=before_lanes,
        lanes_after=after_lanes,
    )


def exercise(suite):
    with ExitStack() as connections:
        client_a, client_b, control = check_election(suite, connections)
        broker_pid = client_a.hello["pid"]
        check_missing_identity(suite, client_a, control)
        first_status, edited_source = projects.create_and_edit(suite, client_a, client_b)
        rom_a, rom_b, hash_a, hash_b = projects.build_roms(suite, client_a, client_b)
        last_frame = projects.check_emulators(suite, client_a, client_b, rom_a, rom_b, hash_a, hash_b)
        replay.check_replay(suite, client_b, rom_b)
        tool_friction.check_tool_friction(suite, client_b, rom_b)
        projects.check_result_fidelity(suite, client_a, rom_a)
        projects.check_owner_identity(suite, client_a, client_b, first_status)
        art.check_art_import(suite, client_b)
        art_limits.check_art_limits(suite, client_b)
        debugging.check_live_state(suite, client_b)
        authoring.check_symbols_and_events(suite, client_b)
        audio.check_audio(suite, client_b)
        ownership.check_child_lease(suite, client_a, edited_source, last_frame)
        client_c = connections.enter_context(BrokerClient(suite.state))
        ownership.check_writer_handoff(suite, client_a, client_c)
        ownership.check_hardware_policy(suite, client_a)
        ownership.check_desktop_activity(suite, control)
        recovery.check_worker_restart(suite, client_a)
        recovery.check_broker_crash(suite, control, broker_pid)
    recovery.check_restarted_brokers(suite, broker_pid, rom_a)


def run() -> int:
    name = time.strftime("%Y%m%dT%H%M%S")
    with (
        tempfile.TemporaryDirectory(prefix=f"chromatic-acceptance-{name}-") as work,
        mock.patch.dict(os.environ, {"HERMRETRO_WRITER_HANDOFF_SECONDS": str(HANDOFF)}),
    ):
        suite = BrokerRun(Path(work), name)
        try:
            with mock.patch("backend.broker.client.spawn_broker", suite.spawn_broker):
                exercise(suite)
            passed = all(check["passed"] for check in suite.checks)
            evidence = suite.write_evidence(passed)
            count = sum(check["passed"] for check in suite.checks)
            print(
                json.dumps(
                    {"passed": passed, "checks": f"{count}/{len(suite.checks)}", "evidence": str(evidence)}, indent=2
                )
            )
            return 0 if passed else 1
        except Exception:  # noqa: BLE001 - record the failed stage before cleaning up
            crashed = traceback.format_exc()
            print(crashed, file=sys.stderr, flush=True)
            suite.write_evidence(False, crashed)
            return 1
        finally:
            suite.stop_brokers()


if __name__ == "__main__":
    raise SystemExit(run())
