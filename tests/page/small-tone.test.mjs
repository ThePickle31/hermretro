// Small (page/shared/ui/text.js) takes only tone: 'warn'; any other tone renders as plain small print without a
// word of warning, so this refuses one written in page/.
// Run alone: node tests/page/small-tone.test.mjs
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const TONES = new Set(['warn'])

/** The text of the object literal that starts at `open` (a `{`), skipping quoted strings. */
function objectAt(text, open) {
  let depth = 0
  for (let i = open; i < text.length; i++) {
    const c = text[i]
    if (c === "'" || c === '"' || c === '`') {
      for (i++; i < text.length && text[i] !== c; i++) if (text[i] === '\\') i++
    } else if (c === '{') depth++
    else if (c === '}' && --depth === 0) return text.slice(open, i + 1)
  }
  return text.slice(open)
}

/** Each unsupported Small tone in one file's text, as 'line N: tone ...'. */
export function badTones(text) {
  const found = []
  for (const call of text.matchAll(/\bjsx\(\s*Small\s*,\s*\{/g)) {
    const props = objectAt(text, call.index + call[0].length - 1)
    // Only the call's own props: nested objects (another jsx call's), innermost first, are cut out.
    let own = props.slice(1, -1)
    while (/\{[^{}]*\}/.test(own)) own = own.replace(/\{[^{}]*\}/g, '')
    const tone = own.match(/\btone\s*:\s*([^,}\n]+)/)
    if (!tone) continue
    const literal = tone[1].trim().match(/^(['"])(.*)\1$/)
    if (!literal || !TONES.has(literal[2])) {
      found.push(`line ${text.slice(0, call.index).split('\n').length}: tone ${tone[1].trim()}`)
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
  assert.deepEqual(badTones("jsx(Small, { tone: level, children: 'x' })"), ['line 1: tone level'])
  assert.deepEqual(badTones("jsx(Small, { children: jsx(Tag, { tone: 'bad' }) })"), [], "another component's tone")
  assert.deepEqual(badTones("jsx(Small, { children: jsx(Tag, { a: { b: 1 } }), tone: 'bad' })"), ["line 1: tone 'bad'"])
})

test("page/ gives Small no tone but 'warn'", () => {
  const found = pageFiles(path.join(root, 'page')).flatMap(file =>
    badTones(readFileSync(file, 'utf8')).map(line => `${path.relative(root, file)} ${line}`)
  )
  assert.deepEqual(found, [], "FIX: Small's tone takes only 'warn' (page/shared/ui/text.js); drop the tone or use 'warn'")
})
