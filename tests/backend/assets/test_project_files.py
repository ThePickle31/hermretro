"""backend/assets/project_files.py: project_images walks <root>/assets/<folder>/ for a project's images.

Run alone: python -m unittest tests.backend.assets.test_project_files
"""

import tempfile
import unittest
from pathlib import Path

from backend.assets.project_files import ASSET_FOLDERS, project_images


class ProjectImages(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.root, self.outside = base / "game", base / "outside"
        self.outside.mkdir()
        for folder, files in {
            "sprites": ("cat.png", "bird.PNG", "cat.png.gbsres", "notes.txt"),
            "sprites/more": ("dog.png",),
            "backgrounds": ("field.png",),
            "ui": ("frame.png",),
            "fonts": ("font.png",),
            "music": ("song.png",),
        }.items():
            (self.root / "assets" / folder).mkdir(parents=True, exist_ok=True)
            for name in files:
                (self.root / "assets" / folder / name).write_bytes(b"x")
        (self.outside / "secret.png").write_bytes(b"x")
        (self.root / "assets" / "sprites" / "link.png").symlink_to(self.outside / "secret.png")

    def listed(self, **kwargs):
        return [
            (image.relative_to(self.root).as_posix(), kind)
            for image, _real, kind in project_images(self.root, **kwargs)
        ]

    def test_every_image_in_folder_order_never_outside(self):
        self.assertEqual(
            self.listed(),
            [
                ("assets/sprites/bird.PNG", "sprite"),
                ("assets/sprites/cat.png", "sprite"),
                ("assets/sprites/more/dog.png", "sprite"),
                ("assets/backgrounds/field.png", "background"),
                ("assets/ui/frame.png", "ui"),
                ("assets/fonts/font.png", "ui"),
            ],
        )
        self.assertEqual([folder for folder, _kind in ASSET_FOLDERS], ["sprites", "backgrounds", "ui", "fonts"])

    def test_kinds_filter_and_counting(self):
        self.assertEqual(self.listed(kinds=("background",)), [("assets/backgrounds/field.png", "background")])
        self.assertEqual(sum(1 for _ in project_images(self.root, kinds={"sprite"})), 3)
        self.assertEqual(list(project_images(self.outside)), [])  # no assets folder


if __name__ == "__main__":
    unittest.main()
