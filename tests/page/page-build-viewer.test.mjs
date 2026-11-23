// The Build asset viewer keeps focus while a sprite animates and loads only the scene being viewed.
// Run alone: node tests/page/page-build-viewer.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'
import { mock } from 'node:test'
import { runScenario } from './harness.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, dom, key, mount, page, scenario, settle, typeInto }) => {
  const game = 'fff666fff666'
  const projectRoot = '/home/u/games/FrogPost'
  const sprite = `${projectRoot}/assets/sprites/frog.png`
  const first = `${projectRoot}/assets/backgrounds/pond.png`
  const second = `${projectRoot}/assets/backgrounds/cave.png`
  const actor = `${projectRoot}/assets/sprites/newt.png`
  const scenes = [
    { id: 'pond', name: 'Pond', background: first, actors: [{ sprite }, { sprite: actor }] },
    { id: 'cave', name: 'Cave', background: second, actors: [{ sprite }] }
  ]
  const requested = new Set()
  const dataUrl = 'data:image/png;base64,AA=='
  const imagePrototype = dom.window.HTMLImageElement.prototype
  const imageSrc = Object.getOwnPropertyDescriptor(imagePrototype, 'src')

  // jsdom does not decode image data. Signal load so the viewer draws its normal stage.
  Object.defineProperties(imagePrototype, {
    src: { ...imageSrc, set(value) { imageSrc.set.call(this, value); queueMicrotask(() => this.onload?.()) } },
    naturalWidth: { get: () => 16 },
    naturalHeight: { get: () => 16 }
  })
  dom.window.HTMLCanvasElement.prototype.getContext = () => null

  buildScenario({ selected: game })
  scenario.games = answered({
    games: [{ id: game, title: 'Frog Post', projectRoot, kind: 'gbstudio', state: 'ready',
      rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
    device: { hardwareEnabled: false, skipped: true }
  })
  scenario.byMethod['session.resume'] = params => ({
    session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
      { role: 'user', content: 'Draw a frog.', timestamp: 1000 },
      { role: 'assistant', content: `MEDIA:${sprite}`, timestamp: 1001 }
    ]
  })
  scenario.byMethod['plugin.hermretro.asset'] = ({ path }) => {
    requested.add(path)

    return { ok: true, path, name: path.split('/').at(-1), kind: path === sprite ? 'sprite' : 'image', width: 16, height: 16, dataUrl }
  }
  scenario.byMethod['plugin.hermretro.asset_info'] = ({ path }) => ({
    ok: true, path, kind: 'sprite', scenes,
    sprite: { name: 'Frog', canvasWidth: 16, canvasHeight: 16, animSpeed: 5,
      animations: [{ slot: 0, name: 'Walk right', frames: [[{ sliceX: 0 }], [{ sliceX: 8 }]] }] }
  })

  const view = await mount(page)
  await settle()
  const opener = view.node.querySelector('button[aria-label="Look closer at frog.png"]')
  assert.ok(opener)
  mock.timers.enable({ apis: ['setInterval'] })
  try {
    await act(async () => opener.click())
    await settle()
    const dialog = view.node.querySelector('[role="dialog"]')
    const active = () => dom.window.document.activeElement
    const selectedFrame = () => dialog.querySelector('.cs-v-frame[aria-pressed="true"]')?.getAttribute('aria-label')
    check('the dialog takes focus when it opens', () => assert.ok(active() === dialog))

    const controls = [
      dialog.querySelector('[aria-label="Close"]'),
      [...dialog.querySelectorAll('button')].find(button => button.textContent === 'Change'),
      dialog.querySelector('[aria-label="Frame 2"]')
    ]
    for (const button of controls) {
      await act(async () => button.focus())
      const space = new dom.window.KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true })

      await act(async () => button.dispatchEvent(space))
      check(`Space preserves native activation on ${button.getAttribute('aria-label') ?? button.textContent}`, () => {
        assert.equal(space.defaultPrevented, false)
        assert.ok(dialog.querySelector('[aria-label="Pause"]'))
      })
    }

    await act(async () => dialog.focus())
    await key('keydown', ' ', dialog)
    check('Space on the dialog pauses the animation', () => assert.ok(dialog.querySelector('[aria-label="Play"]')))
    await key('keydown', ' ', dialog)

    await click('Change', dialog)
    const input = dialog.querySelector('textarea')
    check('Change focuses its text box', () => assert.ok(active() === input))
    const before = selectedFrame()

    await typeInto(input, 'Make')
    await act(async () => mock.timers.tick(100))
    check('the sprite keeps animating while the text box has focus', () => {
      assert.ok(before)
      assert.ok(selectedFrame())
      assert.notEqual(selectedFrame(), before)
      assert.ok(active() === input)
    })
    await key('keydown', '.', input)
    await typeInto(input, 'Make the frog green.')
    await act(async () => mock.timers.tick(100))
    check('the second tick leaves the draft and focus in the text box', () => {
      assert.equal(selectedFrame(), before)
      assert.ok(active() === input)
      assert.equal(input.value, 'Make the frog green.')
    })
    check('opening on Animation does not fetch the scenes', () => assert.deepEqual([...requested], [sprite]))

    await click('In game', dialog)
    await settle()
    check('In game loads the first scene and its actors only', () => {
      assert.deepEqual([...requested].sort(), [sprite, first, actor].sort())
    })
    await click('Cave', dialog)
    await settle()
    check('selecting another scene loads its images', () => {
      assert.deepEqual([...requested].sort(), [sprite, first, actor, second].sort())
    })
    await click('Details', dialog)
    await click('Change', dialog)
    const reopened = dialog.querySelector('textarea')
    check('returning to Change focuses the text box and keeps the draft', () => {
      assert.ok(active() === reopened)
      assert.equal(reopened.value, 'Make the frog green.')
    })
    await key('keydown', 'Escape', reopened)
    check('Escape closes the viewer and restores the opener focus', () => {
      assert.equal(view.node.querySelector('[role="dialog"]'), null)
      assert.ok(active() === opener)
    })
  } finally {
    await view.close()
    mock.timers.reset()
  }
})
