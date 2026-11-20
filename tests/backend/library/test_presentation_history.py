"""The presentation history keeps the newest N records, N as docs/dev/STUDIO-PAGES.md states ("newest 100 kept").

Run alone: python -m unittest tests.backend.library.test_presentation_history

Each record is written by the real Registry.present and read back from the registry and through the desktop's
``presentations`` RPC. The clock is a fixed sequence, so the order and every field are known in advance.
isolated_home(self) (tests/support.py) points HERMRETRO_HOME and the plugin's data folder at a temp folder: never
the real library.
"""

import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

ROOT = Path(__file__).resolve().parents[3]
START = 1_700_000_000.0  # the fake clock's first reading; record i is presented at START + i
RPC_LIMIT = 20  # the RPC answers the newest 20 at most, oldest first (its section in docs/dev/STUDIO-PAGES.md)


def documented_cap() -> int:
    """The 'newest N kept' of the presentations RPC section in docs/dev/STUDIO-PAGES.md."""
    text = (ROOT / "docs" / "dev" / "STUDIO-PAGES.md").read_text()
    section = text.split("### `presentations`", 1)[1].split("\n### ", 1)[0]
    found = re.findall(r"newest (\d+) kept", section)
    if len(found) != 1:
        raise AssertionError(f"STUDIO-PAGES.md presentations section: expected one 'newest N kept', found {found}")
    return int(found[0])


class PresentationHistory(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)  # Registry.present runs for real; the RPC reads the same temp library
        self.cap = documented_cap()
        self.here = hermes_host._profile_identity()
        self.elsewhere = str(self.home.base / "hermes" / "profiles" / "studio" / "plugin-data" / "hermretro")
        games_dir = paths.games_dir(create=True)
        self.roots = [make_project(games_dir, name) for name in ("Alpha Game", "Beta Game", "Gamma Game")]
        self.titles = ["Alpha Game", "Beta Game", "Gamma Game"]
        self.registry = hermes_host._registry()
        self.count = 0
        clock = SimpleNamespace(time=lambda: START + self.count)
        patch = mock.patch.object(games, "time", clock)  # only games.py's clock: one known instant per record
        patch.start()
        self.addCleanup(patch.stop)

    def present(self) -> dict:
        """Present record ``self.count`` and return the record the registry should keep for it."""
        index = self.count
        owner = self.here if index % 2 == 0 else self.elsewhere
        chat = {"sessionId": f"run-{index}", "conversationId": f"conv-{index}", "profile": owner}
        shown = self.registry.present(str(self.roots[index % 3]), chat=chat, note=f"  note {index}  ")
        self.assertIsNotNone(shown, index)
        self.count += 1
        return {
            "gameId": games.game_id(self.roots[index % 3]),
            "t": START + index,
            "note": f"note {index}",
            "title": self.titles[index % 3],
            "sessionId": f"run-{index}",
            "conversationId": f"conv-{index}",
            "profile": owner,
        }

    def desktop_view(self, records: list[dict]) -> list[dict]:
        """What the presentations RPC answers for these kept records: the newest 20, oldest first."""
        return [
            {
                "gameId": record["gameId"],
                "title": record["title"],
                "t": record["t"],
                "note": record["note"],
                "sessionId": record["sessionId"],
                "conversationId": record["conversationId"],
                "profile": "default" if record["profile"] == self.here else "studio",
                "thisProfile": record["profile"] == self.here,
            }
            for record in records[-RPC_LIMIT:]
        ]

    def assert_kept(self, expected: list[dict]) -> None:
        self.assertEqual(self.registry.load()["presentations"], expected, "stored records, in order")
        self.assertEqual(self.registry.presentations(), expected, "Registry.presentations()")
        answer = library_rpcs.rpc_presentations(None)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["presentations"], self.desktop_view(expected), "the desktop's presentations RPC")
        oldest = library_rpcs.rpc_presentations(None)({"since": expected[0]["t"] - 0.5})["presentations"]
        self.assertEqual(oldest, self.desktop_view(expected), "since just before the oldest kept record")

    def test_the_documented_cap_is_the_code_constant(self):
        self.assertEqual(self.cap, games.MAX_PRESENTATIONS)
        self.assertGreater(self.cap, RPC_LIMIT, "the cap is past the RPC's own 20")

    def test_exactly_the_cap_keeps_every_record(self):
        expected = [self.present() for _ in range(self.cap)]
        self.assertEqual(len(expected), self.cap)
        self.assert_kept(expected)

    def test_one_past_the_cap_drops_only_the_oldest(self):
        expected = [self.present() for _ in range(self.cap)]
        expected.append(self.present())
        kept = expected[1:]
        self.assertEqual(len(kept), self.cap)
        self.assert_kept(kept)
        self.assertNotIn("conv-0", [item["conversationId"] for item in self.registry.presentations()])
        self.assertEqual(self.registry.presentations(since=START)[0]["conversationId"], "conv-1")


if __name__ == "__main__":
    unittest.main()
