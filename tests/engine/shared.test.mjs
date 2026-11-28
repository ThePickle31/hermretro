// src/shared/ holds the helpers the engine's modules had each kept a copy of. Its modules import only Node's own, so
// any module can use them without a cycle, and no other module declares a copy of one again: the same code under any
// name, with any parameter names, fails here.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import * as acorn from "acorn";

const SRC = fileURLToPath(new URL("../../engine/src/", import.meta.url));
const SHARED = path.join(SRC, "shared");
const PARSE = { ecmaVersion: "latest", sourceType: "module" };

function modules(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
    .map((entry) => path.join(entry.parentPath, entry.name));
}

/** Each top-level declaration in `file` with its code: the tokens, with its own name and its parameters' made generic. */
function declarations(file) {
  const source = readFileSync(file, "utf8");
  const found = [];
  for (let node of acorn.parse(source, PARSE).body) {
    if (node.type === "ExportNamedDeclaration") node = node.declaration;
    if (!node) continue;
    const declared = node.id ? [node] : (node.declarations ?? []).filter((each) => each.id.type === "Identifier");
    for (const declaration of declared) {
      const value = declaration.init ?? declaration;
      const generic = new Map([[declaration.id.name, "<name>"]]);
      for (const [index, parameter] of (value.params ?? []).entries())
        if (parameter.type === "Identifier") generic.set(parameter.name, `<parameter ${index}>`);
      const tokens = [];
      let previous;
      for (const token of acorn.tokenizer(source.slice(value.start, value.end), PARSE)) {
        const isName = token.type.label === "name" && previous?.type.label !== ".";
        tokens.push(isName && generic.has(token.value) ? generic.get(token.value) : (token.value ?? token.type.label));
        previous = token;
      }
      found.push({ name: declaration.id.name, code: tokens.join(" ") });
    }
  }
  return found;
}

test("the shared modules import only Node's own", () => {
  for (const file of modules(SHARED)) {
    for (const node of acorn.parse(readFileSync(file, "utf8"), PARSE).body) {
      const source = node.source?.value;
      if (typeof source === "string") assert.ok(source.startsWith("node:"), `${path.basename(file)} imports ${source}`);
    }
  }
});

test("no module keeps its own copy of a shared helper", () => {
  const shared = new Map(modules(SHARED).flatMap((file) => declarations(file).map((each) => [each.code, each.name])));
  const copies = [];
  for (const file of modules(SRC)) {
    if (file.startsWith(SHARED + path.sep)) continue;
    for (const { name, code } of declarations(file))
      if (shared.has(code)) copies.push(`${path.relative(SRC, file)}: ${name} is shared/'s ${shared.get(code)}`);
  }
  assert.deepEqual(copies, []);
});
