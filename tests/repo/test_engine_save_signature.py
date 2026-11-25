"""The engine setup's repeatable save-signature patch of GB Studio's compiler, and the checks that a compiled CLI
carries it (the dependency doctor, and the standalone installers' reuse)."""

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.support import isolated_home

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "engine" / "modretro-chromatic" / "scripts"

# The three places of the pinned compileData.ts the patch changes, in a stand-in for it.
SOURCE = (
    'import Path from "path";\nimport { ensureDir } from "fs-extra";\n\n'
    "export const removeDisabledScenes = () => {};\n\n"
    "const compile = async (\n  rawProjectData: ProjectResources,\n  options: unknown,\n) => {\n"
    "  const output = {};\n"
    "  output[`game_signature.c`] = compileSaveSignature(\n    JSON.stringify(projectData),\n  );\n"
    "  return output;\n};\n"
)

# Runs one step against the scripts and prints its JSON result. The first argument is the request, so the scripts'
# "run as a command" check (argv[1] is the script itself) never fires.
DRIVER = """
const [request, scripts] = process.argv.slice(1);
const { pathToFileURL } = await import("node:url");
const load = (name) => import(pathToFileURL(scripts + "/" + name).href);
const { step, ...args } = JSON.parse(request);
const compiler = await load("setup-compiler.mjs");
const answer = async () => {
  try {
    if (step === "patched") return { source: compiler.patchedSaveSignatureSource(args.source) };
    if (step === "patch_file") return { changed: await compiler.patchSaveSignature(args.file) };
    if (step === "setup_patch") return (await load("setup-components.mjs")).saveSignaturePatch(args.source);
    if (step === "constants") return compiler.CLI_SAVE_SIGNATURE_PATCH;
    if (step === "worker_current") return { current: await compiler.cliWorkerCurrent(args.cli) };
    if (step === "doctor") {
      const { detectDependencies } = await load("dependency-doctor.mjs");
      const report = await detectDependencies({ setupRoot: args.root, toolchainRoot: args.toolchain, tasks: ["projectBuild"] });
      return report.components.find((item) => item.id === "cli");
    }
  } catch (error) {
    return { error: error.message, code: error.code };
  }
};
process.stdout.write(JSON.stringify(await answer()));
"""


class NodeScripts(unittest.TestCase):
    """Runs the engine's setup scripts in node, each test in a temporary folder of its own."""

    def setUp(self):
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("node is not installed")
        self.tmp = isolated_home(self).base

    def run_step(self, **request):
        result = subprocess.run(
            [self.node, "--input-type=module", "-e", DRIVER, json.dumps(request), str(SCRIPTS)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def marker(self) -> str:
        return self.run_step(step="constants")["marker"]


class SaveSignaturePatch(NodeScripts):
    def test_the_pinned_source_gets_the_repeatable_signature_input(self):
        patched = self.run_step(step="patched", source=SOURCE)["source"]
        self.assertNotIn("JSON.stringify(projectData),", patched)
        self.assertIn("await saveSignatureInput(projectData, projectRoot),", patched)
        self.assertIn('import { ensureDir, readFile } from "fs-extra";\nimport glob from "glob";\n', patched)
        self.assertIn(self.marker(), patched)
        # Only loader metadata of asset records is left out, never a key anywhere (an event's own `_v` arg counts).
        self.assertIn("const { _v, inode, ...stable } = record;", patched)
        self.assertNotIn('key === "_v"', patched)
        self.assertIn("{assets/engine/**,plugins/**}", patched)
        self.assertLess(patched.index("const saveSignatureInput"), patched.index("const compile = async ("))

    def test_any_other_source_is_refused(self):
        patched = self.run_step(step="patched", source=SOURCE)["source"]
        for source in (
            SOURCE.replace("projectData),", "project),"),
            SOURCE.replace("ensureDir", "ensureFile"),
            patched,
        ):
            with self.subTest(source=source[:60]):
                self.assertIn("does not match", self.run_step(step="patched", source=source)["error"])

    def test_patching_a_file_twice_changes_it_once(self):
        folder = self.tmp / "compiler"
        folder.mkdir()
        file = folder / "compileData.ts"
        file.write_text(SOURCE)
        self.assertEqual(self.run_step(step="patch_file", file=str(file)), {"changed": True})
        once = file.read_bytes()
        self.assertEqual(self.run_step(step="patch_file", file=str(file)), {"changed": False})
        self.assertEqual(file.read_bytes(), once)
        self.assertEqual(once.decode(), self.run_step(step="patched", source=SOURCE)["source"])
        self.assertEqual([path.name for path in folder.iterdir()], ["compileData.ts"])  # no temporary file left

    def test_a_crlf_source_keeps_its_line_endings_and_no_stale_bytes(self):
        file = self.tmp / "compileData.ts"
        file.write_bytes(SOURCE.replace("\n", "\r\n").encode())
        self.assertEqual(self.run_step(step="patch_file", file=str(file)), {"changed": True})
        written = file.read_bytes()
        expected = self.run_step(step="patched", source=SOURCE)["source"]
        self.assertEqual(written, expected.replace("\n", "\r\n").encode())
        self.assertNotIn(b"\n", written.replace(b"\r\n", b""))
        self.assertEqual(self.run_step(step="patch_file", file=str(file)), {"changed": False})

    def test_setup_records_the_patch_and_refuses_a_drifted_source(self):
        answer = self.run_step(step="setup_patch", source=SOURCE)
        self.assertEqual(answer["receipt"]["path"], "src/lib/compiler/compileData.ts")
        self.assertIn("save signature", answer["receipt"]["purpose"])
        self.assertEqual(answer["source"], self.run_step(step="patched", source=SOURCE)["source"])
        drifted = self.run_step(step="setup_patch", source="export {};\n")
        self.assertEqual(drifted["code"], "SOURCE_PATCH_MISMATCH")


class CompiledCli(NodeScripts):
    """A CLI setup compiled must carry the patch; one compiled before it is compiled again, never reused."""

    def make_cli(self, worker: str, *, packaged: bool) -> tuple[Path, Path, Path]:
        toolchain = self.tmp / "toolchain"
        cli = toolchain / ".local" / "vendor" / "gb-studio"
        platform = {"darwin": "darwin", "linux": "linux"}[os.uname().sysname.lower()]
        arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}[os.uname().machine.lower()]
        files = {
            "out/cli/gb-studio-cli.js": "// cli\n",
            "out/cli/buildWorker.js": worker,
            "package.json": json.dumps({"name": "gb-studio", "version": "4.3.2"}),
            "appData/engine/engine.json": "{}",
            "appData/engine/gbvm/include/vm.h": "// vm\n",
            f"buildTools/{platform}-{arch}/gbdk/bin/lcc": "#!/bin/sh\n",
            f"buildTools/{platform}-{arch}/gbdk/include/gbdk/version.h": "#define __GBDK_VERSION 450\n",
            **({".codex-setup-source.json": "{}"} if packaged else {".git/HEAD": "ref: refs/heads/main\n"}),
        }
        for relative, text in files.items():
            path = cli / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (cli / f"buildTools/{platform}-{arch}/gbdk/bin/lcc").chmod(0o755)
        return self.tmp, toolchain, cli / "out" / "cli" / "gb-studio-cli.js"

    def doctor(self, worker: str, *, packaged: bool = True) -> dict:
        root, toolchain, _cli = self.make_cli(worker, packaged=packaged)
        return self.run_step(step="doctor", root=str(root), toolchain=str(toolchain))

    def test_a_cli_built_with_the_patch_is_ready(self):
        cli = self.doctor(f'eval("const input = [\\"{self.marker()}\\"];")\n')
        self.assertEqual(cli["status"], "ready", cli)

    def test_a_packaged_cli_built_without_it_is_incompatible_and_setup_rebuilds_it(self):
        cli = self.doctor('eval("compileSaveSignature)(JSON.stringify(projectData));")\n')
        self.assertEqual(cli["status"], "incompatible", cli)
        self.assertIn("without the repeatable save signature", cli["detectionEvidence"][-1])
        self.assertIn("setup.mjs' plan", cli["nextSteps"][0])

    def test_a_standalone_cli_built_without_it_points_at_its_own_installer(self):
        cli = self.doctor("// old worker\n", packaged=False)
        self.assertEqual(cli["status"], "incompatible", cli)
        self.assertIn("scripts/setup-compiler.sh --with-cli", cli["nextSteps"][0])
        self.assertIn("without --use-existing", cli["nextSteps"][0])

    def test_reuse_needs_the_patched_worker(self):
        _root, _toolchain, cli = self.make_cli(f"// {self.marker()}\n", packaged=False)
        self.assertEqual(self.run_step(step="worker_current", cli=str(cli)), {"current": True})
        (cli.parent / "buildWorker.js").write_text("// before the patch\n")
        self.assertEqual(self.run_step(step="worker_current", cli=str(cli)), {"current": False})
        (cli.parent / "buildWorker.js").unlink()
        self.assertEqual(self.run_step(step="worker_current", cli=str(cli)), {"current": False})

    def test_the_shell_installer_checks_the_same_marker(self):
        shell = (SCRIPTS / "setup-compiler.sh").read_text()
        self.assertEqual(
            re.findall(r"grep -q '([^']+)' \"\$setup_vendor/out/cli/buildWorker.js\"", shell), [self.marker()]
        )
        self.assertIn('if [[ ! -f "$setup_cli" ]] || ! cli_worker_current; then', shell)


if __name__ == "__main__":
    unittest.main()
