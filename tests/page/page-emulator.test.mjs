// The Emulator page fed by the games / player RPCs: the demo cartridge, the player's notices, Play from the shelf,
// keys, annotations and the rebuilt banner (starting state: games-fixture.mjs).
// Run alone: node tests/page/page-emulator.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, dom, plugin, scenario, page, text, click, nav, tab, currentTab, settle, button, key, check, answered, notLoaded, complete } = helpers
  const { games, studio } = await gamesStudio(helpers)
  scenario.status = answered({ ...complete, hardware_enabled: true })
  await studio.rerender()
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
  await studio.close()
})
