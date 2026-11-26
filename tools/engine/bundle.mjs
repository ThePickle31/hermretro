// Build the engine's server bundle (dist/server.js) from its modules, the way ModRetro built it
// (scripts/bundle-mcp.mjs): one ESM file for Node 22 holding every dist/ module and the packages they import, with
// scripts/ left as imports beside it, built by the esbuild and packages pinned in tools/engine/npm.
//
//   node tools/engine/bundle.mjs --entry <file> [--engine <folder>] [--out <file>]   build (writes when bytes change)
//   node tools/engine/bundle.mjs --entry <file> [--engine <folder>] --check          verify the bundle; writes nothing
//
// --entry is the server's own module, built in as dist/server.js, the name the bundle has always given it.
// --engine defaults to engine/modretro-chromatic and --out to the engine's dist/server.js. The build runs in a
// temporary copy of the engine's dist/, scripts/ and package.json with the pinned packages as its node_modules, so the bundle's
// module comments read as they always have (`// dist/emulator.js`, `// node_modules/zod/...`).

import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { builtinModules, createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const TOOLS = path.join(ROOT, "tools", "engine", "npm");
export const ENGINE = path.join(ROOT, "engine", "modretro-chromatic");
export const MISSING = "esbuild and the engine's packages were not found (npm ci --prefix tools/engine/npm --ignore-scripts)";
// Every bundled package needs its licence here (each as a `## <name>@<version>` section).
const LICENCES = path.join("licenses", "bundled-javascript.txt");
const BUILTINS = new Set(builtinModules.flatMap((name) => [name, `node:${name}`]));

export function loadEsbuild() {
  if (!existsSync(path.join(TOOLS, "node_modules", "esbuild", "package.json"))) throw new Error(MISSING);
  return createRequire(path.join(TOOLS, "package.json"))("esbuild");
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
    // These dependency-free helpers resolve assets relative to their own files.
    external: [path.join(stage, "scripts", "*")],
    banner: { js: 'import { createRequire as __mcpCreateRequire } from "node:module"; const require = __mcpCreateRequire(import.meta.url);' },
    legalComments: "inline",
    logLevel: "silent",
    // node_modules is a link to the pinned packages; keep the paths under it as they are.
    preserveSymlinks: true,
  };
}

// The name@version of each package the bundle includes, from the nearest package.json above each input.
function bundledPackages(stage, inputs) {
  const found = new Set();
  for (const input of inputs) {
    if (!input.startsWith("node_modules/")) continue;
    for (let folder = path.dirname(path.join(stage, input)); folder !== stage; folder = path.dirname(folder)) {
      const manifest = path.join(folder, "package.json");
      if (!existsSync(manifest)) continue;
      const { name, version } = JSON.parse(readFileSync(manifest, "utf8"));
      if (name && version) {
        found.add(`${name}@${version}`);
        break;
      }
    }
  }
  return [...found].sort();
}

// The bundle's bytes and the packages in it. Throws on anything ModRetro's build refused, and on a package
// without its licence in the engine.
export function bundleEngine({ engine = ENGINE, entry, esbuild = loadEsbuild() }) {
  const stage = mkdtempSync(path.join(os.tmpdir(), "hermretro-engine-bundle-"));
  try {
    cpSync(path.join(engine, "dist"), path.join(stage, "dist"), { recursive: true });
    cpSync(path.join(engine, "scripts"), path.join(stage, "scripts"), { recursive: true });
    // Its "type": "module" makes the modules ES modules in Node's sense, which decides how they import CommonJS.
    cpSync(path.join(engine, "package.json"), path.join(stage, "package.json"));
    cpSync(entry, path.join(stage, "dist", "server.js"));
    symlinkSync(path.join(TOOLS, "node_modules"), path.join(stage, "node_modules"), "dir");
    const result = esbuild.buildSync(options(stage));
    const [output] = Object.values(result.metafile.outputs);
    const kept = output.imports.filter((found) => found.external && !BUILTINS.has(found.path) && !found.path.startsWith("../scripts/"));
    if (kept.length) throw new Error(`the bundle would import packages instead of including them: ${kept.map((found) => found.path).join(", ")}`);
    const inputs = Object.keys(result.metafile.inputs);
    if (inputs.some((input) => input.startsWith("scripts/"))) throw new Error("the bundle took in a file from scripts/, which must stay beside it");
    const packages = bundledPackages(stage, inputs);
    const licences = readFileSync(path.join(engine, LICENCES), "utf8");
    const unlicensed = packages.filter((name) => !licences.includes(`\n## ${name}\n`));
    if (unlicensed.length) throw new Error(`${LICENCES} has no licence for ${unlicensed.join(", ")}`);
    return { contents: Buffer.from(result.outputFiles[0].contents), packages, modules: inputs.length };
  } finally {
    rmSync(stage, { recursive: true, force: true });
  }
}

function parse(argv) {
  const args = { engine: ENGINE, check: false };
  for (let index = 0; index < argv.length; index++) {
    const flag = argv[index];
    if (flag === "--check") args.check = true;
    else if (["--entry", "--engine", "--out"].includes(flag) && argv[index + 1]) args[flag.slice(2)] = path.resolve(argv[++index]);
    else throw new Error(`unknown argument ${flag}`);
  }
  if (!args.entry) throw new Error("--entry <file> is required: the server's own module");
  args.out ??= path.join(args.engine, "dist", "server.js");
  return args;
}

function main(argv) {
  const args = parse(argv);
  const { contents, packages, modules } = bundleEngine(args);
  const summary = `${modules} modules, ${packages.length} packages, ${contents.length} bytes`;
  const current = existsSync(args.out) ? readFileSync(args.out) : null;
  if (args.check) {
    if (current?.equals(contents)) {
      console.log(`${path.relative(process.cwd(), args.out)} is up to date (${summary})`);
      return 0;
    }
    console.error(`${path.relative(process.cwd(), args.out)} is not what its modules build (${summary})`);
    console.error("FIX: node tools/engine/bundle.mjs with the same arguments, then commit the bundle with its modules (never edit it by hand)");
    return 1;
  }
  if (!current?.equals(contents)) writeFileSync(args.out, contents);
  console.log(`${current?.equals(contents) ? "unchanged" : "wrote"} ${path.relative(process.cwd(), args.out)} (${summary})`);
  return 0;
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
