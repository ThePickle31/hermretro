// The Build page's Builds menu (page/pages/build/builds-menu.js): each build of the conversation, and whether
// the backend kept its files (plugin.hermretro.builds). A build's startAt/endAt are page times in milliseconds
// (a message's `timestamp`, Unix seconds, × 1000), and so is a snapshot's `at`/`builds`: a snapshot matches a build
// when one of its times falls from 2 s before the turn started to 5 s after it ended.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, buildScenario, holdTimers, scenario, page, click, settle, key, mount, check, answered, installAnswer }) => {
  buildScenario({ selected: 'fff666fff666' })
  scenario.games = answered({ games: [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } },
    { id: 'ddd666ddd666', title: 'Cloud Hop', projectRoot: '/home/u/games/CloudHop', kind: 'gbstudio', state: 'ready',
      rom: null, webExport: true, session: { storedId: 'st-cloud' } }],
  device: { hardwareEnabled: false, skipped: true } })
  const callOf = (id, name) => ({ id, function: { name, arguments: '{}' } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', content: 'make the frog jump', timestamp: 1000 },
    { role: 'assistant', content: '', timestamp: 1001, tool_calls: [callOf('b1', 'chromatic_rom_build')] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 1020 },
    { role: 'assistant', content: 'It jumps.', timestamp: 1030 },
    { role: 'user', content: 'make it jump higher', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b2', 'chromatic_rom_build')] },
    { role: 'tool', tool_call_id: 'b2', content: JSON.stringify({ ok: true }), timestamp: 2020 },
    { role: 'assistant', content: '', timestamp: 2021, tool_calls: [callOf('frames', 'chromatic_emulator_step')] },
    { role: 'tool', tool_call_id: 'frames', content: JSON.stringify({ images: [
      { file: 'MEDIA:/home/u/games/FrogPost/playtests/start.png' }, { file: 'MEDIA:/home/u/games/FrogPost/playtests/end.png' }, { file: 'MEDIA:/home/u/games/FrogPost/playtests/start.png' }
    ] }), timestamp: 2022 },
    { role: 'assistant', content: 'Higher now.\nMEDIA:/home/u/games/FrogPost/jump.wav', timestamp: 2030 }] })
  const asked = []
  let snapshots = []
  scenario.byMethod['plugin.hermretro.builds'] = params => { asked.push(params); return { ok: true, builds: snapshots } }
  let releaseImage
  const slowImage = new Promise(resolve => { releaseImage = resolve })
  scenario.byMethod['plugin.hermretro.asset'] = async ({ path }) => {
    if (path.endsWith('/end.png')) await slowImage
    return { ok: true, path, name: path.split('/').pop(), width: 160, height: 144, dataUrl: 'data:image/png;base64,iVBORw0KGgo=' }
  }
  const view = await mount(page)
  await settle(100)
  check('a captured frame sequence is a result with the work log folded', () => {
    assert.equal(view.node.querySelector('.cs-b-wk-head').getAttribute('aria-expanded'), 'false')
    assert.equal(view.node.querySelector('input[aria-label="Playtest frame"]').max, '3')
    assert.match(view.node.querySelector('.cs-b-replay').textContent, /Frame 1 of 3/)
  })
  const clock = holdTimers(350)
  await click('Replay frames', view.node.querySelector('.cs-b-replay'))
  await clock.fire()
  await clock.fire()
  check('an audio reply keeps its replay and the replay waits for an uncached frame', () => {
    assert.match(view.node.textContent, /jump\.wav/)
    assert.match(view.node.querySelector('.cs-b-replay').textContent, /Frame 2 of 3.*Pause/)
  })
  await click('Pause', view.node.querySelector('.cs-b-replay'))
  await act(async () => releaseImage())
  await settle()
  assert.match(view.node.querySelector('.cs-b-replay').textContent, /Frame 2 of 3.*Resume/)
  await click('Resume', view.node.querySelector('.cs-b-replay'))
  await clock.fire()
  await clock.fire()
  check('the sequence retains the repeated first capture at the end', () => {
    const result = view.node.querySelector('.cs-b-replay')
    assert.match(result.textContent, /Frame 3 of 3.*Replay frames/)
    assert.ok(result.querySelector('button[aria-label="Look closer at start.png"]'))
  })
  const openMenu = async () => {
    await click('Builds', view.node.querySelector('.cs-b-head'))
    await settle(30)
    const rows = [...view.node.querySelectorAll('.cs-b-brow')]
    const restore = rows[1] && [...rows[1].querySelectorAll('button')].find(node => node.textContent === 'Restore')
    await key('keydown', 'Escape')
    return { rows: rows.map(node => node.textContent), restore }
  }

  // Build #1's turn ran from 1000 s to 1030 s: a snapshot at 1 010 000 ms is its files.
  snapshots = [{ id: 'snap-1', at: 1_010_000, builds: [1_010_000], reason: 'build' }]
  const kept = await openMenu()
  check('the Builds menu asks plugin.hermretro.builds for this game and lists the builds newest first', () => {
    assert.deepEqual(asked.at(-1), { game: 'fff666fff666' })
    assert.equal(kept.rows.length, 2); assert.match(kept.rows[0], /#2make it jump higher/); assert.match(kept.rows[1], /#1make the frog jump/)
  })
  check('a snapshot taken during build #1 (in milliseconds) lets it be restored', () => {
    assert.ok(kept.restore, 'build #1 has a Restore button'); assert.equal(kept.restore.disabled, false)
  })
  // The same time in seconds matches no build: snapshot times are milliseconds, as the page's are.
  snapshots = [{ id: 'snap-1', at: 1010, builds: [1010], reason: 'build' }]
  const lost = await openMenu()
  check('a snapshot from outside the build\u2019s turn matches nothing, so Restore stays disabled', () => {
    assert.ok(lost.restore); assert.equal(lost.restore.disabled, true)
  })
  await click('Builds', view.node.querySelector('.cs-b-head'))
  await settle()
  await click('Show', view.node.querySelectorAll('.cs-b-brow')[1])
  assert.equal(view.node.querySelector('.cs-b-history-row').getAttribute('aria-expanded'), 'true')
  await act(async () => view.node.querySelector('.cs-b-sw').click())
  await click('Cloud Hop', view.node.querySelector('.cs-b-sw-pop'))
  await settle()
  check('another game with the same turn keys starts with its own folded history', () => {
    assert.equal(view.node.querySelector('.cs-b-sw h2').textContent, 'Cloud Hop')
    assert.equal(view.node.querySelector('.cs-b-history-row').getAttribute('aria-expanded'), 'false')
  })
  await view.close()

  // While hermretro updates, Restore (which restores files and sends a build request) and the chat box start nothing.
  snapshots = [{ id: 'snap-1', at: 1_010_000, builds: [1_010_000], reason: 'build' }]
  scenario.status = answered({ ...scenario.status.data, plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
  scenario['plugin-update'] = answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: true, update_target: 'abc' } })
  scenario['update-busy'] = answered([])
  scenario.install = installAnswer({ state: 'idle' })
  scenario.byMethod['plugin.hermretro.install'] = () => scenario.install.data
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  let finish
  scenario.byMethod['plugins.manage'] = params => (params.action === 'update' ? new Promise(resolve => { finish = resolve }) : { ok: true })
  const updating = await mount(page)
  await settle(100)
  await click('Update ready', updating.node); await click('Update now', updating.node); await settle(40)
  await click('Builds', updating.node.querySelector('.cs-b-head')); await settle(30)
  check('while updating, the Builds menu cannot restore a build', () => {
    const buttons = [...updating.node.querySelectorAll('.cs-b-brow button')].filter(node => node.textContent === 'Restore')
    assert.ok(buttons.length, 'Restore buttons are shown'); assert.ok(buttons.every(node => node.disabled), 'every Restore is disabled')
  })
  check('while updating, the chat box sends nothing', () => {
    assert.equal(updating.node.querySelector('.cs-b-chat textarea')?.disabled, true)
  })
  await key('keydown', 'Escape')
  await settle(10)
  finish({ ok: true, unchanged: true }); await settle(40)
  await updating.close()
})
