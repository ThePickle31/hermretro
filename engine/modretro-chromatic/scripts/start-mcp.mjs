#!/usr/bin/env node

/**
 * Start the engine's MCP server from a prepared runtime: this package's own, an intentionally linked one, or an
 * explicitly configured checkout (GB_STUDIO_RUNTIME_ROOT). Keep this script dependency-free: it runs before anything
 * the runtime installs.
 */

import { spawn } from "node:child_process";
import {
  closeSync, constants, existsSync, fstatSync, lstatSync, openSync, readSync,
  realpathSync, statSync, readFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromaticTargetFromManifest, chromaticFormatFromManifest, requireChromaticHostTarget } from "./chromatic-runtime.mjs";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageManifestBytes = 1024 * 1024;
const packagedSetupGuidance = "From a trusted compiled package, use scripts/setup.sh (macOS/Linux) or scripts/setup.ps1 (Windows) to run doctor, then plan with a new owned --root. Only explicitly authorized apply may prepare a replacement; plugin installation and activation remain separate.";
const unsafeLauncherVariables = new Set([
  "BASH_ENV",
  "ENV",
  "NODE_OPTIONS",
  "NODE_PATH",
  "PYTHONHOME",
  "PYTHONPATH",
  "PYTHONSTARTUP",
  "PYTHONUSERBASE",
  "PYTHONWARNINGS",
  "UV_CONFIG_FILE",
  "UV_ENV_FILE",
  "UV_PROJECT",
  "UV_PROJECT_ENVIRONMENT",
  "UV_PYTHON",
  "UV_PYTHON_INSTALL_DIR",
  "UV_PYTHON_PREFERENCE",
  "UV_WORKING_DIR",
  "VIRTUAL_ENV",
]);

function readEnvironment(environment, name, platform) {
  if (platform !== "win32") return environment[name];
  const target = name.toUpperCase();
  let value;
  let found = false;

  for (const [key, candidate] of Object.entries(environment)) {
    if (key.toUpperCase() !== target) continue;
    if (found && candidate !== value) {
      throw new Error(`Conflicting case-insensitive Windows environment values exist for ${name}.`);
    }
    found = true;
    value = candidate;
  }
  return value;
}

function deleteEnvironmentAliases(environment, name, platform) {
  if (platform !== "win32") {
    delete environment[name];
    return;
  }
  const normalized = name.toUpperCase();
  for (const key of Object.keys(environment)) {
    if (key.toUpperCase() === normalized) delete environment[key];
  }
}

/** Select only signals that are actually supported by the current platform. */
export function mcpLauncherSignals(platform = process.platform) {
  return platform === "win32"
    ? ["SIGINT", "SIGTERM"]
    : ["SIGINT", "SIGTERM", "SIGHUP"];
}

/** Preserve enterprise registry/CA settings without inheriting executable hooks. */
export function prepareMcpLauncherEnvironment({
  environment = process.env,
  platform = process.platform,
  runtimeRoot,
  pluginRoot = packageRoot,
  defaultToolchainRoot,
  workingDirectory = process.cwd(),
}) {
  const childEnvironment = {};
  const seen = new Map();

  for (const [key, value] of Object.entries(environment)) {
    const normalized = platform === "win32" ? key.toUpperCase() : key;
    if (unsafeLauncherVariables.has(normalized)) continue;

    if (platform === "win32") {
      const previous = seen.get(normalized);
      if (previous !== undefined) {
        if (previous.value !== value) {
          throw new Error(`Conflicting case-insensitive Windows environment values exist for ${key}.`);
        }
        continue;
      }
      seen.set(normalized, { value });
    }
    childEnvironment[key] = value;
  }

  for (const name of ["GB_STUDIO_RUNTIME_ROOT", "GB_STUDIO_TOOLCHAIN_ROOT", "GB_STUDIO_PLUGIN_ROOT"]) {
    deleteEnvironmentAliases(childEnvironment, name, platform);
  }
  childEnvironment.GB_STUDIO_RUNTIME_ROOT = runtimeRoot;
  childEnvironment.GB_STUDIO_PLUGIN_ROOT = pluginRoot;

  const configuredToolchain = readEnvironment(environment, "GB_STUDIO_TOOLCHAIN_ROOT", platform)?.trim();
  childEnvironment.GB_STUDIO_TOOLCHAIN_ROOT = configuredToolchain
    ? path.resolve(workingDirectory, configuredToolchain)
    : defaultToolchainRoot;

  // The host replaces cwd before launching cached plugins. Only explicitly
  // configured roots can authorize a workspace; the runtime checkout never can.
  for (const variable of ["GB_STUDIO_WORKSPACE_ROOT", "GB_STUDIO_PROJECT_ROOT"]) {
    const configuredRoot = readEnvironment(environment, variable, platform)?.trim();
    deleteEnvironmentAliases(childEnvironment, variable, platform);
    if (configuredRoot) {
      childEnvironment[variable] = path.resolve(workingDirectory, configuredRoot);
    }
  }

  return childEnvironment;
}

function resolvePreparedRuntime(candidate) {
  const candidateServerPath = path.join(candidate, "dist", "server.js");

  try {
    if (!statSync(candidateServerPath).isFile()) {
      return undefined;
    }

    // A cached plugin can intentionally link dist/ to a prepared checkout.
    // Node resolves imports from the real server location, so validate the SDK
    // beside that exact runtime instead of borrowing an unrelated installation.
    const serverPath = realpathSync(candidateServerPath);
    const runtimeRoot = realpathSync(path.resolve(path.dirname(serverPath), ".."));
    const manifestPath = path.join(runtimeRoot, "package.json");
    if (existsSync(manifestPath) && JSON.parse(readFileSync(manifestPath, "utf8")).bundledMcp === true) {
      return { runtimeRoot, serverPath };
    }
    const sdkPath = path.join(runtimeRoot, "node_modules", "@modelcontextprotocol", "sdk");
    if (!statSync(sdkPath).isDirectory()) {
      return undefined;
    }
    const resolvedSdk = realpathSync(sdkPath);
    const relativeSdk = path.relative(runtimeRoot, resolvedSdk);
    if (
      relativeSdk === ".." ||
      relativeSdk.startsWith(`..${path.sep}`) ||
      path.isAbsolute(relativeSdk)
    ) {
      return undefined;
    }

    return { runtimeRoot, serverPath };
  } catch {
    return undefined;
  }
}

function canonicalPathKey(candidate) {
  const resolved = path.resolve(candidate);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function safePackagePath(relative) {
  if (
    typeof relative !== "string" || !relative || relative.length > 1024 ||
    /[\\\\:<>"|?*\u0000-\u001f]/u.test(relative) ||
    path.posix.isAbsolute(relative) || path.win32.isAbsolute(relative)
  ) throw new Error("The package contains an unsafe relative path.");
  const components = relative.split("/");
  if (components.length > 32 || components.some((part) =>
    !part || part === "." || part === ".." || /[. ]$/u.test(part) ||
    /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/iu.test(part)
  )) throw new Error("The package contains an unsafe relative path.");
  return components;
}

/** Reject links and junctions inside an already canonical, explicitly selected root. */
function unlinkedPackageMember(root, relative) {
  const components = safePackagePath(relative);
  let selected = root;
  let metadata;
  for (let index = 0; index < components.length; index++) {
    selected = path.join(selected, components[index]);
    metadata = lstatSync(selected);
    if (
      metadata.isSymbolicLink() ||
      canonicalPathKey(realpathSync(selected)) !== canonicalPathKey(selected)
    ) throw new Error(`The package member traverses a link or junction: ${relative}`);
    if (index < components.length - 1 && !metadata.isDirectory()) {
      throw new Error(`The package member has a non-directory parent: ${relative}`);
    }
  }
  return { selected, metadata };
}

function sameFile(left, right) {
  return left.dev === right.dev && left.ino === right.ino && left.size === right.size &&
    left.mtimeMs === right.mtimeMs && left.ctimeMs === right.ctimeMs;
}

/** Read a bounded regular file without following a link or a replaced leaf, or allocating past its limit. */
function readPackageFile(root, relative, limit) {
  const { selected, metadata: before } = unlinkedPackageMember(root, relative);
  if (!before.isFile() || before.size > limit) {
    throw new Error(`The package member is not a bounded regular file: ${relative}`);
  }
  const descriptor = openSync(selected, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
  try {
    const opened = fstatSync(descriptor);
    if (!opened.isFile() || !sameFile(before, opened)) {
      throw new Error(`The package member changed while opening it: ${relative}`);
    }
    const buffer = Buffer.allocUnsafe(Math.min(64 * 1024, Math.max(1, before.size + 1)));
    const chunks = [];
    let size = 0;
    for (;;) {
      const count = readSync(descriptor, buffer, 0, Math.min(buffer.length, limit - size + 1), null);
      if (count === 0) break;
      size += count;
      if (size > limit || size > before.size) {
        throw new Error(`The package member grew while reading it: ${relative}`);
      }
      chunks.push(Buffer.from(buffer.subarray(0, count)));
    }
    const after = fstatSync(descriptor);
    const current = unlinkedPackageMember(root, relative).metadata;
    if (size !== before.size || !sameFile(opened, after) || !sameFile(after, current)) {
      throw new Error(`The package member changed while reading it: ${relative}`);
    }
    return Buffer.concat(chunks, size);
  } finally {
    closeSync(descriptor);
  }
}

function packageJson(contents, label) {
  let parsed;
  try { parsed = JSON.parse(contents.toString("utf8")); }
  catch { throw new Error(`The ${label} is not valid JSON.`); }
  if (!isObject(parsed)) throw new Error(`The ${label} must be a JSON object.`);
  return parsed;
}

function verifyLauncherPlatform(root) {
  const selected = realpathSync(root);
  try { lstatSync(path.join(selected, "package.json")); }
  catch (error) {
    // A launcher with no package manifest has no platform to check.
    if (error.code === "ENOENT") return;
    throw error;
  }
  const manifest = packageJson(readPackageFile(selected, "package.json", packageManifestBytes), "launcher package manifest");
  requireChromaticHostTarget(chromaticTargetFromManifest(manifest));
  chromaticFormatFromManifest(manifest);
}

function startMcpLauncher() {
  verifyLauncherPlatform(packageRoot);
  const platform = process.platform;
  const requestedRuntimeRoot = readEnvironment(process.env, "GB_STUDIO_RUNTIME_ROOT", platform)?.trim();
  const candidateRoot = path.resolve(requestedRuntimeRoot || packageRoot);
  const preparedRuntime = resolvePreparedRuntime(candidateRoot);

  if (!preparedRuntime) {
    const selection = requestedRuntimeRoot
      ? "the explicitly configured runtime"
      : "this installed plugin";
    console.error(
      `ModRetro Chromatic MCP could not find a prepared runtime for ${selection}. ` +
        `${packagedSetupGuidance} ` +
        `Inspected: ${candidateRoot}`,
    );
    process.exitCode = 1;
    return;
  }

  const { runtimeRoot, serverPath } = preparedRuntime;
  verifyLauncherPlatform(runtimeRoot);
  const localToolchainPath = path.join(runtimeRoot, ".local");
  const bundled = existsSync(path.join(runtimeRoot, "package.json")) && JSON.parse(readFileSync(path.join(runtimeRoot, "package.json"), "utf8")).bundledMcp === true;
  const home = readEnvironment(process.env, platform === "win32" ? "USERPROFILE" : "HOME", platform) || os.homedir();
  const dataRoot = platform === "darwin" ? path.join(home, "Library", "Application Support")
    : platform === "win32" ? readEnvironment(process.env, "LOCALAPPDATA", platform) || path.join(home, "AppData", "Local")
      : readEnvironment(process.env, "XDG_DATA_HOME", platform) || path.join(home, ".local", "share");
  const setupRoot = readEnvironment(process.env, "GB_STUDIO_SETUP_ROOT", platform) || path.join(dataRoot, "modretro-chromatic");
  if (!path.isAbsolute(setupRoot)) throw new Error("The dependency setup root must be absolute.");
  let defaultToolchainRoot = bundled ? path.join(setupRoot, "toolchain") : runtimeRoot;
  if (existsSync(localToolchainPath)) {
    const resolvedLocal = realpathSync(localToolchainPath);
    if (!statSync(resolvedLocal).isDirectory() || path.basename(resolvedLocal).toLowerCase() !== ".local") {
      throw new Error("The trusted local game toolchain must resolve to a real .local directory.");
    }
    defaultToolchainRoot = path.dirname(resolvedLocal);
  }

  const childEnvironment = prepareMcpLauncherEnvironment({
    environment: process.env,
    platform,
    runtimeRoot,
    pluginRoot: realpathSync(packageRoot),
    defaultToolchainRoot,
  });
  const child = spawn(process.execPath, [serverPath, ...process.argv.slice(2)], {
    cwd: runtimeRoot,
    env: childEnvironment,
    stdio: "inherit",
    shell: false,
    windowsHide: true,
  });

  const forwardSignal = (signal) => {
    if (!child.killed && child.exitCode === null) {
      child.kill(signal);
    }
  };
  const cleanupChild = () => forwardSignal("SIGTERM");
  const handlers = new Map();
  for (const signal of mcpLauncherSignals(platform)) {
    const handler = () => forwardSignal(signal);
    handlers.set(signal, handler);
    process.on(signal, handler);
  }
  process.once("exit", cleanupChild);

  const removeHandlers = () => {
    for (const [signal, handler] of handlers) process.removeListener(signal, handler);
    process.removeListener("exit", cleanupChild);
  };

  child.once("error", (error) => {
    removeHandlers();
    console.error(`ModRetro Chromatic MCP could not start ${serverPath}: ${error.message}`);
    process.exitCode = 1;
  });

  child.once("exit", (code, signal) => {
    removeHandlers();
    if (code !== null) {
      process.exitCode = code;
    } else {
      const signalCode = signal === null ? 0 : os.constants.signals[signal] || 0;
      process.exitCode = 128 + signalCode;
    }
  });
}

const invokedEntrypoint = process.argv[1];
if (
  invokedEntrypoint &&
  realpathSync(fileURLToPath(import.meta.url)) === realpathSync(path.resolve(invokedEntrypoint))
) {
  try {
    startMcpLauncher();
  } catch (error) {
    console.error(`ModRetro Chromatic MCP could not start safely: ${error.message}`);
    process.exitCode = 1;
  }
}
