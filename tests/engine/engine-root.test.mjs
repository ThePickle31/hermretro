// engine/src/engine-root.js: every path to the engine's own files is worked out there, from the top of src/, so a
// module can move into a folder without its paths changing (in the tests it runs from src/, in production from
// dist/server.js). No other module that runs in Node may work a path out from its own location.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import * as acorn from "acorn";

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

/** Every use of `import.meta` in a module's code (not its comments), with the nodes around it, nearest first. */
function metaUses(source) {
  const found = [];
  const visit = (node, around) => {
    if (!node || typeof node.type !== "string") return;
    if (node.type === "MetaProperty" && node.meta.name === "import") found.push({ node, around });
    for (const value of Object.values(node)) {
      for (const child of Array.isArray(value) ? value : [value]) {
        if (child && typeof child.type === "string") visit(child, [node, ...around]);
      }
    }
  };
  visit(acorn.parse(source, { ecmaVersion: "latest", sourceType: "module", locations: true }), []);
  return found;
}

// entry.js asks whether it is the script node started, `import.meta.url === pathToFileURL(...).href`: about itself, not a
// path, so the one use allowed outside engine-root.js, and only in that comparison.
function startsItself(relative, { around: [member, comparison] }) {
  const other = comparison?.left === member ? comparison?.right : comparison?.left;
  return (
    relative === "engine/src/entry.js" &&
    member?.type === "MemberExpression" &&
    member.property.name === "url" &&
    comparison?.type === "BinaryExpression" &&
    comparison.operator === "===" &&
    other?.type === "MemberExpression" &&
    other.property.name === "href" &&
    other.object.type === "CallExpression" &&
    other.object.callee.name === "pathToFileURL"
  );
}

test("no module that runs in Node works a path out from its own location", () => {
  const found = [];
  for (const entry of readdirSync(SRC, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".js")) continue;
    const relative = path.relative(REPO, path.join(entry.parentPath, entry.name)).split(path.sep).join("/");
    if (relative === "engine/src/engine-root.js" || inBrowser(relative)) continue;
    const uses = metaUses(readFileSync(path.join(REPO, relative), "utf8")).filter((use) => !startsItself(relative, use));
    found.push(...uses.map(({ node }) => `${relative}:${node.loc.start.line}`));
  }
  assert.deepEqual(found, [], "FIX: take the path from engine/src/engine-root.js (enginePath, engineUrl, ENGINE_ROOT)");
});
