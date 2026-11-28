/**
 * Where the development packages (esbuild, TypeScript, jsdom, React) come from. The plugin itself has no
 * npm dependencies; only building the page and testing it need these. First match wins:
 *   1. $HERMES_DESKTOP_NODE_MODULES, a node_modules folder;
 *   2. $HERMES_DESKTOP_DIR/node_modules, apps/desktop of a Hermes checkout;
 *   3. tools/npm/node_modules, the versions pinned for this repository (npm ci --prefix tools/npm --ignore-scripts);
 *   4. ~/.hermes/hermes-agent/apps/desktop/node_modules, the Hermes Desktop install on this machine.
 */
import { existsSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// The versions this repository pins (npm ci --prefix tools/npm --ignore-scripts).
export const PINNED_MODULES = path.join(ROOT, 'tools', 'npm', 'node_modules')

export function candidateModules() {
  const env = process.env

  return [
    env.HERMES_DESKTOP_NODE_MODULES,
    env.HERMES_DESKTOP_DIR && path.join(env.HERMES_DESKTOP_DIR, 'node_modules'),
    PINNED_MODULES,
    path.join(os.homedir(), '.hermes', 'hermes-agent', 'apps', 'desktop', 'node_modules')
  ].filter(Boolean)
}

/** The first node_modules folder (of `folders`, by default every candidate) that holds every one of `packages`, or null. */
export function findModules(packages, folders = candidateModules()) {
  return folders.find(dir => packages.every(name => existsSync(path.join(dir, name, 'package.json')))) ?? null
}

export const MISSING_HINT = 'run: npm ci --prefix tools/npm --ignore-scripts  (or set HERMES_DESKTOP_DIR to apps/desktop of a Hermes checkout)'
