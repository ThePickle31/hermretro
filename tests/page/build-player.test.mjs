// The inline player's pure logic: whole-number scaling and the play-test checklist.
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

// The modules import each other through the page's aliases: resolve those first (aliases.mjs).
registerAliases()

const { checklist, progress, withReport, withTick } = await import('../../page/pages/build/player/checks.js')
const { playerSize } = await import('../../page/pages/build/player/scale.js')
const { cleanImage, cleanMarks, cleanNote } = await import('../../page/shared/player/frame-values.js')
const { DEVICE_SCREEN_SHARE } = await import('../../page/shared/player/protocol.js')
const { targetLabel, targetRect } = await import('../../page/shared/player/targets.js')

test('Fit picks the largest whole step for the bare screen and for the handheld', () => {
  assert.deepEqual(playerSize('screen', 'fit', { width: 856, height: 942 }), { width: 800, height: 720, step: 5, fits: ['fit', 2, 3, 4] })
  const device = playerSize('device', 'fit', { width: 856, height: 942 })

  assert.deepEqual([device.step, device.fits], [2, ['fit', 2]])
  assert.ok(Math.abs(device.width * DEVICE_SCREEN_SHARE - 320) < 1e-9, 'the handheld\'s screen is exactly 2 \u00d7 160')
})

test('a fixed scale that does not fit falls back to the largest that does, and never goes below 1', () => {
  assert.equal(playerSize('screen', 4, { width: 500, height: 600 }).step, 3)
  assert.equal(playerSize('screen', 2, { width: 900, height: 900 }).step, 2)
  assert.equal(playerSize('screen', 'fit', { width: 100, height: 100 }).step, 1)
})

const r2 = { tested: ['Fly up to the canaries', 'Hover'], untested: ['Fly into a blue jay'] }

test('checks come from the report, untested first, deduplicated', () => {
  const items = checklist({ ...r2, tested: [...r2.tested, 'hover '] }, 2)

  assert.deepEqual(items.map(item => [item.text, item.state]), [['Fly into a blue jay', 'untested'], ['Fly up to the canaries', 'todo'], ['Hover', 'todo']])
})

test('ticks and reports are kept per build; a reported check comes back as fixed on the next build', () => {
  let saved = withTick({}, 2, 'fly up to the canaries', true)

  saved = withReport(saved, 2, 'fly into a blue jay', 'Fly into a blue jay')
  assert.deepEqual(progress(checklist(r2, 2, saved)), { done: 1, total: 3, left: 1, complete: false })
  assert.equal(checklist(r2, 2, saved)[0].state, 'reported')

  const r3 = { tested: ['Bounce off'], untested: [] }

  assert.deepEqual(checklist(r3, 3, saved)[0], { key: 'fly into a blue jay', text: 'Fly into a blue jay', state: 'fixed', from: 2 })

  saved = withTick(saved, 3, 'fly into a blue jay', true)
  assert.equal(checklist(r3, 3, saved)[0].state, 'done', 'ticked on this build: still shown, done')
  assert.ok(!checklist(r3, 4, saved).some(item => item.key === 'fly into a blue jay'), 'settled on a later build')
})

test('a check that is only reported is not "all checked"; one ticked after its report is settled', () => {
  const one = { tested: [], untested: ['Fly into a blue jay'] }
  let saved = withReport({}, 2, 'fly into a blue jay', 'Fly into a blue jay')

  assert.deepEqual(progress(checklist(one, 2, saved)), { done: 0, total: 1, left: 0, complete: false })
  saved = withTick(saved, 2, 'fly into a blue jay', true)
  assert.deepEqual(checklist({ tested: [], untested: [] }, 3, saved), [], 'it worked after all: it does not come back')
})

test('a test-plan check is one item by its ID: failed first, its result on a later build replaces it', () => {
  const b1 = { tested: ['Hover'], untested: [], checks: [{ id: 'T1', text: 'Gate stays shut', result: 'failed' }, { id: 'AUD1', text: 'Chime', result: 'needs review' }, { id: 'T2', text: 'Ending', result: 'not run' }] }

  assert.deepEqual(checklist(b1, 1).map(item => [item.key, item.text, item.state]), [
    ['#t1', 'T1 \u00B7 Gate stays shut', 'failed'],
    ['#aud1', 'AUD1 \u00B7 Chime', 'review'],
    ['#t2', 'T2 \u00B7 Ending', 'untested'],
    ['hover', 'Hover', 'todo']
  ])

  const saved = withReport({}, 1, '#t1', 'T1 \u00B7 Gate stays shut')
  const b2 = { tested: [], untested: [], checks: [{ id: 't1', text: 'Gate stays shut with 2 seeds', result: 'passed' }] }

  assert.deepEqual(checklist(b2, 2, saved), [{ key: '#t1', text: 'T1 \u00B7 Gate stays shut', state: 'fixed', from: 1 }])
  assert.deepEqual(checklist(b2, 2).map(item => item.state), ['todo'])
})

test('what the frame posts is checked before the page uses it', () => {
  const png = 'data:image/png;base64,iVBORw0KGgo='

  assert.equal(cleanImage(png), png)
  assert.equal(cleanImage('https://example.com/x.png'), '')
  assert.equal(cleanImage({}), '')
  const [mark] = cleanMarks([{ n: 'x', id: 'a', name: { bad: 1 }, role: 'game-sprite', colors: ['#112233', 'url(x)'], original: ['#000000', '#ffffff'], image: 'javascript:1', metadata: { Hardware: 7, Tile: { x: 1 } } }, { id: 7 }])

  assert.deepEqual(mark, { n: 1, id: 'a', name: '', role: 'game-sprite', metadata: { Hardware: 7, Tile: '' }, colors: ['#112233'], original: ['#112233'], image: '' })
  assert.equal(cleanMarks(Array.from({ length: 50 }, (_, index) => ({ id: String(index) }))).length, 20)
  assert.deepEqual(cleanNote({ target: null, note: 3, image: png }), { target: { name: '', role: '', metadata: {} }, note: '', image: png })
})

test('the engine names targets in plain words, and its metadata gives the box', () => {
  assert.equal(targetLabel('Inferred sprite group; 4 parts', 'game-sprite'), 'Sprite \u00b7 4 parts')
  assert.equal(targetLabel('Sprite 12; tile 3A', 'game-sprite'), 'Sprite part')
  assert.equal(targetLabel('Background tile 3A', 'game-background'), 'Background tile')
  assert.deepEqual(targetRect({ Hardware: '84,36 16x16px; Inferred group' }), { x: 84, y: 36, w: 16, h: 16 })
  assert.equal(targetRect({}), null)
})
