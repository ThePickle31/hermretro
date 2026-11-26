"""Delegated leases, one game per conversation, hardware policy and the Desktop activity view."""

import json

from tests.acceptance.fixture import OWNER_A, OWNER_C, diff, snapshot, structured

CHILD = {"session_id": "sess-child-1", "task_id": "task-child-1", "delegated": True}


def check_child_lease(suite, client_a, last_frame):
    # A's files as the child finds them (its builds since the edit wrote their ROM's romSha256 into game.json).
    before = snapshot(suite.project_a)
    orphan = client_a.call({"profile": "s01-profile", "conversation_id": "conv-nobody"}, "session_status", origin=CHILD)
    child_read = client_a.call(OWNER_A, "variable_inspect", origin=CHILD)
    child_write = client_a.call(
        OWNER_A,
        "variable_set",
        {"name": "child no lease", "expectedRevision": structured(child_read).get("revision")},
        origin=CHILD,
    )
    child_grant_self = client_a.request(
        {"op": "grant_lease", "owner": OWNER_A, "task_id": "task-child-1", "origin": CHILD}
    )
    snap_a2 = snapshot(suite.project_a)
    grant = client_a.request({"op": "grant_lease", "owner": OWNER_A, "task_id": "task-child-1", "mode": "write"})
    child_write2 = client_a.call(
        OWNER_A,
        "variable_set",
        {
            "name": "S01 child leased",
            "symbol": "var_s01_child",
            "expectedRevision": structured(child_read).get("revision"),
        },
        origin=CHILD,
    )
    child_select = client_a.call(
        OWNER_A, "project_select", {"projectPath": str(suite.project_b / "project.gbsproj")}, origin=CHILD
    )
    child_close = client_a.call(OWNER_A, "emulator_close", origin=CHILD)
    client_a.request({"op": "revoke_lease", "owner": OWNER_A, "task_id": "task-child-1"})
    child_write3 = client_a.call(OWNER_A, "variable_set", {"name": "after revoke"}, origin=CHILD)
    still_running = client_a.call(OWNER_A, "emulator_status")
    suite.check(
        "L1",
        "Delegated child: read allowed, write needs a parent-granted lease, parent-only actions refused",
        orphan.get("denied", {}).get("code") == "NO_PARENT_LANE"
        and child_read.get("ok")
        and child_write.get("denied", {}).get("code") == "LEASE_REQUIRED"
        and child_grant_self.get("denied", {}).get("code") == "PARENT_ONLY"
        and diff(before, snap_a2) == []
        and grant.get("ok")
        and child_write2.get("ok")
        and not child_write2["result"].get("isError")
        and child_select.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_close.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_write3.get("denied", {}).get("code") == "LEASE_REQUIRED"
        and structured(still_running).get("frame") == last_frame,
        codes={
            "orphan": orphan.get("denied"),
            "no_lease": child_write.get("denied"),
            "self_grant": child_grant_self.get("denied"),
            "select": child_select.get("denied"),
            "close": child_close.get("denied"),
            "after_revoke": child_write3.get("denied"),
        },
    )


def check_one_game_per_chat(suite, client_a, client_c):
    """A game is opened and edited only from its own conversation: A made project A, so it is A's game."""
    snap_a3 = snapshot(suite.project_a)
    sel_c = client_c.call(OWNER_C, "project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
    status_c = client_c.call(OWNER_C, "session_status")
    inspect_a2 = client_a.call(OWNER_A, "variable_inspect")
    edit_a2 = client_a.call(
        OWNER_A,
        "variable_set",
        {
            "name": "S01 A second edit",
            "symbol": "var_s01_a_two",
            "expectedRevision": structured(inspect_a2).get("revision"),
        },
    )
    suite.check(
        "W1",
        "Another conversation cannot open a game that is a conversation's own; that conversation keeps editing it",
        sel_c.get("dispatched") is False
        and sel_c.get("denied", {}).get("code") == "GAME_CHAT_ONLY"
        and structured(status_c).get("selected") is not True
        and edit_a2.get("ok")
        and not edit_a2["result"].get("isError")
        and edit_a2["lane"]["writer"] is True
        and len(diff(snap_a3, snapshot(suite.project_a))) > 0,
        denial=sel_c.get("denied"),
        c_status=structured(status_c),
    )
    # The engine's own revision check still guards the owning chat: an edit from a revision read before its last
    # edit is refused (the second guard against stale writes, once the broker let the call through).
    snap_a4 = snapshot(suite.project_a)
    stale_write = client_a.call(
        OWNER_A, "variable_set", {"name": "A stale", "expectedRevision": structured(inspect_a2).get("revision")}
    )
    suite.check(
        "W2",
        "In the game's own conversation, an edit from a stale revision is refused by the engine and changes nothing",
        stale_write.get("ok")
        and stale_write["result"].get("isError") is True
        and structured(stale_write).get("code") == "STALE_RESOURCE"
        and diff(snap_a4, snapshot(suite.project_a)) == [],
        stale_engine_error=structured(stale_write),
    )


def check_hardware_policy(suite, client_a):
    off = {tool: client_a.call(OWNER_A, tool, {}) for tool in ("device", "setup", "flash", "play", "device_capture")}
    unknown = client_a.call(OWNER_A, "not_a_real_tool", {})
    child_hw = client_a.call(OWNER_A, "device", {"command": "status"}, origin=CHILD, policy={"hardware_enabled": True})
    child_prepare = client_a.call(OWNER_A, "toolchain_prepare", {"components": ["emulator"]}, origin=CHILD)
    # 'device status' reads platform and driver requirements without touching USB.
    on_status = client_a.call(OWNER_A, "device", {"command": "status"}, policy={"hardware_enabled": True})
    suite.check(
        "P1",
        "Hardware tools are refused before dispatch unless enabled; children can never use them",
        all(r.get("dispatched") is False and r["denied"]["code"] == "HARDWARE_DISABLED" for r in off.values())
        and unknown.get("denied", {}).get("code") == "UNKNOWN_TOOL"
        and child_hw.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_prepare.get("denied", {}).get("code") == "PARENT_ONLY"
        and on_status.get("dispatched") is True
        and on_status.get("ok") is True,
        enabled_device_status_is_error=on_status.get("result", {}).get("isError"),
        enabled_device_status=json.dumps(structured(on_status))[:600],
    )


def check_desktop_activity(suite, control):
    by_conversation = control.request({"op": "lane_status", "profile": "s01-profile", "session_id": "conv-A"})
    by_session = control.request(
        {"op": "lane_status", "profile": "s01-profile", "session_id": "sess-A-2-after-compaction"}
    )
    other_profile = control.request({"op": "lane_status", "profile": "someone-else", "session_id": "conv-A"})
    doctor = control.request({"op": "doctor"})
    components = {c["id"]: c["status"] for c in structured(doctor).get("components", [])}
    suite.check(
        "D1",
        "Lane lookup works by conversation or runtime session id and is profile-scoped; doctor reports",
        (by_conversation.get("lane") or {}).get("selected_root") == str(suite.project_a)
        and (by_conversation.get("lane") or {}).get("emulator_active") is True
        and (by_session.get("lane") or {}).get("selected_root") == str(suite.project_a)
        and other_profile.get("lane") is None
        and components.get("runtime") == "ready",
        components=components,
    )

    seen = control.request({"op": "activity", "profile": "s01-profile", "ids": ["conv-A"]})
    tools_seen = [event["tool"] for event in seen.get("events") or []]
    frame = seen.get("frame") or {}
    fallback = control.request({"op": "activity", "profile": "s01-profile", "ids": ["a-chat-with-no-worker"]})
    elsewhere = control.request({"op": "activity", "profile": "someone-else", "ids": ["conv-A"]})
    suite.check(
        "D2",
        "The panel view reports a chat's project, build, latest real frame and log from memory; "
        "an unknown chat sees no other chat's; other profiles see nothing",
        seen.get("matched") == "chat"
        and bool(seen["lane"]["project_root"])
        and "rom_build" in tools_seen
        and (seen.get("build") or {}).get("ok") is True
        and frame.get("mimeType") == "image/png"
        and len(frame.get("data") or "") > 200
        and fallback.get("matched") is None
        and fallback.get("lane") is None
        and elsewhere.get("lane") is None,
        tools=tools_seen[-8:],
        build=seen.get("build"),
        frame_tool=frame.get("tool"),
        fallback=fallback.get("matched"),
        elsewhere=elsewhere.get("matched"),
    )
