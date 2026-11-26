// Build the engine's server bundle (dist/server.js) from its modules, the way ModRetro built it
// (scripts/bundle-mcp.mjs): one ESM file for Node 22 holding every dist/ module and the packages they import, with
// scripts/ left as imports beside it, built by the esbuild and packages pinned in tools/engine/npm.
//
//   node tools/engine/bundle.mjs --entry <file> [--engine <folder>] [--out <file>]   build (writes when bytes change)
//   node tools/engine/bundle.mjs --entry <file> [--engine <folder>] --check          verify the bundle; writes nothing
//
// --entry is the server's own module, built in as dist/server.js, the name the bundle has always given it.
// --engine defaults to engine/modretro-chromatic and --out to the engine's dist/server.js. The build runs in a
// temporary folder holding a copy of the engine's dist/, scripts/ and package.json and of the pinned packages as its
// node_modules, so the bundle's module comments read as they always have (`// dist/emulator.js`,
// `// node_modules/zod/...`) and modules resolve as they did for ModRetro. The bundle may hold only the engine's
// modules and packages its lock file (scripts/runtime-package-lock.json) names at that version, each with its
// licence file, whose text the engine's notices (licenses/bundled-javascript.txt) carry; the engine's folders may
// hold no links (as its manifest requires). A stopped build leaves nothing behind.

import { chmodSync, cpSync, existsSync, lstatSync, mkdtempSync, readdirSync, readFileSync, realpathSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { builtinModules, createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const TOOLS = path.join(ROOT, "tools", "engine", "npm");
export const ENGINE = path.join(ROOT, "engine", "modretro-chromatic");
export const MISSING = "esbuild and the engine's packages were not found (npm ci --prefix tools/engine/npm --ignore-scripts)";
const NOTICES = path.join("licenses", "bundled-javascript.txt");
const LOCK = path.join("scripts", "runtime-package-lock.json");
// The names ModRetro's build looks for a package's licence under, in its order.
const LICENCE_FILES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "license", "license.md", "license.txt", "License", "License.txt"];
const BUILTINS = new Set(builtinModules.flatMap((name) => [name, `node:${name}`]));
// The build's own tools, which the bundle never includes.
const NOT_COPIED = new Set([".bin", "esbuild", "@esbuild"]);

export function loadEsbuild() {
  if (!existsSync(path.join(TOOLS, "node_modules", "esbuild", "package.json"))) throw new Error(MISSING);
  return createRequire(path.join(TOOLS, "package.json"))("esbuild");
}

// Files and folders this process made and has not removed yet; a stop (Ctrl-C, SIGTERM) removes them first.
const leftovers = new Set();
function stopped(signal) {
  for (const made of leftovers) rmSync(made, { recursive: true, force: true });
  process.kill(process.pid, signal);
}
function made(where) {
  if (!leftovers.size) process.once("SIGINT", stopped).once("SIGTERM", stopped);
  leftovers.add(where);
  return where;
}
// Removes what this process made. Never throws, so it cannot hide the error that stopped the build; a folder it
// could not remove is named.
function removed(where) {
  try {
    if (existsSync(where) && lstatSync(where).isDirectory()) writable(where);
    rmSync(where, { recursive: true, force: true });
  } catch (error) {
    console.error(`could not remove ${where}: ${error.message}`);
  }
  leftovers.delete(where);
  if (!leftovers.size) process.off("SIGINT", stopped).off("SIGTERM", stopped);
}

// Leaves every import of a file under scripts/ outside the bundle, as a path from the bundle's folder (an import from
// dist/device-capture/ of ../../scripts/x.mjs is ../scripts/x.mjs in dist/server.js), as esbuild writes a path it
// matches with a pattern.
function scriptsBeside(stage) {
  const scripts = path.join(stage, "scripts");
  return {
    name: "scripts-beside",
    setup(build) {
      build.onResolve({ filter: /^\.\.?\// }, ({ path: request, resolveDir }) => {
        const target = path.resolve(resolveDir, request);
        if (!target.startsWith(`${scripts}${path.sep}`)) return undefined;
        return { path: path.relative(path.join(stage, "dist"), target).split(path.sep).join("/"), external: true };
      });
    },
  };
}

// ModRetro's options, unchanged except that the build never writes (the caller does).
function options(stage) {
  return {
    absWorkingDir: stage,
    entryPoints: ["dist/server.js"],
    outfile: "dist/server.js",
    allowOverwrite: true,
    bundle: true,
    platform: "node",
    format: "esm",
    target: "node22",
    write: false,
    metafile: true,
    sourcemap: false,
    // These dependency-free helpers resolve assets relative to their own files. ModRetro's build said this with the
    // pattern `<engine>/scripts/*`; a plugin says it for any folder name (a `*` in the path would be a second
    // wildcard to esbuild).
    plugins: [scriptsBeside(stage)],
    banner: { js: 'import { createRequire as __mcpCreateRequire } from "node:module"; const require = __mcpCreateRequire(import.meta.url);' },
    legalComments: "inline",
    logLevel: "silent",
  };
}

// Refuses a link at where or anywhere under it (the engine's folders hold none).
function noLinks(where) {
  const links = lstatSync(where).isSymbolicLink() ? [where] : [];
  if (!links.length && lstatSync(where).isDirectory()) {
    for (const entry of readdirSync(where, { withFileTypes: true, recursive: true })) {
      if (entry.isSymbolicLink()) links.push(path.join(entry.parentPath, entry.name));
    }
  }
  if (links.length) throw new Error(`the engine's folders hold no links: ${links.join(", ")}`);
}

// Copies keep their folders' modes; a read-only one would stop the build writing its entry or removing the copy.
// Folders are opened before what is in them is listed, so a read-only folder inside a read-only one is reached.
function writable(folder) {
  chmodSync(folder, 0o700);
  for (const entry of readdirSync(folder, { withFileTypes: true })) {
    if (entry.isDirectory() && !entry.isSymbolicLink()) writable(path.join(folder, entry.name));
  }
}

// Each package the bundle includes ({ folder under node_modules/, name, version }): for each input, the nearest
// package.json above it with a name and version (a package's own folders may hold ones without). An input in no
// package is refused.
function bundledPackages(stage, inputs) {
  const found = new Map();
  for (const input of inputs) {
    if (!input.startsWith("node_modules/")) continue;
    let manifest = null;
    let folder = path.dirname(input);
    for (; folder !== "node_modules"; folder = path.dirname(folder)) {
      const file = path.join(stage, folder, "package.json");
      manifest = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : null;
      if (manifest?.name && manifest?.version) break;
    }
    if (folder === "node_modules") throw new Error(`${input} is in no package with a name and version`);
    found.set(folder, { folder, name: manifest.name, version: manifest.version });
  }
  return [...found.values()].sort((a, b) => a.folder.localeCompare(b.folder, "en"));
}

// What the bundle may not be, hold or import, as messages.
function refusals(stage, result, engine) {
  const problems = [];
  const outputs = Object.entries(result.metafile.outputs);
  if (outputs.length !== 1) problems.push(`the build wrote ${outputs.map(([name]) => name).join(", ")}: only dist/server.js is the bundle`);
  const kept = outputs.flatMap(([, output]) => output.imports).filter((found) => found.external && !BUILTINS.has(found.path) && !found.path.startsWith("../scripts/"));
  if (kept.length) problems.push(`the bundle would import packages instead of including them: ${kept.map((found) => found.path).join(", ")}`);
  const inputs = Object.keys(result.metafile.inputs);
  if (inputs.some((input) => input.startsWith("scripts/"))) problems.push("the bundle took in a file from scripts/, which must stay beside it");
  const foreign = inputs.filter((input) => !(input.startsWith("dist/") && !input.includes("/node_modules/")) && !input.startsWith("node_modules/"));
  if (foreign.length) problems.push(`the bundle took in files that are neither the engine's modules nor the pinned packages: ${foreign.join(", ")}`);
  if (problems.length) return { problems, packages: [] };

  const packages = bundledPackages(stage, inputs);
  const locked = JSON.parse(readFileSync(path.join(engine, LOCK), "utf8")).packages;
  const notices = readFileSync(path.join(engine, NOTICES), "utf8");
  for (const { folder, name, version } of packages) {
    const which = `${name}@${version}`;
    if (locked[folder]?.version !== version || !folder.endsWith(`node_modules/${name}`)) {
      problems.push(`${LOCK} does not name ${which}`);
      continue;
    }
    const licence = LICENCE_FILES.map((file) => path.join(stage, folder, file)).find((file) => existsSync(file));
    if (!licence) problems.push(`${which} has no licence file`);
    else if (!notices.includes(`\n## ${which}\n\n${readFileSync(licence, "utf8").trim()}\n`)) problems.push(`${NOTICES} does not carry the licence of ${which}`);
  }
  return { problems, packages };
}

// The bundle's bytes and the packages in it. Throws on anything ModRetro's build refused, on files from anywhere
// but the engine's modules and the pinned packages, and on a package its lock does not name or whose licence the
// engine does not carry.
export async function bundleEngine({ engine = ENGINE, entry, esbuild = loadEsbuild() }) {
  for (const folder of ["dist", "scripts", "package.json"]) noLinks(path.join(engine, folder));
  // Resolved: on macOS the temporary folder is reached through a link, and esbuild matches the resolved paths.
  const stage = made(realpathSync(mkdtempSync(path.join(os.tmpdir(), "hermretro-engine-bundle-"))));
  try {
    cpSync(path.join(engine, "dist"), path.join(stage, "dist"), { recursive: true });
    cpSync(path.join(engine, "scripts"), path.join(stage, "scripts"), { recursive: true });
    // Its "type": "module" makes the modules ES modules in Node's sense, which decides how they import CommonJS.
    cpSync(path.join(engine, "package.json"), path.join(stage, "package.json"));
    const packages = path.join(TOOLS, "node_modules");
    cpSync(packages, path.join(stage, "node_modules"), {
      recursive: true,
      filter: (source) => !NOT_COPIED.has(path.relative(packages, source).split(path.sep)[0]),
    });
    writable(stage);
    cpSync(entry, path.join(stage, "dist", "server.js"));
    const result = await esbuild.build(options(stage));
    const { problems, packages: included } = refusals(stage, result, engine);
    if (problems.length) throw new Error(problems.join("\n"));
    return { contents: Buffer.from(result.outputFiles[0].contents), packages: included, modules: Object.keys(result.metafile.inputs).length };
  } finally {
    removed(stage);
  }
}

function parse(argv) {
  const args = { engine: ENGINE, check: false };
  for (let index = 0; index < argv.length; index++) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--check") args.check = true;
    else if (["--entry", "--engine", "--out"].includes(flag)) {
      if (!value || value.startsWith("--")) throw new Error(`${flag} needs a path`);
      args[flag.slice(2)] = path.resolve(value);
      index++;
    } else throw new Error(`unknown argument ${flag}`);
  }
  if (!args.entry) throw new Error("--entry <file> is required: the server's own module");
  args.out ??= path.join(args.engine, "dist", "server.js");
  return args;
}

// Writes contents beside out, then moves them into its place: a stopped write never leaves half a bundle.
function replace(out, contents) {
  const partial = made(path.join(path.dirname(out), `.${path.basename(out)}.${process.pid}.tmp`));
  try {
    writeFileSync(partial, contents);
    renameSync(partial, out);
  } finally {
    removed(partial);
  }
}

async function main(argv) {
  const args = parse(argv);
  const { contents, packages, modules } = await bundleEngine(args);
  const summary = `${modules} modules, ${packages.length} packages, ${contents.length} bytes`;
  const current = existsSync(args.out) ? readFileSync(args.out) : null;
  const shown = path.relative(process.cwd(), args.out);
  if (args.check) {
    if (current?.equals(contents)) {
      console.log(`${shown} is up to date (${summary})`);
      return 0;
    }
    console.error(`${shown} is not what its modules build (${summary})`);
    console.error("FIX: node tools/engine/bundle.mjs with the same arguments, then commit the bundle with its modules (never edit it by hand)");
    return 1;
  }
  if (!current?.equals(contents)) replace(args.out, contents);
  console.log(`${current?.equals(contents) ? "unchanged" : "wrote"} ${shown} (${summary})`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    if (error.message === MISSING) console.error("FIX: python tools/dev setup");
    process.exitCode = 1;
  }
}
