"""The browser files the engine serves import only files it serves too. The capture page (`ASSETS` in
`native-device-capture.js`) and the preview (`ANNOTATION_FILES` in `web-preview.js`) each list the files they send
under one mount; a listed module importing a URL outside that list fails in the browser with a 404 and never starts.
The lists and the imports are read with the pinned JavaScript parser (tools/engine/npm), so a comment never counts,
and each import is resolved as the browser resolves it: as a URL, against the importing file's own URL."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_ROOT  # noqa: E402 - the repository root goes on sys.path first

TOOLS = ROOT / "tools" / "engine" / "npm"
NODE = shutil.which("node")
# argv: the pinned tools, the module holding the list, the list's name, the folder its entries are relative to.
# Prints the served entries and, per entry, the URLs it imports that leave the mount or are not served.
CHECK = """
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
const [tools, listModule, listName, folder] = process.argv.slice(1);
const acorn = createRequire(path.join(tools, "package.json"))("acorn");
const parse = (file) => acorn.parse(readFileSync(file, "utf8"), { ecmaVersion: "latest", sourceType: "module" });
function* nodes(node) {
  if (!node || typeof node.type !== "string") return;
  yield node;
  for (const value of Object.values(node))
    for (const child of Array.isArray(value) ? value : [value]) if (child && typeof child === "object") yield* nodes(child);
}
const declared = [...nodes(parse(listModule))].find((node) => node.type === "VariableDeclarator" && node.id.name === listName);
if (declared?.init?.type !== "ArrayExpression") throw new Error(`${listModule} has no ${listName} array`);
const served = declared.init.elements.map((element) => element.value);
const mount = "https://engine.invalid/mount/";
const missing = {};
for (const entry of served) {
  const kinds = ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration", "ImportExpression"];
  for (const node of nodes(parse(path.join(folder, entry)))) {
    if (!kinds.includes(node.type) || node.source?.type !== "Literal" || !/^\\.\\.?\\//.test(node.source.value)) continue;
    const url = new URL(node.source.value, mount + entry).href;
    if (!url.startsWith(mount) || !served.includes(url.slice(mount.length))) (missing[entry] ??= []).push(node.source.value);
  }
}
console.log(JSON.stringify({ served, missing }));
"""


@unittest.skipUnless(NODE and (TOOLS / "node_modules" / "acorn").is_dir(), "node or tools/engine/npm is missing")
class ServedFiles(unittest.TestCase):
    def served(self, module: str, name: str, folder: Path) -> list[str]:
        done = subprocess.run(
            [
                NODE,
                "--input-type=module",
                "-e",
                CHECK,
                str(TOOLS),
                str(ENGINE_ROOT / "src" / module),
                name,
                str(folder),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        found = json.loads(done.stdout)
        for entry in found["served"]:
            self.assertTrue((folder / entry).is_file(), f"{entry} is listed in {name} but missing")
        self.assertEqual(found["missing"], {}, f"files in {name} import URLs it does not serve. FIX: list them")
        return found["served"]

    def test_the_capture_page_serves_every_module_its_files_import(self):
        served = self.served("native-device-capture.js", "ASSETS", ENGINE_ROOT / "src")
        # The preview's Device view loads the capture client from the capture page's files.
        self.assertIn("device-capture/native-client.js", served)

    def test_the_preview_serves_every_module_its_annotation_files_import(self):
        self.served("web-preview.js", "ANNOTATION_FILES", ENGINE_ROOT / "src" / "web-annotations")


if __name__ == "__main__":
    unittest.main()
