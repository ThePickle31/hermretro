"""Only real documents are committed; an agent's working notes stay in notes/.

Agents write plans, reports, logs and summaries while they work. Those belong in notes/ (git-ignored), never in
the repository: a stray one in a feature folder misleads the next reader and ships to every user. Every
committed document is listed in tools/layout.toml [docs] with its purpose; any other fails here.

Run alone: python -m unittest tests.repo.test_docs
"""

import fnmatch
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo.test_layout import LAYOUT, files  # noqa: E402 - the repository root goes on the path first

# What counts as a document. Source, data and config files are judged by the layout test instead.
DOCUMENT = (".md", ".markdown", ".txt", ".rst", ".adoc", ".org", ".log")
SKIPPED = ("engine/modretro-chromatic/", "tools/npm/")  # the engine's own documents (from ModRetro), and vendored tools


def unlisted(names: list[str], allowed: dict[str, str]) -> list[str]:
    return [
        name
        for name in names
        if name.lower().endswith(DOCUMENT)
        and not name.startswith(SKIPPED)
        and not any(fnmatch.fnmatch(name, pattern) for pattern in allowed)
    ]


class Docs(unittest.TestCase):
    def test_every_document_is_a_listed_one(self):
        stray = unlisted(files(), LAYOUT["docs"])
        self.assertEqual(
            stray,
            [],
            "\nThese look like working notes, not documents of the plugin:\n  "
            + "\n  ".join(stray)
            + "\nFIX: move plans, reports, notes, logs and summaries to notes/ (never committed). If one is a real "
            "document, list it in tools/layout.toml [docs] with its purpose.",
        )

    def test_every_listed_document_exists(self):
        names = files()
        gone = [pattern for pattern in LAYOUT["docs"] if not any(fnmatch.fnmatch(n, pattern) for n in names)]
        self.assertEqual(
            gone,
            [],
            "\nListed in tools/layout.toml [docs] but not in the tree:\n  "
            + "\n  ".join(gone)
            + "\nFIX: remove the line, or restore the document",
        )

    def test_the_rule_catches_a_stray_note(self):
        allowed = LAYOUT["docs"]
        for stray in (
            "SUMMARY.md",
            "backend/library/PLAN.md",
            ".agents/skills/hermretro-dev-page/review-notes.md",
            "page/pages/build/run.log",
            "tests/report.txt",
            "skills/setup/NOTES.md",
        ):
            self.assertEqual(unlisted([stray], allowed), [stray], stray)
        self.assertEqual(unlisted(["backend/library/README.md", "skills/setup/SKILL.md"], allowed), [])


if __name__ == "__main__":
    unittest.main()
