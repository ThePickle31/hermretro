"""The browser files the engine serves import only files it serves too. The capture page (`ASSETS` in
`native-device-capture.js`) and the preview (`ANNOTATION_FILES` in `web-preview.js`) each list the files they send;
a listed module importing one left off its list fails in the browser with a 404 and never starts."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_ROOT  # noqa: E402 - the repository root goes on sys.path first

SRC = ENGINE_ROOT / "src"
IMPORT = re.compile(
    r"""(?:^|;|\n)\s*(?:import|export)\b[^'"]*?from\s*["'](\.{1,2}/[^"']+)["']|import\(\s*["'](\.{1,2}/[^"']+)["']"""
)


def listed(module: str, name: str) -> list[str]:
    text = (SRC / module).read_text(encoding="utf-8")
    found = re.search(rf"const {name} = \[([^\]]*)\]", text)
    assert found, f"{module} has no {name} list"
    return re.findall(r'"([^"]+)"', found.group(1))


def imports(relative: str) -> set[str]:
    """The files a served module imports, relative to src/ (its own folder for a bare name)."""
    text = (SRC / relative).read_text(encoding="utf-8")
    folder = PurePosixPath(relative).parent
    found = set()
    for static, dynamic in IMPORT.findall(text):
        target = PurePosixPath(folder, static or dynamic).as_posix()
        parts: list[str] = []
        for part in target.split("/"):
            if part == "..":
                parts.pop()
            elif part != ".":
                parts.append(part)
        found.add("/".join(parts))
    return found


class ServedFiles(unittest.TestCase):
    def check(self, served: set[str]):
        for relative in sorted(served):
            with self.subTest(file=relative):
                self.assertTrue((SRC / relative).is_file(), f"src/{relative} is listed but missing")
                missing = sorted(
                    target for target in imports(relative) if target.endswith(".js") and target not in served
                )
                self.assertEqual(missing, [], f"src/{relative} imports files its page does not serve. FIX: list them")

    def test_the_capture_page_serves_every_module_its_files_import(self):
        self.check(set(listed("native-device-capture.js", "ASSETS")))

    def test_the_preview_serves_every_module_its_annotation_files_import(self):
        self.check({f"web-annotations/{name}" for name in listed("web-preview.js", "ANNOTATION_FILES")})


if __name__ == "__main__":
    unittest.main()
