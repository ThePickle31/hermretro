// src/shared/ holds the helpers the engine's modules had each kept a copy of. Its modules import only Node's own, so
// any module can use them without a cycle, and no other module keeps a copy of one again: a helper declared with the
// same code under any name, in either function form, with any local names, or a shared constant's value written out.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import * as acorn from "acorn";

const SRC = fileURLToPath(new URL("../../engine/src/", import.meta.url));
const SHARED = path.join(SRC, "shared");
const PARSE = { ecmaVersion: "latest", sourceType: "module", locations: true };
const POSITIONS = new Set(["type", "start", "end", "loc", "raw"]);
const FUNCTIONS = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);

function modules(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
    .map((entry) => path.join(entry.parentPath, entry.name));
}

function parse(file) {
  return acorn.parse(readFileSync(file, "utf8"), PARSE);
}

function visit(node, each) {
  if (!node || typeof node.type !== "string") return;
  each(node);
  for (const [key, value] of Object.entries(node)) {
    if (POSITIONS.has(key)) continue;
    for (const child of Array.isArray(value) ? value : [value])
      if (child && typeof child === "object") visit(child, each);
  }
}

/** The names a parameter or variable pattern binds. */
function bound(pattern) {
  if (!pattern) return [];
  if (pattern.type === "Identifier") return [pattern.name];
  if (pattern.type === "AssignmentPattern") return bound(pattern.left);
  if (pattern.type === "RestElement") return bound(pattern.argument);
  if (pattern.type === "ArrayPattern") return pattern.elements.flatMap(bound);
  if (pattern.type === "ObjectPattern") return pattern.properties.flatMap((each) => bound(each.value ?? each.argument));
  return [];
}

/**
 * The code of a declaration's value, the same however it is spelled: its own name and the names it binds (parameters,
 * variables, caught errors) become their order of binding, a function is one form whether declared, an expression or
 * an arrow (an arrow's expression body a return), and positions are left out.
 */
function code(value, name) {
  const locals = new Map([[name, "<self>"]]);
  const local = (each) => locals.has(each) || locals.set(each, `<local ${locals.size}>`);
  visit(value, (node) => {
    if (FUNCTIONS.has(node.type)) node.params.flatMap(bound).forEach(local);
    if (node.type === "VariableDeclarator") bound(node.id).forEach(local);
    if (node.type === "CatchClause") bound(node.param).forEach(local);
  });
  const form = (node) => {
    if (Array.isArray(node)) return node.map(form);
    if (!node || typeof node !== "object") return node;
    if (node.type === "Identifier") return locals.get(node.name) ?? node.name;
    if (node.type === "Literal") return ["Literal", node.regex ?? node.bigint ?? node.value];
    if (FUNCTIONS.has(node.type)) {
      const body = node.expression
        ? { type: "BlockStatement", body: [{ type: "ReturnStatement", argument: node.body }] }
        : node.body;
      return ["Function", node.async, node.generator, form(node.params), form(body)];
    }
    if (node.type === "ClassDeclaration" || node.type === "ClassExpression")
      return ["Class", form(node.superClass), form(node.body)];
    // A member's or a key's name is not a local, even when a local shares its spelling.
    if (node.type === "MemberExpression" && !node.computed) return ["Member", form(node.object), node.property.name];
    if (/^(Property|MethodDefinition|PropertyDefinition)$/.test(node.type) && !node.computed)
      return [
        node.type,
        node.kind,
        node.static,
        node.key.type === "Identifier" ? node.key.name : form(node.key),
        form(node.value),
      ];
    return [
      node.type,
      ...Object.entries(node)
        .filter(([key]) => !POSITIONS.has(key))
        .map(([, child]) => form(child)),
    ];
  };
  return JSON.stringify(form(value));
}

/** Each top-level declaration in `file`: its name, its value and that value's code. */
function declarations(file) {
  const found = [];
  for (let node of parse(file).body) {
    if (node.type === "ExportNamedDeclaration") node = node.declaration;
    if (!node) continue;
    const declared = node.id
      ? [{ id: node.id, value: node }]
      : (node.declarations ?? []).map((each) => ({ id: each.id, value: each.init }));
    for (const { id, value } of declared)
      if (id.type === "Identifier" && value) found.push({ name: id.name, value, code: code(value, id.name) });
  }
  return found;
}

test("the shared modules import only Node's own", () => {
  for (const file of modules(SHARED)) {
    visit(parse(file), (node) => {
      const source = node.source;
      if (!source) return;
      const target = source.type === "Literal" ? source.value : "a computed module";
      assert.ok(typeof target === "string" && target.startsWith("node:"), `${path.basename(file)} imports ${target}`);
    });
  }
});

test("no module keeps its own copy of a shared helper", () => {
  const shared = modules(SHARED).flatMap(declarations);
  const helpers = new Map(shared.map((each) => [each.code, each.name]));
  // A constant's value (not a function or a class) is a copy wherever it is written out, not only when declared.
  const constants = shared.filter((each) => !FUNCTIONS.has(each.value.type) && !/^Class/.test(each.value.type));
  const byCode = new Map(constants.map((each) => [each.code, each.name]));
  const types = new Set(constants.map((each) => each.value.type));
  const copies = [];
  for (const file of modules(SRC)) {
    if (file.startsWith(SHARED + path.sep)) continue;
    const where = path.relative(SRC, file);
    for (const { name, code: declared } of declarations(file))
      if (helpers.has(declared)) copies.push(`${where}: ${name} is shared/'s ${helpers.get(declared)}`);
    visit(parse(file), (node) => {
      const value = types.has(node.type) && byCode.get(code(node));
      if (value) copies.push(`${where}:${node.loc.start.line} writes out shared/'s ${value}`);
    });
  }
  assert.deepEqual(copies, []);
});
