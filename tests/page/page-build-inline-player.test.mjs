// Play a build in the conversation, then check controls, the checklist and keyboard focus.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogJumpMessages, frogPost, reportedRobinBuild, resumeConversation } from './frog-post-fixture.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, dom, emit, holdTimers, mount, page, scenario, settle, typeInto }) => {
  const clock = holdTimers()
  const frog = frogPost({ web: { sha256: 'w1', builtAt: 2100 } })
  buildScenario({ selected: frog.id })
  const showConversation = storedId => {
    scenario.games = answered({ games: [{ ...frog, session: { storedId } }], device: { hardwareEnabled: false, skipped: true } })
  }
  showConversation('st-old')
  const skins = [{ id: 'hermes-midnight', name: 'Nous Black', swatch: '#15171c' }, { id: 'hermes-blue', name: 'Nous Blue', swatch: '#0053fd' }]
  scenario.player = answered({
    url: 'http://127.0.0.1:4567/tok/fff666fff666/index.html', romSha256: 'w1', title: 'Frog Post', skins, skin: 'hermes-midnight'
  })
  scenario.byMethod['prompt.submit'] = () => ({ ok: true })
  scenario.byMethod['session.resume'] = resumeConversation(frogJumpMessages)
  // Leave a newer live reply after the resumed build so the build has a folded row to play from.
  const firstVisit = await mount(page)
  await settle(100)
  const runtime = 'rt-of-st-old'
  await typeInto(firstVisit.node.querySelector('textarea[aria-label="Message Hermes"]'), 'make it green')
  await click('Send', firstVisit.node.querySelector('.cs-b-comp'))
  await settle()
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Greener now.' } }) })
  await settle()
  await firstVisit.close()

  // The game plays inside the conversation while the agent is idle.
  const tabsBefore = scenario.workspaces.length
  const conversation = await mount(page)
  await settle(100)
  const inlineFrame = () => conversation.node.querySelector('.cs-ip iframe')
  const framePlay = () => conversation.node.querySelector('.cs-b-pc-go, .cs-b-history-play')
  const closeGame = () => act(async () => { conversation.node.querySelector('.cs-ip button[aria-label="Close the game"]').click() })
  check('the newest build rests in a game frame under its line, with Play build #1; nothing plays until asked', () => {
    assert.match(framePlay()?.textContent ?? '', /Play build #1/); assert.ok(!inlineFrame())
    assert.ok(conversation.node.querySelector('.cs-b-history-play'), 'the last playable build can start from its folded row')
  })
  await act(async () => { framePlay().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('Play opens the real player right in the conversation', () => {
    assert.match(inlineFrame()?.getAttribute('src') ?? '', /tok\/fff666fff666\/index\.html/)
    assert.ok(conversation.node.querySelector('.cs-b-turn .cs-ip') && !conversation.node.querySelector('.cs-b-bc .cs-ip'), 'it plays under the build line'); assert.ok(!framePlay())
  })
  await typeInto(conversation.node.querySelector('textarea[aria-label="Message Hermes"]'), 'how do I jump?')
  await click('Send', conversation.node.querySelector('.cs-b-comp'))
  await settle()
  check('sending a normal message hides the open player while Hermes works', () => {
    assert.equal([...conversation.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'how do I jump?')
    assert.ok(!inlineFrame())
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Press A to jump.' } }) })
  await settle()
  check('a reply without a presentation brings the manually opened player back', () => assert.ok(inlineFrame()))
  await closeGame()
  assert.ok(!inlineFrame(), 'the presentation starts with the player closed')
  await typeInto(conversation.node.querySelector('textarea[aria-label="Message Hermes"]'), 'make it rain')
  await click('Send', conversation.node.querySelector('.cs-b-comp'))
  await settle()
  check('starting a turn folds the previous build and hides its Play button', () => {
    assert.ok(!inlineFrame())
    assert.equal(conversation.node.querySelector('.cs-b-history-row').getAttribute('aria-expanded'), 'false')
    assert.ok(!conversation.node.querySelector('.cs-b-pc-go'))
  })
  scenario.byMethod['prompt.submit'] = () => ({ status: 'queued' })
  await typeInto(conversation.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and make it snow after')
  await click('Send', conversation.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = () => ({ ok: true })
  check('a message Hermes queues while it works waits under the conversation, marked queued', () => {
    const queued = conversation.node.querySelector('.cs-b-user.queued')
    assert.match(queued?.textContent ?? '', /Queued · HermRetro reads this when it finishes.*and make it snow after/)
    assert.equal([...conversation.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'make it rain')
  })
  await act(async () => { emit({ type: 'tool.start', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {} } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {}, result: { result: 'Completed.' } } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p1', name: 'chromatic_present_game', args: {},
    result: { ok: true, studio: { gameId: 'fff666fff666', title: 'Frog Post', note: 'Try the rain', presentedAt: 99 } } } }) })
  await settle()
  await clock.fire()
  check('presenting from a Build conversation opens no tab beside the chat, and the game waits for the turn to end', () => {
    assert.equal(scenario.workspaces.length, tabsBefore); assert.ok(!inlineFrame())
    assert.ok(!conversation.node.querySelector('.cs-b-pc'), 'no game frame while the agent works')
    assert.match(conversation.node.querySelector('.cs-b-history-row').textContent, /#1/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Done.' } }) })
  await settle()
  check('when the turn ends the newest build opens in the newest reply, with the agent\'s note; the older one says it is older', () => {
    assert.ok(inlineFrame()); assert.match(conversation.node.querySelector('.cs-ip').textContent, /Try the rain/)
    const turnsNow = [...conversation.node.querySelectorAll('.cs-b-turn')]
    assert.ok(turnsNow.at(-1).querySelector('.cs-ip'), turnsNow.map(node => node.textContent.slice(0, 60)).join(' | '))
    assert.match(turnsNow.at(-1).querySelector('.cs-b-bc-head').textContent, /#2/); assert.match(conversation.node.querySelector('.cs-b-history-row').textContent, /#1/)
  })
  await act(async () => { emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'Q' } }) })
  await settle()
  check('when its turn starts the queued message joins the conversation as the newest one', () => {
    assert.ok(!conversation.node.querySelector('.cs-b-user.queued'))
    assert.equal([...conversation.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'and make it snow after')
    assert.ok(!inlineFrame(), 'the game rests while the agent works again')
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Snowing.' } }) })
  await settle()
  check('a game the user had open comes back when the agent is done', () => { assert.ok(inlineFrame()) })
  await closeGame()
  check('closing the game puts the frame and its Play back', () => { assert.ok(!inlineFrame()); assert.ok(framePlay()) })
  await conversation.close()
  // The inline player itself: one bar, whole-number sizes, and the play-test panel from the build report.
  showConversation('st-play')
  scenario.byMethod['session.resume'] = resumeConversation(() => reportedRobinBuild('Try flying around.'))
  const controls = await mount(page)
  await settle(100)
  const ipPlay = controls.node.querySelector('.cs-b-pc-go')
  check('the reported build offers Play in its game frame', () => assert.ok(ipPlay))
  await act(async () => { ipPlay.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  const ip = () => controls.node.querySelector('.cs-ip')
  check('the inline player loads the bare screen in the Nous Black finish, with the player\'s own controls hidden', () => {
    assert.match(ip().querySelector('iframe').getAttribute('src'), /index\.html\?view=screen&color=hermes-midnight$/)
    assert.equal(ip().querySelector('.cs-ip-screen').dataset.view, 'screen')
  })
  check('one bar: Fit and whole-number sizes, Chromatic, Play-test, Annotate and Close', () => {
    assert.deepEqual([...ip().querySelectorAll('.cs-ip-seg [role=radio]')].map(node => [node.textContent, node.getAttribute('aria-checked')]), [['Fit', 'true'], ['2×', 'false'], ['3×', 'false'], ['4×', 'false']])
    for (const label of ['Show the Chromatic around the game', 'Close the game']) assert.ok(ip().querySelector(`.cs-ip-bar button[aria-label="${label}"]`), label)
    assert.ok([...ip().querySelectorAll('.cs-ip-bar button')].some(node => /^Annotate/.test(node.getAttribute('aria-label') ?? '')))
    assert.ok([...ip().querySelectorAll('.cs-ip-bar button')].some(node => node.textContent === 'Play-test'))
  })
  const checkRows = () => [...ip().querySelectorAll('.cs-ip-check')].map(node => [node.querySelector('.cs-ip-check-text').textContent, node.dataset.state])
  check('the panel opens with the report\'s checks, what was not tested first', () => {
    assert.ok(ip().querySelector('.cs-ip-panel'))
    assert.deepEqual(checkRows(), [['Sound', 'untested'], ['Robin faces where it flies', 'todo'], ['Camera follows', 'todo']])
    assert.match(ip().querySelector('.cs-ip-panel').textContent, /Try this\s*0\/3/)
  })
  await act(async () => { ip().querySelectorAll('.cs-ip-check input')[1].click() })
  await settle()
  check('a tick is the user\'s, kept for this game and build', () => {
    assert.equal(checkRows()[1][1], 'done')
    assert.deepEqual(Object.keys(scenario.storage.playtest ?? {}), ['fff666fff666'])
    assert.match(JSON.stringify(scenario.storage.playtest), /robin faces where it flies/)
  })
  await act(async () => { ip().querySelector('.cs-ip-bar button[aria-label="Show the Chromatic around the game"]').click() })
  await settle()
  check('Chromatic shows the handheld around the game and is remembered for every game', () => {
    assert.equal(ip().querySelector('.cs-ip-screen').dataset.view, 'device')
    assert.equal(scenario.storage.inlinePlayer.view, 'device')
  })
  const sentKeys = []
  ip().querySelector('iframe').contentWindow.postMessage = message => { if (message.type === 'key') sentKeys.push(`${message.key}:${message.down ? 'down' : 'up'}`) }
  const keyOn = async (target, type, keyName) => act(async () => { target.dispatchEvent(new dom.window.KeyboardEvent(type, { key: keyName, bubbles: true, cancelable: true })) })
  await act(async () => { ip().querySelector('.cs-ip-stage').dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  await keyOn(ip().querySelector('.cs-ip-stage'), 'keydown', 'ArrowUp')
  await keyOn(ip().querySelector('.cs-ip-bar button[aria-label="Close the game"]'), 'keydown', 'Enter')
  check('after a click in the player, game keys on the page reach the game, but Enter on a bar button presses the button', () => {
    assert.deepEqual(sentKeys, ['ArrowUp:down'])
  })
  await act(async () => { controls.node.querySelector('textarea[aria-label="Message Hermes"]').dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  await keyOn(controls.node.querySelector('textarea[aria-label="Message Hermes"]'), 'keydown', 'ArrowDown')
  check('clicking into the message box lets go of a held key, and typing there never reaches the game', () => {
    assert.deepEqual(sentKeys, ['ArrowUp:down', 'ArrowUp:up'])
  })
  await act(async () => { ip().querySelector('.cs-ip-bar button[aria-label="Close the game"]').click() })
  await controls.close()
})
