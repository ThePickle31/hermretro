"""The pre-publish scan (backend/library/publish_scan.py): secrets, home-folder paths and what an install would refuse,
in exactly the files a publish holds, read safely.

Run alone: python -m unittest tests.backend.library.test_publish_scan
"""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import publish_ready, release  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.library.test_publish_ready import Base, codes  # noqa: E402
from tests.support import make_rom  # noqa: E402


class Scan(Base):
    def scanned(self, name: str, content, *, warnings=False) -> list[str]:
        path = self.root / "project" / name
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        found = publish_ready.publish_scan.scan(self.root, [f"project/{name}"])
        return codes(found["warnings" if warnings else "blocking"])

    def test_the_scan_finds_tokens_of_every_known_shape(self):
        tokens = {
            "classic": "gh" + "p_" + "a1B2c3D4" * 5,
            "app": "gh" + "s_" + "12345_eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiIxMjMifQ.c2lnbmF0dXJlLXZhbHVl",
            "aws": "AK" + "IA" + "ABCDEFGHIJ234567",
            "slack": "xo" + "xb-" + "123456789012-abcdefghij",
            "google": "AI" + "za" + "Sy" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
            "api": "s" + "k-" + "proj-" + "A1b2C3d4E5f6G7h8I9j0",
            "key": "-----BEGIN RSA PRIVATE" + " KEY-----",
        }
        for name, token in tokens.items():
            self.assertEqual(self.scanned(f"{name}.gbsres", f'{{"note": "{token}"}}'), ["SECRET"], name)

    def test_the_scan_finds_assigned_secrets_but_not_words_or_ids(self):
        self.assertEqual(self.scanned("a.json", '{"apiKey": "Zq81xL0pW4mNc7Vb2Rt9"}'), ["SECRET"])
        self.assertEqual(self.scanned("b.env", "password=hunter2"), ["SECRET"], "a short password, said to be one")
        self.assertEqual(self.scanned("c.json", '{"password": "sw0rdfish"}'), ["SECRET"])
        self.assertEqual(self.scanned("d.gbsres", '{"token": "sceneTransitionFade"}'), [], "a word is not a secret")
        self.assertEqual(self.scanned("e.gbsres", '{"id": "9b7e6c2a-4f1d-4e8a-b3c5-1d2e3f4a5b6c"}'), [])

    def test_the_scan_finds_home_folders_and_not_urls_or_placeholders(self):
        self.assertEqual(self.scanned("a.gbsres", r'{"p": "c:\\users\\ada\\x.png"}'), ["HOME_PATH"], "any case")
        self.assertEqual(self.scanned("b.gbsres", '{"p": "/home/u/x.png"}'), ["HOME_PATH"])
        self.assertEqual(self.scanned("c.md", "see https://example.invalid/home/u/docs"), [], "a URL is no path")
        self.assertEqual(self.scanned("d.gbsres", '{"p": "/Users/you/x.png"}'), [], "a placeholder names no one")
        self.assertEqual(self.scanned("e.md", "kept in ~/games/space"), [], "a home-relative path names no one")
        with mock.patch.dict(os.environ, {"HOME": str(self.home.base / "you")}):
            self.assertEqual(self.scanned("f.md", f"at {self.home.base / 'you'}/x"), ["HOME_PATH"], "this user's own")

    def test_the_scan_reads_utf16_text_and_rom_strings_and_reports_what_it_cannot_read(self):
        token = "gh" + "p_" + "a1B2c3D4" * 5
        self.assertEqual(self.scanned("a.txt", f"note {token}".encode("utf-16")), ["SECRET"])
        self.assertEqual(self.scanned("b.txt", b"\xff\x00\xfe\x81 not text", warnings=True), ["NOT_TEXT"])
        rom = bytearray(make_rom())
        rom[0x200 : 0x200 + 40] = f"{token}".encode()[:40]
        self.rom.write_bytes(bytes(rom))
        self.assertIn("SECRET", codes(publish_ready.publish_scan.scan(self.root, ["build/game.gbc"])["blocking"]))
        (self.root / "project" / "linked").symlink_to(self.root / "project")
        self.assertEqual(
            codes(publish_ready.publish_scan.scan(self.root, ["project/linked/scene.gbsres"])["blocking"]),
            ["UNREADABLE"],
        )

    def test_a_long_line_costs_little(self):
        started = time.monotonic()
        self.scanned("long.gbsres", "a" * 200_000 + "=" + "b-" * 200_000 + ' "x": ' * 20_000)
        self.assertLess(time.monotonic() - started, 5)

    def test_gb_studios_backups_are_not_published(self):
        (self.root / "project" / "scene.gbsres.bak").write_text("{}")
        (self.root / "project" / "scene.gbsres.new").write_text("{}")
        self.assertNotIn("project/scene.gbsres.bak", release.files(self.root, source=True))
        self.assertNotIn("project/scene.gbsres.new", release.files(self.root, source=True))

    def test_the_scan_refuses_what_an_install_would_and_lists_plugin_code(self):
        big = self.root / "assets" / "music.uge"
        big.parent.mkdir()
        with big.open("wb") as stream:
            stream.truncate(21 * 1024 * 1024)
        (self.root / "plugins" / "fx" / "events").mkdir(parents=True)
        (self.root / "plugins" / "fx" / "events" / "eventShake.js").write_text("module.exports = {};")
        found = publish_ready.scan(self.root, source=True)
        self.assertEqual(codes(found["blocking"]), ["FILE_TOO_LARGE"])
        self.assertEqual(found["warnings"][0]["files"], ["plugins/fx/events/eventShake.js"])
        with mock.patch.object(publish_ready.publish_scan.install_check, "MAX_TOTAL_BYTES", 1024):
            self.assertIn("TOO_LARGE", codes(publish_ready.scan(self.root, source=False)["blocking"]))
        with mock.patch.object(publish_ready.publish_scan.install_check, "MAX_FILES", 2):
            self.assertIn("TOO_MANY", codes(publish_ready.scan(self.root, source=False)["blocking"]))


if __name__ == "__main__":
    unittest.main()
