// The emulator beside the chat, which opens only when the agent presents a game (chromatic_present_game), and the
// presentations fallback (starting state: games-fixture.mjs; Play on the shelf loads Comet Drift first).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, dom, emit, host, plugin, scenario, ctx, page, click, tab, settle, button, key, mount, check, answered, complete } = helpers
  const { games, now2, studio } = await gamesStudio(helpers)
  scenario.status = answered({ ...complete, hardware_enabled: true })
  await studio.rerender()
  await tab('Games')
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-one', title: 'Comet Drift' })
  await click('Play')

  // 13. The emulator beside the chat opens only when the agent presents the game (chromatic_present_game).
  const pageFrame = () => studio.node.querySelector('.cs-rp-stage iframe')
  const library13 = [
    { ...games[0], rom: { ...games[0].rom, sha256: 'native-one' }, web: { sha256: 'sha-one', builtAt: now2 - 60 } },
    games[1],
    { id: 'ccc333ccc333', title: 'Star Farm', projectRoot: '/home/u/ChromaticGames/StarFarm', kind: 'gbstudio', state: 'ready',
      rom: { path: '/x.gbc', sha256: 'native-star', size: 1, builtAt: now2 - 30 }, web: { sha256: 'web-star', builtAt: now2 - 30 },
      webExport: true, thumb: null, chat: { sessionId: 'stored-star', title: 'Star Farm' }, error: null }
  ]
  scenario.byMethod['plugin.hermretro.games'] = () => ({ ok: true, games: library13, device: { hardwareEnabled: true, skipped: false } })
  // The backend answers with its own clock (here ahead of this one) and only presentations after `since`.
  const backendNow = Date.now() / 1000 + 50
  let shownByBackend = []
  scenario.byMethod['plugin.hermretro.presentations'] = params =>
    ({ ok: true, now: backendNow, presentations: shownByBackend.filter(item => params?.since == null || item.t > params.since) })
  scenario.games = answered({ games: library13, device: { hardwareEnabled: true, skipped: false } })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-one', title: 'Comet Drift' })
  await studio.rerender()
  check('the Emulator page keeps Open beside the chat under the player, with no auto-open setting', () => {
    const row = studio.node.querySelector('.cs-rp-foot')
    assert.ok(row, 'row shown'); assert.ok(!row.querySelector('input[type=checkbox]'), 'no setting')
    assert.ok(!/after a build/.test(row.textContent)); assert.match(row.textContent, /when it is ready for you to try/)
    assert.ok([...row.querySelectorAll('button')].some(node => node.textContent.includes('Open beside the chat')))
    assert.ok(!/beside the chat/.test(studio.node.querySelector('.cs-rp-bar').textContent))
    assert.ok(pageFrame(), 'the page runs the game')
  })
  const finish = async (sessionId, name, result, extra = {}) => {
    await act(async () => { emit({ type: 'tool.complete', session_id: sessionId, payload: { tool_id: 't' + Math.random(), name, args: {}, result, ...extra } }) })
    await settle()
  }
  const built = { structuredContent: { success: true }, player: { ready: true }, nextStep: 'call chromatic_present_game' }
  const presented = (gameId, title, note = null, presentedAt = Math.random()) =>
    ({ ok: true, studio: { gameId, playerUrl: `http://127.0.0.1:4567/tok/${gameId}/index.html`, title, note, presentedAt }, message: 'Shown to the user beside the chat.' })
  await finish('rt-comet', 'chromatic_rom_build', { isError: true, error: 'compile failed' })
  await finish('rt-comet', 'chromatic_rom_build', built)
  await finish('rt-comet', 'chromatic_web_preview', { structuredContent: { success: true, url: 'http://e/' } })
  // A build result from an older backend that still names the Studio player opens nothing either.
  await finish('rt-comet', 'chromatic_rom_build', { ...built, studioGameId: 'aaa111aaa111', studioPlayerUrl: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html' })
  await finish('rt-comet', 'chromatic_present_game', { ok: false, code: 'BUILD_FIRST', error: 'Run chromatic_rom_build first.' })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift'), { error: 'tool failed' })
  await finish('rt-comet', 'chromatic_emulator_step', presented('aaa111aaa111', 'Comet Drift'))
  check('build completion opens NOTHING (nor failed presents or other tools)', () => { assert.equal(scenario.workspaces.length, 0); assert.ok(pageFrame()) })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Try the double jump on the second ledge.', 101))
  const tabs = () => scenario.workspaces.filter(tab => !tab.closed)
  check('chromatic_present_game opens one tab docked right of the chat, titled after the game', () => {
    assert.equal(scenario.workspaces.length, 1)
    const [tab] = scenario.workspaces
    assert.equal(tab.id, 'hermretro.emulator.aaa111aaa111'); assert.equal(tab.options.title, 'Emulator · Comet Drift')
    assert.deepEqual(tab.options.dock, { pane: 'workspace', pos: 'right' }); assert.equal(typeof tab.options.render, 'function')
  })
  const side = await mount({ render: scenario.workspaces[0].options.render })
  const sideFrame = () => side.node.querySelector('.cs-rp-stage iframe')
  const sideReload = () => scenario.queries.filter(query => query.key === 'player' && query.queryKey?.[2] === 'side').at(-1)?.queryKey?.[4]
  await studio.rerender()
  check('one live player: the presented tab runs the game, the page says where it is', () => {
    assert.ok(sideFrame(), 'the tab runs the player'); assert.equal(sideFrame().getAttribute('src'), 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html')
    assert.ok(!pageFrame(), 'the page dropped its frame'); assert.match(studio.node.textContent, /Playing beside the chat/)
    assert.ok([...studio.node.querySelectorAll('button')].some(node => node.textContent.includes('Bring it here')))
    assert.match(side.node.textContent, /Ask Hermes/); assert.match(side.node.textContent, /Captures/); assert.match(side.node.textContent, /Keyboard/)
    const install = [...side.node.querySelectorAll('.cs-rp-bar button')].find(node => node.textContent.includes('Install'))
    assert.ok(install, 'the real Install contribution renders in the tab\u2019s bar'); assert.ok(!install.disabled, 'with hardware on and the game built')
  })
  check('the note appears as a slim line above the player in the tab', () => {
    const note = side.node.querySelector('.cs-side-note')
    assert.ok(note, 'note shown'); assert.match(note.textContent, /Try the double jump on the second ledge\./)
    const order = [...side.node.querySelector('.cs-side').children]
    assert.ok(order.indexOf(note) < order.indexOf(side.node.querySelector('.cs-rp-stage')), 'above the player')
  })
  check("the tab compares the web export's own ROM: a fresh build is not reported as rebuilt", () => { assert.ok(!side.node.textContent.includes('Hermes rebuilt')) })
  await click('Bring it here', studio.node)
  check('Bring it here moves the game back to the page and the tab shows a placeholder', () => {
    assert.ok(pageFrame()); assert.ok(!sideFrame()); assert.match(side.node.textContent, /Playing in hermretro/)
  })
  await click('Bring it here', side.node)
  check('and back beside the chat again', () => { assert.ok(sideFrame()); assert.ok(!pageFrame()) })
  await tab('Games'); await tab('Emulator')
  check('visiting the Emulator page again does not take (and restart) the game playing beside the chat', () => {
    assert.ok(sideFrame()); assert.ok(!pageFrame()); assert.match(studio.node.textContent, /Playing beside the chat/)
  })
  const sidePosted = []
  sideFrame().contentWindow.postMessage = message => sidePosted.push(message)
  await key('keydown', 'ArrowRight', dom.window.document.body)
  check('beside the chat, keys typed in the chat do not reach the game', () => { assert.equal(sidePosted.length, 0) })
  await act(async () => { side.node.querySelector('.cs-rp-bar').dispatchEvent(new dom.window.Event('pointerdown', { bubbles: true })) })
  await key('keydown', 'ArrowRight', dom.window.document.body)
  check('after a click in the tab, they do', () => { assert.deepEqual(sidePosted.filter(m => m.type === 'key').map(m => m.key), ['ArrowRight']) })
  await act(async () => { side.node.querySelector('.cs-side-note-x').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('the note can be dismissed', () => { assert.ok(!side.node.querySelector('.cs-side-note')) })
  const reloadBefore = sideReload()
  const frameBefore = sideFrame()
  library13[0] = { ...library13[0], web: { sha256: 'sha-two', builtAt: now2 } }
  scenario.games = answered({ games: library13, device: { hardwareEnabled: true, skipped: false } })
  await finish('rt-comet', 'chromatic_rom_build', built)
  await side.rerender()
  check('a rebuild without a presentation opens nothing and shows the rebuilt banner in the open tab, without reloading', () => {
    assert.equal(scenario.workspaces.length, 1); assert.equal(scenario.workspaces[0].fronted ?? 0, 0)
    assert.match(side.node.textContent, /Hermes rebuilt Comet Drift/); assert.match(side.node.textContent, /Load the new build/)
    assert.equal(sideReload(), reloadBefore); assert.ok(sideFrame() === frameBefore, 'the player frame is retained')
  })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-two', title: 'Comet Drift' })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Now the ledge is lower: try it again.', 102))
  await side.rerender()
  check('presenting again fronts the same tab and loads the newest build directly, with the new note', () => {
    assert.equal(tabs().length, 1); assert.equal(scenario.workspaces.length, 1); assert.equal(scenario.workspaces[0].fronted, 1)
    assert.equal(sideReload(), reloadBefore + 1, 'player asked again'); assert.ok(sideFrame() !== frameBefore, 'new frame')
    assert.ok(!side.node.textContent.includes('Hermes rebuilt'), 'no banner: it is the newest build')
    assert.match(side.node.querySelector('.cs-side-note').textContent, /Now the ledge is lower/)
  })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Now the ledge is lower: try it again.', 102))
  check('the same presentation heard twice is acted on once', () => { assert.equal(scenario.workspaces[0].fronted, 1); assert.equal(sideReload(), reloadBefore + 1) })
  await click('Open beside the chat', studio.node)
  check("the user's own Open beside the chat on the Emulator page still works", () => {
    assert.equal(tabs().length, 1); assert.equal(scenario.workspaces[0].fronted, 2)
  })
  await act(async () => { scenario.workspaces[0].close() })
  await side.close()
  await studio.rerender()
  check('closing the tab frees the game: the Emulator page takes it back', () => { assert.ok(pageFrame()); assert.equal(tabs().length, 0) })
  await finish('rt-comet', 'chromatic_rom_build', built)
  check('later builds never reopen a closed tab', () => { assert.equal(scenario.workspaces.length, 1) })
  await finish('stored-star', 'chromatic_present_game', presented('ccc333ccc333', 'Star Farm', null, backendNow + 0.25))
  check('presenting another game opens its own tab', () => {
    assert.equal(scenario.workspaces.length, 2); assert.equal(scenario.workspaces[1].options.title, 'Emulator · Star Farm')
  })
  const star = await mount({ render: scenario.workspaces[1].options.render })
  check('no note → no note line', () => { assert.ok(!star.node.querySelector('.cs-side-note')) })
  await act(async () => { scenario.workspaces[1].close() })
  await star.close()
  const openWorkspace = host.openWorkspace
  delete host.openWorkspace
  library13.push({ ...library13[2], id: 'ddd444ddd444', title: 'Moon Garden', chat: { sessionId: 'stored-moon' } })
  await finish('rt-moon', 'chromatic_present_game', presented('ddd444ddd444', 'Moon Garden', 'Hi', 104))
  await studio.rerender()
  check('on a desktop without openWorkspace nothing breaks: no tab, the page keeps its player, no Open beside the chat', () => {
    assert.equal(scenario.workspaces.length, 2); assert.ok(pageFrame()); assert.ok(!button('Open beside the chat'))
  })
  host.openWorkspace = openWorkspace
  // A gateway with tool progress off sends no tool.complete: turn ends ask `presentations` instead.
  plugin.register({ ...ctx, registerMany: () => {} })
  const opened = scenario.workspaces.length
  const turnEnd = async sessionId => { await act(async () => { emit({ type: 'message.complete', session_id: sessionId, payload: {} }) }); await settle() }
  await turnEnd('rt-x')
  check('a turn end with no new presentation opens nothing, and asks with a since timestamp', () => {
    assert.equal(scenario.workspaces.length, opened)
    assert.equal(typeof scenario.paramsByMethod['plugin.hermretro.presentations']?.since, 'number')
  })
  library13.push({ ...library13[2], id: 'eee555eee555', title: 'Night Owl', chat: { sessionId: 'stored-owl' }, web: { sha256: 'owl-1', builtAt: now2 + 5 } })
  library13[0] = { ...library13[0], web: { sha256: 'sha-three', builtAt: now2 + 6 } }
  await turnEnd('rt-owl')
  check('a turn end after a build alone (no presentation) opens nothing', () => { assert.equal(scenario.workspaces.length, opened) })
  shownByBackend = [{ gameId: 'eee555eee555', title: 'Night Owl', t: backendNow + 0.5, note: 'Find the owl', sessionId: 'rt-owl' }]
  await turnEnd('rt-owl')
  check('presentations fallback: a turn end that finds a presentation opens it beside the chat', () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.equal(scenario.workspaces.at(-1).options.title, 'Emulator · Night Owl')
    assert.equal(scenario.paramsByMethod['plugin.hermretro.presentations'].since, backendNow - 1, 'since follows the backend clock')
  })
  await turnEnd('rt-owl')
  check('the fallback never repeats a presentation it already acted on', () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.equal(scenario.workspaces.at(-1).fronted ?? 0, 0)
  })
  shownByBackend = [{ gameId: 'ccc333ccc333', title: 'Star Farm', t: backendNow + 0.25, note: null }]
  await turnEnd('rt-star')
  check('nor one first heard through tool.complete', () => { assert.equal(scenario.workspaces.length, opened + 1) })
  shownByBackend = [{ gameId: 'bbb222bbb222', title: 'Robo Run', t: backendNow + 0.75, note: null, sessionId: 'rt-other', thisProfile: false }]
  await turnEnd('rt-owl')
  check('a presentation made in another Hermes profile is not acted on here', () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.ok(!scenario.workspaces.some(tab => /Robo Run/.test(tab.options.title)))
  })
  // After a restart the page no longer knows which chats are Build conversations; the backend still does.
  shownByBackend = [{ gameId: 'ddd444ddd444', title: 'Ace Arena', t: backendNow + 0.8, note: null, sessionId: 'rt-ace', thisProfile: true, buildConversation: true }]
  await turnEnd('rt-ace')
  await finish('rt-ace2', 'chromatic_present_game', { ok: true, studio: { gameId: 'ddd444ddd444', title: 'Ace Arena', note: null, presentedAt: 202, buildConversation: true } })
  check("a game's own Build conversation presenting it opens nothing beside the chat (the Build page plays it)", () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.ok(!scenario.workspaces.some(tab => /Ace Arena/.test(tab.options.title)))
  })
  await act(async () => { scenario.workspaces.at(-1).close() })
  delete scenario.byMethod['plugin.hermretro.presentations']
  await turnEnd('rt-old')
  check('an older backend without the presentations RPC breaks nothing', () => { assert.equal(scenario.workspaces.length, opened + 1) })
  await studio.close()
})
