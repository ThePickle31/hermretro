// Small (page/shared/ui/text.js) takes only tone: 'warn'; any other tone renders as plain small print without a
// word of warning, so this refuses one written in page/.
// Every file is parsed (acorn, from the development packages: npm ci --prefix tools/npm --ignore-scripts), and every
// element call that makes a Small is read: jsx, jsxs, jsxDEV and createElement (React.createElement too), under any
// name Small is imported as. A tone must be provably 'warn' (or absent: undefined, null). A tone the check cannot
// prove (a variable, a call, spread props, props that are not an object written in place) is refused as unverifiable,
// because a guard that let unknown values through would pass exactly the tone it exists to stop; the one exception is
// a name bound in the same file by a top-level `const NAME = <a value it can prove>`.
// Run alone: node tests/page/small-tone.test.mjs
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { findModules, MISSING_HINT } from '../../tools/bundle/node-modules.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const modules = findModules(['acorn'])
if (!modules) throw new Error(`acorn is missing. FIX: ${MISSING_HINT}`)
const { parse } = createRequire(path.join(modules, 'package.json'))('acorn')

const TONES = new Set(['warn'])
const FACTORIES = new Set(['jsx', 'jsxs', 'jsxDEV', 'createElement'])

/** Every node under `node` (acorn's ESTree), parents first. */
function* walk(node) {
  if (!node || typeof node.type !== 'string') return
  yield node
  for (const [key, value] of Object.entries(node)) {
    if (key === 'loc') continue
    if (Array.isArray(value)) for (const item of value) yield* walk(item)
    else if (value && typeof value === 'object') yield* walk(value)
  }
}

/** A property's key as a string, or null when it is computed from an expression. */
function keyName(prop) {
  if (prop.computed) return prop.key.type === 'Literal' ? String(prop.key.value) : null
  return prop.key.type === 'Identifier' ? prop.key.name : String(prop.key.value)
}

/** The tone values `node` can take, as strings (null for none), or undefined when it cannot be proven. */
function values(node, consts, seen = new Set()) {
  if (node.type === 'Literal' && (typeof node.value === 'string' || node.value === null)) return [node.value]
  if (node.type === 'TemplateLiteral' && node.expressions.length === 0) return [node.quasis[0].value.cooked]
  if (node.type === 'Identifier' && node.name === 'undefined') return [null]
  if (node.type === 'Identifier' && consts.has(node.name) && !seen.has(node.name)) {
    return values(consts.get(node.name), consts, new Set([...seen, node.name]))
  }
  if (node.type === 'ConditionalExpression') {
    const a = values(node.consequent, consts, seen)
    const b = values(node.alternate, consts, seen)
    return a && b ? [...a, ...b] : undefined
  }
  return undefined
}

/** Each unsupported Small tone in one file's text, as 'line N: ...'. */
export function badTones(text) {
  const tree = parse(text, { ecmaVersion: 'latest', sourceType: 'module', locations: true })
  const src = node => text.slice(node.start, node.end)
  const smalls = new Set(['Small'])
  const consts = new Map()

  for (const node of tree.body) {
    if (node.type === 'ImportDeclaration') {
      for (const spec of node.specifiers) {
        if (spec.type === 'ImportSpecifier' && (spec.imported.name ?? spec.imported.value) === 'Small') smalls.add(spec.local.name)
      }
    }
    const decl = node.type === 'ExportNamedDeclaration' ? node.declaration : node
    if (decl?.type === 'VariableDeclaration' && decl.kind === 'const') {
      for (const d of decl.declarations) if (d.id.type === 'Identifier' && d.init) consts.set(d.id.name, d.init)
    }
  }

  const found = []
  for (const node of walk(tree)) {
    if (node.type !== 'CallExpression') continue
    const callee = node.callee
    const name =
      callee.type === 'Identifier' ? callee.name : callee.type === 'MemberExpression' && !callee.computed ? callee.property.name : null
    const [type, props] = node.arguments
    if (!FACTORIES.has(name) || type?.type !== 'Identifier' || !smalls.has(type.name) || !props) continue

    const line = `line ${node.loc.start.line}:`
    if (props.type !== 'ObjectExpression') {
      if (!(props.type === 'Literal' && props.value === null)) found.push(`${line} props ${src(props)} (unverifiable)`)
      continue
    }
    for (const prop of props.properties) {
      if (prop.type === 'SpreadElement') found.push(`${line} spread ${src(prop)} (unverifiable)`)
      else if (keyName(prop) === null) found.push(`${line} computed key ${src(prop.key)} (unverifiable)`)
      else if (keyName(prop) === 'tone') {
        const tones = values(prop.value, consts)
        if (!tones) found.push(`${line} tone ${src(prop.value)} (unverifiable)`)
        else if (tones.some(tone => tone !== null && !TONES.has(tone))) found.push(`${line} tone ${src(prop.value)}`)
      }
    }
  }
  return found
}

function pageFiles(folder) {
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(folder, entry.name)
    return entry.isDirectory() ? pageFiles(full) : entry.name.endsWith('.js') ? [full] : []
  })
}

test('the check names a tone Small does not have, and passes warn and none', () => {
  assert.deepEqual(badTones("jsx(Small, { tone: 'warn', children: 'x' })"), [])
  assert.deepEqual(badTones("jsx(Small, { children: 'x' })"), [])
  assert.deepEqual(badTones("a\njsx(Small, {\n  tone: 'error',\n  children: 'x'\n})"), ["line 2: tone 'error'"])
  assert.deepEqual(badTones("jsx(Small, { children: jsx(Tag, { tone: 'bad' }) })"), [], "another component's tone")
  assert.deepEqual(badTones("jsx(Small, { children: jsx(Tag, { a: { b: 1 } }), tone: 'bad' })"), ["line 1: tone 'bad'"])
})

test('jsxs calls are read too: a tone in their props is checked, across lines', () => {
  assert.deepEqual(badTones("jsxs(Small, { tone: 'error', children: ['Failed: ', detail] })"), ["line 1: tone 'error'"])
  assert.deepEqual(badTones("jsxs(Small, { tone: 'warn', children: ['Careful: ', detail] })"), [])
  assert.deepEqual(badTones("a\njsxs(\n  Small,\n  {\n    children: ['x', y],\n    tone: 'error'\n  }\n)"), ["line 2: tone 'error'"])
})

test('the other element factories and an imported alias are read', () => {
  assert.deepEqual(badTones("jsxDEV(Small, { tone: 'error' })"), ["line 1: tone 'error'"])
  assert.deepEqual(badTones("createElement(Small, { tone: 'error' })"), ["line 1: tone 'error'"])
  assert.deepEqual(badTones("React.createElement(Small, { tone: 'error' })"), ["line 1: tone 'error'"])
  assert.deepEqual(badTones("import { Small as S } from '#shared/ui/text.js'\njsxs(S, { tone: 'error' })"), ["line 2: tone 'error'"])
  assert.deepEqual(badTones("document.createElement('small', { tone: 'error' })"), [], 'not a Small')
})

test('a tone it cannot prove is refused; a const, a conditional of proven values and none are read', () => {
  assert.deepEqual(badTones("jsx(Small, { tone: level, children: 'x' })"), ['line 1: tone level (unverifiable)'])
  assert.deepEqual(badTones("jsx(Small, { tone: pick(), children: 'x' })"), ['line 1: tone pick() (unverifiable)'])
  assert.deepEqual(badTones("jsxs(Small, { ...rest, children: ['x'] })"), ['line 1: spread ...rest (unverifiable)'])
  assert.deepEqual(badTones('jsx(Small, props)'), ['line 1: props props (unverifiable)'])
  assert.deepEqual(badTones("jsx(Small, { [key]: 'error' })"), ['line 1: computed key key (unverifiable)'])
  assert.deepEqual(badTones("const WARN = 'warn'\njsxs(Small, { tone: WARN })"), [])
  assert.deepEqual(badTones("const BAD = 'error'\njsxs(Small, { tone: BAD })"), ['line 2: tone BAD'])
  assert.deepEqual(badTones("jsxs(Small, { tone: ok ? undefined : 'warn' })"), [])
  assert.deepEqual(badTones("jsxs(Small, { tone: ok ? 'good' : 'warn' })"), ["line 1: tone ok ? 'good' : 'warn'"])
  assert.deepEqual(badTones('jsx(Small, { tone: `warn` })'), [])
})

test("page/ gives Small no tone but 'warn'", () => {
  const found = pageFiles(path.join(root, 'page')).flatMap(file =>
    badTones(readFileSync(file, 'utf8')).map(line => `${path.relative(root, file)} ${line}`)
  )
  assert.deepEqual(found, [], "FIX: Small's tone takes only 'warn' (page/shared/ui/text.js); write tone: 'warn' or leave it out")
})
