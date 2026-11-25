"""Whether a ROM fits the ModRetro Chromatic's cartridge: what an installed game's ROM must be before it reaches the
library, so every game installed from a link can also be flashed. Standard library only.

The engine's ``flash`` writes a ROM that ``rom_inspect`` calls valid (the Nintendo logo and the header checksum) and
that is 336 bytes to 8 MiB; the vendored engine names no list of cartridge types the Chromatic's cartridge accepts
(the vendor's backend answers ``flash.unsupported`` for one it cannot write). So the types accepted here are the ones
the toolchains hermretro builds with emit: GB Studio writes ``0x1E`` (MBC5+RUMBLE+RAM+BATTERY) or ``0x10``
(MBC3+TIMER+RAM+BATTERY) with 128 KiB of RAM (``buildMakeScript.ts``: ``-Wm-yt``, ``-Wm-ya4``), and GBDK's defaults
are ROM ONLY or another MBC5 or MBC3 variant. Anything else is refused.
"""

from __future__ import annotations

from pathlib import Path

MIN_ROM_BYTES = 336  # a whole cartridge header
MAX_ROM_BYTES = 8 * 1024 * 1024
MIN_BANKED_BYTES = 32 * 1024
NINTENDO_LOGO = bytes.fromhex(
    "ce ed 66 66 cc 0d 00 0b 03 73 00 83 00 0c 00 0d 00 08 11 1f 88 89 00 0e"
    "dc cc 6e e6 dd dd d9 99 bb bb 67 63 6e 0e ec cc dd dc 99 9f bb b9 33 3e"
)
# Cartridge type byte (0x147) -> name, for every type accepted (module docstring).
CARTRIDGE_TYPES = {
    0x00: "ROM ONLY",
    0x0F: "MBC3+TIMER+BATTERY",
    0x10: "MBC3+TIMER+RAM+BATTERY",
    0x11: "MBC3",
    0x12: "MBC3+RAM",
    0x13: "MBC3+RAM+BATTERY",
    0x19: "MBC5",
    0x1A: "MBC5+RAM",
    0x1B: "MBC5+RAM+BATTERY",
    0x1C: "MBC5+RUMBLE",
    0x1D: "MBC5+RUMBLE+RAM",
    0x1E: "MBC5+RUMBLE+RAM+BATTERY",
}
# RAM size byte (0x149) -> bytes (code 1, 2 KiB, was never used by a released cartridge).
RAM_SIZES = {0: 0, 2: 8 * 1024, 3: 32 * 1024, 4: 128 * 1024, 5: 64 * 1024}
# CGB flag (0x143): 0x80 runs on both, 0xC0 on colour only; anything else is a Game Boy game.
COLOUR_FLAGS = (0x80, 0xC0)


def inspect(path: Path) -> dict:
    """``{ok, problems, sizeBytes, title, cartridgeType, colour}`` for the ROM at ``path``; each problem is
    ``{code, message}``. ``colour`` is True for a Game Boy Color ROM."""
    try:
        data = Path(path).read_bytes() if Path(path).stat().st_size <= MAX_ROM_BYTES else None
    except OSError as error:
        return _result([_problem("ROM_UNREADABLE", f"The ROM cannot be read: {error}.")])
    if data is None:
        return _result([_problem("ROM_SIZE", "The ROM is larger than 8 MiB, the most a Chromatic cartridge holds.")])
    return check_bytes(data)


def check_bytes(data: bytes) -> dict:
    size = len(data)
    if size < MIN_ROM_BYTES:
        return _result([_problem("ROM_SIZE", f"The ROM is {size} bytes, too small to be a Game Boy game.")], size)
    problems = []
    if size < MIN_BANKED_BYTES or size & (size - 1):
        problems.append(
            _problem("ROM_SIZE", f"The ROM is {size} bytes; a Game Boy ROM is 32 KiB times a power of two.")
        )
    declared = MIN_BANKED_BYTES << data[0x148] if data[0x148] <= 8 else None
    if declared is not None and declared != size and not problems:
        problems.append(_problem("ROM_SIZE", f"The ROM's header says {declared} bytes, but the file is {size}."))
    elif declared is None:
        problems.append(_problem("ROM_HEADER", f"The ROM's header has an unknown ROM size code 0x{data[0x148]:02x}."))
    if data[0x104:0x134] != NINTENDO_LOGO:
        problems.append(_problem("ROM_HEADER", "The ROM's header does not have the Nintendo logo a cartridge needs."))
    checksum = 0
    for byte in data[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 0xFF
    if checksum != data[0x14D]:
        problems.append(_problem("ROM_CHECKSUM", "The ROM's header checksum is wrong; the file is damaged or edited."))
    total = (sum(data) - data[0x14E] - data[0x14F]) & 0xFFFF
    if total != (data[0x14E] << 8 | data[0x14F]):
        problems.append(_problem("ROM_CHECKSUM", "The ROM's global checksum is wrong; the file is damaged or edited."))
    kind = data[0x147]
    if kind not in CARTRIDGE_TYPES:
        problems.append(
            _problem(
                "ROM_CARTRIDGE", f"The ROM asks for cartridge type 0x{kind:02x}, which a Chromatic cartridge cannot be."
            )
        )
    if data[0x149] not in RAM_SIZES:
        problems.append(_problem("ROM_CARTRIDGE", f"The ROM asks for an unknown save RAM size (code {data[0x149]})."))
    colour = data[0x143] in COLOUR_FLAGS
    title = data[0x134 : 0x143 if colour else 0x144].split(b"\0", 1)[0].decode("ascii", "replace")
    return {**_result(problems, size), "title": title, "cartridgeType": kind, "colour": colour}


def check_name(info: dict, name: str) -> list[dict]:
    """The problem when the ROM's colour support and its file name disagree (``.gbc`` for a Game Boy Color game)."""
    if "colour" not in info:
        return []
    if name.endswith(".gbc") != info["colour"]:
        wanted = "a Game Boy Color game (.gbc)" if name.endswith(".gbc") else "a Game Boy game (.gb)"
        return [_problem("ROM_COLOUR", f"{name} must be {wanted}, but the ROM's header says otherwise.")]
    return []


def _result(problems: list[dict], size: int | None = None) -> dict:
    return {"ok": not problems, "problems": problems, "sizeBytes": size}


def _problem(code: str, message: str) -> dict:
    return {"code": code, "message": message}
