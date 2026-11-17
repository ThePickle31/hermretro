// Resolves the page's import aliases (#sdk, #app/, #pages/, #shared/, #frame/; tools/bundle/bundle.mjs) for a
// test that imports page/ modules directly in Node rather than through the bundle:
//   import { register } from 'node:module'
//   register('./aliases.mjs', import.meta.url)
// then import the modules with import() (static imports would load before the hook is in place).
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { ALIASES } from '../../tools/bundle/bundle.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

export function resolve(specifier, context, next) {
  for (const [alias, target] of Object.entries(ALIASES)) {
    if (specifier === alias || specifier.startsWith(`${alias}/`)) {
      return next(pathToFileURL(path.join(root, target, specifier.slice(alias.length))).href, context)
    }
  }

  return next(specifier, context)
}
