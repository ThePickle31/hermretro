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
// modules and the pinned packages, each package with its licence in the engine.

import { cpSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { builtinModules, createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const TOOLS = path.join(ROOT, "tools", "engine", "npm");
export const ENGINE = path.join(ROOT, "engine", "modretro-chromatic");
export const MISSING = "esbuild and the engine's packages were not found (npm ci --prefix tools/engine/npm --ignore-scripts)";
// Every bundled package needs its licence here (each as a `## <name>@<version>` section).
const LICENCES = path.join("licenses", "bundled-javascript.txt");
const BUILTINS = new Set(builtinModules.flatMap((name) => [name, `node:${name}`]));
// The build's own tools, which the bundle never includes.
const NOT_COPIED = new Set([".bin", "esbuild", "@esbuild"]);

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

// Anything the bundle may not hold or import, as messages.
function refusals(result) {
  const [output] = Object.values(result.metafile.outputs);
  const inputs = Object.keys(result.metafile.inputs);
  const problems = [];
  const kept = output.imports.filter((found) => found.external && !BUILTINS.has(found.path) && !found.path.startsWith("../scripts/"));
  if (kept.length) problems.push(`the bundle would import packages instead of including them: ${kept.map((found) => found.path).join(", ")}`);
  if (inputs.some((input) => input.startsWith("scripts/"))) problems.push("the bundle took in a file from scripts/, which must stay beside it");
  const foreign = inputs.filter((input) => !(input.startsWith("dist/") && !input.includes("/node_modules/")) && !input.startsWith("node_modules/"));
  if (foreign.length) problems.push(`the bundle took in files that are neither the engine's modules nor the pinned packages: ${foreign.join(", ")}`);
  return problems;
}

// The temporary folder the build runs in, removed when the process is stopped before the build removes it.
function stageFolder() {
  // Resolved: on macOS the temporary folder is reached through a link, and esbuild matches the resolved paths.
  const stage = realpathSync(mkdtempSync(path.join(os.tmpdir(), "hermretro-engine-bundle-")));
  const remove = () => rmSync(stage, { recursive: true, force: true });
  const stop = (signal) => {
    remove();
    process.kill(process.pid, signal);
  };
  process.once("SIGINT", stop).once("SIGTERM", stop);
  return {
    stage,
    done: () => {
      process.off("SIGINT", stop).off("SIGTERM", stop);
      remove();
    },
  };
}

// The bundle's bytes and the packages in it. Throws on anything ModRetro's build refused, on files from anywhere
// but the engine's modules and the pinned packages, and on a package without its licence in the engine.
export async function bundleEngine({ engine = ENGINE, entry, esbuild = loadEsbuild() }) {
  const { stage, done } = stageFolder();
  try {
    // A link stays a link, relative to where it is, so a module reached through one is still one module.
    cpSync(path.join(engine, "dist"), path.join(stage, "dist"), { recursive: true, verbatimSymlinks: true });
    cpSync(path.join(engine, "scripts"), path.join(stage, "scripts"), { recursive: true, verbatimSymlinks: true });
    // Its "type": "module" makes the modules ES modules in Node's sense, which decides how they import CommonJS.
    cpSync(path.join(engine, "package.json"), path.join(stage, "package.json"));
    cpSync(entry, path.join(stage, "dist", "server.js"));
    const packages = path.join(TOOLS, "node_modules");
    cpSync(packages, path.join(stage, "node_modules"), {
      recursive: true,
      filter: (source) => !NOT_COPIED.has(path.relative(packages, source).split(path.sep)[0]),
    });
    const result = await esbuild.build(options(stage));
    const problems = refusals(result);
    if (problems.length) throw new Error(problems.join("\n"));
    const inputs = Object.keys(result.metafile.inputs);
    const included = bundledPackages(stage, inputs);
    const licences = readFileSync(path.join(engine, LICENCES), "utf8");
    const unlicensed = included.filter((name) => !licences.includes(`\n## ${name}\n`));
    if (unlicensed.length) throw new Error(`${LICENCES} has no licence for ${unlicensed.join(", ")}`);
    return { contents: Buffer.from(result.outputFiles[0].contents), packages: included, modules: inputs.length };
  } finally {
    done();
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
  if (!current?.equals(contents)) writeFileSync(args.out, contents);
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
