import assert from 'node:assert/strict'
import { runScenario } from './harness.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, emit, holdTimers, key, mount, page, scenario, settle, typeInto }) => {
  const id = 'fff666fff666'
  const root = '/home/u/games/FrogPost'
  const first = `${root}/assets/ui/frame.png`
  const second = `${root}/assets/ui/icons.png`
  const session = 'rt-of-st-frog'
  const publish = (type, payload = {}) => act(async () => emit({ type, session_id: session, payload }))

  holdTimers()
  buildScenario({ selected: id })
  scenario.games = answered({ games: [{ id, title: 'Frog Post', projectRoot: root, kind: 'gbstudio', state: 'ready',
    session: { storedId: 'st-frog' } }], device: { hardwareEnabled: false, skipped: true } })
  const report = { title: 'Frog Post', changes: [
    { kind: 'changed', text: 'Frame', asset: first }, { kind: 'changed', text: 'Icons', asset: second }
  ] }
  scenario.byMethod['session.resume'] = params => ({ session_id: session, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', content: 'Edit the pictures', timestamp: 1000 },
    { role: 'assistant', content: '', timestamp: 1001, tool_calls: [{ id: 'r1', function: { name: 'chromatic_build_report', arguments: JSON.stringify(report) } }] },
    { role: 'tool', tool_call_id: 'r1', timestamp: 1005, content: JSON.stringify({ ok: true, report, reportedAt: 1_004_000 }) },
    { role: 'assistant', content: 'Done', timestamp: 1010 }
  ] })
  const live = new Map([[first, '2'], [second, '2']])
  const imageRequests = []
  scenario.byMethod['plugin.hermretro.asset'] = ({ path, version, at }) => {
    const versionId = version ?? (at ? '1' : live.get(path))
    imageRequests.push({ path, version, at, versionId })

    return { ok: true, path, kind: 'ui', name: path.split('/').at(-1), width: 16, height: 16, versionId,
      dataUrl: `data:image/png;base64,${Buffer.from(`${path}#${versionId}`).toString('base64')}` }
  }
  scenario.byMethod['plugin.hermretro.asset_info'] = ({ path }) => ({ ok: true, path, kind: 'ui',
    versions: ['1', '2', ...(live.get(path) === '3' ? ['3'] : [])].map(version => ({ id: version, at: Number(version) * 1_000_000,
      file: `/kept/${version}.png`, current: version === live.get(path) })) })
  const restores = []
  scenario.byMethod['plugin.hermretro.asset_restore'] = params => { restores.push(params); return { ok: true, path: params.path } }
  const submits = []
  let admit
  const receipt = new Promise(resolve => { admit = resolve })
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return receipt }

  const view = await mount(page)
  const dialog = () => view.node.querySelector('.cs-v')
  const control = label => [...dialog().querySelectorAll('button')].find(button => button.textContent.includes(label))
  const shownPath = () => dialog().querySelector('.cs-v-name').title
  const shownVersion = () => dialog().querySelector('.cs-v-ver[aria-pressed="true"]')?.textContent
  await settle()
  const card = view.node.querySelector('.cs-b-bc')
  await click('Details', card)
  await settle()
  const opener = card.querySelector('.cs-b-bc-changes button[aria-label="Look closer at frame.png"]')
  assert.ok(opener)
  await act(async () => opener.click())
  await settle()
  await publish('message.start', { turn_id: 'unrelated-turn' })
  check('Restore is disabled during an unrelated Build turn', () => assert.equal(control('Restore v1')?.disabled, true))
  await click('Restore v1', dialog())
  check('a disabled Restore makes no RPC', () => assert.deepEqual(restores, []))
  await publish('message.complete', { text: 'Finished the other work.' })
  check('Restore is available again after the unrelated turn', () => assert.equal(control('Restore v1')?.disabled, false))

  await click('Change', dialog())
  await typeInto(dialog().querySelector('textarea'), 'Redraw the frame')
  await click('Send to HermRetro', dialog())
  check('the pending Change is shown on its own asset', () => {
    assert.match(dialog().querySelector('.cs-v-pane').textContent, /You askedRedraw the frame/)
    assert.equal(submits.length, 1)
    assert.match(submits[0].text, /frame\.png:\nRedraw the frame/)
  })
  await key('keydown', 'ArrowRight', dialog())
  await typeInto(dialog().querySelector('textarea'), 'Redraw the icons')
  check('another asset stays navigable with Change disabled during submission', () => {
    assert.equal(shownPath(), second)
    assert.equal(control('Send to HermRetro')?.disabled, true)
    assert.doesNotMatch(dialog().querySelector('.cs-v-pane').textContent, /You asked|Redraw the frame/)
  })
  await click('Send to HermRetro', dialog())
  await act(async () => admit({ status: 'queued' }))
  await publish('message.start', { turn_id: 'frame-change' })
  await key('keydown', 'Enter', dialog().querySelector('textarea'))
  check('an admitted viewer change still prevents another submission during the turn', () => {
    assert.equal(control('Send to HermRetro')?.disabled, true)
    assert.equal(submits.length, 1)
  })

  live.set(first, '3')
  await publish('message.complete', { text: 'Redrew the frame.' })
  check('the other image keeps its selected historical version and can now be changed', () => {
    assert.equal(shownVersion(), 'v1')
    assert.equal(control('Send to HermRetro')?.disabled, false)
  })
  await key('keydown', 'ArrowLeft', dialog())
  await settle()
  check('returning to the changed asset shows its refreshed live image', () => {
    assert.equal(shownPath(), first)
    assert.equal(shownVersion(), 'v3')
    assert.ok(imageRequests.some(request => request.path === first && !request.at && !request.version && request.versionId === '3'))
  })
  await view.close()
})
