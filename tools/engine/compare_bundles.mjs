// Whether two engine bundles hold the same code, module by module: what shows that a rebuild or a reorganisation of
// the engine changed nothing it does.
//
//   node tools/engine/compare_bundles.mjs <before> <after>    exit 1 when any module differs
//
// A bundle's modules are the sections its bundler marks (`// dist/<module>.js`, `// node_modules/...`). Each is
// printed again by esbuild (so layout, indentation and redundant parentheses do not count), its imports are dropped
// (the bundler moves them) and the digits the bundler adds to names it renumbers are removed (`path45` and `path`
// read alike). Strings in quotes are compared exactly.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEsbuild, MISSING } from "./bundle.mjs";

const MARK = /^\/\/ ((?:\.\.\/)*(?:dist|node_modules|scripts|src)\/\S+)$/gm;
// A string in quotes (kept) or a name ending in digits (the digits dropped). Template literals are not skipped: the
// bundler renumbers the names inside their ${}.
const NUMBERED = /("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|\b([A-Za-z_$][\w$]*?)\d+\b/g;

// The bundle's modules by name, in order; a module written in several parts (its imports, then its code) is joined.
export function bundleModules(text) {
  const marks = [...text.matchAll(MARK)];
  const modules = new Map([["(bundle header)", text.slice(0, marks[0]?.index ?? text.length)]]);
  marks.forEach((mark, index) => {
    const name = mark[1].replace(/^(\.\.\/)+/, "");
    const end = index + 1 < marks.length ? marks[index + 1].index : text.length;
    modules.set(name, (modules.get(name) ?? "") + text.slice(mark.index + mark[0].length, end));
  });
  return modules;
}

function normalized(code, esbuild) {
  return esbuild
    .transformSync(code, { loader: "js", format: "esm", target: "esnext", legalComments: "none" })
    .code.replace(NUMBERED, (match, quoted, name) => quoted ?? name)
    .split("\n")
    .filter((line) => !/^import\s/.test(line));
}

// { same, different: [{ name, before, after }] }, where before and after are the first lines that differ
// (null for a module only one bundle has).
export function compareBundles(before, after, esbuild = loadEsbuild()) {
  const [a, b] = [bundleModules(before), bundleModules(after)];
  const result = { same: 0, different: [] };
  for (const name of new Set([...a.keys(), ...b.keys()])) {
    if (!a.has(name) || !b.has(name)) {
      result.different.push({ name, before: a.has(name) ? "(present)" : null, after: b.has(name) ? "(present)" : null });
      continue;
    }
    const [x, y] = [normalized(a.get(name), esbuild), normalized(b.get(name), esbuild)];
    const line = x.findIndex((text, index) => text !== y[index]);
    if (line === -1 && x.length === y.length) result.same++;
    else {
      const at = line === -1 ? Math.min(x.length, y.length) : line;
      result.different.push({ name, before: x[at] ?? "(end)", after: y[at] ?? "(end)" });
    }
  }
  return result;
}

function main([before, after]) {
  if (!before || !after) throw new Error("usage: node tools/engine/compare_bundles.mjs <before> <after>");
  const { same, different } = compareBundles(readFileSync(before, "utf8"), readFileSync(after, "utf8"));
  console.log(`${same} modules the same, ${different.length} different`);
  for (const { name, before: was, after: now } of different) {
    if (was === null || now === null) console.log(`  ${name}: only in ${was === null ? "the second" : "the first"}`);
    else console.log(`  ${name}:\n    - ${was.trim().slice(0, 200)}\n    + ${now.trim().slice(0, 200)}`);
  }
  return different.length ? 1 : 0;
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
