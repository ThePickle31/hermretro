// Running the platformer background (page/backgrounds/platformer/run.js) in the page area, behind the Build page's
// New Game form, with a fake world and a fake clock, in jsdom: it is built for the area alone (the form takes no
// part), keeps its world while the area keeps its size, follows the theme even under reduced motion, cleans up, and
// the header (with the game switcher's menu) stays above the form.
// Run alone: node tests/page/platformer-run.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()
const { JSDOM } = await import('jsdom')
const { runAttract } = await import('../../page/backgrounds/platformer/run.js')
const { BUILD_PAGE } = await import('../../page/pages/build/index.js')
const { SHELL_CSS } = await import('../../page/app/shell.css.js')

const NIGHT = 'rgb(16, 18, 24)', DAY = 'rgb(250, 250, 250)'
// The stylesheet the Build page actually gets (after the shell's): a rule dropped from its composition fails here
// even if it is still in new-game-glass.css.js.
const BUILD_CSS = SHELL_CSS + BUILD_PAGE.css.join('\n')

/** The New Game area with its form, a fake world, a fake clock and frame queue. */
function setup({ still = false } = {}) {
  const dom = new JSDOM(`<!doctype html><div class="cs-pad build" style="background-color: ${NIGHT}">
    <div class="cs-bg" data-bg="platformer"><canvas></canvas></div><div class="cs-b-chat cs-b-attract"><header class="cs-b-head"></header>
    <div class="cs-b-new"><h1></h1><div class="cs-b-comp"><textarea></textarea></div></div></div></div>`)
  const doc = dom.window.document, host = doc.querySelector('.cs-pad'), form = doc.querySelector('.cs-b-new')
  // layout: jsdom has none, so the area and the canvas report a rectangle
  const box = (el, x, y, w, h) => { el.getBoundingClientRect = () => ({ left: x, top: y, right: x + w, bottom: y + h, width: w, height: h }) }
  box(host, 0, 0, 1200, 800); box(doc.querySelector('canvas'), 0, 0, 1200, 800)
  const worlds = [], frames = [], timers = []
  const makeWorld = seed => {
    const w = { seed, builds: [], palettes: [], renders: 0, steps: 0, score: 0, coinsGot: 0 }
    Object.assign(w, {
      L: { groundY: 380 }, build: (W, H, boxes) => w.builds.push({ W, H, boxes }), attach: (cv, sky) => w.palettes.push(sky), setPalette: sky => w.palettes.push(sky),
      step: () => w.steps++, render: () => w.renders++
    })
    worlds.push(w)
    return w
  }
  const motion = { matches: still, listeners: [], addEventListener(_, f) { this.listeners.push(f) }, removeEventListener(_, f) { this.listeners = this.listeners.filter(g => g !== f) } }
  let observed = null, resized = null, now = 0
  const env = {
    raf: f => frames.push(f), caf: () => {}, setTimer: f => timers.push(f), clearTimer: () => {},
    getStyle: el => dom.window.getComputedStyle(el), isHidden: () => false, motion,
    observe: (els, onChange) => { observed = els; resized = onChange; return () => { observed = null } }
  }
  const stop = runAttract({ host, canvasEl: doc.querySelector('canvas'), makeWorld, env, seed: 5 })
  const tick = (n = 1) => { for (let i = 0; i < n; i++) { now += 1000 / 60; const f = frames.shift(); f?.(now) } }
  const fireTimers = () => { while (timers.length) timers.shift()() }
  return { dom, doc, host, form, worlds, tick, fireTimers, stop, motion, observed: () => observed, resize: () => resized() }
}

test('the level is built for the area alone, not around the form, and keeps going', () => {
  const t = setup()
  assert.equal(t.worlds.length, 1)
  assert.deepEqual(t.worlds[0].builds[0], { W: 600, H: 400, boxes: { flat: [] } }, 'built from the area size only')
  assert.deepEqual(t.observed(), [t.host], 'only the area is watched for size changes')
  assert.deepEqual(t.worlds[0].palettes, ['night'])
  t.tick(30)
  assert.ok(t.worlds[0].steps > 20 && t.worlds[0].renders > 20)
  t.stop()
  assert.equal(t.observed(), null, 'resize watching stopped')
  assert.equal(t.motion.listeners.length, 0, 'reduced-motion listener removed')
})

test('a resize to the same size (the page shown again, or another page with this background) keeps the world', () => {
  const t = setup()
  t.worlds[0].W = 600; t.worlds[0].H = 400
  t.resize(); t.fireTimers()
  assert.equal(t.worlds.length, 1, 'she keeps playing the same level')
  t.host.getBoundingClientRect = () => ({ left: 0, top: 0, right: 1000, bottom: 800, width: 1000, height: 800 })
  t.resize(); t.fireTimers()
  assert.equal(t.worlds.length, 2, 'a new size: a level that fits it')
  t.stop()
})

test('the shelf\'s span is kept flat, and the page learns where the ground is', () => {
  const t = setup()
  const shelf = t.doc.createElement('nav')
  let width = 400
  shelf.setAttribute('data-at-flat', '')
  shelf.getBoundingClientRect = () => ({ left: 400, right: 400 + width, top: 600, bottom: 760, width, height: 160 })
  t.host.append(shelf)
  assert.equal(t.host.style.getPropertyValue('--cs-at-ground'), '40px', '(400 - 380) game px from the bottom, x2')
  t.tick(30)
  t.fireTimers()
  assert.equal(t.worlds.length, 2, 'the shelf appeared: rebuilt')
  assert.deepEqual(t.worlds[1].builds[0].boxes, { flat: [[200, 400]] }, 'its span in game pixels')
  t.tick(30)
  t.fireTimers()
  assert.equal(t.worlds.length, 2, 'nothing moved: no rebuild')
  width = 520
  t.tick(30)
  t.fireTimers()
  assert.deepEqual(t.worlds[2].builds[0].boxes, { flat: [[200, 460]] }, 'a cartridge more: rebuilt with the wider span')
  t.stop()
  assert.equal(t.host.style.getPropertyValue('--cs-at-ground'), '', 'removed on stop')
})

test('scrolling the form or typing in it leaves the game running', () => {
  const t = setup()
  const ta = t.doc.querySelector('textarea')
  t.form.scrollTop = 120
  t.form.dispatchEvent(new t.dom.window.Event('scroll'))
  for (let i = 0; i < 8; i++) ta.dispatchEvent(new t.dom.window.Event('input', { bubbles: true }))
  t.fireTimers()
  assert.equal(t.worlds.length, 1, 'the same world: she is not sent back to the start')
  t.stop()
})

test('the page colour is set on the area, where the title and the frosted composer (in the form) inherit it', () => {
  const t = setup()
  const style = t.doc.createElement('style')
  style.textContent = BUILD_CSS
  t.doc.head.append(style)
  const get = sel => t.dom.window.getComputedStyle(t.doc.querySelector(sel)).getPropertyValue('--cs-at-bg').trim()
  assert.equal(get('h1'), NIGHT, 'the title inherits it')
  assert.equal(get('.cs-b-comp'), NIGHT, 'the composer inherits it')
  t.stop()
  assert.equal(t.host.style.getPropertyValue('--cs-at-bg'), '', 'removed on stop')
})

test('the composer and the two frosted choice states are glass over the level, from the Build stylesheet', () => {
  const t = setup()
  const style = t.doc.createElement('style')
  style.textContent = BUILD_CSS
  t.doc.head.append(style)
  const opt = cls => {
    const el = t.doc.createElement('button')
    el.className = cls
    t.form.append(el)
    return el
  }
  const plain = opt('cs-b-opt'), selected = opt('cs-b-opt on')
  const css = el => t.dom.window.getComputedStyle(el)  // the cascaded rule, in the page's own order
  const bg = el => css(el).getPropertyValue('background').replace(/\s+/g, ' ').trim()
  for (const [name, el] of [
    ['.cs-b-new .cs-b-comp', t.doc.querySelector('.cs-b-new .cs-b-comp')],
    ['.cs-b-opt (unselected)', plain],
    ['.cs-b-opt.on (selected)', selected]
  ]) {
    assert.match(css(el).getPropertyValue('backdrop-filter'), /blur\(/, `${name} blurs the level behind it`)
  }
  assert.equal(bg(t.doc.querySelector('.cs-b-new .cs-b-comp')), 'var(--cs-at-glass)', 'the composer is see-through page colour')
  assert.equal(bg(plain), 'var(--cs-at-glass)', 'an unselected choice is see-through page colour')
  assert.equal(
    bg(selected),
    'color-mix(in srgb, var(--ui-accent) 10%, var(--cs-at-glass))',
    'a selected choice tints the glass with the accent, not the plain form colour'
  )
  t.stop()
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
  assert.equal(t.host.style.getPropertyValue('--cs-at-bg'), DAY, 'the glass and the title glow follow the theme')
  t.stop()
})

test('the header (and the game switcher\'s menu) stays above the form; the level stays behind both', () => {
  const t = setup()
  const style = t.doc.createElement('style')
  style.textContent = BUILD_CSS
  t.doc.head.append(style)
  const z = sel => Number(t.dom.window.getComputedStyle(t.doc.querySelector(sel)).zIndex)
  assert.ok(z('.cs-b-head') > z('.cs-b-new'), `header ${z('.cs-b-head')} over form ${z('.cs-b-new')}`)
  assert.ok(z('.cs-b-new') > z('.cs-bg'), 'the form over the level')
  t.stop()
})

test('the composer stays above the frosted choice cards, so its model picker opens over them', () => {
  const t = setup()
  const style = t.doc.createElement('style')
  style.textContent = BUILD_CSS
  t.doc.head.append(style)
  const opt = t.doc.createElement('button')
  opt.className = 'cs-b-opt'
  t.form.append(opt)
  const css = sel => t.dom.window.getComputedStyle(t.doc.querySelector(sel))
  assert.equal(css('.cs-b-comp').position, 'relative', 'the composer is positioned')
  assert.ok(Number(css('.cs-b-comp').zIndex) > (Number(css('.cs-b-opt').zIndex) || 0), `composer ${css('.cs-b-comp').zIndex} over the cards ${css('.cs-b-opt').zIndex}`)
  t.stop()
})
