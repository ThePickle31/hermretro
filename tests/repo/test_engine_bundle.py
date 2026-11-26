"""tools/engine/bundle.mjs and compare_bundles.mjs. A bundle built from an engine's modules runs, holds every module
and the packages they import, keeps scripts/ beside it (the engine reaches the Chromatic CLI through it), and holds
nothing but the engine's modules and the pinned packages, each licensed; --check sees a changed byte. The comparison
calls two bundles the same when only what a bundler changes differs (names, layout, where imports stand) and
different for anything that changes what runs. The pinned packages in tools/engine/npm are the engine's own locked
versions."""

import json
import os
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
# A bundle as esbuild writes one: marked modules, imports at the head of the module that uses them.
BUNDLE = """// dist/a.js
import { basename as basename2, dirname } from "node:path";
var first = 1;
var second = 2;
function pick(value) {
  return { first, value: `level1:${basename2(value)}`, at: /v1/.test(value) ? dirname(value) : value };
}

// dist/b.js
var entry = { sha256: "x", first };
console.log(pick("/v1/a"), entry.sha256, second);
export {
  pick
};
"""


def bundle_with(**replacements: str) -> str:
    text = BUNDLE
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new)
    return text


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

    def node(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([NODE, *args], cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)

    def build(self, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return self.node(
            str(TOOLS / "bundle.mjs"), "--engine", str(self.engine), "--entry", str(self.entry), *extra, env=env
        )

    def run_bundle(self) -> str:
        code = f"console.log((await import({json.dumps(str(self.bundle))})).said)"
        ran = self.node("--input-type=module", "-e", code)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        return ran.stdout.strip()

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
        self.assertEqual(self.run_bundle(), "b:function!")

    def test_a_temporary_folder_reached_through_a_link_builds_the_same(self):
        # macOS reaches its temporary folder through a link; scripts/ must stay outside the bundle there too.
        self.assertEqual(self.build().returncode, 0)
        expected = self.bundle.read_bytes()
        with tempfile.TemporaryDirectory() as real, tempfile.TemporaryDirectory() as holder:
            linked = Path(holder) / "tmp"
            linked.symlink_to(real)
            done = self.build(env={**os.environ, "TMPDIR": str(linked)})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.bundle.read_bytes(), expected)
            self.assertEqual(os.listdir(real), [])

    def test_check_sees_a_changed_byte(self):
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(self.build("--check").returncode, 0)
        self.bundle.write_text(self.bundle.read_text() + " ")
        done = self.build("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FIX: node tools/engine/bundle.mjs", done.stderr)

    def test_a_flag_where_a_path_belongs_is_refused(self):
        done = self.build("--out", "--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--out needs a path", done.stderr)
        self.assertFalse((ROOT / "--check").exists())

    def test_a_package_without_its_licence_is_refused(self):
        (self.engine / "licenses" / "bundled-javascript.txt").write_text("# Bundled JavaScript dependency licenses\n")
        done = self.build()
        self.assertEqual(done.returncode, 1)
        self.assertIn("no licence for pngjs@7.0.0", done.stderr)
        self.assertFalse(self.bundle.exists())

    def test_a_package_from_outside_the_pinned_ones_is_refused(self):
        self.entry.write_text('import { value } from "sample-unpinned";\nexport const said = value;\n')
        # Above the build's folder (found by walking up from it), or inside the engine's dist/.
        for where in ("above", "inside"):
            with self.subTest(where=where), tempfile.TemporaryDirectory() as tmp:
                package = (Path(tmp) if where == "above" else self.engine / "dist") / "node_modules" / "sample-unpinned"
                package.mkdir(parents=True)
                (package / "package.json").write_text('{"name": "sample-unpinned", "version": "1.0.0"}')
                (package / "index.js").write_text("export const value = 1;\n")
                done = self.build(env={**os.environ, "TMPDIR": tmp})
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("neither the engine's modules nor the pinned packages", done.stderr)
                shutil.rmtree(self.engine / "dist" / "node_modules", ignore_errors=True)

    def test_a_module_reached_through_a_link_is_one_module(self):
        (self.engine / "dist" / "count.js").write_text(
            "globalThis.loads = (globalThis.loads ?? 0) + 1;\nexport const loads = () => globalThis.loads;\n"
        )
        (self.engine / "dist" / "alias.js").symlink_to("count.js")
        self.entry.write_text(
            'import { loads } from "./count.js";\nimport { loads as again } from "./alias.js";\n'
            "export const said = `${loads()}${again()}`;\n"
        )
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.run_bundle(), "11")

    def compare(self, before: str, after: str) -> subprocess.CompletedProcess:
        (self.engine / "before.js").write_text(before)
        (self.engine / "after.js").write_text(after)
        return self.node(
            str(TOOLS / "compare_bundles.mjs"), str(self.engine / "before.js"), str(self.engine / "after.js")
        )

    def assertSame(self, before: str, after: str):
        done = self.compare(before, after)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the bundles hold the same program", done.stdout)

    def assertDifferent(self, before: str, after: str, said: str):
        done = self.compare(before, after)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(said, done.stdout)

    def test_the_comparison_ignores_what_a_bundler_changes(self):
        self.assertEqual(self.build().returncode, 0)
        built = self.bundle.read_text()
        renamed = built.replace("import path from", "import path7 from").replace(
            "path.basename(name)", "(path7.basename(name))"
        )
        self.assertNotEqual(renamed, built)
        self.assertSame(built, renamed)
        # Names renumbered, layout changed, an import moved to another module and split in two.
        moved = bundle_with(
            **{
                'import { basename as basename2, dirname } from "node:path";\n': "",
                "basename2(value)": "basename(value)",
                "var first = 1;": "var first3   =   (1);",
                "{ first, value": "{ first: first3, value",
                "sha256: \"x\", first }": "sha256: \"x\", first: first3 }",
                "// dist/b.js\n": '// dist/b.js\nimport { dirname } from "node:path";\nimport { basename } from "node:path";\n',
            }
        )
        self.assertSame(BUNDLE, moved)

    def test_the_comparison_sees_every_change_to_what_runs(self):
        changes = {
            "another import": {"? dirname(value)": "? basename2(value)"},
            "another binding": {"console.log(pick(": "console.log(pick(second, "},
            "a property name": {"entry.sha256": "entry.sha512"},
            "a regular expression": {"/v1/.test": "/v2/.test"},
            "template text": {"`level1:": "`level2:"},
            "an exported name": {"  pick\n};": "  pick as choose\n};"},
            "an imported name": {'dirname } from "node:path"': 'resolve as dirname } from "node:path"'},
        }
        for change, replacements in changes.items():
            with self.subTest(change=change):
                after = bundle_with(**replacements)
                self.assertDifferent(BUNDLE, after, "differ" if change != "an imported name" else "import only in")

    def test_the_comparison_sees_modules_run_in_another_order(self):
        a, b = BUNDLE.split("// dist/b.js\n")
        swapped = "// dist/b.js\n" + b.replace("export {\n  pick\n};\n", "") + a + "export {\n  pick\n};\n"
        self.assertDifferent(BUNDLE, swapped, "first difference")
        # A marker inside a template is text, not a module.
        templated = BUNDLE.replace("`level1:", "`\n// dist/c.js\nlevel1:")
        self.assertSame(templated, templated)


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
        # Anything else is a build tool or what one needs.
        tools, needed = ["node_modules/esbuild", "node_modules/acorn", "node_modules/eslint-scope"], set()
        while tools:
            name = tools.pop()
            if name in needed:
                continue
            needed.add(name)
            for field in ("dependencies", "optionalDependencies"):
                tools.extend(f"node_modules/{dependency}" for dependency in pinned[name].get(field, {}))
        self.assertEqual({name for name in pinned if name and name not in engine} - needed, set())


if __name__ == "__main__":
    unittest.main()
