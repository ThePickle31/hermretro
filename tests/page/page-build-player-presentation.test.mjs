// A presentation belongs to its game, including when a running New Game first gets a library entry.
import assert from 'node:assert/strict'

import { buildView, playable, playerUrl, presentation } from './build-player-fixture.mjs'
import { frogPost, lamplight, resumeConversation } from './frog-post-fixture.mjs'
import { runScenario } from './harness.mjs'

async function presentPendingGame({ act, answered, buildScenario, check, emit, mount, page, scenario, settle, typeInto }, historyOnly = false) {
  const otherGame = playable(frogPost({ session: { storedId: 'st-frog' } }))
  const newGame = playable(lamplight())
  if (historyOnly) {
    newGame.id = 'ccc333ccc333'
    newGame.session = { storedId: 'st-history-first' }
  }
  const stored = newGame.session.storedId
  const runtime = historyOnly ? 'rt-history-first' : 'rt-new-1'
  const device = { hardwareEnabled: false, skipped: true }
  const idea = 'a lighthouse keeper in a storm'
  buildScenario()
  scenario.games = answered({ games: [otherGame], pending: [], device })
  scenario.byMethod['session.create'] = { session_id: runtime, stored_session_id: stored, messages: [] }
  scenario.byMethod['plugin.hermretro.build'] = historyOnly ? { ok: true } : { ok: true, pending: { storedId: stored, name: null, createdAt: 100 } }
  let cursorAvailable = false
  if (historyOnly) {
    scenario.byMethod['plugin.hermretro.presentations'] = params => {
      if (params.cursorOnly && !cursorAvailable) throw new Error('Studio temporarily offline')
      return { ok: true, now: 900, presentations: params.cursorOnly ? [] : [{
        gameId: newGame.id, t: 899, sessionId: runtime, conversationId: stored, buildConversation: true
      }] }
    }
  }
  let acknowledge
  scenario.byMethod['prompt.submit'] = () => {
    emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'first-turn' } })
    emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'first-build', name: 'chromatic_rom_build', args: {}, result: { result: 'Completed.' } } })
    if (!historyOnly) emit(presentation(newGame, runtime, 101))
    return new Promise(resolve => { acknowledge = resolve })
  }
  const view = await mount(page)
  const build = buildView(view.node, act, scenario)
  await settle()

  await typeInto(view.node.querySelector('textarea[aria-label="Your game idea"]'), idea)
  await act(async () => { view.node.querySelector('button[aria-label="Start building"]').click() })
  await settle()
  assert.equal(typeof acknowledge, 'function', 'the first Send is awaiting acknowledgement')
  await build.selectGame(otherGame)
  await settle()
  check('another game can be selected while New Game waits for its first Send acknowledgement', () => {
    build.assertSelected(otherGame.id, otherGame.title)
    build.assertClosed()
  })
  await act(async () => { acknowledge({ ok: true }) })
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

  if (!historyOnly) check('a presentation delivered before the first Send acknowledgement waits while Lamplight is pending', () => {
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

  cursorAvailable = true
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { turn_id: 'first-turn', text: 'Lamplight is ready.' } }) })
  await settle()
  check(historyOnly ? 'New Game recovers its own first presentation after the cursor fails' : 'the pending presentation opens exactly Lamplight once its turn completes', () => {
    build.assertSelected(newGame.id, newGame.title)
    build.assertBusy(false)
    build.assertPlaying(newGame)
    if (!historyOnly) assert.match(view.node.querySelector('.cs-ip')?.textContent ?? '', /Try Lamplight\./)
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

async function reconnectBeforeBinding({ act, answered, buildScenario, check, emit, mount, notLoaded, page, scenario, settle, tab }) {
  const stored = 'st-reconnect'
  const runtime = `rt-of-${stored}`
  const game = playable({ ...lamplight(), session: { storedId: stored } })
  buildScenario({ selected: `pending:${stored}` })
  scenario.games = answered({ games: [], pending: [{ storedId: stored, name: game.title }] })
  const online = scenario.status
  const view = await mount(page)
  const build = buildView(view.node, act, scenario)
  const reconnect = async () => {
    scenario.status = notLoaded
    await view.rerender()
    assert.equal(view.node.querySelector('.cs-b-sw'), null, 'the outage unmounts Build')
    scenario.status = online
    await view.rerender()
  }
  await settle()
  await act(async () => {
    emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'before-outage' } })
    emit(presentation(game, runtime, 103))
    emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Ready to play.' } })
  })
  build.assertBusy(false)
  build.assertClosed()
  await reconnect()
  build.assertSelected(`pending:${stored}`, game.title)
  scenario.games = answered({ games: [game], pending: [] })
  await view.rerender()
  await settle()
  check('reconnect keeps the finished presentation until the shelf lists its game', () => {
    build.assertSelected(game.id, game.title)
    build.assertPlaying(game)
    assert.equal(scenario.workspaces.length, 0)
  })
  await reconnect()
  check('reconnecting while the presented game is open restores its frame', () => build.assertPlaying(game))
  await build.closePlayer()
  await reconnect()
  check('another reconnect leaves a dismissed presentation closed', build.assertClosed)
  await build.play()
  build.assertPlaying(game)
  await tab('Games')
  await tab('Build')
  check('leaving Build ends the player visit even when the same game is selected on return', () => {
    build.assertSelected(game.id, game.title)
    build.assertClosed()
  })
  await view.close()
}

await runScenario(async env => {
  env.holdTimers()
  env.scenario.byMethod['session.resume'] = resumeConversation()
  env.scenario.byMethod['prompt.submit'] = { ok: true }
  // Deliver each presentation once through tool.complete. A turn-end lookup brings nothing newer.
  env.scenario.byMethod['plugin.hermretro.presentations'] = { ok: true, now: 1, presentations: [] }
  env.scenario.player = ([, , , gameId, sha]) => env.answered({ url: playerUrl(gameId), romSha256: sha })

  await presentPendingGame(env)
  await presentOnFirstEdit(env)
  await reconnectBeforeBinding(env)
  await presentPendingGame(env, true)
})
