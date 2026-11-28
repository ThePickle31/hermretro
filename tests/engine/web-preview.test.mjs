// engine/src/web-preview.js: the page a running preview assembles from a game's web export, as a browser loads it.
// Every script the page names is served, and so is every module the annotation scripts import, followed as the browser
// follows them. tests/repo/test_engine_served_files.py checks the lists and the template; this checks the page itself.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import * as acorn from "acorn";

import { WebPreviewService } from "../../engine/src/web-preview.js";
import { copyStarter } from "./support.mjs";

const REPO = new URL("../../", import.meta.url);
const ROM = "rom/hello-color.gbc";

/** A game's web export: the player hermretro ships for its demo, with the engine's hello-color ROM. */
async function webExport(t) {
  const folder = await mkdtemp(path.join(tmpdir(), "hermretro-engine-preview-"));
  t.after(() => rm(folder, { recursive: true, force: true }));
  await cp(new URL("player/web", REPO), folder, { recursive: true });
  await mkdir(path.join(folder, "rom"));
  await cp(new URL("engine/examples/hello-color/hello-color.gbc", REPO), path.join(folder, ROM));
  return folder;
}

function imports(source) {
  const found = [];
  for (const node of acorn.parse(source, { ecmaVersion: "latest", sourceType: "module" }).body) {
    if ((node.type === "ImportDeclaration" || node.type.startsWith("Export")) && node.source) found.push(node.source.value);
  }
  return found;
}

test("the assembled page's scripts, and every module they import, are served", async (t) => {
  const project = await copyStarter(t);
  const folder = await webExport(t);
  const rom = await readFile(path.join(folder, ROM));
  const service = new WebPreviewService();
  t.after(() => service.stop());
  const preview = await service.start(folder, {
    assetsRoot: new URL("engine/src/web-annotations/", REPO).pathname,
    deviceAssetsRoot: new URL("player/skins/", REPO).pathname,
    romPath: ROM,
    romSha256: createHash("sha256").update(rom).digest("hex"),
    romSizeBytes: rom.length,
    sourceRevision: "a".repeat(64),
    projectRoot: path.dirname(project),
  });

  const page = await fetch(preview.url);
  assert.equal(page.status, 200);
  const html = await page.text();
  const scripts = [...html.matchAll(/<script\b([^>]*)\bsrc="([^"]+)"/g)].map(([, attributes, src]) => ({
    url: new URL(src, preview.url).href,
    module: /\btype="module"/.test(attributes),
  }));
  assert.ok(scripts.some((script) => script.module), "the page loads the annotation module");

  const seen = new Set();
  const queue = [...scripts];
  while (queue.length) {
    const { url, module } = queue.shift();
    if (seen.has(url)) continue;
    seen.add(url);
    const response = await fetch(url);
    assert.equal(response.status, 200, `${url.slice(preview.url.length)} is served`);
    const source = await response.text();
    if (module) queue.push(...imports(source).map((request) => ({ url: new URL(request, url).href, module: true })));
  }
  assert.ok(seen.size > scripts.length, "the annotation module's imports were followed");
});
