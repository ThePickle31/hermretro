"""Where an installed game comes from (backend/library/install_source.py): links, the transports installed from, and
links that carry credentials.

Run alone: python -m unittest tests.backend.library.test_install_source
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library.install_source import Source, SourceError, from_record, resolve, within  # noqa: E402
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

GH = "https://github.com/"


class Links(unittest.TestCase):
    def test_every_spelling_of_a_link(self):
        table = {
            "owner/repo": Source(GH + "owner/repo.git"),
            "owner/repo.git": Source(GH + "owner/repo.git"),
            "owner/repo/games/space": Source(GH + "owner/repo.git", None, "games/space"),
            "owner/repo#games/space": Source(GH + "owner/repo.git", None, "games/space"),
            "https://github.com/owner/repo": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo.git": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo/": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo#games/space": Source(GH + "owner/repo.git", None, "games/space"),
            "git@github.com:owner/repo.git": Source("git@github.com:owner/repo.git"),
            "git@host.example:owner/repo.git#space": Source("git@host.example:owner/repo.git", None, "space"),
            "ssh://git@host.example:2222/owner/repo.git": Source("ssh://git@host.example:2222/owner/repo.git"),
        }
        for link, expected in table.items():
            with self.subTest(link):
                self.assertEqual(resolve(link), expected)

    def test_a_tree_link_is_settled_against_the_repositorys_branches_later(self):
        source = resolve("https://github.com/owner/repo/tree/feature/demo")
        self.assertEqual((source.ref, source.subdir, source.tree), (None, None, "feature/demo"))

    def test_links_that_are_refused(self):
        for link in (
            "",
            "repo",
            "owner/repo/../../etc",
            "owner/repo#a/../b",
            "https://github.com/owner",
            "https://github.com/owner/repo/blob/main/game.json",
            "https://github.com/owner/repo/tree/-x",
            "owner/repo with space",
            "https://github.com:abc/owner/repo",  # urllib's ValueError is a BAD_LINK too
            "https://gitlab.example/me/game.git",  # HTTPS only to GitHub
            "http://github.com/owner/repo",
            "https://user:s3cret@github.com/owner/repo",
            "https://token@github.com/owner/repo",
            "https://github.com/owner/repo?token=abc",
            "ssh://git:pw@host.example/owner/repo.git",
            "git@-oProxyCommand=x:owner/repo",
            "git@host:-upload-pack=x",
            "file:///srv/games/space",  # only where local sources are allowed
            "ftp://host/repo",
        ):
            with self.subTest(link), self.assertRaises(SourceError) as refused:
                resolve(link)
            self.assertEqual(refused.exception.code, "BAD_LINK")
        self.assertEqual(resolve("file:///srv/games/space", allow_local=True), Source("file:///srv/games/space"))

    def test_one_canonical_spelling_without_branch_or_user(self):
        spellings = ["owner/Repo", "https://github.com/owner/repo.git", "https://github.com/Owner/repo/"]
        self.assertEqual({resolve(link).canonical for link in spellings}, {GH + "owner/repo"})
        self.assertEqual(Source(GH + "o/r.git", "dev", "x").canonical, Source(GH + "o/r.git", "main", "x").canonical)
        self.assertEqual(resolve("git@host.example:o/r.git").canonical, "ssh://host.example/o/r")
        self.assertEqual(resolve("ssh://git@host.example:2222/o/r.git").canonical, "ssh://host.example:2222/o/r")

    def test_a_recorded_source_is_checked_again(self):
        good = {"url": GH + "o/r.git", "ref": "main", "subdir": None}
        self.assertEqual(from_record(good), Source(GH + "o/r.git", "main"))
        for damaged in (
            {**good, "url": "https://evil.example/o/r.git"},
            {**good, "url": "file:///tmp/repo"},
            {**good, "ref": "--upload-pack=x"},
            {**good, "subdir": "../outside"},
            {**good, "url": 7},
        ):
            with self.subTest(damaged), self.assertRaises(SourceError):
                from_record(damaged)
        self.assertEqual(from_record({**good, "url": "file:///tmp/repo"}, allow_local=True).url, "file:///tmp/repo")


class Within(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def test_a_subfolder_stays_inside_the_checkout(self):
        root = self.home.base / "checkout"
        (root / "games" / "space").mkdir(parents=True)
        (root / "outside").symlink_to(self.home.base)
        self.assertEqual(within(root, "games/space"), (root / "games" / "space").resolve())
        for subdir in ("outside", "missing", "../x"):
            with self.subTest(subdir), self.assertRaises(SourceError):
                within(root, subdir)


if __name__ == "__main__":
    unittest.main()
