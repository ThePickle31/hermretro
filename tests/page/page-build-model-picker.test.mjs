// The current conversation model and effort, questions in other games, and the next New Game model.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogPost, lamplight, resumeConversation } from './frog-post-fixture.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, dom, emit, holdTimers, key, mount, page, scenario, settle, typeInto }) => {
  const clock = holdTimers()
  const frog = frogPost({ session: { storedId: 'st-old' } })
  const lampGame = lamplight()
  buildScenario({ selected: lampGame.id })
  scenario.games = answered({ games: [frog, lampGame], device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = resumeConversation()
  scenario.byMethod['prompt.submit'] = () => ({ ok: true })

  // Open Lamplight's session so it can receive a question while Frog Post is on screen.
  const otherGame = await mount(page)
  await settle()
  await otherGame.close()
  scenario.storage.buildSelected = frog.id

  // Model and effort: one button in the message box opens providers, models and effort together.
  scenario.models = answered({ model: 'claude-opus-5-5[1m]', provider: 'claude-sub', providers: [
    { slug: 'claude-sub', name: 'Claude Subscription', authenticated: true, total_models: 3, models: ['claude-opus-5-5[1m]', 'claude-sonnet-5-5[1m]', 'claude-haiku-4-5-20251001'],
      capabilities: { 'claude-opus-5-5[1m]': { reasoning: true }, 'claude-sonnet-5-5[1m]': { reasoning: true }, 'claude-haiku-4-5-20251001': { reasoning: true } } },
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, total_models: 2, models: ['gpt-6.1-sol', 'gpt-6-sol-900k'],
      capabilities: { 'gpt-6.1-sol': { fast: true, reasoning: true }, 'gpt-6-sol-900k': { fast: true, reasoning: true } } },
    { slug: 'off', name: 'Signed Out Co', authenticated: false, models: ['x-1'] }] })
  scenario.sets = []
  scenario.byMethod['config.set'] = params => { scenario.sets.push(params); return { key: params.key, value: params.value } }
  const conversation = await mount(page)
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-old', payload: { model: 'claude-opus-5-5[1m]', provider: 'claude-sub', reasoning_effort: 'high' } }) })
  await settle()
  // Another game asks a question while this one is open: the title says so.
  await act(async () => { emit({ type: 'clarify.request', session_id: 'rt-new-1', payload: { request_id: 'other-q', question: 'Which lamp?' } }) })
  await settle()
  check('a question in another game shows as "1 needs you" beside the title', () => {
    assert.equal(conversation.node.querySelector('.cs-b-needs')?.textContent, '1 needs you')
    assert.match(conversation.node.querySelector('.cs-b-needs').getAttribute('title'), /Lamplight/)
  })
  await act(async () => { emit({ type: 'clarify.settled', session_id: 'rt-new-1', payload: { request_id: 'other-q' } }) })
  await settle()
  check('once it is answered the badge goes away', () => { assert.ok(!conversation.node.querySelector('.cs-b-needs')) })
  const chip = () => conversation.node.querySelector('.cs-b-mp-chip')
  const pop = () => conversation.node.querySelector('.cs-b-mp-pop')
  check('the message box shows the conversation\'s model and effort in plain words', () => {
    assert.equal(chip().textContent, 'ClClaude Opus 5.5·High')
  })
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('the panel has a rail of connected providers only, the current one\'s models, and the effort levels', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-prov .cs-b-mp-pname')].map(node => node.textContent), ['Claude Subscription', 'ChatGPT or Codex Subscription'])
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-row .cs-b-mp-label')].map(node => node.textContent), ['Claude Opus 5.5', 'Claude Sonnet 5.5', 'Claude Haiku 4.5'])
    // A provider without an official logo keeps its letters (two when another starts the same); ChatGPT or Codex
    // Subscription shows OpenAI's logo (page-build-logos.test.mjs).
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-prov')].map(node => node.firstChild.textContent || node.firstChild.dataset.brand), ['Cl', 'OpenAI'], 'two providers starting with C get two letters')
    assert.equal(pop().querySelector('.cs-b-mp-prov[aria-pressed="true"]').getAttribute('aria-label'), 'Claude Subscription')
    assert.equal(pop().querySelector('.cs-b-mp-row[aria-selected="true"]').textContent, 'ClClaude Opus 5.51M')
    assert.match(pop().querySelector('.cs-b-mp-head').textContent, /^Claude Subscription· 3 models$/)
    assert.deepEqual([...pop().querySelectorAll('[aria-label="Effort"] button')].map(node => node.textContent), ['Off', 'Minimal', 'Low', 'Medium', 'High', 'X-high', 'Max'])
    assert.equal(pop().querySelector('[aria-label="Effort"] button[aria-checked="true"]').textContent, 'High')
    assert.ok(!pop().querySelector('[aria-label="Speed"]'), 'no Standard / Fast for a Claude model')
  })
  await typeInto(pop().querySelector('input[aria-label="Search models"]'), 'sol')
  await act(async () => { pop().querySelectorAll('.cs-b-mp-row')[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('picking a model switches this conversation only, and the button shows it', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'model', value: 'gpt-6.1-sol --provider openai-codex --session' })
    assert.ok(!pop())
    assert.match(chip().textContent, /GPT-6\.1 Sol·High/)
  })
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Medium', pop())
  await settle()
  check('an effort level is one click and applies to this conversation', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'reasoning', value: 'medium' })
    assert.match(chip().textContent, /GPT-6\.1 Sol·Medium/)
  })
  await key('keydown', 'Escape')
  check('Escape closes the panel', () => { assert.ok(!pop()) })
  // While HermRetro works, a pick waits for the turn to end.
  await typeInto(conversation.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add a boss')
  await click('Send', conversation.node.querySelector('.cs-b-comp'))
  await settle()
  const before = scenario.sets.length
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Max', pop())
  await settle()
  await key('keydown', 'Escape')
  await clock.fire()
  check('a pick made while HermRetro works is held, marked "next message", and not sent yet', () => {
    assert.equal(scenario.sets.length, before)
    assert.match(chip().textContent, /Max/); assert.match(chip().textContent, /next message/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Boss added.' } }) })
  await settle()
  check('when the turn ends the held pick is applied', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'reasoning', value: 'max' })
    assert.ok(!/next message/.test(chip().textContent))
  })
  await typeInto(conversation.node.querySelector('textarea[aria-label="Message Hermes"]'), 'now a second boss')
  await click('Send', conversation.node.querySelector('.cs-b-comp'))
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Second boss.' } }) })
  await settle()
  check('a reply names its model when it changed since the message before', () => {
    const labels = [...conversation.node.querySelectorAll('.cs-b-who')].map(node => node.textContent)
    assert.deepEqual(labels, ['GPT-6.1 Sol · Max'], 'only where the model changed: the first message on a model has nothing to compare with')
  })
  // A model that asks before it is used (cost).
  let asked = 0
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params)
    if (params.key === 'model' && !params.confirm_expensive_model) { asked += 1; return { confirm_required: true, confirm_message: 'Opus costs 5× more.' } }
    return { key: params.key, value: params.value }
  }
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Claude Subscription', pop())
  await act(async () => { pop().querySelectorAll('.cs-b-mp-row')[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('a model that asks first shows its question in the panel, and the switch waits', () => {
    assert.equal(asked, 1); assert.match(pop().querySelector('.cs-b-mp-confirm').textContent, /Opus costs 5× more\./)
    assert.match(chip().textContent, /GPT-6\.1 Sol/)
  })
  await click('Use it', pop())
  await settle()
  check('Use it switches, confirmed', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'model', value: 'claude-opus-5-5[1m] --provider claude-sub --session', confirm_expensive_model: true })
    assert.match(chip().textContent, /Claude Opus 5\.5/)
  })
  // A provider that is no longer signed in.
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-old', payload: { model: 'x-1', provider: 'off' } }) })
  await settle()
  check('a conversation on a signed-out provider says so on the button', () => {
    assert.match(chip().textContent, /off is signed out/); assert.ok(chip().classList.contains('warn'))
  })
  await conversation.close()
  // New Game starts on the picked model, and remembers it for the next one.
  scenario.storage.buildSelected = 'new'
  delete scenario.byMethod['config.set']
  const creates = []
  scenario.byMethod['session.create'] = params => {
    creates.push(params)
    return { session_id: 'rt-new-2', stored_session_id: 'st-new-2', info: params, messages: [] }
  }
  scenario.byMethod['plugin.hermretro.build'] = () => ({ ok: true })
  const draft = await mount(page)
  await settle()
  await act(async () => { draft.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { draft.node.querySelectorAll('.cs-b-mp-row')[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { draft.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Low', draft.node.querySelector('.cs-b-mp-pop'))
  await typeInto(draft.node.querySelector('textarea[aria-label="Your game idea"]'), 'a frog racing game')
  await act(async () => { draft.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('New Game makes its conversation on the picked model and effort, and remembers them', () => {
    assert.equal(creates.at(-1).model, 'claude-sonnet-5-5[1m]'); assert.equal(creates.at(-1).provider, 'claude-sub'); assert.equal(creates.at(-1).reasoning_effort, 'low')
    assert.deepEqual(scenario.storage.buildModel, { model: 'claude-sonnet-5-5[1m]', provider: 'claude-sub', effort: 'low' })
  })
  await draft.close()
})
