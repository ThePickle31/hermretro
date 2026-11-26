"""tools/engine/bundle.mjs: a bundle built from an engine's modules runs, holds every module and the packages they
import, keeps scripts/ beside it (the engine reaches the Chromatic CLI through it), and holds nothing but the engine's
modules and packages its lock names, each with its licence in the engine's notices; --check sees a changed byte, and a
build leaves nothing behind. The pinned packages in tools/engine/npm are the engine's own locked versions. The
comparison of two bundles is tested in test_engine_compare.py."""

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
# ModRetro's own build of the engine bundle, which bundle.mjs must match byte for byte.
MODRETRO_BUILD = ROOT / "engine" / "modretro-chromatic" / "scripts" / "bundle-mcp.mjs"


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

    def test_the_entry_is_the_engines_dist_entry_js_unless_named(self):
        (self.engine / "dist" / "entry.js").write_text(ENTRY)
        done = self.node(str(TOOLS / "bundle.mjs"), "--engine", str(self.engine))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.run_bundle(), "b:function!")
        # Built in as dist/server.js, as an entry given by path is, and not copied in a second time.
        self.assertNotIn("dist/entry.js", self.bundle.read_text())
        self.assertEqual(self.node(str(TOOLS / "bundle.mjs"), "--engine", str(self.engine), "--check").returncode, 0)

    def test_the_bundle_is_byte_for_byte_what_modretros_build_makes(self):
        self.assertEqual(self.build().returncode, 0)
        # ModRetro's build (the engine's scripts/bundle-mcp.mjs) of the same modules, in a folder laid out as it wants:
        # the entry as dist/server.js, the packages in node_modules and the device client it also bundles.
        # Resolved: ModRetro's build matches scripts/ against the path it is given, and on macOS the temporary folder
        # is reached through a link (/var is /private/var), so an unresolved path would not match what esbuild sees.
        theirs = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        shutil.copytree(self.engine, theirs, dirs_exist_ok=True)
        shutil.copy(self.entry, theirs / "dist" / "server.js")
        (theirs / "scripts" / "device-client-deps.mjs").write_text("export const client = 1;\n")
        shutil.copytree(TOOLS / "npm" / "node_modules" / "pngjs", theirs / "node_modules" / "pngjs")
        script = (
            f"const {{ bundleMcp }} = await import({json.dumps(MODRETRO_BUILD.as_uri())});"
            f"process.stdout.write(bundleMcp({json.dumps(str(theirs))}).contents);"
        )
        # Its require("esbuild") finds the pinned esbuild, the version it names.
        environment = {**os.environ, "NODE_PATH": str(TOOLS / "npm" / "node_modules")}
        built = subprocess.run(
            [NODE, "--input-type=module", "-e", script], capture_output=True, timeout=120, env=environment
        )
        self.assertEqual(built.returncode, 0, built.stderr.decode())
        self.assertEqual(self.bundle.read_bytes(), built.stdout)

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

    def test_scripts_reached_through_a_package_alias_stay_beside_the_bundle(self):
        # package.json "imports" and the package's own name resolve to scripts/ as a relative path does.
        (self.engine / "package.json").write_text(
            '{"type": "module", "name": "engine", "imports": {"#helper": "./scripts/helper.mjs"},'
            ' "exports": {"./helper": "./scripts/helper.mjs"}}\n'
        )
        for request in ("#helper", "engine/helper"):
            with self.subTest(request=request):
                self.entry.write_text(f'import {{ suffix }} from "{request}";\nexport const said = suffix;\n')
                done = self.build()
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn('from "../scripts/helper.mjs"', self.bundle.read_text())
                self.assertEqual(self.run_bundle(), "!")

    def test_imports_of_scripts_are_kept_as_they_are_written(self):
        # A query makes another module instance, and Node resolves a require() without an extension itself.
        (self.engine / "scripts" / "plain.js").write_text("export const plain = 1;\n")
        (self.engine / "scripts" / "device helper.mjs").write_text("export const device = 1;\n")
        requests = ("../scripts/helper.mjs?one", "../scripts/helper.mjs?two", "../scripts/device%20helper.mjs")
        self.entry.write_text(
            "".join(f'import "{request}";\n' for request in requests)
            + 'export const plain = () => require("../scripts/plain");\nexport const said = 1;\n'
        )
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        text = self.bundle.read_text()
        for request in requests:
            self.assertIn(f'import "{request}";', text)
        self.assertIn('require("../scripts/plain")', text)

    def test_a_write_never_removes_what_was_already_beside_the_bundle(self):
        self.assertEqual(self.build().returncode, 0)
        self.bundle.write_text("older\n")
        # The temporary name the build would use, taken by a folder that is not the build's.
        script = (
            "const { mkdirSync, writeFileSync } = await import('node:fs');"
            f"const out = {json.dumps(str(self.bundle))};"
            "const dir = out.replace(/server\\.js$/, `.server.js.${process.pid}.tmp`);"
            "mkdirSync(dir); writeFileSync(dir + '/keep.txt', 'mine');"
            f"process.argv = [process.argv[0], {json.dumps(str(TOOLS / 'bundle.mjs'))}, '--engine', "
            f"{json.dumps(str(self.engine))}, '--entry', {json.dumps(str(self.entry))}];"
            f"await import({json.dumps((TOOLS / 'bundle.mjs').as_uri())});"
        )
        done = self.node("--input-type=module", "-e", script)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("EEXIST", done.stderr)
        kept = [path for path in self.bundle.parent.iterdir() if path.name.endswith(".tmp")]
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0] / "keep.txt").read_text(), "mine")
        self.assertEqual(self.bundle.read_text(), "older\n")

    def test_a_temporary_folder_with_a_star_in_its_path_builds(self):
        self.assertEqual(self.build().returncode, 0)
        expected = self.bundle.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            starred = Path(tmp) / "a*b"
            starred.mkdir()
            done = self.build(env={**os.environ, "TMPDIR": str(starred)})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.bundle.read_bytes(), expected)

    def test_the_tools_run_through_a_link_to_them(self):
        # Node resolves the link in import.meta.url but not in the script path it was given.
        linked = Path(self.enterContext(tempfile.TemporaryDirectory())) / "engine-tools"
        linked.symlink_to(TOOLS)
        self.assertEqual(self.build().returncode, 0)
        self.bundle.write_text("stale\n")
        done = self.node(
            str(linked / "bundle.mjs"), "--engine", str(self.engine), "--entry", str(self.entry), "--check"
        )
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("is not what its modules build", done.stderr)

    def test_an_entry_given_as_a_link_and_a_tsconfig_above_the_build_change_nothing(self):
        self.assertEqual(self.build().returncode, 0)
        expected = self.bundle.read_bytes()
        linked = self.engine / "entry-link.js"
        linked.symlink_to(self.entry)
        done = self.node(str(TOOLS / "bundle.mjs"), "--engine", str(self.engine), "--entry", str(linked))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.bundle.read_bytes(), expected)
        # A tsconfig.json above the build's temporary folder that would point pngjs somewhere else.
        with tempfile.TemporaryDirectory() as workspace:
            (Path(workspace) / "tsconfig.json").write_text('{"compilerOptions": {"paths": {"pngjs": ["./fake.js"]}}}')
            (Path(workspace) / "fake.js").write_text("export const PNG = 1;\n")
            (Path(workspace) / "tmp").mkdir()
            done = self.build(env={**os.environ, "TMPDIR": str(Path(workspace) / "tmp")})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.bundle.read_bytes(), expected)

    def test_a_read_only_bundle_builds_to_another_place(self):
        # The engine's own bundle is never copied into the build: the entry takes its place.
        self.assertEqual(self.build().returncode, 0)
        expected = self.bundle.read_bytes()
        self.bundle.chmod(0o444)
        self.addCleanup(self.bundle.chmod, 0o644)
        elsewhere = Path(self.enterContext(tempfile.TemporaryDirectory())) / "server.js"
        done = self.build("--out", str(elsewhere))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(elsewhere.read_bytes(), expected)

    def test_check_sees_a_changed_byte(self):
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(self.build("--check").returncode, 0)
        self.bundle.write_text(self.bundle.read_text() + " ")
        done = self.build("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FIX: run the same command without --check", done.stderr)

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

    def test_a_build_that_writes_more_than_the_bundle_is_refused(self):
        (self.engine / "dist" / "look.css").write_text("body { color: red; }\n")
        self.entry.write_text('import "./look.css";\nexport const said = 1;\n')
        done = self.build()
        self.assertEqual(done.returncode, 1)
        self.assertIn("only dist/server.js is the bundle", done.stderr)
        self.assertFalse(self.bundle.exists())


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
