// Whether two engine bundles hold the same program: what shows that a rebuild or a reorganisation of the engine
// changed nothing it does.
//
//   node tools/engine/compare_bundles.mjs <before> <after>    exit 0 only when they hold the same program
//
// Both bundles are parsed and compared as syntax trees, every name included. Only what cannot change what runs is
// left out: layout, comments, how a literal is spelled (`0x10` and `16`, and so `{ 1: a }` and `{ "1": a }`; a
// template's raw text and a directive's spelling, `"use strict"`, are kept), parentheses that group nothing (a
// parenthesised target is kept: `f = () => {}` names the function and `(f) = () => {}` does not), the shorthand of
// `{ a }` for `{ a: a }` (but not `{ __proto__ }`), and where import statements stand: what is imported is compared
// as a sorted list, one entry for each binding (`import a from` is `import { default as a } from`), and the order in
// which modules are first requested (source and attributes) as a list, which is all an import run only for its
// effects does. What a program could see that is not compared is where its code stands: a function's source
// text (Function.prototype.toString) and the file names, line and column numbers a stack trace gives (a
// `//# sourceURL=` comment names a file).
//
// When the bundles differ, the report names the modules whose statements differ (a module is the run of statements
// after a bundler's marker comment, `// src/<module>.js`) and the first statement where they part. When every
// difference is a binding with another name (what a bundler's renumbering does: `path45` for `path`), it lists the
// renamed bindings instead. Renamed bindings are still a difference: a program can see names (error messages,
// a function's name, eval), so whether a rename is harmless is for the reader to judge.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { MISSING, runsAsScript, TOOLS } from "./bundle.mjs";

// A marker names a file, which may have spaces in its name.
const MARK = /^ ((?:\.\.\/)*(?:dist|node_modules|scripts|src)\/.+)$/;
// What JavaScript counts as the end of a line (acorn numbers lines by these).
const LINE_END = /\r\n|[\n\r\u2028\u2029]/;
const HEADER = "(bundle header)";
// Node fields that say where or how something is written, not what it is.
const UNCOMPARED = new Set(["type", "start", "end", "range", "loc"]);
const PROPERTIES = new Set(["Property", "MethodDefinition", "PropertyDefinition"]);
// Nodes whose `left` is a target that names an anonymous function assigned to it, unless it is parenthesised.
const TARGETS = new Set(["AssignmentExpression", "AssignmentPattern"]);

function loadParsers() {
  const require = createRequire(path.join(TOOLS, "package.json"));
  try {
    return { acorn: require("acorn"), scope: require("eslint-scope") };
  } catch {
    throw new Error(MISSING);
  }
}

const attributesOf = (declaration) => (declaration.attributes ?? []).map((attribute) => [attribute.key.name ?? attribute.key.value, attribute.value.value]);

// What an import binds: the module's namespace or one of its exports (`import a from` is
// `import { default as a } from`), its source and its attributes.
function importedBy(specifier, declaration) {
  const what = specifier.type === "ImportNamespaceSpecifier" ? ["namespace"] : ["export", specifier.type === "ImportDefaultSpecifier" ? "default" : (specifier.imported.name ?? specifier.imported.value)];
  return ["import", ...what, declaration.source.value, attributesOf(declaration)];
}

// A property's own key when it is written as a name: `a`, `"a"` and `'a'` are the key "a" (and `1` and `"1"` the
// key "1"); a private name `#a` is a key of another kind, never the same as a string "#a".
function propertyKey(node) {
  if (node.computed) return null;
  if (node.key.type === "PrivateIdentifier") return ["private", node.key.name];
  return ["name", node.key.type === "Identifier" ? node.key.name : String(node.key.value)];
}

// The comparable form of a node. `named(identifier)` says what an identifier that is not a property's own name stands
// for: itself (its name) when names are compared, or the binding it refers to when renaming is looked for.
function form(node, named) {
  if (Array.isArray(node)) return node.map((child) => form(child, named));
  if (!node || typeof node !== "object") return node;
  switch (node.type) {
    case "Identifier":
      return named(node);
    case "Literal":
      // A regular expression's flags in any order are the same flags (`gm` is `mg`).
      if (node.regex) return ["Literal", "regex", node.regex.pattern, [...node.regex.flags].sort().join("")];
      if (node.bigint !== undefined) return ["Literal", "bigint", node.bigint];
      return ["Literal", node.value === null ? "null" : typeof node.value, node.value];
    case "ParenthesizedExpression":
      return form(node.expression, named);
    case "ExportSpecifier":
      return ["ExportSpecifier", form(node.local, named), node.exported.name ?? node.exported.value];
  }
  const fields = [node.type];
  const own = PROPERTIES.has(node.type) ? propertyKey(node) : null;
  for (const [field, value] of Object.entries(node)) {
    if (UNCOMPARED.has(field)) continue;
    // `{ a }` is `{ a: a }`, except that `{ __proto__ }` makes an own property and `{ __proto__: a }` the prototype.
    if (field === "shorthand" && own?.[1] !== "__proto__") continue;
    if (field === "key" && own !== null) fields.push(field, own);
    // A parenthesised target (`(f) = ...`, `[(f) = ...] = ...`) gives an anonymous function no name.
    else if (field === "left" && TARGETS.has(node.type) && value.type === "ParenthesizedExpression") fields.push(field, ["parenthesised", form(value.expression, named)]);
    else fields.push(field, form(value, named));
  }
  return fields;
}

// The program as { requests, imports (sorted, one entry for each binding), statements: [{ module, node, key }] },
// with identifiers as named() says. An import run only for its effects is in the requests alone.
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
  const imports = [];
  const statements = [];
  for (const statement of ast.body) {
    if (statement.source) {
      const request = JSON.stringify([statement.source.value, attributesOf(statement)]);
      if (!requests.includes(request)) requests.push(request);
    }
    if (statement.type === "ImportDeclaration") {
      for (const specifier of statement.specifiers) imports.push(JSON.stringify([...importedBy(specifier, statement), named(specifier.local)]));
      continue;
    }
    statements.push({ module: moduleAt(statement.start), node: statement, key: JSON.stringify(form(statement, named)) });
  }
  return { requests, imports: imports.sort(), statements };
}

// The nodes a node holds, in order, as form() compares them: a property's key written as a name is part of the
// property itself, and parentheses stand for what they hold.
function children(node) {
  const found = [];
  const named = PROPERTIES.has(node.type) && !node.computed;
  for (const [field, value] of Object.entries(node)) {
    if (UNCOMPARED.has(field) || (named && field === "key")) continue;
    for (let child of Array.isArray(value) ? value : [value]) {
      while (child?.type === "ParenthesizedExpression" && !(field === "left" && TARGETS.has(node.type))) child = child.expression;
      if (child && typeof child.type === "string") found.push(child);
    }
  }
  return found;
}

// The innermost nodes where two statements that differ part: the first pair of children that differ, while the two
// hold as many children. Where one holds more (a statement added or taken out), the first child that differs, or
// the first one only one of them has, with the other side's holder where it has none.
function parting(a, b, named) {
  const key = (node) => JSON.stringify(form(node, named));
  for (;;) {
    const [x, y] = [children(a), children(b)];
    const differing = x.findIndex((child, index) => index >= y.length || key(child) !== key(y[index]));
    const at = differing === -1 ? x.length : differing;
    if (x.length !== y.length) return [x[at] ?? a, y[at] ?? b];
    if (differing === -1) return [a, b];
    [a, b] = [x[at], y[at]];
  }
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
  const aliases = new Map();
  manager.scopes.forEach((found, scopeIndex) => {
    // Bindings are numbered in their scope without the imports, so moving an import renumbers nothing.
    let index = 0;
    found.variables.forEach((variable) => {
      const [definition] = variable.defs;
      let place;
      if (definition?.type !== "ImportBinding") place = ["binding", scopeIndex, index++];
      else {
        // Each name an import is given is a binding of its own: the first, second, ... for what it imports.
        const what = JSON.stringify(importedBy(definition.node, definition.parent));
        aliases.set(what, (aliases.get(what) ?? -1) + 1);
        place = [what, aliases.get(what)];
      }
      const entry = { place: JSON.stringify(place), name: variable.name };
      // A class's name is a binding inside the class and another outside it; its declaration stands for the outer.
      for (const identifier of variable.identifiers) if (!placed.has(identifier)) placed.set(identifier, entry);
      for (const reference of variable.references) placed.set(reference.identifier, entry);
    });
  });
  return placed;
}

// The entries of a not in b, counting repeats.
function without(a, b) {
  const left = [...b];
  return a.filter((item) => {
    const at = left.indexOf(item);
    if (at === -1) return true;
    left.splice(at, 1);
    return false;
  });
}

function same(a, b) {
  return JSON.stringify(a.requests) === JSON.stringify(b.requests) && JSON.stringify(a.imports) === JSON.stringify(b.imports) && a.statements.length === b.statements.length && a.statements.every((statement, index) => statement.key === b.statements[index].key);
}

const byName = (identifier) => ["name", identifier.name];

// { same, renamed: null or [{ before, after }], requests, imports: { removed, added }, modules, parted }
export function compareBundles(before, after, parsers = loadParsers()) {
  const parsed = [parse(before, parsers), parse(after, parsers)];
  const [a, b] = parsed.map(({ ast, markers }) => program(ast, markers, byName));
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
  const changed = same(x, y) ? [...names[0]].filter(([place, name]) => names[1].get(place) !== name).map(([place, name]) => ({ before: name, after: names[1].get(place) })) : [];
  // A difference in no name is not a rename: something else differs that the places cannot tell apart.
  const renamed = changed.length ? changed : null;

  const requests = JSON.stringify(a.requests) === JSON.stringify(b.requests) ? null : { before: a.requests, after: b.requests };
  const imports = { removed: without(a.imports, b.imports), added: without(b.imports, a.imports) };
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
    if (was?.key === now?.key) continue;
    const [first, second] = was && now ? parting(was.node, now.node, byName) : [was?.node, now?.node];
    parted = { module: (was ?? now).module, before: first?.loc.start.line ?? null, after: second?.loc.start.line ?? null };
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
    const line = (text, number) => (number === null ? "(end)" : `${number}: ${text.split(LINE_END)[number - 1].trim().slice(0, 200)}`);
    console.log(`first difference, in ${result.parted.module}:\n  - ${line(texts[0], result.parted.before)}\n  + ${line(texts[1], result.parted.after)}`);
  }
  return 1;
}

if (runsAsScript(import.meta.url)) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    if (error.message === MISSING) console.error("FIX: python tools/dev setup");
    process.exitCode = 1;
  }
}
