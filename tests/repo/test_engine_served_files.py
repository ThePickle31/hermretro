"""The browser files the engine serves import only files it serves too. The capture page (`ASSETS` in
`native-device-capture.js`) and the preview (`ANNOTATION_FILES` in `web-preview.js`) each serve their listed files
from one folder URL; a listed module importing anything else fails in the browser with a 404 and never starts.

The lists and the imports are read with the pinned JavaScript parser (tools/engine/npm), so a comment never counts.
Each import is resolved as the browser resolves it, against the importing file's URL in each place its page is
served from, under a capability segment no import can name; only a relative request that lands on a listed file
passes. A listed name must be one the routers serve (each segment plain, never starting with a dot), and each page's
entry script, read from the active <script> tags of the HTML the engine writes, must be listed too."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_ROOT  # noqa: E402 - the repository root goes on sys.path first

SRC = ENGINE_ROOT / "src"
TOOLS = ROOT / "tools" / "engine" / "npm"
NODE = shutil.which("node")
ORIGIN = "https://engine.invalid/capability-9f2c71/"
# Where each page's files are served from, as folder URLs.
PREVIEW = [ORIGIN + "codex-annotations/"]
CAPTURE = [ORIGIN, ORIGIN + "codex-device-view/"]  # the capture page on its own, and inside the preview
# argv: the pinned tools, the module holding the list, the list's name, the folder its entries are relative to, the
# folder URLs they are served from, and whether the server ignores a query. Prints the listed entries and every
# import of theirs that the browser would not find.
CHECK = """
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
const [tools, listModule, listName, folder, basesJson, ignoresQuery] = process.argv.slice(1);
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
const served = declared.init.elements.map((element, index) => {
  if (element?.type !== "Literal" || typeof element.value !== "string")
    throw new Error(`${listName}[${index}] in ${listModule} is not a string literal`);
  return element.value;
});
// A request's text when the source states it: a string, or a template with nothing substituted.
const literal = (source) => source?.type === "Literal" && typeof source.value === "string" ? source.value
  : source?.type === "TemplateLiteral" && source.expressions.length === 0 ? source.quasis[0].value.cooked : null;
const problems = [];
for (const entry of served) {
  const kinds = ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration", "ImportExpression"];
  for (const node of nodes(parse(path.join(folder, entry)))) {
    if (!kinds.includes(node.type) || !node.source) continue;
    const request = literal(node.source);
    if (request === null) continue;  // a computed request: its target is checked by name below
    for (const base of JSON.parse(basesJson)) {
      const url = new URL(request, base + entry);
      const reached = url.href.startsWith(base) ? url.href.slice(base.length) : null;
      // The browser never sends a fragment; the preview's router also drops the query, the capture page's refuses one.
      const sent = reached === null ? null : reached.replace(/#.*$/, "");
      const file = sent === null ? null : ignoresQuery === "yes" ? sent.replace(/\?.*$/, "") : sent;
      if (!/^\\.\\.?\\//.test(request) || file === null || !served.includes(file))
        problems.push(`${entry} imports ${JSON.stringify(request)}, which the page served from ${base} does not serve`);
    }
  }
}
console.log(JSON.stringify({ served, problems }));
"""


# A name both routers serve: plain segments, none starting with a dot (web-preview.js and native-device-capture.js
# refuse those and any of ?#%\\).
SERVABLE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*(?:/[A-Za-z0-9_-][A-Za-z0-9._-]*)*")


def entry_scripts(module: str, mount: str = "") -> list[str]:
    """The module scripts the HTML a page's module writes loads, from its active <script> tags, beside the page (or
    under mount, written as the template's ${...} for it)."""
    text = re.sub(r"<!--.*?-->", "", (SRC / module).read_text(encoding="utf-8"), flags=re.S)
    found = []
    for tag in re.findall(r"<script\b[^>]*>", text):
        source = re.search(r'\bsrc="\./([^"]+)"', tag)
        if re.search(r'\btype="module"', tag) and source:
            found.append(source.group(1).removeprefix(mount))
    assert found, f"{module} writes no module <script>"
    return found


@unittest.skipUnless(NODE and (TOOLS / "node_modules" / "acorn").is_dir(), "node or tools/engine/npm is missing")
class ServedFiles(unittest.TestCase):
    def served(self, module: str, name: str, folder: Path, bases: list[str], ignores_query: bool) -> list[str]:
        command = [NODE, "--input-type=module", "-e", CHECK, str(TOOLS), str(SRC / module), name, str(folder)]
        done = subprocess.run(
            [*command, json.dumps(bases), "yes" if ignores_query else "no"], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        found = json.loads(done.stdout)
        for entry in found["served"]:
            self.assertTrue((folder / entry).is_file(), f"{entry} is listed in {name} but missing")
            self.assertRegex(entry, f"^{SERVABLE.pattern}$", f"{entry} in {name} is a name the routers refuse")
        self.assertEqual(found["problems"], [], f"FIX: list what {name}'s files import, as paths beside them")
        return found["served"]

    def test_the_capture_page_serves_its_entry_and_every_module_its_files_import(self):
        served = self.served("native-device-capture.js", "ASSETS", SRC, CAPTURE, ignores_query=False)
        for entry in entry_scripts("device-capture/page.js"):
            self.assertIn(entry, served, "the capture page's HTML loads it")
        # The preview's Device view loads the capture client from the capture page's files by a computed URL.
        self.assertIn("device-capture/native-client.js", served)

    def test_the_preview_serves_its_entry_and_every_module_its_annotation_files_import(self):
        served = self.served("web-preview.js", "ANNOTATION_FILES", SRC / "web-annotations", PREVIEW, ignores_query=True)
        for entry in entry_scripts("web-preview.js", mount="${ANNOTATION_MOUNT}/"):
            self.assertIn(entry, served, "the preview's HTML loads it")


if __name__ == "__main__":
    unittest.main()
