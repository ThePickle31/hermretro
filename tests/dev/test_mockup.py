"""tools/dev/mockup.py: mockup labels and titles, and the gallery that carries every picture inside it."""

import base64
import contextlib
import io
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOP / "tools" / "dev"))
_spec = importlib.util.spec_from_file_location("mockup", TOP / "tools" / "dev" / "mockup.py")
mockup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mockup)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class MockupTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        (self.folder / "mockups").mkdir()

    def test_labels_are_the_part_before_the_first_dash(self):
        self.assertEqual(mockup.label("b2-dock"), "B2")
        self.assertEqual(mockup.label("current"), "Now")

    def test_titles_come_from_the_mockup_source(self):
        (self.folder / "mockups" / "a-stage.jsx").write_text("export const title = 'Stage beside the chat'\n")
        (self.folder / "mockups" / "b-plain.jsx").write_text("export function BuildPage() {}\n")
        found = mockup.titles(self.folder, ["a-stage", "b-plain"])
        self.assertEqual(found, {"current": "Today", "a-stage": "Stage beside the chat", "b-plain": "b-plain"})

    def test_the_gallery_holds_every_picture_and_cannot_be_closed_early(self):
        shot = self.folder / "shot.png"
        shot.write_bytes(PNG)
        entry = {"file": str(shot), "mockup": "a-x", "label": "A", "title": "</script><b>", "state": "builds",
                 "width": 1440, "theme": "dark"}  # fmt: skip
        with contextlib.redirect_stdout(io.StringIO()):
            page = mockup.gallery(self.folder, [entry]).read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64," + base64.b64encode(PNG).decode(), page)
        self.assertNotIn("</script><b>", page)
        data = page.split("const SHOTS = ", 1)[1].split("\n", 1)[0]
        self.assertEqual(json.loads(data.replace("<\\/", "</"))[0]["title"], "</script><b>")


if __name__ == "__main__":
    unittest.main()
