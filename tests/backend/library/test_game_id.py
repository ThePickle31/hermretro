"""game_id and valid_id: a game's id is exactly 12 lower-case hex digits, and nothing else passes."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import game_id, valid_id  # noqa: E402 - the repository root goes on sys.path first


class GameId(unittest.TestCase):
    def test_twelve_lower_case_hex_digits_are_valid(self):
        self.assertTrue(valid_id("0123456789ab"))
        self.assertTrue(valid_id("abcdef012345"))

    def test_a_made_id_is_valid(self):
        self.assertTrue(valid_id(game_id("/some/project")))
        self.assertEqual(len(game_id("/some/project")), 12)

    def test_the_wrong_length_is_refused(self):
        for value in ("", "0123456789a", "0123456789abc", "0" * 40):
            self.assertFalse(valid_id(value), value)

    def test_upper_case_and_non_hex_are_refused(self):
        for value in ("0123456789AB", "ABCDEF012345", "0123456789ag", "0123456789a-", "01234 6789ab", "../../etc/pa"):
            self.assertFalse(valid_id(value), value)

    def test_a_non_string_is_refused(self):
        for value in (None, 123456789012, b"0123456789ab", ["0123456789ab"], {"id": "0123456789ab"}):
            self.assertFalse(valid_id(value), value)


if __name__ == "__main__":
    unittest.main()
