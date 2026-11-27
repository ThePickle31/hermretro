"""The browser files the engine serves import only files it serves too. The capture page (`ASSETS` in
`native-device-capture.js`) and the preview (`ANNOTATION_FILES` in `web-preview.js`) each serve their listed files
from one folder URL; a listed module importing anything else fails in the browser with a 404 and never starts.

`engine_served_files.mjs` reads the lists and the imports with the pinned JavaScript parser (tools/engine/npm), so a
comment never counts, and resolves each request as the browser does (WHATWG URL), against the importing file's URL in
each place its page is served from, under a capability segment no import can name: only a relative request that
lands on a listed file passes. Each page's entry scripts, read with an HTML parser from the HTML the engine writes,
are resolved the same way from the page's URL. A listed name must be one the routers serve."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_ROOT  # noqa: E402 - the repository root goes on sys.path first

SRC = ENGINE_ROOT / "src"
TOOLS = ROOT / "tools" / "engine" / "npm"
SCRIPT = Path(__file__).with_name("engine_served_files.mjs")
NODE = shutil.which("node")
ORIGIN = "https://engine.invalid/capability-9f2c71/"
# Where each page's files are served from, as folder URLs: the preview page is at ORIGIN, its files under its mount;
# the capture page's files are beside it, on its own or inside the preview.
PREVIEW = [ORIGIN + "codex-annotations/"]
CAPTURE = [ORIGIN, ORIGIN + "codex-device-view/"]
# A name both routers serve: plain segments, none starting with a dot (web-preview.js and native-device-capture.js
# refuse those and any of ?#%\).
SERVABLE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*(?:/[A-Za-z0-9_-][A-Za-z0-9._-]*)*")


class ModuleScripts(HTMLParser):
    """The src of each <script type="module"> in HTML, read the way a browser reads its attributes."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "module" and attributes.get("src"):
            self.found.append(attributes["src"])


def entry_scripts(module: str, substitutions: dict[str, str] | None = None) -> list[str]:
    """The src of each module script in the HTML a page's module writes, as written there."""
    text = (SRC / module).read_text(encoding="utf-8")
    for name, value in (substitutions or {}).items():
        text = text.replace("${" + name + "}", value)
    parser = ModuleScripts()
    parser.feed(text)
    assert parser.found, f"{module} writes no module <script>"
    return parser.found


def string_constant(module: str, name: str) -> str:
    found = re.search(rf'const {name} = "([^"]+)";', (SRC / module).read_text(encoding="utf-8"))
    assert found, f"{module} has no {name}"
    return found.group(1)


@unittest.skipUnless(NODE and (TOOLS / "node_modules" / "acorn").is_dir(), "node or tools/engine/npm is missing")
class ServedFiles(unittest.TestCase):
    def served(self, module: str, name: str, folder: Path, bases: list[str], *, ignores_query: bool, entries) -> list:
        done = subprocess.run(
            [
                NODE,
                str(SCRIPT),
                str(TOOLS),
                str(SRC / module),
                name,
                str(folder),
                json.dumps(bases),
                "yes" if ignores_query else "no",
                json.dumps(entries),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        found = json.loads(done.stdout)
        for entry in found["served"]:
            self.assertTrue((folder / entry).is_file(), f"{entry} is listed in {name} but missing")
            self.assertRegex(entry, f"^{SERVABLE.pattern}$", f"{entry} in {name} is a name the routers refuse")
        self.assertEqual(found["problems"], [], f"FIX: serve what the page loads, as files on {name}")
        return found["served"]

    def test_the_capture_page_serves_its_entry_and_every_module_its_files_import(self):
        entries = [[page, page, source] for page in CAPTURE for source in entry_scripts("device-capture/page.js")]
        served = self.served("native-device-capture.js", "ASSETS", SRC, CAPTURE, ignores_query=False, entries=entries)
        # The preview's Device view loads the capture client from the capture page's files by a computed URL.
        self.assertIn("device-capture/native-client.js", served)

    def test_the_preview_serves_its_entry_and_every_module_its_annotation_files_import(self):
        mount = string_constant("web-preview.js", "ANNOTATION_MOUNT")
        entries = [[ORIGIN, PREVIEW[0], src] for src in entry_scripts("web-preview.js", {"ANNOTATION_MOUNT": mount})]
        folder = SRC / "web-annotations"
        self.served("web-preview.js", "ANNOTATION_FILES", folder, PREVIEW, ignores_query=True, entries=entries)


if __name__ == "__main__":
    unittest.main()
