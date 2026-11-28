// Where the engine's own files are, for every module wherever it sits. This file stays at the top of src/: in the
// tests a module runs from src/ (or a folder in it), and in production every module runs from dist/server.js, so a
// path worked out from a module's own location (import.meta.url) is right in only one of the two once it moves into a
// folder. Here both are one folder below engine/, so these resolve the same in both.
import path from "node:path";
import { fileURLToPath } from "node:url";

const ENGINE_URL = new URL("../", import.meta.url);

/** The engine folder (engine/), without a trailing separator. */
export const ENGINE_ROOT = path.resolve(fileURLToPath(ENGINE_URL));

/** A URL inside the engine folder: `relative` as a URL path from engine/ (a trailing "/" names a folder). */
export function engineUrl(relative) {
  return new URL(relative, ENGINE_URL);
}

/** The file path of `engineUrl(relative)`. */
export function enginePath(relative) {
  return fileURLToPath(engineUrl(relative));
}
