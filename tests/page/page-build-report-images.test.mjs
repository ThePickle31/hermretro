// Images mentioned only by a build report open the same path and version seen on the card.
// Run alone: node tests/page/page-build-report-images.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'
import { runScenario } from './harness.mjs'

await runScenario(async ({ act, answered, buildScenario, check, key, mount, page, scenario, settle }) => {
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
    report('r2', 2001, [{ kind: 'changed', text: 'Workshop room', asset: `file://${room}` }]),
    { role: 'tool', tool_call_id: 'r2', timestamp: 2005 },
    { role: 'assistant', content: `Made the changes.\nMEDIA:${cover}`, timestamp: 2010 }
  ] })

  const history = [
    { id: '11', at: 1_900_000 }, { id: '12', at: 2_005_000 }, { id: '13', at: 2_200_000, current: true }
  ]
  const kind = path => path === player ? 'sprite' : path === room ? 'background' : 'cover'
  scenario.byMethod['plugin.hermretro.asset'] = ({ path, root, version, at }) => {
    assert.equal(root, projectRoot)
    assert.ok([player, room, cover].includes(path))
    const entry = path === room && (version ? history.find(item => item.id === version) : history.findLast(item => !at || item.at <= at))
    const dataUrl = `data:image/png;base64,${Buffer.from(`${path}#${entry?.id ?? '1'}`).toString('base64')}`

    return { ok: true, path, name: path.split('/').at(-1), kind: kind(path), width: 16, height: 16, dataUrl,
      versionId: entry?.id ?? '1', earlier: Boolean(entry && !entry.current) }
  }
  scenario.byMethod['plugin.hermretro.asset_info'] = ({ path }) => ({ ok: true, path, kind: kind(path), versions: path === room ? history : [] })

  const view = await mount(page)
  await settle()
  const cards = view.node.querySelectorAll('.cs-b-bc')
  const dialog = () => view.node.querySelector('[role="dialog"]')
  const open = async (card, label) => {
    const opener = card.querySelector(`button[aria-label="${label}"]`)
    assert.ok(opener, label)
    await act(async () => opener.click())
    await settle()
  }
  const close = () => key('keydown', 'Escape', dialog())
  const shownPath = () => dialog()?.querySelector('.cs-v-name')?.title
  const shownVersion = () => dialog()?.querySelector('.cs-v-ver[aria-pressed="true"]')?.textContent

  await open(cards[0], 'Look closer at workshop_player.png')
  check('a report-only turn opens the player thumbnail', () => assert.equal(shownPath(), player))
  await key('keydown', 'ArrowRight', dialog())
  check('the viewer steps to the other report image', () => assert.equal(shownPath(), room))
  await close()
  await open(cards[0], 'Look closer at workshop.png')
  check('the second thumbnail of a report-only turn opens the room', () => assert.equal(shownPath(), room))
  await close()

  await open(cards[1], 'Look closer at workshop.png')
  check('the report thumbnail opens the exact room instead of the reply cover', () => {
    assert.equal(shownPath(), room)
    assert.equal(shownVersion(), 'v3')
  })
  await close()

  for (const [label, version] of [['before', 'v1'], ['after', 'v2']]) {
    await open(cards[1], `Look closer at ${label} version of workshop.png`)
    check(`the ${label} image opens the room at ${version}`, () => {
      assert.equal(shownPath(), room)
      assert.equal(shownVersion(), version)
    })
    await close()
  }
  await view.close()
})
