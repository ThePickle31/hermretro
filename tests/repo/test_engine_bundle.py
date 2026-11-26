"""tools/engine/bundle.mjs and compare_bundles.mjs: an engine built from its modules runs, holds every module and the
packages they import, keeps scripts/ beside it, refuses a package without its licence, and its --check sees a
changed byte; the comparison ignores what a bundler changes (layout, renumbered names) and nothing else. The pinned
packages in tools/engine/npm are the engine's own locked versions."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "engine"
NODE = shutil.which("node")
INSTALLED = (TOOLS / "npm" / "node_modules" / "esbuild" / "package.json").is_file()

ENGINE = {
    "package.json": '{"type": "module"}\n',
    "dist/greet.js": (
        'import path from "node:path";\n'
        'import { PNG } from "pngjs";\n'
        "export function greet(name) {\n"
        "  return `${path.basename(name)}:${typeof PNG}`;\n"
        "}\n"
    ),
    "scripts/helper.mjs": 'export const suffix = "!";\n',
    "licenses/bundled-javascript.txt": "# Bundled JavaScript dependency licenses\n\n## pngjs@7.0.0\n\nMIT\n",
}
ENTRY = (
    'import { greet } from "./greet.js";\nimport { suffix } from "../scripts/helper.mjs";\n'
    'export const said = greet("/a/b") + suffix;\n'
)


@unittest.skipUnless(NODE and INSTALLED, "node or tools/engine/npm is missing (npm ci --prefix tools/engine/npm)")
class EngineBundleTests(unittest.TestCase):
    def setUp(self):
        self.engine = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for rel, text in ENGINE.items():
            (self.engine / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.engine / rel).write_text(text)
        self.entry = self.engine / "entry.js"
        self.entry.write_text(ENTRY)
        self.bundle = self.engine / "dist" / "server.js"

    def node(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([NODE, *args], cwd=ROOT, capture_output=True, text=True, timeout=120)

    def build(self, *extra: str) -> subprocess.CompletedProcess:
        return self.node(str(TOOLS / "bundle.mjs"), "--engine", str(self.engine), "--entry", str(self.entry), *extra)

    def test_the_bundle_runs_and_keeps_scripts_beside_it(self):
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        text = self.bundle.read_text()
        for module in ("// dist/greet.js", "// dist/server.js", "// node_modules/pngjs/lib/png.js"):
            self.assertIn(module, text)
        self.assertIn('from "../scripts/helper.mjs"', text)
        self.assertTrue(text.startswith('import { createRequire as __mcpCreateRequire } from "node:module";'))
        # The modules are ES modules in Node's sense (package.json), so CommonJS imports use Node's interop.
        self.assertIn("__toESM(require_png(), 1)", text)
        ran = self.node(
            "--input-type=module", "-e", f"console.log((await import({json.dumps(str(self.bundle))})).said)"
        )
        self.assertEqual(ran.stdout.strip(), "b:function!", ran.stderr)

    def test_check_sees_a_changed_byte(self):
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(self.build("--check").returncode, 0)
        self.bundle.write_text(self.bundle.read_text() + " ")
        done = self.build("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FIX: node tools/engine/bundle.mjs", done.stderr)

    def test_a_package_without_its_licence_is_refused(self):
        (self.engine / "licenses" / "bundled-javascript.txt").write_text("# Bundled JavaScript dependency licenses\n")
        done = self.build()
        self.assertEqual(done.returncode, 1)
        self.assertIn("no licence for pngjs@7.0.0", done.stderr)
        self.assertFalse(self.bundle.exists())

    def compare(self, before: str, after: str) -> subprocess.CompletedProcess:
        (self.engine / "before.js").write_text(before)
        (self.engine / "after.js").write_text(after)
        return self.node(
            str(TOOLS / "compare_bundles.mjs"), str(self.engine / "before.js"), str(self.engine / "after.js")
        )

    def test_the_comparison_ignores_layout_and_renumbering_only(self):
        self.assertEqual(self.build().returncode, 0)
        text = self.bundle.read_text()
        self.assertIn("path.basename(name)", text)
        rebuilt = text.replace("import path from", "import path7 from").replace(
            "path.basename(name)", "(path7.basename(name))"
        )
        same = self.compare(text, rebuilt)
        self.assertEqual(same.returncode, 0, same.stdout)
        changed = self.compare(text, text.replace("}:${", "}-${"))
        self.assertEqual(changed.returncode, 1)
        self.assertIn("dist/greet.js", changed.stdout)
        self.assertIn("0 different", same.stdout)


class EnginePackagesTests(unittest.TestCase):
    def test_the_pinned_packages_are_the_engines_locked_versions(self):
        engine = json.loads((ROOT / "engine/modretro-chromatic/scripts/runtime-package-lock.json").read_text())[
            "packages"
        ]
        pinned = json.loads((TOOLS / "npm" / "package-lock.json").read_text())["packages"]
        for name, package in engine.items():
            if not name:
                continue
            with self.subTest(package=name):
                self.assertIn(name, pinned)
                for field in ("version", "resolved", "integrity"):
                    self.assertEqual(pinned[name].get(field), package.get(field))
        extra = {name for name in pinned if name and name not in engine}
        self.assertEqual({name for name in extra if "esbuild" not in name}, set())


if __name__ == "__main__":
    unittest.main()
