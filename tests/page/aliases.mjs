// Resolves the page's import aliases (#sdk, #app/, #pages/, #shared/, #frame/; tools/bundle/bundle.mjs) for a
// test that imports page/ modules directly in Node rather than through the bundle:
//   import { registerAliases } from './aliases.mjs'
//   registerAliases()
// then import the modules with import() (static imports would load before the hook is in place).
// registerAliases uses module.registerHooks (in-thread, synchronous) where Node has it, and falls back to
// module.register (deprecated since Node 26, DEP0205) on older Node.
// It also gives those modules what the bundle leaves to the app: '@hermes/plugin-sdk' is the stand-in in
// sdk-stub.mjs, and react, react-dom and jsdom come from tools/bundle/node-modules.mjs's folder (one copy
// each, shared by the test and the page). A PNG import becomes its data URL, as the bundle makes it.
import { readFileSync } from 'node:fs'
import module, { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { ALIASES } from '../../tools/bundle/bundle.mjs'
import { findModules } from '../../tools/bundle/node-modules.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')
const PACKAGES = /^(react|react-dom|jsdom)(\/.*)?$/
let packages = null
let inside = false

export function resolve(specifier, context, next) {
  for (const [alias, target] of Object.entries(ALIASES)) {
    if (specifier === alias || specifier.startsWith(`${alias}/`)) {
      return next(pathToFileURL(path.join(root, target, specifier.slice(alias.length))).href, context)
    }
  }

  if (specifier === '@hermes/plugin-sdk') {
    return next(pathToFileURL(path.join(here, 'sdk-stub.mjs')).href, context)
  }

  // registerHooks' hooks also see require.resolve's own lookups: let those through untouched.
  if (PACKAGES.test(specifier) && !inside) {
    const modules = findModules(['react', 'react-dom', 'jsdom'])

    if (modules) {
      packages ??= createRequire(path.join(modules, 'package.json'))

      inside = true
      try {
        // Answered here, not through next(): CommonJS require calls (react-dom's) pass through these hooks too.
        return { url: pathToFileURL(packages.resolve(specifier)).href, shortCircuit: true }
      } finally {
        inside = false
      }
    }
  }

  return next(specifier, context)
}

// `import art from './art.png'` (page/shared/art/index.js): the bundle inlines it as a data URL; so does this.
export function load(url, context, next) {
  if (url.startsWith('file:') && url.endsWith('.png')) {
    const data = readFileSync(fileURLToPath(url)).toString('base64')

    return { format: 'module', source: `export default 'data:image/png;base64,${data}'`, shortCircuit: true }
  }

  return next(url, context)
}

// Puts resolve() and load() in place for this process: before any import() of a page module.
export function registerAliases() {
  if (typeof module.registerHooks === 'function') {
    module.registerHooks({ resolve, load })
  } else {
    module.register(import.meta.url)
  }
}
