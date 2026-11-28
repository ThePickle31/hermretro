// The engine's packages (zod, pngjs, the MCP SDK) for its tests. The engine's modules import them by name, and in
// this repository they are installed only in tools/engine/npm, where tools/engine/bundle.mjs bundles them from: a bare
// name a module under engine/ (or a test here) imports resolves from there, so a test loads the engine's source modules
// as they are, with the very packages the bundle holds.
const FROM = [new URL("../../engine/", import.meta.url).href, new URL("./", import.meta.url).href];
const TOOLS = new URL("../../tools/engine/npm/package.json", import.meta.url).href;
const BARE = /^(?![a-z][a-z0-9+.-]*:)(?![./])/i; // not node:, file: or another scheme, and not a path

// Synchronous, as module.registerHooks needs; module.register's asynchronous chain takes it too.
export function resolve(specifier, context, nextResolve) {
  if (BARE.test(specifier) && FROM.some((folder) => context.parentURL?.startsWith(folder))) {
    return nextResolve(specifier, { ...context, parentURL: TOOLS });
  }
  return nextResolve(specifier, context);
}
