"""Replacing a compiled CLI: setup keeps the old one until its replacement is ready, and what the engine kept from the
old compiler (a cached web export, the native ROM receipt) is not reused with the new one."""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.support import isolated_home

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine" / "modretro-chromatic"

# applySetup for the build components, with detection, probes and the CLI installer replaced: an owned root gets a
# first CLI, the compiler then changes (detection reports it incompatible), and an upgrade fails offline before a
# retry succeeds while detection finds some other CLI (a desktop application's).
SETUP = """
import { mkdir, writeFile, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
const [root, scripts] = process.argv.slice(1);
const { applySetup } = await import(pathToFileURL(path.join(scripts, "setup.mjs")).href);
const target = path.join(root, "toolchain", ".local", "vendor", "gb-studio");
const cli = () => readFile(path.join(target, "out", "cli", "gb-studio-cli.js"), "utf8").catch(() => null);
let cliStatus = "missing";
let builds = 0;
const seen = [];
const report = () => ({ roots: {}, tasks: {}, components: ["node", "runtime", "cli", "gbdk", "python", "pyboy",
  "pillow", "uv", "desktop"].map((id) => ({ id, status: id === "cli" ? cliStatus : "ready" })) });
const installer = (offline) => async (id, context) => {
  seen.push({ id, previous: await cli() });
  if (offline) throw Object.assign(new Error("offline"), { code: "DOWNLOAD_FAILED" });
  const prepared = path.join(context.stageRoot, "gb-studio");
  await mkdir(path.join(prepared, "out", "cli"), { recursive: true });
  await writeFile(path.join(prepared, "out", "cli", "gb-studio-cli.js"), `build ${++builds}`);
  cliStatus = "ready";
  return { preparedPath: prepared, version: "4.3.2", provenance: {} };
};
const run = async (offline) => (await applySetup({ yes: true, root, components: ["build"], detect: async () => report(),
  probe: async (checked) => ({ ...checked, probesPassed: true, probeResults: [] }), installComponent: installer(offline) }))
  .components.find((entry) => entry.id === "cli").status;
const steps = {};
steps.install = await run(false);
cliStatus = "incompatible";
steps.offline = await run(true);
steps.afterOffline = await cli();
steps.quarantinedAfterOffline = (await readdir(path.join(root, "quarantine"))).length;
cliStatus = "ready";
steps.retry = await run(false);
steps.afterRetry = await cli();
steps.quarantined = (await readdir(path.join(root, "quarantine"))).length;
steps.seen = seen;
process.stdout.write(JSON.stringify(steps));
"""

# The engine's compiler-bound signing key, taken from the bundle as it runs, over a CLI folder.
KEY = """
import { createHash as createHash33, createHmac } from "node:crypto";
import { createReadStream } from "node:fs";
import { writeFile } from "node:fs/promises";
import path37 from "node:path";
const [source, cli] = process.argv.slice(1);
const compilerBoundKey = new Function("createHash33", "createHmac", "createReadStream", "path37",
  source + "\\nreturn compilerBoundKey;")(createHash33, createHmac, createReadStream, path37);
const key = Buffer.alloc(32, 7);
const hex = async () => (await compilerBoundKey(key, cli)).toString("hex");
const first = await hex();
const again = await hex();
await writeFile(path37.join(path37.dirname(cli), "buildWorker.js"), "// another compiler\\n");
const replaced = await hex();
process.stdout.write(JSON.stringify({ first, again, replaced }));
"""


def bundle_functions(*names: str) -> str:
    """The named top-level functions of the engine bundle, as its source text."""
    bundle = (ENGINE / "dist" / "server.js").read_text()
    found = []
    for name in names:
        match = re.search(rf"^(?:async )?function {name}\(.*?^}}\n", bundle, re.M | re.S)
        assert match, name
        found.append(match.group(0))
    return "\n".join(found)


class NodeTest(unittest.TestCase):
    def setUp(self):
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("node is not installed")
        self.tmp = isolated_home(self).base

    def node_json(self, script: str, *args: str) -> dict:
        result = subprocess.run(
            [self.node, "--input-type=module", "-e", script, *args], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class UpgradeOrder(NodeTest):
    def test_the_old_cli_stays_until_its_replacement_is_ready(self):
        root = self.tmp / "setup"
        root.mkdir()
        steps = self.node_json(SETUP, str(root), str(ENGINE / "scripts"))
        self.assertEqual(steps["install"], "prepared")
        # Offline, the upgrade fails and the CLI that was there still builds.
        self.assertEqual(steps["offline"], "failed")
        self.assertEqual(steps["afterOffline"], "build 1")
        self.assertEqual(steps["quarantinedAfterOffline"], 0)
        # The failed attempt's receipt does not let another detected CLI count as reused: the retry installs.
        self.assertEqual(steps["retry"], "prepared")
        self.assertEqual(steps["afterRetry"], "build 2")
        self.assertEqual(steps["quarantined"], 1)
        # Each preparation ran with the previous CLI still in place.
        self.assertEqual([entry["previous"] for entry in steps["seen"]], [None, "build 1", "build 1"])


class CompilerBoundKey(NodeTest):
    def test_a_replaced_build_worker_changes_the_key(self):
        cli = self.tmp / "out" / "cli" / "gb-studio-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("// cli\n")
        (cli.parent / "buildWorker.js").write_text("// compiler\n")
        source = bundle_functions("hashFile", "updateHash", "compilerBoundKey")
        keys = self.node_json(KEY, source, str(cli))
        self.assertEqual(keys["first"], keys["again"])
        self.assertNotEqual(keys["first"], keys["replaced"])

    def test_the_web_cache_and_the_native_receipt_use_it(self):
        bundle = (ENGINE / "dist" / "server.js").read_text()
        self.assertIn("const attestationKey = await compilerBoundKey(signing, cli);", bundle)
        self.assertIn(
            "const key = await compilerBoundKey(await signingKey(before.root, official.toolchainRoot, runtime), "
            "official.cliPath);",
            bundle,
        )
        self.assertEqual(bundle.count("await signingKey("), 2)


if __name__ == "__main__":
    unittest.main()
