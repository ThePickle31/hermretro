"""Each backend feature and each page folder carries a README.md, its map for the next person.

One test per area, so work on the backend and on the page never edits the same test file (the map and size
rules stay in tests/repo/test_layout.py).

Run alone: python -m unittest tests.repo.test_readmes
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BackendReadmes(unittest.TestCase):
    def test_features_have_a_readme(self):
        # Each backend feature says what it owns, what it adds and exposes, and where its tests are (pages: PageReadmes).
        missing = []
        for folder in sorted(p for p in (ROOT / "backend").iterdir() if p.is_dir() and not p.name.startswith("__")):
            if not (folder / "README.md").is_file():
                missing.append(f"{folder.relative_to(ROOT)}/README.md")
        self.assertEqual(
            missing,
            [],
            "\nA backend feature's README is its map for the next person: what it does, "
            "what it adds (RPCs, tools, hooks, events), its front door and where its tests are:\n  "
            + "\n  ".join(missing)
            + "\nFIX: add the README (copy the shape of backend/library/README.md)",
        )


class PageReadmes(unittest.TestCase):
    def test_pages_have_a_readme(self):
        # A failure: each page (and the page's app/ and shared/) says what it shows, its tabs, the events it emits
        # and listens to, the slots it declares and fills, its tests, and how to add a tab there.
        page = ROOT / "page"
        folders = [p for p in (page / "pages").iterdir() if p.is_dir()] + [page / "app", page / "shared"]
        missing = [
            f"{folder.relative_to(ROOT)}/README.md"
            for folder in sorted(folders)
            if not (folder / "README.md").is_file()
        ]
        self.assertEqual(
            missing,
            [],
            "\nEvery page folder says what it shows and how it connects to the others:\n  "
            + "\n  ".join(missing)
            + "\nFIX: add the README.md (copy page/pages/games/README.md's "
            "sections: what it shows, tabs, events, slots, tests, adding a tab)",
        )


if __name__ == "__main__":
    unittest.main()
