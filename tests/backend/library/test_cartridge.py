"""Whether a ROM fits a Chromatic cartridge (backend/library/cartridge.py): what an installed game's ROM must be.

Run alone: python -m unittest tests.backend.library.test_cartridge
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import cartridge  # noqa: E402 - the repository root goes on sys.path first
from tests.support import make_rom  # noqa: E402 - the repository root goes on sys.path first


def codes(data: bytes) -> list[str]:
    return [problem["code"] for problem in cartridge.check_bytes(data)["problems"]]


def resign(rom: bytearray) -> bytes:
    """Put the checksums right again after editing a header field."""
    checksum = 0
    for byte in rom[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 0xFF
    rom[0x14D] = checksum
    rom[0x14E] = rom[0x14F] = 0
    total = sum(rom) & 0xFFFF
    rom[0x14E], rom[0x14F] = total >> 8, total & 0xFF
    return bytes(rom)


class Cartridge(unittest.TestCase):
    def test_what_gb_studio_writes_fits(self):
        for kind in (0x1E, 0x10):
            info = cartridge.check_bytes(make_rom(64 * 1024, kind=kind))
            self.assertTrue(info["ok"], info)
            self.assertTrue(info["colour"])
        self.assertTrue(cartridge.check_bytes(make_rom(colour=False, kind=0x00, ram=0))["ok"])
        self.assertTrue(cartridge.check_bytes(make_rom(cartridge.MAX_ROM_BYTES))["ok"])

    def test_size(self):
        self.assertEqual(codes(b"\0" * 100), ["ROM_SIZE"])
        self.assertIn("ROM_SIZE", codes(make_rom()[: 24 * 1024]))
        declared = bytearray(make_rom(64 * 1024))
        declared[0x148] = 0  # says 32 KiB
        self.assertEqual(codes(resign(declared)), ["ROM_SIZE"])
        unknown = bytearray(make_rom())
        unknown[0x148] = 0x52
        self.assertEqual(codes(resign(unknown)), ["ROM_HEADER"])
        with self.subTest("larger than a cartridge"):
            path = Path(self.enterContext(__import__("tempfile").TemporaryDirectory())) / "big.gbc"
            path.write_bytes(b"\0" * (cartridge.MAX_ROM_BYTES + 1))
            self.assertEqual([problem["code"] for problem in cartridge.inspect(path)["problems"]], ["ROM_SIZE"])

    def test_header_and_checksums(self):
        logo = bytearray(make_rom())
        logo[0x104] ^= 0xFF
        self.assertEqual(codes(resign(logo)), ["ROM_HEADER"])
        header = bytearray(make_rom())
        header[0x14D] ^= 1
        self.assertIn("ROM_CHECKSUM", codes(bytes(header)))
        body = bytearray(make_rom())
        body[0x4000] = 0x42  # the header still matches; the global checksum does not
        self.assertEqual(codes(bytes(body)), ["ROM_CHECKSUM"])

    def test_cartridge_type_and_ram(self):
        self.assertEqual(codes(make_rom(kind=0x22)), ["ROM_CARTRIDGE"])  # MBC7
        self.assertEqual(codes(make_rom(kind=0xFC)), ["ROM_CARTRIDGE"])  # a camera
        self.assertEqual(codes(make_rom(ram=1)), ["ROM_CARTRIDGE"])

    def test_the_name_says_whether_it_is_a_colour_game(self):
        colour = cartridge.check_bytes(make_rom(colour=True))
        mono = cartridge.check_bytes(make_rom(colour=False))
        self.assertEqual(cartridge.check_name(colour, "build/game.gbc"), [])
        self.assertEqual(cartridge.check_name(mono, "build/game.gb"), [])
        self.assertEqual([p["code"] for p in cartridge.check_name(mono, "build/game.gbc")], ["ROM_COLOUR"])
        self.assertEqual([p["code"] for p in cartridge.check_name(colour, "build/game.gb")], ["ROM_COLOUR"])


if __name__ == "__main__":
    unittest.main()
