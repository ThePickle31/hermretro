// The shell's background layer (page/app/background-layer.js) and the backgrounds' registry: a page that asks for a
// background gets it before it paints; another page asking for the same one keeps it running; a page without one
// hides it, paused, and going back shows the same one again rather than starting it over.
// Run alone: node tests/page/background-layer.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><div id="root"></div>')

globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const { jsx, jsxs } = await import('react/jsx-runtime')
const { BACKGROUNDS } = await import('../../page/backgrounds/index.js')
const { Background } = await import('../../page/app/background.js')
const { BackgroundLayer } = await import('../../page/app/background-layer.js')

test('every background has a unique id, a start function and its own folder', () => {
  const ids = BACKGROUNDS.map(background => background.id)
  assert.equal(new Set(ids).size, ids.length, `ids repeat: ${ids}`)
  for (const background of BACKGROUNDS) {
    assert.match(background.id, /^[a-z0-9-]+$/)
    assert.equal(typeof background.start, 'function', background.id)
    assert.ok(Array.isArray(background.css ?? []), background.id)
  }
})

test('pages share a running background and get it back as they left it', async () => {
  const platformer = BACKGROUNDS.find(background => background.id === 'platformer')
  const real = platformer.start
  const runs = []
  platformer.start = ({ host, layer }) => {
    const run = { host, layer, stopped: false }
    runs.push(run)
    return () => { run.stopped = true }
  }
  const node = document.createElement('div')
  document.body.append(node)
  const root = createRoot(node)
  const page = content => act(async () => root.render(jsxs('div', { className: 'cs-pad', children: [jsx(BackgroundLayer, {}, 'bg'), content] })))
  const layer = () => node.querySelector('.cs-bg')

  try {
    await page(jsx('section', { children: jsx(Background, { id: 'platformer' }) }, 'build'))
    assert.equal(runs.length, 1, 'started once')
    assert.equal(layer().hidden, false)
    assert.equal(runs[0].host, node.querySelector('.cs-pad'), 'drawn in the page area')

    await page(jsx('article', { children: jsx(Background, { id: 'platformer' }) }, 'games'))
    assert.equal(runs.length, 1, 'another page with the same background: still the first run')
    assert.equal(layer().hidden, false)

    await page(jsx('main', {}, 'setup'))
    assert.equal(layer().hidden, true, 'a page without one: hidden')
    assert.equal(runs[0].stopped, false, 'kept, paused, not stopped')

    await page(jsx('section', { children: jsx(Background, { id: 'platformer' }) }, 'build'))
    assert.equal(layer().hidden, false)
    assert.equal(runs.length, 1, 'back to it: the same run carries on')

    const warned = []
    const warn = console.warn
    console.warn = text => warned.push(text)
    await page(jsx('section', { children: jsx(Background, { id: 'no-such-thing' }) }, 'other'))
    console.warn = warn
    assert.match(warned.join(), /no background "no-such-thing"/)
    assert.equal(layer().hidden, true, 'an unknown id shows nothing')

    await act(async () => root.unmount())
    assert.equal(runs[0].stopped, true, 'stopped with the page')
  } finally {
    platformer.start = real
    node.remove()
  }
})
