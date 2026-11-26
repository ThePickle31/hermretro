// Whether two engine bundles hold the same program: what shows that a rebuild or a reorganisation of the engine
// changed nothing it does.
//
//   node tools/engine/compare_bundles.mjs <before> <after>    exit 1 when they differ
//
// Both bundles are parsed and compared as syntax trees, so layout and parentheses never count. What a bundler
// renames does not count either: each name that refers to a binding stands for that binding, an import's binding
// for what it imports (its kind, source, name and attributes) and any other for its module, its scope within the
// module and its place there. Everything else is compared exactly: values of literals, template text, property
// names, labels, names with no binding (globals), and the names a running program can see, which are a function's
// or class's own name and, when the bundle calls eval, every name. Where import statements stand does not count;
// the order in which modules are first requested does, and so does the set of things imported. Not compared:
// comments, and a function's source text (Function.prototype.toString).
//
// A module is the run of statements after a bundler's marker comment (`// dist/<module>.js`, `// node_modules/...`);
// a module written in several parts (its imports, then its code) is one module. When the bundles differ, the report
// names the modules whose statements differ and the first statement where the two programs part.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { MISSING, TOOLS } from "./bundle.mjs";

const MARK = /^ ((?:\.\.\/)*(?:dist|node_modules|scripts|src)\/\S+)$/;
const HEADER = "(bundle header)";
// Node fields that say where or how something is written, not what it is: `{ a }` is `{ a: a }`.
const UNCOMPARED = new Set(["type", "start", "end", "range", "loc", "shorthand"]);
const FUNCTIONS = new Set(["FunctionExpression", "ArrowFunctionExpression", "ClassExpression"]);
const PROPERTIES = new Set(["Property", "MethodDefinition", "PropertyDefinition"]);

function loadParsers() {
  const require = createRequire(path.join(TOOLS, "package.json"));
  try {
    return { acorn: require("acorn"), scope: require("eslint-scope") };
  } catch {
    throw new Error(MISSING);
  }
}

// What an import takes: its kind (default, namespace, named, or none for an import only run for its effects), source,
// the name it takes there, and its attributes.
function imported(specifier, declaration) {
  const kind = specifier ? { ImportDefaultSpecifier: "default", ImportNamespaceSpecifier: "namespace", ImportSpecifier: "named" }[specifier.type] : "none";
  const name = kind === "named" ? (specifier.imported.name ?? specifier.imported.value) : null;
  const attributes = (declaration.attributes ?? []).map((attribute) => [attribute.key.name ?? attribute.key.value, attribute.value.value]);
  return JSON.stringify(["import", kind, declaration.source.value, name, attributes]);
}

// The identifiers a declaration binds (`function a`, `class A`, `var a, { b = 1 } = c`).
function declared(declaration) {
  if (declaration.id) return [declaration.id];
  const found = [];
  const collect = (pattern) => {
    if (!pattern) return;
    if (pattern.type === "Identifier") found.push(pattern);
    else if (pattern.type === "ObjectPattern") pattern.properties.forEach((property) => collect(property.type === "RestElement" ? property.argument : property.value));
    else if (pattern.type === "ArrayPattern") pattern.elements.forEach(collect);
    else if (pattern.type === "AssignmentPattern") collect(pattern.left);
    else if (pattern.type === "RestElement") collect(pattern.argument);
  };
  (declaration.declarations ?? []).forEach((declarator) => collect(declarator.id));
  return found;
}

const anonymous = (node) => node && FUNCTIONS.has(node.type) && !node.id;

// Whether a running program can see the binding's name: a function's or class's own name, or a name given to an
// anonymous function or class (`var f = () => {}`, `f = class {}`, `(f = function () {}) => f`).
function seen(variable) {
  if (variable.defs.some((definition) => definition.type === "FunctionName" || definition.type === "ClassName")) return true;
  if (variable.defs.some((definition) => definition.node.type === "VariableDeclarator" && definition.node.id === definition.name && anonymous(definition.node.init))) return true;
  return variable.references.some((reference) => reference.isWrite() && anonymous(reference.writeExpr));
}

// The bundle as { requests, imports, statements: [{ module, line, key }] }: the modules it requests in the order it
// first does, what it imports, and each top-level statement but the imports as a comparable key.
export function canonical(text, { acorn, scope }) {
  const markers = [];
  const ast = acorn.parse(text, {
    ecmaVersion: "latest",
    sourceType: "module",
    allowHashBang: true,
    ranges: true,
    locations: true,
    onComment: (block, comment, start) => {
      const mark = !block && MARK.exec(comment);
      if (mark) markers.push({ start, name: mark[1].replace(/^(\.\.\/)+/, "") });
    },
  });
  const moduleAt = (position) => {
    let name = HEADER;
    for (const mark of markers) {
      if (mark.start > position) break;
      name = mark.name;
    }
    return name;
  };
  const manager = scope.analyze(ast, { ecmaVersion: 2026, sourceType: "module" });
  const evaluated = manager.globalScope.through.some((reference) => reference.identifier.name === "eval");

  // Each binding's identity, and what each identifier node refers to.
  const refers = new Map();
  const scopesIn = new Map();
  const placesIn = new Map();
  const next = (counts, key) => {
    const count = counts.get(key) ?? 0;
    counts.set(key, count + 1);
    return count;
  };
  for (const found of manager.scopes) {
    const owner = moduleAt(found.block.start);
    const scopeName = found.type === "module" || found.type === "global" ? "top" : next(scopesIn, owner);
    for (const variable of found.variables) {
      const [definition] = variable.defs;
      let identity;
      if (!definition) identity = JSON.stringify(["implicit", variable.name]);
      else if (definition.type === "ImportBinding") identity = imported(definition.node, definition.parent);
      else {
        const module = moduleAt(definition.name.start);
        const place = next(placesIn, `${module}\0${scopeName}`);
        identity = JSON.stringify(["binding", module, scopeName, place, evaluated || seen(variable) ? variable.name : null]);
      }
      // A class's name is a binding inside the class and another outside it; its declaration stands for the outer.
      for (const identifier of variable.identifiers) if (!refers.has(identifier)) refers.set(identifier, ["B", identity]);
      for (const reference of variable.references) refers.set(reference.identifier, ["B", identity]);
    }
    for (const reference of found.references) if (!reference.resolved) refers.set(reference.identifier, ["G", reference.identifier.name]);
  }

  const key = (node) => {
    if (Array.isArray(node)) return node.map(key);
    if (!node || typeof node !== "object") return node;
    if (node.type === "Identifier") return refers.get(node) ?? ["N", node.name];
    if (node.type === "Literal") {
      if (node.regex) return ["Literal", "regex", node.regex.pattern, node.regex.flags];
      if (node.bigint !== undefined) return ["Literal", "bigint", node.bigint];
      return ["Literal", node.value === null ? "null" : typeof node.value, node.value];
    }
    if (node.type === "ExportSpecifier") return ["ExportSpecifier", key(node.local), node.exported.name ?? node.exported.value];
    // A property's own name is a name even where it is also a binding's (`{ a }`).
    const named = PROPERTIES.has(node.type) && !node.computed && node.key.type === "Identifier";
    const fields = [node.type];
    for (const [name, value] of Object.entries(node)) {
      if (!UNCOMPARED.has(name)) fields.push(name, named && name === "key" ? ["N", value.name] : key(value));
    }
    // `export function a` exports the name "a", whatever the binding is called.
    if (node.type === "ExportNamedDeclaration" && node.declaration) fields.push("exports", declared(node.declaration).map((identifier) => identifier.name));
    return fields;
  };

  const requests = [];
  const imports = new Set();
  const statements = [];
  for (const statement of ast.body) {
    if (statement.source && !requests.includes(statement.source.value)) requests.push(statement.source.value);
    if (statement.type === "ImportDeclaration") {
      if (!statement.specifiers.length) imports.add(imported(null, statement));
      for (const specifier of statement.specifiers) imports.add(imported(specifier, statement));
      continue;
    }
    statements.push({ module: moduleAt(statement.start), line: statement.loc.start.line, key: JSON.stringify(key(statement)) });
  }
  return { requests, imports, statements };
}

function grouped(statements) {
  const modules = new Map();
  for (const { module, key } of statements) modules.set(module, [...(modules.get(module) ?? []), key]);
  return modules;
}

// { same, requests: null or both orders, imports: { removed, added }, modules: [names whose statements differ],
// parted: null or { module, before, after } (the line of the first statement where the programs part, or null) }
export function compareBundles(before, after, parsers = loadParsers()) {
  const [a, b] = [canonical(before, parsers), canonical(after, parsers)];
  const requests = JSON.stringify(a.requests) === JSON.stringify(b.requests) ? null : { before: a.requests, after: b.requests };
  const imports = { removed: [...a.imports].filter((item) => !b.imports.has(item)), added: [...b.imports].filter((item) => !a.imports.has(item)) };
  const [x, y] = [grouped(a.statements), grouped(b.statements)];
  const modules = [...new Set([...x.keys(), ...y.keys()])].filter((name) => JSON.stringify(x.get(name)) !== JSON.stringify(y.get(name)));
  const length = Math.max(a.statements.length, b.statements.length);
  let parted = null;
  for (let index = 0; index < length && !parted; index++) {
    const [was, now] = [a.statements[index], b.statements[index]];
    if (was?.key !== now?.key) parted = { module: (was ?? now).module, before: was?.line ?? null, after: now?.line ?? null };
  }
  const same = !requests && !imports.removed.length && !imports.added.length && !parted;
  return { same, requests, imports, modules, parted };
}

function main([before, after]) {
  if (!before || !after) throw new Error("usage: node tools/engine/compare_bundles.mjs <before> <after>");
  const texts = [readFileSync(before, "utf8"), readFileSync(after, "utf8")];
  const result = compareBundles(...texts);
  if (result.same) {
    console.log("the bundles hold the same program");
    return 0;
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
