// engine/src/engine-root.js: every path to the engine's own files is worked out there, from the top of src/, so a
// module can move into a folder without its paths changing (in the tests it runs from src/, in production from
// dist/server.js). No other module that runs in Node may work a path out from its own location.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { BROWSER } from "../../tools/engine/lint.mjs";
import { ENGINE_ROOT, enginePath, engineUrl } from "../../engine/src/engine-root.js";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const SRC = path.join(REPO, "engine", "src");
// The browser's files resolve their URLs from the page they are served on, which is right where they are.
const inBrowser = (relative) =>
  BROWSER.some((pattern) => (pattern.endsWith("/**/*.js") ? relative.startsWith(pattern.slice(0, -"**/*.js".length)) : relative === pattern));

test("the root is the engine folder, and paths and URLs inside it resolve there", () => {
  assert.equal(ENGINE_ROOT, path.join(REPO, "engine"));
  assert.ok(existsSync(enginePath("package.json")));
  assert.ok(enginePath("src/web-annotations/").endsWith(`${path.sep}web-annotations${path.sep}`), "a folder keeps its separator");
  assert.equal(JSON.parse(readFileSync(engineUrl("package.json"), "utf8")).name, "hermretro-engine");
});

test("no module that runs in Node works a path out from its own location", () => {
  const found = [];
  for (const entry of readdirSync(SRC, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".js")) continue;
    const relative = path.relative(REPO, path.join(entry.parentPath, entry.name)).split(path.sep).join("/");
    if (relative === "engine/src/engine-root.js" || inBrowser(relative)) continue;
    readFileSync(path.join(REPO, relative), "utf8").split("\n").forEach((line, index) => {
      // entry.js asks whether it is the script node started, which is about itself, not a path.
      if (/import\.meta\.(url|dirname|filename)/.test(line) && !/import\.meta\.url === pathToFileURL\(/.test(line)) {
        found.push(`${relative}:${index + 1}`);
      }
    });
  }
  assert.deepEqual(found, [], "FIX: take the path from engine/src/engine-root.js (enginePath, engineUrl, ENGINE_ROOT)");
});
