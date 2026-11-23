// The Build page, part one: New Game, the streamed conversation, questions and approvals, the games menu,
// binding a game to its conversation, an older backend, and a resumed conversation with its art and build card.
// Part two is page-build-turns.test.mjs.
// Run alone: node tests/page/page-build.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, act, dom, emit, scenario, page, click, tab, settle, holdTimers, button, typeInto, key, mount, check, answered, installAnswer, complete }) => {
  // Where the Emulator scenarios leave the app: a game loaded in the player.
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-two', title: 'Comet Drift' })
  scenario.install = installAnswer({ state: 'idle' })
  // The open-request poll (a 1.2 to 4 s timer) runs when clock.fire() says, not when a real clock gets there.
  const clock = holdTimers()

  // 14. Build: one game, one conversation, driven through the gateway and the event stream.
  // The games are a menu on the title: open it, take a copy, close it again.
  const gamesMenu = async view => {
    await act(async () => { view.node.querySelector('.cs-b-sw').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    const menu = view.node.querySelector('.cs-b-sw-pop').cloneNode(true)
    await key('keydown', 'Escape')
    return menu
  }
  const fire = (node, type, init = {}) => act(async () => { node.dispatchEvent(new dom.window.MouseEvent(type, { bubbles: true, cancelable: true, ...init })) })
  const editAGame = async view => {
    await fire(view.node.querySelector('.cs-b-sw'), 'click')
    const edit = [...view.node.querySelectorAll('.cs-b-sw-pop button')].find(node => /Edit a game/.test(node.textContent))
    await fire(edit, 'click')
  }
  // Edit a game's list: open the menu, go to the library, take a copy, back out with Escape twice.
  const libraryMenu = async view => {
    await editAGame(view)
    const menu = view.node.querySelector('.cs-b-sw-pop').cloneNode(true)
    await key('keydown', 'Escape'); await key('keydown', 'Escape')
    return menu
  }
  const pickFromLibrary = async (view, title) => {
    await editAGame(view)
    await fire([...view.node.querySelectorAll('.cs-b-sw-list button')].find(node => node.textContent.includes(title)), 'click')
    await settle()
  }
  buildScenario()
  const lib14 = [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio', state: 'ready',
    rom: null, webExport: true, thumb: null, chat: null, error: null }]
  scenario.games = answered({ games: lib14, device: { hardwareEnabled: false, skipped: true } })
  const submits = []
  let created = 0
  scenario.byMethod['session.create'] = params => { created += 1; scenario.lastCreate = params; return { session_id: `rt-new-${created}`, stored_session_id: `st-new-${created}`, messages: [] } }
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, messages: [
    { role: 'user', content: 'make the frog jump' }, { role: 'assistant', content: [{ type: 'text', text: 'Added a jump.' }],
      tool_calls: [{ id: 't0', function: { name: 'chromatic_rom_build' } }] },
    { role: 'tool', tool_call_id: 't0', content: '{}' }, { role: 'user', text: 'secret', display_kind: 'hidden' }] })
  scenario.byMethod['session.interrupt'] = params => { scenario.interrupted = params; return { ok: true } }
  const buildCalls = []
  let buildAnswer = params => ({ ok: true })
  scenario.byMethod['plugin.hermretro.build'] = params => { buildCalls.push(params); return buildAnswer(params) }
  const build14 = await mount(page)
  await tab('Setup')
  await click('Check everything again')
  await tab('Build')
  let menu14 = await gamesMenu(build14)
  const shelf14 = await libraryMenu(build14)
  check('Build opens on New Game: one centred composer and two explained choices, no name field, genre chips or hardware choice', () => {
    const page = build14.node.querySelector('.cs-b-new')
    assert.match(page.querySelector('h1').textContent, /^What are we making\?$/)
    assert.ok(page.querySelector('.cs-b-comp textarea[aria-label="Your game idea"]'), 'the Build page composer')
    assert.ok(!page.querySelector('input'), 'no name field')
    const opts = [...page.querySelectorAll('[role="radiogroup"] [role="radio"]')]
    assert.deepEqual(opts.map(o => o.querySelector('b').textContent), ['Build it', 'Plan first'])
    assert.deepEqual(opts.map(o => o.getAttribute('aria-checked')), ['true', 'false'], 'Build it is the default')
    assert.match(opts[0].textContent, /Approve a short list before the project is created/)
    assert.match(opts[1].textContent, /brief, backlog and test plan\. Approve the brief before authoring begins/)
    assert.ok(!/Game Boy\b(?! Color)/.test(page.textContent.replace('Game Boy Color', '')), 'no hardware choice')
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
  })
  check('the menu lists only games being edited; the rest of the library is under Edit a game', () => {
    assert.match(menu14.textContent, /New gameEdit a game/)
    assert.ok(!/Frog Post/.test(menu14.textContent)); assert.ok(!/Editing now/.test(menu14.textContent))
    assert.match(shelf14.textContent, /Frog Post/); assert.ok(shelf14.querySelector('input[aria-label="Search your games"]'))
    assert.ok(!build14.node.querySelector('.cs-b-sw-pop'), 'Escape backs out of the list, then closes the menu')
  })
  await typeInto(build14.node.querySelector('textarea[aria-label="Your game idea"]'), 'a lighthouse keeper in a storm')
  build14.node.querySelector('[role="radio"][data-mode="plan"]').click()
  await settle()
  check('choosing Plan first checks it, and the send button says it starts planning', () => {
    assert.equal(build14.node.querySelector('[data-mode="plan"]').getAttribute('aria-checked'), 'true')
    assert.equal(build14.node.querySelector('[data-mode="build"]').getAttribute('aria-checked'), 'false')
    assert.equal(build14.node.querySelector('.cs-b-new .cs-b-send').getAttribute('aria-label'), 'Start planning')
  })
  build14.node.querySelector('[role="radio"][data-mode="build"]').click()
  await settle()
  // The real gateway answers a New Game's first message "queued" (its own queue, nothing ahead): it starts at once.
  const plainSubmit14 = scenario.byMethod['prompt.submit']
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued', forwarded: true } }
  build14.node.querySelector('.cs-b-new .cs-b-send').click()
  await settle()
  scenario.byMethod['prompt.submit'] = plainSubmit14
  check('a first message Hermes answers "queued" with no turn running stays in the conversation, not in the queue', () => {
    assert.ok(!build14.node.querySelector('.cs-b-user.queued'))
    assert.equal(build14.node.querySelector('.cs-b-user').textContent, 'a lighthouse keeper in a storm')
  })
  check('sending makes a hidden New game session, records it as a New Game with no name, then sends the idea as written', () => {
    assert.deepEqual(scenario.lastCreate, { hidden: true, source: 'gui' })
    assert.deepEqual(buildCalls.at(-1), { action: 'start', stored: 'st-new-1', name: null, plan: false })
    assert.equal(submits.at(-1).session_id, 'rt-new-1'); assert.match(submits.at(-1).submission_id, /^uuid-/)
    assert.equal(submits.at(-1).text, 'a lighthouse keeper in a storm', 'the backend tells the agent how to start')
  })
  menu14 = await gamesMenu(build14)
  check('the new game is listed as working, with its own conversation open and the user\'s words in a bubble', () => {
    assert.match(menu14.textContent, /Editing nowNew gameHermRetro is working/, 'unnamed until the agent creates the project')
    assert.ok(menu14.querySelector('.cs-b-spin'))
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
    assert.equal(build14.node.querySelector('.cs-b-user').textContent, 'a lighthouse keeper in a storm')
  })
  check('while the agent works, the status line above the message box says so, and Stop is there', () => {
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /HermRetro is thinking/)
    assert.ok(button('Stop'))
  })
  // Text streams in batches (one render per frame); everything else lands at once.
  const ev = (type, payload, extra = {}) => act(async () => { emit({ type, session_id: 'rt-new-1', payload, ...extra }); await new Promise(resolve => setTimeout(resolve, 80)) })
  await ev('message.start', { turn_id: 'T1' }, { seq: 1 })
  await ev('message.delta', { text: 'Making ', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 2 })
  await ev('message.delta', { text: 'Making the project', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 3 })
  await ev('message.delta', { text: 'ignored', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 3 })
  await ev('tool.start', { tool_id: 'c0', name: 'tool_describe', args: {} }, { seq: 4 })
  await ev('tool.start', { tool_id: 'c1', name: 'chromatic_project_create', args: { name: 'Lamplight', content: 'x'.repeat(5000) } }, { seq: 5 })
  await act(async () => { emit({ type: 'message.delta', session_id: 'rt-other', payload: { text: 'not ours' } }) })
  check('the stream lands in this conversation only, re-sent chunks are dropped, and steps read in plain words', () => {
    assert.equal(build14.node.querySelector('.cs-b-agent').textContent, 'Making the project')
    assert.ok(!build14.node.textContent.includes('not ours')); assert.ok(!build14.node.textContent.includes('ignored'))
    const rows = build14.node.querySelectorAll('.cs-b-tool')
    assert.equal(rows.length, 1, 'plumbing such as tool_describe is not a step')
    assert.equal(rows[0].dataset.state, 'running'); assert.match(rows[0].textContent, /Creating the project/)
    assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'true', 'the steps are open while it works')
    assert.match(build14.node.querySelector('.cs-b-wk-head').textContent, /Working for/)
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /HermRetro is creating the project/)
    assert.ok(!build14.node.querySelector('.cs-b-who'), 'no name over the reply, as in a chat thread')
  })
  // Questions reach the app as server requests: while the turn runs the page reads the open ones.
  let openRequests = [{ id: 'srq-1', method: 'clarify', params: { session_id: 'rt-new-1', questions: [
    { qid: 'q0', question: 'What is the core loop?', choices: ['Explore (Recommended)', 'Sneak'] }, { qid: 'q1', question: 'How long?', choices: ['Short', 'Long'] }] } }]
  const plainResume = scenario.byMethod['session.resume']
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? { session_id: params.session_id, running: true, open_requests: openRequests } : plainResume(params))
  scenario.locks = []
  scenario.byMethod['clarify.lock'] = params => { scenario.locks.push(params); if (scenario.locks.length === 2) openRequests = []; return { status: 'ok', remaining: [] } }
  await clock.fire()
  menu14 = await gamesMenu(build14)
  check('a question is asked in the message box, with numbered choices and the suggested one marked', () => {
    assert.equal(build14.node.querySelectorAll('.cs-b-card.ask').length, 1)
    assert.ok(build14.node.querySelector('.cs-b-comp.asking .cs-b-card.ask'), 'in the box, not in the thread')
    assert.ok(!build14.node.querySelector('.cs-b-comp textarea'), 'the box is the question while it is open')
    const card = build14.node.querySelector('.cs-b-card.ask')
    assert.match(card.textContent, /What is the core loop\?.*Explore.*Suggested.*Sneak.*How long\?/)
    assert.ok(!card.textContent.includes('(Recommended)'))
    assert.ok(button('Send answer').disabled, 'every question needs an answer first')
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /waiting for your answer/)
    assert.match(menu14.textContent, /Needs your answer/)
  })
  await key('keydown', '2')
  await typeInto(build14.node.querySelectorAll('.cs-b-own')[1], 'about ten minutes')
  await click('Send answer', build14.node)
  await settle()
  check('a number key picks a choice, Send answer locks each question, and the answers become a step', () => {
    assert.deepEqual(scenario.locks, [{ request_id: 'srq-1', question_id: 'q0', answer: 'Sneak' }, { request_id: 'srq-1', question_id: 'q1', answer: 'about ten minutes' }])
    assert.equal(build14.node.querySelectorAll('.cs-b-card.ask').length, 0)
    assert.match(build14.node.querySelector('.cs-b-wk').textContent, /You answeredSneakabout ten minutes/)
  })
  scenario.byMethod['session.resume'] = plainResume
  await ev('tool.complete', { tool_id: 'c1', name: 'chromatic_project_create', result: { ok: false, error: 'folder exists' } }, { seq: 6 })
  // A build that ran and stopped, as the engine answers it live: success false, the reason in a diagnostic.
  await ev('tool.start', { tool_id: 'b1', name: 'chromatic_rom_build', args: {} }, { seq: 7 })
  await ev('tool.complete', { tool_id: 'b1', name: 'chromatic_rom_build', result: { result: 'Operation failed (diagnostics: 1).', structuredContent: { success: false, diagnostics: [{ severity: 'error', message: 'Bank 3 is full.' }] } } }, { seq: 8 })
  await ev('message.complete', { text: 'Making the project', status: 'complete' }, { seq: 9 })
  check('a build that stopped, live, is a failed build card with its reason and no Play', () => {
    const card = build14.node.querySelector('.cs-b-bc')
    assert.ok(card?.classList.contains('bad')); assert.match(card.textContent, /didn’t finish.*Bank 3 is full/)
    assert.ok(![...card.querySelectorAll('button')].some(node => /^\s*Play\b/.test(node.textContent)), 'nothing to play from a build that stopped')
  })
  check('a failed step says why; the turn end folds the steps into "Worked for", ends the status, and keeps one reply', () => {
    const row = build14.node.querySelector('.cs-b-tool')
    assert.equal(row.dataset.state, 'failed'); assert.match(row.textContent, /Creating the project failed.*folder exists/)
    assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'false')
    assert.match(build14.node.querySelector('.cs-b-wk-head').textContent, /Worked for \d+s/)
    assert.equal(build14.node.querySelectorAll('.cs-b-agent').length, 1); assert.ok(!button('Stop'))
    assert.ok(!build14.node.querySelector('.cs-b-status'))
  })
  await click('Worked for', build14.node)
  check('the folded steps open again on a click', () => { assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'true') })
  // The gateway restarted: a new replay epoch counts from 1 again and must not be dropped as seen.
  await ev('message.start', { turn_id: 'T2' }, { seq: 1, replay_epoch: 'E2' })
  await ev('message.delta', { text: 'After restart', turn_id: 'T2', segment: 0, offset: 0 }, { seq: 2, replay_epoch: 'E2' })
  check('after a gateway restart (new replay epoch) the stream is shown again, as a new reply', () => {
    assert.match([...build14.node.querySelectorAll('.cs-b-agent')].at(-1).textContent, /After restart/)
    assert.equal(build14.node.querySelectorAll('.cs-b-her').length, 2)
  })
  // A question announced as an event and then seen again by the poll is one card; settling it answers it.
  await ev('approval.request', { request_id: 'ap-1', command: 'flash', description: 'Flash the cart' }, { seq: 3, replay_epoch: 'E2' })
  scenario.byMethod['session.resume'] = params => (params.omit_messages
    ? { session_id: params.session_id, running: true, open_requests: [{ id: 'ap-1', method: 'approval', params: { command: 'flash' } }] }
    : plainResume(params))
  await clock.fire()
  check('an approval seen both as an event and by the poll is one card', () => {
    assert.equal(build14.node.querySelectorAll('.cs-b-card.warn').length, 1)
    assert.match(build14.node.querySelector('.cs-b-comp.asking .cs-b-card.warn').textContent, /needs your OK/)
  })
  await ev('approval.settled', { request_id: 'ap-1' }, { seq: 4, replay_epoch: 'E2' })
  scenario.byMethod['session.resume'] = plainResume
  // A second approval the turn never settles: when the turn ends it has expired and must not hold the message box.
  await ev('approval.request', { request_id: 'ap-2', command: 'flash', description: 'Flash again' }, { seq: 5, replay_epoch: 'E2' })
  await ev('error', { message: 'provider went away' }, { seq: 6, replay_epoch: 'E2' })
  check('an error frame ends the turn and says why in a card; an approval it left open no longer holds the box', () => {
    assert.match(build14.node.querySelector('.cs-b-card.bad').textContent, /Something went wrong.*provider went away/); assert.ok(!button('Stop'))
    assert.equal(build14.node.querySelectorAll('.cs-b-card.warn').length, 0)
    assert.ok(build14.node.querySelector('.cs-b-comp textarea')); assert.ok(!build14.node.querySelector('.cs-b-comp.asking'))
  })
  // The game the conversation made appears in the library: the conversation becomes that game's.
  scenario.games = answered({ games: [...lib14], pending: [{ storedId: 'st-new-1', name: 'Lamplight' }], device: { hardwareEnabled: false, skipped: true } })
  await build14.rerender(); await settle()
  menu14 = await gamesMenu(build14)
  check('until its project exists the New Game conversation is listed from the backend, once', () => {
    assert.equal((menu14.textContent.match(/Lamplight/g) ?? []).length, 1)
  })
  const replyDraft = 'Give the keeper a raincoat.'
  await typeInto(build14.node.querySelector('textarea[aria-label="Message Hermes"]'), replyDraft)
  lib14.push({ id: 'aaa000aaa000', title: 'Lamplight', projectRoot: '/home/u/games/Lamplight', kind: 'gbstudio', state: 'unbuilt',
    rom: null, webExport: false, thumb: null, chat: null, session: { storedId: 'st-new-1' }, error: null })
  scenario.games = answered({ games: [...lib14], pending: [], device: { hardwareEnabled: false, skipped: true } })
  await build14.rerender(); await settle()
  menu14 = await gamesMenu(build14)
  check('once the backend binds the game it made, the conversation is that game\'s and stays selected', () => {
    assert.equal(menu14.textContent.match(/Lamplight/g).length, 1)
    assert.ok(!/Setting up/.test(menu14.textContent))
    assert.equal(build14.node.querySelector('.cs-b-head h2').textContent, 'Lamplight')
    assert.equal(build14.node.querySelector('.cs-b-agent').textContent, 'Making the project')
    assert.equal(build14.node.querySelector('textarea[aria-label="Message Hermes"]').value, replyDraft)
  })
  const shelfLamp = await libraryMenu(build14)
  check('a game with its own conversation is not in the Edit a game list, and the list says it is open above', () => {
    assert.ok(!/Lamplight/.test([...shelfLamp.querySelectorAll('.cs-b-sw-list')].map(node => node.textContent).join('')))
    assert.match(shelfLamp.querySelector('.cs-b-sw-foot').textContent, /Lamplight is already open above\./)
  })
  await pickFromLibrary(build14, 'Frog Post')
  menu14 = await gamesMenu(build14)
  check('picking a game from Edit a game opens it, and it joins Editing now', () => {
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'Frog Post')
    assert.match(menu14.textContent, /Editing now.*Frog PostNew editing chat.*Lamplight/)
    assert.ok(!/Edit a game/.test(menu14.textContent), 'nothing left in the library: no Edit a game')
  })
  await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: '2', ctrlKey: true, bubbles: true, cancelable: true })) })
  await settle()
  menu14 = await gamesMenu(build14)
  check('Ctrl+2 switches to the second game in the menu; a game left without a conversation drops out of it', () => {
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'Lamplight')
    assert.ok(!/Frog Post/.test(menu14.textContent))
  })
  await pickFromLibrary(build14, 'Frog Post')
  check('a game with no conversation opens a blank one; nothing is created until the first message', () => {
    assert.equal(created, 1); assert.match(build14.node.textContent, /Tell HermRetro what to make or change in Frog Post/)
  })
  await typeInto(build14.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add rain')
  await click('Send', build14.node.querySelector('.cs-b-comp'))
  await settle()
  check('the first message creates the conversation, binds it to the game in the backend, and sends what the user typed', () => {
    assert.equal(created, 2)
    assert.deepEqual(buildCalls.at(-1), { action: 'bind', game: 'fff666fff666', stored: 'st-new-2' })
    assert.equal(submits.at(-1).text, 'add rain')
    assert.equal([...build14.node.querySelectorAll('.cs-b-user')].at(-1).textContent, 'add rain')
  })
  // Stop editing (right-click a game being edited): the game is unbound and its old conversation un-hidden.
  scenario.byMethod['session.set_hidden'] = params => { scenario.unhidden = params; return { hidden: false } }
  const frogRow = () => [...build14.node.querySelectorAll('.cs-b-sw-list button')].find(node => node.textContent.includes('Frog Post'))
  await fire(build14.node.querySelector('.cs-b-sw'), 'click')
  await fire(frogRow(), 'contextmenu', { clientX: 60, clientY: 120 })
  check('right-clicking a game being edited offers Open in full chat and Stop editing, and nothing else', () => {
    const items = [...build14.node.querySelectorAll('.cs-b-ctx button')].map(node => node.textContent)
    assert.deepEqual(items, ['Open in full chat', 'Stop editing'])
    assert.ok(build14.node.querySelector('.cs-b-ctx button.danger').disabled, 'not while the agent works')
  })
  await key('keydown', 'Escape'); await key('keydown', 'Escape')
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-new-2', payload: { text: 'Raining now.' } }) })
  await settle()
  await fire(build14.node.querySelector('.cs-b-sw'), 'click')
  await fire(frogRow(), 'contextmenu', { clientX: 60, clientY: 120 })
  await fire(build14.node.querySelector('.cs-b-ctx button.danger'), 'click')
  await settle()
  menu14 = await gamesMenu(build14)
  const shelfAfter = await libraryMenu(build14)
  check('Stop editing unbinds the game, shows its old conversation in the Hermes sidebar, and puts it back under Edit a game', () => {
    assert.deepEqual(buildCalls.at(-1), { action: 'unbind', game: 'fff666fff666', stored: 'st-new-2' })
    assert.deepEqual(scenario.unhidden, { session_id: 'st-new-2', hidden: false })
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
    assert.ok(!/Frog Post/.test(menu14.textContent)); assert.match(shelfAfter.textContent, /Frog Post/)
  })
  await build14.close()
  // An older backend without the build RPC: the binding lasts this visit, and the message names the project.
  buildAnswer = () => { throw Object.assign(new Error('unknown method'), { code: -32601 }) }
  lib14[0] = { ...lib14[0], session: null }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.buildSelected = 'fff666fff666'
  const build14o = await mount(page)
  await settle()
  await typeInto(build14o.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add snow')
  await click('Send', build14o.node.querySelector('.cs-b-comp'))
  await settle()
  check('on an older backend the first message names the project instead, and still shows what the user typed', () => {
    assert.match(submits.at(-1).text, /\/home\/u\/games\/FrogPost/); assert.match(submits.at(-1).text, /add snow$/)
    assert.equal([...build14o.node.querySelectorAll('.cs-b-user')].at(-1).textContent, 'add snow')
  })
  await build14o.close()
  buildAnswer = () => ({ ok: true })
  // A bound game from an earlier visit resumes its stored conversation: history with timings, Hermes's
  // deferred tool_call unwrapped, and the images its steps made.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-old' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.buildSelected = 'fff666fff666'
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make the frog jump', timestamp: 1000 },
    { role: 'assistant', content: [{ type: 'text', text: 'On it.' }], timestamp: 1001, tool_calls: [
      { id: 'v1', function: { name: 'vision_analyze', arguments: JSON.stringify({ image_url: '/home/u/games/FrogPost/docs/art/frog.png', question: 'ok?' }) } },
      { id: 'w1', function: { name: 'tool_call', arguments: JSON.stringify({ calls: [{ name: 'chromatic_asset_import', arguments: { assetPath: 'assets/sprites/frog.png', kind: 'sprite' } }, { name: 'chromatic_rom_build', arguments: {} }] }) } }] },
    { role: 'tool', tool_call_id: 'v1', name: 'vision_analyze', timestamp: 1004 },
    { role: 'tool', tool_call_id: 'w1', name: 'tool_call', args: { calls: [{ name: 'chromatic_asset_import', arguments: { assetPath: 'assets/sprites/frog.png' } }] }, timestamp: 1020 },
    { role: 'assistant', content: 'Added a jump.', timestamp: 1167 },
    { role: 'user', text: 'secret', display_kind: 'hidden' }] })
  scenario.assetCalls = []
  scenario.byMethod['plugin.hermretro.asset'] = params => {
    scenario.assetCalls.push(params.path)
    return { ok: true, path: params.path, name: params.path.split('/').pop(), relative: 'assets/sprites/frog.png', kind: 'sprite', width: 32, height: 16, bytes: 90,
      dataUrl: 'data:image/png;base64,iVBORw0KGgo=', sprite: { name: 'Frog', frameWidth: 16, frameHeight: 16, animSpeed: 15 } }
  }
  // What the viewer shows beside a sprite: its animations (from the sidecar) and kept versions.
  scenario.byMethod['plugin.hermretro.asset_info'] = params => ({ ok: true, path: params.path, relative: 'assets/sprites/frog.png', kind: 'sprite',
    versions: [{ id: '1', at: 1000, file: params.path, current: true }],
    sprite: { name: 'Frog', id: 'frog', type: 'fixed_movement', flipLeft: false, canvasWidth: 16, canvasHeight: 16, animSpeed: 15, numTiles: 4,
      animations: [{ slot: 0, name: 'Idle', frames: [[{ x: 0, y: 0, sliceX: 0, sliceY: 0 }, { x: 8, y: 0, sliceX: 8, sliceY: 0 }]] }] },
    usedIn: [], scenes: [] })
  const build14b = await mount(page)
  await settle(100)
  check('a bound game resumes its stored session: history, plain-word steps from inside tool_call, and how long it took', () => {
    assert.match(build14b.node.textContent, /make the frog jump/); assert.match(build14b.node.textContent, /Added a jump\./)
    assert.ok(!build14b.node.textContent.includes('secret'))
    const steps = [...build14b.node.querySelectorAll('.cs-b-tool')].map(node => node.textContent)
    assert.equal(steps.length, 3, 'a call and its result row are one step; tool_call is its calls')
    assert.match(steps[0], /Looked at frog\.png/); assert.match(steps[1], /Added art to the game/); assert.match(steps[2], /Built the game/)
    assert.match(build14b.node.querySelector('.cs-b-wk-head').textContent, /Worked for 2m 47s· drew the art, built it/)
    assert.equal(build14b.node.querySelector('.cs-b-agent').textContent, 'On it.', 'the words before the first step come first')
  })
  check('the folded line shows what the turn made as a small stack and an \u201cN assets\u201d link (not pictures it only looked at)', () => {
    assert.deepEqual([...new Set(scenario.assetCalls)].sort(), ['/home/u/games/FrogPost/assets/sprites/frog.png', '/home/u/games/FrogPost/docs/art/frog.png'], 'each picture is fetched once')
    const link = build14b.node.querySelector('.cs-b-wk-row .cs-b-wk-assets')
    assert.ok(link); assert.match(link.textContent, /^1 asset$/)
    assert.equal(link.querySelectorAll('.cs-b-stack-i').length, 1)
    assert.ok(!/new images/.test(build14b.node.querySelector('.cs-b-wk-head').textContent))
  })
  check('a turn that built the game ends in build #1, titled by the request, with its game frame saying it is not playable yet', () => {
    const card = build14b.node.querySelector('.cs-b-bc')
    assert.ok(card); assert.equal(card.dataset.build, '1')
    assert.match(card.querySelector('.cs-b-bc-head').textContent, /#1make the frog jump/)
    const frame = build14b.node.querySelector('.cs-b-pc.unplayable')
    assert.ok(frame && !card.contains(frame), 'the frame is under the build line, not in it'); assert.match(frame.textContent, /The playable copy is not ready yet/)
    assert.ok(!build14b.node.querySelector('.cs-ip'))
  })
  check('the header shows the build pill and a Builds menu; the Assets panel and Full chat button are gone', () => {
    assert.equal(build14b.node.querySelector('.cs-b-pill').textContent, 'Build #1 · up to date')
    assert.ok(button('Builds')); assert.ok(!build14b.node.querySelector('button[aria-label^="Assets"]')); assert.ok(!build14b.node.querySelector('button[aria-label="Open in full chat"]'))
  })
  await act(async () => { build14b.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(50)
  check('the assets link opens the viewer on the picture it made, without folding the steps open', () => {
    const viewer = build14b.node.querySelector('.cs-v')
    assert.ok(viewer); assert.match(viewer.textContent, /Frog/); assert.match(viewer.textContent, /32×16/)
    assert.equal(build14b.node.querySelector('.cs-b-wk').dataset.open, 'false')
    assert.ok(!build14b.node.querySelector('.cs-b-ap'), 'no Assets panel any more')
  })
  check('the viewer is image-first: a sprite has Animation, Sheet, and Details or Change beside it', () => {
    const viewer = build14b.node.querySelector('.cs-v')
    assert.deepEqual([...viewer.querySelectorAll('.cs-v-seg button')].map(node => node.textContent), ['Animation', 'Sheet'])
    assert.deepEqual([...viewer.querySelectorAll('.cs-v-tabs button')].map(node => node.textContent), ['Details', 'Change'])
    assert.match(viewer.querySelector('.cs-v-quote')?.textContent ?? '', /make the frog jump/, 'it quotes the message that asked for it')
  })
  await click('Show in folder', build14b.node.querySelector('.cs-v'))
  check('Show in folder reveals the file', () => { assert.match(scenario.revealed, /frog\.png$/) })
  await key('keydown', 'Escape')
  check('Escape closes the viewer', () => { assert.ok(!build14b.node.querySelector('.cs-v')) })
  await act(async () => { build14b.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(30)
  await click('Change', build14b.node.querySelector('.cs-v-tabs'))
  await typeInto(build14b.node.querySelector('.cs-v-input'), 'make it green')
  await click('Send to HermRetro', build14b.node.querySelector('.cs-v'))
  await settle()
  check('Change sends the request from the viewer, naming the image, and the viewer stays open', () => {
    assert.match(submits.at(-1).text, /^About \/home\/u\/games\/FrogPost\/[^\n]*frog\.png:\nmake it green\n\n- When it is done, build the game and show it to me/)
    const bubble = [...build14b.node.querySelectorAll('.cs-b-user')].at(-1)
    assert.match(bubble.textContent, /frog\.png/); assert.match(bubble.textContent, /make it green$/)
    assert.ok(build14b.node.querySelector('.cs-v'), 'the viewer stays open while it works')
    assert.match(build14b.node.querySelector('.cs-v-pane').textContent, /You asked/)
  })
  await key('keydown', 'Escape')
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Greener now.' } }) })
  await settle()
  await build14b.close()
})
