// New Game starts a fresh thread for each idea and sends only on the selected route.
// Run alone: node tests/page/page-build-model-routing.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, scenario, page, act, emit, mount, settle, typeInto, click, tab, check, answered, holdTimers }) => {
  holdTimers() // Test turns end explicitly through completion events, not the open-request poll.
  buildScenario({ selected: 'new' })
  scenario.games = answered({ games: [], pending: [] })
  const codex = { model: 'gpt-6.2-sol', provider: 'openai-codex' }
  const claude = { model: 'claude-opus-5-5[1m]', provider: 'claude-subscription-directsdk-experimental' }
  scenario.models = answered({ ...claude, providers: [
    { slug: claude.provider, name: 'Claude Subscription', authenticated: true, models: [claude.model] },
    { slug: codex.provider, name: 'ChatGPT or Codex Subscription', authenticated: true, models: [codex.model] }
  ] })

  const calls = []
  let created = 0
  let route = null
  let returnOld = false
  // The canonical gateway treats a title as a lookup key, not a display label. Seed an old thread with that title.
  const old = { session_id: 'rt-old', stored_session_id: 'st-old', info: claude, messages: [{ role: 'user', content: 'an old game' }] }
  scenario.byMethod['session.create'] = params => {
    calls.push(['create', params])
    if (params.title === 'New game' || returnOld) return old
    const n = ++created
    const info = route ?? (params.model ? { model: params.model, provider: params.provider } : codex)
    return { session_id: `rt-new-${n}`, stored_session_id: `st-new-${n}`, info, messages: [] }
  }
  scenario.byMethod['plugin.hermretro.build'] = params => { calls.push(['bind', params]); return { ok: true } }
  scenario.byMethod['prompt.submit'] = params => { calls.push(['submit', params]); return { status: 'queued' } }

  let view = await mount(page)
  await settle()
  const press = selector => act(async () => view.node.querySelector(selector).click())
  const idea = () => view.node.querySelector('textarea[aria-label="Your game idea"]')
  const send = () => press('.cs-b-new .cs-b-send')
  const choose = async (providerName, model) => {
    await press('.cs-b-mp-chip')
    await press(`.cs-b-mp-rail button[aria-label="${providerName}"]`)
    await press(`.cs-b-mp-row[title="${model} · ${providerName}"]`)
  }
  const backToNew = async () => {
    await press('.cs-b-sw')
    await press('.cs-b-sw-pop .cs-b-sw-new')
  }

  await choose('Claude Subscription', claude.model)
  check('clicking the visible default model pins that exact route for future drafts', () => {
    assert.deepEqual(scenario.storage.buildModel, claude)
  })
  await choose('ChatGPT or Codex Subscription', codex.model)
  await typeInto(idea(), 'a racing game')
  await send()
  await settle()
  check('New Game does not reuse the old titled thread and opens on the chosen model', () => {
    assert.deepEqual(calls.map(([step]) => step), ['create', 'bind', 'submit'])
    assert.deepEqual(calls[0][1], { hidden: true, source: 'gui', ...codex })
    assert.equal(calls[1][1].stored, 'st-new-1')
    assert.equal(calls[2][1].session_id, 'rt-new-1')
    assert.equal(calls[2][1].text, 'a racing game')
    assert.match(view.node.querySelector('.cs-b-mp-chip').textContent, /GPT-6\.2 Sol/)
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-1', payload: { text: 'First reply.' } }))
  await backToNew()
  await choose('Claude Subscription', claude.model)
  await typeInto(idea(), 'a flying game')
  await send()
  await settle()
  check('a second game opens a different thread on its own choice', () => {
    assert.deepEqual(calls.map(([step]) => step), ['create', 'bind', 'submit', 'create', 'bind', 'submit'])
    assert.deepEqual(calls[3][1], { hidden: true, source: 'gui', ...claude })
    assert.equal(calls[4][1].stored, 'st-new-2')
    assert.equal(calls[5][1].session_id, 'rt-new-2')
    assert.equal(calls[5][1].text, 'a flying game')
    assert.doesNotMatch(view.node.textContent, /First reply/)
    assert.match(view.node.querySelector('.cs-b-mp-chip').textContent, /Claude Opus 5\.5/)
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-2', payload: { text: 'Second reply.' } }))
  await backToNew()
  await typeInto(idea(), 'a jumping game')
  returnOld = true
  await send()
  await settle()
  check('an existing thread is refused even when its model and provider match', () => {
    assert.equal(calls.length, 7)
    assert.equal(calls.at(-1)[0], 'create')
    assert.match(scenario.notices.at(-1).message, /existing conversation.*not sent/i)
  })
  returnOld = false
  await choose('ChatGPT or Codex Subscription', codex.model)
  route = { ...codex, provider: 'nous' }
  await send()
  await settle()
  check('a wrong provider blocks binding and submission and keeps the idea for retry', () => {
    assert.equal(calls.length, 8)
    assert.equal(calls.at(-1)[0], 'create')
    assert.equal(idea().value, 'a jumping game')
    assert.equal(scenario.notices.at(-1).kind, 'error')
    assert.match(scenario.notices.at(-1).message, /gpt-6\.2-sol.*openai-codex.*not sent/i)
  })
  route = { ...codex, model: 'gpt-5-mini' }
  await send()
  await settle()
  check('a wrong model from the right provider also blocks the send', () => {
    assert.equal(calls.length, 9)
    assert.equal(idea().value, 'a jumping game')
  })
  route = null
  await send()
  await settle()
  check('retry binds and submits to the fresh session when the route matches', () => {
    assert.deepEqual(calls.slice(9).map(([step]) => step), ['create', 'bind', 'submit'])
    assert.equal(calls[10][1].stored, 'st-new-5')
    assert.equal(calls[11][1].session_id, 'rt-new-5')
    assert.equal(calls[11][1].text, 'a jumping game')
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-5', payload: { text: 'Third reply.' } }))
  await view.close()

  scenario.storage.buildSelected = 'new'
  delete scenario.storage.buildModel
  view = await mount(page)
  await settle()
  const defaultStart = calls.length
  await typeInto(idea(), 'a platform game')
  check('the draft shows the cached studio default before the send', () => {
    assert.match(view.node.querySelector('.cs-b-mp-chip').textContent, /Claude Opus 5\.5/)
    assert.equal(scenario.storage.buildModel, undefined, 'the default is not a saved user pick')
  })
  await send()
  await settle()
  check('the unpinned route shown in the draft is still explicit at creation', () => {
    assert.deepEqual(calls[defaultStart], ['create', { hidden: true, source: 'gui', ...claude }])
    assert.equal(calls[defaultStart + 2][1].session_id, 'rt-new-6')
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-6', payload: { text: 'Fourth reply.' } }))
  await view.close()

  const game = { id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', session: { storedId: 'st-missing', exists: false, thisProfile: true } }
  const path = `${game.projectRoot}/assets/sprites/frog.png`
  scenario.games = answered({ games: [game], pending: [], device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['plugin.hermretro.assets'] = () => ({ ok: true, assets: [{ name: 'Frog sprite', path, kind: 'sprite' }] })
  scenario.storage.buildSelected = game.id
  view = await mount(page)
  await settle()
  await click('Start a new conversation', view.node)
  await press('button[aria-label="Mention an asset"]')
  await settle()
  await press('.cs-b-mention-row')
  const edit = () => view.node.querySelector('textarea[aria-label="Message Hermes"]')
  const sendEdit = 'button[aria-label="Send"]'
  await typeInto(edit(), 'make the frog jump')
  const beforeEdit = calls.length
  route = { ...claude, provider: 'nous' }
  await press(sendEdit)
  await settle()
  check('a failed first edit keeps the text and attachment and does not touch the binding', () => {
    assert.deepEqual(calls.slice(beforeEdit).map(([step]) => step), ['create'])
    assert.equal(edit().value, 'make the frog jump')
    assert.match(view.node.querySelector('.cs-b-comp .cs-b-chips').textContent, /Frog sprite/)
    assert.equal(view.node.querySelector(sendEdit).disabled, false)
  })

  route = null
  let finishCreate, finishBind
  const create = scenario.byMethod['session.create']
  const bind = scenario.byMethod['plugin.hermretro.build']
  scenario.byMethod['session.create'] = params => {
    const reply = create(params)
    return new Promise(resolve => { finishCreate = () => resolve(reply) })
  }
  scenario.byMethod['plugin.hermretro.build'] = params => {
    const reply = bind(params)
    return new Promise(resolve => { finishBind = () => resolve(reply) })
  }
  // Both clicks run before React can render the button disabled. The guard must also be synchronous.
  await act(async () => {
    const button = view.node.querySelector(sendEdit)
    button.click()
    button.click()
  })
  await settle()
  check('a duplicate first send cannot open a second replacement thread', () => {
    assert.deepEqual(calls.slice(beforeEdit + 1).map(([step]) => step), ['create'])
    assert.equal(view.node.querySelector(sendEdit).disabled, true)
    assert.equal(edit().disabled, true)
  })
  await act(async () => finishCreate())
  await settle()
  check('the first edit stays disabled until the replacement is bound', () => {
    assert.deepEqual(calls.slice(beforeEdit + 1).map(([step]) => step), ['create', 'bind'])
    assert.equal(view.node.querySelector(sendEdit).disabled, true)
    assert.equal(edit().value, 'make the frog jump')
  })
  const submit = scenario.byMethod['prompt.submit']
  scenario.byMethod['prompt.submit'] = params => {
    submit(params)
    throw new Error('The first submit was rejected')
  }
  await act(async () => finishBind())
  await settle()
  check('once bound, a rejected first submit leaves the full edit for transcript retry only', () => {
    assert.deepEqual(calls.slice(beforeEdit + 1).map(([step]) => step), ['create', 'bind', 'submit'])
    assert.deepEqual(calls[beforeEdit + 2][1], { action: 'bind', game: game.id, stored: 'st-new-8', replace: 'st-missing' })
    assert.equal(calls[beforeEdit + 3][1].session_id, 'rt-new-8')
    assert.equal(calls[beforeEdit + 3][1].text, `About ${path}:\nmake the frog jump`)
    assert.equal(edit().value, '')
    assert.equal(view.node.querySelector(sendEdit).disabled, true)
    assert.equal(view.node.querySelector('.cs-b-comp .cs-b-chips'), null)
    assert.equal(view.node.querySelector('.cs-b-user').textContent.includes('make the frog jump'), true)
  })
  scenario.byMethod['prompt.submit'] = submit
  await click('Try again', view.node.querySelector('.cs-b-card.bad'))
  await settle()
  check('the transcript retries on the bound thread with the original attachment and text', () => {
    assert.deepEqual(calls.slice(beforeEdit + 1).map(([step]) => step), ['create', 'bind', 'submit', 'submit'])
    assert.equal(calls.at(-1)[1].session_id, 'rt-new-8')
    assert.equal(calls.at(-1)[1].text, `About ${path}:\nmake the frog jump`)
    assert.equal(edit().value, '')
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-8', payload: { text: 'The frog jumps.' } }))
  await view.close()

  scenario.byMethod['plugin.hermretro.build'] = params => {
    const result = bind(params)
    const changed = { ...game, session: { ...game.session, storedId: params.stored, exists: true } }
    scenario.games = answered({ games: [changed], pending: [], device: { hardwareEnabled: false, skipped: true } })
    return result
  }
  view = await mount(page)
  await settle()
  await click('Start a new conversation', view.node)
  await typeInto(edit(), 'make the frog swim')
  const beforeNavigation = calls.length
  await press(sendEdit)
  await settle()
  await tab('Prompts')
  assert.equal(edit(), null, 'Build unmounted')
  await tab('Build')
  await settle()
  check('reopening Build cannot start another replacement while the first create is pending', () => {
    const restart = [...view.node.querySelectorAll('button')].find(node => node.textContent === 'Start a new conversation')
    assert.equal(restart?.disabled, true)
    assert.equal(edit().disabled, true)
    assert.deepEqual(calls.slice(beforeNavigation).map(([step]) => step), ['create'])
  })
  await act(async () => finishCreate())
  await settle()
  await view.rerender() // Deliver the updated library response to the reopened Build page.
  check('the first replacement completes on its own thread after reopening Build', () => {
    assert.deepEqual(calls.slice(beforeNavigation).map(([step]) => step), ['create', 'bind', 'submit'])
    assert.equal(calls.at(-1)[1].session_id, 'rt-new-9')
    assert.equal(calls.at(-1)[1].text, 'make the frog swim')
    assert.match(view.node.querySelector('.cs-b-user').textContent, /make the frog swim/)
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-new-9', payload: { text: 'The frog swims.' } }))
  await view.close()
})
