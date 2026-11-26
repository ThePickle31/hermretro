"""tools/engine/bundle.mjs and compare_bundles.mjs. A bundle built from an engine's modules runs, holds every module
and the packages they import, keeps scripts/ beside it (the engine reaches the Chromatic CLI through it), and holds
nothing but the engine's modules and packages its lock names, each licensed; --check sees a changed byte. The
comparison calls two bundles the same only when nothing but layout, grouping parentheses and where imports stand
differs, names a difference that is only renamed bindings, and calls different anything that changes what runs:
each such case is run in Node first, to show the two programs really do differ. The pinned packages in
tools/engine/npm are the engine's own locked versions."""

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
ENGINE_LOCK = ROOT / "engine" / "modretro-chromatic" / "scripts" / "runtime-package-lock.json"
PNGJS_LICENCE = TOOLS / "npm" / "node_modules" / "pngjs" / "LICENSE"


def lock_naming(*packages: str) -> str:
    """An engine lock file naming only these of the real engine's locked packages."""
    locked = json.loads(ENGINE_LOCK.read_text())["packages"]
    return json.dumps({"packages": {"": {}, **{name: locked[name] for name in packages}}})


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
    "scripts/runtime-package-lock.json": lock_naming("node_modules/pngjs"),
    # The notice carries the package's own licence text, as ModRetro's build writes it.
    "licenses/bundled-javascript.txt": "# Bundled JavaScript dependency licenses\n\n## pngjs@7.0.0\n\n"
    + (PNGJS_LICENCE.read_text().strip() + "\n" if PNGJS_LICENCE.is_file() else ""),
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
# Modules the programs below import.
HELPERS = {
    "a.mjs": 'console.log("a");\n',
    "b.mjs": 'console.log("b");\n',
    "star.mjs": 'const v = 5;\nexport { v as "*" };\nexport const k = 1;\n',
}
# Pairs of programs that differ in what they do, though a careless comparison would call them the same.
DIFFERENT = {
    "import order": ('import "./a.mjs";\nimport "./b.mjs";\n', 'import "./b.mjs";\nimport "./a.mjs";\n'),
    "a binding and a global": ("const a = 1;\nconsole.log(typeof a);\n", "const a = 1;\nconsole.log(typeof b);\n"),
    "a namespace and an export named *": (
        'import * as v from "./star.mjs";\nconsole.log(typeof v);\n',
        'import { "*" as v } from "./star.mjs";\nconsole.log(typeof v);\n',
    ),
    "a name eval reads": (
        'const a = 1;\nconsole.log(eval("typeof a"));\n',
        'const b = 1;\nconsole.log(eval("typeof a"));\n',
    ),
    "a function's own name": ("function f() {}\nconsole.log(f.name);\n", "function g() {}\nconsole.log(g.name);\n"),
    "a name given to an arrow": (
        "const f = () => 1;\nconsole.log(f.name);\n",
        "const g = () => 1;\nconsole.log(g.name);\n",
    ),
    "__proto__ in shorthand": (
        "const __proto__ = { value: 7 };\nconsole.log({ __proto__ }.value);\n",
        "const __proto__ = { value: 7 };\nconsole.log({ __proto__: __proto__ }.value);\n",
    ),
    "a parenthesised assignment target": (
        "let f;\nf = () => {};\nconsole.log(f.name);\n",
        "let f;\n(f) = () => {};\nconsole.log(f.name);\n",
    ),
    "an imported name eval reads": (
        'import { basename as aa } from "node:path";\nconsole.log(eval("typeof aa"));\n',
        'import { basename as bb } from "node:path";\nconsole.log(eval("typeof aa"));\n',
    ),
    "a name in an error message": (
        "try {\n  const first = first;\n} catch (error) {\n  console.log(error.message);\n}\n",
        "try {\n  const second = second;\n} catch (error) {\n  console.log(error.message);\n}\n",
    ),
    "private names": (
        "class A {\n  #x = 1;\n  #y = 2;\n  get v() {\n    return this.#x;\n  }\n}\nconsole.log(new A().v);\n",
        "class A {\n  #y = 1;\n  #x = 2;\n  get v() {\n    return this.#x;\n  }\n}\nconsole.log(new A().v);\n",
    ),
    "a template's raw text": ("console.log(String.raw`\\x61`);\n", "console.log(String.raw`a`);\n"),
    "a parenthesised target in a pattern": (
        "let f;\n[f = () => {}] = [];\nconsole.log(f.name);\n",
        "let f;\n[(f) = () => {}] = [];\nconsole.log(f.name);\n",
    ),
}
# Bundles that must compare the same as themselves.
VALID = {
    "an imported binding exported again": 'import { suffix } from "../scripts/helper.mjs";\nexport { suffix };\n',
    "a class that names itself": "class C {\n  static self = C;\n}\nexport { C };\n",
    "an exported pattern with a default": "export const { a = 1 } = {};\n",
    "a string like a separator": 'console.log("/*! hermretro-statement */");\n',
    "imports only": 'import "./a.mjs";\nimport { k } from "./star.mjs";\n',
    "a marker inside a template": "console.log(`\n// dist/c.js\nlevel1`);\n",
    "statements ended by a line break": 'foo()\nimport "./a.mjs"\n[bar()];\n',
}


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

    def node(self, *args: str, env: dict | None = None, cwd: Path = ROOT) -> subprocess.CompletedProcess:
        return subprocess.run([NODE, *args], cwd=cwd, capture_output=True, text=True, timeout=120, env=env)

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
        self.assertEqual(sorted(os.listdir(self.bundle.parent)), ["greet.js", "server.js"])

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

    def test_a_read_only_folder_in_the_engine_is_built_and_cleaned_up(self):
        folder = self.engine / "dist" / "fixed"
        folder.mkdir()
        (folder / "data.js").write_text("export const data = 1;\n")
        folder.chmod(0o555)
        self.addCleanup(folder.chmod, 0o755)
        with tempfile.TemporaryDirectory() as tmp:
            done = self.build(env={**os.environ, "TMPDIR": tmp})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(os.listdir(tmp), [])
        # A copy that fails after it made a read-only folder still leaves nothing, and says why it failed.
        secret = self.engine / "scripts" / "secret.mjs"
        secret.write_text("export const secret = 1;\n")
        secret.chmod(0o000)
        self.addCleanup(secret.chmod, 0o644)
        with tempfile.TemporaryDirectory() as tmp:
            done = self.build(env={**os.environ, "TMPDIR": tmp})
            self.assertEqual(done.returncode, 1)
            self.assertIn("EACCES", done.stderr)
            self.assertNotIn("could not remove", done.stderr)
            self.assertEqual(os.listdir(tmp), [])

    def test_a_temporary_folder_with_a_star_in_its_path_builds(self):
        self.assertEqual(self.build().returncode, 0)
        expected = self.bundle.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            starred = Path(tmp) / "a*b"
            starred.mkdir()
            done = self.build(env={**os.environ, "TMPDIR": str(starred)})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.bundle.read_bytes(), expected)

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

    def test_a_package_without_its_licence_or_lock_entry_is_refused(self):
        notices = ENGINE["licenses/bundled-javascript.txt"]
        refusals = {
            "licenses/bundled-javascript.txt": (
                notices.replace("Permission", "Leave"),
                "does not carry the licence of pngjs",
            ),
            "scripts/runtime-package-lock.json": (lock_naming(), "does not name pngjs@7.0.0"),
        }
        for rel, (text, said) in refusals.items():
            with self.subTest(file=rel):
                original = (self.engine / rel).read_text()
                (self.engine / rel).write_text(text)
                done = self.build()
                (self.engine / rel).write_text(original)
                self.assertEqual(done.returncode, 1)
                self.assertIn(said, done.stderr)
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

    def test_a_link_in_the_engine_is_refused(self):
        (self.engine / "dist" / "alias.js").symlink_to(self.engine / "dist" / "greet.js")
        done = self.build("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("the engine's folders hold no links", done.stderr)
        (self.engine / "dist" / "alias.js").unlink()
        outside = Path(self.enterContext(tempfile.TemporaryDirectory()))
        # A dist/ that is itself a link is refused before anything is written through it.
        shutil.move(self.engine / "dist", outside / "dist")
        (self.engine / "dist").symlink_to(outside / "dist")
        before = (outside / "dist" / "greet.js").read_text()
        done = self.build("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("the engine's folders hold no links", done.stderr)
        self.assertEqual(sorted(os.listdir(outside / "dist")), ["greet.js"])
        self.assertEqual((outside / "dist" / "greet.js").read_text(), before)

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

    def assertDifferent(self, before: str, after: str):
        done = self.compare(before, after)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")

    def test_the_comparison_ignores_layout_grouping_and_where_imports_stand(self):
        # Layout changed, parentheses added, a shorthand written out, an import moved to another module and split.
        moved = bundle_with(
            **{
                'import { basename as basename2, dirname } from "node:path";\n': "",
                "var first = 1;": "var first   =   (1);",
                "{ first, value": "{ first: first, value",
                "// dist/b.js\n": (
                    '// dist/b.js\nimport { dirname } from "node:path";\n'
                    'import { basename as basename2 } from "node:path";\n'
                ),
            }
        )
        self.assertSame(BUNDLE, moved)

    def test_renamed_bindings_are_named_and_still_differ(self):
        self.assertEqual(self.build().returncode, 0)
        built = self.bundle.read_text()
        renamed = built.replace("import path from", "import path7 from").replace(
            "path.basename(name)", "path7.basename(name)"
        )
        self.assertNotEqual(renamed, built)
        done = self.compare(built, renamed)
        self.assertEqual(done.returncode, 1)
        self.assertIn("differ only in the names of 1 bindings:\n  path -> path7", done.stdout)
        # Removing one of two names for the same import is not a rename.
        both = 'import { basename as aa, basename as bb } from "node:path";\nconsole.log(aa);\n'
        done = self.compare(both, 'import { basename as aa } from "node:path";\nconsole.log(aa);\n')
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("differ only in the names", done.stdout)
        self.assertIn("imported only by the first", done.stdout)

    def test_a_build_that_writes_more_than_the_bundle_is_refused(self):
        (self.engine / "dist" / "look.css").write_text("body { color: red; }\n")
        self.entry.write_text('import "./look.css";\nexport const said = 1;\n')
        done = self.build()
        self.assertEqual(done.returncode, 1)
        self.assertIn("only dist/server.js is the bundle", done.stderr)
        self.assertFalse(self.bundle.exists())

    def test_the_comparison_sees_requests_in_another_order(self):
        # The same module asked for with other attributes can be another module, so attributes are part of a request.
        first = 'import data from "./x.json" with { type: "json" };\nimport "./x.json";\nconsole.log(data);\n'
        second = 'import "./x.json";\nimport data from "./x.json" with { type: "json" };\nconsole.log(data);\n'
        done = self.compare(first, second)
        self.assertEqual(done.returncode, 1)
        self.assertIn("requested in another order", done.stdout)

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
                self.assertDifferent(BUNDLE, bundle_with(**replacements))

    def test_the_comparison_sees_modules_run_in_another_order(self):
        a, b = BUNDLE.split("// dist/b.js\n")
        swapped = "// dist/b.js\n" + b.replace("export {\n  pick\n};\n", "") + a + "export {\n  pick\n};\n"
        done = self.compare(BUNDLE, swapped)
        self.assertEqual(done.returncode, 1)
        self.assertIn("first difference", done.stdout)

    def test_programs_that_run_differently_compare_different(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for name, text in HELPERS.items():
            (folder / name).write_text(text)
        for case, (before, after) in DIFFERENT.items():
            with self.subTest(case=case):
                outputs = []
                for name, text in (("before.mjs", before), ("after.mjs", after)):
                    (folder / name).write_text(text)
                    ran = self.node(str(folder / name), cwd=folder)
                    outputs.append((ran.returncode, ran.stdout, ran.stderr.splitlines()[-1:]))
                self.assertNotEqual(outputs[0], outputs[1], "the two programs should run differently")
                self.assertDifferent(before, after)

    def test_valid_bundles_compare_the_same_as_themselves(self):
        for case, text in VALID.items():
            with self.subTest(case=case):
                self.assertSame(text, text)
        self.assertDifferent(VALID["statements ended by a line break"], "foo()[bar()];\n")


class EnginePackagesTests(unittest.TestCase):
    def test_the_pinned_packages_are_the_engines_locked_versions(self):
        engine = json.loads(ENGINE_LOCK.read_text())["packages"]
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
