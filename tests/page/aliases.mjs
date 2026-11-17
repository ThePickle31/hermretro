// Resolves the page's import aliases (#sdk, #app/, #pages/, #shared/, #frame/; tools/bundle/bundle.mjs) for a
// test that imports page/ modules directly in Node rather than through the bundle:
//   import { register } from 'node:module'
//   register('./aliases.mjs', import.meta.url)
// then import the modules with import() (static imports would load before the hook is in place).
// It also gives those modules what the bundle leaves to the app: '@hermes/plugin-sdk' is the stand-in in
// sdk-stub.mjs, and react, react-dom and jsdom come from tools/bundle/node-modules.mjs's folder (one copy
// each, shared by the test and the page).
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { ALIASES } from '../../tools/bundle/bundle.mjs'
import { findModules } from '../../tools/bundle/node-modules.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')
const PACKAGES = /^(react|react-dom|jsdom)(\/.*)?$/
let packages = null

export function resolve(specifier, context, next) {
  for (const [alias, target] of Object.entries(ALIASES)) {
    if (specifier === alias || specifier.startsWith(`${alias}/`)) {
      return next(pathToFileURL(path.join(root, target, specifier.slice(alias.length))).href, context)
    }
  }

  if (specifier === '@hermes/plugin-sdk') {
    return next(pathToFileURL(path.join(here, 'sdk-stub.mjs')).href, context)
  }

  if (PACKAGES.test(specifier)) {
    const modules = findModules(['react', 'react-dom', 'jsdom'])

    if (modules) {
      packages ??= createRequire(path.join(modules, 'package.json'))

      return next(pathToFileURL(packages.resolve(specifier)).href, context)
    }
  }

  return next(specifier, context)
}
