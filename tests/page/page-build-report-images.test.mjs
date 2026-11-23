// Images mentioned only by a build report open the same path and version seen on the card.
// Run alone: node tests/page/page-build-report-images.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'
import { runScenario } from './harness.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, dom, emit, key, mount, page, scenario, settle }) => {
  const game = 'fff666fff666'
  const projectRoot = '/home/u/games/TinkerShop'
  const player = `${projectRoot}/assets/sprites/workshop_player.png`
  const room = `${projectRoot}/assets/backgrounds/workshop.png`
  const cover = `${projectRoot}/cover.png`
  const report = (id, timestamp, changes) => ({
    role: 'assistant', content: '', timestamp, tool_calls: [{
      id, function: { name: 'chromatic_build_report', arguments: JSON.stringify({ title: 'Tinker Shop', changes }) }
    }]
  })
  const roomChange = [{ kind: 'changed', text: 'Workshop room', asset: `file://${room}` }]
  const playerChange = { kind: 'changed', text: 'Workshop player', asset: player }
  const reportResult = reportedAt => ({ ok: true, reportedAt, report: { title: 'Tinker Shop', changes: roomChange } })

  buildScenario({ selected: game })
  scenario.games = answered({ games: [{ id: game, title: 'Tinker Shop', projectRoot, kind: 'gbstudio', state: 'ready',
    rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-tinker' } }],
  device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', content: 'Make the shop and its player.', timestamp: 1000 },
    report('r1', 1001, [{ kind: 'added', text: 'Workshop player', asset: 'assets/sprites/workshop_player.png' },
      { kind: 'added', text: 'Workshop room', asset: `file://${room}` }]),
    { role: 'tool', tool_call_id: 'r1', timestamp: 1005 },
    { role: 'assistant', content: 'The shop is ready.', timestamp: 1010 },
    { role: 'user', content: 'Edit the workshop room.', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [{ id: 'r2', function: {
      name: 'tool_call', arguments: JSON.stringify({ calls: [{
        name: 'chromatic_build_report', arguments: { title: 'Tinker Shop', changes: [...roomChange, playerChange] }
      }] })
    } }] },
    { role: 'tool', tool_call_id: 'r2', tool_name: 'chromatic_build_report', timestamp: 2007, content: JSON.stringify({ ...reportResult(2_005_001.625),
      report: { title: 'Tinker Shop', changes: [...roomChange, playerChange] } }) },
    { role: 'assistant', content: `Made the changes.\nMEDIA:${cover}`, timestamp: 2010 }
  ] })

  const history = [
    { id: '10', at: 1_004_000 }, { id: '11', at: 1_900_000 }, { id: '12', at: 2_004_000 },
    { id: '13', at: 2_006_000 }, { id: '14', at: 2_200_000, current: true }
  ]
  const playerHistory = [{ id: '21', at: 1_004_000 }, { id: '22', at: 2_003_000 }, { id: '23', at: 2_200_000, current: true }]
  let liveRoom = history.at(-1)
  let liveReadsAfterRestore = 0
  const kind = path => path === player ? 'sprite' : path === room ? 'background' : 'cover'
  const imageUrl = (path, id) => `data:image/png;base64,${Buffer.from(`${path}#${id}`).toString('base64')}`
  scenario.byMethod['plugin.hermretro.asset'] = ({ path, root, version, at }) => {
    assert.equal(root, projectRoot)
    assert.ok([player, room, cover].includes(path))
    const versions = path === room ? history : path === player ? playerHistory : []
    const live = path === room ? liveRoom : versions.at(-1)
    const entry = version ? versions.find(item => item.id === version) : at ? versions.findLast(item => item.at <= at) : live
    const dataUrl = imageUrl(path, entry?.bytesId ?? entry?.id ?? '1')

    if (path === room && liveRoom.id === '15' && !at && !version) {
      liveReadsAfterRestore += 1
    }

    return { ok: true, path, name: path.split('/').at(-1), kind: kind(path), width: 16, height: 16, dataUrl,
      versionId: entry?.id ?? '1', earlier: Boolean(entry && entry !== live) }
  }
  scenario.byMethod['plugin.hermretro.asset_info'] = ({ path }) => ({
    ok: true, path, kind: kind(path), versions: path === room ? (liveRoom.id === '15' ? [] : history) : path === player ? playerHistory : []
  })
  scenario.byMethod['plugin.hermretro.asset_restore'] = ({ path, version }) => {
    assert.equal(path, room)
    assert.equal(version, '10')
    liveRoom = { id: '15', bytesId: version, current: true }

    return { ok: true, path, versions: [] }
  }

  // jsdom needs a stand-in for decoding images and drawing the viewer's stage.
  const imagePrototype = dom.window.HTMLImageElement.prototype
  const imageSrc = Object.getOwnPropertyDescriptor(imagePrototype, 'src')
  Object.defineProperties(imagePrototype, {
    src: { ...imageSrc, set(value) { imageSrc.set.call(this, value); queueMicrotask(() => this.onload?.()) } },
    naturalWidth: { get: () => 16 },
    naturalHeight: { get: () => 16 }
  })
  dom.window.HTMLCanvasElement.prototype.getContext = function () {
    return {
      clearRect() {},
      drawImage: image => { this.dataset.imageSrc = image.src },
      getImageData: () => ({ data: [] })
    }
  }

  const view = await mount(page)
  await settle()
  const cards = view.node.querySelectorAll('.cs-b-bc')
  assert.equal(cards.length, 2)
  check('the result features the room comparison and keeps additional edits folded', () => {
    assert.equal(cards[1].querySelectorAll('.cs-b-ba').length, 1)
    assert.ok(cards[1].querySelector('button[aria-label="Look closer at before version of workshop.png"]'))
    assert.equal(cards[1].querySelector('.cs-b-bc-details'), null)
  })
  for (const card of cards) {
    await click('Details', card)
  }
  const dialog = () => view.node.querySelector('[role="dialog"]')
  const thumbnail = (card, label) => {
    const area = label.includes('version of') ? card : card.querySelector('.cs-b-bc-changes')
    return area?.querySelector(`button[aria-label="${label}"]`)
  }
  const open = async (card, label) => {
    const opener = thumbnail(card, label)
    assert.ok(opener, label)
    await act(async () => opener.click())
    await settle()
  }
  const close = () => key('keydown', 'Escape', dialog())
  const shownPath = () => dialog()?.querySelector('.cs-v-name')?.title
  const shownVersion = () => dialog()?.querySelector('.cs-v-ver[aria-pressed="true"]')?.textContent
  const stageImage = () => dialog()?.querySelector('.cs-v-canvas canvas')?.dataset.imageSrc
  const roomLabel = 'Look closer at workshop.png'

  check('each report thumbnail shows the room at the report time', () => {
    assert.equal(thumbnail(cards[0], roomLabel).querySelector('img').src, imageUrl(room, '10'))
    assert.equal(thumbnail(cards[1], roomLabel).querySelector('img').src, imageUrl(room, '12'))
  })

  await open(cards[0], 'Look closer at workshop_player.png')
  check('a report-only turn opens the player thumbnail', () => assert.equal(shownPath(), player))
  await key('keydown', 'ArrowRight', dialog())
  check('the viewer steps to the other report image at the report time', () => {
    assert.equal(shownPath(), room)
    assert.equal(shownVersion(), 'v1')
  })
  await close()
  await open(cards[0], roomLabel)
  check('the second thumbnail of a report-only turn opens the room', () => assert.equal(shownPath(), room))
  await close()

  await open(cards[1], roomLabel)
  check('the report thumbnail opens the room at the version on the card', () => {
    assert.equal(shownPath(), room)
    assert.equal(shownVersion(), 'v3')
  })
  await close()

  for (const [label, version] of [['before', 'v2'], ['after', 'v4']]) {
    await open(cards[1], `Look closer at ${label} version of workshop.png`)
    check(`the ${label} image opens the room at ${version}`, () => {
      assert.equal(shownPath(), room)
      assert.equal(shownVersion(), version)
    })
    await close()
  }

  await open(cards[1], 'Look closer at after version of workshop_player.png')
  check('Details keeps the additional comparison at the end-of-turn version', () => {
    assert.ok(cards[1].querySelector('.cs-b-bc-details button[aria-label="Look closer at after version of workshop_player.png"]'))
    assert.equal(shownPath(), player)
    assert.equal(shownVersion(), 'v2')
  })
  await close()

  const session_id = 'rt-of-st-tinker'
  await act(async () => {
    emit({ type: 'message.start', session_id })
    emit({ type: 'tool.complete', session_id, payload: {
      tool_id: 'late-report', name: 'chromatic_build_report',
      result: reportResult(2_005_002.625)
    } })
    emit({ type: 'message.complete', session_id, payload: { text: 'The delayed report is ready.' } })
  })
  await settle()
  const liveCard = [...view.node.querySelectorAll('.cs-b-bc')].at(-1)
  await click('Details', liveCard)
  check('a delayed completion shows the image from the Hermes report time', () => {
    assert.equal(thumbnail(liveCard, roomLabel).querySelector('img').src, imageUrl(room, '12'))
  })
  await open(liveCard, roomLabel)
  check('the delayed report opens the same image shown on the card', () => assert.equal(shownVersion(), 'v3'))
  await close()

  await open(cards[0], roomLabel)
  await click('Restore v1', dialog())
  await settle()
  check('Restore loads and shows the live bytes when refreshed history is empty', () => {
    assert.ok(liveReadsAfterRestore > 0)
    assert.equal(stageImage(), imageUrl(room, '10'))
  })
  await key('keydown', 'ArrowRight', dialog())
  await settle()
  check('moving after Restore opens the other asset at its report version', () => {
    assert.equal(shownPath(), player)
    assert.equal(shownVersion(), 'v1')
    assert.equal(stageImage(), imageUrl(player, '21'))
  })
  await close()
  await view.close()
})
