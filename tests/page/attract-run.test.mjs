// Running the New Game level in the page (page/pages/build/attract/run.js) with a fake world and a fake clock, in
// jsdom: it rebuilds when the form scrolls, follows the theme even under reduced motion, cleans up, and the header
// (with the game switcher's menu) stays above the form.
// Run alone: node tests/page/attract-run.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()
const { JSDOM } = await import('jsdom')
const { runAttract } = await import('../../page/pages/build/attract/run.js')
const { ATTRACT_CSS } = await import('../../page/pages/build/attract/attract.css.js')

const NIGHT = 'rgb(16, 18, 24)', DAY = 'rgb(250, 250, 250)'

/** The New Game area with its form, a fake world, a fake clock and frame queue. */
function setup({ still = false } = {}) {
  const dom = new JSDOM(`<!doctype html><div class="cs-b-chat cs-b-attract" style="background-color: ${NIGHT}">
    <div class="cs-at"><canvas></canvas></div><header class="cs-b-head"></header>
    <div class="cs-b-new"><h1 data-plat="title"></h1><div data-plat="composer"><textarea></textarea></div></div></div>`)
  const doc = dom.window.document, host = doc.querySelector('.cs-b-chat'), form = doc.querySelector('.cs-b-new')
  // layout: jsdom has none, so each box reports a rectangle that moves with the form's scroll position
  const box = (el, x, y, w, h, scrolls) => { el.getBoundingClientRect = () => { const top = y - (scrolls ? form.scrollTop : 0); return { left: x, top, right: x + w, bottom: top + h, width: w, height: h } } }
  box(host, 0, 0, 1200, 800); box(doc.querySelector('canvas'), 0, 0, 1200, 800)
  box(doc.querySelector('h1'), 400, 200, 400, 100, true); box(doc.querySelector('[data-plat="composer"]'), 300, 320, 600, 120, true)
  const worlds = [], frames = [], timers = []
  const makeWorld = seed => {
    const w = { seed, builds: [], palettes: [], renders: 0, steps: 0, score: 0, coinsGot: 0, typed: 0 }
    Object.assign(w, {
      build: (W, H, boxes) => w.builds.push({ W, H, boxes }), attach: (cv, sky) => w.palettes.push(sky), setPalette: sky => w.palettes.push(sky),
      step: () => w.steps++, render: () => w.renders++, typingCoin: () => w.typed++
    })
    worlds.push(w)
    return w
  }
  const motion = { matches: still, listeners: [], addEventListener(_, f) { this.listeners.push(f) }, removeEventListener(_, f) { this.listeners = this.listeners.filter(g => g !== f) } }
  let observed = null, now = 0
  const env = {
    raf: f => frames.push(f), caf: () => {}, setTimer: f => timers.push(f), clearTimer: () => {},
    getStyle: el => dom.window.getComputedStyle(el), isHidden: () => false, motion,
    observe: els => { observed = els; return () => { observed = null } }
  }
  const layer = doc.querySelector('.cs-at')
  const stop = runAttract({ host, layer, canvasEl: doc.querySelector('canvas'), makeWorld, env, seed: 5 })
  const tick = (n = 1) => { for (let i = 0; i < n; i++) { now += 1000 / 60; const f = frames.shift(); f?.(now) } }
  const fireTimers = () => { while (timers.length) timers.shift()() }
  return { dom, doc, host, form, layer, worlds, tick, fireTimers, stop, motion, observed: () => observed }
}

test('the level is built around the form and keeps going', () => {
  const t = setup()
  assert.equal(t.worlds.length, 1)
  assert.deepEqual(t.worlds[0].builds[0].boxes.map(b => b.kind), ['title', 'composer'])
  assert.deepEqual(t.worlds[0].palettes, ['night'])
  t.tick(30)
  assert.ok(t.worlds[0].steps > 20 && t.worlds[0].renders > 20)
  t.stop()
})

test('scrolling the form rebuilds the level at the boxes\' new places', () => {
  const t = setup()
  const before = t.worlds[0].builds[0].boxes.find(b => b.kind === 'composer').y
  t.form.scrollTop = 120
  t.form.dispatchEvent(new t.dom.window.Event('scroll')) // scroll does not bubble: run.js listens in the capture phase
  t.fireTimers()
  assert.equal(t.worlds.length, 2, 'a new world after the scroll')
  assert.equal(t.worlds[1].builds[0].boxes.find(b => b.kind === 'composer').y, before - 60, 'the composer moved up 120 px = 60 game px')
  t.stop()
  t.form.dispatchEvent(new t.dom.window.Event('scroll'))
  t.fireTimers()
  assert.equal(t.worlds.length, 2, 'nothing after stop')
  assert.equal(t.observed(), null, 'resize watching stopped')
  assert.equal(t.motion.listeners.length, 0, 'reduced-motion listener removed')
})

test('under reduced motion it draws one still frame and repaints it when the theme changes', () => {
  const t = setup({ still: true })
  const w = t.worlds[0]
  assert.equal(w.steps, 90, 'settled once')
  const renders = w.renders
  t.tick(120)
  assert.equal(w.steps, 90, 'no animation')
  assert.equal(w.renders, renders, 'no repaint while nothing changed')
  t.host.style.backgroundColor = DAY
  t.tick(31)
  assert.deepEqual(w.palettes, ['night', 'day'])
  assert.ok(w.renders > renders, 'the still frame repainted in the day palette')
  assert.equal(t.layer.style.getPropertyValue('--cs-at-bg'), DAY, 'the spotlight follows the theme')
  t.stop()
})

test('typing in the composer pops a coin now and then', () => {
  const t = setup()
  const ta = t.doc.querySelector('textarea')
  for (let i = 0; i < 8; i++) ta.dispatchEvent(new t.dom.window.Event('input', { bubbles: true }))
  assert.equal(t.worlds[0].typed, 2)
  t.stop()
})

test('the header (and the game switcher\'s menu) stays above the form; the level stays behind both', () => {
  const t = setup()
  const style = t.doc.createElement('style')
  style.textContent = ATTRACT_CSS
  t.doc.head.append(style)
  const z = sel => Number(t.dom.window.getComputedStyle(t.doc.querySelector(sel)).zIndex)
  assert.ok(z('.cs-b-head') > z('.cs-b-new'), `header ${z('.cs-b-head')} over form ${z('.cs-b-new')}`)
  assert.ok(z('.cs-b-new') > z('.cs-at'), 'the form over the level')
  t.stop()
})
