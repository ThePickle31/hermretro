// The Build model picker's Speed control (page/pages/build/composer/model-settings.js): Normal / Fast, only for
// ChatGPT or Codex Subscription models that list fast mode, per conversation and in the New Game draft pick.
// Run alone: node tests/page/page-build-speed.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, act, dom, emit, scenario, page, click, settle, typeInto, key, mount, check, answered }) => {
  buildScenario({ selected: 'fff666fff666' })
  scenario.games = answered({ games: [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
  device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: [] })
  scenario.models = answered({ model: 'gpt-6.2-sol', provider: 'openai-codex', providers: [
    { slug: 'claude-sub', name: 'Claude Subscription', authenticated: true, models: ['claude-opus-5-5[1m]'],
      capabilities: { 'claude-opus-5-5[1m]': { reasoning: true } } },
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, models: ['gpt-6.2-sol', 'gpt-5-mini'],
      capabilities: { 'gpt-6.2-sol': { fast: true, reasoning: true }, 'gpt-5-mini': { reasoning: true } } }] })
  scenario.sets = []
  scenario.byMethod['config.set'] = params => { scenario.sets.push(params); return { key: params.key, value: params.value } }
  scenario.byMethod['prompt.submit'] = () => ({ ok: true })

  const view = await mount(page)
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium', fast: false } }) })
  await settle()
  const chip = () => view.node.querySelector('.cs-b-mp-chip')
  const pop = () => view.node.querySelector('.cs-b-mp-pop')
  const open = async () => { await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  const speed = () => pop()?.querySelector('[aria-label="Speed"]')
  const row = name => [...pop().querySelectorAll('.cs-b-mp-row')].find(node => node.title === name)

  await open()
  check('a ChatGPT or Codex Subscription model with fast mode shows Speed beside Effort, Normal picked', () => {
    assert.deepEqual([...speed().querySelectorAll('button')].map(node => node.textContent), ['Normal', 'Fast'])
    assert.equal(speed().querySelector('[aria-checked="true"]').textContent, 'Normal')
    assert.ok(pop().querySelector('.cs-b-mp-effort').classList.contains('beside'))
    assert.deepEqual([...pop().querySelectorAll('[aria-label="Effort"] button')].map(node => node.textContent), ['Off', 'Minimal', 'Low', 'Medium', 'High', 'X-high', 'Max'])
    assert.ok(!chip().querySelector('.cs-b-mp-bolt'))
  })
  await click('Fast', speed())
  await settle()
  check('Fast turns fast mode on for this conversation only, and the button shows a bolt', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'fast', value: 'fast' })
    assert.equal(speed().querySelector('[aria-checked="true"]').textContent, 'Fast')
    assert.ok(chip().querySelector('.cs-b-mp-bolt'))
  })
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { fast: false } }) })
  await settle()
  check('the bolt follows what Hermes says the conversation runs on', () => { assert.ok(!chip().querySelector('.cs-b-mp-bolt')) })
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { fast: true } }) })
  await settle()

  await act(async () => { row('gpt-5-mini').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('a Codex model without fast mode switches back to normal speed and shows no Speed control', () => {
    assert.deepEqual(scenario.sets.slice(-2).map(set => [set.key, set.value]), [['model', 'gpt-5-mini --provider openai-codex --session'], ['fast', 'normal']])
    assert.ok(!chip().querySelector('.cs-b-mp-bolt'))
  })
  await open()
  check('Speed is not offered for that model', () => { assert.ok(!speed()); assert.ok(!pop().querySelector('.cs-b-mp-effort').classList.contains('beside')) })
  await click('Claude Subscription', pop())
  check('nor for another provider', () => { assert.ok(!speed()) })
  await click('ChatGPT or Codex Subscription', pop())
  await act(async () => { row('gpt-6.2-sol').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  const before = scenario.sets.length
  check('picking a model while fast mode is off sends no speed', () => { assert.deepEqual(scenario.sets.at(-1).key, 'model') })

  // While HermRetro works, a speed pick waits for the turn to end, like model and effort.
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add a boss')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await settle()
  await open()
  await click('Fast', speed())
  await settle()
  await key('keydown', 'Escape')
  check('a speed picked while HermRetro works is held and marked "next message"', () => {
    assert.equal(scenario.sets.length, before)
    assert.ok(chip().querySelector('.cs-b-mp-bolt')); assert.match(chip().textContent, /next message/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-frog', payload: { text: 'Boss added.' } }) })
  await settle()
  check('when the turn ends the held speed is applied', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'fast', value: 'fast' })
  })

  // A narrow window: Speed moves under Effort with a short hint instead of squeezing it.
  const width = dom.window.innerWidth
  dom.window.innerWidth = 600
  await open()
  check('in a narrow window Speed sits on its own line under Effort, with a hint', () => {
    assert.ok(!pop().querySelector('.cs-b-mp-effort').classList.contains('beside'))
    assert.equal(pop().querySelector('.cs-b-mp-speed .cs-faint').textContent, 'Quicker, uses more of your plan')
  })
  await key('keydown', 'Escape')
  dom.window.innerWidth = width
  await view.close()

  // New Game: the draft pick remembers fast mode and sends it with session.create, for Codex models only.
  scenario.storage.buildSelected = 'new'
  scenario.storage.buildModel = { model: 'gpt-6.2-sol', provider: 'openai-codex', effort: 'low' }
  const creates = []
  scenario.byMethod['session.create'] = params => { creates.push(params); return { session_id: 'rt-new-1', stored_session_id: 'st-new-1', messages: [] } }
  const draft = await mount(page)
  await settle()
  await act(async () => { draft.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Fast', draft.node.querySelector('[aria-label="Speed"]'))
  await typeInto(draft.node.querySelector('textarea[aria-label="Your game idea"]'), 'a frog racing game')
  await act(async () => { draft.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('New Game makes its conversation with fast mode on, and remembers it', () => {
    assert.equal(creates.at(-1).fast, true); assert.equal(creates.at(-1).provider, 'openai-codex')
    assert.deepEqual(scenario.storage.buildModel, { model: 'gpt-6.2-sol', provider: 'openai-codex', effort: 'low', fast: true })
  })
  await draft.close()
  scenario.storage.buildSelected = 'new'
  scenario.storage.buildModel = { model: 'claude-opus-5-5[1m]', provider: 'claude-sub', fast: true }
  const other = await mount(page)
  await settle()
  await typeInto(other.node.querySelector('textarea[aria-label="Your game idea"]'), 'a moth game')
  await act(async () => { other.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('another provider never gets fast mode with session.create', () => { assert.ok(!('fast' in creates.at(-1))) })
  await other.close()
})
