// Every UI slot passes its contributions exactly the props its doc string promises. The doc string is the
// contract a contributing page reads ("Props: { a, b, ... }" in the host page's index.js `slots`, plus
// conditional ones written "plus x(...) on the <where> only"), so a prop documented but never passed, or passed
// but never documented, fails here. A probe stands in for the real contributions while each host renders.
// A slot declared but not yet rendered by any page (what `retrodev new slot` leaves) has no props to check
// and passes; once a page renders it with jsx(Slot, { name: '...' }), it needs its recipe in HOSTS below.
// Run alone: node tests/page/slots.test.mjs
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><div id="root"></div>')

globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const { jsx } = await import('react/jsx-runtime')
const { PAGES } = await import('../../page/pages/index.js')
const { PAGE_SLOTS } = await import('../../page/app/slots.js')
// Importing the registry wires every page's slots into PAGE_SLOTS.
await import('../../page/app/registry.js')
const { scenario } = await import('./sdk-stub.mjs')
const { answered, ownPage, pageShell, shapeOf } = await import('./shells.mjs')

const ctx = { storage: { get: (key, fallback) => fallback, set() {} }, os: {} }
const game = { id: 'abc123abc123', title: 'Probe', state: 'ready', rom: { path: '/x.gb' }, web: null, webExport: true, chat: null, projectRoot: '/games/probe' }
const playerQuery = { data: { url: 'http://127.0.0.1:1/p/index.html' }, isFetching: false }

async function render(element) {
  const node = document.createElement('div')
  const root = createRoot(node)

  await act(async () => root.render(element))

  return { node, close: async () => act(async () => root.unmount()) }
}

const pageOf = id => PAGES.find(page => page.id === id)

// How to draw each slot's host, once per place it renders the slot. `where` matches the doc string's
// "on the <where> only". A new slot gets its recipe here (the first test says so). Draw a page with ownPage(page)
// (its Page, or its first tab's once it has tabs), never page.Page. A slot on a page that reads the shell:
// draw it with { shell: pageShell({ ... }) } from tests/page/shells.mjs (every field of the real shell, with its shape; the last
// tests here check that list against the real shell).
const HOSTS = {
  'emulator.barActions': [
    {
      where: 'Emulator page',
      draw: async () => {
        const player = { game, query: playerQuery, focused: false, capturesOpen: false, rebuilt: false, ask() {}, fullScreen() {}, later() {}, reload() {}, refresh() {}, toggleCaptures() {} }

        return render(jsx(ownPage(pageOf('emulator')), { shell: { ctx, go() {}, hardwareOn: true, player } }))
      }
    },
    {
      where: 'emulator tab beside the chat',
      draw: async () => {
        const { openSideEmulator } = await import('../../page/pages/emulator/beside-chat/tab.js')

        scenario.games = { data: { games: [game], device: { hardwareEnabled: true } }, isFetching: false }
        scenario.player = playerQuery
        assert.ok(openSideEmulator(ctx, game), 'the tab opened')

        return render(scenario.workspaces.at(-1).options.render())
      }
    }
  ],
  'games.cardMenu': [
    {
      where: 'Games shelf',
      draw: async () => {
        const games = { data: { games: [game], device: { hardwareEnabled: true } }, isFetching: false }
        const shown = await render(jsx(ownPage(pageOf('games')), { shell: { ctx, games, gameList: [game], hardwareOn: true, go() {}, openPrompt() {}, play() {}, setUpDevice() {} } }))
        const caret = shown.node.querySelector('.cs-split .caret')

        assert.ok(caret, 'the card has its arrow menu')
        await act(async () => caret.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })))

        return shown
      }
    }
  ]
}

/** The props a slot's doc string promises: `always`, and `extra` passed only `where`. */
function documentedProps(doc) {
  const start = doc.indexOf('Props: {')

  assert.ok(start >= 0, `the slot's doc string names its props as "Props: { a, b, ... }": ${doc}`)
  let depth = 0
  let end = start + 'Props: '.length

  for (; end < doc.length; end++) {
    depth += doc[end] === '{' || doc[end] === '(' ? 1 : doc[end] === '}' || doc[end] === ')' ? -1 : 0

    if (depth === 0) {
      break
    }
  }

  const names = text => {
    const out = []
    let level = 0
    let part = ''

    for (const char of `${text},`) {
      level += '({'.includes(char) ? 1 : ')}'.includes(char) ? -1 : 0

      if (char === ',' && level === 0) {
        const name = part.trim().match(/^[A-Za-z_$][\w$]*/)?.[0]

        if (name) {
          out.push(name)
        }

        part = ''
      } else {
        part += char
      }
    }

    return out
  }
  const always = names(doc.slice(start + 'Props: {'.length, end))
  const plus = doc.slice(end + 1).match(/^\s*,?\s*plus (.+?) on the (.+?) only/)

  return { always, extra: plus ? names(plus[1].replace(/\band\b/g, ',')) : [], where: plus ? plus[2] : null }
}

const PAGE_DIR = fileURLToPath(new URL('../../page/', import.meta.url))

/** Each page source file under `dir`, as [path relative to page/, text]. */
function pageSources(dir = PAGE_DIR) {
  return readdirSync(dir, { recursive: true })
    .filter(name => /\.(m?js|jsx)$/.test(name))
    .map(name => [`page/${name}`, readFileSync(join(dir, name), 'utf8')])
}

/** The slot names `sources` render (`jsx(Slot, { name: '...' })`, comments skipped), and where each is. */
function renderedSlots(sources) {
  const rendered = new Map()
  const unnamed = []

  for (const [file, text] of sources) {
    const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

    for (const call of code.matchAll(/\bjsx\(\s*Slot\s*,\s*\{([^}]*)/g)) {
      const name = call[1].match(/^\s*name:\s*(['"])([^'"]+)\1/)?.[2]

      if (name) {
        rendered.set(name, [...(rendered.get(name) ?? []), file])
      } else {
        unnamed.push(file)
      }
    }
  }

  return { rendered, unnamed }
}

/** Which declared slots lack a host recipe (`problems`), and which no page renders yet (`notYet`). */
function hostCheck(declared, rendered, hosts) {
  const problems = []
  const notYet = []

  for (const [name, { doc }] of declared) {
    if (!rendered.has(name)) {
      notYet.push(name)
      continue
    }

    if (!hosts[name]) {
      problems.push(`"${name}" is rendered in ${rendered.get(name).join(', ')}. FIX: add how to draw its host to HOSTS in tests/page/slots.test.mjs`)
      continue
    }

    const { where } = documentedProps(doc)

    if (where && !hosts[name].some(host => host.where === where)) {
      problems.push(`"${name}" passes props on the ${where} only. FIX: give its HOSTS entry in tests/page/slots.test.mjs a recipe with where: '${where}'`)
    }
  }

  return { problems, notYet }
}

test('a slot doc string is read as its props', () => {
  assert.deepEqual(documentedProps('Props: { ctx, game, item(icon, label, { disabled, why }) }; return item(...)'), { always: ['ctx', 'game', 'item'], extra: [], where: null })
  assert.deepEqual(documentedProps('Props: { ctx, game }, plus go(pageId) and later on the Emulator page only (more)'), { always: ['ctx', 'game'], extra: ['go', 'later'], where: 'Emulator page' })
})

test('the slots a page renders are found in its source', () => {
  const sources = [
    ['page/a.js', "jsx(Slot, { name: 'a.one', props: { ctx } })\n  // jsx(Slot, { name: 'a.commented' })"],
    ['page/b.js', "/* jsx(Slot, { name: 'b.block' }) */ jsx( Slot, {name: \"a.one\"}, 'k') jsx(Slot, { name: slotName })"]
  ]
  const { rendered, unnamed } = renderedSlots(sources)

  assert.deepEqual([...rendered], [['a.one', ['page/a.js', 'page/b.js']]])
  assert.deepEqual(unnamed, ['page/b.js'])
})

test('a declared slot no page renders yet needs no host recipe; once rendered, it does', () => {
  const declared = new Map([['probe.notYet', { owner: 'probe', doc: 'Props: { ctx }' }]])

  assert.deepEqual(hostCheck(declared, new Map(), {}), { problems: [], notYet: ['probe.notYet'] })
  const { problems } = hostCheck(declared, new Map([['probe.notYet', ['page/pages/probe/probe-page.js']]]), {})

  assert.equal(problems.length, 1)
  assert.match(problems[0], /rendered in page\/pages\/probe\/probe-page\.js\. FIX: add how to draw its host to HOSTS in tests\/page\/slots\.test\.mjs/)
})

test('every rendered slot has a host recipe here, and a place for its conditional props', t => {
  assert.ok(PAGE_SLOTS.declared().size >= 2, 'the page\'s slots are wired')
  const { rendered, unnamed } = renderedSlots(pageSources())

  assert.deepEqual(unnamed, [], 'FIX: name the slot as a string literal (jsx(Slot, { name: \'page.slot\', ... })) so this test can find its host')
  const { problems, notYet } = hostCheck(PAGE_SLOTS.declared(), rendered, HOSTS)

  for (const name of notYet) {
    t.diagnostic(`${name}: declared, not rendered yet: no props to check`)
  }

  assert.deepEqual(problems, [])
})

test('each host passes a contribution exactly the props its slot documents', async () => {
  const original = PAGE_SLOTS.contributions

  try {
    for (const [name, { doc }] of PAGE_SLOTS.declared()) {
      const { always, extra, where } = documentedProps(doc)

      // A slot no page renders yet has no host (the test above).
      for (const host of HOSTS[name] ?? []) {
        const seen = []
        const Probe = props => {
          seen.push(Object.keys(props).sort())

          return null
        }

        PAGE_SLOTS.contributions = slot => (slot === name ? [Probe] : original(slot))
        const shown = await host.draw()
        const expected = [...always, ...(host.where === where ? extra : [])].sort()

        assert.ok(seen.length, `${name} was rendered on the ${host.where}`)
        assert.deepEqual(seen.at(-1), expected, `${name} on the ${host.where}: the props passed (left) and documented (right) in its doc string`)
        await shown.close()
        PAGE_SLOTS.contributions = original
      }
    }
  } finally {
    PAGE_SLOTS.contributions = original
  }
})

test("a page's own Page is its first tab's once it has tabs", () => {
  const First = () => null
  const Own = () => null

  assert.equal(ownPage({ id: 'p', Page: Own }), Own)
  assert.equal(ownPage({ id: 'p', tabs: [{ id: 'a', Page: First }, { id: 'b', Page: Own }] }), First)
})

test('Games draws from pageShell(), the fixture a host recipe uses', async () => {
  const shown = await render(jsx(ownPage(pageOf('games')), { shell: pageShell() }))

  assert.ok(shown.node.querySelector('.cs-empty'), 'the empty shelf rendered')
  assert.ok(shown.node.textContent.includes('Create a new game'), 'with its action')
  await shown.close()
})

// The real shell (page/app/studio-page.js) with a probe in Games' place: pageShell() has exactly its fields, each
// with the same kind of value, so a page that starts reading any shell field (shell.viaProfile) finds it there.
test("pageShell() matches the shell a page really gets", async () => {
  const { StudioPage } = await import('../../page/app/studio-page.js')
  const probe = pageOf('games')
  const original = probe.Page
  const seen = []
  const storage = { page: 'games', setup: { onboarded: true, onboardStarted: true, hardwareSkipped: true } }
  const real = { storage: { get: (key, fallback) => storage[key] ?? fallback, set: (key, value) => { storage[key] = value } }, os: {} }

  scenario.status = answered({ ok: true, via_profile: 'hermretro', hardware_enabled: false, project: null, plugin: { version: '9' }, node: { ok: true }, engine: { present: true, verified: true },
    profile: { name: 'hermretro', is_studio: true, studio: { name: 'hermretro', exists: true, installed: true, ours: true } }, deps: { device_cli: { state: 'installed', version: '1.2.1' } } })
  scenario.doctor = answered({ ok: true, missing_required: [], components: [] })
  scenario.games = answered({ games: [game], device: { hardwareEnabled: false } })
  probe.Page = ({ shell }) => { seen.push(shell); return null }
  try {
    const shown = await render(jsx(StudioPage, { ctx: real }))

    assert.ok(seen.length, 'the probe rendered')
    const shell = seen.at(-1)
    const fixture = pageShell()
    // null or a value, by setup state and routing
    const scalar = new Set(['auto', 'autoId', 'choosing', 'shown', 'viaProfile'])
    const missing = Object.keys(fixture).filter(key => !(key in shell))
    const absent = Object.keys(shell).filter(key => !(key in fixture))
    const differ = Object.keys(fixture).filter(key => key in shell && !scalar.has(key) && shapeOf(shell[key]) !== shapeOf(fixture[key]))

    assert.deepEqual(missing, [], 'FIX: pageShell() in tests/page/shells.mjs lists a field the real shell lacks')
    assert.deepEqual(absent, [], 'FIX: add the real shell field to pageShell() in tests/page/shells.mjs')
    assert.deepEqual(differ.map(key => `${key}: real ${shapeOf(shell[key])}, fixture ${shapeOf(fixture[key])}`), [], 'FIX: give the field its real shape in pageShell()')
    const reads = pageSources().filter(([file]) => file.startsWith('page/pages/')).flatMap(([file, text]) => [...text.matchAll(/\bshell\.(\w+)/g)].map(match => `${match[1]} (${file})`))

    assert.deepEqual([...new Set(reads)].filter(read => !(read.split(' ')[0] in fixture)), [], 'FIX: add the shell field a page now reads to pageShell() in tests/page/shells.mjs')
    await shown.close()
  } finally {
    probe.Page = original
  }
})
