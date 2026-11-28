// The engine's modules import each other without cycles: a cycle ties modules together so none can be read, moved or
// tested alone. The ones there are today are listed in KNOWN; each refactor that breaks one takes it off, and a new
// cycle fails here.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import * as acorn from "acorn";

const SRC = fileURLToPath(new URL("../../engine/src/", import.meta.url));
const KNOWN = [
  ["actors.js", "event-catalog.js", "native-script-events.js", "project-snapshot.js", "project.js", "world-script-graph.js"],
  ["assets.js", "audio.js", "contact-sheet.js", "palettes.js", "scene-graphics.js", "sprites.js"],
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

test("the engine's modules import each other in no cycle but the known ones", () => {
  assert.deepEqual(cycles(importGraph()), KNOWN, "FIX: break the new cycle (or, having broken a known one, take it off KNOWN)");
});
