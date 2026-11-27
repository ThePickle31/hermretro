// For tests/repo/test_engine_served_files.py: what a page serving a list of the engine's browser files would 404 on.
//
//   node engine_served_files.mjs <tools> <module> <list> <folder> <bases> <ignores-query> <entries>
//
// <tools> holds the pinned parser (tools/engine/npm); <module> declares the list <list> of files, relative to
// <folder>; <bases> are the folder URLs (JSON) the page serves them from; <ignores-query> is "yes" when its router
// drops a query; <entries> are the page's entry scripts (JSON) as [page URL, folder URL, src]. Prints the listed files
// and every import or entry script the browser would not find, each request resolved as the browser resolves it.

import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";

const [tools, listModule, listName, folder, basesJson, ignoresQuery, entriesJson] = process.argv.slice(2);
const acorn = createRequire(path.join(tools, "package.json"))("acorn");
const parse = (file) => acorn.parse(readFileSync(file, "utf8"), { ecmaVersion: "latest", sourceType: "module" });

function* nodes(node) {
  if (!node || typeof node.type !== "string") return;
  yield node;
  for (const value of Object.values(node))
    for (const child of Array.isArray(value) ? value : [value]) if (child && typeof child === "object") yield* nodes(child);
}

const declared = [...nodes(parse(listModule))].find((node) => node.type === "VariableDeclarator" && node.id.name === listName);
if (declared?.init?.type !== "ArrayExpression") throw new Error(`${listModule} has no ${listName} array`);
const served = declared.init.elements.map((element, index) => {
  if (element?.type !== "Literal" || typeof element.value !== "string")
    throw new Error(`${listName}[${index}] in ${listModule} is not a string literal`);
  return element.value;
});

// The listed file a relative request made from a URL reaches under base, or null. The browser never sends a
// fragment; the preview's router also drops the query, the capture page's refuses one.
function reaches(request, from, base) {
  if (!/^\.\.?\//.test(request)) return null;
  const url = new URL(request, from).href.replace(/#.*$/, "");
  if (!url.startsWith(base)) return null;
  const file = ignoresQuery === "yes" ? url.slice(base.length).replace(/\?.*$/, "") : url.slice(base.length);
  return served.includes(file) ? file : null;
}

// A request's text when the source states it: a string, or a template with nothing substituted.
const literal = (source) => source?.type === "Literal" && typeof source.value === "string" ? source.value
  : source?.type === "TemplateLiteral" && source.expressions.length === 0 ? source.quasis[0].value.cooked : null;

const problems = [];
for (const [page, base, source] of JSON.parse(entriesJson))
  if (reaches(source, page, base) === null) problems.push(`the page at ${page} loads ${JSON.stringify(source)}, which it does not serve`);
const kinds = ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration", "ImportExpression"];
for (const entry of served) {
  for (const node of nodes(parse(path.join(folder, entry)))) {
    if (!kinds.includes(node.type) || !node.source) continue;
    const request = literal(node.source);
    if (request === null) continue; // a computed request: its target is checked by name in the test
    for (const base of JSON.parse(basesJson))
      if (reaches(request, base + entry, base) === null)
        problems.push(`${entry} imports ${JSON.stringify(request)}, which the page served from ${base} does not serve`);
  }
}
console.log(JSON.stringify({ served, problems }));
