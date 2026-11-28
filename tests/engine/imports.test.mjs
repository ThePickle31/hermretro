// The engine's modules import each other without cycles: a cycle ties modules together so none can be read, moved or
// tested alone. The imports inside the cycles there are today are listed in KNOWN, as "importer -> imported"; each
// refactor that breaks one takes its imports off, and any other import inside a cycle (a module importing itself
// included) fails here.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import * as acorn from "acorn";

const SRC = fileURLToPath(new URL("../../engine/src/", import.meta.url));
const KNOWN = [
  "actors.js -> native-script-events.js",
  "actors.js -> project.js",
  "assets.js -> audio.js",
  "assets.js -> palettes.js",
  "assets.js -> scene-graphics.js",
  "assets.js -> sprites.js",
  "audio.js -> assets.js",
  "contact-sheet.js -> palettes.js",
  "event-catalog.js -> native-script-events.js",
  "event-catalog.js -> project.js",
  "event-catalog.js -> world-script-graph.js",
  "native-script-events.js -> event-catalog.js",
  "palettes.js -> scene-graphics.js",
  "project-snapshot.js -> project.js",
  "project.js -> actors.js",
  "project.js -> native-script-events.js",
  "project.js -> project-snapshot.js",
  "scene-graphics.js -> contact-sheet.js",
  "scene-graphics.js -> palettes.js",
  "scene-graphics.js -> sprites.js",
  "sprites.js -> assets.js",
  "sprites.js -> palettes.js",
  "sprites.js -> scene-graphics.js",
  "world-script-graph.js -> project.js",
];

/** Each module (by its path under src/) and the modules under src/ it imports. */
function importGraph() {
  const graph = new Map();
  for (const entry of readdirSync(SRC, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".js")) continue;
    const file = path.join(entry.parentPath, entry.name);
    const tree = acorn.parse(readFileSync(file, "utf8"), { ecmaVersion: "latest", sourceType: "module" });
    const targets = new Set();
    for (const node of tree.body) {
      const source = node.source?.value;  // import ... from, export ... from
      if (typeof source === "string" && source.startsWith(".")) {
        const target = path.relative(SRC, path.resolve(path.dirname(file), source)).split(path.sep).join("/");
        if (!target.startsWith("..")) targets.add(target);
      }
    }
    graph.set(path.relative(SRC, file).split(path.sep).join("/"), targets);
  }
  return graph;
}

/** The groups of modules that import each other in a loop (strongly connected components of more than one). */
function cycles(graph) {
  const index = new Map(), low = new Map(), stack = [], onStack = new Set(), found = [];
  let next = 0;
  const visit = (node) => {
    index.set(node, next); low.set(node, next); next += 1; stack.push(node); onStack.add(node);
    for (const target of graph.get(node) ?? []) {
      if (!graph.has(target)) continue;
      if (!index.has(target)) { visit(target); low.set(node, Math.min(low.get(node), low.get(target))); }
      else if (onStack.has(target)) low.set(node, Math.min(low.get(node), index.get(target)));
    }
    if (low.get(node) === index.get(node)) {
      const group = [];
      let member;
      do { member = stack.pop(); onStack.delete(member); group.push(member); } while (member !== node);
      if (group.length > 1) found.push(group.sort());
    }
  };
  for (const node of graph.keys()) if (!index.has(node)) visit(node);
  return found.sort((a, b) => a[0].localeCompare(b[0]));
}

/** Every import from one module to another inside the same cycle, and every import of a module by itself. */
function cycleImports(graph) {
  const group = new Map();
  for (const members of cycles(graph)) for (const member of members) group.set(member, members);
  const found = [];
  for (const [importer, targets] of graph) {
    for (const imported of targets) {
      if (imported === importer || (group.has(importer) && group.get(importer) === group.get(imported))) {
        found.push(`${importer} -> ${imported}`);
      }
    }
  }
  return found.sort();
}

test("the engine's modules import each other in no cycle but the known imports", () => {
  assert.deepEqual(
    cycleImports(importGraph()),
    KNOWN,
    "FIX: break the new cycle (or, having broken a known one, take its imports off KNOWN)",
  );
});
