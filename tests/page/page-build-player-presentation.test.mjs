// A presentation belongs to its game, including when a running New Game first gets a library entry.
import assert from 'node:assert/strict'

import { frogPost, lamplight, resumeConversation } from './frog-post-fixture.mjs'
import { runScenario } from './harness.mjs'

const playerUrl = gameId => `http://127.0.0.1:4567/tok/${gameId}/index.html`
const playable = game => ({ ...game, state: 'ready', webExport: true, web: { sha256: `web-${game.id}`, builtAt: Date.now() / 1000 } })

function presentation(game, runtime, presentedAt) {
  return {
    type: 'tool.complete',
    session_id: runtime,
    payload: {
      tool_id: `present-${game.id}`,
      name: 'chromatic_present_game',
      args: {},
      result: { ok: true, studio: { gameId: game.id, title: game.title, note: `Try ${game.title}.`, presentedAt, buildConversation: true } }
    }
  }
}

function buildView(node, act, scenario) {
  const frame = () => node.querySelector('.cs-ip iframe')
  const frameUrl = () => frame()?.getAttribute('src')?.split('?')[0] ?? null
  const assertClosed = () => {
    assert.equal(frameUrl(), null, 'no game frame should be open')
    assert.equal(Boolean(node.querySelector('.cs-ip')), false, 'the inline player should be closed')
  }
  return {
    assertSelected: (id, title) => {
      assert.equal(scenario.storage.buildSelected, id)
      assert.equal(node.querySelector('.cs-b-sw h2')?.textContent, title)
    },
    assertBusy: expected => assert.equal(Boolean(node.querySelector('button[aria-label="Stop"]')), expected),
    assertClosed,
    assertPlaying: game => {
      assert.equal(frameUrl(), playerUrl(game.id))
      assert.equal(frame().getAttribute('title'), `${game.title} in ModRetro's Chromatic player`)
      assert.equal(node.querySelectorAll('.cs-ip iframe').length, 1)
    },
    play: () => act(async () => { node.querySelector('.cs-b-pc-go').click() }),
    closePlayer: () => act(async () => { node.querySelector('button[aria-label="Close the game"]').click() }),
    selectGame: async game => {
      await act(async () => { node.querySelector('.cs-b-sw').click() })
      const item = [...node.querySelectorAll('.cs-b-sw-list button')].find(button => button.querySelector('b')?.textContent === game.title)
      assert.ok(item, `the switcher lists ${game.title}`)
      await act(async () => { item.click() })
    }
  }
}

async function switchAfterPresentation({ act, answered, buildScenario, check, click, emit, mount, page, scenario, settle, typeInto }) {
  const frog = playable(frogPost({ session: { storedId: 'st-frog' } }))
  const comet = playable({
    id: 'abc123abc123', title: 'Comet Drift', kind: 'gbstudio', projectRoot: '/home/u/games/CometDrift', session: { storedId: 'st-comet' }
  })
  const runtime = 'rt-of-st-frog'
  const shown = presentation(frog, runtime, 100)
  buildScenario({ selected: comet.id })
  scenario.games = answered({ games: [frog, comet], device: { hardwareEnabled: false, skipped: true } })
  const view = await mount(page)
  const build = buildView(view.node, act, scenario)
  await settle()
  check('Comet Drift starts as an idle conversation with its player closed', () => {
    build.assertSelected(comet.id, comet.title)
    build.assertBusy(false)
    build.assertClosed()
    assert.ok(view.node.querySelector('.cs-b-pc-go'))
  })

  await build.selectGame(frog)
  await settle()
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'show me the game')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await act(async () => { emit(shown) })
  check('Frog Post receives a presentation while its turn is busy', () => {
    build.assertSelected(frog.id, frog.title)
    build.assertBusy(true)
    build.assertClosed()
    assert.equal(scenario.paramsByMethod['prompt.submit'].session_id, runtime)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Here it is.' } }) })
  await settle()
  check('Frog Post opens when its turn ends', () => build.assertPlaying(frog))

  await build.selectGame(comet)
  await settle()
  check('switching from presented Frog Post to idle Comet Drift leaves Comet Drift closed', () => {
    build.assertSelected(comet.id, comet.title)
    build.assertBusy(false)
    build.assertClosed()
    assert.ok(view.node.querySelector('.cs-b-pc-go'))
  })
  await build.play()
  check('Play still opens Comet Drift by request', () => build.assertPlaying(comet))
  await build.closePlayer()
  check('Close returns Comet Drift to its Play card', () => {
    build.assertClosed()
    assert.ok(view.node.querySelector('.cs-b-pc-go'))
  })

  await build.selectGame(frog)
  await settle()
  check('returning to closed Frog Post does not open its previously seen presentation', () => {
    build.assertSelected(frog.id, frog.title)
    build.assertClosed()
  })
  await act(async () => { emit({ ...shown, replayed: true }); emit(shown) })
  check('gateway replay and duplicate delivery leave Frog Post closed', () => {
    build.assertClosed()
    assert.equal(scenario.workspaces.length, 0)
  })
  await view.close()
}

async function presentPendingGame({ act, answered, buildScenario, check, emit, mount, page, scenario, settle, typeInto }) {
  const otherGame = playable(frogPost({ session: { storedId: 'st-frog' } }))
  const newGame = playable(lamplight())
  const stored = newGame.session.storedId
  const runtime = 'rt-new-1'
  const device = { hardwareEnabled: false, skipped: true }
  const idea = 'a lighthouse keeper in a storm'
  buildScenario()
  scenario.games = answered({ games: [otherGame], pending: [], device })
  scenario.byMethod['session.create'] = { session_id: runtime, stored_session_id: stored, messages: [] }
  scenario.byMethod['plugin.hermretro.build'] = { ok: true }
  scenario.byMethod['prompt.submit'] = () => {
    emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'first-turn' } })
    emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'first-build', name: 'chromatic_rom_build', args: {}, result: { result: 'Completed.' } } })
    emit(presentation(newGame, runtime, 101))
    return { ok: true }
  }
  const view = await mount(page)
  const build = buildView(view.node, act, scenario)
  await settle()

  await typeInto(view.node.querySelector('textarea[aria-label="Your game idea"]'), idea)
  await act(async () => { view.node.querySelector('button[aria-label="Start building"]').click() })
  await settle()
  scenario.games = answered({ games: [otherGame], pending: [{ storedId: stored, name: null }], device })
  await view.rerender()
  check('New Game starts a hidden pending conversation and sends the first turn', () => {
    assert.deepEqual(scenario.paramsByMethod['session.create'], { hidden: true, source: 'gui' })
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.build'], { action: 'start', stored, name: null, plan: false })
    assert.equal(scenario.paramsByMethod['prompt.submit'].session_id, runtime)
    assert.equal(scenario.paramsByMethod['prompt.submit'].text, idea)
    build.assertSelected(`pending:${stored}`, 'New game')
    build.assertBusy(true)
    build.assertClosed()
  })

  check('a presentation delivered before the first Send acknowledgement waits while Lamplight is pending', () => {
    build.assertSelected(`pending:${stored}`, 'New game')
    build.assertBusy(true)
    build.assertClosed()
    assert.equal(scenario.workspaces.length, 0)
  })

  // The library finally reports the binding. Hermes is still running the same turn.
  scenario.games = answered({ games: [newGame, otherGame], pending: [], device })
  await view.rerender()
  await settle()
  check('binding the game keeps the first turn running with no player open', () => {
    build.assertSelected(newGame.id, newGame.title)
    assert.equal(view.node.querySelector('.cs-b-user')?.textContent, idea)
    build.assertBusy(true)
    build.assertClosed()
  })

  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { turn_id: 'first-turn', text: 'Lamplight is ready.' } }) })
  await settle()
  check('the pending presentation opens exactly Lamplight once its turn completes', () => {
    build.assertSelected(newGame.id, newGame.title)
    build.assertBusy(false)
    build.assertPlaying(newGame)
    assert.match(view.node.querySelector('.cs-ip')?.textContent ?? '', /Try Lamplight\./)
    assert.equal(scenario.workspaces.length, 0)
  })
  await view.close()
}

async function presentOnFirstEdit({ act, answered, buildScenario, check, click, emit, mount, page, scenario, settle, typeInto }) {
  const game = playable(frogPost())
  const stored = 'st-first-edit'
  const runtime = `rt-of-${stored}`
  buildScenario({ selected: game.id })
  scenario.games = answered({ games: [game] })
  scenario.byMethod['session.create'] = { session_id: runtime, stored_session_id: stored, messages: [] }
  scenario.byMethod['plugin.hermretro.build'] = { ok: true }
  scenario.byMethod['prompt.submit'] = () => {
    emit(presentation(game, runtime, 102))
    return { ok: true }
  }
  const view = await mount(page)
  const build = buildView(view.node, act, scenario)
  await settle()
  build.assertClosed()
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'show me how it plays')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await settle()
  check('a presentation delivered during the first edit waits for the new conversation', () => {
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.build'], { action: 'bind', game: game.id, stored })
    build.assertBusy(true)
    build.assertClosed()
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Ready.' } }) })
  await settle()
  check('the existing game plays its first presentation after its conversation is attached', () => build.assertPlaying(game))
  await view.close()
}

await runScenario(async env => {
  env.holdTimers()
  env.scenario.byMethod['session.resume'] = resumeConversation()
  env.scenario.byMethod['prompt.submit'] = { ok: true }
  // Deliver each presentation once through tool.complete. A turn-end lookup brings nothing newer.
  env.scenario.byMethod['plugin.hermretro.presentations'] = { ok: true, presentations: [] }
  env.scenario.player = ([, , , gameId, sha]) => env.answered({ url: playerUrl(gameId), romSha256: sha })

  await switchAfterPresentation(env)
  await presentPendingGame(env)
  await presentOnFirstEdit(env)
})
