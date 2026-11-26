// Whether two engine bundles hold the same program: what shows that a rebuild or a reorganisation of the engine
// changed nothing it does.
//
//   node tools/engine/compare_bundles.mjs <before> <after>    exit 0 only when they hold the same program
//
// Both bundles are parsed and compared as syntax trees, every name included. Only what cannot change what runs is
// left out: layout, comments, how a literal is spelled (`0x10` and `16`), parentheses that group nothing (a
// parenthesised assignment target is kept: `f = () => {}` names the function and `(f) = () => {}` does not), the
// shorthand of `{ a }` for `{ a: a }` (but not `{ __proto__ }`), and where import statements stand: what is imported
// is compared as a set, and the order in which modules are first requested (source and attributes) as a list. The
// one thing a program could see that is not compared is a function's source text (Function.prototype.toString).
//
// When the bundles differ, the report names the modules whose statements differ (a module is the run of statements
// after a bundler's marker comment, `// dist/<module>.js`) and the first statement where they part. When every
// difference is a binding with another name (what a bundler's renumbering does: `path45` for `path`), it lists the
// renamed bindings instead. Renamed bindings are still a difference: a program can see names (error messages,
// a function's name, eval), so whether a rename is harmless is for the reader to judge.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { MISSING, TOOLS } from "./bundle.mjs";

const MARK = /^ ((?:\.\.\/)*(?:dist|node_modules|scripts|src)\/\S+)$/;
const HEADER = "(bundle header)";
// Node fields that say where or how something is written, not what it is.
const UNCOMPARED = new Set(["type", "start", "end", "range", "loc", "raw"]);
const PROPERTIES = new Set(["Property", "MethodDefinition", "PropertyDefinition"]);

function loadParsers() {
  const require = createRequire(path.join(TOOLS, "package.json"));
  try {
    return { acorn: require("acorn"), scope: require("eslint-scope") };
  } catch {
    throw new Error(MISSING);
  }
}

const attributesOf = (declaration) => (declaration.attributes ?? []).map((attribute) => [attribute.key.name ?? attribute.key.value, attribute.value.value]);

// What an import binds: its kind (none for an import run only for its effects), source, the name it takes there,
// and its attributes.
function importedBy(specifier, declaration) {
  const kind = specifier ? { ImportDefaultSpecifier: "default", ImportNamespaceSpecifier: "namespace", ImportSpecifier: "named" }[specifier.type] : "none";
  const name = kind === "named" ? (specifier.imported.name ?? specifier.imported.value) : null;
  return ["import", kind, declaration.source.value, name, attributesOf(declaration)];
}

const propertyName = (node) => (node.computed ? null : node.key.type === "Identifier" ? node.key.name : node.key.value);

// The comparable form of a node. `named(identifier)` says what an identifier that is not a property's own name stands
// for: itself (its name) when names are compared, or the binding it refers to when renaming is looked for.
function form(node, named) {
  if (Array.isArray(node)) return node.map((child) => form(child, named));
  if (!node || typeof node !== "object") return node;
  switch (node.type) {
    case "Identifier":
      return named(node);
    case "Literal":
      if (node.regex) return ["Literal", "regex", node.regex.pattern, node.regex.flags];
      if (node.bigint !== undefined) return ["Literal", "bigint", node.bigint];
      return ["Literal", node.value === null ? "null" : typeof node.value, node.value];
    case "ParenthesizedExpression":
      return form(node.expression, named);
    case "AssignmentExpression":
      return ["AssignmentExpression", node.operator, node.left.type === "ParenthesizedExpression" ? ["parenthesised", form(node.left.expression, named)] : form(node.left, named), form(node.right, named)];
    case "ExportSpecifier":
      return ["ExportSpecifier", form(node.local, named), node.exported.name ?? node.exported.value];
  }
  const fields = [node.type];
  const own = PROPERTIES.has(node.type) ? propertyName(node) : null;
  for (const [field, value] of Object.entries(node)) {
    if (UNCOMPARED.has(field)) continue;
    // `{ a }` is `{ a: a }`, except that `{ __proto__ }` makes an own property and `{ __proto__: a }` the prototype.
    if (field === "shorthand" && own !== "__proto__") continue;
    fields.push(field, field === "key" && own !== null ? ["name", own] : form(value, named));
  }
  return fields;
}

// The program as { requests, imports: Set, statements: [{ module, line, key }] }, with identifiers as named() says.
function program(ast, markers, named) {
  const moduleAt = (position) => {
    let name = HEADER;
    for (const mark of markers) {
      if (mark.start > position) break;
      name = mark.name;
    }
    return name;
  };
  const requests = [];
  const imports = new Set();
  const statements = [];
  for (const statement of ast.body) {
    if (statement.source) {
      const request = JSON.stringify([statement.source.value, attributesOf(statement)]);
      if (!requests.includes(request)) requests.push(request);
    }
    if (statement.type === "ImportDeclaration") {
      if (!statement.specifiers.length) imports.add(JSON.stringify(importedBy(null, statement)));
      for (const specifier of statement.specifiers) imports.add(JSON.stringify([...importedBy(specifier, statement), named(specifier.local)]));
      continue;
    }
    statements.push({ module: moduleAt(statement.start), line: statement.loc.start.line, key: JSON.stringify(form(statement, named)) });
  }
  return { requests, imports, statements };
}

function parse(text, { acorn }) {
  const markers = [];
  const ast = acorn.parse(text, {
    ecmaVersion: "latest",
    sourceType: "module",
    allowHashBang: true,
    preserveParens: true,
    ranges: true,
    locations: true,
    onComment: (block, comment, start) => {
      const mark = !block && MARK.exec(comment);
      if (mark) markers.push({ start, name: mark[1].replace(/^(\.\.\/)+/, "") });
    },
  });
  return { ast, markers };
}

// Each identifier that refers to a binding, mapped to that binding's place: its scope (by the order scopes start
// in) and its place in that scope, or what it imports. Places are only for looking for renamed bindings.
function places({ ast }, { scope }) {
  const manager = scope.analyze(ast, { ecmaVersion: 2026, sourceType: "module", childVisitorKeys: { ParenthesizedExpression: ["expression"] } });
  const placed = new Map();
  manager.scopes.forEach((found, scopeIndex) => {
    found.variables.forEach((variable, index) => {
      const [definition] = variable.defs;
      const place = definition?.type === "ImportBinding" ? importedBy(definition.node, definition.parent) : ["binding", scopeIndex, index];
      const entry = { place: JSON.stringify(place), name: variable.name };
      // A class's name is a binding inside the class and another outside it; its declaration stands for the outer.
      for (const identifier of variable.identifiers) if (!placed.has(identifier)) placed.set(identifier, entry);
      for (const reference of variable.references) placed.set(reference.identifier, entry);
    });
  });
  return placed;
}

function same(a, b) {
  return JSON.stringify(a.requests) === JSON.stringify(b.requests) && JSON.stringify([...a.imports].sort()) === JSON.stringify([...b.imports].sort()) && a.statements.length === b.statements.length && a.statements.every((statement, index) => statement.key === b.statements[index].key);
}

// { same, renamed: null or [{ before, after }], requests, imports: { removed, added }, modules, parted }
export function compareBundles(before, after, parsers = loadParsers()) {
  const parsed = [parse(before, parsers), parse(after, parsers)];
  const [a, b] = parsed.map(({ ast, markers }) => program(ast, markers, (identifier) => ["name", identifier.name]));
  if (same(a, b)) return { same: true };

  // Is every difference a binding with another name?
  const placed = parsed.map((one) => places(one, parsers));
  const names = [new Map(), new Map()];
  const [x, y] = parsed.map(({ ast, markers }, side) =>
    program(ast, markers, (identifier) => {
      const entry = placed[side].get(identifier);
      if (!entry) return ["name", identifier.name];
      names[side].set(entry.place, entry.name);
      return ["binding", entry.place];
    }),
  );
  const renamed = same(x, y) ? [...names[0]].filter(([place, name]) => names[1].get(place) !== name).map(([place, name]) => ({ before: name, after: names[1].get(place) })) : null;

  const requests = JSON.stringify(a.requests) === JSON.stringify(b.requests) ? null : { before: a.requests, after: b.requests };
  const imports = { removed: [...a.imports].filter((item) => !b.imports.has(item)), added: [...b.imports].filter((item) => !a.imports.has(item)) };
  const grouped = (statements) => {
    const modules = new Map();
    for (const { module, key } of statements) modules.set(module, [...(modules.get(module) ?? []), key]);
    return modules;
  };
  const [p, q] = [grouped(a.statements), grouped(b.statements)];
  const modules = [...new Set([...p.keys(), ...q.keys()])].filter((name) => JSON.stringify(p.get(name)) !== JSON.stringify(q.get(name)));
  let parted = null;
  for (let index = 0; index < Math.max(a.statements.length, b.statements.length) && !parted; index++) {
    const [was, now] = [a.statements[index], b.statements[index]];
    if (was?.key !== now?.key) parted = { module: (was ?? now).module, before: was?.line ?? null, after: now?.line ?? null };
  }
  return { same: false, renamed, requests, imports, modules, parted };
}

function main([before, after]) {
  if (!before || !after) throw new Error("usage: node tools/engine/compare_bundles.mjs <before> <after>");
  const texts = [readFileSync(before, "utf8"), readFileSync(after, "utf8")];
  const result = compareBundles(...texts);
  if (result.same) {
    console.log("the bundles hold the same program");
    return 0;
  }
  if (result.renamed) {
    const pairs = new Map();
    for (const { before: was, after: now } of result.renamed) pairs.set(`${was} -> ${now}`, (pairs.get(`${was} -> ${now}`) ?? 0) + 1);
    console.log(`the bundles differ only in the names of ${result.renamed.length} bindings:`);
    for (const [pair, count] of [...pairs].slice(0, 50)) console.log(`  ${pair}${count > 1 ? ` (${count} bindings)` : ""}`);
    if (pairs.size > 50) console.log(`  (and ${pairs.size - 50} more names)`);
    return 1;
  }
  if (result.requests) console.log(`the modules are requested in another order:\n  - ${result.requests.before.join(", ")}\n  + ${result.requests.after.join(", ")}`);
  for (const item of result.imports.removed) console.log(`imported only by the first: ${item}`);
  for (const item of result.imports.added) console.log(`imported only by the second: ${item}`);
  if (result.modules.length) console.log(`${result.modules.length} modules differ:\n${result.modules.map((name) => `  ${name}`).join("\n")}`);
  else if (result.parted) console.log("every module has the same statements, in another order");
  if (result.parted) {
    const line = (text, number) => (number === null ? "(end)" : `${number}: ${text.split("\n")[number - 1].trim().slice(0, 200)}`);
    console.log(`first difference, in ${result.parted.module}:\n  - ${line(texts[0], result.parted.before)}\n  + ${line(texts[1], result.parted.after)}`);
  }
  return 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    if (error.message === MISSING) console.error("FIX: python tools/dev setup");
    process.exitCode = 1;
  }
}
