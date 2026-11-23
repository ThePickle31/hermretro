// The page registry (page/pages/index.js, app/registry.js), page events (app/events.js), UI slots
// (app/slots.js), tabs (app/page-view.js) and the stylesheet order (app/style.js), from the sources.
// Run alone: node tests/page/registry.test.mjs
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { registerAliases } from './aliases.mjs'
import { selectedPageTab, tabButton } from './harness.mjs'
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

  assert.deepEqual(PAGES.map(page => page.id), ['build', 'setup', 'games', 'emulator'])
  assert.deepEqual([...folders].sort(), PAGES.map(page => page.id).sort(), 'every folder under page/pages/ is a page in page/pages/index.js')
  assert.deepEqual(pageProblems(PAGES), [])
  assert.equal(NAV_PAGES, PAGES)

  for (const page of PAGES) {
    assert.equal(typeof page.label, 'string')
    assert.deepEqual(missingComponents(page), [], `${page.id} has a Page`)
  }
})

// A page whose tabs are the whole page drops its own Page (.agents/skills/hermretro-dev-page/references/adding.md, "A tab"): then each tab
// needs one instead.
function missingComponents(page) {
  if (page.tabs?.length) {
    return page.tabs.filter(tab => typeof tab.Page !== 'function').map(tab => `${page.id}/${tab.id} has no Page`)
  }

  return typeof page.Page === 'function' ? [] : [`${page.id} has no Page`]
}

test('a page needs a Page, or tabs that each have one', () => {
  assert.deepEqual(missingComponents(fakePage('plain')), [])
  assert.deepEqual(missingComponents({ id: 'tabbed', label: 'Tabbed', tabs: [{ id: 'one', label: 'One', Page: Text('one') }] }), [])
  assert.deepEqual(missingComponents({ id: 'tabbed', label: 'Tabbed', tabs: [{ id: 'one', label: 'One' }] }), ['tabbed/one has no Page'])
  assert.deepEqual(missingComponents({ id: 'bare', label: 'Bare' }), ['bare has no Page'])
})

/** Pages whose descriptor's own Page is defined in index.js rather than imported from one of its files. */
function pagesDefiningPage(sources) {
  return sources.flatMap(([id, text]) => {
    const name = text.match(/^ {2}Page: (\w+),?$/m)?.[1]

    return name && new RegExp(`^(?:export\\s+)?(?:async\\s+)?(?:function|const|let|class)\\s+${name}\\b`, 'm').test(text)
      ? [`page/pages/${id}/index.js defines ${name}. FIX: move it into page/pages/${id}/${id}-page.js, export it and import { ${name} } from './${id}-page.js' in index.js`]
      : []
  })
}

// A page's Page lives in its own file, so a tab can take it over as the first tab
// (a tab importing the page's index.js would be a cycle).
test("each page's own Page is imported into index.js from its own file, not defined there", () => {
  assert.equal(pagesDefiningPage([['probe', "function Probe() {}\nexport const PROBE_PAGE = {\n  id: 'probe',\n  Page: Probe,\n}"]]).length, 1)
  assert.deepEqual(pagesDefiningPage([['probe', "import { Probe } from './probe-page.js'\nexport const PROBE_PAGE = {\n  Page: Probe\n}"]]), [])
  const pagesDir = fileURLToPath(new URL('../../page/pages/', import.meta.url))
  const sources = readdirSync(pagesDir)
    .filter(id => statSync(path.join(pagesDir, id)).isDirectory())
    .map(id => [id, readFileSync(path.join(pagesDir, id, 'index.js'), 'utf8')])

  assert.deepEqual(pagesDefiningPage(sources), [])
})

test('events are declared once, by the page their name starts with', () => {
  const declared = PAGE_EVENTS.declared()

  assert.deepEqual([...declared.keys()].sort(), ['emulator.presented', 'games.coverRequested', 'setup.demoRequested', 'setup.firstIdea'])

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
  startPages({})
  startPages({}) // registering again replaces the listeners: nothing is handled twice

  emit('games.coverRequested', { game: { id: 'frog', session: { storedId: 'st-9', thisProfile: true, exists: true } }, prompt: 'Draw it' })
  assert.deepEqual(BUILD_INJECT.get()['st-9'], { seq: 1, text: 'Draw it' })

  emit('emulator.presented', { gameId: 'frog', seq: 3, note: 'try it', t: 5 })
  assert.deepEqual(BUILD_PRESENTED.get().frog, { seq: 3, note: 'try it', t: 5 })
})

// Filling a real slot changes only `expected` in the `filled` assertion below (a new, empty slot only the declared list); the
// empty case renders on a table of its own. A slot's contributions are listed in PAGES order
// (page/pages/index.js), whatever order the contributing pages were written in.
test('slots: the real ones are declared, and what fills them', () => {
  assert.deepEqual([...PAGE_SLOTS.declared().keys()].sort(), ['emulator.barActions', 'games.cardMenu'])
  const filled = Object.fromEntries([...PAGE_SLOTS.declared().keys()].map(name => [name, PAGE_SLOTS.contributions(name)]).filter(([, list]) => list.length))

  const expected = { 'emulator.barActions': [InstallButton] }
  const named = slots => JSON.stringify(Object.fromEntries(Object.entries(slots).map(([slot, list]) => [slot, list.map(item => item.name || '(anonymous)')])))

  assert.deepEqual(filled, expected, `slots filled: ${named(filled)}, expected ${named(expected)}\nFIX: when a page's contributes changed on purpose, change \`expected\` here (.agents/skills/hermretro-dev-page/references/adding.md, "A contribution to a slot")`)
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
  const problems = pageProblems([{ id: 'Bad', label: '', colour: 'red', events: { 'Bad.x': '' } }, fakePage('dup'), fakePage('dup')])
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
  assert.equal(selectedPageTab(node), 'One')
  await act(async () => tabButton(node, 'Two').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })))
  assert.ok(node.textContent.includes('second tab') && !node.textContent.includes('first tab'))
  assert.equal(storage['tab:tools'], 'two')
  assert.equal(selectedPageTab(node), 'Two')

  // Scoped: another tabbed page beside it does not change the answer for this one, and a page without tabs has none.
  const beside = await render(jsx(PageView, { page: { ...page, id: 'other' }, shell: { ctx } }))
  assert.equal(selectedPageTab(beside.node), 'One')
  assert.equal(selectedPageTab(node), 'Two')
  const plain = await render(jsx(PageView, { page: { id: 'plain', label: 'Plain', Page: Text('no tabs') }, shell: { ctx } }))
  assert.equal(selectedPageTab(plain.node), null)
  await act(async () => { root.unmount(); beside.root.unmount(); plain.root.unmount() })
})

// The shell every Page gets, from the real StudioPage, with a probe in Games' place.

// A shared component's class is styled by the shared stylesheets, not by one page's: removing that page (as Home was)
// must not leave the component bare on every other page.
test('every class a shared component sets (and the default of Screen) has a rule in the composed stylesheet', () => {
  const css = composeStyles(PAGES)
  const dir = path.join(ROOT, 'page', 'shared', 'ui')
  const used = new Set(readdirSync(dir).filter(name => name.endsWith('.js') && !name.endsWith('.css.js'))
    .flatMap(name => [...readFileSync(path.join(dir, name), 'utf8').matchAll(/className(?: = |: )'(cs-[a-z0-9-]+)/g)].map(match => match[1])))

  assert.ok(used.has('cs-foot') && used.has('cs-screen'), 'the scan finds the footer and the screen')
  assert.deepEqual([...used].filter(name => !new RegExp(`\\.${name}(?![\\w-])`).test(css)), [], 'FIX: style the class in page/shared/styles/ or page/app/shell.css.js')
})

test('the stylesheet holds each page rule once and sizes the inline player within its frame', () => {
  const css = composeStyles(PAGES)

  for (const page of PAGES) {
    for (const chunk of page.css ?? []) {
      assert.equal(css.split(chunk).length, 2, `${page.id}'s css appears once`)
    }
  }

  const fixture = new JSDOM('<div class="cs-pad flush"><div class="cs-ip-fit"><div class="cs-rp-stage"></div></div></div>')
  const doc = fixture.window.document
  const style = doc.createElement('style')

  style.textContent = css
  doc.head.appendChild(style)
  assert.equal(fixture.window.getComputedStyle(doc.querySelector('.cs-rp-stage')).height, '100%')
  fixture.window.close()
})
