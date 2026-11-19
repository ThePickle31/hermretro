// The page registry (page/pages/index.js, app/registry.js), page events (app/events.js), UI slots
// (app/slots.js), tabs (app/page-view.js) and the stylesheet order (app/style.js), from the sources.
//   node --test tests/page/registry.test.mjs
import assert from 'node:assert/strict'
import { readdirSync, statSync } from 'node:fs'
import { registerAliases } from './aliases.mjs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

// The modules import each other through the page's aliases, and React and the SDK stand-in: resolve those first.
registerAliases()

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><div id="root"></div>')

globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const { jsx, jsxs } = await import('react/jsx-runtime')
const { PAGES } = await import('../../page/pages/index.js')
const { NAV_PAGES, pageProblems, startPages, wirePages } = await import('../../page/app/registry.js')
const { createEvents, emit, on, PAGE_EVENTS } = await import('../../page/app/events.js')
const { createSlots, PAGE_SLOTS, Slot } = await import('../../page/app/slots.js')
const { PageView } = await import('../../page/app/page-view.js')
const { composeStyles } = await import('../../page/app/style.js')
const { RESPONSIVE_CSS } = await import('../../page/shared/styles/responsive.css.js')
const { InstallButton } = await import('../../page/pages/games/games-page.js')
const { BUILD_INJECT, BUILD_PRESENTED } = await import('../../page/pages/build/chat/store.js')

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const Text = text => () => jsx('span', { children: text })
const fakePage = (id, extra = {}) => ({ id, label: id, Page: Text(id), ...extra })

/** Render `element` into a fresh root; returns the root's text and DOM node. */
async function render(element) {
  const node = document.createElement('div')
  const root = createRoot(node)

  await act(async () => root.render(element))

  return { node, root }
}

test('the registry lists every page folder once, in nav order, each describing itself', () => {
  const folders = readdirSync(path.join(ROOT, 'page', 'pages')).filter(name => statSync(path.join(ROOT, 'page', 'pages', name)).isDirectory())

  assert.deepEqual(PAGES.map(page => page.id), ['home', 'build', 'setup', 'prompts', 'games', 'emulator'])
  assert.deepEqual([...folders].sort(), PAGES.map(page => page.id).sort(), 'every folder under page/pages/ is a page in page/pages/index.js')
  assert.deepEqual(pageProblems(PAGES), [])
  assert.equal(NAV_PAGES, PAGES)

  for (const page of PAGES) {
    assert.equal(typeof page.label, 'string')
    assert.equal(typeof page.Page, 'function', `${page.id} has a Page`)
  }
})

test('events are declared once, by the page their name starts with', () => {
  const declared = PAGE_EVENTS.declared()

  assert.deepEqual([...declared.keys()].sort(), ['emulator.presented', 'games.coverRequested'])

  for (const [name, { owner }] of declared) {
    assert.ok(name.startsWith(`${owner}.`), name)
  }

  const twice = [fakePage('a', { events: { 'a.done': 'doc' } }), fakePage('b', { events: { 'a.done': 'doc' } })]

  assert.ok(pageProblems(twice).some(problem => problem.includes('"a.done" must be named "b.<name>"')))
  assert.ok(pageProblems([fakePage('a', { events: { 'a.done': 'doc' }, tabs: [{ id: 't', label: 'T', Page: Text('t'), events: { 'a.done': 'doc' } }] })]).some(problem => problem.includes('declared twice')))
  const hub = createEvents()

  hub.declare('x.y', 'x', 'doc')
  assert.throws(() => hub.declare('x.y', 'z', 'doc'), /declared by both x and z/)
})

test('an unknown event fails: emitting, listening, or a page listening to it', () => {
  assert.throws(() => emit('games.nope', {}), /unknown page event "games.nope"/)
  assert.throws(() => on('nobody.event', () => {}), /unknown page event/)
  assert.ok(pageProblems([fakePage('a', { listens: { 'b.thing': () => {} } })]).some(problem => problem.includes('listens to "b.thing", which no page declares')))
  assert.throws(() => wirePages([fakePage('a', { listens: { 'b.thing': () => {} } })], { events: createEvents(), slots: createSlots() }), /the page registry has problems/)
})

test('a listener that throws is logged and never stops the others', () => {
  const hub = createEvents()
  const heard = []
  const logged = []
  const original = console.error

  hub.declare('a.done', 'a', 'doc')
  hub.on('a.done', () => {
    throw new Error('boom (expected)')
  })
  const stop = hub.on('a.done', payload => heard.push(payload))

  console.error = (...args) => logged.push(args.join(' '))

  try {
    hub.emit('a.done', 1)
    stop()
    hub.emit('a.done', 2)
  } finally {
    console.error = original
  }

  assert.deepEqual(heard, [1])
  assert.equal(logged.length, 2)
  assert.ok(logged[0].includes('a listener of "a.done" failed'))
})

test('pages listen for their whole life: a cover request and a presentation reach Build', () => {
  const storage = {}
  const ctx = { storage: { get: (key, fallback) => storage[key] ?? fallback, set: (key, value) => { storage[key] = value } } }

  startPages(ctx)
  startPages(ctx) // registering again replaces the listeners: nothing is handled twice

  emit('games.coverRequested', { game: { id: 'frog', session: { storedId: 'st-9', thisProfile: true, exists: true } }, prompt: 'Draw it' })
  assert.equal(storage.buildSelected, 'frog')
  assert.deepEqual(BUILD_INJECT.get()['st-9'], { seq: 1, text: 'Draw it' })

  emit('emulator.presented', { gameId: 'frog', seq: 3, note: 'try it', t: 5 })
  assert.deepEqual(BUILD_PRESENTED.get().frog, { seq: 3, note: 'try it', t: 5 })
})

// Filling a real slot changes only the `filled` assertion below (a new, empty slot only the declared list); the
// empty case renders on a table of its own. A slot's contributions are listed in PAGES order
// (page/pages/index.js), whatever order the contributing pages were written in.
test('slots: the real ones are declared, and what fills them', () => {
  assert.deepEqual([...PAGE_SLOTS.declared().keys()].sort(), ['emulator.barActions', 'games.cardMenu'])
  const filled = Object.fromEntries([...PAGE_SLOTS.declared().keys()].map(name => [name, PAGE_SLOTS.contributions(name)]).filter(([, list]) => list.length))

  assert.deepEqual(filled, { 'emulator.barActions': [InstallButton] })
})

// emulator.barActions is drawn on the Emulator page (which has the shell, so it passes go) and in the emulator tab
// beside the chat (page/pages/emulator/beside-chat/tab.js, no shell, so no go). A probe stands in for the real
// contributions while the two render.
test('an emulator.barActions contribution gets go on the Emulator page, not beside the chat', async () => {
  const { EMULATOR_PAGE } = await import('../../page/pages/emulator/index.js')
  const { openSideEmulator } = await import('../../page/pages/emulator/beside-chat/tab.js')
  const { scenario } = await import('./sdk-stub.mjs')
  const seen = []
  const Probe = props => { seen.push(Object.keys(props).sort()); return null }
  const original = PAGE_SLOTS.contributions
  const game = { id: 'abc123abc123', title: 'Probe', rom: '/x.gb', web: null, chat: null }
  const query = { data: { url: 'http://127.0.0.1:1/p/index.html' }, isFetching: false }
  const player = { game, query, focused: false, capturesOpen: false, rebuilt: false, ask() {}, fullScreen() {}, later() {}, reload() {}, refresh() {}, toggleCaptures() {} }
  const ctx = { storage: { get: (key, fallback) => fallback, set() {} } }

  PAGE_SLOTS.contributions = name => (name === 'emulator.barActions' ? [Probe] : original(name))
  try {
    const onPage = await render(jsx(EMULATOR_PAGE.Page, { shell: { ctx, go() {}, hardwareOn: true, player } }))

    assert.deepEqual(seen, [['ctx', 'game', 'go', 'hardwareOn']], 'on the Emulator page')
    await act(async () => onPage.root.unmount())
    seen.length = 0
    scenario.games = { data: { games: [game], device: { hardwareEnabled: true } }, isFetching: false }
    scenario.player = query
    assert.ok(openSideEmulator(ctx, game), 'the tab opened')
    const beside = await render(scenario.workspaces.at(-1).options.render())

    assert.deepEqual(seen.at(-1), ['ctx', 'game', 'hardwareOn'], 'beside the chat')
    await act(async () => beside.root.unmount())
  } finally {
    PAGE_SLOTS.contributions = original
  }
})

test('an empty slot renders nothing', async () => {
  const slots = createSlots()

  slots.declare('host.panel', 'host', 'a panel')
  const { node, root } = await render(jsxs('div', { children: ['before', jsx(Slot, { name: 'host.panel', props: {}, slots })] }))

  assert.equal(node.innerHTML, '<div>before</div>')
  await act(async () => root.unmount())
})

test('a contribution renders in its slot with the props the host gives, in page order', async () => {
  const slots = createSlots()
  const Item = ({ who }) => jsx('b', { children: `hello ${who}` })
  const Other = ({ who }) => jsx('i', { children: `bye ${who}` })

  wirePages(
    [fakePage('host', { slots: { 'host.panel': 'a panel' } }), fakePage('one', { contributes: { 'host.panel': [Item] } }), fakePage('two', { contributes: { 'host.panel': [Other] } })],
    { events: createEvents(), slots }
  )

  const { node, root } = await render(jsx(Slot, { name: 'host.panel', props: { who: 'there' }, slots }))

  assert.equal(node.innerHTML, '<b>hello there</b><i>bye there</i>')
  await act(async () => root.unmount())
})

test('an unknown slot fails: rendering it, or contributing to it', () => {
  assert.throws(() => Slot({ name: 'games.nope' }), /unknown UI slot "games.nope"/)
  assert.ok(pageProblems([fakePage('a', { contributes: { 'b.panel': [Text('x')] } })]).some(problem => problem.includes('contributes to "b.panel", which no page declares')))
  assert.ok(pageProblems([fakePage('a', { slots: { 'a.panel': 'doc' } }), fakePage('b', { contributes: { 'a.panel': ['not a component'] } })]).some(problem => problem.includes('must be a list of components')))
})

test('descriptors are checked: ids, labels, Page or tabs, unknown fields, descriptions', () => {
  const problems = pageProblems([{ id: 'Bad', label: '', colour: 'red', events: { 'Bad.x': '' } }, fakePage('home'), fakePage('home')])
  const text = problems.join('\n')

  for (const part of ['id must be a unique lowercase name', 'label must be', 'give the page a Page component, or tabs', 'unknown field "colour"', 'needs a one-line description']) {
    assert.ok(text.includes(part), part)
  }
})

test('a page with tabs gets a tab bar; the chosen tab is shown and remembered', async () => {
  const storage = {}
  const ctx = { storage: { get: (key, fallback) => storage[key] ?? fallback, set: (key, value) => { storage[key] = value } } }
  const page = { id: 'tools', label: 'Tools', tabs: [{ id: 'one', label: 'One', Page: Text('first tab') }, { id: 'two', label: 'Two', Page: Text('second tab') }] }

  assert.deepEqual(pageProblems([page]), [])

  const { node, root } = await render(jsx(PageView, { page, shell: { ctx } }))
  const tabs = [...node.querySelectorAll('[role="tab"]')]

  assert.deepEqual(tabs.map(tab => tab.textContent), ['One', 'Two'])
  assert.ok(node.textContent.includes('first tab'))
  await act(async () => tabs[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })))
  assert.ok(node.textContent.includes('second tab') && !node.textContent.includes('first tab'))
  assert.equal(storage['tab:tools'], 'two')
  assert.equal(node.querySelector('[aria-selected="true"]').textContent, 'Two')
  await act(async () => root.unmount())
})

test('the stylesheet holds every page rule once; Build after the narrow-pane rules', () => {
  const css = composeStyles(PAGES)

  for (const page of PAGES) {
    for (const chunk of page.css ?? []) {
      assert.equal(css.split(chunk).length, 2, `${page.id}'s css appears once`)
    }
  }

  const build = PAGES.find(page => page.id === 'build')

  assert.ok(css.indexOf(build.css[0]) > css.indexOf(RESPONSIVE_CSS))
})
