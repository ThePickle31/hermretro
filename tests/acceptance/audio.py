"""Music and sound import, the note-list composer, a bundled track, and the sound hardware playing it, on project B."""

import gzip
import json
import math
import random
import shutil
import struct
import uuid

from tests.acceptance.fixture import OWNER_B, structured

THEME = {
    "assetPath": "assets/music/theme.uge",
    "name": "Theme",
    "ticksPerRow": 7,
    "sections": [
        {
            "name": "A",
            "pulse1": "C5:2 E5:2 G5:4 E5:2 C5:2 D5:4",
            "pulse2": {"notes": "E4:8 G4:8", "instrument": "pluck"},
            "wave": "C3:4 G2:4 A2:4 G2:4",
            "noise": "kick:4 hat:4 snare:4 hat:4",
        },
        {"name": "B", "pulse1": "F5:4 A5:4 G5:8", "wave": "F2:8 G2:8"},
    ],
    "order": ["A", "A", "B"],
}


def wav(seconds: float, *, channels: int = 1, rate: int = 8000, bits: int = 8) -> bytes:
    """A 440 Hz tone as unsigned 8-bit or signed 16-bit PCM."""
    frames = int(rate * seconds)
    width = 1 if bits == 8 else 2
    tone = [math.sin(i * 2 * math.pi * 440 / rate) for i in range(frames)]
    if width == 1:
        samples = bytes(128 + int(100 * value) for value in tone for _ in range(channels))
    else:
        samples = b"".join(struct.pack("<h", int(20000 * value)) for value in tone for _ in range(channels))
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * channels * width, channels * width, bits)
    return riff(fmt, samples)


def riff(fmt: bytes, samples: bytes) -> bytes:
    return (
        b"RIFF"
        + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(samples))
        + b"WAVEfmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(samples))
        + samples
    )


def vgm(commands: bytes) -> bytes:
    """A VGM 1.71 header with a Game Boy clock, then the command stream."""
    header = bytearray(0x100)
    header[0:4] = b"Vgm "
    struct.pack_into("<I", header, 0x08, 0x171)
    struct.pack_into("<I", header, 0x34, 0x100 - 0x34)
    struct.pack_into("<I", header, 0x80, 4194304)
    return bytes(header) + commands


# One square-wave blip on pulse 1: NR52 on, NR50/NR51, NR12 envelope, NR11 duty, NR13/NR14 trigger; wait; end.
BLIP = bytes([0xB3, 0x16, 0x80, 0xB3, 0x14, 0x77, 0xB3, 0x15, 0xFF, 0xB3, 0x02, 0xF3, 0xB3, 0x01, 0x80])
BLIP += bytes([0xB3, 0x03, 0x00, 0xB3, 0x04, 0x87, 0x62, 0x62, 0x66])


def sidecar(root, asset: str) -> dict:
    return json.loads((root / f"{asset}.gbsres").read_text())


def call(client, tool, arguments=None):
    return structured(client.call(OWNER_B, tool, arguments or {}))


def check_audio(suite, client_b):
    theme = check_compose(suite, client_b)
    check_import(suite, client_b)
    check_refusals(suite, client_b)
    check_bundled(suite, client_b)
    check_playing(suite, client_b, theme)


def check_compose(suite, client_b):
    root = suite.project_b
    first = call(client_b, "music_compose", THEME)
    written = (root / THEME["assetPath"]).read_bytes()
    again = call(client_b, "music_compose", THEME)
    higher = {**THEME["sections"][0], "pulse1": "C6:2 E6:2 G6:4 E6:2 C6:2 D6:4"}
    higher_song = {**THEME, "sections": [higher, THEME["sections"][1]]}
    replaced = call(client_b, "music_compose", {**higher_song, "overwrite": True})
    meta = sidecar(root, THEME["assetPath"])
    suite.check(
        "U1",
        "music_compose writes a .uge from note lists with a sidecar and an ID that stays the same; writing it again "
        "needs overwrite, which keeps the ID",
        first.get("kind") == "music"
        and first.get("type") == "uge"
        and first.get("rows") == 48
        and first.get("patterns") == 4
        and 0 < first.get("romBytes", 0) <= 16384
        and first.get("playEvent") == {"command": "EVENT_MUSIC_PLAY", "args": {"musicId": first.get("id")}}
        and written[:4] == struct.pack("<I", 6)
        and again.get("code") == "ASSET_ALREADY_EXISTS"
        and replaced.get("replaced") is True
        and replaced.get("id") == first.get("id")
        and (root / THEME["assetPath"]).read_bytes() != written
        and meta == {**meta, "_resourceType": "music", "id": first["id"], "symbol": "song_theme", "type": "uge"},
        first=first,
        again=again,
        replaced=replaced,
        sidecar=meta,
    )

    # Every channel cuts on the last row: the loop break must not replace a cut, so it moves to the row after.
    silent_end = call(
        client_b,
        "music_compose",
        {
            "assetPath": "assets/music/cut.uge",
            "sections": [{"name": "A", "pulse1": "C5:3 .", "pulse2": "E4:3 .", "wave": "C3:3 .", "noise": "kick:3 ."}],
        },
    )
    rows = uge_rows(root / "assets/music/cut.uge")
    lines = random.Random(6)
    notes = [f"{name}{octave}" for name in "CDEFGAB" for octave in (4, 5)]

    def line(count):
        return " ".join(lines.choice(notes) for _ in range(count))

    sections = [
        {"name": f"S{index}", "pulse1": line(256), "pulse2": line(256), "wave": line(256)} for index in range(16)
    ]
    oversized = call(client_b, "music_compose", {"assetPath": "assets/music/long.uge", "sections": sections})
    suite.check(
        "U6",
        "A song whose last row cuts every channel keeps each cut and breaks the loop on the silent row after it; a "
        "song too large for its 16 KiB ROM bank is refused and nothing is written",
        silent_end.get("rows") == 5
        and [cell[2:] for cell in rows[3]] == [(14, 0)] * 4
        and [cell[2] for cell in rows[4]] == [0, 0, 0, 13]
        and oversized.get("code") == "INVALID_SONG"
        and "16 KiB" in str(oversized.get("error"))
        and not (root / "assets/music/long.uge").exists()
        and not (root / "assets/music/long.uge.gbsres").exists(),
        silent_end=silent_end,
        rows=rows[3:5],
        oversized=oversized,
    )
    return first


def uge_rows(path) -> list[list[tuple[int, int, int, int]]]:
    """Rows 0-5 of a one-block version 6 .uge, as (note, instrument, effect, parameter) per channel."""
    data = path.read_bytes()
    instrument = 4 + 256 + 4 + 1 + 1 + 4 + 1 + 4 + 4 + 4 + 1 + 4 + 4 + 4 + 1 + 64 * 17
    offset = 4 + 3 * 256 + 45 * instrument + 16 * 32 + 4 + 5
    count = struct.unpack_from("<I", data, offset)[0]
    patterns = []
    for index in range(count):
        start = offset + 4 + index * (4 + 64 * 17) + 4
        patterns.append(
            [
                (
                    *struct.unpack_from("<IIII", data, start + row * 17)[:2],
                    *struct.unpack_from("<IB", data, start + row * 17 + 12),
                )
                for row in range(6)
            ]
        )
    return [[patterns[channel][row] for channel in range(4)] for row in range(6)]


def check_import(suite, client_b):
    root = suite.project_b
    sounds = root / "sounds-in"
    sounds.mkdir()
    shutil.copyfile(root / THEME["assetPath"], sounds / "copy.uge")
    (sounds / "blip.wav").write_bytes(wav(0.25))
    (sounds / "long.wav").write_bytes(wav(5))
    (sounds / "chord.wav").write_bytes(wav(0.5, channels=3, rate=500))
    (sounds / "hi.wav").write_bytes(wav(0.2, rate=44100, bits=16))
    (sounds / "zap.vgz").write_bytes(gzip.compress(vgm(BLIP)))
    imported = call(
        client_b,
        "asset_import",
        {
            "assets": [
                {"assetPath": "assets/music/copy.uge", "kind": "music", "sourcePath": "sounds-in/copy.uge"},
                {"assetPath": "assets/sounds/blip.wav", "kind": "sound", "sourcePath": "sounds-in/blip.wav"},
            ]
        },
    )
    items = {item.get("kind"): item for item in imported.get("imported", [])}
    inspected = call(client_b, "asset_inspect", {"assetId": items.get("sound", {}).get("id", "")})
    suite.check(
        "U2",
        "A song and a sound effect import in one call: the files are checked, their sidecars written with IDs that "
        "stay the same, and each result says how to play it",
        imported.get("count") == 2
        and items["music"].get("symbol") == "song_copy"
        and items["music"].get("patterns") == 4
        and items["sound"].get("seconds") == 0.25
        and items["sound"].get("playEvent", {}).get("args", {}).get("type") == items["sound"].get("id")
        and sidecar(root, "assets/sounds/blip.wav")
        == {
            "_resourceType": "sound",
            "id": items["sound"]["id"],
            "name": "blip",
            "symbol": "sound_blip",
            "filename": "blip.wav",
            "type": "wav",
        }
        and inspected.get("id") == items["sound"]["id"]
        and inspected.get("seconds") == 0.25,
        imported=imported,
        inspected=inspected,
    )

    # A loose effect GB Studio compiles without a sidecar still holds its symbol (sound_coin_sav from coin.sav).
    loose = root / "assets/sounds/coin.sav"
    loose.write_bytes(b"\0" * 16)
    nested = call(
        client_b,
        "asset_import",
        {
            "assets": [
                {"assetPath": "assets/sounds/fx/chord.wav", "kind": "sound", "sourcePath": "sounds-in/chord.wav"},
                {"assetPath": "assets/sounds/fx/hi.wav", "kind": "sound", "sourcePath": "sounds-in/hi.wav"},
                {"assetPath": "assets/sounds/fx/zap.vgz", "kind": "sound", "sourcePath": "sounds-in/zap.vgz"},
                {"assetPath": "assets/sounds/coin_sav.wav", "kind": "sound", "sourcePath": "sounds-in/blip.wav"},
            ]
        },
    )
    loose.unlink()
    found = {item.get("assetPath"): item for item in nested.get("imported", [])}
    chord = found.get("assets/sounds/fx/chord.wav", {})
    suite.check(
        "U7",
        "Sounds GB Studio converts import from a subfolder with the sidecar naming the path under assets/sounds: a "
        "three-channel 500 Hz and a 16-bit 44.1 kHz WAV and a VGZ; a symbol avoids one GB Studio derives for a "
        "file without a sidecar",
        nested.get("count") == 4
        and chord.get("channels") == 3
        and chord.get("romBytes") == (4000 // 32) * 18 + 2
        and sidecar(root, "assets/sounds/fx/chord.wav").get("filename") == "fx/chord.wav"
        and found.get("assets/sounds/fx/hi.wav", {}).get("bits") == 16
        and found.get("assets/sounds/fx/zap.vgz", {}).get("type") == "vgm"
        and found.get("assets/sounds/coin_sav.wav", {}).get("symbol") == "sound_coin_sav_0",
        nested=nested,
    )


def check_refusals(suite, client_b):
    root = suite.project_b
    sounds = root / "sounds-in"
    (sounds / "theme.UGE").write_bytes((root / THEME["assetPath"]).read_bytes())
    (sounds / "few.wav").write_bytes(wav(16 / 8000))
    three_bit = struct.pack("<HHIIHH", 1, 1, 8000, 3000, 1, 3)
    (sounds / "three.wav").write_bytes(riff(three_bit, bytes(4000)))
    (sounds / "other.vgm").write_bytes(vgm(BLIP[:-1] + bytes([0x63, 0x66])))
    (sounds / "open.vgm").write_bytes(vgm(BLIP[:-1]))
    long_stream = (BLIP[:-3] + bytes([0x62])) * 2000 + bytes([0x66])
    (sounds / "big.vgm").write_bytes(vgm(long_stream))

    def refusal(asset_path, kind, source):
        return call(
            client_b, "asset_import", {"assetPath": asset_path, "kind": kind, "sourcePath": f"sounds-in/{source}"}
        )

    refused = call(
        client_b,
        "asset_import",
        {
            "assets": [
                {"assetPath": "assets/sounds/blip2.wav", "kind": "sound", "sourcePath": "sounds-in/blip.wav"},
                {"assetPath": "assets/sounds/long.wav", "kind": "sound", "sourcePath": "sounds-in/long.wav"},
            ]
        },
    )
    suite.check(
        "U3",
        "An audio file the game cannot play imports nothing and says why",
        refused.get("code") == "INVALID_AUDIO"
        and "assets[1]" in str(refused.get("error"))
        and "16 KiB" in str(refused.get("error"))
        and not (root / "assets/sounds/blip2.wav").exists()
        and not (root / "assets/sounds/blip2.wav.gbsres").exists(),
        refused=refused,
    )

    paths = {
        "upper": refusal("assets/music/theme2.UGE", "music", "theme.UGE"),
        "mixed": refusal("assets/sounds/blip3.Wav", "sound", "blip.wav"),
        "dot": refusal("assets/sounds/.hidden/blip.wav", "sound", "blip.wav"),
    }
    formats = {
        "few": refusal("assets/sounds/few.wav", "sound", "few.wav"),
        "three": refusal("assets/sounds/three.wav", "sound", "three.wav"),
        "command": refusal("assets/sounds/other.vgm", "sound", "other.vgm"),
        "open": refusal("assets/sounds/open.vgm", "sound", "open.vgm"),
        "big": refusal("assets/sounds/big.vgm", "sound", "big.vgm"),
    }
    reasons = {name: str(result.get("error")) for name, result in formats.items()}
    suite.check(
        "U8",
        "Imports GB Studio would skip, misread or fail to compile are refused: a .UGE, a mixed-case extension, a dot "
        "folder, a WAV under one 32-sample block, a 3-bit WAV, a VGM with an unsupported command, one without its "
        "end marker and one larger than its bank",
        all(result.get("code") == "INVALID_ASSET_PATH" for result in paths.values())
        and all(result.get("code") == "INVALID_AUDIO" for result in formats.values())
        and "32" in reasons["few"]
        and "3 bits" in reasons["three"]
        and "0x63" in reasons["command"]
        and "0x66" in reasons["open"]
        and "16 KiB" in reasons["big"]
        and not any((root / "assets/sounds").glob("*.vgm")),
        paths=paths,
        formats=formats,
    )


def check_bundled(suite, client_b):
    root = suite.project_b
    bundled = call(client_b, "music_compose", {"bundled": "victory-lap"})
    inspected = call(client_b, "asset_inspect", {"assetPath": "assets/music/victory-lap.uge"})
    suite.check(
        "U4",
        "A bundled original track writes into the game as a registered song",
        bundled.get("bundled") == "victory-lap"
        and bundled.get("name") == "Victory Lap"
        and bundled.get("loopSeconds", 0) > 0
        and (root / "assets/music/victory-lap.uge").is_file()
        and inspected.get("id") == bundled.get("id")
        and inspected.get("title") == "Victory Lap",
        bundled=bundled,
        inspected=inspected,
    )


def check_playing(suite, client_b, theme):
    scene_id = call(client_b, "project_inspect")["settings"]["startSceneId"]
    event = {"id": str(uuid.uuid4()), **theme["playEvent"]}
    edited = call(
        client_b, "script_edit", {"action": "insert", "target": {"sceneId": scene_id}, "event": event, "index": 0}
    )
    built = call(client_b, "rom_build")
    rom = built.get("outputPath")
    call(client_b, "emulator_run", {"romPath": rom, "initialFrames": 0, "recording": {}})
    silent = call(client_b, "emulator_audio")
    call(client_b, "emulator_step", {"inputs": [{"buttons": [], "frames": 120}]})
    playing = call(client_b, "emulator_audio")
    replayed = call(client_b, "emulator_replay", {"romPath": rom})
    again = call(client_b, "emulator_audio")
    call(client_b, "emulator_close")
    active = [channel["channel"] for channel in playing.get("channels", []) if channel.get("active")]
    suite.check(
        "U5",
        "A scene that plays the composed song builds and runs: the sound channels are idle before the game starts "
        "and active once the scene has, and a replay of that attempt runs with the same sound hardware",
        edited.get("action") == "insert"
        and built.get("success") is True
        and silent.get("active") is False
        and playing.get("active") is True
        and playing.get("power") is True
        and len(active) >= 2
        and all({"enabled", "dac", "panned"} <= set(channel) for channel in playing.get("channels", []))
        and replayed.get("replay", {}).get("status") == "matched"
        and again.get("registers") == playing.get("registers"),
        built=built.get("diagnostics"),
        silent=silent,
        playing=playing,
        replayed=replayed.get("replay"),
        again=again,
    )
