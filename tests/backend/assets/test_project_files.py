"""backend/assets/project_files.py: project_images walks <root>/assets/<folder>/ for a project's images.

Run alone: python -m unittest tests.backend.assets.test_project_files
"""

import os
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

    def test_relative_root_and_symlinked_root_list_the_same_images(self):
        # The containment check compares against the resolved root, so neither "." nor a link to the project
        # rejects every image; the outside link stays out either way.
        expected = self.listed()
        link = self.outside.parent / "game-link"
        link.symlink_to(self.root, target_is_directory=True)
        found = [(image.relative_to(link).as_posix(), kind) for image, _real, kind in project_images(link)]
        self.assertEqual(found, expected)
        self.assertTrue(all(real.is_relative_to(self.root) for _image, real, _kind in project_images(link)))
        previous = os.getcwd()
        os.chdir(self.root)
        try:
            found = [(image.as_posix(), kind) for image, _real, kind in project_images(Path("."))]
        finally:
            os.chdir(previous)
        self.assertEqual(found, expected)


if __name__ == "__main__":
    unittest.main()
