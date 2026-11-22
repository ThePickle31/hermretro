"""The game card limits in .agents/skills/hermretro-dev-architecture/references/contract.md, game_card's constants and chromatic_game_info's schema agree."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.library import game_card  # noqa: E402 - the repository root goes on sys.path first
from backend.library import game_cover  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first

CONTRACT = ROOT / ".agents/skills/hermretro-dev-architecture/references/contract.md"


def card_section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## The game card")
    end = text.find("\n## ", start + 1)
    return " ".join(text[start : end if end > 0 else len(text)].split())


def number(pattern: str, text: str) -> int:
    found = re.search(pattern, text)
    if not found:
        raise AssertionError(
            f".agents/skills/hermretro-dev-architecture/references/contract.md's game card section no longer matches {pattern!r}"
        )
    return int(found.group(1))


class ContractLimits(unittest.TestCase):
    """Each number the CONTRACT gives for the card is the one game_card enforces (a changed limit changes both)."""

    def setUp(self):
        self.doc = card_section()

    def test_text_field_ranges(self):
        for field in ("title", "tagline", "description"):
            low = number(rf"\b{field} \((\d+)–\d+\)", self.doc)
            high = number(rf"\b{field} \(\d+–(\d+)\)", self.doc)
            self.assertEqual((low, high), game_card.LIMITS[field], field)
        self.assertEqual(number(r"about \(≤(\d+)\)", self.doc), game_card.LIMITS["about"][1])

    def test_list_limits(self):
        self.assertEqual(number(r"1–(\d+) genres", self.doc), game_card.MAX_GENRES)
        self.assertEqual(number(r"tags \(≤(\d+),", self.doc), game_card.MAX_TAGS)
        self.assertEqual(number(r"tags \(≤\d+, ≤(\d+) chars\)", self.doc), game_card.MAX_TAG_CHARS)
        self.assertEqual(number(r"controls \(≤(\d+),", self.doc), game_card.MAX_CONTROLS)
        self.assertEqual(number(r"button ≤(\d+) chars", self.doc), game_card.MAX_BUTTON_CHARS)
        self.assertEqual(number(r"action ≤(\d+) chars", self.doc), game_card.MAX_CONTROL_CHARS)

    def test_genre_names(self):
        found = re.search(r"genres from `([^`]+)`", self.doc)
        self.assertIsNotNone(found, "the CONTRACT lists the genres in one code span")
        self.assertEqual(tuple(g.strip() for g in found.group(1).split(",")), game_card.GENRES)

    def test_file_sizes_and_cover(self):
        self.assertEqual(number(r"`game\.json` is at most (\d+) KB", self.doc) * 1024, game_card.MAX_CARD_BYTES)
        self.assertEqual(number(r"a PNG of at most (\d+) KB", self.doc) * 1024, game_cover.MAX_COVER_BYTES)
        self.assertEqual(number(r"exactly (\d+)×\d+", self.doc), game_card.COVER_WIDTH)
        self.assertEqual(number(r"exactly \d+×(\d+)", self.doc), game_card.COVER_HEIGHT)
        self.assertEqual(number(r"(\d+)–\d+ colours", self.doc), game_cover.MIN_COVER_COLOURS)
        self.assertEqual(number(r"\d+–(\d+) colours", self.doc), game_card.MAX_COVER_COLOURS)


class SchemaLimits(unittest.TestCase):
    """chromatic_game_info's schema caps each field at game_card's limit, so the agent hears the same numbers."""

    def test_schema(self):
        props = library_tools.GAME_INFO_TOOL["parameters"]["properties"]
        self.assertNotIn("required", library_tools.GAME_INFO_TOOL["parameters"])
        for field, (_low, high) in game_card.LIMITS.items():
            self.assertEqual(props[field]["maxLength"], high, field)
        self.assertEqual(props["genres"]["maxItems"], game_card.MAX_GENRES)
        self.assertEqual(props["genres"]["items"]["enum"], list(game_card.GENRES))
        self.assertIn(str(game_card.MAX_GENRES), props["genres"]["description"])
        self.assertEqual(props["tags"]["maxItems"], game_card.MAX_TAGS)
        self.assertEqual(props["tags"]["items"]["maxLength"], game_card.MAX_TAG_CHARS)
        self.assertEqual(props["controls"]["maxProperties"], game_card.MAX_CONTROLS)
        self.assertEqual(props["controls"]["additionalProperties"]["maxLength"], game_card.MAX_CONTROL_CHARS)


if __name__ == "__main__":
    unittest.main()
