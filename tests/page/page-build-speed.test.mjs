// The Build model panel's rail, stars and Standard / Fast bar (page/pages/build/composer/model-list.js,
// model-settings.js): Fast only for ChatGPT or Codex Subscription and OpenAI API models that list fast mode, only on
// their provider's tab, per conversation and in the New Game draft pick.
// Run alone: node tests/page/page-build-speed.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, act, dom, emit, scenario, page, click, settle, typeInto, key, mount, check, answered, holdTimers }) => {
  // The test ends turns via events. A real open-request poll can otherwise report idle early on a loaded runner.
  holdTimers()
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
    { slug: 'openai-api', name: 'OpenAI API', authenticated: true, models: ['gpt-6.2'], capabilities: { 'gpt-6.2': { fast: true, reasoning: true } } },
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
      ['Starred', 'Anthropic', 'ChatGPT or Codex Subscription', 'OpenAI API', 'Connect another provider'])
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

  // The toggle shows only on the tab of the Codex model in use: not on the other OpenAI tab, nor in a search.
  await press(tile('OpenAI API'))
  check('the OpenAI API tab has no toggle while a Codex model is in use', () => { assert.ok(!speed()) })
  await press(tile('ChatGPT or Codex Subscription'))
  const search = () => pop().querySelector('input[aria-label="Search models"]')
  await typeInto(search(), 'gpt')
  check('a search has no toggle, even from the Codex tab', () => { assert.ok(!speed()) })
  await typeInto(search(), '')
  check('clearing the search brings it back', () => { assert.ok(speed()) })

  // Stars: kept in the page's storage, listed under Starred with each model's provider.
  await press(row('gpt-6.2-sol').parentElement.querySelector('.cs-b-mp-star'))
  await press(tile('Anthropic'))
  check('another provider\u2019s tab lists its models without Standard / Fast; the conversation stays fast', () => {
    assert.equal(pop().querySelector('.cs-b-mp-head').textContent, 'Anthropic· 1 model')
    assert.ok(!speed(), 'no toggle on a provider whose models it does not apply to (even Anthropic with fast)')
    assert.ok(chip().querySelector('.cs-b-mp-bolt'), 'the button still shows the conversation is fast')
  })
  await press(row('claude-opus-5-5').parentElement.querySelector('.cs-b-mp-star'))
  await press(tile('Starred'))
  check('Starred lists the starred models of every provider, each with its provider, and remembers them', () => {
    assert.ok(!speed(), 'no toggle on Starred')
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
  await press(tile('OpenAI API'))
  await press(row('gpt-6.2'))
  await settle()
  await open()
  check('an OpenAI API model with fast mode has Standard / Fast on its tab', () => { assert.ok(speed()) })
  await click('Fast', speed())
  await settle()
  check('and Fast turns fast mode on for the conversation', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'fast', value: 'fast' })
  })
  await click('Standard', speed())
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { fast: false } }) })
  await settle()
  await press(tile('ChatGPT or Codex Subscription'))
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

  // Review round 1: a Fast still on its way must not carry over to a model without the switch.
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { fast: false } }) })
  await settle()
  let release
  const plainSet = scenario.byMethod['config.set']
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params)
    return params.key === 'fast' && params.value === 'fast' && !release ? new Promise(done => { release = () => done({ key: 'fast', value: 'fast' }) }) : { key: params.key, value: params.value }
  }
  await open()
  await click('Fast', speed())
  await settle()
  await press(tile('Anthropic'))
  await press(row('claude-opus-5-5'))
  await settle()
  await act(async () => { release() })
  await settle()
  check('a model without fast mode picked while Fast is still on its way goes back to standard', () => {
    assert.deepEqual(scenario.sets.slice(-3).map(set => [set.key, set.value]), [['fast', 'fast'], ['model', 'claude-opus-5-5 --provider anthropic --session'], ['fast', 'normal']])
  })
  scenario.byMethod['config.set'] = plainSet
  await open()
  await press(tile('ChatGPT or Codex Subscription'))
  await press(row('gpt-6.2-sol'))
  await settle()

  // Review round 1: Standard / Fast and the Effort list are radio groups with one Tab stop, moved by arrow keys.
  await open()
  check('each radio group has one Tab stop: the picked choice', () => {
    assert.deepEqual([...speed().querySelectorAll('button')].map(node => node.tabIndex), [0, -1])
    assert.deepEqual([...pop().querySelectorAll('[aria-label="Effort"] button')].map(node => node.tabIndex).filter(index => index === 0).length, 1)
  })
  await act(async () => { speed().querySelector('[data-key="normal"]').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })) })
  await settle()
  check('an arrow key picks the next speed', () => { assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'fast', value: 'fast' }) })
  await act(async () => { pop().querySelector('[aria-label="Effort"] [data-key="medium"]').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })) })
  await settle()
  check('and the next effort level', () => { assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'reasoning', value: 'high' }) })
  await key('keydown', 'Escape')

  // Review round 2: the panel shows a change still on its way, so the next choice is judged against it.
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium', fast: false } }) })
  await settle()
  const waits = []
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params)
    return new Promise(done => { waits.push(() => done({ key: params.key, value: params.value })) })
  }
  const releaseAll = async () => { while (waits.length) { await act(async () => { waits.shift()() }); await settle() } }
  await open()
  await press(tile('Anthropic'))
  await press(row('claude-opus-5-5'))
  await settle()
  await open()
  check('reopened before Hermes answers a model switch, the panel shows the new model and offers no Fast', () => {
    assert.match(chip().textContent, /Claude Opus 5\.5/)
    assert.ok(!speed())
  })
  await key('keydown', 'Escape')
  await releaseAll()
  check('so the switch ends on the new model without fast mode', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'model', value: 'claude-opus-5-5 --provider anthropic --session' })
    assert.ok(!scenario.sets.some(set => set.key === 'fast' && set.value === 'fast' && scenario.sets.indexOf(set) > scenario.sets.length - 3))
  })
  await open()
  await act(async () => { pop().querySelector('[aria-label="Effort"] [data-key="medium"]').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })) })
  await settle()
  await act(async () => { pop().querySelector('[aria-label="Effort"] [data-key="high"]').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })) })
  await settle()
  check('two arrow presses before Hermes answers move from the focused level and come back to Medium', () => {
    assert.equal(pop().querySelector('[aria-label="Effort"] [aria-checked="true"]').getAttribute('data-key'), 'medium')
    assert.equal(dom.window.document.activeElement?.getAttribute('data-key'), 'medium')
  })
  await key('keydown', 'Escape')
  await releaseAll()
  check('and Medium is what is sent last', () => { assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-frog', key: 'reasoning', value: 'medium' }) })
  scenario.byMethod['config.set'] = plainSet
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium', fast: true } }) })
  await settle()
  await open()
  check('long provider and model names wrap instead of being cut', () => {
    // The rendered picker's own rules, not a synthetic probe that only rejects nowrap: a rule missing from
    // the stylesheet now fails instead of counting as a pass.
    const css = el => dom.window.getComputedStyle(el)
    const prop = (el, name) => css(el).getPropertyValue(name).trim()
    assert.equal(prop(pop().querySelector('.cs-b-mp-head'), 'flex-wrap'), 'wrap', 'the head wraps provider and count')
    assert.equal(prop(pop().querySelector('.cs-b-mp-head b'), 'overflow-wrap'), 'anywhere', 'the provider name breaks')
    assert.equal(prop(pop().querySelector('.cs-b-mp-label'), 'overflow-wrap'), 'anywhere', 'a model name breaks')
    assert.equal(prop(pop().querySelector('.cs-b-mp-ehead'), 'flex-wrap'), 'wrap', 'the effort heading wraps')
    assert.equal(prop(pop().querySelector('.cs-b-mp-emodel'), 'overflow-wrap'), 'anywhere', 'the effort model name breaks')
  })
  await press(tile('Starred'))
  check('the starred list names each row\u2019s provider on a second line that wraps too', () => {
    const label = pop().querySelector('.cs-b-mp-label.two')
    assert.ok(label, 'the starred list mixes providers, so it names each row\u2019s')
    assert.equal(dom.window.getComputedStyle(label.querySelector('span')).getPropertyValue('overflow-wrap').trim(), 'anywhere')
  })
  await press(tile('ChatGPT or Codex Subscription'))
  await key('keydown', 'Escape')

  // Review round 3: a message sent right after a switch waits for it, the Standard reset included.
  const calls = []
  const later = []
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params); calls.push(`${params.key}=${params.value}`)
    return new Promise(done => { later.push(() => done({ key: params.key, value: params.value })) })
  }
  scenario.byMethod['prompt.submit'] = params => { calls.push(`submit:${params.text}`); return { ok: true } }
  await open()
  await press(tile('Anthropic'))
  await press(row('claude-opus-5-5'))
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'make it rain')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await settle()
  check('a message sent while the switch is on its way waits for the model', () => { assert.deepEqual(calls, ['model=claude-opus-5-5 --provider anthropic --session']) })
  await act(async () => { later.shift()() }); await settle()
  check('then for the Standard reset', () => { assert.deepEqual(calls.slice(1), ['fast=normal']) })
  await act(async () => { later.shift()() }); await settle(60)
  check('and only then goes to Hermes', () => { assert.deepEqual(calls.slice(2), ['submit:make it rain']) })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-frog', payload: { text: 'Rain added.' } }) })
  await settle()
  // A switch that fails keeps the message to send again.
  let refuse
  scenario.byMethod['config.set'] = params => { calls.push(`${params.key}=${params.value}`); return new Promise((_, fail) => { refuse = () => fail(new Error('provider refused')) }) }
  await open()
  await press(tile('ChatGPT or Codex Subscription'))
  await press(row('gpt-6.2-sol'))
  await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add thunder')
  await click('Send', view.node.querySelector('.cs-b-comp'))
  await settle()
  await act(async () => { refuse() })
  await settle(80)
  check('when the switch fails the message is not sent, and it can be sent again', () => {
    assert.ok(!calls.includes('submit:add thunder'))
    assert.match(view.node.querySelector('.cs-b-turns, .cs-b-tx')?.textContent ?? view.node.textContent, /The model change did not go through/)
  })
  scenario.byMethod['config.set'] = plainSet
  scenario.byMethod['prompt.submit'] = () => ({ ok: true })
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium', fast: false } }) })
  await settle()

  // Review round 3: no speed change while a model's cost question is open, and none reaches it after Use it.
  let costAsked = false
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params)
    if (params.key === 'model' && !params.confirm_expensive_model) { costAsked = true; return { confirm_required: true, confirm_message: 'Opus costs more.' } }
    return { key: params.key, value: params.value }
  }
  await open()
  await press(tile('Anthropic'))
  await press(row('claude-opus-5-5'))
  await settle()
  check('while a model asks "Use it", Standard / Fast cannot be changed', () => {
    assert.ok(costAsked); assert.ok(pop().querySelector('.cs-b-mp-confirm'))
    assert.ok([...speed().querySelectorAll('button')].every(node => node.disabled))
  })
  const mark = scenario.sets.length
  await click('Fast', speed())
  await click('Use it', pop())
  await settle()
  check('so Use it switches without sending Fast to the new model', () => {
    assert.ok(!scenario.sets.slice(mark).some(set => set.key === 'fast' && set.value === 'fast'))
    assert.match(chip().textContent, /Claude Opus 5\.5/); assert.ok(!chip().querySelector('.cs-b-mp-bolt'))
  })
  await key('keydown', 'Escape')
  scenario.byMethod['config.set'] = plainSet
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium', fast: true } }) })
  await settle()

  // A narrow window: the Effort column narrows, drops its note, and the words shorten. The open panel follows a resize.
  const width = dom.window.innerWidth
  await open()
  check('the panel opens at its full width', () => { assert.ok(!pop().classList.contains('narrow')) })
  dom.window.innerWidth = 470
  await act(async () => { dom.window.dispatchEvent(new dom.window.Event('resize')) })
  check('a window made narrow while the panel is open narrows it at once', () => {
    assert.ok(pop().classList.contains('narrow')); assert.ok(!pop().classList.contains('tiny'))
    assert.ok(!pop().querySelector('.cs-b-mp-enote'))
    assert.equal(pop().querySelector('.cs-b-mp-head').textContent, 'ChatGPT or Codex Subscription· 19')
    assert.match(pop().querySelector('.cs-b-mp-manage').textContent, /^Providers$/)
  })
  await key('keydown', 'Escape')
  dom.window.innerWidth = 340
  await open()
  check('too narrow for three columns, Effort moves under the models', () => { assert.ok(pop().classList.contains('tiny')) })
  await key('keydown', 'Escape')
  dom.window.innerWidth = width
  await view.close()

  // New Game: the draft pick remembers fast mode and sends it with session.create, for Codex and OpenAI API models only.
  scenario.storage.buildSelected = 'new'
  scenario.storage.buildModel = { model: 'gpt-6.2-sol', provider: 'openai-codex', effort: 'low' }
  const creates = []
  scenario.byMethod['session.create'] = params => {
    const n = creates.push(params)
    return { session_id: `rt-new-${n}`, stored_session_id: `st-new-${n}`, info: params, messages: [] }
  }
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
  scenario.storage.buildSelected = 'new'
  scenario.storage.buildModel = { model: 'gpt-6.2', provider: 'openai-api' }
  const api = await mount(page)
  await settle()
  await act(async () => { api.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Fast', api.node.querySelector('[aria-label="Speed"]'))
  await typeInto(api.node.querySelector('textarea[aria-label="Your game idea"]'), 'a heron game')
  await act(async () => { api.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('an OpenAI API draft with Fast makes its conversation with fast mode on', () => {
    assert.deepEqual([creates.at(-1).model, creates.at(-1).provider, creates.at(-1).fast], ['gpt-6.2', 'openai-api', true])
  })
  await api.close()
})
