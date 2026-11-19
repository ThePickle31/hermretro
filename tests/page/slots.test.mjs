// Every UI slot passes its contributions exactly the props its doc string promises. The doc string is the
// contract a contributing page reads ("Props: { a, b, ... }" in the host page's index.js `slots`, plus
// conditional ones written "plus x(...) on the <where> only"), so a prop documented but never passed, or passed
// but never documented, fails here. A probe stands in for the real contributions while each host renders.
//   node --test tests/page/slots.test.mjs
import assert from 'node:assert/strict'
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
// "on the <where> only". A new slot gets its recipe here (the first test says so).
const HOSTS = {
  'emulator.barActions': [
    {
      where: 'Emulator page',
      draw: async () => {
        const player = { game, query: playerQuery, focused: false, capturesOpen: false, rebuilt: false, ask() {}, fullScreen() {}, later() {}, reload() {}, refresh() {}, toggleCaptures() {} }

        return render(jsx(pageOf('emulator').Page, { shell: { ctx, go() {}, hardwareOn: true, player } }))
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
        const shown = await render(jsx(pageOf('games').Page, { shell: { ctx, games, gameList: [game], hardwareOn: true, go() {}, openPrompt() {}, play() {}, setUpDevice() {} } }))
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

test('a slot doc string is read as its props', () => {
  assert.deepEqual(documentedProps('Props: { ctx, game, item(icon, label, { disabled, why }) }; return item(...)'), { always: ['ctx', 'game', 'item'], extra: [], where: null })
  assert.deepEqual(documentedProps('Props: { ctx, game }, plus go(pageId) and later on the Emulator page only (more)'), { always: ['ctx', 'game'], extra: ['go', 'later'], where: 'Emulator page' })
})

test('every declared slot has a host recipe here, and a place for its conditional props', () => {
  assert.ok(PAGE_SLOTS.declared().size >= 2, 'the page\'s slots are wired')
  for (const [name, { doc }] of PAGE_SLOTS.declared()) {
    assert.ok(HOSTS[name], `add how to draw the host of "${name}" to HOSTS in tests/page/slots.test.mjs`)
    const { where } = documentedProps(doc)

    if (where) {
      assert.ok(HOSTS[name].some(host => host.where === where), `"${name}" passes props on the ${where} only: give HOSTS a recipe with where: '${where}'`)
    }
  }
})

test('each host passes a contribution exactly the props its slot documents', async () => {
  const original = PAGE_SLOTS.contributions

  try {
    for (const [name, { doc }] of PAGE_SLOTS.declared()) {
      const { always, extra, where } = documentedProps(doc)

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
