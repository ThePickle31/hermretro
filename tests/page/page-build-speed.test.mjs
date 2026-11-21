// The Build model panel's rail, stars and Standard / Fast bar (page/pages/build/composer/model-list.js,
// model-settings.js): Fast only for ChatGPT or Codex Subscription models that list fast mode, per conversation and in
// the New Game draft pick.
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
    { slug: 'anthropic', name: 'Anthropic', authenticated: true, models: ['claude-opus-5-5'],
      capabilities: { 'claude-opus-5-5': { fast: true, reasoning: true } } },
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, total_models: 19, models: ['gpt-6.2-sol', 'gpt-5-mini'],
      capabilities: { 'gpt-6.2-sol': { fast: true, reasoning: true }, 'gpt-5-mini': { reasoning: true } } },
    { slug: 'gone', name: 'Signed Out Co', authenticated: false, models: ['x-1'] }] })
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
  const press = async node => { await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  const speed = () => pop()?.querySelector('[aria-label="Speed"]')
  const row = name => [...pop().querySelectorAll('.cs-b-mp-row')].find(node => node.title.startsWith(`${name} `))
  const tile = label => pop().querySelector(`.cs-b-mp-rail [aria-label="${label}"]`)

  await open()
  check('the rail has Starred, one mark per signed-in provider, and connect another', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-rail button')].map(node => node.getAttribute('aria-label')),
      ['Starred', 'Anthropic', 'ChatGPT or Codex Subscription', 'Connect another provider'])
    assert.equal(tile('ChatGPT or Codex Subscription').getAttribute('aria-pressed'), 'true', 'it opens on the conversation\u2019s provider')
    assert.equal(pop().querySelector('.cs-b-mp-head').textContent, 'ChatGPT or Codex Subscription· 19 models')
  })
  check('Effort is a list with the model\u2019s name, and a note on what the level is for', () => {
    assert.equal(pop().querySelector('.cs-b-mp-emodel').textContent, 'GPT-6.2 Sol')
    assert.equal(pop().querySelector('[aria-label="Effort"] [aria-checked="true"]').textContent, 'Medium')
    assert.equal(pop().querySelector('.cs-b-mp-enote').textContent, 'MediumMost changes')
  })
  check('a ChatGPT or Codex Subscription model with fast mode has Standard / Fast, Standard picked', () => {
    assert.deepEqual([...speed().querySelectorAll('button')].map(node => node.textContent), ['Standard', 'Fast'])
    assert.equal(speed().querySelector('[aria-checked="true"]').textContent, 'Standard')
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

  // Stars: kept in the page's storage, listed under Starred with each model's provider.
  await press(row('gpt-6.2-sol').parentElement.querySelector('.cs-b-mp-star'))
  await press(tile('Anthropic'))
  check('another provider\u2019s tab lists its models and keeps the speed of the model in use', () => {
    assert.equal(pop().querySelector('.cs-b-mp-head').textContent, 'Anthropic· 1 model')
    assert.ok(speed(), 'Speed follows the conversation\u2019s model, not the tab')
  })
  await press(row('claude-opus-5-5').parentElement.querySelector('.cs-b-mp-star'))
  await press(tile('Starred'))
  check('Starred lists the starred models of every provider, each with its provider, and remembers them', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-row .cs-b-mp-label')].map(node => node.textContent), ['Claude Opus 5.5Anthropic', 'GPT-6.2 SolChatGPT or Codex Subscription'])
    assert.deepEqual(scenario.storage.buildModelStars, ['openai-codex:gpt-6.2-sol', 'anthropic:claude-opus-5-5'])
  })
  await press(row('claude-opus-5-5').parentElement.querySelector('.cs-b-mp-star'))
  check('unstarring takes it off the list', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-row')].map(node => node.title), ['gpt-6.2-sol · ChatGPT or Codex Subscription'])
  })
  await typeInto(pop().querySelector('input[aria-label="Search models"]'), 'o')
  check('a search groups matches under each provider\u2019s name and drops the tab\u2019s highlight', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-group')].map(node => node.textContent), ['Anthropic', 'ChatGPT or Codex Subscription'])
    assert.ok(!pop().querySelector('.cs-b-mp-rail [aria-pressed="true"]'))
  })
  await key('keydown', 'Escape')

  // Another provider while fast mode is on: back to standard, and no Standard / Fast.
  await open()
  await press(tile('Anthropic'))
  await press(row('claude-opus-5-5'))
  await settle()
  check('a model from another provider switches back to standard speed', () => {
    assert.deepEqual(scenario.sets.slice(-2).map(set => [set.key, set.value]), [['model', 'claude-opus-5-5 --provider anthropic --session'], ['fast', 'normal']])
    assert.ok(!chip().querySelector('.cs-b-mp-bolt'))
  })
  await open()
  check('and its panel has no Standard / Fast (even though Hermes lists fast for it), only Manage providers', () => {
    assert.ok(!speed()); assert.match(pop().querySelector('.cs-b-mp-bar').textContent, /Manage providers/)
  })
  await press(tile('ChatGPT or Codex Subscription'))
  await press(row('gpt-5-mini'))
  await settle()
  await open()
  check('nor does a Codex model without fast mode', () => { assert.ok(!speed()) })
  await press(row('gpt-6.2-sol'))
  await settle()
  const before = scenario.sets.length

  // While HermRetro works, a speed pick waits for the turn to end, like model and effort.
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add a boss')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await settle()
  await open()
  await click('Fast', speed())
  await settle()
  check('a speed picked while HermRetro works is held: the bar and the button say so', () => {
    assert.equal(scenario.sets.length, before)
    assert.match(pop().querySelector('.cs-b-mp-bar').textContent, /Switches when HermRetro finishes this turn/)
    assert.ok(chip().querySelector('.cs-b-mp-bolt')); assert.match(chip().textContent, /next message/)
  })
  await key('keydown', 'Escape')
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-frog', payload: { text: 'Boss added.' } }) })
  await settle()
  check('when the turn ends the held speed is applied', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'fast', value: 'fast' })
  })

  // A narrow window: the Effort column narrows, drops its note, and the words shorten.
  const width = dom.window.innerWidth
  dom.window.innerWidth = 470
  await open()
  check('in a narrow window the panel narrows and shortens its words', () => {
    assert.ok(pop().classList.contains('narrow'))
    assert.ok(!pop().querySelector('.cs-b-mp-enote'))
    assert.equal(pop().querySelector('.cs-b-mp-head').textContent, 'ChatGPT or Codex Subscription· 19')
    assert.match(pop().querySelector('.cs-b-mp-manage').textContent, /^Providers$/)
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
  check('the draft picker shows the starred models too', () => {
    assert.ok(draft.node.querySelector('.cs-b-mp-item.starred'))
  })
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
  scenario.storage.buildModel = { model: 'claude-opus-5-5', provider: 'anthropic', fast: true }
  const other = await mount(page)
  await settle()
  await typeInto(other.node.querySelector('textarea[aria-label="Your game idea"]'), 'a moth game')
  await act(async () => { other.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('another provider never gets fast mode with session.create', () => { assert.ok(!('fast' in creates.at(-1))) })
  await other.close()
})
