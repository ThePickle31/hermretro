"""A recorded attempt replayed onto the same ROM and onto a rebuild, on B's worker (no later check uses B's game)."""

from tests.acceptance.fixture import OWNER_B, structured

ROUTE = [
    {"buttons": ["down"], "frames": 20},
    {"buttons": [], "frames": 10},
    {"buttons": ["right"], "frames": 15},
    {"buttons": [], "frames": 1},
]


def images(response) -> list[dict]:
    return [b for b in response["result"].get("content", []) if b.get("type") == "image"]


def check_replay(suite, client_b, rom_b):
    client_b.call(OWNER_B, "emulator_run", {"romPath": rom_b, "recording": {}})
    played = structured(client_b.call(OWNER_B, "emulator_step", {"inputs": ROUTE}))
    source = played.get("recordingSpan", {}).get("recordingPath")
    same = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b})
    replay = structured(same).get("replay", {})
    saved = structured(client_b.call(OWNER_B, "emulator_checkpoint", {"action": "save"}))
    refused = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "toActionIndex": 100_000})
    after_refusal = structured(client_b.call(OWNER_B, "emulator_status"))
    suite.check(
        "M5",
        "A recorded attempt replays onto its ROM frame for frame and play continues there; a refused replay "
        "leaves the session as it was",
        not same["result"].get("isError")
        and replay.get("status") == "matched"
        and replay.get("comparedFrames", 0) > 0
        and replay.get("replayedActions")
        == replay.get("toActionIndex")
        == played.get("recordingSpan", {}).get("toActionIndex")
        and structured(same).get("frame") == played.get("frame")
        and [i.get("role") for i in structured(same).get("images", [])] == ["end"]
        and structured(same)["images"][0].get("sha256") == played.get("samples", [{}])[-1].get("sha256")
        and len(images(same)) == 1
        and bool(saved.get("checkpointId"))
        and refused["result"].get("isError") is True
        and after_refusal.get("frame") == played.get("frame"),
        replay=replay,
        frame=structured(same).get("frame"),
        played_frame=played.get("frame"),
        checkpoint=saved.get("checkpointId") or saved.get("error"),
        refused=structured(refused).get("error"),
        frame_after_refusal=after_refusal.get("frame"),
    )

    # Move the player's start and rebuild: the first frame showing the player differs.
    client_b.call(OWNER_B, "settings_update", {"settings": {"startX": 3}})
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    stopped = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source})
    divergence = structured(stopped).get("replay", {}).get("divergence", {})
    onward = client_b.call(
        OWNER_B, "emulator_replay", {"romPath": rom_b, "recordingPath": source, "onDivergence": "continue"}
    )
    continued = structured(onward).get("replay", {})
    suite.check(
        "M6",
        "Replayed onto a rebuild, the attempt stops at the first differing frame with the recorded and new images, "
        "or plays on to the end when asked",
        rebuilt.get("success") is not False
        and structured(stopped).get("replay", {}).get("status") == "diverged"
        and structured(stopped).get("frame") == divergence.get("frame")
        and divergence.get("expectedSha256") != divergence.get("actualSha256")
        and [i.get("role") for i in structured(stopped).get("images", [])] == ["expected", "actual"]
        and len(images(stopped)) == 2
        and continued.get("status") == "diverged"
        and continued.get("divergence", {}).get("frame") == divergence.get("frame")
        and continued.get("replayedActions") == continued.get("toActionIndex")
        and structured(onward).get("frame") == played.get("frame")
        and [i.get("role") for i in structured(onward).get("images", [])] == ["expected", "actual", "end"],
        divergence=divergence,
        continued=continued,
        frame_stopped=structured(stopped).get("frame"),
        frame_continued=structured(onward).get("frame"),
    )
