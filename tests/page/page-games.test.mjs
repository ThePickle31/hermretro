// Home, Games, Prompts and the Emulator fed by the games / player RPCs, and the emulator beside the chat that
// opens only when the agent presents a game (chromatic_present_game).
// Run alone: node tests/page/page-games.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, emit, host, plugin, scenario, ctx, page, text, heading, HOME, click, nav, tab, currentTab, settle, button, typeInto, key, mount, check, answered, notLoaded, doctor, installAnswer, complete }) => {
  // Where the studio-profile scenarios leave the app: the active profile has the plugin but is not the studio,
  // a hermretro route is known, and the profile RPCs still answer (Refresh below forgets the route).
  scenario.ambient = { ...complete, profile: { name: 'default', is_studio: false,
    create: { name: 'hermretro', description: 'hermretro', no_skills: true, share_auth: true, no_alias: true },
    studio: { name: 'hermretro', exists: true, installed: false, ours: false } } }
  scenario.routes = [{ profile: 'default', connectionId: 'local' }, { profile: 'hermretro', targetProfile: 'hermretro', connectionId: 'local' }]
  scenario.byProfile = {}
  scenario.byMethod['profiles.create'] = { ok: true, name: 'hermretro' }
  scenario.byMethod['plugin.hermretro.studio_profile'] = { ok: false, code: 'NAME_TAKEN', error: 'A profile named hermretro already exists and was not made by hermretro.' }
  scenario.install = installAnswer({ state: 'idle' })

  // 12. Games, Prompts and the Emulator, fed by the games / player RPCs (docs/dev/STUDIO-PAGES.md).
  scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
  scenario.storage = { setup: { hardwareSkipped: true } }
  const now2 = Math.round(Date.now() / 1000)
  const games = [
    { id: 'aaa111aaa111', title: 'Comet Drift', projectRoot: '/home/u/ChromaticGames/CometDrift', kind: 'gbstudio', state: 'ready',
      rom: { path: '/home/u/ChromaticGames/CometDrift/build/web/rom/game.gbc', sha256: 'sha-one', size: 262144, builtAt: now2 - 120 },
      webExport: true, thumb: 'data:image/png;base64,AAAA', chat: { sessionId: 'stored-comet', title: 'Comet Drift — first level' }, error: null },
    { id: 'bbb222bbb222', title: 'Robo Run', projectRoot: '/home/u/ChromaticGames/RoboRun', kind: 'gbdk', state: 'failed', rom: null,
      webExport: false, thumb: null, chat: null, error: 'background uses 212 tiles (limit 192)' }
  ]
  scenario.games = answered({ games, gamesDir: '/home/u/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
  scenario.player = { isPending: true }
  const studio = await mount(page)
  await click('Refresh') // forget the profile route left over from the cases above
  check('Home continues with the last game from the games RPC', () => {
    assert.equal(heading(), HOME)
    assert.equal(dom.window.document.querySelector('.cs-cont .name').textContent, 'Comet Drift')
    assert.match(text(), /Chat: Comet Drift — first level/)
  })
  await tab('Games')
  check('Games shows each game as the real cartridge with its title screen, state and meta, plus a blank cartridge', () => {
    const cards = [...dom.window.document.querySelectorAll('.cs-gcard')]
    assert.equal(cards.length, 3)
    assert.equal(cards[0].querySelector('.cs-cart .slot img').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.match(cards[0].textContent, /Ready/); assert.doesNotMatch(cards[0].textContent, /GB Studio/)
    assert.match(cards[0].querySelector('.cs-gline').getAttribute('title'), /256 KB/)
    assert.match(cards[0].querySelector('.cs-split .main').textContent, /^Play$/)
    assert.match(cards[1].textContent, /Build failed/); assert.match(cards[1].querySelector('.cs-split .main').textContent, /Fix in chat/)
    assert.match(cards[1].textContent, /212 tiles/)
    assert.equal(cards[0].querySelectorAll('.cs-split > button, .cs-split > span > button').length, 2, 'one split control per card')
    assert.ok(!dom.window.document.querySelector('.cs-dev'), 'no hardware strip above a full shelf')
    assert.match(cards[2].textContent, /Blank cartridge/)
    assert.doesNotMatch(text(), /in your studio|Games showcase/)
  })
  scenario.revealed = null
  await click('Open games folder')
  check('the shelf shows the games folder and opens it', () => {
    assert.match(dom.window.document.querySelector('.cs-gfolder').textContent, /\/home\/u\/\.hermes\/hermretro\/games/)
    assert.equal(scenario.revealed, '/home/u/.hermes/hermretro/games')
  })
  const openGameMenu = async card => {
    await act(async () => { card.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    return card.querySelector('.cs-gmenu')
  }
  const firstCard = () => dom.window.document.querySelectorAll('.cs-gcard')[0]
  check('the split arrow is closed until pressed', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  {
    const menu = await openGameMenu(firstCard())
    check('without hardware tools Install is locked in the menu and the header chip offers to set up the Chromatic', () => {
      const install = [...menu.querySelectorAll('button')].find(node => /Install on Chromatic/.test(node.textContent))
      assert.ok(install.disabled); assert.match(install.textContent, /Needs your Chromatic/)
      assert.match(menu.textContent, /Open its chat/); assert.match(menu.textContent, /Show in folder/)
      assert.match(text(), /Emulator only · Set up my Chromatic/)
    })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
    check('Escape closes the game menu', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  }
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Fix in chat')
  await settle()
  check('Fix in chat puts the build error into a chat, not sent', () => {
    assert.ok(scenario.inserted.some(([, value]) => /212 tiles/.test(value) && /Robo Run/.test(value)))
    assert.ok(!scenario.calls.some(call => /send|submit/i.test(call[0])))
  })
  scenario.status = answered({ ...complete, hardware_enabled: true })
  await studio.rerender()
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Install on Chromatic', await openGameMenu(firstCard()))
  await settle()
  check("Install sends the flash prompt, naming the game, to that game's own chat (the chat's approval gate applies)", () => {
    assert.deepEqual(scenario.calls[0], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /^Flash the built ROM of "Comet Drift" \(\/home\/u\/ChromaticGames\/CometDrift\) to the connected Chromatic cartridge/)
  })
  scenario.games = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the games RPC is reported honestly', () => { assert.match(text(), /cannot list your games yet/) })
  scenario.games = answered({ games: [], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('an empty library offers a new game and the remix', () => { assert.equal(heading(), 'No games yet'); assert.match(text(), /Remix Wrecklight/) })
  // The Emulator never shows an empty page: with nothing of the user's to play it loads the demo cartridge.
  scenario.games = answered({ games: [], demo: { id: 'demo', title: 'Hello Color', kind: 'gbdk', note: 'ModRetro example' }, device: { hardwareEnabled: true, skipped: false } })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/demo/index.html', romSha256: 'sha-demo', title: 'Hello Color', demo: true })
  scenario.byMethod['plugin.hermretro.player'] = params => ({ url: `http://127.0.0.1:4567/tok/${params.id}/index.html` })
  await tab('Emulator')
  check('an empty library still shows the player: the demo cartridge in a sandboxed frame', () => {
    const demoFrame = dom.window.document.querySelector('.cs-rp-stage iframe')
    assert.ok(demoFrame, 'the player frame is shown')
    assert.equal(demoFrame.getAttribute('src'), 'http://127.0.0.1:4567/tok/demo/index.html')
    assert.equal(demoFrame.getAttribute('data-sandbox'), 'allow-scripts allow-downloads')
    assert.ok(!/the player is not available/i.test(text())); assert.ok(!/Nothing to play yet/.test(text()))
  })
  await scenario.fns.player()
  check('the player RPC is asked for the demo id', () => { assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.player'], { id: 'demo' }) })
  check('the bar above the player holds only its controls: no game tabs, demo chip or profile line, and no Install for the demo', () => {
    assert.ok(!dom.window.document.querySelector('.cs-rp-games')); assert.ok(!/Demo cartridge/.test(text())); assert.ok(!button('Make your first game'))
    assert.ok(!dom.window.document.querySelector('.cs-top-profile')); assert.ok(!button('Install')); assert.match(text(), /Ask Hermes/)
  })
  check('every bar button keeps an accessible name when a narrow pane hides its label (.cs-lbl)', () => {
    const bar = dom.window.document.querySelector('.cs-rp-bar')
    for (const name of ['Ask Hermes', 'Captures', 'Full screen']) {
      assert.ok(bar.querySelector(`button[aria-label="${name}"]`), `${name} has an aria-label`)
    }
    assert.ok([...bar.querySelectorAll('.cs-lbl')].some(node => node.textContent === 'Captures'))
    assert.ok(dom.window.document.querySelector('.cs-top button[aria-label="Refresh"] .cs-lbl'), 'Refresh label can hide too')
  })
  scenario.player = notLoaded
  await tab('Prompts')
  await tab('Emulator')
  check('an old backend without the player RPC: a compact notice with the reason and Refresh, above an empty device area', () => {
    const note = dom.window.document.querySelector('.cs-rp-note')
    assert.ok(note, 'notice shown')
    assert.match(note.textContent, /This profile is running an older copy of the hermretro backend\. Reload the plugin \(Capabilities › Plugins, switch it off and on\) and press Refresh\./)
    assert.ok([...note.querySelectorAll('button')].some(node => node.textContent.includes('Refresh')))
    const stage = dom.window.document.querySelector('.cs-rp-stage')
    assert.ok(note.compareDocumentPosition(stage) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING, 'the notice sits above the device area')
    assert.ok(stage.querySelector('.cs-rp-void')); assert.ok(!stage.querySelector('iframe'))
    assert.ok(!/the player is not available/i.test(text()))
  })
  scenario.player = { isError: true, isFetching: false, error: new Error('gateway timed out') }
  await studio.rerender()
  check('any other player failure shows its real reason in the same notice', () => {
    assert.match(dom.window.document.querySelector('.cs-rp-note').textContent, /gateway timed out/)
  })
  delete scenario.byMethod['plugin.hermretro.player']
  scenario.player = { isPending: true }
  await tab('Games')
  scenario.games = answered({ games, gamesDir: '/home/u/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()

  // Prompts: the Reader.
  await click('New game', dom.window.document.querySelector('.cs-shelf'))
  check('the blank cartridge opens the Create a new game prompt', () => {
    assert.equal(currentTab(), 'Prompts'); assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Create a new game')
  })
  check('the Reader lists the prompts grouped Plan / Create / Play / Polish / On your Chromatic', () => {
    const groups = [...dom.window.document.querySelectorAll('.cs-rgrp > span:first-child')].map(node => node.textContent)
    assert.deepEqual(groups, ['Plan', 'Create', 'Play', 'Polish', 'On your Chromatic'])
    assert.equal(dom.window.document.querySelectorAll('.cs-ritem').length, 11)
  })
  const area = () => dom.window.document.querySelector('.cs-rdetail textarea')
  check('{folder}/{name} become inputs; the folder defaults to the plugin games folder', () => {
    assert.equal(dom.window.document.getElementById('cs-f-folder').value, '/home/u/.hermes/hermretro/games')
    assert.equal(dom.window.document.getElementById('cs-f-name').value, 'MoonGarden')
    assert.match(area().value, /new GB Studio project at \/home\/u\/\.hermes\/hermretro\/games\/MoonGarden\. Make a small exploration game/)
  })
  await typeInto(dom.window.document.getElementById('cs-f-name'), 'StarFarm')
  check('editing the name rewrites the prompt', () => {
    assert.match(area().value, /\/home\/u\/\.hermes\/hermretro\/games\/StarFarm\./)
  })
  await typeInto(area(), 'My own words')
  check('the prompt text is editable and can be reset', () => { assert.equal(area().value, 'My own words'); assert.ok(button('Reset text')) })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Start a new chat')
  await settle()
  check('Start a new chat opens a new chat and puts the edited text in its composer', () => {
    assert.deepEqual(scenario.calls[0], ['newChat', null]); assert.deepEqual(scenario.inserted.at(-1), ['new', 'My own words'])
  })
  await click('Reset text')
  check('Reset text restores the prompt', () => { assert.match(area().value, /StarFarm/) })
  scenario.calls.length = 0
  await click('Add to current chat')
  await settle()
  check('Add to current chat goes to the composer the user is in first', () => { assert.deepEqual(scenario.calls[0], ['insert', null]) })
  await key('keydown', 'ArrowDown', dom.window.document.body)
  check('↓ moves to the next prompt', () => { assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Remix an example') })
  await typeInto(dom.window.document.querySelector('.cs-search input'), 'palette')
  check('search filters the list', () => {
    assert.deepEqual([...dom.window.document.querySelectorAll('.cs-ritem')].map(node => node.textContent), ['Update the palette'])
    assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Update the palette')
  })

  // Emulator: Play on the shelf opens ModRetro's player in a sandboxed frame.
  await tab('Games')
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-one', title: 'Comet Drift' })
  await click('Play')
  const frame = () => dom.window.document.querySelector('.cs-rp-stage iframe')
  check('Play switches to the Emulator page and loads the player RPC url in a sandboxed frame', () => {
    assert.equal(currentTab(), 'Emulator')
    assert.equal(frame().getAttribute('src'), 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html')
    assert.equal(frame().getAttribute('data-sandbox'), 'allow-scripts allow-downloads')
    assert.match(text(), /Ask Hermes/); assert.match(text(), /Captures/); assert.match(text(), /Keyboard/)
    assert.ok(!text().includes('Hermes rebuilt'))
  })
  const posted = []
  frame().contentWindow.postMessage = message => posted.push(message)
  await key('keydown', 'ArrowLeft', dom.window.document.body); await key('keyup', 'ArrowLeft', dom.window.document.body)
  await key('keydown', 'q', dom.window.document.body)
  check('game keys typed on the page reach the frame; other keys do not', () => {
    assert.deepEqual(posted.filter(message => message.type === 'key').map(message => [message.key, message.down]), [['ArrowLeft', true], ['ArrowLeft', false]])
  })
  const kept2 = frame()
  await tab('Home')
  check('leaving the Emulator keeps the frame loaded but hidden, and holds the game', () => {
    assert.ok(frame() === kept2, 'the player frame is retained'); assert.ok(dom.window.document.querySelector('.cs-rp-stage.off'))
    assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'hold' })
    assert.ok(nav().querySelector('.live'), 'the Emulator tab shows that a game is loaded')
  })
  await tab('Emulator')
  check('coming back releases it, without reloading the frame', () => {
    assert.ok(frame() === kept2, 'the player frame is retained'); assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'release' })
  })
  scenario.byMethod['plugin.hermretro.capture_image'] = params => ({ path: `/home/u/ChromaticGames/CometDrift/captures/${params.id}.png` })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: frame().contentWindow, data: {
      cs: 'annotate', target: { name: 'Sprite 1; tile 00', role: 'game-sprite', metadata: { oam: 1, tile: 0 } }, note: 'The jump is too low', image: 'data:image/png;base64,AAAA' } }))
  })
  await settle()
  check("an annotation is saved through capture_image and put into the game's chat with the note and screenshot path, not sent", () => {
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.capture_image'], { id: 'aaa111aaa111', png: 'data:image/png;base64,AAAA' })
    assert.deepEqual(scenario.calls.map(call => call[0]).slice(0, 3), ['request', 'openSession', 'insert'])
    assert.deepEqual(scenario.calls[1], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /I marked Sprite 1; tile 00 \(sprite\)/); assert.match(value, /The jump is too low/)
    assert.match(value, /"oam":1/); assert.match(value, /Screenshot: \/home\/u\/ChromaticGames\/CometDrift\/captures\/aaa111aaa111\.png/)
  })
  scenario.byMethod['plugin.hermretro.capture_image'] = () => { throw Object.assign(new Error('unknown method'), { code: -32601 }) }
  scenario.notices.length = 0; scenario.inserted.length = 0
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: frame().contentWindow, data: { cs: 'annotate', target: { name: 'Background' }, note: 'too dark', image: 'data:image/png;base64,AAAA' } }))
  })
  await settle()
  check('without capture_image the note still reaches the chat and the missing screenshot is reported', () => {
    assert.match(scenario.inserted.at(-1)[1], /too dark/); assert.ok(!/Screenshot:/.test(scenario.inserted.at(-1)[1]))
    assert.ok(scenario.notices.some(notice => notice.kind === 'warning' && /cannot save screenshots yet/.test(notice.message)))
  })
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: dom.window, data: { cs: 'annotate', target: { name: 'spoof' } } }))
  })
  await settle()
  check('messages that do not come from the player frame are ignored', () => { assert.ok(!scenario.inserted.some(([, value]) => /spoof/.test(value))) })
  scenario.games = answered({ games: [{ ...games[0], rom: { ...games[0].rom, sha256: 'sha-two' } }, games[1]], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('a rebuild in chat (new ROM hash) shows the banner', () => { assert.match(text(), /Hermes rebuilt Comet Drift/); assert.match(text(), /Load the new build/) })
  check('the games list polls every 5 s while the Emulator is shown', () => {
    assert.equal(scenario.queries.filter(query => query.key === 'games').at(-1).refetchInterval, 5000)
  })
  await click('Later')
  check('Later hides the banner for that build', () => { assert.ok(!text().includes('Hermes rebuilt')) })
  scenario.player = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the player RPC is reported honestly', () => { assert.match(text(), /older copy of the hermretro backend/); assert.ok(dom.window.document.querySelector('.cs-rp-note')) })
  scenario.player = answered({ error: 'Comet Drift has no web export yet. Ask Hermes in its chat to build it.' })
  await studio.rerender()
  check("the player's own error is shown with a way to build it", () => { assert.match(text(), /has no web export yet/); assert.match(text(), /Build it in chat/) })

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
  await act(async () => { scenario.workspaces.at(-1).close() })
  delete scenario.byMethod['plugin.hermretro.presentations']
  await turnEnd('rt-old')
  check('an older backend without the presentations RPC breaks nothing', () => { assert.equal(scenario.workspaces.length, opened + 1) })
  await studio.close()
})
