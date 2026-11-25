"""A recorded attempt replayed onto the same ROM and onto a rebuild, on B's worker (no later check uses B's game)."""

from tests.acceptance import checkpoints
from tests.acceptance.fixture import OWNER_B, structured

ROUTE = [
    {"buttons": ["down"], "frames": 20},
    {"buttons": [], "frames": 10},
    {"buttons": ["right"], "frames": 15},
    {"buttons": [], "frames": 1},
]


def images(response) -> list[dict]:
    return [b for b in response["result"].get("content", []) if b.get("type") == "image"]


def roles(response) -> list[str]:
    return [i.get("role") for i in structured(response).get("images", [])]


def refused(response) -> bool:
    return response["result"].get("isError") is True


def check_replay(suite, client_b, rom_b):
    source, played = check_same_rom(suite, client_b, rom_b)
    check_branch_and_cutoff(suite, client_b, rom_b, source)
    check_without_session(suite, client_b, rom_b, source, played)
    cross = checkpoints.check_signature_only_rebuild(suite, client_b, rom_b)
    checkpoints.check_restored_replay(suite, client_b, rom_b, cross)
    checkpoints.check_unverified_symbols(suite, client_b, rom_b, cross)
    checkpoints.check_archived_checkpoint(suite, client_b, rom_b, cross)
    check_rebuild(suite, client_b, rom_b, source, played)
    checkpoints.check_changed_rebuild(suite, client_b, cross)


def check_same_rom(suite, client_b, rom_b):
    client_b.call(OWNER_B, "emulator_run", {"romPath": rom_b, "recording": {}})
    played = structured(client_b.call(OWNER_B, "emulator_step", {"inputs": ROUTE}))
    source = played.get("recordingSpan", {}).get("recordingPath")
    same = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b})
    replay = structured(same).get("replay", {})
    saved = structured(client_b.call(OWNER_B, "emulator_checkpoint", {"action": "save"}))
    refusals = {
        "toActionIndex": client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "toActionIndex": 100_000}),
        "maxFrames": client_b.call(
            OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source, "recording": {"maxFrames": 130}}
        ),
        "outputPath": client_b.call(
            OWNER_B,
            "emulator_replay",
            {"romPath": rom_b, "recordingPath": source, "recording": {"outputPath": f"{source}/inside"}},
        ),
    }
    after_refusal = structured(client_b.call(OWNER_B, "emulator_status"))
    suite.check(
        "M5",
        "A recorded attempt replays onto its ROM, every frame compared, and play continues there; a refused replay "
        "(no such action, a frame limit shorter than the route, an output inside the attempt) leaves the session",
        not same["result"].get("isError")
        and replay.get("status") == "matched"
        and replay.get("coverage") == "every-frame"
        and replay.get("deterministic") is True
        and replay.get("comparedFrames") == played.get("frame", 0) + 1
        and replay.get("replayedActions")
        == replay.get("toActionIndex")
        == played.get("recordingSpan", {}).get("toActionIndex")
        and structured(same).get("frame") == played.get("frame")
        and roles(same) == ["end"]
        and structured(same)["images"][0].get("sha256") == played.get("samples", [{}])[-1].get("sha256")
        and len(images(same)) == 1
        and bool(saved.get("checkpointId"))
        and all(refused(response) for response in refusals.values())
        and after_refusal.get("frame") == played.get("frame")
        and after_refusal.get("recording", {}).get("recordingPath") == structured(same)["recording"]["recordingPath"],
        replay=replay,
        frame=structured(same).get("frame"),
        played_frame=played.get("frame"),
        checkpoint=saved.get("checkpointId") or saved.get("error"),
        refusals={key: structured(response).get("error") for key, response in refusals.items()},
        frame_after_refusal=after_refusal.get("frame"),
    )
    return source, played


def check_branch_and_cutoff(suite, client_b, rom_b, source):
    """An explicit checkpoint branch replays to its own end; a replay cut right after a button change holds it."""
    derived = structured(client_b.call(OWNER_B, "emulator_status")).get("recording", {}).get("recordingPath")
    checkpoint = structured(client_b.call(OWNER_B, "emulator_checkpoint", {"action": "save"})).get("checkpointId")
    detour = structured(
        client_b.call(
            OWNER_B, "emulator_step", {"inputs": [{"buttons": ["up"], "frames": 8}, {"buttons": [], "frames": 1}]}
        )
    )
    client_b.call(OWNER_B, "emulator_checkpoint", {"action": "restore", "checkpointId": checkpoint})
    branched = structured(
        client_b.call(
            OWNER_B, "emulator_step", {"inputs": [{"buttons": ["left"], "frames": 6}, {"buttons": [], "frames": 1}]}
        )
    )
    first = client_b.call(
        OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": derived, "branchId": "branch-0001"}
    )
    first_replay = structured(first).get("replay", {})

    exported = structured(
        client_b.call(OWNER_B, "emulator_recording", {"action": "export", "recordingPath": source, "limit": 128})
    )
    actions = exported.get("actions", [])
    cut = next(
        (i for i, a in enumerate(actions, 1) if a.get("type") == "set_buttons" and a.get("buttons") == ["right"]), 0
    )
    cut_frame = exported.get("startingCondition", {}).get("initialFrames", 0) + sum(
        a.get("frames", 0) for a in actions[:cut] if a.get("type") == "step"
    )
    cutoff = structured(
        client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source, "toActionIndex": cut})
    )
    onward = structured(client_b.call(OWNER_B, "emulator_step", {"inputs": [{"buttons": ["right"], "frames": 1}]}))
    suite.check(
        "M7",
        "A checkpoint branch named explicitly replays to its own end; a replay cut right after a button change ends "
        "there with the button held, and stepping goes on from it",
        bool(checkpoint)
        and branched.get("recordingSpan", {}).get("branchId") == "branch-0002"
        and not first["result"].get("isError")
        and first_replay.get("status") == "matched"
        and first_replay.get("source", {}).get("branchId") == "branch-0001"
        and structured(first).get("frame") == detour.get("frame")
        and cut > 0
        and cutoff.get("replay", {}).get("status") == "matched"
        and cutoff.get("replay", {}).get("replayedActions") == cut
        and cutoff.get("frame") == cut_frame
        and cutoff.get("activeButtons") == ["right"]
        and onward.get("frame") == cut_frame + 1,
        first_replay=first_replay,
        detour_frame=detour.get("frame"),
        branch_frame=branched.get("frame"),
        cut=cut,
        cut_frame=cut_frame,
        cutoff_frame=cutoff.get("frame"),
        held=cutoff.get("activeButtons"),
        onward_frame=onward.get("frame"),
    )


def check_without_session(suite, client_b, rom_b, source, played):
    """After close, a named attempt replays on a worker of its own; a refused one gives the recording lease back."""
    lease = suite.project_b / "artifacts" / ".recording-access" / "lease.json"
    client_b.call(OWNER_B, "emulator_close", {})
    cold_refusal = client_b.call(
        OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source, "toActionIndex": 100_000}
    )
    lease_after_refusal = lease.exists()
    status_after_refusal = client_b.call(OWNER_B, "emulator_status")
    cold = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source})
    suite.check(
        "M8",
        "With no session, a replay of a named attempt starts its own worker; refused, it gives the recording lease back",
        refused(cold_refusal)
        and not lease_after_refusal
        and refused(status_after_refusal)
        and not cold["result"].get("isError")
        and structured(cold).get("replay", {}).get("status") == "matched"
        and structured(cold).get("frame") == played.get("frame"),
        refusal=structured(cold_refusal).get("error"),
        lease_after_refusal=lease_after_refusal,
        cold=structured(cold).get("replay") or structured(cold).get("error"),
    )


def check_rebuild(suite, client_b, rom_b, source, played):
    # Move the player's start and rebuild: the first frame showing the player differs.
    client_b.call(OWNER_B, "settings_update", {"settings": {"startX": 3}})
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    stopped = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source})
    divergence = structured(stopped).get("replay", {}).get("divergence", {})
    derived = structured(stopped).get("recording", {}).get("recordingPath")
    provenance = structured(
        client_b.call(OWNER_B, "emulator_recording", {"action": "status", "recordingPath": derived})
    ).get("replayOf", {})
    # Named by default: the stopped replay played only part of the route, so its source stays the default.
    onward = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "onDivergence": "continue"})
    continued = structured(onward).get("replay", {})
    suite.check(
        "M6",
        "Replayed onto a rebuild, the attempt stops at the first differing frame with the new image (and the recorded "
        "one when kept), notes what it replayed, and the follow-up replays the whole original route",
        rebuilt.get("success") is not False
        and structured(stopped).get("replay", {}).get("status") == "diverged"
        and structured(stopped).get("frame") == divergence.get("frame")
        and roles(stopped) == (["expected", "actual"] if "expectedSha256" in divergence else ["actual"])
        and divergence.get("expectedSha256") != divergence.get("actualSha256")
        and len(images(stopped)) == len(roles(stopped))
        and provenance.get("source", {}).get("recordingPath") == source
        and provenance.get("replayedActions") == structured(stopped)["replay"].get("replayedActions")
        and provenance.get("status") == "diverged"
        and continued.get("source", {}).get("recordingPath") == source
        and continued.get("status") == "diverged"
        and continued.get("divergence", {}).get("frame") == divergence.get("frame")
        and continued.get("replayedActions")
        == continued.get("toActionIndex")
        == continued.get("source", {}).get("actionCount")
        and structured(onward).get("frame") == played.get("frame")
        and roles(onward)[-1:] == ["end"],
        divergence=divergence,
        provenance=provenance,
        continued=continued,
        frame_stopped=structured(stopped).get("frame"),
        frame_continued=structured(onward).get("frame"),
    )
