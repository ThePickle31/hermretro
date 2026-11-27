"""The browser files the engine serves import only files it serves too. The capture page (`ASSETS` in
`native-device-capture.js`) and the preview (`ANNOTATION_FILES` in `web-preview.js`) each list the files they send;
a listed module importing one left off its list fails in the browser with a 404 and never starts. The imports are
read with the pinned JavaScript parser (tools/engine/npm), so comments and strings never count as one."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_ROOT  # noqa: E402 - the repository root goes on sys.path first

SRC = ENGINE_ROOT / "src"
TOOLS = ROOT / "tools" / "engine" / "npm"
NODE = shutil.which("node")
# Every relative module a file names: import and export declarations (a side-effect `import "./x.js"` too) and
# dynamic imports of a string literal.
PARSE = """
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const acorn = createRequire(process.argv[1] + "/package.json")("acorn");
const found = {};
for (const file of JSON.parse(process.argv[2])) {
  const tree = acorn.parse(readFileSync(file, "utf8"), { ecmaVersion: "latest", sourceType: "module" });
  const sources = [];
  (function walk(node) {
    if (!node || typeof node.type !== "string") return;
    const named = ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration", "ImportExpression"];
    if (named.includes(node.type) && node.source?.type === "Literal") sources.push(node.source.value);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === "object") walk(value);
    }
  })(tree);
  found[file] = sources;
}
console.log(JSON.stringify(found));
"""


def listed(module: str, name: str) -> list[str]:
    text = (SRC / module).read_text(encoding="utf-8")
    found = re.search(rf"const {name} = \[([^\]]*)\]", text)
    assert found, f"{module} has no {name} list"
    return re.findall(r'"([^"]+)"', found.group(1))


def resolved(relative: str, request: str) -> str:
    """A module request from src/<relative>, as a path relative to src/."""
    parts: list[str] = []
    for part in PurePosixPath(PurePosixPath(relative).parent, request).as_posix().split("/"):
        if part == "..":
            parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


@unittest.skipUnless(NODE and (TOOLS / "node_modules" / "acorn").is_dir(), "node or tools/engine/npm is missing")
class ServedFiles(unittest.TestCase):
    def imports(self, served: set[str]) -> dict[str, set[str]]:
        files = {str(SRC / relative): relative for relative in served}
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", PARSE, str(TOOLS), json.dumps(sorted(files))],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return {
            files[file]: {resolved(files[file], request) for request in requests if request.startswith(".")}
            for file, requests in json.loads(done.stdout).items()
        }

    def check(self, served: set[str]):
        for relative in sorted(served):
            self.assertTrue((SRC / relative).is_file(), f"src/{relative} is listed but missing")
        for relative, targets in sorted(self.imports(served).items()):
            with self.subTest(file=relative):
                missing = sorted(target for target in targets if target not in served)
                self.assertEqual(missing, [], f"src/{relative} imports files its page does not serve. FIX: list them")

    def test_the_capture_page_serves_every_module_its_files_import(self):
        assets = set(listed("native-device-capture.js", "ASSETS"))
        self.check(assets)
        # The preview's Device view loads the capture client from the capture page's files.
        self.assertIn("device-capture/native-client.js", assets)

    def test_the_preview_serves_every_module_its_annotation_files_import(self):
        self.check({f"web-annotations/{name}" for name in listed("web-preview.js", "ANNOTATION_FILES")})


if __name__ == "__main__":
    unittest.main()
