// Live tool events and saved presentations as the user switches between games.
import assert from 'node:assert/strict'

import { buildView, playable, playerUrl, presentation } from './build-player-fixture.mjs'
import { frogPost, resumeConversation } from './frog-post-fixture.mjs'
import { runScenario } from './harness.mjs'

async function switchAfterPresentation({ act, answered, buildScenario, check, click, emit, mount, page, scenario, settle, typeInto }) {
  const frog = playable(frogPost({ session: { storedId: 'st-frog' } }))
  const comet = playable({
    id: 'abc123abc123', title: 'Comet Drift', kind: 'gbstudio', projectRoot: '/home/u/games/CometDrift', session: { storedId: 'st-comet' }
  })
  const runtime = 'rt-of-st-frog'
  const shown = presentation(frog, runtime, 100)
  scenario.byMethod['plugin.hermretro.presentations'] = { ok: true, now: 99, presentations: [] }
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
  await build.selectGame(frog)
  await settle()
  check('returning directly to Frog Post leaves its previously open frame closed', build.assertClosed)
  await build.selectGame(comet)
  await settle()
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

  await build.selectGame(comet)
  await settle()
  const method = 'plugin.hermretro.presentations'
  let now = 200
  let cursor = () => ({ ok: true, now, presentations: [] })
  let lookup
  let reply
  const record = { gameId: frog.id, title: frog.title, sessionId: runtime, buildConversation: true }
  const answer = t => ({ ok: true, now, presentations: [{ ...record, t }] })
  scenario.byMethod[method] = params => params.cursorOnly ? cursor() : lookup()
  const holdLookup = async session => {
    reply = null
    lookup = () => new Promise(resolve => { reply = resolve })
    await act(async () => { emit({ type: 'message.complete', session_id: session, payload: {} }) })
    await settle()
    assert.equal(typeof reply, 'function', 'the completed turn requested presentations')
  }

  await holdLookup(runtime)
  const beforeSwitch = answer(200)
  now = 201
  await build.selectGame(frog)
  await settle()
  build.assertClosed()
  await act(async () => { reply(beforeSwitch) })
  check('a delayed fallback for a turn finished before the switch leaves the player closed', build.assertClosed)
  now = 202
  lookup = () => answer(202)
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: {} }) })
  await settle()
  check('the next presentation found by the fallback opens the selected game', () => build.assertPlaying(frog))

  now = 500
  await build.selectGame(comet)
  await build.selectGame(frog)
  now = 600
  lookup = () => answer(203)
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-elsewhere', payload: {} }) })
  await settle()
  check('a later lookup skips a presentation recorded before the selection', build.assertClosed)
  await build.selectGame(comet)
  await holdLookup('rt-elsewhere')
  now = 601
  await build.selectGame(frog)
  await settle()
  now = 602
  await act(async () => { reply(answer(602)) })
  check('another session’s pending lookup can deliver a fresh presentation after selection', () => build.assertPlaying(frog))

  await build.selectGame(comet)
  await holdLookup('rt-elsewhere')
  now = 603
  const captured = answer(603)
  now = 604
  await build.selectGame(frog)
  await settle()
  await act(async () => { reply(captured) })
  check('another session’s reply captured before the switch cannot replay its presentation', build.assertClosed)

  await act(async () => { emit(presentation(frog, runtime, 603.5)) })
  check('a delayed live tool completion from before selection leaves the game closed', build.assertClosed)

  await build.selectGame(comet)
  await holdLookup(runtime)
  now = 605
  let confirmSelection
  cursor = () => new Promise(resolve => { confirmSelection = resolve })
  await build.selectGame(frog)
  await settle()
  check('the previous game stays visible until the backend records the switch', () => {
    assert.equal(typeof confirmSelection, 'function')
    build.assertSelected(comet.id, comet.title)
  })
  await act(async () => { confirmSelection({ ok: true, now, presentations: [] }) })
  build.assertSelected(frog.id, frog.title)
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'show the new build')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  build.assertBusy(true)
  now = 606
  await act(async () => { reply(answer(606)) })
  build.assertClosed()
  lookup = () => answer(606)
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Done.' } }) })
  await settle()
  check('a previous turn’s query can discover the next turn’s presentation and play it once idle', () => build.assertPlaying(frog))
  now = 607
  cursor = () => ({ ok: true, now, presentations: [] })
  await build.selectGame(comet)
  await act(async () => { emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'busy-frog' } }) })
  cursor = () => new Promise(resolve => { confirmSelection = resolve })
  await build.selectGame(frog)
  await settle()
  now = 608
  await act(async () => { confirmSelection({ ok: true, now, presentations: [] }) })
  build.assertSelected(frog.id, frog.title)
  build.assertBusy(true)
  now = 609
  lookup = () => answer(609)
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { turn_id: 'busy-frog', text: 'Ready to play.' } }) })
  await settle()
  check('a busy game plays a history presentation made after the switch becomes visible', () => build.assertPlaying(frog))
  await build.selectGame(comet)
  await settle()
  await build.selectGame(frog)
  await act(async () => { confirmSelection({ ok: true, now, presentations: [] }) })
  check('choosing the current game cancels a slow switch and keeps its player open', () => {
    build.assertSelected(frog.id, frog.title)
    build.assertPlaying(frog)
  })
  await view.close()
}

await runScenario(async env => {
  env.holdTimers()
  env.scenario.byMethod['session.resume'] = resumeConversation()
  env.scenario.byMethod['prompt.submit'] = { ok: true }
  env.scenario.player = ([, , , gameId]) => env.answered({ url: playerUrl(gameId) })
  await switchAfterPresentation(env)
})
