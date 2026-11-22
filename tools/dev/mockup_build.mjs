// Builds the page with mockups in it, for the sandbox:
//   node tools/dev/mockup_build.mjs <round folder> <out file>
// The round folder holds `round.json` ({"replaces": "page/pages/build/build-page.js", "exports": ["BuildPage"], ...})
// and `mockups/*.jsx`, each exporting a `title` and the same components as the module it replaces. The output is the
// whole page (page/index.js, as tools/bundle/bundle.mjs builds it) where that module is a switch: it shows today's
// version or a mockup, picked by the plugin storage key `mockup` and changed live by a `hermretro-mockup` window event
// (its detail is the mockup's id). A mockup imports anything of the page through the usual aliases (#sdk, #app/,
// #pages/, #shared/), and today's version of the module it replaces as `#original`.
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { ALIASES, artDataUrl, EXTERNAL } from '../bundle/bundle.mjs'
import { findModules, MISSING_HINT } from '../bundle/node-modules.mjs'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const [roundDir, out] = process.argv.slice(2).map(item => path.resolve(item))
const round = JSON.parse(readFileSync(path.join(roundDir, 'round.json'), 'utf8'))
const replaced = path.join(ROOT, round.replaces)
const names = round.exports
const files = readdirSync(path.join(roundDir, 'mockups')).filter(name => /\.(jsx|js)$/.test(name)).sort()
const modules = findModules(['esbuild'])

if (!modules) {
  console.error(`esbuild was not found\n${MISSING_HINT}`)
  process.exit(1)
}

const esbuild = createRequire(path.join(modules, 'noop.js'))('esbuild')
const id = file => file.replace(/\.(jsx|js)$/, '')

// The switch that stands in for the replaced module.
const switcher = `
import { jsx, useEffect, useState } from '#sdk'
import * as original from '#original'
${files.map((file, index) => `import * as m${index} from ${JSON.stringify(path.join(roundDir, 'mockups', file))}`).join('\n')}
const VARIANTS = { current: original, ${files.map((file, index) => `${JSON.stringify(id(file))}: m${index}`).join(', ')} }
const KEY = 'hermes.plugin.hermretro.mockup'
const stored = () => { try { return JSON.parse(localStorage.getItem(KEY)) } catch { return null } }
function useVariant() {
  const [chosen, choose] = useState(stored)
  useEffect(() => {
    const change = event => choose(event.detail)
    window.addEventListener('hermretro-mockup', change)
    return () => window.removeEventListener('hermretro-mockup', change)
  }, [])
  return VARIANTS[chosen] ?? original
}
${names.map(name => `export function ${name}(props) {\n  const variant = useVariant()\n  return jsx(variant.${name} ?? original.${name}, props, ${JSON.stringify(name)} + (variant === original ? '' : ':m'))\n}`).join('\n')}
export const MOCKUPS = ${JSON.stringify(files.map(id))}
`

const mockupSwitch = {
  name: 'mockup-switch',
  setup(build) {
    build.onResolve({ filter: /^#original$/ }, () => ({ path: replaced }))
    // Every import of the replaced module, from anywhere in the page, gets the switch instead.
    build.onResolve({ filter: /.*/ }, args => {
      if (args.namespace === 'mockup' || !args.path.startsWith('.')) return undefined
      return path.resolve(args.resolveDir, args.path) === replaced ? { path: 'switch', namespace: 'mockup' } : undefined
    })
    build.onLoad({ filter: /.*/, namespace: 'mockup' }, () => ({ contents: switcher, loader: 'js', resolveDir: ROOT }))
  }
}

const result = await esbuild.build({
  absWorkingDir: ROOT,
  entryPoints: [path.join(ROOT, 'page', 'index.js')],
  bundle: true,
  format: 'esm',
  external: EXTERNAL,
  platform: 'browser',
  target: 'esnext',
  charset: 'utf8',
  write: false,
  logLevel: 'warning',
  jsx: 'automatic',
  loader: { '.jsx': 'jsx' },
  alias: Object.fromEntries(Object.entries(ALIASES).map(([alias, target]) => [alias, `./${target}`])),
  plugins: [mockupSwitch, artDataUrl]
})

writeFileSync(out, result.outputFiles[0].text)
console.log(JSON.stringify({ mockups: files.map(id), out }))
