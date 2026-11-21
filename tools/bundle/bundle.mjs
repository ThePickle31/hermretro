/**
 * Builds the plugin's two generated scripts from the modules in page/:
 *   - desktop/plugin.js       the one file Hermes Desktop loads (entry page/index.js);
 *   - player/frame-shim.js    the script the player frame runs first (entry page/frame/index.js),
 *                             inlined into the frame page by the player backend (backend/player/).
 *
 *   node tools/bundle/bundle.mjs                  build (writes only when the bytes change)
 *   node tools/bundle/bundle.mjs --watch          rebuild on every source save; a linked checkout hot-reloads
 *   node tools/bundle/bundle.mjs --check          verify the committed files; writes nothing
 *   node tools/bundle/bundle.mjs --check --same-esbuild   also fail when the byte comparison cannot run (releases)
 *   node tools/bundle/bundle.mjs --report         lines per source file
 *
 * Both outputs are plain, readable code: the page bundle is ESM that imports only the three
 * specifiers the app's loader allows, the frame script a self-contained IIFE. Each banner records the
 * esbuild version and two hashes (sources: only the folders that output bundles, and body), so a stale or
 * hand-edited output is detected without esbuild (here, and in tests/repo/test_desktop_bundle.py).
 * esbuild and TypeScript come from the first place tools/bundle/node-modules.mjs finds them (the pinned
 * tools/npm/node_modules, or a Hermes Desktop checkout).
 *
 * Before building, it regenerates page/app/rpc-names.js from the backend's @rpc declarations with
 * tools/bundle/rpc_names.py (Python from PATH); --check fails when that file is stale.
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { lineCount, lintSources, sourceFiles } from './lint.mjs'
import { findModules, MISSING_HINT } from './node-modules.mjs'
import { rpcNames } from './rpc-names.mjs'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const SOURCE = 'page'
// Import aliases: a module imports a file in its own folder (or a subfolder of it) as ./x.js and anything
// else through one of these, so no source path climbs a folder (tools/bundle/lint.mjs). Part of the
// sources hash, as this file is.
export const ALIASES = {
  '#sdk': `${SOURCE}/sdk.js`,
  '#app': `${SOURCE}/app`,
  '#pages': `${SOURCE}/pages`,
  '#shared': `${SOURCE}/shared`,
  '#frame': `${SOURCE}/frame`
}
const EXTERNAL = ['@hermes/plugin-sdk', 'react', 'react/jsx-runtime']
const MAX_LINE = 2_000
const ART_ROW = 96
// The characters the install scanner treats as hidden text.
const INVISIBLE = /[\u200b-\u200d\u2060\u2062-\u2064\ufeff\u202a-\u202e\u2066-\u2069]/
const CLIMBS_TWICE = '..' + '/..'
// What Hermes's admission lint refuses in a desktop plugin (hermes_cli/plugin_validate_desktop.py);
// tests/repo/test_desktop_bundle.py holds the same list.
const REFUSED = {
  'code evaluated from a string': new RegExp('(?<![\\w$.])' + 'ev' + 'al\\(|\\bnew\\s+Function\\('),
  'a dynamic import': /\bimport\(/,
  'an injected script': new RegExp(`createElement\\(\\s*['"]script['"]\\s*\\)|<` + 'script\\b'),
  'a reach into the preview webview': /\(\s*[`'"]webview\b/
}
const BANNER = /^\/\*\*\n(?: \*[^\n]*\n)*? \* build: esbuild (\S+)\n \* sources: sha256 ([0-9a-f]{64})\n \* body: sha256 ([0-9a-f]{64})\n \*\/\n/

const sha256 = data => createHash('sha256').update(data).digest('hex')
const abs = relative => path.join(ROOT, relative)
const importsOf = text => [...text.matchAll(/^import\s(?:[^;]*?\sfrom\s+)?"([^"]+)";$/gm)].map(match => match[1]).sort()

/** The outputs: where each comes from, what its banner says, and what must hold for it whatever built it.
 *  `sources` are the folders its banner hashes: everything it bundles must lie in them (checked on each build),
 *  so a page edit restamps only desktop/plugin.js. tests/repo/test_desktop_bundle.py holds the same lists. */
const TARGETS = [
  {
    output: 'desktop/plugin.js',
    entry: `${SOURCE}/index.js`,
    sources: [SOURCE],
    about: [
      'hermretro \u2014 Hermes Desktop half. GENERATED FILE, do not edit.',
      `Source: ${SOURCE}/ (one folder per page). Rebuild: node tools/bundle/bundle.mjs`,
      'Plain ESM; imports only @hermes/plugin-sdk, react and react/jsx-runtime.'
    ],
    esbuild: { format: 'esm', external: EXTERNAL },
    // Hermes's install scanner notes any single file over 1024 KB.
    maxBytes: 1_000_000,
    warnBytes: 900_000,
    problems(text) {
      const imported = importsOf(text)
      const strays = readdirSync(abs('desktop')).filter(name => name !== 'plugin.js')

      return [
        imported.join() === [...EXTERNAL].sort().join() ? null : `the bundle must import exactly ${EXTERNAL.join(', ')} (one statement each); it imports ${imported.join(', ') || 'nothing'}`,
        strays.length ? `desktop/ is published as it stands and must hold only plugin.js; it also holds ${strays.join(', ')}` : null,
        existsSync(abs('plugin.js')) ? 'a plugin.js at the repository root would replace desktop/plugin.js as the desktop half' : null,
        ...Object.entries(REFUSED).map(([what, pattern]) => (pattern.test(text) ? `the bundle holds ${what}, which the app refuses to load` : null))
      ]
    }
  },
  {
    output: 'player/frame-shim.js',
    entry: `${SOURCE}/frame/index.js`,
    sources: [`${SOURCE}/frame`, `${SOURCE}/shared`],
    about: [
      'hermretro \u2014 the player frame shim. GENERATED FILE, do not edit.',
      `Source: ${SOURCE}/frame/. Rebuild: node tools/bundle/bundle.mjs`,
      'Inlined first in the player frame page by the player backend (backend/player/); imports nothing.'
    ],
    esbuild: { format: 'iife', external: [] },
    maxBytes: 100_000,
    warnBytes: 80_000,
    problems(text) {
      return [
        importsOf(text).length ? 'the frame shim must import nothing (it runs as an inline classic script)' : null,
        ['__DEFAULT_COLOR__', '__COLOR_KEY__'].every(marker => text.includes(marker)) ? null : 'the frame shim lost a placeholder that the player backend (backend/player/) fills in'
      ]
    }
  }
]

function toolchain() {
  const modules = findModules(['esbuild', 'typescript'])

  if (!modules) {
    return { esbuild: null, ts: null, missing: 'esbuild and typescript were not found' }
  }

  const require = createRequire(path.join(modules, 'package.json'))

  return { esbuild: require('esbuild'), ts: require('typescript'), missing: null }
}

/** `import art from './art.png'` (or `.svg`) becomes a data URL: the prefix on its own line, the payload in short
 *  rows. A PNG is base64; an SVG is its own text, byte for byte, percent-encoded where a URL or a quoted JS string
 *  needs it (smaller than base64, so the provider logos fit the bundle's size budget). */
const svgText = text => text.replace(/[%#\n\r\t]|[^\x20-\x7e]/gu, encodeURIComponent)
const artRows = text => text.match(new RegExp(`[^]{1,${ART_ROW}}`, 'g')) ?? []
const artDataUrl = {
  name: 'art-data-url',
  setup(build) {
    build.onLoad({ filter: /\.(png|svg)$/ }, async ({ path: file }) => {
      const svg = file.endsWith('.svg')
      const bytes = await readFile(file)
      const prefix = svg ? 'data:image/svg+xml,' : 'data:image/png;base64,'
      const rows = artRows(svg ? svgText(bytes.toString('utf8')) : bytes.toString('base64'))

      return {
        contents: `export default [\n  ${JSON.stringify(prefix)},\n${rows.map(row => `  ${JSON.stringify(row)}`).join(',\n')}\n].join('')\n`,
        loader: 'js'
      }
    })
  }
}

const options = target => ({
  absWorkingDir: ROOT,
  entryPoints: [target.entry],
  bundle: true,
  ...target.esbuild,
  platform: 'browser',
  target: 'esnext',
  // Without this esbuild escapes every non-ASCII character, which the install scanner notes.
  charset: 'utf8',
  legalComments: 'none',
  write: false,
  metafile: true,
  logLevel: 'warning',
  alias: Object.fromEntries(Object.entries(ALIASES).map(([alias, target]) => [alias, `./${target}`])),
  plugins: [artDataUrl]
})

const buildAll = tools => Promise.all(TARGETS.map(target => tools.esbuild.build(options(target))))

/** SHA-256 over a target's source folders and this tool: path, a zero byte, then the bytes, in path order. */
function sourcesHash(target) {
  const hash = createHash('sha256')
  const files = target.sources.flatMap(folder => sourceFiles(abs(folder)).map(name => `${folder}/${name}`))

  for (const file of [...files, 'tools/bundle/bundle.mjs'].sort()) {
    hash.update(file).update('\0').update(readFileSync(abs(file)))
  }

  return hash.digest('hex')
}

const banner = (target, stamp) =>
  `/**\n${target.about.map(line => ` * ${line}\n`).join('')} * build: esbuild ${stamp.esbuild}\n * sources: sha256 ${stamp.sources}\n * body: sha256 ${stamp.body}\n */\n`

function readStamp(text) {
  const match = BANNER.exec(text)

  return match ? { length: match[0].length, esbuild: match[1], sources: match[2], body: match[3] } : null
}

const readOutput = target => (existsSync(abs(target.output)) ? readFileSync(abs(target.output), 'utf8') : '')

/** Bundled files outside the folders a target's banner hashes (an edit there would not mark it stale). */
const unhashed = (target, result) =>
  Object.keys(result.metafile.inputs)
    .filter(file => !target.sources.some(folder => file.startsWith(`${folder}/`)))
    .map(file => `${target.output} bundles ${file}, outside the folders its banner hashes (${target.sources.join(', ')})\nFIX: add the folder to that target's sources in tools/bundle/bundle.mjs and to SOURCES in tests/repo/test_desktop_bundle.py`)

/** What must hold for an output, whatever built it. */
function outputProblems(target, text) {
  const bytes = Buffer.byteLength(text)
  const longest = Math.max(...text.split('\n').map(line => line.length))

  if (bytes > target.warnBytes && bytes <= target.maxBytes) {
    console.warn(`warning: ${target.output} is ${bytes} bytes, close to the ${target.maxBytes} limit`)
  }

  return [
    bytes > target.maxBytes ? `${target.output} is ${bytes} bytes; the limit is ${target.maxBytes}` : null,
    longest > MAX_LINE ? `${target.output} has a line of ${longest} characters; the limit is ${MAX_LINE}` : null,
    INVISIBLE.test(text) ? `${target.output} holds an invisible unicode character (write it as a visible alternative in the source)` : null,
    text.includes(CLIMBS_TWICE) ? `${target.output} holds a relative path that climbs two folders` : null,
    ...target.problems(text)
  ].filter(Boolean)
}

/** The finished outputs for one esbuild result per target, and everything wrong with them or the sources. */
function finish(results, tools) {
  const texts = TARGETS.map((target, index) => {
    const body = results[index].outputFiles[0].text

    return banner(target, { esbuild: tools.esbuild.version, sources: sourcesHash(target), body: sha256(body) }) + body
  })
  // Every source file belongs to one output or the other: lint them as one tree.
  const inputs = Object.assign({}, ...results.map(result => result.metafile.inputs))

  return {
    texts,
    problems: [...lintSources({ root: ROOT, source: SOURCE, aliases: ALIASES, inputs, ts: tools.ts }), ...TARGETS.flatMap((target, index) => [...unhashed(target, results[index]), ...outputProblems(target, texts[index])])]
  }
}

/** Replace an output in one step (the app watches the bundle), and only when it changed. */
function write(relative, text) {
  if (existsSync(abs(relative)) && readFileSync(abs(relative), 'utf8') === text) {
    return false
  }

  // Per process, so a watch and a manual build never rename the same temporary file.
  const temp = abs(`.dev/${path.basename(relative)}.${process.pid}.tmp`)

  mkdirSync(path.dirname(temp), { recursive: true })
  writeFileSync(temp, text)
  renameSync(temp, abs(relative))

  return true
}

/** Why the committed outputs cannot be trusted, from their banners alone (no esbuild needed). */
export function staleReasons() {
  return TARGETS.flatMap(target => {
    const text = readOutput(target)
    const stamp = readStamp(text)

    if (!stamp) {
      return [`${target.output} is missing or has no build banner`]
    }

    return [
      sha256(text.slice(stamp.length)) === stamp.body ? null : `${target.output} was edited by hand (its body hash differs)`,
      sourcesHash(target) === stamp.sources ? null : `${target.output} is stale (${target.sources.join('/, ')}/ or the build tool changed since it was built)`
    ].filter(Boolean)
  })
}

async function check(tools, strict) {
  const problems = staleReasons()
  const texts = TARGETS.map(readOutput)
  const stamps = texts.map(readStamp)

  if (stamps.some(stamp => !stamp)) {
    return problems
  }

  TARGETS.forEach((target, index) => problems.push(...outputProblems(target, texts[index])))

  const versions = [...new Set(stamps.map(stamp => stamp.esbuild))]
  const skipped = tools.missing
    ? tools.missing
    : versions.some(version => version !== tools.esbuild.version)
      ? `built with esbuild ${versions.join(', ')}, this machine has ${tools.esbuild.version}`
      : null

  if (skipped && strict) {
    problems.push(`${skipped}: the byte comparison could not run`)
  } else if (skipped) {
    console.log(`${skipped}: byte comparison skipped`)
  } else {
    const built = finish(await buildAll(tools), tools)

    problems.push(...built.problems.filter(problem => !problems.includes(problem)))

    // A stale or edited output differs too; say so only when nothing above explains it.
    if (!problems.length) {
      TARGETS.forEach((target, index) => built.texts[index] !== texts[index] && problems.push(`a fresh build differs from ${target.output}`))
    }
  }

  return problems
}

function report(results) {
  const rows = [...new Set(results.flatMap(result => Object.keys(result.metafile.inputs)))]
    .filter(file => file.endsWith('.js'))
    .map(file => [lineCount(readFileSync(abs(file), 'utf8')), file])
    .sort(([a], [b]) => b - a)

  for (const [lines, file] of rows) {
    console.log(`${String(lines).padStart(6)}  ${file}${lines > 300 ? '   (over the 300-line aim)' : ''}`)
  }

  console.log(`${rows.length} modules, ${rows.reduce((sum, [lines]) => sum + lines, 0)} lines`)
}

function fail(problems) {
  for (const problem of problems) {
    console.error(`error: ${problem}`)
  }

  return problems.length ? 1 : 0
}

/** Write every output, or none when anything is wrong. */
function emit(results, tools) {
  const { texts, problems } = finish(results, tools)

  if (!problems.length) {
    TARGETS.forEach((target, index) => console.log(`${target.output}: ${Buffer.byteLength(texts[index])} bytes, ${write(target.output, texts[index]) ? 'written' : 'unchanged'}`))
  }

  return fail(problems)
}

/** Rebuild on every save. Each output has its own esbuild context; they are written together from the
 *  latest good result of each, so the lint always sees the whole tree. */
async function watch(tools) {
  const latest = TARGETS.map(() => null)

  for (const [index, target] of TARGETS.entries()) {
    const onEnd = result => {
      latest[index] = result.errors.length ? null : result

      if (latest.every(Boolean)) {
        emit(latest, tools)
      }
    }
    const context = await tools.esbuild.context({ ...options(target), plugins: [artDataUrl, { name: 'emit', setup: build => build.onEnd(onEnd) }] })

    await context.watch()
  }

  console.log(`watching ${SOURCE}/ (Ctrl+C to stop)`)

  return new Promise(() => {})
}

async function main(flags) {
  const tools = toolchain()
  const names = rpcNames(ROOT, flags.has('--check'))

  if (names.length) {
    return fail(names)
  }

  if (flags.has('--check')) {
    const code = fail(await check(tools, flags.has('--same-esbuild')))

    if (!code) {
      console.log(`ok: ${TARGETS.map(target => target.output).join(' and ')} match ${SOURCE}/`)
    }

    return code
  }

  if (tools.missing) {
    return fail([`${tools.missing}; ${MISSING_HINT}`])
  }

  if (flags.has('--watch')) {
    return watch(tools)
  }

  const results = await buildAll(tools)

  if (flags.has('--report')) {
    report(results)

    return 0
  }

  return emit(results, tools)
}

// Node runs this file by its real path but keeps argv as typed: compare real paths, or a checkout
// reached through a symlink would import the module and silently do nothing.
const realPath = file => {
  try {
    return realpathSync(file)
  } catch {
    return path.resolve(file)
  }
}

if (process.argv[1] && realPath(process.argv[1]) === realPath(fileURLToPath(import.meta.url))) {
  process.exit(await main(new Set(process.argv.slice(2))).catch(error => fail([error.message])))
}
