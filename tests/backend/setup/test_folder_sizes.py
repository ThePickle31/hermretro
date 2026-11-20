"""The two folder-size helpers: download_bytes (downloads/ and cache/ only) and folder_bytes (the whole tree)."""

import os
import tempfile
import unittest
from pathlib import Path

from backend import setup


class FolderSizesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel, size in (("downloads/a.zip", 100), ("cache/deep/b.bin", 20), ("bin/tool", 3), ("top.txt", 4)):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_bytes(b"x" * size)

    def test_download_bytes_counts_only_downloads_and_cache(self):
        self.assertEqual(setup.download_bytes(self.root), 120)

    def test_folder_bytes_counts_the_whole_tree_without_following_links(self):
        os.symlink(self.root / "downloads", self.root / "link")
        link = (self.root / "link").lstat().st_size
        self.assertEqual(setup.folder_bytes(self.root), 127 + link)
        self.assertEqual(setup.folder_bytes(self.root / "top.txt"), 4)


if __name__ == "__main__":
    unittest.main()
