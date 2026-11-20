"""The snapshot limits in docs/dev/CONTRACT.md's build history paragraph are the ones snapshots enforces."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.history import snapshots  # noqa: E402 - the repository root goes on sys.path first

CONTRACT = ROOT / "docs" / "dev" / "CONTRACT.md"


def history_section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## Build history (snapshots)")
    end = text.find("\n## ", start + 1)
    return " ".join(text[start : end if end > 0 else len(text)].split())


def number(pattern: str, text: str) -> int:
    """The number the pattern's group holds, with its thousands spaces (``20 000``) removed."""
    found = re.search(pattern, text)
    if not found:
        raise AssertionError(f"docs/dev/CONTRACT.md's build history section no longer matches {pattern!r}")
    return int(re.sub(r"\s", "", found.group(1)))


class ContractLimits(unittest.TestCase):
    """A changed limit changes the CONTRACT's paragraph too, and the reverse."""

    def setUp(self):
        self.doc = history_section()

    def test_size_cap(self):
        self.assertEqual(number(r"A project over (\d+) MB", self.doc) * 1024 * 1024, snapshots.MAX_BYTES)

    def test_file_cap(self):
        self.assertEqual(number(r"or ([\d\s]*\d) files is skipped", self.doc), snapshots.MAX_FILES)

    def test_kept_count(self):
        self.assertEqual(number(r"The newest (\d+) are kept", self.doc), snapshots.KEEP)


if __name__ == "__main__":
    unittest.main()
