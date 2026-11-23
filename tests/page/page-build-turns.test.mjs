// The Build page, part two: long turns and build cards, suggestions and @ mentions, the inline player, removed
// and lost conversations, the model and effort picker, and the game card on the Games page.
// Part one is page-build.test.mjs.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

// The player RPC's device skins (player/skins/), as the backend answers them.
const SKINS = { skins: [{ id: 'hermes-midnight', name: 'Nous Black', swatch: '#15171c' }, { id: 'hermes-blue', name: 'Nous Blue', swatch: '#0053fd' }], skin: 'hermes-midnight' }

await runScenario(async ({ buildScenario, act, dom, emit, scenario, page, text, click, settle, button, typeInto, key, mount, check, answered, installAnswer, complete }) => {
  // Where the Emulator scenarios leave the app: a game loaded in the player.
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-two', title: 'Comet Drift', ...SKINS })
  scenario.install = installAnswer({ state: 'idle' })

  // The same games, conversations and backend replies as page-build.test.mjs.
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
  const plainResume = scenario.byMethod['session.resume']
  scenario.byMethod['session.set_hidden'] = params => { scenario.unhidden = params; return { hidden: false } }
  // Part one leaves Lamplight's New Game conversation (rt-new-1 / st-new-1) open on the page: start it the
  // same way, end its turn, and let the library bind the game it made.
  const lamplight = await mount(page)
  await settle()
  await typeInto(lamplight.node.querySelector('textarea[aria-label="Your game idea"]'), 'a lighthouse keeper in a storm')
  lamplight.node.querySelector('.cs-b-new .cs-b-send').click()
  await settle()
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-new-1', payload: { text: 'Making the project' } }) })
  await settle()
  lib14.push({ id: 'aaa000aaa000', title: 'Lamplight', projectRoot: '/home/u/games/Lamplight', kind: 'gbstudio', state: 'unbuilt',
    rom: null, webExport: false, thumb: null, chat: null, session: { storedId: 'st-new-1' }, error: null })
  scenario.games = answered({ games: [...lib14], pending: [], device: { hardwareEnabled: false, skipped: true } })
  await lamplight.rerender(); await settle()
  await lamplight.close()
  // Frog Post is bound to its stored conversation st-old, whose history built the game once.
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
  scenario.assetRoots = new Set()
  scenario.byMethod['plugin.hermretro.asset'] = params => {
    scenario.assetCalls.push(params.path)
    scenario.assetRoots.add(params.root)
    if (params.path.startsWith('/home/u/games/Lamplight/')) {
      return { ok: false, code: 'OTHER_GAME', error: 'That image belongs to another game.' }
    }
    return { ok: true, path: params.path, name: params.path.split('/').pop(), relative: 'assets/sprites/frog.png', kind: 'sprite', width: 32, height: 16, bytes: 90,
      dataUrl: 'data:image/png;base64,iVBORw0KGgo=', sprite: { name: 'Frog', frameWidth: 16, frameHeight: 16, animSpeed: 15 } }
  }
  // What the viewer shows beside a sprite: its animations (from the sidecar) and kept versions.
  scenario.byMethod['plugin.hermretro.asset_info'] = params => (scenario.assetRoots.add(params.root), { ok: true, path: params.path, relative: 'assets/sprites/frog.png', kind: 'sprite',
    versions: [{ id: '1', at: 1000, file: params.path, current: true }],
    sprite: { name: 'Frog', id: 'frog', type: 'fixed_movement', flipLeft: false, canvasWidth: 16, canvasHeight: 16, animSpeed: 15, numTiles: 4,
      animations: [{ slot: 0, name: 'Idle', frames: [[{ x: 0, y: 0, sliceX: 0, sliceY: 0 }, { x: 8, y: 0, sliceX: 8, sliceY: 0 }]] }] },
    usedIn: [], scenes: [] })

  // Part one also sent a change from the image viewer in Frog Post's conversation and got a reply: replay that
  // turn, so the checks below run with an earlier live turn between the build and the newest reply, as before.
  {
    const frog = await mount(page)
    await settle(100)
    await act(async () => { frog.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    await settle(30)
    await click('Change', frog.node.querySelector('.cs-v-tabs'))
    await typeInto(frog.node.querySelector('.cs-v-input'), 'make it green')
    await click('Send to HermRetro', frog.node.querySelector('.cs-v'))
    await settle()
    if (!/make it green$/.test([...frog.node.querySelectorAll('.cs-b-user')].at(-1)?.textContent ?? '')) {
      throw new Error('replaying part one: the viewer change was not sent')
    }
    await key('keydown', 'Escape')
    await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Greener now.' } }) })
    await settle()
    await frog.close()
  }

  // A long turn: Simple shows five plain groups, Technical every step; a reply's pictures are small cards.
  const resume14b = scenario.byMethod['session.resume']
  const lib14Session = lib14[0].session
  lib14[0] = { ...lib14[0], session: { storedId: 'st-long' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const callOf = (id, name, args = {}) => ({ id, function: { name, arguments: JSON.stringify(args) } })
  const report14 = { title: 'Robin in the sky', summary: 'A little red robin in a big daytime sky. Fly anywhere with the D-pad.',
    changes: [{ kind: 'added', text: 'Robin sprite, 3 views', asset: 'assets/sprites/bird.png' }, { kind: 'changed', text: 'Camera follows the player' }],
    tested: ['Robin faces where it flies', 'Camera follows'], untested: ['Sound'], notes: ['It only flaps while moving'], suggestions: ['Flap while idle', 'Fly faster'] }
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: 'Planning.', timestamp: 2001, tool_calls: [
      callOf('p1', 'skill_view', { name: 'hermretro:authoring' }), callOf('p2', 'skill_view', { name: 'hermretro:pixel-art' }), callOf('p3', 'chromatic_project_inspect'), callOf('p4', 'chromatic_project_inventory'),
      callOf('a1', 'chromatic_asset_import', { assetPath: 'assets/sprites/bird.png' }), callOf('a2', 'chromatic_sprite_edit'), callOf('a3', 'terminal', { command: 'python draw.py' }),
      callOf('w1', 'chromatic_scene_update'), callOf('w2', 'chromatic_actor_update'),
      callOf('b1', 'chromatic_rom_build'), callOf('b2', 'chromatic_emulator_step'), callOf('r1', 'chromatic_build_report', report14)] },
    ...['p1', 'p2', 'p3', 'p4', 'a1', 'a2', 'a3', 'w1', 'w2', 'b1', 'b2', 'r1'].map((id, index) => ({ role: 'tool', tool_call_id: id, timestamp: 2002 + index })),
    { role: 'assistant', content: 'Here they are:\n\nMEDIA:/home/u/games/FrogPost/assets/sprites/bird.png\nMEDIA:/home/u/games/FrogPost/cover.png\nMEDIA:/home/u/games/Lamplight/cover.png\n\nWant it to flap all the time?', timestamp: 2100 },
    { role: 'user', content: 'add music', timestamp: 3000 },
    // As the gateway resumes it: the build went through Hermes's tool_call door, and its result row has no name.
    { role: 'assistant', content: '', timestamp: 3001, tool_calls: [callOf('m1', 'tool_call', { calls: [{ name: 'chromatic_rom_build', arguments: {} }] })] },
    // The engine's own shape for a build that ran and stopped: success false, the reason in a diagnostic.
    { role: 'tool', tool_call_id: 'm1', content: JSON.stringify({ result: 'Operation failed (diagnostics: 1).', structuredContent: { success: false, diagnostics: [{ severity: 'error', code: 'BANK_FULL', message: 'The song is 2.4 KB too big for the cartridge.' }] } }), timestamp: 3050 },
    { role: 'assistant', content: 'The music did not fit.', timestamp: 3060 }] })
  const build14ph = await mount(page)
  await settle(100)
  check('the report becomes build card #1: title, summary, what changed, and a footer with what was tested', () => {
    const card = build14ph.node.querySelector('.cs-b-bc[data-build="1"]')
    assert.ok(card); assert.match(card.querySelector('.cs-b-bc-title').textContent, /Robin in the sky/)
    assert.match(card.querySelector('.cs-b-bc-sum').textContent, /little red robin/)
    assert.deepEqual([...card.querySelectorAll('.cs-b-bc-changes li')].map(node => node.textContent), ['+Robin sprite, 3 views', '~Camera follows the player'])
    assert.match(card.querySelector('.cs-b-bc-foot').textContent, /✓ 2 play-tested.*○ 1 not tested.*⚠ 1 note/)
    assert.ok(!/chromatic_build_report|Using build report/.test(build14ph.node.textContent), 'the report is not a step')
  })
  check('the reply after a report is a line after the card, and its pictures are small cards in one row', () => {
    const turn = build14ph.node.querySelectorAll('.cs-b-turn')[0]
    const order = [...turn.querySelector('.cs-b-her').children].map(node => node.className.split(' ')[0])
    assert.ok(order.indexOf('cs-b-bc') < order.lastIndexOf('cs-b-agent'), 'card first, then the reply')
    const cards = turn.querySelectorAll('.cs-b-rimgs .cs-b-rchip')
    assert.equal(cards.length, 2)
  })
  check('every picture is asked for as Frog Post\u2019s, so the backend can refuse another game\u2019s', () => {
    assert.deepEqual([...scenario.assetRoots], [lib14[0].projectRoot])
  })
  check('another game\u2019s picture in the reply stays an inert line the app does not open', () => {
    const turn = build14ph.node.querySelectorAll('.cs-b-turn')[0]
    const inert = [...turn.querySelectorAll('[data-markdown][data-inert]')].map(node => node.textContent)
    assert.deepEqual(inert, ['MEDIA:/home/u/games/Lamplight/cover.png'])
  })
  await click('Details', build14ph.node.querySelector('.cs-b-bc[data-build="1"]'))
  check('Details lists what was play-tested, not tested and the notes', () => {
    const details = build14ph.node.querySelector('.cs-b-bc-details').textContent
    assert.match(details, /Play-tested.*Robin faces where it flies.*Not tested.*Sound.*You might notice.*only flaps while moving/)
  })
  check('a failed compile is build #2 that didn\u2019t finish, with what went wrong, and the pill says so', () => {
    const card = build14ph.node.querySelector('.cs-b-bc[data-build="2"]')
    assert.ok(card); assert.ok(card.classList.contains('bad'))
    assert.match(card.textContent, /#2The build didn’t finish/); assert.match(card.textContent, /2\.4 KB too big/)
    assert.ok(button('Ask HermRetro to fix it'))
    assert.match(build14ph.node.querySelector('.cs-b-pill').textContent, /Build #2 didn’t finish/)
    assert.match(build14ph.node.querySelectorAll('.cs-b-turn')[1].textContent, /Worked for [^·]*· 1 step(?!s)/, 'the result row is the build step, not another one')
  })
  check('next-step chips show only under the newest reply', () => {
    assert.equal(build14ph.node.querySelectorAll('.cs-b-next-steps').length, 0, 'the last turn reported nothing to suggest')
  })
  await click('Worked for', build14ph.node.querySelector('.cs-b-turn'))
  check('Simple shows the turn as five plain groups, folded, each with its step count', () => {
    const heads = [...build14ph.node.querySelectorAll('.cs-b-ph-head')].map(node => node.textContent)
    assert.deepEqual(heads.map(text => text.replace(/\d+ steps?.*/, '').trim()), ['Planned it', 'Drew the art', 'Set up the level', 'Built it', 'Play-tested it'])
    assert.match(heads[1], /3 steps/, 'a command joins the group it was helping')
    assert.equal(build14ph.node.querySelectorAll('.cs-b-ph-body').length, 0, 'a finished turn starts with every group folded')
  })
  await click('Planned it', build14ph.node)
  check('a group of only glances says so instead of listing them', () => {
    const body = build14ph.node.querySelector('.cs-b-ph-body')
    assert.equal(body.querySelectorAll('.cs-b-tool').length, 0); assert.match(body.textContent, /Technical shows them/)
  })
  await click('Technical', build14ph.node.querySelector('.cs-b-wk-mode'))
  check('Technical lists every step with its detail, for every turn', () => {
    assert.equal(build14ph.node.querySelector('.cs-b-turn .cs-b-wk-inner').querySelectorAll('.cs-b-tool').length, 11)
    assert.match(build14ph.node.querySelector('.cs-b-turn .cs-b-wk-inner').textContent, /python draw\.py/)
  })
  await click('Simple', build14ph.node.querySelector('.cs-b-wk-mode'))
  await click('Builds', build14ph.node.querySelector('.cs-b-head'))
  await settle(30)
  await key('keydown', 'Escape')
  await build14ph.close()
  // The report's suggestions and the @ picker: chips fill the box; @ lists the game's pictures.
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b1', 'chromatic_rom_build'), callOf('r1', 'chromatic_build_report', report14)] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 2010 },
    { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report: report14 }), timestamp: 2011 },
    { role: 'assistant', content: 'Want it to flap all the time?', timestamp: 2012 }] })
  lib14[0] = { ...lib14[0], session: { storedId: 'st-long2' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const gamePictures = []
  scenario.byMethod['plugin.hermretro.assets'] = params => {
    gamePictures.push(params.game)
    return { ok: true, assets: [
      { path: '/home/u/games/FrogPost/cover.png', name: 'Cover', file: 'cover.png', kind: 'cover', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/sprites/bird.png', name: 'Robin', file: 'bird.png', kind: 'sprite', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/backgrounds/sky.png', name: 'Open Sky', file: 'sky.png', kind: 'background', modifiedAt: 5 }] }
  }
  const build14pa = await mount(page)
  await settle(100)
  check('the newest reply ends with its suggestions as chips', () => {
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-next-steps button')].map(node => node.textContent), ['Flap while idle', 'Fly faster'])
  })
  await click('Fly faster', build14pa.node.querySelector('.cs-b-next-steps'))
  await settle()
  check('a suggestion fills the message box and is not sent', () => {
    assert.equal(build14pa.node.querySelector('textarea[aria-label="Message Hermes"]').value, 'Fly faster')
  })
  const box14 = build14pa.node.querySelector('textarea[aria-label="Message Hermes"]')
  await typeInto(box14, 'make @')
  await settle(50)
  check('typing @ lists the game\u2019s pictures', () => {
    assert.deepEqual(gamePictures.slice(-1), ['fff666fff666'])
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Cover', 'Robin', 'Open Sky'])
  })
  await typeInto(box14, 'make @rob')
  await settle(20)
  check('what follows @ filters the list', () => {
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Robin'])
  })
  await key('keydown', 'Enter', box14)
  await settle()
  check('Enter picks it: the @word leaves the text and the picture is attached as a mention', () => {
    assert.ok(!build14pa.node.querySelector('.cs-b-mention'))
    assert.equal(box14.value, 'make ')
    assert.match(build14pa.node.querySelector('.cs-b-comp .cs-b-chip.mention').textContent, /@Robin/)
  })
  await typeInto(box14, 'make it chubbier')
  await click('Send', build14pa.node.querySelector('.cs-b-comp'))
  await settle()
  check('the message names the file for the agent and shows the mention in the bubble', () => {
    assert.match(submits.at(-1).text, /^About \/home\/u\/games\/FrogPost\/assets\/sprites\/bird\.png:\nmake it chubbier$/)
    assert.match([...build14pa.node.querySelectorAll('.cs-b-user')].at(-1).textContent, /@Robin/)
  })
  delete scenario.byMethod['plugin.hermretro.assets']
  await build14pa.close()
  scenario.byMethod['session.resume'] = resume14b
  lib14[0] = { ...lib14[0], session: lib14Session }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  // The game plays inside the conversation, only while the agent is not working.
  lib14[0] = { ...lib14[0], web: { sha256: 'w1', builtAt: 2100 } } // made by build #1 (it ran from 2000 s)
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const playerBefore = scenario.player
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/fff666fff666/index.html', romSha256: 'w1', title: 'Frog Post', ...SKINS })
  const tabsBefore = scenario.workspaces.length
  const build14p = await mount(page)
  await settle(100)
  const inlineFrame = () => build14p.node.querySelector('.cs-ip iframe')
  const framePlay = () => build14p.node.querySelector('.cs-b-pc-go')
  check('the newest build rests in a game frame under its line, with Play build #1; nothing plays until asked', () => {
    assert.match(framePlay()?.textContent ?? '', /Play build #1/); assert.ok(!inlineFrame())
    assert.ok(!build14p.node.querySelector('.cs-b-bc .cs-b-pc'), 'under the build line, not in it')
  })
  await act(async () => { framePlay().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('Play opens the real player right in the conversation', () => {
    assert.match(inlineFrame()?.getAttribute('src') ?? '', /tok\/fff666fff666\/index\.html/)
    assert.ok(build14p.node.querySelector('.cs-b-turn .cs-ip') && !build14p.node.querySelector('.cs-b-bc .cs-ip'), 'it plays under the build line'); assert.ok(!framePlay())
  })
  await typeInto(build14p.node.querySelector('textarea[aria-label="Message Hermes"]'), 'make it rain')
  await click('Send', build14p.node.querySelector('.cs-b-comp'))
  await settle()
  check('while the agent works the game rests as a card that says when it is back', () => {
    assert.ok(!inlineFrame())
    assert.match(build14p.node.querySelector('.cs-b-bc').textContent, /Playable again when HermRetro finishes/, [...build14p.node.querySelectorAll('.cs-b-turn')].map(node => `[${node.dataset.turn}] ${node.textContent.slice(0, 120)}`).join(' || '))
  })
  const runtime = 'rt-of-st-old'
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued' } }
  await typeInto(build14p.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and make it snow after')
  await click('Send', build14p.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  check('a message Hermes queues while it works waits under the conversation, marked queued', () => {
    const queued = build14p.node.querySelector('.cs-b-user.queued')
    assert.match(queued?.textContent ?? '', /Queued · HermRetro reads this when it finishes.*and make it snow after/)
    assert.equal([...build14p.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'make it rain')
  })
  await act(async () => { emit({ type: 'tool.start', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {} } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {}, result: { result: 'Completed.' } } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p1', name: 'chromatic_present_game', args: {},
    result: { ok: true, studio: { gameId: 'fff666fff666', title: 'Frog Post', note: 'Try the rain', presentedAt: 99 } } } }) })
  await settle()
  check('presenting from a Build conversation opens no tab beside the chat, and the game waits for the turn to end', () => {
    assert.equal(scenario.workspaces.length, tabsBefore); assert.ok(!inlineFrame())
    assert.ok(!build14p.node.querySelector('.cs-b-pc'), 'no game frame while the agent works')
    assert.match(build14p.node.querySelector('.cs-b-bc').textContent, /Earlier build/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Done.' } }) })
  await settle()
  check('when the turn ends the newest build opens in the newest reply, with the agent\'s note; the older one says it is older', () => {
    assert.ok(inlineFrame()); assert.match(build14p.node.querySelector('.cs-ip').textContent, /Try the rain/)
    const turnsNow = [...build14p.node.querySelectorAll('.cs-b-turn')]
    assert.ok(turnsNow.at(-1).querySelector('.cs-ip'), turnsNow.map(node => node.textContent.slice(0, 60)).join(' | '))
    assert.match(turnsNow.at(-1).querySelector('.cs-b-bc-head').textContent, /#2/); assert.match(build14p.node.textContent, /Earlier build/)
  })
  await act(async () => { emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'Q' } }) })
  await settle()
  check('when its turn starts the queued message joins the conversation as the newest one', () => {
    assert.ok(!build14p.node.querySelector('.cs-b-user.queued'))
    assert.equal([...build14p.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'and make it snow after')
    assert.ok(!inlineFrame(), 'the game rests while the agent works again')
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Snowing.' } }) })
  await settle()
  check('a game the user had open comes back when the agent is done', () => { assert.ok(inlineFrame()) })
  await act(async () => { build14p.node.querySelector('.cs-ip button[aria-label="Close the game"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('closing the game puts the frame and its Play back', () => { assert.ok(!inlineFrame()); assert.ok(framePlay()) })
  await build14p.close()
  // The inline player itself: one bar, whole-number sizes, and the play-test panel from the build report.
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b1', 'chromatic_rom_build'), callOf('r1', 'chromatic_build_report', report14)] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 2010 },
    { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report: report14 }), timestamp: 2011 },
    { role: 'assistant', content: 'Try flying around.', timestamp: 2012 }] })
  lib14[0] = { ...lib14[0], session: { storedId: 'st-play' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const build14ip = await mount(page)
  await settle(100)
  const ipPlay = build14ip.node.querySelector('.cs-b-pc-go')
  check('the reported build offers Play in its game frame', () => assert.ok(ipPlay))
  await act(async () => { ipPlay.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  const ip = () => build14ip.node.querySelector('.cs-ip')
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
  await act(async () => { build14ip.node.querySelector('textarea[aria-label="Message Hermes"]').dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  await keyOn(build14ip.node.querySelector('textarea[aria-label="Message Hermes"]'), 'keydown', 'ArrowDown')
  check('clicking into the message box lets go of a held key, and typing there never reaches the game', () => {
    assert.deepEqual(sentKeys, ['ArrowUp:down', 'ArrowUp:up'])
  })
  await act(async () => { ip().querySelector('.cs-ip-bar button[aria-label="Close the game"]').click() })
  await build14ip.close()
  delete scenario.storage.inlinePlayer
  scenario.byMethod['session.resume'] = resume14b
  scenario.player = playerBefore
  lib14[0] = { ...lib14[0], web: null }
  // The conversation was removed from Hermes: say so, and replace it on the next message.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-gone' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => { if (params.session_id === 'st-gone') throw Object.assign(new Error('session not found'), { code: 4007 }); return plainResume(params) }
  const build14c = await mount(page)
  await settle()
  check('a game whose conversation was removed says so and offers a new one', () => {
    assert.match(build14c.node.textContent, /conversation was removed from Hermes/)
    assert.ok(button('Start a new conversation'))
  })
  await click('Start a new conversation', build14c.node)
  await typeInto(build14c.node.querySelector('textarea[aria-label="Message Hermes"]'), 'start again')
  await click('Send', build14c.node.querySelector('.cs-b-comp'))
  await settle()
  check('the next message makes a new conversation and replaces the removed one', () => {
    assert.deepEqual(buildCalls.at(-1), { action: 'bind', game: 'fff666fff666', stored: `st-new-${created}`, replace: 'st-gone' })
    assert.equal(submits.at(-1).text, 'start again')
  })
  await build14c.close()
  // A turn Hermes lost when it restarted pauses the conversation: the page says so, and Continue drops it.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-lost' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  let lostRows = [{ admission_id: 'adm-lost', status: 'unknown', text: 'make a bird', execution_generation: 1 }, { admission_id: 'adm-q', status: 'queued', text: 'continue' }]
  let lostRunning = false
  const resolved = []
  scenario.byMethod['session.resume'] = params => ({ ...plainResume(params), running: lostRunning, pending: lostRows })
  scenario.byMethod['prompt.resolve_unknown'] = params => { resolved.push(params); lostRows = lostRows.filter(row => row.admission_id !== params.admission_id); return { status: 'terminal', outcome: 'interrupted' } }
  const build14l = await mount(page)
  await settle()
  check('a conversation paused on a lost turn says so, with the message that waits behind it', () => {
    assert.match(build14l.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /HermRetro stopped partway through.*Continue to send your waiting message/)
    assert.match(build14l.node.querySelector('.cs-b-user.queued')?.textContent ?? '', /Waiting · sent when you continue.*continue/)
  })
  const submitsBefore = submits.length
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued' } }
  await typeInto(build14l.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and add clouds')
  await click('Send', build14l.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  check('a message sent while paused waits too, and the page does not claim to be working', () => {
    assert.deepEqual([...build14l.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['continue', 'and add clouds'])
    assert.ok(!build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  // While hermretro updates, Continue (which would release the waiting messages) starts nothing.
  scenario.status = answered({ ...scenario.status.data, plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
  scenario['plugin-update'] = answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: true, update_target: 'abc' } })
  scenario['update-busy'] = answered([])
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  let finishUpdate
  scenario.byMethod['plugins.manage'] = params => (params.action === 'update' ? new Promise(resolve => { finishUpdate = resolve }) : { ok: true })
  await build14l.rerender()
  await click('Update ready', build14l.node); await click('Update now', build14l.node); await settle()
  const lostContinue = () => [...build14l.node.querySelector('.cs-b-card.warn').querySelectorAll('button')].find(node => node.textContent === 'Continue')
  const submitsUpdating = submits.length
  check('while hermretro updates, Continue is disabled', () => { assert.equal(lostContinue().disabled, true) })
  lostContinue().click(); await settle()
  check('and pressing it releases nothing: no lost turn dropped, no message sent', () => {
    assert.deepEqual(resolved, []); assert.equal(submits.length, submitsUpdating)
  })
  await act(async () => { finishUpdate({ ok: true, unchanged: true }) }); await settle()
  // Continue pressed first; an update starts while its session.resume is still on the way: when that answer
  // arrives, nothing is released.
  const normalResume = scenario.byMethod['session.resume']
  let releaseResume = null
  scenario.byMethod['session.resume'] = params => (params.omit_messages && !releaseResume
    ? new Promise(resolve => { releaseResume = () => resolve(normalResume(params)) })
    : normalResume(params))
  await click('Continue', build14l.node.querySelector('.cs-b-card.warn')); await settle()
  await click('Update ready', build14l.node); await click('Update now', build14l.node); await settle()
  check('the resume is still on the way when the update starts', () => { assert.ok(releaseResume, 'session.resume is pending') })
  await act(async () => { releaseResume() }); await settle()
  check('a Continue pressed before an update releases nothing once the update has started', () => {
    assert.deepEqual(resolved, []); assert.equal(submits.length, submitsUpdating)
    assert.ok(build14l.node.querySelector('.cs-b-card.warn'), 'the conversation stays paused')
  })
  await act(async () => { finishUpdate({ ok: true, unchanged: true }) }); await settle()
  scenario.byMethod['session.resume'] = normalResume
  scenario['plugin-update'] = undefined
  await build14l.rerender()
  await click('Continue', build14l.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('Continue drops the lost turn (not run again) and sends nothing new when messages wait', () => {
    assert.deepEqual(resolved, [{ session_id: 'rt-of-st-lost', admission_id: 'adm-lost' }])
    assert.equal(submits.length, submitsBefore + 1)
    assert.ok(!build14l.node.querySelector('.cs-b-card.warn'))
  })
  lostRunning = true // polling can land between any two of these events on a loaded machine
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L1' } }) })
  await settle()
  check('then the waiting messages run in order', () => {
    assert.equal([...build14l.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'continue')
    assert.deepEqual([...build14l.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['and add clouds'])
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-lost', payload: { text: 'Done.' } }) })
  // Lost again with nothing waiting: Continue asks HermRetro to pick up where it stopped.
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L2' } }) })
  await settle()
  check('while a turn runs the message box offers Stop', () => { assert.ok(build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]')) })
  lostRunning = false
  lostRows = [{ admission_id: 'adm-lost-2', status: 'unknown', text: 'and add clouds', execution_generation: 3 }]
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-lost', payload: { pending: lostRows, running: false } }) })
  await settle()
  check('a turn lost while the page watched stops the working state and shows the card', () => {
    assert.match(build14l.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /pick up where it stopped/)
    assert.ok(!build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  await click('Continue', build14l.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('with nothing waiting, Continue drops the lost turn and asks to continue', () => {
    assert.deepEqual(resolved.at(-1), { session_id: 'rt-of-st-lost', admission_id: 'adm-lost-2' })
    assert.match(submits.at(-1).text, /cut off when Hermes restarted\. Continue where you left off/)
    assert.equal([...build14l.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'Continue')
  })
  await build14l.close()
  scenario.byMethod['session.resume'] = plainResume
  // Model and effort: one button in the message box opens providers, models and effort together.
  scenario.models = answered({ model: 'claude-opus-5-5[1m]', provider: 'claude-sub', providers: [
    { slug: 'claude-sub', name: 'Claude Subscription', authenticated: true, total_models: 3, models: ['claude-opus-5-5[1m]', 'claude-sonnet-5-5[1m]', 'claude-haiku-4-5-20251001'],
      capabilities: { 'claude-opus-5-5[1m]': { reasoning: true }, 'claude-sonnet-5-5[1m]': { reasoning: true }, 'claude-haiku-4-5-20251001': { reasoning: true } } },
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, total_models: 2, models: ['gpt-6.1-sol', 'gpt-6-sol-900k'],
      capabilities: { 'gpt-6.1-sol': { fast: true, reasoning: true }, 'gpt-6-sol-900k': { fast: true, reasoning: true } } },
    { slug: 'off', name: 'Signed Out Co', authenticated: false, models: ['x-1'] }] })
  scenario.sets = []
  scenario.byMethod['config.set'] = params => { scenario.sets.push(params); return { key: params.key, value: params.value } }
  lib14[0] = { ...lib14[0], session: { storedId: 'st-old' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const build14m = await mount(page)
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-old', payload: { model: 'claude-opus-5-5[1m]', provider: 'claude-sub', reasoning_effort: 'high' } }) })
  await settle()
  // Another game asks a question while this one is open: the title says so.
  await act(async () => { emit({ type: 'clarify.request', session_id: 'rt-new-1', payload: { request_id: 'other-q', question: 'Which lamp?' } }) })
  await settle()
  check('a question in another game shows as "1 needs you" beside the title', () => {
    assert.equal(build14m.node.querySelector('.cs-b-needs')?.textContent, '1 needs you')
    assert.match(build14m.node.querySelector('.cs-b-needs').getAttribute('title'), /Lamplight/)
  })
  await act(async () => { emit({ type: 'clarify.settled', session_id: 'rt-new-1', payload: { request_id: 'other-q' } }) })
  await settle()
  check('once it is answered the badge goes away', () => { assert.ok(!build14m.node.querySelector('.cs-b-needs')) })
  const chip = () => build14m.node.querySelector('.cs-b-mp-chip')
  const pop = () => build14m.node.querySelector('.cs-b-mp-pop')
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
  await typeInto(build14m.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add a boss')
  await click('Send', build14m.node.querySelector('.cs-b-comp'))
  await settle()
  const before = scenario.sets.length
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Max', pop())
  await settle()
  await key('keydown', 'Escape')
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
  await typeInto(build14m.node.querySelector('textarea[aria-label="Message Hermes"]'), 'now a second boss')
  await click('Send', build14m.node.querySelector('.cs-b-comp'))
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Second boss.' } }) })
  await settle()
  check('a reply names its model when it changed since the message before', () => {
    const labels = [...build14m.node.querySelectorAll('.cs-b-who')].map(node => node.textContent)
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
  await build14m.close()
  // New Game starts on the picked model, and remembers it for the next one.
  scenario.storage.buildSelected = 'new'
  delete scenario.byMethod['config.set']
  const creates = []
  const plainCreate = scenario.byMethod['session.create']
  scenario.byMethod['session.create'] = params => { creates.push(params); return { ...plainCreate(params), info: params } }
  const build14n = await mount(page)
  await settle()
  await act(async () => { build14n.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { build14n.node.querySelectorAll('.cs-b-mp-row')[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { build14n.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Low', build14n.node.querySelector('.cs-b-mp-pop'))
  await typeInto(build14n.node.querySelector('textarea[aria-label="Your game idea"]'), 'a frog racing game')
  await act(async () => { build14n.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('New Game makes its conversation on the picked model and effort, and remembers them', () => {
    assert.equal(creates.at(-1).model, 'claude-sonnet-5-5[1m]'); assert.equal(creates.at(-1).provider, 'claude-sub'); assert.equal(creates.at(-1).reasoning_effort, 'low')
    assert.deepEqual(scenario.storage.buildModel, { model: 'claude-sonnet-5-5[1m]', provider: 'claude-sub', effort: 'low' })
  })
  scenario.byMethod['session.create'] = plainCreate
  await build14n.close()
  // The game card on the Games page: cover art, tagline and genres; a game without one offers to make it.
  scenario.games = answered({ games: [
    { ...lib14[0], session: null, card: null, cover: false },
    { id: 'ccc333ccc333', title: 'Comet', displayTitle: 'Comet Drift', projectRoot: '/home/u/games/Comet', kind: 'gbstudio', state: 'ready',
      rom: { sha256: 'r1' }, webExport: true, thumb: 'data:image/png;base64,COVER', cover: true, chat: null, error: null, session: null,
      card: { title: 'Comet Drift', tagline: 'Dodge comets in a tiny ship.', description: 'Fly through three comet belts.', genres: ['Arcade', 'Action'],
        tags: [], controls: {}, complete: true, missing: [], hasCover: true } }], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.page = 'games'
  const shelf = await mount(page)
  await settle()
  const cards = () => [...shelf.node.querySelectorAll('.cs-gcard')]
  check('a game with a card shows its cover, display title, tagline and genres, and no Make cover art', () => {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    assert.equal(comet.querySelector('.cs-cart img').getAttribute('alt'), 'Comet Drift cover art')
    assert.equal(comet.querySelector('.cs-gtag').textContent, 'Dodge comets in a tiny ship.')
    assert.match(comet.querySelector('.cs-gtag').getAttribute('title'), /Arcade · Action/)
    assert.ok(!comet.querySelector('.nocover'))
  })
  {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    await act(async () => { comet.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    check('a game with a complete card has no Make cover art in its menu', () => { assert.ok(!/Make cover art/.test(comet.querySelector('.cs-gmenu').textContent)) })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
  }
  const frog = () => cards().find(node => /Frog Post/.test(node.textContent))
  await act(async () => { frog().querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('a game without a card offers Make cover art in its menu', () => { assert.ok(/Make cover art/.test(frog().querySelector('.cs-gmenu').textContent)) })
  await click('Make cover art', frog().querySelector('.cs-gmenu'))
  await settle()
  check('Make cover art opens that game on Build with the request in its message box, not sent', () => {
    assert.equal(shelf.node.querySelector('.cs-b-sw h2')?.textContent, 'Frog Post')
    assert.match(shelf.node.querySelector('textarea[aria-label="Message Hermes"]').value, /160x144 pixel-art cover.*chromatic_game_info/)
  })
  await shelf.close()
  scenario.storage.page = 'build'
})
