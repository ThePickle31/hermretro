// Whether two engine bundles hold the same program: what shows that a rebuild or a reorganisation of the engine
// changed nothing it does.
//
//   node tools/engine/compare_bundles.mjs <before> <after>    exit 1 when they differ
//
// Each bundle is parsed and every name is replaced by one that says where it is declared, so the names a bundler
// gives (`path45` for `path`) do not count and nothing else does: an import becomes what it imports (its source and
// the name it takes there, wherever the import statement stands), and any other binding becomes its module, its
// scope within the module and its place in that scope. Each top-level statement is then printed again by esbuild, so
// layout and redundant parentheses do not count either. The two bundles are the same when they import the same
// things and their statements are equal, in the same order. Strings, templates, regular expressions, property
// names and labels are compared exactly. Not compared: the order in which imported modules are first evaluated,
// comments, and what renaming changes at runtime (a function's `name`).
//
// A module is the run of statements after a bundler's marker comment (`// dist/<module>.js`, `// node_modules/...`);
// a module written in several parts (its imports, then its code) is one module. When the bundles differ, the report
// names the modules whose statements differ, or the first statement whose order changed.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEsbuild, MISSING, TOOLS } from "./bundle.mjs";

const MARK = /^ ((?:\.\.\/)*(?:dist|node_modules|scripts|src)\/\S+)$/;
const HEADER = "(bundle header)";
const SEPARATOR = "/*! hermretro-statement */";

function loadParsers() {
  const require = createRequire(path.join(TOOLS, "package.json"));
  try {
    return { acorn: require("acorn"), scope: require("eslint-scope") };
  } catch {
    throw new Error(MISSING);
  }
}

const short = (text) => createHash("sha256").update(text).digest("hex").slice(0, 12);

// Every node's parent, for the few places where a name stands for two things (shorthand properties and exports).
function parents(root) {
  const found = new Map();
  const visit = (node, parent) => {
    if (!node || typeof node.type !== "string") return;
    found.set(node, parent);
    for (const [key, value] of Object.entries(node)) {
      if (key === "loc" || key === "range") continue;
      if (Array.isArray(value)) value.forEach((child) => visit(child, node));
      else if (value && typeof value === "object") visit(value, node);
    }
  };
  visit(root, null);
  return found;
}

// The text to put where a binding's identifier stands, keeping what a shorthand also says (`{ a }` is `{ a: a }`,
// `export { a }` is `export { a as a }`).
function spelled(identifier, tree, name) {
  const parent = tree.get(identifier);
  const holder = parent?.type === "AssignmentPattern" && parent.left === identifier ? tree.get(parent) : parent;
  if (holder?.type === "Property" && holder.shorthand) return `${identifier.name}: ${name}`;
  if (parent?.type === "ExportSpecifier" && parent.local === identifier && parent.exported.start === identifier.start) return `${name} as ${identifier.name}`;
  return name;
}

// The text of node with the edits inside it made.
function renamed(text, edits, node) {
  let out = "";
  let at = node.start;
  for (let position = node.start; position < node.end; position++) {
    const edit = edits.get(position);
    if (!edit) continue;
    out += text.slice(at, position) + edit.text;
    at = edit.end;
    position = edit.end - 1;
  }
  return out + text.slice(at, node.end);
}

// The identifiers a declaration binds (`function a`, `class A`, `var a, { b } = c`).
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

// The bundle as { imports: Set, statements: [{ module, text }] } with every binding renamed by where it is declared.
export function canonical(text, { acorn, scope }, esbuild) {
  const markers = [];
  const ast = acorn.parse(text, {
    ecmaVersion: "latest",
    sourceType: "module",
    allowHashBang: true,
    ranges: true,
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
  const tree = parents(ast);

  // A name for each binding: an import by what it imports, anything else by its module, scope and place.
  const names = new Map();
  const scopesIn = new Map();
  const placesIn = new Map();
  const counter = (map, key) => {
    const next = (map.get(key) ?? 0) + 1;
    map.set(key, next);
    return next - 1;
  };
  for (const found of manager.scopes) {
    const owner = moduleAt(found.block.start);
    const scopeName = found.type === "module" || found.type === "global" ? "top" : String(counter(scopesIn, owner));
    for (const variable of found.variables) {
      const [definition] = variable.defs;
      if (!definition) continue;
      if (definition.type === "ImportBinding") {
        const specifier = definition.node;
        const imported = specifier.type === "ImportDefaultSpecifier" ? "default" : specifier.type === "ImportNamespaceSpecifier" ? "*" : (specifier.imported.name ?? specifier.imported.value);
        names.set(variable, `$i_${short(`${definition.parent.source.value}\0${imported}`)}`);
      } else {
        const module = moduleAt(definition.name.start);
        const place = counter(placesIn, `${module}\0${scopeName}`);
        names.set(variable, `$${short(module)}_${scopeName}_${place}`);
      }
    }
  }
  const edits = new Map();
  for (const [variable, name] of names) {
    for (const identifier of [...variable.identifiers, ...variable.references.map((reference) => reference.identifier)]) {
      edits.set(identifier.start, { end: identifier.end, text: spelled(identifier, tree, name) });
    }
  }

  const imports = new Set();
  const pieces = [];
  for (const statement of ast.body) {
    if (statement.type === "ImportDeclaration") {
      const attributes = JSON.stringify((statement.attributes ?? []).map((attribute) => [attribute.key.name ?? attribute.key.value, attribute.value.value]));
      if (!statement.specifiers.length) imports.add(`${statement.source.value} ${attributes}`);
      for (const specifier of statement.specifiers) {
        const imported = specifier.type === "ImportDefaultSpecifier" ? "default" : specifier.type === "ImportNamespaceSpecifier" ? "*" : (specifier.imported.name ?? specifier.imported.value);
        imports.add(`${statement.source.value} ${attributes} ${imported}`);
      }
      continue;
    }
    // `export function a` is `function a` exported as "a": its exported name stays, its binding is renamed.
    const exported = statement.type === "ExportNamedDeclaration" && statement.declaration;
    const code = renamed(text, edits, exported ? statement.declaration : statement);
    const names = exported ? declared(statement.declaration).map((identifier) => `${edits.get(identifier.start).text} as ${identifier.name}`) : [];
    pieces.push({ module: moduleAt(statement.start), text: names.length ? `${code};\nexport { ${names.join(", ")} };` : code });
  }
  const printed = esbuild
    .transformSync(pieces.map((piece) => piece.text).join(`\n${SEPARATOR}\n`), { loader: "js", format: "esm", target: "esnext", legalComments: "inline" })
    .code.split(SEPARATOR)
    .map((part) => part.trim());
  if (printed.length !== pieces.length) throw new Error("esbuild did not keep the statements apart");
  return { imports, statements: pieces.map((piece, index) => ({ module: piece.module, text: printed[index] })) };
}

function grouped(statements) {
  const modules = new Map();
  for (const { module, text } of statements) modules.set(module, [...(modules.get(module) ?? []), text]);
  return modules;
}

// { same, imports: { removed, added }, modules: [names whose statements differ], order: null or the first
// statement (with its module) where the two orders part }
export function compareBundles(before, after, esbuild = loadEsbuild(), parsers = loadParsers()) {
  const [a, b] = [canonical(before, parsers, esbuild), canonical(after, parsers, esbuild)];
  const imports = { removed: [...a.imports].filter((key) => !b.imports.has(key)), added: [...b.imports].filter((key) => !a.imports.has(key)) };
  const [x, y] = [grouped(a.statements), grouped(b.statements)];
  const modules = [...new Set([...x.keys(), ...y.keys()])].filter((name) => JSON.stringify(x.get(name)) !== JSON.stringify(y.get(name)));
  const index = a.statements.findIndex((statement, at) => statement.text !== b.statements[at]?.text);
  const parted = index === -1 && a.statements.length !== b.statements.length ? Math.min(a.statements.length, b.statements.length) : index;
  const order = parted === -1 ? null : { module: (a.statements[parted] ?? b.statements[parted]).module, before: a.statements[parted]?.text ?? "(end)", after: b.statements[parted]?.text ?? "(end)" };
  const same = !imports.removed.length && !imports.added.length && order === null;
  return { same, imports, modules, order };
}

function main([before, after]) {
  if (!before || !after) throw new Error("usage: node tools/engine/compare_bundles.mjs <before> <after>");
  const result = compareBundles(readFileSync(before, "utf8"), readFileSync(after, "utf8"));
  if (result.same) {
    console.log("the bundles hold the same program");
    return 0;
  }
  for (const key of result.imports.removed) console.log(`import only in the first: ${key}`);
  for (const key of result.imports.added) console.log(`import only in the second: ${key}`);
  if (result.modules.length) console.log(`${result.modules.length} modules differ:\n${result.modules.map((name) => `  ${name}`).join("\n")}`);
  else if (result.order) console.log("every module has the same statements, in a different order");
  if (result.order) {
    // The first line of the two statements that differs.
    const [was, now] = [result.order.before.split("\n"), result.order.after.split("\n")];
    const at = Math.max(0, was.findIndex((line, index) => line !== now[index]));
    const line = (lines) => (lines[at] ?? "(end)").trim().slice(0, 200);
    console.log(`first difference, in ${result.order.module}:\n  - ${line(was)}\n  + ${line(now)}`);
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
